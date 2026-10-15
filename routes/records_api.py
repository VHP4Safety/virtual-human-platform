"""The platform's records as graphs of the W3C SPARQL 1.1 Graph Store HTTP Protocol, with flask-smorest: each
record is a graph, named by its address. GET /api/records?graph=<address> gives it in JSON-LD, Turtle or
N-Triples, as Accept asks; PUT adds or replaces it, POST /api/records adds a record at an address made from
its kind and name, and DELETE removes it.

A record is written in JSON-LD, with its fields named as the platform's JSON-LD context names them ("name",
"url", "about", ..., and "dct:conformsTo" for a field of another vocabulary), or with a context of its own;
a link is {"@id": "https://..."}. The model's SHACL shapes (/api/shapes.ttl) say what each field takes: a
record that does not fit is refused, with what is wrong with each field. Writing needs a write token, or an
editor's login on the editor page. A record's ETag is its version: a write that sends it in If-Match is
refused when the record has changed since. With preview=true, a write saves nothing and answers with what
it would change.
"""

import json

from flask import Response, jsonify, redirect, request, url_for
from flask_smorest import Api, Blueprint, abort
from marshmallow import INCLUDE, Schema, fields
from rdflib import Graph, URIRef
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

from admin import changes, tokens, writes
from database import images, records
from linkeddata import checks, documents, storage
from linkeddata.model import RELEASE, settings, shapes
from routes import account, limiter
from routes.record_pages import SERIALIZATIONS, data

blueprint = Blueprint("api", __name__, url_prefix="/api", description="The records, as graphs named by their addresses.")
limiter.limit("300 per minute")(blueprint)
TOKEN = [{"token": []}]


class Record(Schema.from_dict({"@type": fields.Raw(metadata={"description": "The record's class; a new record needs it."})})):
    """A record in JSON-LD. The model's SHACL shapes (/api/shapes.ttl) say what each field of its class takes."""

    class Meta:
        unknown = INCLUDE


class Address(Schema):
    graph = fields.Url(required=True, require_tld=False, metadata={"description": "The record's address, which names its graph."})


class Writing(Address):
    preview = fields.Boolean(load_default=False, metadata={"description": "Save nothing; answer with what the write would change."})


class Adding(Schema):
    preview = fields.Boolean(load_default=False, metadata={"description": "Save nothing; answer with what the write would change."})


class Removal(Address):
    permanent = fields.Boolean(load_default=False, metadata={"description": "Remove the address too, so that another record can have it."})


class Move(Schema):
    to = fields.Url(required=True, require_tld=False, metadata={"description": "The record's new address."})


class Done(Schema.from_dict({"@id": fields.String(metadata={"description": "The record's address."})})):
    """A change that is saved: the record's address, the change's page, the record's version, and the
    recommended fields that are empty."""

    change = fields.String()
    version = fields.String(allow_none=True)
    warnings = fields.Dict(keys=fields.String(), values=fields.List(fields.String()))


class Image(Schema.from_dict({"@id": fields.String(metadata={"description": "The image's address, to give in a record's image field."})})):
    pass


def kind_of(address: str | None, body: dict) -> str | None:
    """The kind of the record at an address, or of the class that a new record's @type names."""
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
    """Who makes the request (a token, or an editor of the editor page) when they may write records of *kind*."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return tokens.check(header.removeprefix("Bearer ").strip(), kind)
    return account.editor_of_request(kind)


def writer(kind: str | None):
    found = identity(kind) if kind is not None else None
    if found is None:
        abort(401, message="A valid write token for this kind of record, or an editor's login, is needed.")
    return found


def done(address: str, revision, status: int, warnings: dict | None = None):
    record = records.get(address)
    version = record.updated_at if record is not None else None
    headers = {"ETag": f'"{version}"'} if version else {}
    if status == 201:
        headers["Location"] = url_for("api.read", graph=address)
    return {"@id": address, "change": url_for("changes.change", number=revision.id), "version": version, "warnings": warnings or {}}, status, headers


def unchanged(address: str) -> None:
    """A write that names the version it read (If-Match) is refused when the record has changed since."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if expected and record is not None and record.updated_at != expected:
        abort(412, message="Someone else changed this record since you opened it. Open it again to see their change, then make yours.")


def store(address: str, body: dict, replace: bool, preview: bool):
    """The record of a request's body is checked and saved at *address*."""
    kind = kind_of(address, body)
    if kind is None:
        abort(400, message="The record's @type is not one of the platform's classes.")
    who = writer(kind)
    if "@context" in body:
        body = documents.document(Graph().parse(data=json.dumps(body), format="json-ld"), address)
    kind = settings()["kinds"][kind]
    try:
        found, problems, warnings = checks.checked(writes.document(kind, address, body))
    except ValueError as problem:
        abort(422, message=str(problem))
    if preview:
        before = changes.statements(documents.document_of(address))
        return jsonify({**changes.edges(before, found, URIRef(address)), "fields": problems, "warnings": warnings})
    unchanged(address)
    if problems:
        abort(422, message=str(checks.NotFitting(problems)), errors=problems)
    revision = writes.save(documents.document(found, address), kind, who.name, who.orcid, replace)
    return done(address, revision, 201 if revision.action == "Added" else 200, warnings)


@blueprint.get("/records")
@blueprint.arguments(Address, location="query")
@blueprint.doc(responses={"200": {"description": "The record, in the format that Accept asks for.", "content": {
    "application/ld+json": {"schema": {"$ref": "#/components/schemas/Record"}},
    "text/turtle": {"schema": {"type": "string"}},
    "application/n-triples": {"schema": {"type": "string"}},
}}})
def read(given):
    """A record, in JSON-LD, Turtle or N-Triples, as Accept asks."""
    record = records.get(given["graph"])
    if record is None:
        abort(404, message="There is no record at this address.")
    if record.moved_to:
        return redirect(url_for("api.read", graph=record.moved_to), code=301)
    if record.removed_at:
        abort(410, message="This record was removed.")
    media = request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS]) or "application/ld+json"
    answer = data(storage.read([record.iri]), media, record.iri)
    answer.headers["ETag"] = f'"{record.updated_at}"'
    return answer


@blueprint.put("/records")
@blueprint.arguments(Writing, location="query")
@blueprint.arguments(Record)
@blueprint.response(200, Done, description="The record was replaced; with preview=true, what the write would change.")
@blueprint.alt_response(201, schema=Done, description="The record was added.")
@blueprint.doc(security=TOKEN, requestBody={"content": {"text/turtle": {"schema": {"type": "string"}}}})
def replace(given, body):
    """Add or replace the record at this address, given in JSON-LD or in Turtle."""
    record = records.get(given["graph"])
    if record is not None and (record.moved_to or record.removed_at):
        abort(409, message="This address belongs to a record that moved or was removed, and is not written again.")
    if request.mimetype == "text/turtle":
        body = documents.document(Graph().parse(data=request.get_data(as_text=True), format="turtle"), given["graph"])
    return store(given["graph"], body, True, given["preview"])


@blueprint.post("/records")
@blueprint.arguments(Adding, location="query")
@blueprint.arguments(Record)
@blueprint.response(201, Done, description="The record was added; Location gives it. With preview=true, 200 and what the write would change.")
@blueprint.doc(security=TOKEN)
def add(given, body):
    """Add a record at an address made from its kind and its name.

    When another record has that address, a number is added to it."""
    kind = kind_of(None, body)
    name = body.get("name")
    if kind is None or not isinstance(name, str) or not name.strip():
        abort(400, message="A new record needs a name and an @type of one of the platform's classes.")
    identifier = writes.slug(name)
    number = 2
    while True:
        address = records.address(f"{kind}/{identifier}")
        if records.get(address) is None:
            try:
                return store(address, body, False, given["preview"])
            except IntegrityError:
                pass
        identifier = f"{writes.slug(name)}-{number}"
        number += 1


@blueprint.delete("/records")
@blueprint.arguments(Removal, location="query")
@blueprint.response(200, Done, description="The record was removed.")
@blueprint.doc(security=TOKEN)
def remove(given):
    """Remove a record.

    Its address answers 410 Gone from then on, and is not given to another record, unless the removal is
    permanent. A removed record can be put back with restore."""
    record = records.get(given["graph"])
    if record is None or (record.removed_at and not given["permanent"]):
        abort(404, message="There is no record at this address.")
    who = writer(kind_of(record.iri, {}))
    unchanged(record.iri)
    if given["permanent"]:
        return done(record.iri, writes.remove(record.iri, who.name, who.orcid), 200)
    return done(record.iri, writes.retire(record.iri, who.name, who.orcid), 200)


@blueprint.post("/records/move")
@blueprint.arguments(Address, location="query")
@blueprint.arguments(Move)
@blueprint.response(200, Done, description="The record moved; its old address forwards to the new one.")
@blueprint.doc(security=TOKEN)
def move(given, body):
    """Move a record to a new address; the old one forwards to it."""
    record = records.get(given["graph"])
    if record is None or record.removed_at:
        abort(404, message="There is no record at this address.")
    who = writer(kind_of(record.iri, {}))
    target = records.get(body["to"])
    if target is not None and target.moved_to != record.iri:
        abort(409, message="This address is taken by another record, or was one.")
    unchanged(record.iri)
    return done(body["to"], writes.move(record.iri, body["to"], who.name, who.orcid), 200)


@blueprint.post("/records/restore")
@blueprint.arguments(Address, location="query")
@blueprint.response(200, Done, description="The record was put back.")
@blueprint.doc(security=TOKEN)
def restore(given):
    """Put back a removed record."""
    record = records.get(given["graph"])
    if record is None or not record.removed_at:
        abort(404, message="There is no removed record at this address.")
    who = writer(kind_of(record.iri, {}))
    return done(record.iri, writes.restore(record.iri, who.name, who.orcid), 200)


@blueprint.post("/images")
@blueprint.response(201, Image)
@blueprint.doc(security=TOKEN)
def upload_image():
    """Upload an image, such as a tool's logo, as the form field "image".

    The image is checked and saved again as WebP; its address is what a record gives in its image field."""
    who = None
    for kind in settings()["kinds"]:
        who = who or identity(kind)
    if who is None:
        abort(401, message="A valid write token, or an editor's login, is needed.")
    request.max_content_length = images.MAX_BYTES
    try:
        upload = request.files.get("image")
    except RequestEntityTooLarge:
        abort(413, message="The image is larger than 5 MB.")
    if upload is None:
        abort(400, message='The image is sent as the form field "image".')
    try:
        return {"@id": images.store(upload.stream, who.name, who.orcid)}
    except ValueError as problem:
        abort(422, message=str(problem))


@blueprint.get("/shapes.ttl")
@blueprint.doc(responses={"200": {"description": "The shapes, in Turtle.", "content": {"text/turtle": {"schema": {"type": "string"}}}}})
def model_shapes():
    """The model's SHACL shapes, which say what each field of a record takes."""
    return Response(shapes().serialize(format="turtle"), mimetype="text/turtle")


def register(app) -> None:
    """The records API and its OpenAPI document, at /api/docs/records/."""
    app.config.update(
        RECORDS_API_TITLE=f"{settings()['title']}: records",
        RECORDS_API_VERSION=RELEASE,
        RECORDS_OPENAPI_VERSION="3.1.0",
        RECORDS_OPENAPI_URL_PREFIX="/api/docs/records",
        RECORDS_OPENAPI_JSON_PATH="openapi.json",
        RECORDS_OPENAPI_SWAGGER_UI_PATH="/swagger/",
        RECORDS_OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/",
        RECORDS_API_SPEC_OPTIONS={"info": {"description": __doc__}},
    )
    api = Api(app, config_prefix="RECORDS_")
    api.spec.components.security_scheme("token", {"type": "http", "scheme": "bearer", "description": tokens.__doc__})
    api.spec.components.schema("Record", component={"x-jsonld-context": documents.context(settings())}, schema=Record)
    api.register_blueprint(blueprint)
