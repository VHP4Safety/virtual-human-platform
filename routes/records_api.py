"""The API of the platform is made here with flask-smorest. It is documented at /api/docs/."""

import json

from flask import Response, current_app, g, jsonify, redirect, request, url_for
from flask_smorest import Api, Blueprint, abort
from marshmallow import INCLUDE, Schema, fields, pre_load
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO
from rdfsolve.ontology.service import PROVIDERS, Ontologies, serving
from werkzeug.exceptions import RequestEntityTooLarge

import database
from admin import changes, tokens, writes
from database import images, records
from linkeddata import catalogue, checks, documents, storage
from linkeddata.model import RELEASE, settings, shapes
from routes import account, limiter
from routes.record_pages import SERIALIZATIONS, data, markdown_of

DESCRIPTION = """Records are read in JSON-LD, Turtle, N-Triples or Markdown, and written in JSON-LD or Turtle. The JSON-LD
context of the platform gives the names of the fields. The SHACL shapes at /api/shapes.ttl tell what each field takes. A record that does not fit
the shapes is refused, with the problems of each field.

Writes need a write token or the login of an editor. The ETag of a record is its version. A write that sends this
version in If-Match is refused when the record was changed after it. With preview=true, nothing is saved and the
changes are shown."""

blueprint = Blueprint("api", __name__, url_prefix="/api", description="Records of each kind, at the addresses of their pages.")
limiter.limit("300 per minute")(blueprint)
TOKEN = [{"token": []}]
WRITE = {"security": TOKEN, "requestBody": {"content": {"text/turtle": {"schema": {"type": "string"}}}}}
# Records of a few kinds, as examples of a write.
EXAMPLES = {
    "tool": {"summary": "A tool, added with POST /api/tools", "value": {
        "@type": "SoftwareApplication", "name": "AOP-Builder", "description": "Builds AOPs from the literature.",
        "url": {"@id": "https://github.com/VHP4Safety/aop-builder"},
        "processFlowStep": [{"@id": "https://vhp4safety.github.io/glossary#VHP0000156"}]}},
    "casestudy": {"summary": "A case study with a question, written with PUT /api/casestudies/kidney", "value": {
        "@type": "bioschemas_draft:Study", "name": "Kidney case study", "description": "To study kidney disease.",
        "regulatoryQuestion": [{"@type": "HowTo", "name": "Question 1: Cisplatin dose", "position": 1}]}},
}


class Record(Schema.from_dict({"@type": fields.Raw(metadata={"description": "The class of the record. It is needed for a new record."})})):
    """A record in JSON-LD. The fields are set by the SHACL shapes at /api/shapes.ttl."""

    class Meta:
        unknown = INCLUDE


class Writing(Schema):
    preview = fields.Boolean(load_default=False, metadata={"description": "Nothing is saved, and the changes are shown."})
    page = fields.Boolean(load_default=False, metadata={"description": "With preview, the page is shown in HTML as it will be saved."})


class Removal(Schema):
    permanent = fields.Boolean(load_default=False, metadata={"description": "The address is removed too, so that it can be used again."})


class Restore(Schema):
    record = fields.String(required=True, metadata={"description": "The page address of the record, such as tools/aopsuite."})


class Move(Restore):
    to = fields.String(required=True, metadata={"description": "The new address of the record, such as tools/aop-suite."})


class Done(Schema.from_dict({"@id": fields.String(metadata={"description": "The address (IRI) of the record.", "format": "iri"})})):
    """The address and the version of the record, the page of the change and the empty recommended fields are
    given for a saved change."""

    change = fields.String()
    version = fields.String(allow_none=True)
    warnings = fields.Dict(keys=fields.String(), values=fields.List(fields.String()))


class Image(Schema.from_dict({"@id": fields.String(metadata={"description": "The address (IRI) of the image, for the image field of a record.", "format": "iri"})})):
    pass


def kind_of(address: str | None, body: dict) -> str | None:
    """The kind of the record at an address, or of the @type of a new record, is found by its class or by a
    class above it."""
    record = records.get(address) if address else None
    given = record.type if record is not None else body.get("@type")
    names = {}
    for name, kind in settings()["kinds"].items():
        for of_class in catalogue.within(kind):
            names[of_class] = name
    for value in given if isinstance(given, list) else [given]:
        if isinstance(value, str):
            iri = value if value.startswith(("http://", "https://")) else documents.expand(value)
            if iri in names:
                return names[iri]
    return None


def identity(kind: str):
    """The token or the logged-in editor of the request is given when it is allowed to write records of *kind*."""
    secret = tokens.bearer(request.headers.get("Authorization", ""))
    if secret is not None:
        return tokens.check(secret, kind)
    return account.editor_of_request(kind)


def reader(kind: str | None) -> bool:
    """Private fields, such as email addresses, are read only by an editor of the kind, with a login or a write
    token. No form token is needed, as nothing is changed."""
    if kind is None:
        return False
    secret = tokens.bearer(request.headers.get("Authorization", ""))
    if secret is not None:
        return tokens.check(secret, kind) is not None
    editor = account.current_editor()
    return editor is not None and kind in editor.kinds


def readable(found: Graph, kind: str | None) -> Graph:
    """Private fields are taken out of the statements for visitors."""
    return found if reader(kind) else documents.public(found)


@blueprint.after_request
def varied(response):
    """The answers are different for editors, as private fields are read by them too."""
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
        headers["Location"] = url_for("api.read", path=records.path(address))
    return {"@id": address, "change": url_for("changes.change", number=revision.id), "version": version, "warnings": warnings or {}}, status, headers


def unchanged(address: str) -> None:
    """A write with a version in If-Match is refused when the record was changed after that version."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if expected and record is not None and record.updated_at != expected:
        abort(412, message="Changed since it was opened; reopen it to see the change.")


def whole(record) -> None:
    """A part, such as a case study question, is written with its record."""
    if record is not None and record.part_of:
        abort(409, message=f"Part of {record.part_of}; written with it.")


def saved(address: str, found: Graph, kind: str, who):
    """The record is saved, and the new records in it are saved apart."""
    created = writes.separate(found)
    # A new record in the form of another record, such as a person, needs write access to the kind of the new record.
    for _, of_kind, _ in created:
        writer(kind_of(None, {"@type": of_kind}))
    for iri, of_kind, own in created:
        writes.save(documents.document(own, iri), of_kind, who.name, who.orcid)
    return writes.save(documents.document(found, address), kind, who.name, who.orcid)


def rendered(address: str, found: Graph, kind: str, who) -> Response:
    """The page of the record is made as it will be after the save, from a copy of the database."""
    with database.copied():
        saved(address, found, kind, who)
        path = "/" + records.path(address)
        with current_app.app_context(), current_app.test_request_context(path, base_url=request.host_url):
            answer = current_app.full_dispatch_request()
    return Response(answer.get_data(), status=answer.status_code, mimetype="text/html")


def store(address: str, body: dict, preview: bool = False, page: bool = False):
    """The record in the request body is checked and saved at *address*."""
    kind = kind_of(address, body)
    if kind is None:
        abort(400, message="Unknown @type.")
    who = writer(kind)
    if "@context" in body:
        body = documents.document(Graph().parse(data=json.dumps(body), format="json-ld"), address)
    kind = writes.class_of(settings()["kinds"][kind], body)
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


def formats(description: str, *media: str) -> dict:
    """The answer is documented in each of the formats."""
    content = {}
    for name in media:
        content[name] = {"schema": {"$ref": "#/components/schemas/Record"} if name == "application/ld+json" else {"type": "string"}}
    return {"200": {"description": description, "content": content}}


def found_record(path: str):
    """The record at the address of a page is found, also when it was moved or removed."""
    record = records.get(records.address(path))
    if record is None:
        abort(404, message="No record at this address.")
    return record


class Search(Schema):
    text = fields.String(load_default="", metadata={"description": "Text in the name or address."})
    of_class = fields.List(fields.Url(metadata={"format": "iri"}), data_key="class", load_default=list, metadata={"description": "Class IRIs of the records or terms. Subclasses are included."})
    within = fields.String(load_default="", metadata={"description": "The start of the address, such as a vocabulary namespace."})
    vocabulary = fields.Url(load_default="", metadata={"format": "iri", "description": "The terms of this vocabulary are searched."})
    limit = fields.Integer(load_default=20, validate=lambda number: 1 <= number <= 200)


class Registry(Schema):
    text = fields.String(load_default="", metadata={"description": "Text in the name of a vocabulary or a term."})
    namespace = fields.String(load_default="", metadata={"description": "The namespace of the vocabulary searched."})


def registered() -> None:
    """Registries are asked for editors only, with a login or a valid write token."""
    token = tokens.find(tokens.bearer(request.headers.get("Authorization", "")))
    if account.current_editor() is None and token is None:
        abort(401, message="Login or write token needed.")


@blueprint.get("/registries")
def registries():
    """The vocabulary registries searched by the editor are listed."""
    registered()
    return jsonify(PROVIDERS)


@blueprint.get("/registries/<registry>/vocabularies")
@blueprint.arguments(Registry, location="query")
def registry_vocabularies(given, registry):
    """The vocabularies of a registry with the text in their identifier or title are listed. The title, namespace
    and description of each are given."""
    registered()
    if registry not in PROVIDERS:
        abort(404, message="No such registry.")
    with Ontologies(registry, cache=database.STATE_DIR / "registries.json") as provider:
        return jsonify(provider.vocabularies(given["text"])[:50])


@blueprint.get("/registries/terms")
@blueprint.arguments(Registry, location="query")
def registry_terms(given):
    """The terms in a namespace with the text in their names are listed, from the registry of the namespace. The
    address, label, definition and code of each term are given."""
    registered()
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


@blueprint.get("/search")
@blueprint.arguments(Search, location="query")
def search(given):
    """Records, parts and vocabulary terms are found by name or address. The address, class and name of each
    are given in JSON-LD."""
    found = []
    among = catalogue.holders(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet), [given["vocabulary"]]) if given["vocabulary"] else None
    for record in records.search(given["text"], given["of_class"] or list(settings()["kinds"].values()), given["within"], limit=given["limit"], among=among):
        found.append({"@id": record.iri, "@type": documents.term(record.type), "name": record.name or record.iri})
    return jsonify({"@context": documents.context(settings()), "@graph": found})


class FacetValue(Schema):
    value = fields.String(metadata={"description": "The value as in records and queries: an IRI, or a text of a list."})
    name = fields.String(metadata={"description": "The name of the record or the label of the term."})
    count = fields.Integer(metadata={"description": "The count of found records with the value."})
    fits = fields.Boolean(metadata={"description": "False for a text where an IRI is needed, or for a value that is not in the list."})


class Query(Schema):
    search = fields.String(load_default="", metadata={"description": "Text in the name or address of the record, in any case."})

    class Meta:
        unknown = INCLUDE

    @pre_load
    def every_value(self, data, **kwargs):
        """All values of a field filter are kept."""
        found = {}
        for name in data:
            found[name] = data[name] if name in self.fields else data.getlist(name)
        return found


KIND = "/<any({}):kind>".format(", ".join(settings()["kinds"]))
LISTED = "The records in JSON-LD (the default), Turtle or N-Triples, by the Accept header."


@blueprint.route(KIND, methods=["GET"])
@blueprint.response(200, {"type": "object"}, content_type="application/ld+json", description=LISTED)
@blueprint.alt_response(200, schema={"type": "string"}, content_type="text/turtle", success=True, description=LISTED)
@blueprint.alt_response(200, schema={"type": "string"}, content_type="application/n-triples", success=True, description=LISTED)
@blueprint.arguments(Query, location="query", unknown=INCLUDE)
@blueprint.paginate(page_size=20, max_page_size=200)
def listed(given, kind, pagination_parameters):
    """The records of a kind are listed a page at a time, found by name and by field values.

    A field value is given by the name of the field in /api/shapes.ttl, such as
    /api/tools?processFlowStep=https://vhp4safety.github.io/glossary%23VHP0000156. Several values of one field
    match any. Several fields match all."""
    of_class = settings()["kinds"][kind]
    total, iris = catalogue.page(of_class, catalogue.filters(of_class, given), given["search"], pagination_parameters.first_item, pagination_parameters.page_size)
    pagination_parameters.item_count = total
    found = readable(storage.graph(iris), kind)
    # The format asked for at the page of a kind (/tools) is used, also when it is asked by an ending (/tools.ttl).
    media = g.get("media") or request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS], "application/ld+json")
    if media in SERIALIZATIONS:
        return data(found, media)
    documented = []
    for iri in iris:
        document = documents.document(found, iri)
        document.pop("@context", None)
        documented.append(document)
    return Response(json.dumps({"@context": documents.context(settings()), "@graph": documented}, indent=1), mimetype="application/ld+json", headers={"Vary": "Accept"})


@blueprint.get(KIND + "/facets")
@blueprint.arguments(Query, location="query", unknown=INCLUDE)
@blueprint.response(200, {"type": "object", "additionalProperties": {"type": "array", "items": {"$ref": "#/components/schemas/FacetValue"}}},
                    description="The values of each field, by the name of the field.")
def counted(given, kind):
    """The found records are counted per value of each field that can be browsed, with the query of the list.

    The filter of a field is not used for the counts of that field, so each count is what that value finds."""
    return jsonify(catalogue.counted(settings()["kinds"][kind], given))


@blueprint.post(KIND)
@blueprint.arguments(Record, content_type="application/ld+json", examples=EXAMPLES)
@blueprint.response(201, Done)
@blueprint.doc(**WRITE)
def added(body, kind):
    """A record is added in JSON-LD or Turtle, at an address made from its name."""
    # A record in Turtle is the node of the class of the kind.
    given = None
    if request.mimetype == "text/turtle":
        given = Graph().parse(data=request.get_data(as_text=True), format="turtle")
        node = given.value(None, RDF.type, URIRef(settings()["kinds"][kind]))
        body = {"name": str(given.value(node, SDO.name) or "")}
    # A vocabulary term is kept at its address. Other records are given an address from their name.
    address = body.get("@id") or writes.free(records.address(f"{kind}/{writes.slug(str(body.get('name') or kind))}"), set())
    if records.get(address) is not None:
        abort(409, message="Address taken.")
    if given is not None:
        writes.renamed(given, node, address)
        body = documents.document(given, address)
    body = {"@type": documents.term(settings()["kinds"][kind]), **body}
    return store(address, body)


@blueprint.get("/<path:path>")
@blueprint.doc(responses=formats("The record, in the format of the Accept header.", "application/ld+json", *SERIALIZATIONS, "text/markdown"))
def read(path):
    """A record or a part is read at the address of its page, in JSON-LD, Turtle, N-Triples or Markdown, by the
    Accept header."""
    record = found_record(path)
    if record.moved_to:
        return redirect(url_for("api.read", path=records.path(record.moved_to)), code=301)
    if record.removed_at:
        abort(410, message="Removed.")
    media = request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS, "text/markdown"]) or "application/ld+json"
    if media == "text/markdown":
        return markdown_of(record)
    # A part, such as a case study question, is read as its record is.
    kind = kind_of(record.part_of or record.iri, {})
    answer = data(readable(storage.with_names(storage.graph([record.iri])), kind), media, record.iri)
    answer.headers["ETag"] = f'"{record.updated_at}"'
    return answer


@blueprint.put("/<path:path>")
@blueprint.arguments(Writing, location="query")
@blueprint.arguments(Record, content_type="application/ld+json", examples=EXAMPLES)
@blueprint.response(200, Done, description="Replaced. With preview=true, the changes are shown and nothing is saved.")
@blueprint.alt_response(201, schema=Done, description="Added.")
@blueprint.doc(**WRITE)
def replace(given, body, path):
    """A record is added or replaced at the address of its page, in JSON-LD or Turtle."""
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
    """A record is removed, with its parts.

    Then 410 Gone is given at its address, and the address is not used again, unless the removal is permanent.
    The record can be put back with restore."""
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
@blueprint.response(200, Done, description="Moved. The old address forwards to the new one.")
@blueprint.doc(security=TOKEN)
def move(body):
    """A record is moved, with its parts, to a new address. The old address forwards to the new one."""
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
    """A removed record is put back, with its parts."""
    record = found_record(body["record"])
    if not record.removed_at:
        abort(404, message="No removed record at this address.")
    who = writer(kind_of(record.iri, {}))
    return done(record.iri, writes.restore(record.iri, who.name, who.orcid), 200)


@blueprint.post("/images")
@blueprint.response(201, Image)
@blueprint.doc(security=TOKEN)
def upload_image():
    """An image, such as the logo of a tool, is uploaded in the form field "image".

    The image is checked and saved as WebP. Its address is given in the image field of a record."""
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
@blueprint.doc(responses=formats("Every published statement, in Turtle or N-Triples, by the Accept header.", *SERIALIZATIONS))
def dump():
    """Every record with a page is given with its parts, as one file. Private fields are left out. The file is
    described at /.well-known/void."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published(), media)


@blueprint.get("/dump/terms")
@blueprint.doc(responses=formats("The vocabulary terms that the records link to, in Turtle or N-Triples, by the Accept header.", *SERIALIZATIONS))
def dump_terms():
    """The vocabulary terms that the records link to are given as one file, apart from the records. The source and
    licence of the terms are given by each vocabulary (/.well-known/void)."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published_terms(), media)


@blueprint.get("/shapes.ttl")
@blueprint.doc(responses=formats("The shapes, in Turtle.", "text/turtle"))
def model_shapes():
    """The SHACL shapes of the model tell what each field takes."""
    return Response(shapes().serialize(format="turtle"), mimetype="text/turtle")


def register(app) -> None:
    """The API is added to the app, with the OpenAPI document at /api/docs/."""
    app.config.update(
        API_TITLE=settings()["title"],
        API_VERSION=RELEASE,
        OPENAPI_VERSION="3.1.0",
        OPENAPI_URL_PREFIX="/api/docs",
        OPENAPI_JSON_PATH="openapi.json",
        OPENAPI_SWAGGER_UI_PATH="/",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/",
        API_SPEC_OPTIONS={"info": {"description": DESCRIPTION}},
    )
    api = Api(app)
    api.spec.components.security_scheme("token", {"type": "http", "scheme": "bearer", "description": tokens.__doc__})
    api.spec.components.schema("Record", component={"x-jsonld-context": documents.context(settings())}, schema=Record)
    api.spec.components.schema("FacetValue", schema=FacetValue)
    api.register_blueprint(blueprint)
