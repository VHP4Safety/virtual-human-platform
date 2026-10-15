"""The write API. Records of the kinds listed under `writable` in model.yaml are created, replaced and
removed with a write token. rdfsolve checks each record against the model, and the record and its
revision are saved in the database, so its page shows it at once.

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

import re
import time

from flask import Blueprint, jsonify, request, url_for
from rdflib import URIRef
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

from admin import changes, tokens, writes
from database import images, records
from linkeddata import rdf
from linkeddata.model import settings
from routes import account

IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")
# Requests are limited per client address, as in ToxTempAssistant's API.
RATE_LIMIT = 300
RATE_WINDOW = 60

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
def put(kind: str, identifier: str):
    if not IDENTIFIER.fullmatch(identifier):
        return error("An identifier has lowercase letters, digits and hyphens.", 400)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is not None and record.moved_to:
        return error(f"This record moved to {record.moved_to}; write it there.", 409)
    if record is not None and record.removed_at:
        return error("This address belonged to a removed record and is not given again.", 409)
    return store(kind, identifier)


@blueprint.post("/api/<kind>")
def post(kind: str):
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
def delete(kind: str, identifier: str):
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
def move(kind: str, identifier: str):
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
def restore(kind: str, identifier: str):
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
def upload_image():
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
