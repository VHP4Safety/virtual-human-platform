"""JSON Schemas of the records of each kind, for the OpenAPI description, made from the fields of the profile that the
record editor also uses. The values are described as the API writes them in JSON-LD: a link is {"@id": ...}, a field
with several values has one value or an array, a list is an array or {"@list": [...]}, and a typed value may be
{"@value": ..., "@type": ...}. The fields that the profiles require or recommend are named in x-required and
x-recommended, not in required: the API stores a record without them, with a warning.

To be made by the JSON Schema export of rdfsolve once it is released."""

import re
from functools import cache

from rdflib.namespace import XSD

from database.records import browsed
from linkeddata.profile import fields, jsonld_name, settings, shape_fields, terms
from rdfsolve.iris import local_name

REF = "#/components/schemas/"
# The JSON type of each datatype that is not a text.
TYPES = {str(XSD.integer): {"type": "integer"}, str(XSD.boolean): {"type": "boolean"}, str(XSD.decimal): {"type": "number"},
         str(XSD.double): {"type": "number"}, str(XSD.float): {"type": "number"}, str(XSD.date): {"type": "string", "format": "date"},
         str(XSD.dateTime): {"type": "string", "format": "date-time"}, str(XSD.anyURI): {"type": "string", "format": "iri"}}
SHARED = {
    "Link": {"type": "object", "required": ["@id"], "description": "A link to a record, a term or a page.", "properties": {
        "@id": {"type": "string", "format": "iri"},
        "@type": {"description": "The class of the linked record, in responses.", "readOnly": True},
        "name": {"type": "string", "description": "The name of the linked record, in responses.", "readOnly": True}}},
    "Value": {"type": "object", "required": ["@value"], "description": "A value with its datatype, such as a year.", "properties": {
        "@value": {"type": "string"}, "@type": {"type": "string", "format": "iri", "description": "The datatype."}}},
    "Types": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}], "description": "The class, or the classes, by their JSON-LD names."},
}


def plain(text: str) -> str:
    """Return a description as one line of plain text, without the HTML of schema.org, such as <a class="localLink">."""
    return " ".join(re.sub(r"<[^>]+>", "", text).split())


def name_of(shape: str) -> str:
    """Return the name of the schema of a node shape of parts, such as CaseStudy.HowTo or LabProtocol.howtostep."""
    profile, _, fragment = shape.partition("#")
    return f"{profile.rstrip('/').split('/')[-2]}.{fragment.rsplit('/', 1)[-1]}"


def kind_name(of_class: str) -> str:
    """Return the name of the schema of the records of a class, such as SoftwareApplication."""
    return local_name(of_class)


def value(field: dict) -> dict:
    """Return the schema of one value of a field."""
    if field["values"] or field["fixed"]:
        listed = field["fixed"] or field["values"]
        if field["iris"] or field["address"]:
            return {"type": "object", "required": ["@id"], "properties": {"@id": {"type": "string", "enum": listed}}}
        return {"type": "string", "enum": listed}
    choices = [{"$ref": REF + name_of(node)} for node in field["parts"].values()]
    if field["links"] or field["address"]:
        choices.append({"$ref": REF + "Link"})
    if field["texts"]:
        typed = TYPES.get(field["datatype"]) if field["datatype"] else None
        choices += [typed or {"type": "string"}, {"$ref": REF + "Value"}]
    return choices[0] if len(choices) == 1 else {"anyOf": choices}


def field_schema(field: dict) -> dict:
    """Return the schema of a field: one value, an ordered list, or one value or an array."""
    one = value(field)
    if field["list"]:
        listed = {"type": "array", "items": one}
        schema = {"anyOf": [listed, {"type": "object", "required": ["@list"], "properties": {"@list": listed}}]}
    elif field["single"]:
        schema = dict(one)
    else:
        schema = {"anyOf": [one, {"type": "array", "items": one}]}
    notes = [field["description"]]
    if field["links"]:
        notes.append("A link to a record: " + ", ".join(field["links"].values()) + ".")
    if field["required"]:
        notes.append("Required by the profile.")
    elif field["recommended"]:
        notes.append("Recommended by the profile.")
    if field["iri"] in settings()["private"]:
        notes.append("Returned to editors only.")
    schema = {"title": field["label"], **schema, "description": plain(" ".join(note for note in notes if note))}
    if field["read_only"]:
        schema["readOnly"] = True
    return schema


def object_schema(listed: list[dict], title: str, description: str, of_class: str | None = None) -> dict:
    """Return the schema of a record or a part with the fields in listed."""
    properties = {"@id": {"type": "string", "format": "iri", "description": "The address. The API makes it from the name for a new record."},
                  "@type": {"$ref": REF + "Types"}}
    for field in listed:
        properties[field["name"]] = field_schema(field)
    schema = {"type": "object", "title": title, "description": plain(description), "properties": properties}
    for level in ("required", "recommended"):
        named = [field["name"] for field in listed if field[level]]
        if named:
            schema[f"x-{level}"] = named
    if of_class:
        schema["x-class"] = of_class
        schema["x-type"] = jsonld_name(of_class)
    return schema


@cache
def schemas() -> dict[str, dict]:
    """Return the schema of the records of each kind and of each part they hold, by name."""
    found = dict(SHARED)
    waiting = []
    for of_class in settings()["kinds"].values():
        about = terms([of_class]).get(of_class, {}).get("description", "")
        found[kind_name(of_class)] = object_schema(fields(of_class), settings()["labels"][of_class], about, of_class)
        waiting += [node for field in fields(of_class) for node in field["parts"].values()]
    while waiting:
        node = waiting.pop(0)
        if name_of(node) in found:
            continue
        listed = shape_fields(node)
        found[name_of(node)] = object_schema(listed, name_of(node), f"A part, with the fields of the shape {node}.")
        waiting += [shape for field in listed for shape in field["parts"].values()]
    return found


def filters(of_class: str) -> list[dict]:
    """Return a query parameter for each field that filters the records of a class."""
    found = []
    for field in fields(of_class):
        if not browsed(field):
            continue
        item = {"type": "string"}
        if field["iris"]:
            item["format"] = "iri"
        if field["values"]:
            item["enum"] = field["values"]
        found.append({"in": "query", "name": field["name"], "required": False, "style": "form", "explode": True,
                      "description": f"{field['label']}: the records with any of these values. The field {field['name']} of the schema {kind_name(of_class)}.",
                      "schema": {"type": "array", "items": item}})
    return found
