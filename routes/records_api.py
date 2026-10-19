"""The platform's API, with flask-smorest, documented at /api/docs/.

Each kind of record has a resource:
- GET /api/<kind> lists its records a page at a time, found by name (search) or by field values
  (/api/tools?processFlowStep=<address>), as JSON rows with the profile's field names, or as JSON-LD,
  Turtle or N-Triples, by the Accept header.
- GET /api/<kind>/facets counts the records per value of those fields.
- POST /api/<kind> adds a record, at an address made from its name.
- GET, PUT and DELETE /api/tools/aopsuite read a record, with its parts, in JSON-LD, Turtle or N-Triples,
  add or replace it, and remove it. /api/casestudies/kidney/Q1, a case study question, is read with its
  steps and written with its case study.

A record is written in JSON-LD, with the platform's context names ("name", "url", "processFlowStep", ...,
"dct:conformsTo" for another vocabulary) or a context of its own, or in Turtle; a link is
{"@id": "https://..."}. What each field takes is set by the model's SHACL shapes (/api/shapes.ttl); a
record that does not fit is refused, with each field's problems. Writes need a write token, or an editor's
login. A record's ETag is its version: a write that sends it in If-Match is refused when the record has
changed since. With preview=true, nothing is saved; the statements before and after, and each field's
problems, are given back; with page=true too, the record's page as saved, in HTML.
"""

import json
import re
from functools import cache
from urllib.parse import quote

from flask import Response, current_app, g, jsonify, redirect, request, url_for
from flask_smorest import Api, Blueprint, abort
from marshmallow import INCLUDE, Schema, fields
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SDO, XSD
from werkzeug.exceptions import RequestEntityTooLarge

import database
from admin import changes, tokens, writes
from database import images, records
from linkeddata import catalogue, checks, documents, fields as model_fields, markdown, patches, storage
from linkeddata.model import RELEASE, settings, shapes
from routes import account, limiter
from routes.record_pages import SERIALIZATIONS, data, markdown_of

blueprint = Blueprint("api", __name__, url_prefix="/api", description="Records of each kind, at their page addresses.")
limiter.limit("300 per minute")(blueprint)
TOKEN = [{"token": []}]


class Record(Schema.from_dict({"@type": fields.Raw(metadata={"description": "The record's class; needed for a new record."})})):
    """A record in JSON-LD; what each field takes is set by the SHACL shapes (/api/shapes.ttl)."""

    class Meta:
        unknown = INCLUDE


class Writing(Schema):
    preview = fields.Boolean(load_default=False, metadata={"description": "Nothing is saved; the changes are shown."})
    page = fields.Boolean(load_default=False, metadata={"description": "With preview, the page as saved, in HTML."})


class Removal(Schema):
    permanent = fields.Boolean(load_default=False, metadata={"description": "The address is removed too, for reuse."})


class Restore(Schema):
    record = fields.String(required=True, metadata={"description": "The record's page address, such as tools/aopsuite."})


class Move(Restore):
    to = fields.String(required=True, metadata={"description": "The record's new address, such as tools/aop-suite."})


class Done(Schema.from_dict({"@id": fields.String(metadata={"description": "The record's address (IRI).", "format": "iri"})})):
    """A saved change: the record's address, the change's page, the record's version, and the empty
    recommended fields."""

    change = fields.String()
    version = fields.String(allow_none=True)
    warnings = fields.Dict(keys=fields.String(), values=fields.List(fields.String()))


class Image(Schema.from_dict({"@id": fields.String(metadata={"description": "The image's address (IRI), for a record's image field.", "format": "iri"})})):
    pass


def kind_of(address: str | None, body: dict) -> str | None:
    """The kind of the record at an address, or of a new record's @type."""
    record = records.get(address) if address else None
    given = record.type if record is not None else body.get("@type")
    names = {}
    for name, kind in settings()["kinds"].items():
        names[kind] = name
    for value in given if isinstance(given, list) else [given]:
        if isinstance(value, str):
            iri = value if value.startswith(("http://", "https://")) else documents.expand(value)
            if iri in names:
                return names[iri]
    return None


def identity(kind: str):
    """The requester (a token, or a logged-in editor), when allowed to write records of *kind*."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return tokens.check(header.removeprefix("Bearer ").strip(), kind)
    return account.editor_of_request(kind)


def reader(kind: str | None) -> bool:
    """Whether the request may read private fields, such as email addresses: an editor of the kind, logged in
    or with a write token. Reading needs no form token, as nothing is changed."""
    if kind is None:
        return False
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return tokens.check(header.removeprefix("Bearer ").strip(), kind) is not None
    editor = account.current_editor()
    return editor is not None and kind in editor.kinds


def readable(found: Graph, kind: str | None) -> Graph:
    """The statements as the request may read them: private fields are taken out for visitors."""
    return found if reader(kind) else documents.public(found)


@blueprint.after_request
def varied(response):
    """Answers differ for editors, who also read private fields."""
    response.vary.add("Cookie")
    response.vary.add("Authorization")
    return response


def writer(kind: str | None):
    found = identity(kind) if kind is not None else None
    if found is None:
        abort(401, message="Login or write token for this kind needed.")
    return found


def done(address: str, revision, status: int, warnings: dict | None = None):
    record = records.get(address)
    version = record.updated_at if record is not None else None
    headers = {"ETag": f'"{version}"'} if version else {}
    if status == 201:
        headers["Location"] = url_for("api.read", path=address.removeprefix(settings()["base"]))
    return {"@id": address, "change": url_for("changes.change", number=revision.id), "version": version, "warnings": warnings or {}}, status, headers


def unchanged(address: str) -> None:
    """A write that names the version it read (If-Match) is refused when the record has changed since."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if expected and record is not None and record.updated_at != expected:
        abort(412, message="Changed since it was opened; reopen it to see the change.")


def whole(record) -> None:
    """A part, such as a case study question, is written with its record."""
    if record is not None and record.part_of:
        abort(409, message=f"Part of {record.part_of}; written with it.")


def saved(address: str, found: Graph, kind: str, who):
    """The record is saved, and the new records it holds are saved on their own."""
    created = writes.separate(found)
    # A record added in another's form, such as a person, needs write access to its own kind.
    for _, of_kind, _ in created:
        writer(kind_of(None, {"@type": of_kind}))
    for iri, of_kind, own in created:
        writes.save(documents.document(own, iri), of_kind, who.name, who.orcid)
    return writes.save(documents.document(found, address), kind, who.name, who.orcid)


def rendered(address: str, found: Graph, kind: str, who) -> Response:
    """The record's page as saving makes it, from a copy of the database with the record saved."""
    with database.copied():
        saved(address, found, kind, who)
        path = "/" + address.removeprefix(settings()["base"])
        with current_app.app_context(), current_app.test_request_context(path, base_url=request.host_url):
            answer = current_app.full_dispatch_request()
    return Response(answer.get_data(), status=answer.status_code, mimetype="text/html")


def store(address: str, body: dict, preview: bool = False, page: bool = False):
    """A request body's record is checked and saved at *address*."""
    kind = kind_of(address, body)
    if kind is None:
        abort(400, message="Unknown @type.")
    who = writer(kind)
    if "@context" in body:
        body = documents.document(Graph().parse(data=json.dumps(body), format="json-ld"), address)
    kind = settings()["kinds"][kind]
    try:
        found = documents.statements(writes.document(kind, address, body))
    except ValueError as problem:
        abort(422, message=str(problem))
    writes.addressed(found)
    found, problems, warnings = checks.checked(documents.document(found, address))
    if preview and page:
        return rendered(address, found, kind, who)
    if preview:
        before = changes.statements(documents.document_of(address))
        labels = {}
        for path in list(problems) + list(warnings):
            labels[path] = checks.named(kind, path)
        return jsonify({**changes.edges(before, found, URIRef(address)), "fields": problems, "warnings": warnings, "labels": labels,
                        "document": documents.document(storage.with_names(found), address)})
    unchanged(address)
    if problems:
        abort(422, message=str(checks.NotFitting(problems)), errors=problems)
    revision = saved(address, found, kind, who)
    return done(address, revision, 201 if revision.action == "Added" else 200, warnings)


RECORD_FORMATS = {"200": {"description": "The record, in the Accept header's format.", "content": {
    "application/ld+json": {"schema": {"$ref": "#/components/schemas/Record"}},
    "text/turtle": {"schema": {"type": "string"}},
    "application/n-triples": {"schema": {"type": "string"}},
    "text/markdown": {"schema": {"type": "string"}},
}}}


def found_record(path: str):
    """The record at a page's address, moved and removed ones too."""
    record = records.get(records.address(path))
    if record is None:
        abort(404, message="No record at this address.")
    return record


class Search(Schema):
    text = fields.String(load_default="", metadata={"description": "Text in the name or address."})
    of_class = fields.List(fields.Url(metadata={"format": "iri"}), data_key="class", load_default=list, metadata={"description": "Class IRIs of the records or terms; subclasses included."})
    within = fields.String(load_default="", metadata={"description": "The address start, such as a vocabulary namespace."})
    vocabulary = fields.Url(load_default="", metadata={"format": "iri", "description": "The vocabulary whose terms are searched."})
    limit = fields.Integer(load_default=20, validate=lambda number: 1 <= number <= 200)


class Registry(Schema):
    text = fields.String(load_default="", metadata={"description": "Text in a vocabulary's or term's name."})
    namespace = fields.String(load_default="", metadata={"description": "The namespace of the vocabulary searched."})


def registered() -> None:
    """Registries answer editors only (logged in, or with a valid write token), as they are asked on their
    behalf."""
    header = request.headers.get("Authorization", "")
    token = tokens.find(header.removeprefix("Bearer ").strip()) if header.startswith("Bearer ") else None
    if account.current_editor() is None and token is None:
        abort(401, message="Login or write token needed.")


@blueprint.get("/registries")
def registries():
    """The vocabulary registries searched by the editor."""
    registered()
    return jsonify(patches.REGISTRIES)


@blueprint.get("/registries/<registry>/vocabularies")
@blueprint.arguments(Registry, location="query")
def registry_vocabularies(given, registry):
    """A registry's vocabularies whose identifier or title has the text: title, namespace and description."""
    registered()
    if registry not in patches.REGISTRIES:
        abort(404, message="No such registry.")
    return jsonify(patches.vocabularies(registry, given["text"], database.STATE_DIR / "registries.json")[:50])


@blueprint.get("/registries/terms")
@blueprint.arguments(Registry, location="query")
def registry_terms(given):
    """The terms at a namespace whose names have the text, from the registry that has them: address,
    label, definition and code."""
    registered()
    if not given["text"].strip() or not given["namespace"]:
        return jsonify({"registry": None, "terms": []})
    registry = patches.serving(given["namespace"], database.STATE_DIR / "registries.json")
    found = patches.terms(registry, given["text"], given["namespace"], database.STATE_DIR / "registries.json") if registry else []
    return jsonify({"registry": registry, "title": patches.REGISTRIES.get(registry), "terms": found})


@blueprint.get("/search")
@blueprint.arguments(Search, location="query")
def search(given):
    """Records, parts and vocabulary terms found by name or address, in JSON-LD: address, class and name."""
    found = []
    among = catalogue.holders(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet), [given["vocabulary"]]) if given["vocabulary"] else None
    for record in records.search(given["text"], given["of_class"] or list(settings()["kinds"].values()), given["within"], limit=given["limit"], among=among):
        found.append({"@id": record.iri, "@type": documents.term(record.type), "name": record.name or record.iri})
    return jsonify({"@context": documents.context(settings()), "@graph": found})


MEDIA = ["application/json", "application/ld+json", *SERIALIZATIONS, "text/markdown"]
LINKED = "JSON rows with the profile's field names, or JSON-LD, Turtle, N-Triples or Markdown, by the Accept header."


class FacetValue(Schema):
    value = fields.String(metadata={"description": "The value as in rows and queries: an IRI, or a text of a list."})
    name = fields.String(metadata={"description": "The record's name or the term's label."})
    count = fields.Integer(metadata={"description": "The count of found records with it."})
    fits = fields.Boolean(metadata={"description": "Whether the profile takes it: false for a text where an IRI belongs, or a value off the list."})


# The JSON types of literal datatypes; other datatypes are texts.
JSON_TYPES = {str(XSD.integer): {"type": "integer"}, str(XSD.boolean): {"type": "boolean"},
              str(XSD.date): {"type": "string", "format": "date"}, str(XSD.dateTime): {"type": "string", "format": "date-time"}}


def browsed(field: dict) -> bool:
    """Whether a catalogue is browsed by a field: a list (sh:in), or links to records or terms (sh:class,
    sh:or), without parts or fixed values."""
    return bool(field["values"] or field["classes"]) and not field["part"] and not field["fixed"]


def resource(of_class: str) -> str:
    """The API resource listing a class's records: its kind's, or the search for the class."""
    for kind, of_kind in settings()["kinds"].items():
        if of_kind == of_class:
            return f"{blueprint.url_prefix}/{kind}"
    return f"{blueprint.url_prefix}/search?class={quote(of_class, safe=':/')}"


def described(field: dict) -> str:
    """A field's description: its label, description and values, from the profile."""
    text = f"{field['label']}. {field['description']}".strip()
    if field["part"]:
        return text
    if field["values"] and field["iris"]:
        names = records.names(field["values"])
        listed = []
        for value in field["values"]:
            listed.append(f"{names.get(value, value)} ({value})")
        text += " One of these IRIs: " + "; ".join(listed) + "."
    elif field["classes"]:
        listed = []
        for of_class in field["classes"]:
            listed.append(f"{documents.term(of_class)} ({of_class}, at {resource(of_class)})")
        text += " IRIs of records of " + " or ".join(listed) + "."
    elif field["iris"]:
        text += " IRIs."
    # A pattern on a namespace, such as ^https://vhp4safety\.github\.io/glossary#, keeps one vocabulary's terms.
    namespace = re.sub(r"\\(.)", r"\1", field["pattern"].removeprefix("^"))
    if field["pattern"].startswith("^") and re.match(field["pattern"], namespace):
        text += f" Only in the namespace {namespace}."
    if field["fixed"]:
        text += " Fixed values: " + ", ".join(field["fixed"]) + "."
    return text


def value_field(field: dict, allow_none: bool = False) -> fields.Field:
    """One value of a field, as the profile types it: an IRI as an iri-format text, a literal in its JSON
    type, a list value (sh:in) as an enum, with the field's pattern. The list and pattern are documented, not
    enforced, so misfitting values are found too; the facets count them apart."""
    metadata = {}
    if field["values"]:
        metadata["enum"] = list(field["values"])
    if field["pattern"]:
        metadata["pattern"] = field["pattern"]
    if field["iris"]:
        return fields.String(allow_none=allow_none, metadata={"format": "iri", **metadata})
    if field["datatype"] in JSON_TYPES:
        return fields.Raw(allow_none=allow_none, metadata={**JSON_TYPES[field["datatype"]], **metadata})
    return fields.String(allow_none=allow_none, metadata=metadata)


def query_schema(of_class: str, in_use: dict) -> type[Schema]:
    """A catalogue's query: a text, and values of each browsable field, with the most used ones as examples."""
    found = {"search": fields.String(load_default="", metadata={"description": "Text in the record's name or address, in any case."})}
    for field in model_fields.of(of_class):
        if not browsed(field):
            continue
        text = described(field) + f" {resource(of_class)}/facets counts the records per value."
        listed = []
        examples = []
        for item in in_use[field["name"]]:
            if item["count"] and item["fits"] and len(examples) < 10:
                named = item["value"] if item["name"] == item["value"] else f"{item['name']} ({item['value']})"
                listed.append(f"{named}: {item['count']}")
                examples.append([item["value"]])
        if listed and not field["values"]:
            text += " The most used values, with record counts: " + "; ".join(listed) + "."
        metadata = {"description": text}
        if examples:
            metadata["examples"] = examples
        found[field["name"]] = fields.List(value_field(field), metadata=metadata)
    return Schema.from_dict(found, name=documents.term(of_class).replace(":", "_") + "Query")


@cache
@cache
def row_schema(of_class: str) -> type[Schema]:
    """A row of a class's record or part: the profile's fields by JSON-LD name, a list for several values,
    a value or null for one, typed as the profile types them; parts are rows of their own."""
    found = {"@id": fields.String(metadata={"description": "The address (IRI) of the record or part.", "format": "iri"})}
    for field in model_fields.of(of_class):
        if field["part"] and field["classes"]:
            value = fields.Nested(lambda of_part=field["classes"][0]: row_schema(of_part)(), allow_none=field["single"])
        else:
            value = value_field(field, field["single"])
        if not field["single"]:
            value = fields.List(value)
        value.metadata["description"] = described(field)
        found[field["name"]] = value
    return Schema.from_dict(found, name=documents.term(of_class).replace(":", "_"))


def row(found: Graph, node, of_class: str) -> dict:
    """A record, or a part of one, as a row with the profile's field names."""
    answer = {}
    if isinstance(node, URIRef):
        answer["@id"] = str(node)
    for field in model_fields.of(of_class):
        values = []
        for value in found.objects(node, URIRef(field["iri"])):
            if field["part"] and field["classes"]:
                values.append(row(found, value, str(found.value(value, RDF.type) or field["classes"][0])))
            elif isinstance(value, Literal) and isinstance(value.toPython(), (bool, int)):
                # Numbers and booleans that fit their datatype, such as xsd:integer, are given as such.
                values.append(value.toPython())
            else:
                values.append(str(value))
        if field["single"]:
            answer[field["name"]] = values[0] if values else None
        else:
            answer[field["name"]] = values
    return answer


def filters_of(of_class: str, given: dict) -> dict:
    found = {}
    for field in model_fields.of(of_class):
        if browsed(field) and given.get(field["name"]):
            found[field["iri"]] = given[field["name"]]
    return found


def listing(of_class: str):
    def listed(given, pagination_parameters):
        total, iris = catalogue.page(of_class, filters_of(of_class, given), given["search"], pagination_parameters.first_item, pagination_parameters.page_size)
        pagination_parameters.item_count = total
        found = readable(storage.graph(iris), kind_of(None, {"@type": of_class}))
        # A kind's page passes on the format it was asked for, also by an ending (/tools.md).
        media = g.get("media") or request.accept_mimetypes.best_match(MEDIA, "application/json")
        if media == "application/json":
            return [row(found, URIRef(iri), of_class) for iri in iris]
        if media == "text/markdown":
            listed = []
            for iri in iris:
                description = found.value(URIRef(iri), SDO.description)
                listed.append({"name": str(found.value(URIRef(iri), SDO.name) or iri), "address": iri,
                               "description": markdown.text({"text": str(description), "html": description.datatype == RDF.HTML}) if description else ""})
            kind = kind_of(None, {"@type": of_class}) or of_class
            return Response(markdown.listing(kind.capitalize(), listed, settings()["license"]), content_type=markdown.MEDIA, headers={"Vary": "Accept"})
        if media == "application/ld+json":
            documented = []
            for iri in iris:
                document = documents.document(found, iri)
                document.pop("@context", None)
                documented.append(document)
            return Response(json.dumps({"@context": documents.context(settings()), "@graph": documented}, indent=1), mimetype=media, headers={"Vary": "Accept"})
        return data(found, media)

    return listed


def faceting(of_class: str):
    def counted(given):
        browsed_fields = [field for field in model_fields.of(of_class) if browsed(field)]
        counts = catalogue.facets(of_class, [field["iri"] for field in browsed_fields], filters_of(of_class, given), given["search"])
        every = []
        for field in browsed_fields:
            every.extend(field["values"])
            for value, iri in counts[field["iri"]]:
                if iri:
                    every.append(value)
        names = records.names(every)
        found = {}
        for field in browsed_fields:
            # List values are counted even when no record has them.
            values = {}
            for value in field["values"]:
                values[(value, field["iris"])] = 0
            for key, count in counts[field["iri"]].items():
                values[key] = values.get(key, 0) + count
            listed = []
            for (value, iri), count in values.items():
                # A value fits as an IRI where IRIs belong, and as one of the field's list.
                fits = iri == field["iris"] and (value in field["values"] or not field["values"])
                listed.append({"value": value, "name": (names.get(value) if iri else None) or value, "count": count, "fits": fits})
            listed.sort(key=lambda item: (not item["fits"], -item["count"], item["name"]))
            found[field["name"]] = listed
        return found

    return counted


def resources() -> None:
    """Each kind's catalogue, its facets, and the addition of records."""
    for kind, of_class in settings()["kinds"].items():
        browsed_fields = [field for field in model_fields.of(of_class) if browsed(field)]
        query = query_schema(of_class, faceting(of_class)({"search": ""}))

        listed = listing(of_class)
        listed.__doc__ = (f"The {kind}, a page at a time, found by name and field values.\n\n"
                          "Several values of one field match any; several fields match all.")
        view = blueprint.paginate(page_size=20, max_page_size=200)(listed)
        view = blueprint.arguments(query, location="query")(view)
        for media, schema in {"application/ld+json": {"type": "object"}, "text/turtle": {"type": "string"}, "application/n-triples": {"type": "string"}, "text/markdown": {"type": "string"}}.items():
            view = blueprint.alt_response(200, schema=schema, content_type=media, success=True, description=LINKED)(view)
        view = blueprint.response(200, row_schema(of_class)(many=True), description=LINKED)(view)
        blueprint.route(f"/{kind}", endpoint=f"list_{kind}", methods=["GET"], tags=[kind])(view)

        counted = faceting(of_class)
        counted.__doc__ = (f"The count of {kind} found per value of each browsable field.\n\n"
                           "A field's own filter is left out of its counts, so each count is what that value would find.")
        facet_schema = Schema.from_dict({field["name"]: fields.List(fields.Nested(FacetValue), metadata={"description": described(field)}) for field in browsed_fields},
                                        name=documents.term(of_class).replace(":", "_") + "Facets")
        view = blueprint.response(200, facet_schema)(blueprint.arguments(query, location="query")(counted))
        blueprint.route(f"/{kind}/facets", endpoint=f"facets_{kind}", methods=["GET"], tags=[kind])(view)

        def added(body, kind=kind):
            # A record given in Turtle is the node of the kind's class.
            given = None
            if request.mimetype == "text/turtle":
                given = Graph().parse(data=request.get_data(as_text=True), format="turtle")
                node = given.value(None, RDF.type, URIRef(settings()["kinds"][kind]))
                body = {"name": str(given.value(node, SDO.name) or "")}
            # A vocabulary term keeps its own address; other records get one from their name.
            address = body.get("@id") or writes.free(records.address(f"{kind}/{writes.slug(str(body.get('name') or kind))}"), set())
            if records.get(address) is not None:
                abort(409, message="Address taken.")
            if given is not None:
                writes.renamed(given, node, address)
                body = documents.document(given, address)
            body = {"@type": documents.term(settings()["kinds"][kind]), **body}
            return store(address, body)

        added.__doc__ = f"Add a record to the {kind}, in JSON-LD or Turtle, at an address made from its name."
        blueprint.route(f"/{kind}", endpoint=f"add_{kind}", methods=["POST"], tags=[kind])(
            blueprint.doc(security=TOKEN, requestBody={"content": {"text/turtle": {"schema": {"type": "string"}}}})(
                blueprint.response(201, Done)(blueprint.arguments(Record)(added))))


@blueprint.get("/<path:path>")
@blueprint.doc(responses=RECORD_FORMATS)
def read(path):
    """A record or part at its page's address, in JSON-LD, Turtle, N-Triples or Markdown, by the Accept header."""
    record = found_record(path)
    if record.moved_to:
        return redirect(url_for("api.read", path=record.moved_to.removeprefix(settings()["base"])), code=301)
    if record.removed_at:
        abort(410, message="Removed.")
    media = request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS, "text/markdown"]) or "application/ld+json"
    if media == "text/markdown":
        return markdown_of(record)
    # A part, such as a case study question, is read as its record is.
    kind = kind_of(record.part_of or record.iri, {})
    answer = data(storage.with_names(readable(storage.graph([record.iri]), kind)), media, record.iri)
    answer.headers["ETag"] = f'"{record.updated_at}"'
    return answer


@blueprint.put("/<path:path>")
@blueprint.arguments(Writing, location="query")
@blueprint.arguments(Record)
@blueprint.response(200, Done, description="Replaced; with preview=true, the changes it would make.")
@blueprint.alt_response(201, schema=Done, description="Added.")
@blueprint.doc(security=TOKEN, requestBody={"content": {"text/turtle": {"schema": {"type": "string"}}}})
def replace(given, body, path):
    """Add or replace the record at its page's address, in JSON-LD or Turtle."""
    address = records.address(path)
    record = records.get(address)
    whole(record)
    if record is not None and (record.moved_to or record.removed_at):
        abort(409, message="Address of a moved or removed record; not reused.")
    if request.mimetype == "text/turtle":
        body = documents.document(Graph().parse(data=request.get_data(as_text=True), format="turtle"), address)
    return store(address, body, given["preview"], given["page"])


@blueprint.delete("/<path:path>")
@blueprint.arguments(Removal, location="query")
@blueprint.response(200, Done, description="Removed.")
@blueprint.doc(security=TOKEN)
def remove(given, path):
    """Remove a record, with its parts.

    Its address then answers 410 Gone and is not reused, unless the removal is permanent. It can be put
    back with restore."""
    record = found_record(path)
    if record.removed_at and not given["permanent"]:
        abort(404, message="No record at this address.")
    whole(record)
    who = writer(kind_of(record.iri, {}))
    unchanged(record.iri)
    if given["permanent"]:
        return done(record.iri, writes.remove(record.iri, who.name, who.orcid), 200)
    return done(record.iri, writes.retire(record.iri, who.name, who.orcid), 200)


@blueprint.post("/move")
@blueprint.arguments(Move)
@blueprint.response(200, Done, description="Moved; the old address forwards to the new one.")
@blueprint.doc(security=TOKEN)
def move(body):
    """Move a record, with its parts, to a new address; the old one forwards to it."""
    record = found_record(body["record"])
    if record.removed_at:
        abort(404, message="No record at this address.")
    whole(record)
    who = writer(kind_of(record.iri, {}))
    target = records.get(records.address(body["to"]))
    if target is not None and target.moved_to != record.iri:
        abort(409, message="Address taken, now or before.")
    unchanged(record.iri)
    return done(records.address(body["to"]), writes.move(record.iri, records.address(body["to"]), who.name, who.orcid), 200)


@blueprint.post("/restore")
@blueprint.arguments(Restore)
@blueprint.response(200, Done, description="Restored.")
@blueprint.doc(security=TOKEN)
def restore(body):
    """Put back a removed record, with its parts."""
    record = found_record(body["record"])
    if not record.removed_at:
        abort(404, message="No removed record at this address.")
    who = writer(kind_of(record.iri, {}))
    return done(record.iri, writes.restore(record.iri, who.name, who.orcid), 200)


@blueprint.post("/images")
@blueprint.response(201, Image)
@blueprint.doc(security=TOKEN)
def upload_image():
    """Upload an image, such as a tool's logo, as the form field "image".

    It is checked and saved as WebP; its address is given in a record's image field."""
    who = None
    for kind in settings()["kinds"]:
        who = who or identity(kind)
    if who is None:
        abort(401, message="Login or write token needed.")
    request.max_content_length = images.MAX_BYTES
    try:
        upload = request.files.get("image")
    except RequestEntityTooLarge:
        abort(413, message="Over 5 MB.")
    if upload is None:
        abort(400, message='Form field "image" missing.')
    try:
        return {"@id": images.store(upload.stream, who.name, who.orcid)}
    except ValueError as problem:
        abort(422, message=str(problem))


@blueprint.get("/dump")
@blueprint.doc(responses={"200": {"description": "Every published statement, in N-Triples or Turtle, by the Accept header.", "content": {
    "application/n-triples": {"schema": {"type": "string"}}, "text/turtle": {"schema": {"type": "string"}}}}})
def dump():
    """Every record with a page, with its parts and the vocabulary terms they use, as one file; private fields
    are left out. It is described at /.well-known/void."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published(), media)


@blueprint.get("/shapes.ttl")
@blueprint.doc(responses={"200": {"description": "The shapes, in Turtle.", "content": {"text/turtle": {"schema": {"type": "string"}}}}})
def model_shapes():
    """The model's SHACL shapes: what each field takes."""
    return Response(shapes().serialize(format="turtle"), mimetype="text/turtle")


def register(app) -> None:
    """The API, with its OpenAPI document at /api/docs/."""
    app.config.update(
        API_TITLE=settings()["title"],
        API_VERSION=RELEASE,
        OPENAPI_VERSION="3.1.0",
        OPENAPI_URL_PREFIX="/api/docs",
        OPENAPI_JSON_PATH="openapi.json",
        OPENAPI_SWAGGER_UI_PATH="/",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/",
        API_SPEC_OPTIONS={"info": {"description": __doc__}},
    )
    api = Api(app)
    api.spec.components.security_scheme("token", {"type": "http", "scheme": "bearer", "description": tokens.__doc__})
    api.spec.components.schema("Record", component={"x-jsonld-context": documents.context(settings())}, schema=Record)
    # Each row schema gives its class and JSON-LD context (x-jsonld-type, x-jsonld-context), as proposed for
    # linked data in REST APIs; part schemas come before their class's.
    named = set()

    def hinted(of_class: str) -> None:
        name = documents.term(of_class).replace(":", "_")
        if name in named:
            return
        named.add(name)
        for field in model_fields.of(of_class):
            if field["part"] and field["classes"]:
                hinted(field["classes"][0])
        api.spec.components.schema(name, schema=row_schema(of_class), component={"x-jsonld-type": of_class, "x-jsonld-context": documents.context(settings())})

    for of_class in settings()["kinds"].values():
        hinted(of_class)
    resources()
    api.register_blueprint(blueprint)
