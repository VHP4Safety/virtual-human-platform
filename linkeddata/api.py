"""The write API. Records of the kinds listed under `writable` in model.yaml are created, replaced and
removed with a write token. rdfsolve checks each record against the model, and the record and its
revision are saved in the database, so its page shows it at once.

    PUT    /api/<kind>/<id>                  create or replace the record with this identifier
    POST   /api/<kind>                       create a record; its identifier is made from its name
    DELETE /api/<kind>/<id>                  remove the record; its address stays gone
    DELETE /api/<kind>/<id>?permanent=true   remove the record and its address
    POST   /api/images                       upload an image (the form field "image"); gives its address

The body of PUT and POST is a JSON object of the record's fields, named as in the model ("name",
"description", "url", "about", ...). A link is written as {"@id": "https://..."}, and a field
with several values as a list. A record that does not fit the model is refused with what is wrong
with each field.
"""

import re
import time

from flask import Blueprint, jsonify, request, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

from linkeddata import forms, images, rdf, records, tokens
from linkeddata.database import PLATFORM
from linkeddata.model import settings

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


def values(kind: str, body: dict) -> dict[str, list]:
    """The fields of a request's body, named as in the database, each with a list of values. The
    values that the application profile fixes are set by the platform."""
    found = {}
    for name, value in body.items():
        if name.startswith("@"):
            continue
        items = []
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict) and list(item) == ["@id"]:
                items.append(item["@id"])
            else:
                items.append(item)
        found[rdf.field_of(kind, name)] = items
    for field in forms.form(kind):
        if field["fixed"]:
            found[field["name"]] = field["fixed"]
    return found


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "record"


@blueprint.before_request
def limit():
    if rate_limited():
        return error("Too many requests; try again in a minute.", 429)
    return None


def authorized(kind: str):
    """The token of the request when it may write records of *kind*."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return tokens.check(header.removeprefix("Bearer ").strip(), kind)


def done(address: str, revision, status: int):
    return jsonify({"@id": address, "change": url_for("changes.change", number=revision.id)}), status


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
    try:
        row = rdf.row(address, writable[kind], PLATFORM, values(writable[kind], body))
        document = rdf.document(rdf.check(row))
    except rdf.NotFitting as problem:
        return jsonify({"error": str(problem), "fields": problem.problems}), 422
    except ValueError as problem:
        return error(str(problem), 422)
    revision = records.save(row, document, token.name, token.orcid, replace)
    return done(address, revision, 201 if revision.action == "Added" else 200)


@blueprint.put("/api/<kind>/<identifier>")
def put(kind: str, identifier: str):
    if not IDENTIFIER.fullmatch(identifier):
        return error("An identifier has lowercase letters, digits and hyphens.", 400)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is not None and record.removed_at:
        return error("This address belonged to a removed record and is not given again.", 409)
    return store(kind, identifier)


@blueprint.post("/api/<kind>")
def post(kind: str):
    body = request.get_json(silent=True)
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or not name.strip():
        return error("A new record needs a name, from which its identifier is made.", 400)
    identifier = slug(name)
    number = 2
    while True:
        if records.get(records.address(f"{kind}/{identifier}")) is None:
            try:
                return store(kind, identifier, replace=False)
            except IntegrityError:
                pass
        identifier = f"{slug(name)}-{number}"
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
    if permanent:
        revision = records.remove(record.iri, token.name, token.orcid)
    else:
        revision = records.retire(record.iri, token.name, token.orcid)
    return done(record.iri, revision, 200)


@blueprint.post("/api/images")
def upload_image():
    uploader = None
    for kind in settings().get("writable", {}):
        uploader = uploader or authorized(kind)
    if uploader is None:
        return error("A valid write token is needed.", 401)
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
