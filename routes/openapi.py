"""The OpenAPI document of the platform's API, made from the code and the model when it is asked for. Every
route under /api/ is described by its view: the first paragraph of its docstring is its summary, the rest
its description, and `described` gives what it answers, reads and needs. The records' schemas come from
the application profile and the vocabularies, as the editor's form does (forms.py), and the examples from
the records that fit the model. A route that is not described makes the document fail, so that no route is
left out."""

import inspect
import re
import sys
from http import HTTPStatus

from flask import current_app, request
from sqlalchemy import select

import database
from admin import tokens
from admin.writes import IDENTIFIER
from database.tables import Note, Record, Source
from linkeddata import forms, rdf, tables
from linkeddata.model import RELEASE, settings, terms

# The records whose documents are read for the examples of a kind.
SAMPLE = 100
# Entries of the editor's form whose values are only links.
LINKED = ("links", "choice", "address", "addresses", "image", "details", "fixed")
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"
LANGUAGE_STRING = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"


def described(answers: dict, kinds: str | None = None, body: str | None = None, query: dict | None = None,
              headers: dict | None = None, token: bool = False, filters: bool = False):
    """The description of a view for the OpenAPI document. *answers* gives, for each status, the schemas of
    the answer (names of `answer_schemas`) and when it is given; *kinds* the kinds of records that <kind>
    stands for ("listed" or "writable"); *body* what the request sends ("record", "move" or "image");
    *query* and *headers* other parameters, by name, as (schema, description); *token* whether a write
    token is needed; and *filters* whether each field of the kind is a query parameter."""
    def mark(view):
        view.openapi = {"answers": answers, "kinds": kinds, "body": body, "query": query or {},
                        "headers": headers or {}, "token": token, "filters": filters}
        return view
    return mark


def ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def local(iri: str) -> str:
    return re.split(r"[/#]", iri)[-1]


def paragraphs(text: str) -> str:
    """A docstring's text with its lines joined into paragraphs, for Markdown."""
    joined = []
    for block in text.strip().split("\n\n"):
        if block.startswith("    "):
            joined.append(block)
        else:
            joined.append(" ".join(block.split()))
    return "\n\n".join(joined)


def first_paragraph(text: str) -> str:
    """The first paragraph of a vocabulary's explanation of a term, which says what the term is."""
    return " ".join(text.strip().split("\n\n")[0].split())


def plain(value):
    """A value of a document as a query parameter takes it: the address of a link, or the text of a value."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        return value.get("@id", value.get("@value"))
    return value


def samples(kind: str) -> list[dict]:
    """The documents of some records of a class that fit the model, the fullest first, for the examples."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.type == kind, Record.removed_at.is_(None)).order_by(Record.iri).limit(SAMPLE)))
        noted = set(db.scalars(select(Note.iri).where(Note.iri.in_(iris))))
    fitting = []
    for iri in iris:
        if iri not in noted:
            fitting.append(iri)
    found = tables.graph(fitting)
    documents = []
    for iri in fitting:
        document = forms.shaped(rdf.document(found, iri), kind)
        document.pop("@context", None)
        documents.append(document)
    documents.sort(key=lambda document: -len(document))
    return documents


def example(documents: list[dict], name: str):
    for document in documents:
        if name in document:
            return document[name]
    return None


def literal(datatype: str, field: dict) -> dict:
    """The schema of a value of a datatype: a text, a text in a language, or a value with its datatype."""
    if datatype == XSD_STRING:
        schema = {"type": "string"}
        if field["pattern"]:
            schema["pattern"] = field["pattern"]
        return schema
    if datatype == LANGUAGE_STRING:
        return ref("LanguageText")
    return {"allOf": [ref("TypedValue"), {"properties": {"@type": {"const": datatype}}}]}


def link(field: dict, writing: bool) -> dict:
    if field["pattern"]:
        return {
            "type": "object",
            "required": ["@id"],
            "properties": {"@id": {"type": "string", "format": "uri", "pattern": field["pattern"]}},
            "additionalProperties": False,
        }
    if writing and field["entry"] == "details":
        return ref("TitledLink")
    return ref("Link")


def value(field: dict, writing: bool) -> dict:
    """The schema of one value of a field, from the values that its shapes allow; in the body of a write, a
    field that takes links also takes web addresses."""
    if field["fixed"]:
        return {"type": "object", "required": ["@id"], "properties": {"@id": {"enum": field["fixed"]}}}
    if field["options"]:
        return {"type": "string", "enum": field["options"]}
    options = []
    if field["entry"] in LINKED:
        options.append(link(field, writing))
    else:
        for datatype in field["datatypes"]:
            options.append(literal(datatype, field))
        if field["links"]:
            options.append(link(field, writing))
    if writing and field["links"]:
        options.append({"type": "string", "format": "uri", "description": "A web address, kept as a link."})
    if len(options) == 1:
        return options[0]
    return {"anyOf": options}


def explained(field: dict) -> str:
    """What a field holds, from the profile and the model: its explanation, what it links to, and whether it
    is required, recommended or set by the platform."""
    parts = []
    if field["help"]:
        parts.append(field["help"])
    names = {}
    for name, kind in settings()["kinds"].items():
        names[kind] = name
    targets = []
    if field["links"] and not field["options"]:
        for target in field["classes"]:
            shown = f"{local(target)} (/api/{names[target]})" if target in names else local(target)
            if shown not in targets:
                targets.append(shown)
    if targets:
        parts.append("Links to records of the classes " + ", ".join(targets) + ".")
    found = terms(field["terms"])
    if found:
        listed = []
        for iri, term in found.items():
            listed.append(f"{term['name']} <{iri}>")
        title = list(found.values())[0]["title"]
        parts.append(f"Links to these terms of {title}: " + "; ".join(listed) + ".")
    if field["fixed"]:
        parts.append("Set by the platform.")
    elif field["required"]:
        parts.append("Required.")
    elif field["recommended"]:
        parts.append("Recommended.")
    if field["message"]:
        parts.append(field["message"])
    return " ".join(parts)


def field_schema(field: dict, documents: list[dict], writing: bool) -> dict:
    """The schema of a field. A record keeps the values of its sources as they are given, so a record that
    the API gives can also have values that do not fit the model, which /api/notes notes; a write takes only
    values that fit."""
    item = value(field, writing)
    if not writing:
        item = {"anyOf": [item, ref("AsGiven")]}
    if field["several"]:
        schema = {"type": "array", "items": item, "uniqueItems": True}
    elif writing:
        schema = dict(item)
    else:
        several = {"type": "array", "items": ref("AsGiven"), "description": "Several values where the model takes one, as the source gives them."}
        schema = {"anyOf": [*item["anyOf"], several]}
    schema["title"] = field["label"]
    schema["description"] = explained(field)
    schema["externalDocs"] = {"description": field["property"], "url": field["iri"]}
    found = example(documents, field["name"])
    if found is not None:
        schema["examples"] = [found]
    return schema


def record_schemas(name: str, kind: str, documents: list[dict]) -> dict:
    """The schemas of a kind's records: as the API gives them, as the body of a write when the kind is
    written through the API, and as a page of them."""
    title = local(kind)
    described_class = terms([kind]).get(kind, {})
    properties = {
        "@context": {"description": "The JSON-LD context of the document, when it is not given by a collection."},
        "@id": {"type": "string", "format": "uri", "readOnly": True, "description": "The record's address."},
        "@type": {
            "anyOf": [{"const": rdf.term(kind)}, {"type": "array", "contains": {"const": rdf.term(kind)}}],
            "description": "The class of the record.",
        },
    }
    body = {}
    required = []
    for field in forms.form(kind):
        properties[field["name"]] = field_schema(field, documents, False)
        if not field["fixed"]:
            body[field["name"]] = field_schema(field, documents, True)
            if field["required"]:
                required.append(field["name"])
    explanation = first_paragraph(described_class.get("description", ""))
    record = {
        "type": "object",
        "title": described_class.get("name", title),
        "description": f"{explanation} The records of /api/{name}.".strip(),
        "externalDocs": {"url": kind},
        "required": ["@id", "@type"],
        "properties": properties,
        "additionalProperties": True,
    }
    if documents:
        record["examples"] = [documents[0]]
    collection = {
        "type": "object",
        "title": f"A page of the records of /api/{name}",
        "required": ["@context", "@id", "@type", "hydra:totalItems", "hydra:member", "hydra:view"],
        "properties": {
            "@context": {"type": "object", "description": "The JSON-LD context of the page and of its records."},
            "@id": {"type": "string", "format": "uri", "description": "The address of the records that the filters give."},
            "@type": {"const": "hydra:Collection"},
            "hydra:totalItems": {"type": "integer", "minimum": 0, "description": "How many records the filters give."},
            "hydra:member": {"type": "array", "items": ref(title), "description": "The records of this page."},
            "hydra:view": ref("PartialCollectionView"),
        },
    }
    found = {title: record, title + "Collection": collection}
    if name in settings().get("writable", {}):
        written = {
            "type": "object",
            "title": f"A record of /api/{name}, as it is written",
            "description": "The fields of the record; a field that is not one of these is refused. Fields set by the platform are left out.",
            "required": required,
            "properties": body,
            "patternProperties": {"^@": {"description": "Keys of JSON-LD, such as @id or @context, are read but not kept."}},
            "additionalProperties": False,
        }
        if documents:
            given = {}
            for key, kept in documents[0].items():
                if key in body:
                    given[key] = kept
            written["examples"] = [given]
        found[title + "Body"] = written
    return found


def table_schema(model) -> dict:
    """The schema of a row of a table of the database, from its columns and their documentation."""
    properties = {}
    required = []
    for column in model.__table__.columns:
        kind = "integer" if column.type.python_type is int else "string"
        properties[column.name] = {"type": [kind, "null"] if column.nullable else kind}
        if column.doc:
            properties[column.name]["description"] = column.doc
        if not column.nullable:
            required.append(column.name)
    return {"type": "object", "description": paragraphs(inspect.getdoc(model) or ""), "required": required, "properties": properties}


def shared_schemas() -> dict:
    identifier = {"type": "string", "pattern": f"^{IDENTIFIER.pattern}$"}
    return {
        "Link": {
            "type": "object",
            "description": "A link to a record or to a page elsewhere, by its address.",
            "required": ["@id"],
            "properties": {"@id": {"type": "string", "format": "uri"}},
            "additionalProperties": False,
        },
        "TitledLink": {
            "type": "object",
            "description": "A link to a page with its title, which the platform keeps as the page's name.",
            "required": ["@id"],
            "properties": {"@id": {"type": "string", "format": "uri"}, "name": {"type": "string"}},
            "additionalProperties": False,
        },
        "LanguageText": {
            "type": "object",
            "description": "A text in a language, with the language's tag (BCP 47).",
            "required": ["@value", "@language"],
            "properties": {"@value": {"type": "string"}, "@language": {"type": "string"}},
            "additionalProperties": False,
        },
        "TypedValue": {
            "type": "object",
            "description": "A value with its datatype, such as a date.",
            "required": ["@value", "@type"],
            "properties": {"@value": {"type": "string"}, "@type": {"type": "string", "format": "uri"}},
            "additionalProperties": False,
        },
        "AsGiven": {
            "description": "A value that does not fit the model, as its source gives it; /api/notes notes it.",
            "anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}, ref("Link"), ref("LanguageText"), ref("TypedValue")],
        },
        "PartialCollectionView": {
            "type": "object",
            "description": "This page of a collection, and the addresses of the first, previous, next and last pages.",
            "required": ["@id", "@type", "hydra:first", "hydra:last"],
            "properties": {
                "@id": {"type": "string", "format": "uri"},
                "@type": {"const": "hydra:PartialCollectionView"},
                "hydra:first": {"type": "string", "format": "uri"},
                "hydra:previous": {"type": "string", "format": "uri"},
                "hydra:next": {"type": "string", "format": "uri"},
                "hydra:last": {"type": "string", "format": "uri"},
            },
        },
        "Error": {
            "type": "object",
            "description": "Why a request is refused.",
            "required": ["error"],
            "properties": {"error": {"type": "string"}},
        },
        "Problems": {
            "type": "object",
            "description": "A record that does not fit the model, with what is wrong with each field.",
            "required": ["error"],
            "properties": {
                "error": {"type": "string"},
                "fields": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
            },
        },
        "Done": {
            "type": "object",
            "description": "A change that is saved.",
            "required": ["@id", "change", "version", "warnings"],
            "properties": {
                "@id": {"type": "string", "format": "uri", "description": "The record's address."},
                "change": {"type": "string", "description": "The path of the change's page; with .json, the change as JSON."},
                "version": {"type": ["string", "null"], "description": "The record's version, to send back in If-Match."},
                "warnings": {
                    "type": "object",
                    "description": "What is recommended, by field.",
                    "additionalProperties": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "Preview": {
            "type": "object",
            "description": "What a write would change, saving nothing: the statements about the record before and after it, as edges from the record to each value, and what is wrong with each field.",
            "required": ["record", "edges", "fields", "warnings"],
            "properties": {
                "record": {"type": "string", "format": "uri"},
                "record_name": {"type": "string"},
                "type": {"type": "string"},
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "The field's name in the form."},
                            "property": {"type": "string"},
                            "value": {"type": "string"},
                            "link": {"type": "boolean"},
                            "name": {"type": ["string", "null"], "description": "The name of the record a link goes to."},
                            "entry": {"type": "string"},
                            "status": {"enum": ["added", "removed", "kept"]},
                            "order": {"type": "integer"},
                        },
                    },
                },
                "fields": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
                "warnings": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
            },
        },
        "Move": {
            "type": "object",
            "required": ["to"],
            "properties": {"to": {**identifier, "description": "The record's new identifier."}},
            "additionalProperties": False,
        },
        "Upload": {
            "type": "object",
            "required": ["image"],
            "properties": {"image": {"type": "string", "contentMediaType": "application/octet-stream", "description": "A PNG, JPEG, GIF or WebP image."}},
        },
        "Image": {
            "type": "object",
            "required": ["@id"],
            "properties": {"@id": {"type": "string", "format": "uri", "description": "The image's address, to give in a record's image field."}},
        },
        "Note": table_schema(Note),
        "Notes": {
            "type": "object",
            "required": ["total", "notes"],
            "properties": {"total": {"type": "integer", "minimum": 0}, "notes": {"type": "array", "items": ref("Note")}},
        },
        "Source": table_schema(Source),
        "Sources": {"type": "object", "required": ["sources"], "properties": {"sources": {"type": "array", "items": ref("Source")}}},
        "OpenAPI": {"type": "object", "description": "An OpenAPI 3.1 document."},
        "Page": {"type": "string", "description": "An HTML page."},
    }


def answer_schemas(name: str | None) -> dict:
    """The media type and schema of each kind of answer, for the records of the kind *name*."""
    title = local(settings()["kinds"][name]) if name else ""
    return {
        "record": ("application/ld+json", ref(title)),
        "collection": ("application/ld+json", ref(title + "Collection")),
        "done": ("application/json", ref("Done")),
        "preview": ("application/json", ref("Preview")),
        "problems": ("application/json", ref("Problems")),
        "error": ("application/json", ref("Error")),
        "image": ("application/json", ref("Image")),
        "notes": ("application/json", ref("Notes")),
        "sources": ("application/json", ref("Sources")),
        "openapi": ("application/json", ref("OpenAPI")),
        "page": ("text/html", ref("Page")),
    }


def parameters(view, rule, name: str | None, documents: list[dict]) -> list[dict]:
    """The parameters of an operation: those of its path, the fields of its kind when they filter it, and the
    query parameters and headers its description gives."""
    given = view.openapi
    found = []
    for argument in sorted(rule.arguments - {"kind"}):
        identifier = {
            "name": argument,
            "in": "path",
            "required": True,
            "description": f"The record's identifier: its address is {settings()['base']}{name}/{{{argument}}}.",
            "schema": {"type": "string", "pattern": f"^{IDENTIFIER.pattern}$"},
        }
        if documents:
            identifier["example"] = documents[0]["@id"].rsplit("/", 1)[-1]
        found.append(identifier)
    if given["filters"]:
        for field in forms.form(settings()["kinds"][name]):
            if field["name"] in given["query"]:
                raise ValueError(f"The field {field['name']} of {name} has the name of a parameter of the API.")
            item = {"type": "string"}
            if field["entry"] in LINKED:
                item["format"] = "uri"
            if field["options"]:
                item["enum"] = field["options"]
            parameter = {
                "name": field["name"],
                "in": "query",
                "required": False,
                "description": f"Records whose field {field['label']} ({field['property']}) has one of these values: "
                               f"{'the address of a link' if field['links'] else 'a text'}, as the record gives it. {explained(field)}",
                "schema": {"type": "array", "items": item},
                "style": "form",
                "explode": True,
            }
            found_example = plain(example(documents, field["name"]))
            if found_example is not None:
                parameter["example"] = [found_example]
            found.append(parameter)
    for argument, (schema, description) in given["query"].items():
        found.append({"name": argument, "in": "query", "required": False, "description": description, "schema": schema})
    for header, (schema, description) in given["headers"].items():
        found.append({"name": header, "in": "header", "required": False, "description": description, "schema": schema})
    return found


def request_body(given: dict, name: str | None) -> dict | None:
    if given["body"] == "record":
        schema = {"schema": ref(local(settings()["kinds"][name]) + "Body")}
        return {"required": True, "content": {"application/json": schema, "application/ld+json": schema}}
    if given["body"] == "move":
        return {"required": True, "content": {"application/json": {"schema": ref("Move")}}}
    if given["body"] == "image":
        return {"required": True, "content": {"multipart/form-data": {"schema": ref("Upload")}}}
    return None


def operation(view, rule, name: str | None, documents: list[dict]) -> dict:
    given = view.openapi
    summary, _, rest = (inspect.getdoc(view) or "").partition("\n\n")
    tag = name or rule.rule.removeprefix("/api/").split("/")[0]
    found = {
        "operationId": f"{view.__name__}_{name}" if name else view.__name__,
        "summary": " ".join(summary.split()),
        "tags": [tag],
        "parameters": parameters(view, rule, name, documents),
        "responses": {},
    }
    if rest:
        found["description"] = paragraphs(rest)
    body = request_body(given, name)
    if body is not None:
        found["requestBody"] = body
    if given["token"]:
        found["security"] = [{"token": []}]
    schemas = answer_schemas(name)
    for status, (kinds, why) in sorted(given["answers"].items()):
        content = {}
        options = {}
        for kind in [kinds] if isinstance(kinds, str) else kinds:
            media, schema = schemas[kind]
            options.setdefault(media, []).append(schema)
        for media, listed in options.items():
            content[media] = {"schema": listed[0] if len(listed) == 1 else {"oneOf": listed}}
        answer = {"description": why or HTTPStatus(status).phrase}
        if content:
            answer["content"] = content
        found["responses"][str(status)] = answer
    return found


def document() -> dict:
    """The OpenAPI document of the API, as the code and the model of the release give it now."""
    config = settings()
    by_kind = {}
    tags = []
    components = shared_schemas()
    for name, kind in config["kinds"].items():
        by_kind[name] = samples(kind)
        components.update(record_schemas(name, kind, by_kind[name]))
        described_class = terms([kind]).get(kind, {})
        tags.append({"name": name, "description": first_paragraph(described_class.get("description", local(kind))), "externalDocs": {"url": kind}})
    paths = {}
    description = ""
    for rule in sorted(current_app.url_map.iter_rules(), key=lambda rule: rule.rule):
        if not rule.rule.startswith("/api/"):
            continue
        view = current_app.view_functions[rule.endpoint]
        if not hasattr(view, "openapi"):
            raise ValueError(f"The route {rule.rule} is not described for the OpenAPI document.")
        description = description or paragraphs(inspect.getdoc(sys.modules[view.__module__]) or "")
        names = [None]
        if view.openapi["kinds"] == "listed":
            names = list(config["kinds"])
        elif view.openapi["kinds"] == "writable":
            names = list(config.get("writable", {}))
        for name in names:
            path = re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule.rule.replace("<kind>", name or "<kind>"))
            for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                paths.setdefault(path, {})[method.lower()] = operation(view, rule, name, by_kind.get(name, []))
    return {
        "openapi": "3.1.0",
        "info": {"title": config["title"], "version": RELEASE, "description": description},
        "servers": [{"url": request.url_root.rstrip("/")}],
        "tags": tags,
        "paths": paths,
        "components": {
            "schemas": components,
            "securitySchemes": {
                "token": {"type": "http", "scheme": "bearer", "description": paragraphs(inspect.getdoc(tokens) or "")},
            },
        },
    }
