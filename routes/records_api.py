"""The platform's records as linked data. The API gives every record in JSON-LD, with its fields named as
the platform's JSON-LD context names them ("name", "url", "about", ..., and "dct:conformsTo" for a field
of another vocabulary). A link is {"@id": "https://..."}, and a field that takes several values always
gives a list. Each record's schema carries its JSON-LD type and context (x-jsonld-type, x-jsonld-context),
and the model's SHACL shapes (/api/shapes.ttl) say what each field takes.

The records of a kind are listed a page at a time as a Hydra collection, filtered by any of their
fields. The address of each record gives its page, or its data in JSON-LD, Turtle or N-Triples, as the
request's Accept header asks.

Records of the kinds listed under `writable` in model.yaml are added, replaced, moved and removed with
a write token, or by the editor page with an editor's login. Each record is checked against the model,
and one that does not fit is refused with what is wrong with each field. Every answer gives the record's
version: a write that sends it back in If-Match is refused when the record has changed since. With
?preview=true, a write saves nothing and answers with what it would change.
"""

import json
import re
import time
from functools import cache
from typing import Any, Literal
from urllib.parse import urlencode

from flask import Blueprint, Response as Answer, jsonify, redirect, request, url_for
from pydantic import BaseModel, ConfigDict, Field, RootModel, create_model
from rdflib import URIRef
from spectree import Response, SecurityScheme, SecuritySchemeData, SpecTree
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import RequestEntityTooLarge

import database
from admin import changes, tokens, writes
from admin.writes import IDENTIFIER
from database import images, records
from database.tables import Record
from linkeddata import checks, documents, forms, storage
from linkeddata.model import RELEASE, settings, shapes
from routes import account

# Requests are limited per client address, as in ToxTempAssistant's API.
RATE_LIMIT = 300
RATE_WINDOW = 60
HYDRA = "http://www.w3.org/ns/hydra/core#"
# How many records a page of a collection gives, unless it asks for another number, and at most.
PAGE = 50
LARGEST_PAGE = 200
# The formats of a record's data at its address, by the media type that asks for them.
FORMATS = ("application/ld+json", "text/turtle", "application/n-triples")

blueprint = Blueprint("api", __name__)
_requests = {}


class Error(BaseModel):
    """Why a request is refused."""

    error: str


class Problems(Error):
    """A record that does not fit the model, with what is wrong with each field."""

    fields: dict[str, list[str]] = {}


class Done(BaseModel):
    """A change that is saved."""

    id: str = Field(alias="@id", description="The record's address.")
    change: str = Field(description="The path of the change's page; with .json, the change as JSON.")
    version: str | None = Field(description="The record's version, to send back in If-Match.")
    warnings: dict[str, list[str]] = Field(description="The recommended fields that are empty, with why.")


class Edge(BaseModel):
    label: str = Field(description="The field's name in the editor's form.")
    property: str
    value: str
    link: bool
    name: str | None = Field(description="The name of the record that a link goes to.")
    entry: str
    status: Literal["added", "removed", "kept"]
    order: int


class Preview(BaseModel):
    """What a write would change, saving nothing: the statements about the record before and after it, as
    edges from the record to each value, and what is wrong with each field."""

    record: str
    record_name: str
    type: str
    edges: list[Edge]
    fields: dict[str, list[str]]
    warnings: dict[str, list[str]]


class Written(RootModel[Done | Preview]):
    """A replaced record, or, with preview=true, what the write would change."""


class Write(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview: bool = Field(False, description="Save nothing; answer with what the write would change.")


class Removal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permanent: bool = Field(False, description="Remove the record's address too, so that another record can have it.")


class Move(BaseModel):
    to: str = Field(pattern=f"^{IDENTIFIER.pattern}$", description="The record's new identifier.")


class Image(BaseModel):
    id: str = Field(alias="@id", description="The image's address, to give in a record's image field.")


def local(iri: str) -> str:
    return re.split(r"[/#]", iri)[-1]


@cache
def record_model(kind: str) -> type[BaseModel]:
    """A record of a class in JSON-LD: its fields, as the model's shapes name and explain them."""
    fields = {
        "@id": (str | None, Field(None, description="The record's address.")),
        "@type": (Any, Field(None, description="The record's class.")),
    }
    for field in forms.form(kind):
        fields[field["name"]] = (Any, Field(None, title=field["label"], description=field["help"] or None))
    extensions = {"x-jsonld-type": kind, "x-jsonld-context": documents.context(settings())}
    return create_model(local(kind), __config__=ConfigDict(extra="allow", json_schema_extra=extensions), **fields)


@cache
def collection_model(kind: str) -> type[BaseModel]:
    """A page of the records of a class, as a Hydra collection."""
    fields = {
        "@context": (dict, Field(description="The JSON-LD context of the page and of its records.")),
        "@id": (str, Field(description="The address of the records of the query.")),
        "@type": (Literal["hydra:Collection"], ...),
        "hydra:totalItems": (int, Field(description="How many records the query gives.")),
        "hydra:member": (list[record_model(kind)], Field(description="The records of this page.")),
        "hydra:view": (dict[str, str], Field(description="This page, and the addresses of the first, previous, next and last pages.")),
    }
    extensions = {"x-jsonld-type": HYDRA + "Collection", "x-jsonld-context": {"hydra": HYDRA}}
    return create_model(local(kind) + "Collection", __config__=ConfigDict(json_schema_extra=extensions), **fields)


@cache
def query_model(kind: str) -> type[BaseModel]:
    """The query of a page of the records of a class: every field is a filter."""
    fields = {
        "q": (str | None, Field(None, description="Records whose name has this text, in small or capital letters.")),
        "id": (list[str] | None, Field(None, description="Records at these addresses.")),
        "source": (list[str] | None, Field(None, description='Records of these sources, or of "platform" for records written on the platform.')),
        "limit": (int, Field(PAGE, ge=1, le=LARGEST_PAGE, description="How many records a page gives.")),
        "offset": (int, Field(0, ge=0, description="How many records come before this page.")),
    }
    for field in forms.form(kind):
        explanation = f"Records whose field has one of these values; a link is given by its address. {field['help']}"
        fields[field["name"]] = (list[str] | None, Field(None, title=field["label"], description=explanation.strip()))
    return create_model(local(kind) + "Query", __config__=ConfigDict(extra="forbid"), **fields)


class RecordsDocument(SpecTree):
    """The OpenAPI document of this API. JSON-LD answers are given under their own media type, and the
    addresses of the records, which answer by content negotiation, are added to the API's own routes."""

    def _generate_spec(self) -> dict:
        found = super()._generate_spec()
        schemas = found["components"]["schemas"]
        for operations in found["paths"].values():
            for operation in operations.values():
                for answer in operation["responses"].values():
                    content = answer.get("content", {})
                    name = content.get("application/json", {}).get("schema", {}).get("$ref", "").rsplit("/", 1)[-1]
                    if "x-jsonld-type" in schemas.get(name, {}):
                        content["application/ld+json"] = content.pop("application/json")
        found["paths"].update(addresses())
        return found


document = RecordsDocument(
    "flask",
    title=f"{settings()['title']}: records",
    version=RELEASE,
    description=__doc__,
    path="api/docs/records",
    mode="strict",
    annotations=False,
    naming_strategy=lambda model: model.__name__,
    nested_naming_strategy=lambda parent, child: child,
    security_schemes=[SecurityScheme(name="token", data=SecuritySchemeData(type="http", scheme="bearer", description=tokens.__doc__))],
)


@blueprint.record_once
def register(state) -> None:
    document.register(state.app)


def addresses() -> dict:
    """The addresses of the records on the platform, one path for each form they take, with what each
    answers: the record's page, or its data in the format that Accept asks for."""
    base = settings()["base"]
    found = {}
    with database.session() as db:
        kept = db.execute(select(Record.iri, Record.type).where(Record.iri.startswith(base), Record.removed_at.is_(None))).all()
    for iri, kind in kept:
        parts = iri.removeprefix(base).split("/")
        if len(parts) < 2:
            continue
        names = []
        for number in range(1, len(parts) - 1):
            names.append(f"part{number}")
        names.append("identifier")
        path = "/" + parts[0]
        parameters = []
        for name in names:
            path += "/{" + name + "}"
            parameters.append({"name": name, "in": "path", "required": True, "schema": {"type": "string"}})
        content = {"text/html": {"schema": {"type": "string"}}}
        for media in FORMATS:
            content[media] = {"schema": {"type": "string"}}
        content[FORMATS[0]] = {"schema": {"$ref": f"#/components/schemas/{local(kind)}"}}
        found.setdefault(path, {"get": {
            "summary": f"A record of {local(kind)}: its page, or its data",
            "description": "The record's page, or its data in the format that the Accept header asks for; the endings .jsonld, .ttl and .nt ask for a format too.",
            "operationId": "record" + path.replace("/", "_").replace("{", "").replace("}", ""),
            "tags": ["record addresses"],
            "parameters": parameters,
            "responses": {
                "200": {"description": "The record.", "content": content},
                "301": {"description": "The record moved; Location gives its new address."},
                "410": {"description": "The record was removed."},
            },
        }})
    return found


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


def answers(**given) -> Response:
    """The answers of a route, and the refusal of too many requests that every route gives."""
    return Response(**given, HTTP_429=(Error, f"More than {RATE_LIMIT} requests in {RATE_WINDOW} seconds came from this address."))


def paged(offset: int, limit: int) -> str:
    """The address of a page of the collection that the request asks for."""
    given = request.args.copy()
    given["offset"] = str(offset)
    given["limit"] = str(limit)
    return request.base_url + "?" + urlencode(list(given.items(multi=True)))


def listing(kind: str):
    """The records of a kind, a page at a time.

    A record is given when each field of the query has one of the values given for it; repeat a
    parameter for several values. The records come in the order of their names."""
    kinds = settings()["kinds"]
    fields = {}
    for field in forms.form(kinds[kind]):
        fields[field["name"]] = field["iri"]
    given = request.context.query.model_dump(exclude_none=True)
    conditions = [Record.type == kinds[kind], Record.removed_at.is_(None)]
    for name, values in given.items():
        if name in fields:
            conditions.append(storage.having(kinds[kind], fields[name], values))
    if "q" in given:
        conditions.append(func.lower(Record.name).contains(given["q"].lower(), autoescape=True))
    if "id" in given:
        conditions.append(Record.iri.in_(given["id"]))
    if "source" in given:
        conditions.append(Record.source.in_(given["source"]))
    limit, offset = given["limit"], given["offset"]
    with database.session() as db:
        total = db.scalar(select(func.count()).select_from(Record).where(*conditions))
        statement = select(Record.iri).where(*conditions).order_by(func.lower(Record.name), Record.iri)
        page = list(db.scalars(statement.limit(limit).offset(offset)))
    found = storage.read(page)
    members = []
    for iri in page:
        member = forms.shaped(documents.document(found, iri), kinds[kind])
        member.pop("@context", None)
        members.append(member)
    view = {"@id": paged(offset, limit), "@type": "hydra:PartialCollectionView", "hydra:first": paged(0, limit),
            "hydra:last": paged(max(total - 1, 0) // limit * limit, limit)}
    if offset > 0:
        view["hydra:previous"] = paged(max(offset - limit, 0), limit)
    if offset + limit < total:
        view["hydra:next"] = paged(offset + limit, limit)
    collection = {
        "@context": {**documents.context(settings()), "hydra": HYDRA},
        "@id": request.base_url,
        "@type": "hydra:Collection",
        "hydra:totalItems": total,
        "hydra:member": members,
        "hydra:view": view,
    }
    return Answer(json.dumps(collection, indent=2), mimetype="application/ld+json")


def get(kind: str, identifier: str):
    """A record, as the API takes it back with PUT."""
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is None or record.type != settings()["writable"][kind]:
        return error("There is no record of this kind at this address.", 404)
    if record.moved_to:
        return redirect(url_for(f"api.get_{kind}", identifier=record.moved_to.rsplit("/", 1)[-1]), code=301)
    if record.removed_at:
        return error("This record was removed.", 410)
    found = forms.shaped(documents.document(storage.read([record.iri]), record.iri), record.type)
    return Answer(json.dumps(found, indent=2), mimetype="application/ld+json")


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
    """The record of the request's body is checked and saved; the answer says how it went."""
    writable = settings()["writable"]
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
        found, problems, warnings = checks.checked(writes.document(writable[kind], address, body))
    except ValueError as problem:
        return error(str(problem), 422)
    if problems:
        return jsonify({"error": str(checks.NotFitting(problems)), "fields": problems}), 422
    revision = writes.save(documents.document(found, address), writable[kind], token.name, token.orcid, replace)
    writes.name_things(writes.titled(writable[kind], body))
    return done(address, revision, 201 if revision.action == "Added" else 200, warnings)


def preview(address: str, kind: str, body: dict):
    """The statements a write would publish, compared with the record as it is, and what is wrong with each field."""
    try:
        found, problems, warnings = checks.checked(writes.document(kind, address, body))
    except ValueError as problem:
        return error(str(problem), 422)
    before = changes.statements(documents.document_of(address))
    return jsonify({**changes.edges(before, found, URIRef(address)), "fields": problems, "warnings": warnings})


def put(kind: str, identifier: str):
    """Add or replace the record with this identifier.

    The record is checked against the model; one that does not fit is refused, with what is wrong with each
    field. Fields set by the platform are set as the model gives them."""
    if not IDENTIFIER.fullmatch(identifier):
        return error("An identifier has lowercase letters, digits, hyphens and underscores.", 400)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is not None and record.moved_to:
        return error(f"This record moved to {record.moved_to}; write it there.", 409)
    if record is not None and record.removed_at:
        return error("This address belonged to a removed record and is not given again.", 409)
    return store(kind, identifier)


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


def delete(kind: str, identifier: str):
    """Remove a record.

    Its address answers 410 Gone from then on, and is not given to another record, unless the removal is
    permanent. A removed record can be put back with restore."""
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
        return done(record.iri, writes.remove(record.iri, token.name, token.orcid), 200)
    return done(record.iri, writes.retire(record.iri, token.name, token.orcid), 200)


def move(kind: str, identifier: str):
    """Move a record to a new identifier.

    Its old address forwards to the new one."""
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is None or record.removed_at:
        return error("There is no record at this address.", 404)
    body = request.get_json(silent=True)
    to = body.get("to") if isinstance(body, dict) else None
    if not isinstance(to, str) or not IDENTIFIER.fullmatch(to):
        return error('The new address is given as {"to": "<identifier>"}, with lowercase letters, digits, hyphens and underscores.', 400)
    target = records.get(records.address(f"{kind}/{to}"))
    if target is not None and target.moved_to != record.iri:
        return error("This address is taken by another record, or was one.", 409)
    conflict = changed_since_read(record.iri)
    if conflict:
        return conflict
    address = records.address(f"{kind}/{to}")
    return done(address, writes.move(record.iri, address, token.name, token.orcid), 200)


def restore(kind: str, identifier: str):
    """Put back a removed record."""
    token = authorized(kind)
    if token is None:
        return error("A valid write token for this kind of record is needed.", 401)
    record = records.get(records.address(f"{kind}/{identifier}"))
    if record is None or not record.removed_at:
        return error("There is no removed record at this address.", 404)
    return done(record.iri, writes.restore(record.iri, token.name, token.orcid), 200)


TOKEN = (Error, "No valid write token for this kind of record, and no login of an editor who may write it.")
CHANGED = (Error, "The record changed since the version that If-Match gives.")
MISSING = (Error, "There is no record at this address.")
NOT_FITTING = (Problems, "The record does not fit the model, or has a field that the platform does not keep.")


@blueprint.post("/api/images")
@document.validate(resp=answers(HTTP_201=Image, HTTP_400=(Error, 'No form field "image".'), HTTP_401=TOKEN,
                                HTTP_413=(Error, "The image is larger than 5 MB."), HTTP_422=(Error, "The file is not an image that the platform takes.")),
                   tags=["images"], security={"token": []})
def upload_image():
    """Upload an image, such as a tool's logo, as the form field "image".

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


@blueprint.get("/api/shapes.ttl")
@document.validate(resp=answers(HTTP_200=None), tags=["model"])
def model_shapes():
    """The model's SHACL shapes, which say what each field of a record takes."""
    return Answer(shapes().serialize(format="turtle"), mimetype="text/turtle")


# The routes of each kind of record, with the models of its own fields.
for name, kind in settings()["kinds"].items():
    view = document.validate(query=query_model(kind), resp=answers(HTTP_200=(collection_model(kind), "A page of the records, with how many the query gives.")), tags=[name])(listing)
    blueprint.add_url_rule(f"/api/{name}", f"list_{name}", view, methods=["GET"], defaults={"kind": name})
for name, kind in settings().get("writable", {}).items():
    record = record_model(kind)
    routes = [
        ("/<identifier>", "GET", get, {"resp": answers(HTTP_200=record, HTTP_301=None, HTTP_404=MISSING, HTTP_410=(Error, "The record was removed."))}),
        ("/<identifier>", "PUT", put, {"query": Write, "json": record, "security": {"token": []}, "resp": answers(
            HTTP_200=(Written, "The record was replaced; with preview=true, what the write would change."), HTTP_201=(Done, "The record was added."),
            HTTP_400=(Error, "The identifier or the body is not as the API takes it."), HTTP_401=TOKEN,
            HTTP_409=(Error, "The record moved, or the address belonged to a removed record."), HTTP_412=CHANGED, HTTP_422=NOT_FITTING)}),
        ("", "POST", post, {"query": Write, "json": record, "security": {"token": []}, "resp": answers(
            HTTP_200=(Preview, "With preview=true, what the write would change."), HTTP_201=(Done, "The record was added."),
            HTTP_400=(Error, "The body has no name."), HTTP_401=TOKEN, HTTP_422=NOT_FITTING)}),
        ("/<identifier>", "DELETE", delete, {"query": Removal, "security": {"token": []}, "resp": answers(
            HTTP_200=(Done, "The record was removed."), HTTP_401=TOKEN, HTTP_404=MISSING, HTTP_412=CHANGED)}),
        ("/<identifier>/move", "POST", move, {"json": Move, "security": {"token": []}, "resp": answers(
            HTTP_200=(Done, "The record moved."), HTTP_401=TOKEN, HTTP_404=MISSING,
            HTTP_409=(Error, "The new address is taken by another record, or was one."), HTTP_412=CHANGED)}),
        ("/<identifier>/restore", "POST", restore, {"security": {"token": []}, "resp": answers(
            HTTP_200=(Done, "The record was put back."), HTTP_401=TOKEN, HTTP_404=(Error, "There is no removed record at this address."))}),
    ]
    for ending, method, function, given in routes:
        view = document.validate(tags=[name], **given)(function)
        blueprint.add_url_rule(f"/api/{name}{ending}", f"{function.__name__}_{name}", view, methods=[method], defaults={"kind": name})
