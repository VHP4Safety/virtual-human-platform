"""The write API. Records of the kinds listed under `writable` in model.yaml are created, replaced and
removed with a write token. rdfsolve checks each record against the model, the record is kept as a
file in the records repository, and the build runs again in the background.

    PUT    /api/<kind>/<id>                  create or replace the record with this identifier
    POST   /api/<kind>                       create a record; its identifier is made from its name
    DELETE /api/<kind>/<id>                  remove the record; its address stays gone
    DELETE /api/<kind>/<id>?permanent=true   remove the record and its address

The body of PUT and POST is a JSON object of the record's fields, named as in the model ("name",
"description", "about", ...). A link is written as {"@id": "https://..."}.
"""

import os
import re
import time
from pathlib import Path

from flask import Blueprint, jsonify, request
from rdflib import URIRef

from linkeddata import records, tokens
from linkeddata.build import request_build
from linkeddata.document import compact
from linkeddata.model import contract_client, settings

BUILD_DIR = Path(os.environ.get("PLATFORM_BUILD", "build"))
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")
# Requests are limited per client address, as in ToxTempAssistant's API.
RATE_LIMIT = 300
RATE_WINDOW = 60

blueprint = Blueprint("api", __name__)
_client = None
_requests = {}


def model():
    global _client
    if _client is None:
        _client = contract_client()
    return _client


def error(message: str, status: int):
    return jsonify({"error": message}), status


def rate_limited() -> bool:
    address = request.remote_addr or ""
    count, started = _requests.get(address, (0, time.time()))
    if time.time() - started >= RATE_WINDOW:
        count, started = 0, time.time()
    _requests[address] = (count + 1, started)
    return count + 1 > RATE_LIMIT


def terms(value):
    """A JSON value as rdfsolve takes it: {"@id": ...} is a link."""
    if isinstance(value, list):
        items = []
        for item in value:
            items.append(terms(item))
        return items
    if isinstance(value, dict) and list(value) == ["@id"]:
        return URIRef(value["@id"])
    return value


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


def store(kind: str, identifier: str):
    """The record of the request's body is checked, saved and built; the response says how it went."""
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
    address = config["base"] + kind + "/" + identifier
    fields = {}
    for name, value in body.items():
        if not name.startswith("@"):
            fields[name] = terms(value)
    try:
        record = model().create(writable[kind], uri=address, **fields)
    except ValueError as problem:
        return error(str(problem), 422)
    created = not records.record_path(kind, identifier).exists()
    document = compact(record.to_graph().serialize(format="nt"), config)
    records.save(kind, identifier, document, token["name"], token["orcid"])
    request_build(BUILD_DIR)
    return jsonify({"@id": address}), 201 if created else 200


@blueprint.put("/api/<kind>/<identifier>")
def put(kind: str, identifier: str):
    if not IDENTIFIER.fullmatch(identifier):
        return error("An identifier has lowercase letters, digits and hyphens.", 400)
    if records.gone_path(kind, identifier).exists():
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
    while records.taken(kind, identifier):
        identifier = f"{slug(name)}-{number}"
        number += 1
    return store(kind, identifier)


@blueprint.delete("/api/<kind>/<identifier>")
def delete(kind: str, identifier: str):
    if kind not in settings().get("writable", {}):
        return error(f"Records of kind {kind!r} are not written through the API.", 404)
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    permanent = request.args.get("permanent") == "true"
    if not records.record_path(kind, identifier).exists() and not (permanent and records.taken(kind, identifier)):
        return error("There is no record at this address.", 404)
    if permanent:
        records.remove(kind, identifier, token["name"], token["orcid"])
    else:
        records.retire(kind, identifier, token["name"], token["orcid"])
    request_build(BUILD_DIR)
    return "", 204
