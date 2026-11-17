"""API of the platform, made with flask-smorest and documented at /api/docs/."""

import copy
import json
import re
from functools import lru_cache
from http import HTTPStatus
from urllib.parse import quote, quote_plus, urlsplit

from flask import Response, g, jsonify, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_smorest import Api, Blueprint, abort
from marshmallow import INCLUDE, Schema, fields, pre_load, validate
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO
from rdfsolve.iris import prefix_map
from rdfsolve.ontology.service import PROVIDERS, Ontologies, serving
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

import database
from admin import changes, tokens, writes
from database import images, records, tables
from linkeddata import checks, documents, pages, schemas, void
from linkeddata.profile import RELEASE, jsonld_name, settings, shapes
from linkeddata.profile import fields as fields_of
from routes import account

FORMATS = {".jsonld": "application/ld+json", ".ttl": "text/turtle", ".nt": "application/n-triples"}
FORMAT_NAMES = {".jsonld": "JSON-LD", ".ttl": "Turtle", ".nt": "N-Triples"}
# A page in Markdown, for readers of plain text such as agents.
MARKDOWN = ".md"
SERIALIZATIONS = {"text/turtle": "turtle", "application/n-triples": "nt"}
# The formats of a record sent in a write.
WRITTEN = ("application/ld+json", "application/json", "text/turtle")
# The counts are kept in memory, as the platform is run with one worker. The headers tell a client its limit, and when
# to ask again (Retry-After).
limiter = Limiter(get_remote_address, storage_uri="memory://", headers_enabled=True)
LIMIT = "300 per minute"
# The registry operations ask the registries, which may block the platform if it asks too often.
REGISTRY_LIMIT = "30 per minute"


def data(found: Graph, media: str, iri: str | None = None) -> Response:
    """Return the statements in found in JSON-LD, Turtle or N-Triples."""
    if media in ("application/ld+json", "application/json"):
        body = json.dumps(documents.document(found, iri, named=True), indent=2)
    else:
        # The prefixes of the profile and of rdfsolve are bound, so that no namespace is written as ns1.
        terms = {str(term) for term in found.predicates()} | {str(term) for term in found.objects(None, RDF.type)}
        for prefix, namespace in prefix_map(terms, settings()["prefixes"]).items():
            found.bind(prefix, namespace, override=True, replace=True)
        body = found.serialize(format=SERIALIZATIONS[media])
    return Response(body, mimetype=media, headers={"Vary": "Accept"})


def markdown_of(record: tables.Record) -> Response:
    """Return the page of a record in Markdown."""
    formats = {}
    for ending, name in FORMAT_NAMES.items():
        formats[name] = record.iri + ending
    body = pages.markdown(record, formats, void.platform()["license"])
    return Response(body, content_type=pages.MEDIA, headers={"Vary": "Accept"})


# The examples are filled in from the first stored record (pages.first_record), so that each one works on this platform.
DESCRIPTION = """The records of the platform: {kinds}. Reading needs no token. The requests of each client address are
limited to {limit}; over the limit, the answer is 429 Too Many Requests, with Retry-After.

To answer a question, start here:

1. Search all records by name or address: `GET /api/search?text={text}`. Each result has its address (`@id`), its
   class (`@type`) and its name.
2. Read the record: `GET /api/<kind>/<name>`, such as `GET /api/{record}`, in JSON-LD, Turtle, N-Triples or Markdown,
   by the Accept header. The page of the record is at its `@id`.
3. To list the records of one kind, or filter them by a field: `GET /api/{kind}`, or `GET /api/{kind}?{filter}`. Count
   the records for each field value with `GET /api/{kind}/facets`.

Each kind has its own operations, with a filter for each field. The fields of each kind are in the schema of its
class, under components, and in `GET /api/shapes.ttl`. All records are in one file at `GET /api/dump`, and the entry
points are at `GET /api`.

Writes need a write token or the login of an editor.

[The platform](/) · [llms.txt](/llms.txt) · [Write tokens](/account/tokens/) · [Record editor](/admin/)"""

# In the documentation, the operations of the blueprint are grouped under its name, and the others under TAGS.
blueprint = Blueprint("records", __name__, url_prefix="/api", description="Read, list, filter and search records.")
TAGS = [
    {"name": "downloads", "description": "Download all records, the vocabulary terms in use and the SHACL shapes, each as one file."},
    {"name": "editing", "description": "Add, change, move, remove and restore records. A write token for the kind is required."},
    {"name": "registries", "description": "Search vocabulary registries for vocabularies and terms that are not on the platform yet. As each search is sent on to a registry, the searches of each client address are limited to " + REGISTRY_LIMIT + "."},
]
# The requests of a client to all operations of the API are counted together, and the registry searches also apart.
limiter.shared_limit(LIMIT, scope="api")(blueprint)
TOKEN = [{"token": []}]
WRITE = {"security": TOKEN, "requestBody": {"content": {"text/turtle": {"schema": {"type": "string"}}}}}
class Record(Schema.from_dict({"@type": fields.Raw(metadata={"description": "The class of the record, such as SoftwareApplication. Required for a new record."})})):
    """Record in JSON-LD, with the fields of /api/shapes.ttl."""

    class Meta:
        unknown = INCLUDE


class Writing(Schema):
    preview = fields.Boolean(load_default=False, metadata={"description": "If true, check the record without storing it, and return the changes and the warnings."})
    page = fields.Boolean(load_default=False, metadata={"description": "With preview, return the page of the record in HTML, as it is shown after the change."})


class Removal(Schema):
    permanent = fields.Boolean(load_default=False, metadata={"description": "If true, also release the address, so that it can be used for a new record."})


class Restore(Schema):
    record = fields.String(required=True, metadata={"description": "The page address of the record, such as tools/aopsuite."})


class Move(Restore):
    to = fields.String(required=True, metadata={"description": "The new page address, such as tools/aop-suite."})


class Done(Schema.from_dict({"@id": fields.String(metadata={"description": "The address (IRI) of the record.", "format": "iri"})})):
    """The result of a stored change."""

    change = fields.String(metadata={"description": "The address of the change in the list of changes."})
    version = fields.String(allow_none=True, metadata={"description": "The new version of the record, as sent in the ETag header."})
    warnings = fields.Dict(keys=fields.String(), values=fields.List(fields.String()), metadata={"description": "The problems found in each field. The record is stored with them."})


class Image(Schema.from_dict({"@id": fields.String(metadata={"description": "The address of the stored image, for the image field of a record.", "format": "iri"})})):
    pass


def kinds() -> dict[str, str]:
    """Return the kind of each class of records, with the classes below the class of each kind."""
    names = {}
    for name, kind in settings()["kinds"].items():
        for of_class in records.within(kind):
            names[of_class] = name
    return names


def kind_of(address: str | None, body: dict) -> str | None:
    """Return the kind of the record at address, or of the @type of a new record in body."""
    record = records.get(address) if address else None
    given = [record.type] if record is not None else writes.classes(body)
    return next((kinds()[of_class] for of_class in given if of_class in kinds()), None)


def written(address: str) -> bool:
    """Return True if address is an http or https address without a space or another character that no address holds."""
    return web(address) and not any(char.isspace() or char in '<>"{}|\\^`' for char in address)


def placed(address: str, kind: str | None) -> None:
    """Refuse a new address that is not <kind>/<name> in the kind of the record, with a name such as the API makes from a
    name. Only a term of a vocabulary is stored outside the platform, at its own http or https address."""
    path = records.path(address)
    head, _, name = path.partition("/")
    hosts = {urlsplit(settings()[base]).netloc for base in ("base", "release base")}
    if kind in settings()["kinds"] and (path != address and head == kind and writes.named(name) or path == address and vocabulary_kind(kind) and written(address) and urlsplit(address).netloc not in hosts):
        return
    if kind not in settings()["kinds"]:
        abort(422, message="A new record is at <kind>/<name>, in a kind of GET /api, such as tools/<name>; a term of a vocabulary may be at its own http or https address.")
    label = settings()["labels"][settings()["kinds"][kind]].lower()
    outside = ", or at its own http or https address outside the platform" if vocabulary_kind(kind) else ""
    abort(422, message=f"A {label} record is at {kind}/<name>, with a name of lowercase letters, digits and single hyphens, such as {kind}/{writes.slug(name or label)}{outside}.")


def kind_at(address: str, body: dict) -> str:
    """Return the kind of the record written at address with body: the kind of the stored record, or else of the new
    address, or for a term outside the platform of its class. Refuse a class of another kind, as a record keeps the kind
    of its class and of its address."""
    given = {of_class: kinds()[of_class] for of_class in writes.classes(body) if of_class in kinds()}
    if body.get("@type") and not given:
        abort(400, message="Unknown @type: send the class of the record, such as " + jsonld_name(next(iter(settings()["kinds"].values()))) + "; the classes of each kind are in GET /api/shapes.ttl.")
    path = records.path(address)
    kind = kind_of(address, {}) or (path.partition("/")[0] if path != address else next(iter(given.values()), None))
    if records.get(address) is None:
        placed(address, kind)
    for of_class, of_kind in given.items():
        if of_kind != kind:
            abort(422, message=f"{jsonld_name(of_class)} is a class of the kind {of_kind}, not {kind}; a record keeps the kind of its class, so add it with POST /api/{of_kind}.")
    return kind


def identity(kind: str):
    """Return the token or the signed-in editor of the request, if records of kind may be written."""
    secret = tokens.bearer(request.headers.get("Authorization", ""))
    if secret is not None:
        return tokens.check(secret, kind)
    return account.editor_of_request(kind)


def reader(kind: str | None) -> bool:
    """Return True if the private fields of records of kind may be read."""
    if kind is None:
        return False
    secret = tokens.bearer(request.headers.get("Authorization", ""))
    if secret is not None:
        return tokens.check(secret, kind) is not None
    editor = account.current_editor()
    return editor is not None and kind in editor.kinds


def readable(found: Graph, kind: str | None) -> Graph:
    """Remove the private fields from the statements for visitors."""
    return found if reader(kind) else documents.public(found)


@blueprint.after_request
def varied(response):
    """Vary the responses with the cookie and the token, as private fields are returned to editors only."""
    response.vary.add("Cookie")
    response.vary.add("Authorization")
    return response


def signed_in():
    """Return the valid write token or the signed-in editor of the request, for any kind, or None."""
    secret = tokens.bearer(request.headers.get("Authorization", ""))
    return tokens.find(secret) if secret is not None else account.editor_of_request(None)


def writer(kind: str | None):
    """Return the token or the signed-in editor of the request, if records of kind may be written. Refuse a request
    without a valid token or login with 401, and with a token or login for other kinds with 403."""
    found = identity(kind) if kind is not None else None
    if found is None and signed_in() is None:
        abort(401, message="Login or write token needed.", headers={"WWW-Authenticate": "Bearer"})
    if found is None:
        abort(403, message=f"The write token or the login is not for the kind {kind}." if kind else "No kind of records holds this record.")
    return found


def done(address: str, revision, status: int, warnings: dict | None = None):
    record = records.get(address)
    version = record.updated_at if record is not None else None
    headers = {"ETag": f'"{version}"'} if version else {}
    if status == 201:
        headers["Location"] = url_for("records.read", path=records.path(address))
    return {"@id": address, "change": url_for("changes.change", number=revision.id), "version": version, "warnings": warnings or {}}, status, headers


def unchanged(address: str) -> None:
    """Refuse a write with a version in If-Match if the record was changed after that version."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if expected and record is not None and record.updated_at != expected:
        abort(412, message="Changed since it was opened; reopen it to see the change.")


def editable(record) -> None:
    """Refuse a change from the record editor to a stored record of a kind that is kept as it is there, such as a model.
    A write token of the API changes it."""
    if record is not None and kind_of(record.iri, {}) in settings()["read only in the editor"] and tokens.bearer(request.headers.get("Authorization", "")) is None:
        abort(403, message="Kept as it is in the record editor; a write token of the API changes it.")


def whole(record) -> None:
    """Refuse a write of a part, such as a case-study question, as parts are written with their record."""
    if record is not None and record.part_of:
        abort(409, message=f"Part of {record.part_of}; written with it.")


def web(value) -> bool:
    """Return True if value is an http or https address. The startswith of rdflib takes no tuple, so a URIRef is compared as
    a text."""
    return isinstance(value, str) and str(value).startswith(("https://", "http://"))


def inline(value) -> bool:
    """Return True if each JSON-LD context in value is an object in value, so that no context is read from an address."""
    if isinstance(value, list):
        return all(inline(given) for given in value)
    if not isinstance(value, dict):
        return True
    for name, given in value.items():
        contexts = given if isinstance(given, list) else [given]
        if name == "@import" or (name == "@context" and not all(context is None or isinstance(context, dict) for context in contexts)):
            return False
        if not inline(given):
            return False
    return True


def parsed(text: str, media: str) -> Graph:
    """Return the statements of a body in Turtle or JSON-LD, or refuse a body that cannot be read."""
    try:
        return Graph().parse(data=text, format="turtle" if media == "text/turtle" else "json-ld")
    # The parsers of rdflib raise errors of many classes for a body they cannot read.
    except Exception as problem:
        abort(422, message=f"Not valid {'Turtle' if media == 'text/turtle' else 'JSON-LD'}: {problem}")


def sent(body: dict, address: str | None = None):
    """Return the statements of a body in Turtle, or in JSON-LD with a context of its own, with the node of the record in
    them: the node at address, or else the one node that no other node links to, which for a write at an address has no
    address of its own. Return None for a body in JSON in the context of the platform."""
    if request.mimetype not in WRITTEN:
        abort(415, message="Send the record in " + ", ".join(WRITTEN) + ".")
    if request.mimetype != "text/turtle" and "@context" not in body:
        return None
    if request.mimetype != "text/turtle" and not inline(body):
        abort(422, message="Send the @context in the body, as an object; a context at an address is not read.")
    found = parsed(request.get_data(as_text=True) if request.mimetype == "text/turtle" else json.dumps(body), request.mimetype)
    if address is not None and (URIRef(address), None, None) in found:
        return found, URIRef(address)
    tops = [node for node in set(found.subjects()) if set(found.subjects(None, node)) <= {node}]
    if len(tops) != 1 or (address is not None and web(tops[0])):
        abort(422, message=f"Send the record at {address}, or one node without an address." if address else "Send one record: one node that no other node links to.")
    return found, tops[0]


def rendered(address: str, found: Graph, kind: str) -> Response:
    """Return the page of a record from the sent statements, without storing it."""
    for _, _, own in writes.separate(found):
        found += own
    shown = documents.public(records.with_names(found))
    node = URIRef(address)
    description = str(shown.value(node, SDO.description) or "")
    if kind in records.within(str(SDO.WebPage)):
        listed = pages.sections(shown, node)
        about = shown.value(node, SDO.about)
        page = {"name": str(shown.value(node, SDO.name) or ""), "description": description, "sections": listed,
                "tabbed": any(section["heading"] for section in listed), "kinds": pages.kinds(str(about)) if about is not None else []}
        return Response(render_template("records/page.html", page=page), mimetype="text/html")
    names = {}
    for iri, name in shown.subject_objects(SDO.name):
        names[str(iri)] = str(name)
    outline = pages.node_outline(shown, node, names)
    outline["named_on"] = pages.named_on(tables.Record(iri=address))
    record = {"iri": address, "name": outline["name"], "description": description, "image": str(shown.value(node, SDO.image) or "")}
    return Response(render_template("records/record.html", record=record, outline=outline), mimetype="text/html")


def store(address: str, body: dict, preview: bool = False, page: bool = False):
    """Check and store the record in body at address, and return the warnings."""
    kind = kind_at(address, body)
    who = writer(kind)
    # A text with a lone surrogate, such as \ud800, cannot be stored.
    try:
        json.dumps(body, ensure_ascii=False).encode()
    except UnicodeEncodeError:
        abort(422, message="Only valid Unicode text, without lone surrogates such as \\ud800.")
    kind = writes.class_of(settings()["kinds"][kind], body)
    try:
        found = documents.statements(writes.document(kind, address, body))
    except ValueError as problem:
        abort(422, message=str(problem))
    writes.kept(found, address, kind)
    writes.classed(found, address)
    # Only http and https addresses are accepted, so that no script (javascript:) or file address is stored as a link, nor
    # as a text in a field of links.
    for holder, predicate, value in found:
        linked = isinstance(value, URIRef) or urlsplit(str(value)).scheme not in ("", "http", "https") and any(
            field["iri"] == str(predicate) and field["iris"] and not field["texts"] for field in fields_of(records.class_of(found, holder)))
        if linked and predicate != RDF.type and not written(str(value)):
            abort(422, message=f"{jsonld_name(str(predicate))}: only https:// or http:// addresses.")
    writes.addressed(found)
    found, warnings, recommended = checks.checked(documents.document(found, address))
    for path, messages in recommended.items():
        warnings.setdefault(path, []).extend(messages)
    if preview and page:
        return rendered(address, found, kind)
    if preview:
        before = changes.statements(documents.document_of(address))
        labels = {}
        for path in warnings:
            labels[path] = checks.named(kind, path)
        return jsonify({**changes.edges(before, found, URIRef(address)), "warnings": warnings, "labels": labels,
                        "document": documents.document(records.with_names(found), address)})
    unchanged(address)
    created = writes.separate(found)
    # Write access is also required to the kind of each new record in the request, such as a person.
    for _, of_kind, _ in created:
        writer(kind_of(None, {"@type": of_kind}))
    for iri, of_kind, own in created:
        writes.save(documents.document(own, iri), of_kind, who.name, who.orcid)
    revision = writes.save(documents.document(found, address), kind, who.name, who.orcid)
    return done(address, revision, 201 if revision.action == "Added" else 200, warnings)


def formats(description: str, media: list[str]) -> dict:
    """Document the response in each format; the examples are taken from the records (described)."""
    content = {}
    for name in media:
        content[name] = {"schema": {"type": "string"}}
    return {"200": {"description": description, "content": content}}


def found_record(path: str):
    """Return the record at a page address, also if it was moved or removed."""
    record = records.get(records.address(path))
    if record is None:
        abort(404, message="No record at this address.")
    return record


# A text searched for is at most as long as a registry takes it, and holds no NUL, which ends a text in SQLite.
TEXT = validate.And(validate.Length(max=200), validate.ContainsNoneOf(["\x00"]))


class Search(Schema):
    text = fields.String(load_default="", validate=TEXT, metadata={"description": "Text in the name or the address."})
    of_class = fields.List(fields.Url(metadata={"format": "iri"}), data_key="class", load_default=list, metadata={"description": "Classes (IRIs) of the records or terms. Subclasses are included."})
    within = fields.String(load_default="", metadata={"description": "The start of the address, such as a vocabulary namespace."})
    vocabulary = fields.Url(load_default="", metadata={"format": "iri", "description": "The IRI of a vocabulary. Only its terms are searched."})
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=200), metadata={"description": "The maximum number of results."})


class Registry(Schema):
    text = fields.String(load_default="", validate=TEXT, metadata={"description": "Text in the name of a vocabulary or a term."})
    namespace = fields.String(load_default="", metadata={"description": "The namespace of the vocabulary that is searched, such as the namespace of a vocabulary record."})


ADDRESS = {"type": "string", "format": "uri"}
INDEX = {"type": "object", "required": ["title", "start", "search", "kinds", "openapi"], "properties": {
    "title": {"type": "string", "description": "The name of the platform."},
    "start": {"type": "string", "description": "Where to start, to answer a question."},
    "index": {**ADDRESS, "description": "This index of the API."},
    "search": {**ADDRESS, "description": "An example search of all records; the text is in the text parameter."},
    "record": {**ADDRESS, "description": "An example record. Each record is at api/<kind>/<name>, and its page is at <kind>/<name>."},
    "kinds": {"type": "object", "description": "The listing of each kind of record, by kind.", "additionalProperties": ADDRESS},
    "openapi": {**ADDRESS, "description": "The OpenAPI description of all operations."},
    "documentation": {**ADDRESS, "description": "The documentation of the operations, in HTML."},
    "dump": {**ADDRESS, "description": "All records in one file, in N-Triples or Turtle."},
    "terms": {**ADDRESS, "description": "The vocabulary terms that the records use, in one file."},
    "shapes": {**ADDRESS, "description": "The SHACL shapes: the fields of each kind of record."},
    "void": {**ADDRESS, "description": "The VoID description of the dataset, with its licence."},
    "catalog": {**ADDRESS, "description": "The API catalog of the platform (RFC 9727)."},
    "llms": {**ADDRESS, "description": "What the platform holds and where to start, in Markdown (llms.txt)."},
}}

# The fields of the JSON responses, so that agents and tool generators know them before the call.
CONTEXT = {"type": "object", "description": "The JSON-LD context: the prefixes and the JSON names of the fields."}
FOUND = {"type": "object", "required": ["@id", "@type", "name"], "properties": {
    "@id": {**ADDRESS, "description": "The address of the record, part or term. The page of a record is at this address, and the record in JSON-LD is at api/ followed by its page path."},
    "@type": {"type": "string", "description": "The class of the record, by its JSON-LD name, such as SoftwareApplication."},
    "name": {"type": "string", "description": "The name, or the address when there is no name."},
}}
SEARCHED = {"type": "object", "required": ["@context", "@graph"], "properties": {
    "@context": CONTEXT, "@graph": {"type": "array", "items": FOUND, "description": "The records, parts and terms found."}}}
LISTING = {"type": "object", "required": ["@context", "@graph"], "properties": {
    "@context": CONTEXT, "@graph": {"type": "array", "items": {"type": "object"}, "description": "The records of the page, with their fields."}}}
REGISTRIES = {"type": "object", "description": "The title of each registry, by its name.", "additionalProperties": {"type": "string"}}
VOCABULARY = {"type": "object", "properties": {
    "id": {"type": "string", "description": "The identifier of the vocabulary in the registry."},
    "title": {"type": "string"},
    "namespace": {**ADDRESS, "description": "The start of the addresses of the terms."},
    "description": {"type": "string"},
    "prefix": {"type": "string", "description": "The prefix of the compact identifiers of the terms."},
}}
TERMS = {"type": "object", "required": ["registry", "terms"], "properties": {
    "registry": {"type": ["string", "null"], "description": "The name of the registry that serves the namespace, or null."},
    "title": {"type": ["string", "null"], "description": "The title of the registry."},
    "terms": {"type": "array", "items": {"type": "object", "required": ["@id", "name"], "properties": {
        "@id": ADDRESS, "name": {"type": "string"}, "description": {"type": "string"}, "code": {"type": "string", "description": "The compact identifier: the prefix of the vocabulary and the local name."}}}},
}}


@blueprint.get("/registries", tags=["registries"])
@blueprint.doc(operationId="listRegistries")
@blueprint.response(200, REGISTRIES, example=PROVIDERS)
@blueprint.doc(description="Return the title of each vocabulary registry, by the name that the other registry operations take.")
def registries():
    """List the vocabulary registries."""
    return jsonify(PROVIDERS)


@blueprint.get("/registries/<registry>/vocabularies", tags=["registries"])
@blueprint.doc(operationId="listRegistryVocabularies")
@blueprint.arguments(Registry, location="query")
@blueprint.response(200, {"type": "array", "items": VOCABULARY})
@blueprint.doc(description="Return up to 50 vocabularies with the text in the identifier or the title.")
@limiter.limit(REGISTRY_LIMIT, override_defaults=False)
def registry_vocabularies(given, registry):
    """Search the vocabularies of a registry."""
    if registry not in PROVIDERS:
        abort(404, message="No such registry.")
    with Ontologies(registry, cache=database.STATE_DIR / "registries.json") as provider:
        return jsonify(provider.vocabularies(given["text"])[:50])


@blueprint.get("/registries/terms", tags=["registries"])
@blueprint.doc(operationId="searchRegistryTerms")
@blueprint.arguments(Registry, location="query")
@blueprint.response(200, TERMS)
@blueprint.doc(description=(
    "Return the terms of the namespace with the text in the name. The terms are read from the registry of the "
    "namespace."
))
@limiter.limit(REGISTRY_LIMIT, override_defaults=False)
def registry_terms(given):
    """Search the terms of a vocabulary."""
    if not given["text"].strip() or not given["namespace"]:
        return jsonify({"registry": None, "terms": []})
    registry = serving(given["namespace"], cache=database.STATE_DIR / "registries.json")
    found = []
    if registry:
        with Ontologies(registry, cache=database.STATE_DIR / "registries.json") as provider:
            for term in provider.terms(given["text"], given["namespace"]):
                found.append({"@id": term["iri"], "name": term.get("label") or term["iri"],
                              "description": " ".join(term.get("description") or []), "code": term["code"]})
    return jsonify({"registry": registry, "title": PROVIDERS.get(registry), "terms": found})




# The index is at /api and at /api/, as the API catalog anchors the API at /api.
@blueprint.get("/", strict_slashes=False)
@blueprint.doc(operationId="getApiIndex")
@blueprint.response(200, INDEX, content_type="application/json")
@blueprint.doc(description="Return the addresses where agents and scripts start: search, the record kinds, the downloads and the "
               "descriptions of the API. The API catalog at /.well-known/api-catalog points here.")
def index():
    """List the entry points of the API."""
    return jsonify(pages.entry_points())


@blueprint.get("/search")
@blueprint.doc(operationId="searchRecords")
@blueprint.arguments(Search, location="query")
@blueprint.response(200, SEARCHED, content_type="application/ld+json")
@blueprint.doc(description="Return the records, parts and terms with the text in the name or the address.")
def search(given):
    """Search records and vocabulary terms."""
    among = records.nodes_with(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet), [given["vocabulary"]]) if given["vocabulary"] else None
    return Response(json.dumps(searched(given["text"], given["of_class"], given["within"], given["limit"], among)), mimetype="application/ld+json")


def searched(text: str, classes: list[str] | None = None, within: str = "", limit: int = 20, among=None) -> dict:
    """Return the records, parts and terms with text in the name or the address, as the search returns them."""
    found = []
    for record in records.search(text, classes or list(settings()["kinds"].values()), within, limit=limit, among=among):
        found.append({"@id": record.iri, "@type": jsonld_name(record.type), "name": record.name or record.iri})
    return {"@context": documents.context(settings()), "@graph": found}


class FacetValue(Schema):
    value = fields.String(metadata={"description": "The value as used in a filter: an IRI, or a text from a list."})
    name = fields.String(metadata={"description": "The name of the record or the label of the term."})
    count = fields.Integer(metadata={"description": "The number of records with the value."})
    fits = fields.Boolean(metadata={"description": "False if the value does not fit the field: a text where a link is required, or a value that is not in the list."})


class Query(Schema):
    # No example, as Swagger UI fills in an example, and an optional filter then changes the list.
    search = fields.String(load_default="", validate=TEXT, metadata={"description": "Text in the name or the address of the record. The case is ignored."})

    class Meta:
        unknown = INCLUDE

    @pre_load
    def every_value(self, data, **kwargs):
        """Keep all values of a field filter."""
        found = {}
        for name in data:
            found[name] = data[name] if name in self.fields else data.getlist(name)
        return found


class Listing(Query):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1, max=records.PAGES), metadata={"description": "The number of the page."})
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=200), metadata={"description": "The number of records on a page."})


def filtered(of_class: str, given: dict) -> dict:
    """Return the filters of a listing, and refuse a filter that the kind has not, as it would otherwise filter nothing
    unseen."""
    names = sorted(field["name"] for field in fields_of(of_class) if records.browsed(field))
    unknown = sorted(set(given) - set(names) - set(Listing().fields))
    if unknown:
        abort(422, message=f"No filter {', '.join(unknown)}; the filters of this kind are {', '.join(names)}.", errors={"query": {name: ["Unknown filter."] for name in unknown}})
    return records.filters(of_class, given)


# The number of records and pages of a listing, as made by flask-smorest, in JSON.
PAGED = {"X-Pagination": {"description": "The number of records and of pages, and the numbers of the first, last, previous and next page.", "content": {"application/json": {"schema": {
    "type": "object", "required": ["total", "total_pages"], "properties": {name: {"type": "integer"} for name in ("total", "total_pages", "first_page", "last_page", "page", "previous_page", "next_page")}}}}}}


KIND = "/<any({}):kind>".format(", ".join(settings()["kinds"]))
OF_KIND = [{"in": "path", "name": "kind", "description": "The kind of the records.", "example": "tools",
            "schema": {"type": "string", "enum": list(settings()["kinds"])}}]
AT_PATH = [{"in": "path", "name": "path", "description": "The page address of the record, without the base address: <kind>/<name>."}]
LISTED = "One page of records, in the format requested in the Accept header."


@blueprint.route(KIND, methods=["GET"], parameters=OF_KIND)
@blueprint.doc(operationId="listRecords")
@blueprint.response(200, LISTING, content_type="application/ld+json", description=LISTED, headers=PAGED)
@blueprint.alt_response(200, schema={"type": "string"}, content_type="text/turtle", success=True, description=LISTED, headers=PAGED)
@blueprint.alt_response(200, schema={"type": "string"}, content_type="application/n-triples", success=True, description=LISTED, headers=PAGED)
@blueprint.alt_response(200, schema={"type": "string"}, content_type="text/markdown", success=True, description=LISTED, headers=PAGED)
@blueprint.arguments(Listing, location="query", unknown=INCLUDE)
@blueprint.doc(description=(
    "Return one page of records, sorted by name, in the format of the Accept header. Find records by name or "
    "address with search. Filter records by the fields below: give several values of one field to find the records "
    "with any of them, and several fields to find the records that match all of them. The number of records is in "
    "the X-Pagination header."
))
def listed(given, kind):
    """List the records of a kind."""
    of_class = settings()["kinds"][kind]
    # At the address of a kind (/tools.ttl), all records of the kind are returned as one file, not as pages.
    page, size = (1, None) if "listing" in g else (given["page"], given["page_size"])
    total, iris = records.page(of_class, filtered(of_class, given), given["search"], (page - 1) * (size or 0), size)
    found = readable(records.graph(iris), kind)
    # The format requested at the page of a kind (/tools) is used, also when it is requested with a file extension (/tools.ttl).
    media = g.get("media") or request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS, "text/markdown"], "application/ld+json")
    if media == "text/markdown":
        texts = []
        for iri in iris:
            texts.append(markdown_of(records.get(iri)).get_data(as_text=True))
        answer = Response("\n".join(texts), content_type=pages.MEDIA, headers={"Vary": "Accept"})
    elif media in SERIALIZATIONS:
        answer = data(found, media)
    else:
        documented = []
        for iri in iris:
            document = documents.document(found, iri)
            document.pop("@context", None)
            documented.append(document)
        answer = Response(json.dumps({"@context": documents.context(settings()), "@graph": documented}, indent=1), mimetype="application/ld+json", headers={"Vary": "Accept"})
    answer.headers["X-Pagination"] = json.dumps(blueprint._make_pagination_metadata(page, size or max(total, 1), total))
    return answer


@blueprint.get(KIND + "/facets", parameters=OF_KIND)
@blueprint.doc(operationId="countFieldValues")
@blueprint.arguments(Query, location="query", unknown=INCLUDE)
@blueprint.response(200, {"type": "object", "additionalProperties": {"type": "array", "items": {"$ref": "#/components/schemas/FacetValue"}}},
                    description="The values of each field, by the name of the field.")
@blueprint.doc(description=(
    "Return the number of records for each value of each filter field, for the same query as the list. The filter "
    "of a field is not applied to the counts of that field."
))
def counted(given, kind):
    """Count the records of a kind by field value."""
    filtered(settings()["kinds"][kind], given)
    return jsonify(records.counted(settings()["kinds"][kind], given))


def vocabulary_kind(kind: str) -> bool:
    """Return True if the records of kind are terms of a vocabulary."""
    return any(field["iri"] == str(SDO.inDefinedTermSet) for field in fields_of(settings()["kinds"][kind]))


@blueprint.post(KIND, tags=["editing"], parameters=OF_KIND)
@blueprint.doc(operationId="addRecord")
@blueprint.arguments(Record, content_type="application/ld+json")
@blueprint.response(201, Done, description="Added.")
@blueprint.doc(**WRITE)
@blueprint.doc(description=(
    "Store a new record of the kind, sent in JSON-LD or Turtle, at an address made from the name. Store a "
    "vocabulary term at the address in @id. Store a record that does not fit the shapes too, and return the "
    "problems as warnings."
))
def added(body, kind):
    """Add a record."""
    # In Turtle or in JSON-LD with a context, the record is the node that no other node links to, and its http or https
    # address is its @id.
    given = sent(body)
    if given is not None:
        found, node = given
        body = {"@id": str(node)} if web(node) else {"name": str(found.value(node, SDO.name) or "")}
    # A term of a vocabulary is stored at the address in @id. Other records are stored at an address made from the name.
    if body.get("@id") is not None and not (web(body["@id"]) and vocabulary_kind(kind)):
        abort(422, message="Send @id only for a term of a vocabulary, as an http or https address.")
    address = body.get("@id") or writes.free(records.address(f"{kind}/{writes.slug(str(body.get('name') or kind))}"), set())
    if records.get(address) is not None:
        abort(409, message="Address taken.")
    if given is not None:
        writes.renamed(found, node, address)
        body = documents.document(found, address)
    body = {"@type": jsonld_name(settings()["kinds"][kind]), **body}
    return store(address, body)


@blueprint.get("/<path:path>", parameters=AT_PATH)
@blueprint.doc(operationId="getRecord")
@blueprint.doc(responses=formats("The record, in the format requested in the Accept header.", ["application/ld+json", *SERIALIZATIONS, "text/markdown"]))
@blueprint.doc(description=(
    "Return the record or part at a page address, <kind>/<name>, in the format of the Accept header. The"
    " version of the record is sent in the ETag header. Redirect a moved record, and return 410 Gone for a removed "
    "record."
))
def read(path):
    """Get a record."""
    record = found_record(path)
    if record.moved_to:
        return redirect(url_for("records.read", path=records.path(record.moved_to)), code=301)
    if record.removed_at:
        abort(410, message="Removed.")
    media = request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS, "text/markdown"]) or "application/ld+json"
    if media == "text/markdown":
        return markdown_of(record)
    # A part, such as a case-study question, is read with the access rights of its record.
    kind = kind_of(record.part_of or record.iri, {})
    answer = data(readable(records.with_names(records.graph([record.iri])), kind), media, record.iri)
    answer.headers["ETag"] = f'"{record.updated_at}"'
    return answer


@blueprint.put("/<path:path>", tags=["editing"], parameters=AT_PATH)
@blueprint.doc(operationId="replaceRecord")
@blueprint.arguments(Writing, location="query")
@blueprint.arguments(Record, content_type="application/ld+json")
@blueprint.response(200, Done, description="Replaced. With preview=true, the changes and the warnings are returned, and nothing is stored.")
@blueprint.alt_response(201, schema=Done, description="Added.")
@blueprint.doc(**WRITE)
@blueprint.doc(description=(
    "Store the record, sent in JSON-LD or Turtle, at the page address. Refuse the write with 412 if the version in "
    "If-Match is older than the stored record. With preview=true, store nothing, and return the changes and the "
    "warnings."
))
def replace(given, body, path):
    """Add or replace a record at an address."""
    address = records.address(path)
    record = records.get(address)
    whole(record)
    if record is not None and (record.moved_to or record.removed_at):
        abort(409, message="Address of a moved or removed record; not reused.")
    if not given["preview"]:
        editable(record)
    received = sent(body, address)
    if received is not None:
        found, node = received
        writes.renamed(found, node, address)
        body = documents.document(found, address)
    return store(address, body, given["preview"], given["page"])


@blueprint.delete("/<path:path>", tags=["editing"], parameters=AT_PATH)
@blueprint.doc(operationId="removeRecord")
@blueprint.arguments(Removal, location="query")
@blueprint.response(200, Done, description="Removed.")
@blueprint.doc(security=TOKEN)
@blueprint.doc(description=(
    "Remove the record with its parts. Return 410 Gone at its address from then on, unless permanent=true is set. "
    "Restore a removed record with POST /api/restore."
))
def remove(given, path):
    """Remove a record."""
    record = found_record(path)
    if record.removed_at and not given["permanent"]:
        abort(404, message="No record at this address.")
    whole(record)
    editable(record)
    who = writer(kind_of(record.iri, {}))
    unchanged(record.iri)
    if given["permanent"]:
        return done(record.iri, writes.remove(record.iri, who.name, who.orcid), 200)
    return done(record.iri, writes.retire(record.iri, who.name, who.orcid), 200)


@blueprint.post("/move", tags=["editing"])
@blueprint.doc(operationId="moveRecord")
@blueprint.arguments(Move)
@blueprint.response(200, Done, description="Moved.")
@blueprint.doc(security=TOKEN)
@blueprint.doc(description="Move the record with its parts, and redirect the old address to the new address.")
def move(body):
    """Move a record to a new address."""
    record = found_record(body["record"])
    if record.removed_at:
        abort(404, message="No record at this address.")
    whole(record)
    editable(record)
    kind = kind_of(record.iri, {})
    who = writer(kind)
    # The new address is a page address on the platform, in the kind of the record, or an earlier address of the record.
    address = settings()["base"] + body["to"].strip("/")
    if address == record.iri:
        abort(409, message="The record is at this address already.")
    target = records.get(address)
    if target is not None and target.moved_to != record.iri:
        abort(409, message="Address taken, now or before.")
    if target is None:
        placed(address, kind)
    unchanged(record.iri)
    return done(address, writes.move(record.iri, address, who.name, who.orcid), 200)


@blueprint.post("/restore", tags=["editing"])
@blueprint.doc(operationId="restoreRecord")
@blueprint.arguments(Restore)
@blueprint.response(200, Done, description="Restored.")
@blueprint.doc(security=TOKEN, description=(
    "Restore the removed record at the address and its parts, with the values they had when they were removed. A moved "
    "record is not restored, as its old address redirects to the new one."
))
def restore(body):
    """Restore a removed record."""
    record = found_record(body["record"])
    if not record.removed_at or record.moved_to:
        abort(404, message="No removed record at this address.")
    whole(record)
    editable(record)
    who = writer(kind_of(record.iri, {}))
    return done(record.iri, writes.restore(record.iri, who.name, who.orcid), 200)


@blueprint.post("/images", tags=["editing"])
@blueprint.doc(operationId="uploadImage")
@blueprint.response(201, Image, description="Uploaded.")
@blueprint.doc(security=TOKEN)
@blueprint.doc(description=(
    "Store an image, sent in the form field image, as WebP, and return its address. Refuse images over 5 MB."
))
def upload_image():
    """Upload an image."""
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


@blueprint.get("/dump", tags=["downloads"])
@blueprint.doc(operationId="downloadRecords")
@blueprint.doc(responses=formats("All records, in the format requested in the Accept header.", ["application/n-triples", "text/turtle"]))
@blueprint.doc(description=(
    "Return all records with a page, with their parts, in N-Triples (the default) or Turtle, without private "
    "fields. The dataset is described at /.well-known/void."
))
def dump():
    """Download all records."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published(), media)


@blueprint.get("/dump/terms", tags=["downloads"])
@blueprint.doc(operationId="downloadTerms")
@blueprint.doc(responses=formats("The vocabulary terms, in the format requested in the Accept header.", ["application/n-triples", "text/turtle"]))
@blueprint.doc(description=(
    "Return the vocabulary terms linked from the records, in N-Triples (the default) or Turtle. The source and the "
    "licence of each vocabulary are described at /.well-known/void."
))
def dump_terms():
    """Download the vocabulary terms in use."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published_terms(), media)


@blueprint.get("/shapes.ttl", tags=["downloads"])
@blueprint.doc(operationId="getShapes")
@blueprint.doc(responses=formats("The shapes, in Turtle.", ["text/turtle"]))
@blueprint.doc(description=(
    "Return the shapes in Turtle, with the fields of each kind of record, their JSON-LD names and their allowed "
    "values."
))
def model_shapes():
    """Get the SHACL shapes of the model."""
    return Response(shapes().serialize(format="turtle"), mimetype="text/turtle")


def shortened(value):
    """Return a JSON-LD value with the first value of each array only, so that an example shows each field, and is short."""
    if isinstance(value, list):
        return [shortened(value[0])] if value else []
    if isinstance(value, dict):
        return {name: shortened(given) for name, given in value.items()}
    return value


def example_documents(iris: list[str]) -> dict[str, dict]:
    """Return the records at iris as the API returns them to visitors in JSON-LD, shortened, without their context."""
    found = documents.public(records.with_names(records.graph(iris)))
    shown = {}
    for iri in iris:
        document = documents.document(found, iri, named=True)
        document.pop("@context", None)
        shown[iri] = shortened(document)
    return shown


def camel(text: str) -> str:
    """Return a label or a kind as one word, for an operationId: Case study gives CaseStudy."""
    return "".join(word[:1].upper() + word[1:] for word in re.findall(r"[A-Za-z0-9]+", text))


def for_kind(template: dict, kind: str, operation: str, summary: str, parameters: list | None = None) -> dict:
    """Return a copy of an operation of all kinds for the records of one kind."""
    found = copy.deepcopy(template)
    found.update(operationId=operation, summary=summary, tags=[kind])
    found["parameters"] = [*found.get("parameters", []), *(parameters or [])]
    return found


def described(spec: dict) -> dict:
    """Return the OpenAPI description with the schema of each kind of record, the operations of each kind with a filter
    for each field, and examples from the stored records (pages.examples and pages.first_record), so that each example
    works on this platform and nothing is written twice."""
    paths, components = spec["paths"], spec["components"]["schemas"]
    components.update(copy.deepcopy(schemas.schemas()))
    # The filters of a kind are written once, for its list and for its counts.
    shared = spec["components"].setdefault("parameters", {})
    listing, counting, reading = paths.pop("/api/{kind}"), paths.pop("/api/{kind}/facets"), paths.pop("/api/{path}")
    tags, mapping, addresses = [], {}, {}
    chosen = pages.examples()
    documented = example_documents(list(chosen.values()))
    for kind, of_class in settings()["kinds"].items():
        name, label, filters = schemas.kind_name(of_class), settings()["labels"][of_class], []
        for given in schemas.filters(of_class):
            key = re.sub(r"[^A-Za-z0-9._-]", "_", f"{name}.{given['name']}")
            shared[key] = given
            filters.append({"$ref": "#/components/parameters/" + key})
        record = {"$ref": schemas.REF + name}
        mapping[jsonld_name(of_class)] = schemas.REF + name
        iri = chosen.get(of_class)
        if iri:
            components[name]["examples"] = [documented[iri]]
            if pages.readable_at(iri):
                addresses[kind] = {"summary": label, "value": records.path(iri)}
        listed = for_kind(listing["get"], kind, "list" + camel(kind), f"List {label} records", filters)
        listed["responses"]["200"]["content"]["application/ld+json"]["schema"]["properties"]["@graph"]["items"] = record
        counted = for_kind(counting["get"], kind, f"count{camel(label)}Values", f"Count {label} records by field value", filters)
        counted["responses"]["200"]["content"]["application/json"]["schema"] = {
            "type": "object", "description": "The values of each filter field, by the name of the field.",
            "propertyNames": {"enum": [shared[given["$ref"].rsplit("/", 1)[-1]]["name"] for given in filters]},
            "additionalProperties": {"type": "array", "items": {"$ref": schemas.REF + "FacetValue"}}}
        added = for_kind(listing["post"], kind, f"add{camel(label)}", f"Add a {label} record")
        added["requestBody"]["content"]["application/ld+json"]["schema"] = record
        paths[f"/api/{kind}"] = {"get": listed, "post": added}
        paths[f"/api/{kind}/facets"] = {"get": counted}
        tags.append({"name": kind, "description": f"{label} records, of the class {jsonld_name(of_class)}, with the fields of the schema {name}. {components[name]['description']}"})
    # A record of any kind, told apart by its class: the class of its kind, a class below it, or the class of a part.
    for of_class, part in records.types():
        mapping.setdefault(jsonld_name(of_class), schemas.REF + ("Part" if part or of_class not in kinds() else schemas.kind_name(settings()["kinds"][kinds()[of_class]])))
    anything = {"anyOf": [{"$ref": ref} for ref in dict.fromkeys(mapping.values())], "discriminator": {"propertyName": "@type", "mapping": mapping}}
    reading["get"]["responses"]["200"]["content"]["application/ld+json"]["schema"] = anything
    reading["put"]["requestBody"]["content"]["application/ld+json"]["schema"] = anything
    # The schema of the request bodies, of any record, is replaced by those of the kinds.
    components.pop("Record")
    # The errors are problem details, as problem_details returns them, in place of the Error of flask-smorest. A record
    # may be moved or removed, and each operation is limited.
    components.pop("Error")
    components["ProblemDetails"] = PROBLEM
    responses = spec["components"].setdefault("responses", {})
    for name, status in (("NOT_FOUND", 404), ("GONE", 410), ("TOO_MANY_REQUESTS", 429)):
        responses[name] = {"description": HTTPStatus(status).phrase}
    for response in responses.values():
        response["content"] = {"application/problem+json": {"schema": {"$ref": schemas.REF + "ProblemDetails"}}}
    reading["get"]["responses"].update({"301": {"description": "Moved: the record is at the address in Location."},
                                        "404": {"$ref": "#/components/responses/NOT_FOUND"}, "410": {"$ref": "#/components/responses/GONE"}})
    for _, _, operation in [(path, method, operation) for path, methods in [*paths.items(), ("/api/{path}", reading)] for method, operation in methods.items() if method != "parameters"]:
        operation["responses"]["429"] = {"$ref": "#/components/responses/TOO_MANY_REQUESTS"}
    for parameter in reading.get("parameters", []):
        if parameter["name"] == "path" and addresses:
            parameter["examples"] = addresses
    paths["/api/{path}"] = reading
    spec["tags"] = [*tags, *spec.get("tags", [])]
    # The other examples are those of the first record, as in the entry points.
    shown = pages.first_record()
    if shown is not None:
        found = records.graph([shown.iri])
        content = reading["get"]["responses"]["200"]["content"]
        for media in SERIALIZATIONS:
            content[media]["example"] = data(documents.public(Graph() + found), media).get_data(as_text=True)
        content["text/markdown"]["example"] = markdown_of(shown).get_data(as_text=True)
        searching = paths["/api/search"]["get"]
        text = (shown.name or "").split(" ")[0]
        next(given for given in searching["parameters"] if given["name"] == "text")["example"] = text
        searching["responses"]["200"]["content"]["application/ld+json"]["example"] = searched(text, limit=3)
    paths["/api/"]["get"]["responses"]["200"]["content"]["application/json"]["example"] = pages.entry_points()
    spec["info"]["description"] = DESCRIPTION.format(**start(shown))
    return spec


def start(shown) -> dict:
    """Return the values of the description of the API: the kinds, and the search, record and filter of the example."""
    kinds = settings()["kinds"]
    kind, of_class = next(((kind, of_class) for kind, of_class in kinds.items() if shown is not None and shown.iri.startswith(records.address(kind) + "/")),
                          next(iter(kinds.items())))
    found = {"kinds": ", ".join(label.lower() for label in settings()["labels"].values()), "limit": LIMIT, "text": "<text>",
             "record": "<kind>/<name>", "kind": kind, "filter": "<field>=<value>"}
    if shown is not None:
        found.update(text=quote_plus((shown.name or "").split(" ")[0]), record=records.path(shown.iri))
        for name, values in records.counted(of_class, {"search": ""}).items():
            used = next((value["value"] for value in values if value["count"] and value["fits"]), None)
            if used:
                found["filter"] = f"{name}={quote(used, safe=':/')}"
                break
    return found


def hint(code: int) -> str:
    """Return what an agent can try after an error with the status code."""
    found = pages.entry_points()
    if code in (404, 410):
        return f"Search the records at {found['search']}, or see the entry points at {found['index']}."
    if code in (401, 403):
        return ("Reading needs no token. A write needs a write token for the kind of the record, sent as "
                f"Authorization: Bearer <token>; editors make tokens at {records.address('account/tokens')}/.")
    if code in (400, 422):
        return f"Check the parameters and the body against the operation in {found['openapi']}."
    if code == 429:
        return "Too many requests: wait a minute, then try again."
    return f"See the operations in {found['openapi']}, and the entry points at {found['index']}."


# The fields of problem_details, for the description.
PROBLEM = {"type": "object", "required": ["type", "title", "status", "detail", "hint"], "description": "An error, as problem details (RFC 9457), with a hint of what to try next.", "properties": {
    "type": {"type": "string", "description": "about:blank, as the status tells the error."},
    "title": {"type": "string", "description": "The name of the status, such as Not Found."},
    "status": {"type": "integer", "description": "The status code."},
    "detail": {"type": "string", "description": "What is wrong."},
    "hint": {"type": "string", "description": "What to try next."},
    "code": {"type": "integer", "description": "The status code, as flask-smorest also sends it."},
    "message": {"type": "string", "description": "What is wrong, as flask-smorest also sends it."},
    "errors": {"type": "object", "description": "The problems found in each part of the request, such as query or json, by field."}}}


def problem_details(problem: HTTPException, payload: dict, code: int, headers: dict) -> Response:
    """Return an error as problem details (RFC 9457) with a hint, keeping the code, message and errors of flask-smorest,
    and the headers of the error, such as Allow of 405."""
    body = {"type": "about:blank", "title": problem.name, "status": code, "detail": payload.get("message") or problem.description,
            "hint": hint(code)}
    for name in ("code", "message", "errors"):
        if name in payload:
            body[name] = payload[name]
    kept = {name: value for name, value in problem.get_headers() if name.lower() != "content-type"}
    return Response(json.dumps(body), status=code, headers={**kept, **(headers or {})}, content_type="application/problem+json")


def register(app) -> None:
    """Add the API to the app, with the OpenAPI document at /api/docs/ and the error pages of the app."""
    app.config.update(
        API_TITLE=settings()["title"],
        API_VERSION=RELEASE,
        OPENAPI_VERSION="3.1.0",
        OPENAPI_URL_PREFIX="/api/docs",
        OPENAPI_JSON_PATH="openapi.json",
        OPENAPI_SWAGGER_UI_PATH="/",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.20.1/",
        # The server is this copy of the platform.
        API_SPEC_OPTIONS={"info": {"description": DESCRIPTION}, "servers": [{"url": "/", "description": "This platform"}]},
        # GET operations are run at once, an operation has its own link, and the token is kept after a reload.
        OPENAPI_SWAGGER_UI_CONFIG={"tryItOutEnabled": True, "deepLinking": True, "persistAuthorization": True, "displayRequestDuration": True},
    )
    api = Api(app)

    # Errors are returned as problem details (RFC 9457), with the fields of flask-smorest. For pages requested by
    # browsers, an HTML error page is returned with the same status code.
    @app.errorhandler(HTTPException)
    def error_page(problem: HTTPException):
        if request.path.startswith("/api/") or not any(media == "text/html" for media, _ in request.accept_mimetypes):
            return problem_details(problem, *api.handle_http_exception(problem))
        return render_template("error.html", error=problem, page_title=f"{problem.code} {problem.name} — VHP4Safety",
                               meta_description=problem.description or problem.name), problem.code
    api.spec.components.security_scheme("token", {"type": "http", "scheme": "bearer", "description": "A write token, sent as `Authorization: Bearer <token>`. Make tokens at `/account/tokens/`. A token is valid for the kinds chosen for it, for 90 days by default."})
    api.spec.components.schema("FacetValue", schema=FacetValue)
    api.register_blueprint(blueprint)
    for tag in TAGS:
        api.spec.tag(tag)

    # The description is made again when a record changes, as its examples are taken from the records.
    @lru_cache(maxsize=8)
    def openapi(state: str, version: str) -> str:
        return json.dumps(described(copy.deepcopy(api.spec.to_dict())))

    def openapi_json():
        return Response(openapi(str(database.STATE_DIR), records.latest_change()), mimetype="application/json")

    app.view_functions["api-docs.openapi_json"] = openapi_json
