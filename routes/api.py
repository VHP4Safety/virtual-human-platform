"""The API of the platform's records. Every record is linked data: the API gives it in JSON-LD, with the
fields named as the platform's JSON-LD context names them ("name", "url", "about", ..., and
"dct:conformsTo" for a field of another vocabulary). A link is {"@id": "https://..."}, and a field that
takes several values always gives a list.

    GET    /api/<kind>                       the records of a kind, a page at a time, filtered by their fields
    GET    /api/<kind>/<id>                  a record of a kind that is written through the API
    GET    /api/notes                        what the checks found in the records that does not fit the model
    GET    /api/sources                      where the records come from, and how each source becomes the model
    GET    /api/openapi.json                 this API, described in OpenAPI 3.1; /api/docs shows it

A page of records is a Hydra collection: hydra:member holds the records, hydra:totalItems says how
many there are, and hydra:view links the other pages.

Records of the kinds listed under `writable` in model.yaml are created, replaced and removed with a
write token. rdfsolve checks each record against the model, and the record and its revision are saved
in the database, so its page shows it at once.

    PUT    /api/<kind>/<id>                  create or replace the record with this identifier
    POST   /api/<kind>                       create a record; its identifier is made from its name
    DELETE /api/<kind>/<id>                  remove the record; its address stays gone
    DELETE /api/<kind>/<id>?permanent=true   remove the record and its address
    POST   /api/<kind>/<id>/restore          put a removed record back
    POST   /api/<kind>/<id>/move             move the record to a new address ({"to": "<id>"}); the old one forwards
    POST   /api/images                       upload an image (the form field "image"); gives its address

With ?preview=true, PUT and POST save nothing: they answer with the statements the record would have,
compared with those it has, and with what is wrong with each field.

The body of PUT and POST is a JSON object of the record's fields, named as in the platform's JSON-LD
("name", "description", "url", "about", ..., and "dct:conformsTo" for a field of another vocabulary).
A link is written as {"@id": "https://..."}, or as a web address in a field that takes links, and a
field with several values as a list. A record that does not fit the model is refused with what is wrong
with each field. A request is made with a write token, or by the editor page with an editor's login.
Every answer gives the record's version; a request that sends it back (If-Match) is refused when the
record has changed since, so that one editor's change never silently replaces another's.
"""

import json
import time
from urllib.parse import urlencode

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for
from rdflib import URIRef
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

import database
from admin import changes, tokens, writes
from admin.writes import IDENTIFIER
from database import images, records
from database.tables import Note, Record, Source
from linkeddata import forms, rdf, tables
from linkeddata.document import context
from linkeddata.model import settings
from routes import account, openapi

# Requests are limited per client address, as in ToxTempAssistant's API.
RATE_LIMIT = 300
RATE_WINDOW = 60
# The vocabulary of the pages of a collection.
HYDRA = "http://www.w3.org/ns/hydra/core#"
# How many records a page of a collection gives, unless it asks for another number, and at most.
PAGE = 50
LARGEST_PAGE = 200

blueprint = Blueprint("api", __name__)
_requests = {}


def error(message: str, status: int):
    return jsonify({"error": message}), status


def rate_limited() -> bool:
    address = request.remote_addr or ""
    count, started = _requests.get(address, (0, time.time()))
    if time.time() - started >= RATE_WINDOW:
        count, started = 0, time.time()
    _requests[address] = (count + 1, started)
    return count + 1 > RATE_LIMIT


@blueprint.before_request
def limit():
    if rate_limited():
        return error("Too many requests; try again in a minute.", 429)
    return None


def described(answers: dict, **given):
    """The description of a view for the OpenAPI document (see routes/openapi.py); every route of the API
    refuses too many requests from one address."""
    return openapi.described({**answers, 429: ("error", f"More than {RATE_LIMIT} requests in {RATE_WINDOW} seconds came from this address.")}, **given)


TOKEN = ("error", "No valid write token for this kind of record, and no login of an editor who may write it.")
UNKNOWN = ("error", "The kind of record is not written through the API, or there is no record at this address.")
CHANGED = ("error", "The record changed since the version that If-Match gives.")
VERSION = {"If-Match": ({"type": "string"}, "The version of the record that the change was made on, as the API gave it; the change is refused when the record has changed since.")}
PREVIEW = {"preview": ({"type": "boolean", "default": False}, "Save nothing; answer with what the write would change, and with what is wrong with each field.")}
WRITTEN = (["done", "preview"], "The record was replaced, or, with preview=true, what the write would change.")
NOT_FITTING = ("problems", "The record does not fit the model; what is wrong with each field.")


def paged(offset: int, limit: int) -> str:
    """The address of a page of the collection that the request asks for."""
    given = request.args.copy()
    given["offset"] = str(offset)
    given["limit"] = str(limit)
    return request.base_url + "?" + urlencode(list(given.items(multi=True)))


@blueprint.get("/api/<kind>")
@described(
    {200: ("collection", "A page of the records, with how many records the filters give."),
     400: ("error", "A parameter that is not a field of the kind, or a limit or an offset out of range."),
     404: ("error", "There is no kind of record of this name.")},
    kinds="listed",
    filters=True,
    query={
        "q": ({"type": "string"}, "Records whose name has this text, in small or capital letters."),
        "id": ({"type": "array", "items": {"type": "string", "format": "uri"}}, "Records at these addresses."),
        "source": ({"type": "array", "items": {"type": "string"}}, 'Records of these sources: the name of a source of /api/sources, or "platform" for records written on the platform.'),
        "limit": ({"type": "integer", "minimum": 1, "maximum": LARGEST_PAGE, "default": PAGE}, "How many records a page gives."),
        "offset": ({"type": "integer", "minimum": 0, "default": 0}, "How many records come before this page."),
    },
)
def listing(kind: str):
    """The records of a kind, a page at a time.

    Each field of the kind is a query parameter: a record is given when its field has one of the values
    given for it (repeat a parameter for several values), and when it has every field given. A link is
    given by its address. The records come in the order of their names."""
    kinds = settings()["kinds"]
    if kind not in kinds:
        return error(f"There is no kind of record {kind!r}; the kinds are {', '.join(kinds)}.", 404)
    fields = {}
    for field in forms.form(kinds[kind]):
        fields[field["name"]] = field["iri"]
    conditions = [Record.type == kinds[kind], Record.removed_at.is_(None)]
    for name in request.args:
        values = request.args.getlist(name)
        if name in fields:
            conditions.append(tables.having(kinds[kind], fields[name], values))
        elif name == "q":
            conditions.append(func.lower(Record.name).contains(values[0].lower(), autoescape=True))
        elif name == "id":
            conditions.append(Record.iri.in_(values))
        elif name == "source":
            conditions.append(Record.source.in_(values))
        elif name not in ("limit", "offset"):
            return error(f"{name!r} is not a field of {kind}; its fields are {', '.join(fields)}.", 400)
    limit = request.args.get("limit", str(PAGE))
    offset = request.args.get("offset", "0")
    if not limit.isdigit() or not 1 <= int(limit) <= LARGEST_PAGE or not offset.isdigit():
        return error(f"limit is a number from 1 to {LARGEST_PAGE}, and offset a number from 0.", 400)
    limit, offset = int(limit), int(offset)
    with database.session() as db:
        total = db.scalar(select(func.count()).select_from(Record).where(*conditions))
        statement = select(Record.iri).where(*conditions).order_by(func.lower(Record.name), Record.iri)
        page = list(db.scalars(statement.limit(limit).offset(offset)))
    found = tables.graph(page)
    members = []
    for iri in page:
        member = forms.shaped(rdf.document(found, iri), kinds[kind])
        member.pop("@context", None)
        members.append(member)
    last = max(total - 1, 0) // limit * limit
    view = {"@id": paged(offset, limit), "@type": "hydra:PartialCollectionView", "hydra:first": paged(0, limit), "hydra:last": paged(last, limit)}
    if offset > 0:
        view["hydra:previous"] = paged(max(offset - limit, 0), limit)
    if offset + limit < total:
        view["hydra:next"] = paged(offset + limit, limit)
    filtered = request.args.copy()
    filtered.pop("limit", None)
    filtered.pop("offset", None)
    collection = {
        "@context": {**context(settings()), "hydra": HYDRA},
        "@id": request.base_url + ("?" + urlencode(list(filtered.items(multi=True))) if filtered else ""),
        "@type": "hydra:Collection",
        "hydra:totalItems": total,
        "hydra:member": members,
        "hydra:view": view,
    }
    return Response(json.dumps(collection, indent=2), mimetype="application/ld+json")


@blueprint.get("/api/<kind>/<identifier>")
@described(
    {200: ("record", "The record."),
     301: ([], "The record moved; Location gives its new address in the API."),
     404: ("error", "There is no record of this kind at this address."),
     410: ("error", "The record was removed.")},
    kinds="writable",
)
def get(kind: str, identifier: str):
    """A record, as the API takes it back with PUT."""
    writable = settings().get("writable", {})
    record = records.get(records.address(f"{kind}/{identifier}"))
    if kind not in writable or record is None or record.type != writable[kind]:
        return error("There is no record of this kind at this address.", 404)
    if record.moved_to:
        return redirect(url_for("api.get", kind=kind, identifier=record.moved_to.rsplit("/", 1)[-1]), code=301)
    if record.removed_at:
        return error("This record was removed.", 410)
    document = forms.shaped(rdf.document(tables.graph([record.iri]), record.iri), record.type)
    return Response(json.dumps(document, indent=2), mimetype="application/ld+json")


@blueprint.get("/api/notes")
@described(
    {200: ("notes", "The notes, a page at a time, by source, field and record."),
     400: ("error", "A limit or an offset out of range.")},
    query={
        "source": ({"type": "array", "items": {"type": "string"}}, "Notes of these sources."),
        "iri": ({"type": "array", "items": {"type": "string", "format": "uri"}}, "Notes of the records at these addresses."),
        "field": ({"type": "array", "items": {"type": "string", "format": "uri"}}, "Notes of these fields, by the address of their property."),
        "limit": ({"type": "integer", "minimum": 1, "maximum": LARGEST_PAGE, "default": PAGE}, "How many notes a page gives."),
        "offset": ({"type": "integer", "minimum": 0, "default": 0}, "How many notes come before this page."),
    },
)
def notes():
    """What the checks found that does not fit the model, in the records of each source.

    The imports note each value that does not fit, and the records written on the platform are checked
    again every night, as the model may have changed since they were written."""
    conditions = []
    for name, column in (("source", Note.source), ("iri", Note.iri), ("field", Note.field)):
        if name in request.args:
            conditions.append(column.in_(request.args.getlist(name)))
    limit = request.args.get("limit", str(PAGE))
    offset = request.args.get("offset", "0")
    if not limit.isdigit() or not 1 <= int(limit) <= LARGEST_PAGE or not offset.isdigit():
        return error(f"limit is a number from 1 to {LARGEST_PAGE}, and offset a number from 0.", 400)
    with database.session() as db:
        total = db.scalar(select(func.count()).select_from(Note).where(*conditions))
        statement = select(Note).where(*conditions).order_by(Note.source, Note.field, Note.iri, Note.id)
        found = list(db.scalars(statement.limit(int(limit)).offset(int(offset))))
    rows = []
    for note in found:
        row = {}
        for column in Note.__table__.columns:
            row[column.name] = getattr(note, column.name)
        rows.append(row)
    return jsonify({"total": total, "notes": rows})


@blueprint.get("/api/sources")
@described({200: ("sources", "Every source, as its last import fetched it.")})
def sources():
    """Where the records come from: each source, when its last import fetched it, and the rdfsolve queries
    that convert it into the model."""
    with database.session() as db:
        found = list(db.scalars(select(Source).order_by(Source.name)))
    rows = []
    for source in found:
        row = {}
        for column in Source.__table__.columns:
            row[column.name] = getattr(source, column.name)
        rows.append(row)
    return jsonify({"sources": rows})


@blueprint.get("/api/openapi.json")
@described({200: ("openapi", "The document, as the code and the model of the release give it now.")})
def openapi_document():
    """This API, described in OpenAPI 3.1."""
    return jsonify(openapi.document())


@blueprint.get("/api/docs")
@described({200: ("page", "The page.")})
def documentation():
    """This API's documentation, a page made from its OpenAPI document."""
    return render_template("api/docs.html", page_title="API — VHP4Safety")


def authorized(kind: str):
    """Who makes the request (a token, or an editor of the editor page) when they may write records of *kind*."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return tokens.check(header.removeprefix("Bearer ").strip(), kind)
    return account.editor_of_request(kind)


def done(address: str, revision, status: int, warnings: dict | None = None):
    record = records.get(address)
    return jsonify({
        "@id": address,
        "change": url_for("changes.change", number=revision.id),
        "version": record.updated_at if record is not None else None,
        "warnings": warnings or {},
    }), status


def changed_since_read(address: str):
    """A refusal when the request names the version it read (If-Match) and the record has changed since."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if not expected or record is None or record.updated_at == expected:
        return None
    return error("Someone else changed this record since you opened it. Open it again to see their change, then make yours.", 412)


def store(kind: str, identifier: str, replace: bool = True):
    """The record of the request's body is checked and saved; the response says how it went."""
    config = settings()
    writable = config.get("writable", {})
    if kind not in writable:
        return error(f"Records of kind {kind!r} are not written through the API.", 404)
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error("The body is a JSON object of the record's fields.", 400)
    address = records.address(f"{kind}/{identifier}")
    if request.args.get("preview") == "true":
        return preview(address, writable[kind], body)
    conflict = changed_since_read(address)
    if conflict:
        return conflict
    try:
        found, problems, warnings = rdf.checked(writes.document(writable[kind], address, body))
    except ValueError as problem:
        return error(str(problem), 422)
    if problems:
        refused = rdf.NotFitting(problems)
        return jsonify({"error": str(refused), "fields": problems}), 422
    document = rdf.document(found, address)
    revision = writes.save(document, writable[kind], token.name, token.orcid, replace)
    writes.name_things(writes.titled(writable[kind], body))
    return done(address, revision, 201 if revision.action == "Added" else 200, writes.together(warnings, rdf.duplicates(document, writable[kind])))


def preview(address: str, kind: str, body: dict):
    """The statements a write would publish, compared with the record as it is, and what is wrong with each field."""
    try:
        new = writes.document(kind, address, body)
        found, problems, warnings = rdf.checked(new)
    except ValueError as problem:
        return error(str(problem), 422)
    before = changes.statements(rdf.document_of(address))
    edges = changes.edges(before, found, URIRef(address))
    return jsonify({**edges, "fields": problems, "warnings": writes.together(warnings, rdf.duplicates(new, kind))})


@blueprint.put("/api/<kind>/<identifier>")
@described(
    {200: WRITTEN, 201: ("done", "The record was added."),
     400: ("error", "The identifier or the body is not as the API takes it."), 401: TOKEN, 404: UNKNOWN,
     409: ("error", "The record moved to another address, or the address belonged to a removed record."),
     412: CHANGED, 422: NOT_FITTING},
    kinds="writable", body="record", query=PREVIEW, headers=VERSION, token=True,
)
def put(kind: str, identifier: str):
    """Add or replace the record with this identifier.

    The record is checked against the model; one that does not fit is refused, with what is wrong with each
    field. Fields set by the platform are set as the model gives them."""
    if not IDENTIFIER.fullmatch(identifier):
        return error("An identifier has lowercase letters, digits and hyphens.", 400)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is not None and record.moved_to:
        return error(f"This record moved to {record.moved_to}; write it there.", 409)
    if record is not None and record.removed_at:
        return error("This address belonged to a removed record and is not given again.", 409)
    return store(kind, identifier)


@blueprint.post("/api/<kind>")
@described(
    {200: (["preview"], "With preview=true, what the write would change."), 201: ("done", "The record was added."),
     400: ("error", "The body has no name, or is not as the API takes it."), 401: TOKEN, 404: UNKNOWN, 422: NOT_FITTING},
    kinds="writable", body="record", query=PREVIEW, token=True,
)
def post(kind: str):
    """Add a record; its identifier is made from its name.

    When another record has that identifier, a number is added to it."""
    body = request.get_json(silent=True)
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or not name.strip():
        return error("A new record needs a name, from which its identifier is made.", 400)
    identifier = writes.slug(name)
    number = 2
    while True:
        if records.get(records.address(f"{kind}/{identifier}")) is None:
            try:
                return store(kind, identifier, replace=False)
            except IntegrityError:
                pass
        identifier = f"{writes.slug(name)}-{number}"
        number += 1


@blueprint.delete("/api/<kind>/<identifier>")
@described(
    {200: ("done", "The record was removed."), 401: TOKEN, 404: UNKNOWN, 412: CHANGED},
    kinds="writable", headers=VERSION, token=True,
    query={"permanent": ({"type": "boolean", "default": False}, "Remove the record's address too, so that it can be given to another record.")},
)
def delete(kind: str, identifier: str):
    """Remove a record.

    Its address answers 410 Gone from then on, and is not given to another record, unless the removal is
    permanent. A removed record can be put back with restore."""
    if kind not in settings().get("writable", {}):
        return error(f"Records of kind {kind!r} are not written through the API.", 404)
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    record = records.get(records.address(f"{kind}/{identifier}"))
    permanent = request.args.get("permanent") == "true"
    if record is None or (record.removed_at and not permanent):
        return error("There is no record at this address.", 404)
    conflict = changed_since_read(record.iri)
    if conflict:
        return conflict
    if permanent:
        revision = writes.remove(record.iri, token.name, token.orcid)
    else:
        revision = writes.retire(record.iri, token.name, token.orcid)
    return done(record.iri, revision, 200)


@blueprint.post("/api/<kind>/<identifier>/move")
@described(
    {200: ("done", "The record moved."), 400: ("error", "The new identifier is not as the API takes it."), 401: TOKEN, 404: UNKNOWN,
     409: ("error", "The new address is taken by another record, or was one."), 412: CHANGED},
    kinds="writable", body="move", headers=VERSION, token=True,
)
def move(kind: str, identifier: str):
    """Move a record to a new identifier.

    Its old address forwards to the new one."""
    if kind not in settings().get("writable", {}):
        return error(f"Records of kind {kind!r} are not written through the API.", 404)
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is None or record.removed_at:
        return error("There is no record at this address.", 404)
    body = request.get_json(silent=True)
    to = body.get("to") if isinstance(body, dict) else None
    if not isinstance(to, str) or not IDENTIFIER.fullmatch(to):
        return error('The new address is given as {"to": "<identifier>"}, with lowercase letters, digits and hyphens.', 400)
    target = records.get(records.address(f"{kind}/{to}"))
    if target is not None and target.moved_to != record.iri:
        return error("This address is taken by another record, or was one.", 409)
    conflict = changed_since_read(record.iri)
    if conflict:
        return conflict
    address = records.address(f"{kind}/{to}")
    return done(address, writes.move(record.iri, address, token.name, token.orcid), 200)


@blueprint.post("/api/<kind>/<identifier>/restore")
@described(
    {200: ("done", "The record was put back."), 401: TOKEN, 404: ("error", "There is no removed record at this address.")},
    kinds="writable", token=True,
)
def restore(kind: str, identifier: str):
    """Put back a removed record."""
    if kind not in settings().get("writable", {}):
        return error(f"Records of kind {kind!r} are not written through the API.", 404)
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is None or not record.removed_at:
        return error("There is no removed record at this address.", 404)
    return done(record.iri, writes.restore(record.iri, token.name, token.orcid), 200)


@blueprint.post("/api/images")
@described(
    {201: ("image", "The image was saved."), 400: ("error", 'No form field "image".'), 401: TOKEN,
     413: ("error", "The image is larger than 5 MB."), 422: ("error", "The file is not an image that the platform takes.")},
    body="image", token=True,
)
def upload_image():
    """Upload an image, such as a tool's logo.

    The image is checked and saved again as WebP; its address is what a record gives in its image field."""
    uploader = None
    for kind in settings().get("writable", {}):
        uploader = uploader or authorized(kind)
    if uploader is None:
        return error("A valid write token, or an editor's login, is needed.", 401)
    request.max_content_length = images.MAX_BYTES
    try:
        upload = request.files.get("image")
    except RequestEntityTooLarge:
        return error("The image is larger than 5 MB.", 413)
    if upload is None:
        return error('The image is sent as the form field "image".', 400)
    try:
        address = images.store(upload.stream, uploader.name, uploader.orcid)
    except ValueError as problem:
        return error(str(problem), 422)
    return jsonify({"@id": address}), 201
