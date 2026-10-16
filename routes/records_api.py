"""The platform's API, with flask-smorest, documented at /api/docs/.

Each kind of record has a resource: GET /api/<kind> lists its records, found by their name (search) or by
the value of any of their fields (/api/tools?processFlowStep=<address>), a page at a time; POST /api/<kind>
adds one, at an address made from its name. Each record is at the API's address of its page, with the
parts it holds: GET, PUT and DELETE /api/tools/aopsuite read it in JSON-LD, Turtle or N-Triples, as Accept
asks, add or replace it, and remove it; /api/casestudies/kidney/Q1 is a question of a case study, read
with its steps and written with its case study.

A record is written in JSON-LD, with its fields named as the platform's JSON-LD context names them ("name",
"url", "processFlowStep", ..., and "dct:conformsTo" for a field of another vocabulary), or with a context of
its own, or in Turtle; a link is {"@id": "https://..."}. The model's SHACL shapes (/api/shapes.ttl) say what
each field takes: a record that does not fit is refused, with what is wrong with each field. Writing needs a
write token, or an editor's login on the editor page. A record's ETag is its version: a write that sends it
in If-Match is refused when the record has changed since. With preview=true, a write saves nothing and
answers with the statements about the record before and after it, and what is wrong with each field. The
rows of the platform's tables are at /api/tables/<table>.
"""

import json

from flask import Response, jsonify, redirect, request, url_for
from flask_smorest import Api, Blueprint, abort
from marshmallow import INCLUDE, Schema, fields
from rdflib import Graph, URIRef
from werkzeug.exceptions import RequestEntityTooLarge

from admin import changes, tokens, writes
from database import images, records
from linkeddata import checks, documents, fields as model_fields, storage
from linkeddata.model import RELEASE, settings, shapes
from routes import account, limiter, tables_api
from routes.record_pages import SERIALIZATIONS, data

blueprint = Blueprint("api", __name__, url_prefix="/api", description="The records of each kind, each at the address of its page.")
limiter.limit("300 per minute")(blueprint)
TOKEN = [{"token": []}]


class Record(Schema.from_dict({"@type": fields.Raw(metadata={"description": "The record's class; a new record needs it."})})):
    """A record in JSON-LD. The model's SHACL shapes (/api/shapes.ttl) say what each field of its class takes."""

    class Meta:
        unknown = INCLUDE


class Writing(Schema):
    preview = fields.Boolean(load_default=False, metadata={"description": "Save nothing; answer with what the write would change."})


class Removal(Schema):
    permanent = fields.Boolean(load_default=False, metadata={"description": "Remove the address too, so that another record can have it."})


class Restore(Schema):
    record = fields.String(required=True, metadata={"description": "The address of the record's page, such as tools/aopsuite."})


class Move(Restore):
    to = fields.String(required=True, metadata={"description": "The record's new address, such as tools/aop-suite."})


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
        headers["Location"] = url_for("api.read", path=address.removeprefix(settings()["base"]))
    return {"@id": address, "change": url_for("changes.change", number=revision.id), "version": version, "warnings": warnings or {}}, status, headers


def unchanged(address: str) -> None:
    """A write that names the version it read (If-Match) is refused when the record has changed since."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if expected and record is not None and record.updated_at != expected:
        abort(412, message="Someone else changed this record since you opened it. Open it again to see their change, then make yours.")


def whole(record) -> None:
    """A part of a record, such as a question of a case study, is written with the record that holds it."""
    if record is not None and record.part_of:
        abort(409, message=f"This address is a part of the record at {record.part_of}, and is written with it.")


def store(address: str, body: dict, preview: bool = False):
    """The record of a request's body is checked and saved at *address*."""
    kind = kind_of(address, body)
    if kind is None:
        abort(400, message="The record's @type is not one of the platform's classes.")
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
    if preview:
        before = changes.statements(documents.document_of(address))
        return jsonify({**changes.edges(before, found, URIRef(address)), "fields": problems, "warnings": warnings, "document": documents.document(storage.with_names(found), address)})
    unchanged(address)
    if problems:
        abort(422, message=str(checks.NotFitting(problems)), errors=problems)
    created = writes.separate(found)
    # A record added in another record's form, such as a person, is written by those who may write its kind.
    for _, of_kind, _ in created:
        writer(kind_of(None, {"@type": of_kind}))
    for iri, of_kind, own in created:
        writes.save(documents.document(own, iri), of_kind, who.name, who.orcid)
    revision = writes.save(documents.document(found, address), kind, who.name, who.orcid)
    return done(address, revision, 201 if revision.action == "Added" else 200, warnings)


RECORD_FORMATS = {"200": {"description": "The record, in the format that Accept asks for.", "content": {
    "application/ld+json": {"schema": {"$ref": "#/components/schemas/Record"}},
    "text/turtle": {"schema": {"type": "string"}},
    "application/n-triples": {"schema": {"type": "string"}},
}}}


def found_record(path: str):
    """The record at the address of a page, with the address it moved to and whether it was removed."""
    record = records.get(records.address(path))
    if record is None:
        abort(404, message="There is no record at this address.")
    return record


class Search(Schema):
    text = fields.String(load_default="", metadata={"description": "Text that the name or the address has."})
    of_class = fields.List(fields.Url(), data_key="class", load_default=list, metadata={"description": "The classes of the records (or of the terms), with their subclasses."})
    within = fields.String(load_default="", metadata={"description": "The start of the addresses, such as the namespace of a vocabulary."})
    limit = fields.Integer(load_default=20, validate=lambda number: 1 <= number <= 200)


@blueprint.get("/search")
@blueprint.arguments(Search, location="query")
def search(given):
    """Records, their parts and the terms of vocabularies, found by name or address: their address, class
    and name, in JSON-LD."""
    found = []
    for record in records.search(given["text"], given["of_class"] or list(settings()["kinds"].values()), given["within"], limit=given["limit"]):
        found.append({"@id": record.iri, "@type": documents.term(record.type), "name": record.name or record.iri})
    return jsonify({"@context": documents.context(settings()), "@graph": found})


def listing(kind: str, given: dict) -> Response:
    """The records of a kind that have the values asked for, and whose name has the text searched for, a
    page at a time, in JSON-LD or Turtle; X-Total-Count gives how many there are."""
    listed = [record.iri for record in records.search(given.get("search", ""), [settings()["kinds"][kind]], parts=False, limit=None)]
    found = storage.graph(listed)
    for name, value in given.items():
        if name not in ("search", "page", "page_size"):
            kept = []
            for iri in listed:
                if value in documents.stored_values(found, iri, name):
                    kept.append(iri)
            listed = kept
    first = (given["page"] - 1) * given["page_size"]
    page = listed[first:first + given["page_size"]]
    media = request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS]) or "application/ld+json"
    if media == "application/ld+json":
        documented = []
        for iri in page:
            document = documents.document(found, iri)
            document.pop("@context", None)
            documented.append(document)
        answer = jsonify({"@context": documents.context(settings()), "@graph": documented})
    else:
        shown = Graph()
        for iri in page:
            shown += storage.described(found, iri)
        answer = data(shown, media)
    answer.headers["X-Total-Count"] = str(len(listed))
    return answer


def resources() -> None:
    """A resource for each kind of record: its records listed and found by the values of their fields, and
    a new record added."""
    for kind, of_class in settings()["kinds"].items():
        filters = {
            "search": fields.String(metadata={"description": "Text that the record's name has."}),
            "page": fields.Integer(load_default=1, validate=lambda number: number >= 1),
            "page_size": fields.Integer(load_default=50, validate=lambda number: 1 <= number <= 200),
        }
        for field in model_fields.of(of_class):
            filters[field["name"]] = fields.String(metadata={"description": f"{field['label']}: a value, or the address of a link, that the record has."})
        query = Schema.from_dict(filters, name=f"{kind.capitalize()}Query")

        def listed(given, kind=kind):
            return listing(kind, given)

        def added(body, kind=kind):
            # A term of a vocabulary is at its own address; another record is given one from its name.
            address = body.get("@id") or writes.free(records.address(f"{kind}/{writes.slug(str(body.get('name') or kind))}"), set())
            if records.get(address) is not None:
                abort(409, message="There is a record at this address already.")
            body = {"@type": documents.term(settings()["kinds"][kind]), **body}
            return store(address, body)

        listed.__doc__ = f"The {kind}, found by their name or by the values of their fields."
        added.__doc__ = f"Add a record to the {kind}, at an address made from its name."
        blueprint.route(f"/{kind}", endpoint=f"list_{kind}", methods=["GET"])(
            blueprint.doc(responses={"200": {"description": f"The {kind}, in JSON-LD (@graph) or Turtle."}})(blueprint.arguments(query, location="query")(listed)))
        blueprint.route(f"/{kind}", endpoint=f"add_{kind}", methods=["POST"])(
            blueprint.doc(security=TOKEN)(blueprint.response(201, Done)(blueprint.arguments(Record)(added))))


@blueprint.get("/<path:path>")
@blueprint.doc(responses=RECORD_FORMATS)
def read(path):
    """A record, or a part of one, at the address of its page, in JSON-LD, Turtle or N-Triples, as Accept asks."""
    record = found_record(path)
    if record.moved_to:
        return redirect(url_for("api.read", path=record.moved_to.removeprefix(settings()["base"])), code=301)
    if record.removed_at:
        abort(410, message="This record was removed.")
    media = request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS]) or "application/ld+json"
    answer = data(storage.with_names(storage.graph([record.iri])), media, record.iri)
    answer.headers["ETag"] = f'"{record.updated_at}"'
    return answer


@blueprint.put("/<path:path>")
@blueprint.arguments(Writing, location="query")
@blueprint.arguments(Record)
@blueprint.response(200, Done, description="The record was replaced; with preview=true, what the write would change.")
@blueprint.alt_response(201, schema=Done, description="The record was added.")
@blueprint.doc(security=TOKEN, requestBody={"content": {"text/turtle": {"schema": {"type": "string"}}}})
def replace(given, body, path):
    """Add or replace the record at the address of its page, given in JSON-LD or in Turtle."""
    address = records.address(path)
    record = records.get(address)
    whole(record)
    if record is not None and (record.moved_to or record.removed_at):
        abort(409, message="This address belongs to a record that moved or was removed, and is not written again.")
    if request.mimetype == "text/turtle":
        body = documents.document(Graph().parse(data=request.get_data(as_text=True), format="turtle"), address)
    return store(address, body, given["preview"])


@blueprint.delete("/<path:path>")
@blueprint.arguments(Removal, location="query")
@blueprint.response(200, Done, description="The record was removed.")
@blueprint.doc(security=TOKEN)
def remove(given, path):
    """Remove a record, with its parts.

    Its address answers 410 Gone from then on, and is not given to another record, unless the removal is
    permanent. A removed record can be put back with restore."""
    record = found_record(path)
    if record.removed_at and not given["permanent"]:
        abort(404, message="There is no record at this address.")
    whole(record)
    who = writer(kind_of(record.iri, {}))
    unchanged(record.iri)
    if given["permanent"]:
        return done(record.iri, writes.remove(record.iri, who.name, who.orcid), 200)
    return done(record.iri, writes.retire(record.iri, who.name, who.orcid), 200)


@blueprint.post("/move")
@blueprint.arguments(Move)
@blueprint.response(200, Done, description="The record moved; its old address forwards to the new one.")
@blueprint.doc(security=TOKEN)
def move(body):
    """Move a record, with its parts, to a new address; the old one forwards to it."""
    record = found_record(body["record"])
    if record.removed_at:
        abort(404, message="There is no record at this address.")
    whole(record)
    who = writer(kind_of(record.iri, {}))
    target = records.get(records.address(body["to"]))
    if target is not None and target.moved_to != record.iri:
        abort(409, message="This address is taken by another record, or was one.")
    unchanged(record.iri)
    return done(records.address(body["to"]), writes.move(record.iri, records.address(body["to"]), who.name, who.orcid), 200)


@blueprint.post("/restore")
@blueprint.arguments(Restore)
@blueprint.response(200, Done, description="The record was put back.")
@blueprint.doc(security=TOKEN)
def restore(body):
    """Put back a removed record, with its parts."""
    record = found_record(body["record"])
    if not record.removed_at:
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
    """The API, with the rows of the tables, and its OpenAPI document, at /api/docs/."""
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
    resources()
    api.register_blueprint(blueprint)
    tables_api.register(api)
