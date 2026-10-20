"""API of the platform, made with flask-smorest and documented at /api/docs/."""

import json

from flask import Response, g, jsonify, redirect, render_template, request, url_for
from flask_smorest import Api, Blueprint, abort
from marshmallow import INCLUDE, Schema, fields, pre_load
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO
from rdfsolve.ontology.service import PROVIDERS, Ontologies, serving
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

import database
from admin import changes, tokens, writes
from database import images, records, tables
from linkeddata import checks, documents, pages
from linkeddata.profile import RELEASE, jsonld_name, settings, shapes
from routes import account, limiter
from routes.record_pages import SERIALIZATIONS, data, markdown_of

DESCRIPTION = """REST API of the VHP4Safety platform. Read, list and filter records in JSON-LD, Turtle, N-Triples and
Markdown. Write records in JSON-LD or Turtle with a write token.

The records conform to schema.org and Bioschemas. The field names are defined in the JSON-LD context
(`x-jsonld-context` of the Record schema), and the fields of each kind are described in the SHACL shapes at
`/api/shapes.ttl`. To get the data of a page of the website, add a file extension to the page address, such as
`/tools/aopwiki.ttl`.

[The platform](/) · [Write tokens](/account/tokens/) · [Record editor](/admin/)"""

# In the documentation, the operations of the blueprint are grouped under its name, and the others under TAGS.
blueprint = Blueprint("records", __name__, url_prefix="/api", description="Read, list, filter and search records.")
TAGS = [
    {"name": "downloads", "description": "Download all records, the vocabulary terms in use and the SHACL shapes, each as one file."},
    {"name": "editing", "description": "Add, change, move, remove and restore records. A write token for the kind is required."},
    {"name": "vocabularies", "description": "Search vocabulary registries for terms. For editors only."},
]
limiter.limit("300 per minute")(blueprint)
TOKEN = [{"token": []}]
WRITE = {"security": TOKEN, "requestBody": {"content": {"text/turtle": {"schema": {"type": "string"}}}}}
BASE = settings()["base"]
GLOSSARY = "https://vhp4safety.github.io/glossary#"
# Examples of the records that are written.
NEW_TOOL = {"tool": {"summary": "A new tool", "value": {
    "@type": "SoftwareApplication", "name": "AOP-Builder", "description": "Builds AOPs from the literature.",
    "url": {"@id": "https://github.com/VHP4Safety/aop-builder"},
    "processFlowStep": [{"@id": GLOSSARY + "VHP0000156"}]}}}
CASE_STUDY = {"casestudy": {"summary": "A case study with one question, at /api/casestudies/kidney", "value": {
    "@type": "bioschemas_draft:Study", "name": "Kidney case study", "description": "To study kidney disease.",
    "regulatoryQuestion": [{"@type": "HowTo", "name": "Question 1: Cisplatin dose", "position": 1}]}}}
# Examples of the records that are read.
TOOL = {"@id": BASE + "tools/aopwikiapi", "@type": "SoftwareApplication", "name": "AOP-Wiki API",
        "description": "A REST API for the AOP-Wiki RDF data that returns AOPs, Key Events and stressors as JSON or CSV.",
        "about": {"@id": GLOSSARY + "VHP0000023"}, "license": {"@id": "https://spdx.org/licenses/MIT"},
        "dct:conformsTo": {"@id": "https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE"}}
TOOL_TURTLE = f"""@prefix dct: <http://purl.org/dc/terms/> .
@prefix glossary: <{GLOSSARY}> .
@prefix schema: <https://schema.org/> .

<{BASE}tools/aopwikiapi> a schema:SoftwareApplication ;
    dct:conformsTo <https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE> ;
    schema:about glossary:VHP0000023 ;
    schema:description "A REST API for the AOP-Wiki RDF data that returns AOPs, Key Events and stressors as JSON or CSV." ;
    schema:license <https://spdx.org/licenses/MIT> ;
    schema:name "AOP-Wiki API" .
"""
TOOL_MARKDOWN = f"""# AOP-Wiki API

<{BASE}tools/aopwikiapi>

**Description**

A REST API for the AOP-Wiki RDF data that returns AOPs, Key Events and stressors as JSON or CSV.

- **Topics:** [Adverse Outcome Pathway]({GLOSSARY}VHP0000023)
- **License:** [MIT License](https://spdx.org/licenses/MIT)

---

Data: [JSON-LD]({BASE}tools/aopwikiapi.jsonld) · [Turtle]({BASE}tools/aopwikiapi.ttl) · [N-Triples]({BASE}tools/aopwikiapi.nt)
"""


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


def kind_of(address: str | None, body: dict) -> str | None:
    """Return the kind of the record at address, or of the @type of a new record in body."""
    record = records.get(address) if address else None
    given = record.type if record is not None else body.get("@type")
    names = {}
    for name, kind in settings()["kinds"].items():
        for of_class in records.within(kind):
            names[of_class] = name
    for value in given if isinstance(given, list) else [given]:
        if isinstance(value, str):
            iri = value if value.startswith(("http://", "https://")) else documents.expand(value)
            if iri in names:
                return names[iri]
    return None


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
        headers["Location"] = url_for("records.read", path=records.path(address))
    return {"@id": address, "change": url_for("changes.change", number=revision.id), "version": version, "warnings": warnings or {}}, status, headers


def unchanged(address: str) -> None:
    """Refuse a write with a version in If-Match if the record was changed after that version."""
    expected = request.headers.get("If-Match", "").strip('" ')
    record = records.get(address)
    if expected and record is not None and record.updated_at != expected:
        abort(412, message="Changed since it was opened; reopen it to see the change.")


def whole(record) -> None:
    """Refuse a write of a part, such as a case-study question, as parts are written with their record."""
    if record is not None and record.part_of:
        abort(409, message=f"Part of {record.part_of}; written with it.")


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
    writes.kept(found, address, kind)
    writes.classed(found, address)
    # Only http and https addresses are accepted, so that no script (javascript:) or file address is stored as a link.
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != RDF.type and not str(value).startswith(("https://", "http://")):
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


def formats(description: str, examples: dict) -> dict:
    """Document the response in each format, with an example."""
    content = {}
    for name, example in examples.items():
        content[name] = {"schema": {"$ref": "#/components/schemas/Record"} if name == "application/ld+json" else {"type": "string"}, "example": example}
    return {"200": {"description": description, "content": content}}


def found_record(path: str):
    """Return the record at a page address, also if it was moved or removed."""
    record = records.get(records.address(path))
    if record is None:
        abort(404, message="No record at this address.")
    return record


class Search(Schema):
    text = fields.String(load_default="", metadata={"description": "Text in the name or the address.", "example": "aop-wiki"})
    of_class = fields.List(fields.Url(metadata={"format": "iri"}), data_key="class", load_default=list, metadata={"description": "Classes (IRIs) of the records or terms. Subclasses are included.", "example": ["https://schema.org/SoftwareApplication"]})
    within = fields.String(load_default="", metadata={"description": "The start of the address, such as a vocabulary namespace."})
    vocabulary = fields.Url(load_default="", metadata={"format": "iri", "description": "The IRI of a vocabulary. Only its terms are searched."})
    limit = fields.Integer(load_default=20, validate=lambda number: 1 <= number <= 200, metadata={"description": "The maximum number of results, from 1 to 200."})


class Registry(Schema):
    text = fields.String(load_default="", metadata={"description": "Text in the name of a vocabulary or a term.", "example": "liver"})
    namespace = fields.String(load_default="", metadata={"description": "The namespace of the vocabulary that is searched.", "example": "http://purl.obolibrary.org/obo/UBERON_"})


def registered() -> None:
    """Refuse registry requests from visitors. Allow editors, signed in or with a valid write token."""
    token = tokens.find(tokens.bearer(request.headers.get("Authorization", "")))
    if account.current_editor() is None and token is None:
        abort(401, message="Login or write token needed.")


@blueprint.get("/registries", tags=["vocabularies"])
@blueprint.response(200, {"type": "object"}, example=PROVIDERS)
def registries():
    """List the vocabulary registries."""
    registered()
    return jsonify(PROVIDERS)


@blueprint.get("/registries/<registry>/vocabularies", tags=["vocabularies"])
@blueprint.arguments(Registry, location="query")
@blueprint.response(200, {"type": "array"}, example=[{"id": "uberon", "title": "Uber-anatomy ontology", "namespace": "http://purl.obolibrary.org/obo/UBERON_",
                                                     "description": "An integrated cross-species anatomy ontology.", "prefix": "UBERON"}])
@blueprint.doc(description="Return up to 50 vocabularies with the text in the identifier or the title.")
def registry_vocabularies(given, registry):
    """Search the vocabularies of a registry."""
    registered()
    if registry not in PROVIDERS:
        abort(404, message="No such registry.")
    with Ontologies(registry, cache=database.STATE_DIR / "registries.json") as provider:
        return jsonify(provider.vocabularies(given["text"])[:50])


@blueprint.get("/registries/terms", tags=["vocabularies"])
@blueprint.arguments(Registry, location="query")
@blueprint.response(200, {"type": "object"}, example={"registry": "ols", "title": PROVIDERS["ols"], "terms": [
    {"@id": "http://purl.obolibrary.org/obo/UBERON_0002107", "name": "liver", "description": "An exocrine gland which secretes bile.", "code": "UBERON:0002107"}]})
@blueprint.doc(description=(
    "Return the terms of the namespace with the text in the name. The terms are read from the registry of the "
    "namespace."
))
def registry_terms(given):
    """Search the terms of a vocabulary."""
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
@blueprint.response(200, {"type": "object"}, content_type="application/ld+json", example={"@graph": [
    {"@id": BASE + "tools/aopwikiapi", "@type": "SoftwareApplication", "name": "AOP-Wiki API"},
    {"@id": GLOSSARY + "VHP0000318", "@type": "DefinedTerm", "name": "AOP-Wiki API"}]})
@blueprint.doc(description="Return the records, parts and terms with the text in the name or the address.")
def search(given):
    """Search records and vocabulary terms."""
    found = []
    among = records.nodes_with(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet), [given["vocabulary"]]) if given["vocabulary"] else None
    for record in records.search(given["text"], given["of_class"] or list(settings()["kinds"].values()), given["within"], limit=given["limit"], among=among):
        found.append({"@id": record.iri, "@type": jsonld_name(record.type), "name": record.name or record.iri})
    return jsonify({"@context": documents.context(settings()), "@graph": found})


class FacetValue(Schema):
    value = fields.String(metadata={"description": "The value as used in a filter: an IRI, or a text from a list."})
    name = fields.String(metadata={"description": "The name of the record or the label of the term."})
    count = fields.Integer(metadata={"description": "The number of records with the value."})
    fits = fields.Boolean(metadata={"description": "False if the value does not fit the field: a text where a link is required, or a value that is not in the list."})


class Query(Schema):
    # No example, as Swagger UI fills in an example, and an optional filter then changes the list.
    search = fields.String(load_default="", metadata={"description": "Text in the name or the address of the record, such as aop. The case is ignored."})

    class Meta:
        unknown = INCLUDE

    @pre_load
    def every_value(self, data, **kwargs):
        """Keep all values of a field filter."""
        found = {}
        for name in data:
            found[name] = data[name] if name in self.fields else data.getlist(name)
        return found


KIND = "/<any({}):kind>".format(", ".join(settings()["kinds"]))
OF_KIND = [{"in": "path", "name": "kind", "description": "The kind of the records.", "example": "tools",
            "schema": {"type": "string", "enum": list(settings()["kinds"])}}]
AT_PATH = [{"in": "path", "name": "path", "description": "The page address of the record, without the base address.", "example": "tools/aopwikiapi"}]
LISTED = "One page of records, in the format requested in the Accept header."


@blueprint.route(KIND, methods=["GET"], parameters=OF_KIND)
@blueprint.response(200, {"type": "object"}, content_type="application/ld+json", description=LISTED, example={"@graph": [TOOL]})
@blueprint.alt_response(200, schema={"type": "string"}, content_type="text/turtle", success=True, description=LISTED, example=TOOL_TURTLE)
@blueprint.alt_response(200, schema={"type": "string"}, content_type="application/n-triples", success=True, description=LISTED,
                        example=f'<{BASE}tools/aopwikiapi> <https://schema.org/name> "AOP-Wiki API" .\n')
@blueprint.alt_response(200, schema={"type": "string"}, content_type="text/markdown", success=True, description=LISTED, example=TOOL_MARKDOWN)
@blueprint.arguments(Query, location="query", unknown=INCLUDE)
@blueprint.paginate(page_size=20, max_page_size=200)
@blueprint.doc(description=(
    "Return one page of records, sorted by name, in the format of the Accept header. Find records by name or "
    "address with search. Filter records by the field names of /api/shapes.ttl, such as "
    "/api/tools?processFlowStep=https://vhp4safety.github.io/glossary%23VHP0000156. Give several values of one "
    "field to find the records with any of them, and several fields to find the records that match all of them."
))
def listed(given, kind, pagination_parameters):
    """List the records of a kind."""
    of_class = settings()["kinds"][kind]
    # At the address of a kind (/tools.ttl), all records of the kind are returned as one file, not as pages.
    whole = "listing" in g
    first, size = (0, None) if whole else (pagination_parameters.first_item, pagination_parameters.page_size)
    total, iris = records.page(of_class, records.filters(of_class, given), given["search"], first, size)
    if whole:
        pagination_parameters.page, pagination_parameters.page_size = 1, max(total, 1)
    pagination_parameters.item_count = total
    found = readable(records.graph(iris), kind)
    # The format requested at the page of a kind (/tools) is used, also when it is requested with a file extension (/tools.ttl).
    media = g.get("media") or request.accept_mimetypes.best_match(["application/ld+json", *SERIALIZATIONS, "text/markdown"], "application/ld+json")
    if media == "text/markdown":
        texts = []
        for iri in iris:
            texts.append(markdown_of(records.get(iri)).get_data(as_text=True))
        return Response("\n".join(texts), content_type=pages.MEDIA, headers={"Vary": "Accept"})
    if media in SERIALIZATIONS:
        return data(found, media)
    documented = []
    for iri in iris:
        document = documents.document(found, iri)
        document.pop("@context", None)
        documented.append(document)
    return Response(json.dumps({"@context": documents.context(settings()), "@graph": documented}, indent=1), mimetype="application/ld+json", headers={"Vary": "Accept"})


@blueprint.get(KIND + "/facets", parameters=OF_KIND)
@blueprint.arguments(Query, location="query", unknown=INCLUDE)
@blueprint.response(200, {"type": "object", "additionalProperties": {"type": "array", "items": {"$ref": "#/components/schemas/FacetValue"}}},
                    description="The values of each field, by the name of the field.",
                    example={"about": [{"value": GLOSSARY + "VHP0000023", "name": "Adverse Outcome Pathway", "count": 9, "fits": True},
                                       {"value": GLOSSARY + "VHP0000148", "name": "Chemical Information Tool", "count": 5, "fits": True}]})
@blueprint.doc(description=(
    "Return the number of records for each value of each filter field, for the same query as the list. The filter "
    "of a field is not applied to the counts of that field."
))
def counted(given, kind):
    """Count the records of a kind by field value."""
    return jsonify(records.counted(settings()["kinds"][kind], given))


@blueprint.post(KIND, tags=["editing"], parameters=OF_KIND)
@blueprint.arguments(Record, content_type="application/ld+json", examples=NEW_TOOL)
@blueprint.response(201, Done, description="Added.")
@blueprint.doc(**WRITE)
@blueprint.doc(description=(
    "Store a new record of the kind, sent in JSON-LD or Turtle, at an address made from the name. Store a "
    "vocabulary term at the address in @id. Store a record that does not fit the shapes too, and return the "
    "problems as warnings."
))
def added(body, kind):
    """Add a record."""
    # In Turtle, the record is the node of the class of the kind.
    given = None
    if request.mimetype == "text/turtle":
        given = Graph().parse(data=request.get_data(as_text=True), format="turtle")
        node = given.value(None, RDF.type, URIRef(settings()["kinds"][kind]))
        body = {"name": str(given.value(node, SDO.name) or "")}
    # A vocabulary term is stored at the address in @id. Other records are stored at an address made from the name.
    address = body.get("@id") or writes.free(records.address(f"{kind}/{writes.slug(str(body.get('name') or kind))}"), set())
    if records.get(address) is not None:
        abort(409, message="Address taken.")
    if given is not None:
        writes.renamed(given, node, address)
        body = documents.document(given, address)
    body = {"@type": jsonld_name(settings()["kinds"][kind]), **body}
    return store(address, body)


@blueprint.get("/<path:path>", parameters=AT_PATH)
@blueprint.doc(responses=formats("The record, in the format requested in the Accept header.", {
    "application/ld+json": TOOL, "text/turtle": TOOL_TURTLE,
    "application/n-triples": f'<{BASE}tools/aopwikiapi> <https://schema.org/name> "AOP-Wiki API" .\n', "text/markdown": TOOL_MARKDOWN}))
@blueprint.doc(description=(
    "Return the record or part at a page address, such as tools/aopwikiapi, in the format of the Accept header. The"
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
@blueprint.arguments(Writing, location="query")
@blueprint.arguments(Record, content_type="application/ld+json", examples=CASE_STUDY)
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
    if request.mimetype == "text/turtle":
        body = documents.document(Graph().parse(data=request.get_data(as_text=True), format="turtle"), address)
    return store(address, body, given["preview"], given["page"])


@blueprint.delete("/<path:path>", tags=["editing"], parameters=AT_PATH)
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
    who = writer(kind_of(record.iri, {}))
    unchanged(record.iri)
    if given["permanent"]:
        return done(record.iri, writes.remove(record.iri, who.name, who.orcid), 200)
    return done(record.iri, writes.retire(record.iri, who.name, who.orcid), 200)


@blueprint.post("/move", tags=["editing"])
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
    who = writer(kind_of(record.iri, {}))
    target = records.get(records.address(body["to"]))
    if target is not None and target.moved_to != record.iri:
        abort(409, message="Address taken, now or before.")
    unchanged(record.iri)
    return done(records.address(body["to"]), writes.move(record.iri, records.address(body["to"]), who.name, who.orcid), 200)


@blueprint.post("/restore", tags=["editing"])
@blueprint.arguments(Restore)
@blueprint.response(200, Done, description="Restored.")
@blueprint.doc(security=TOKEN)
def restore(body):
    """Restore a removed record."""
    record = found_record(body["record"])
    if not record.removed_at:
        abort(404, message="No removed record at this address.")
    who = writer(kind_of(record.iri, {}))
    return done(record.iri, writes.restore(record.iri, who.name, who.orcid), 200)


@blueprint.post("/images", tags=["editing"])
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
@blueprint.doc(responses=formats("All records, in the format requested in the Accept header.", {
    "application/n-triples": f'<{BASE}tools/aopwikiapi> <https://schema.org/name> "AOP-Wiki API" .\n', "text/turtle": TOOL_TURTLE}))
@blueprint.doc(description=(
    "Return all records with a page, with their parts, in N-Triples (the default) or Turtle, without private "
    "fields. The dataset is described at /.well-known/void."
))
def dump():
    """Download all records."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published(), media)


@blueprint.get("/dump/terms", tags=["downloads"])
@blueprint.doc(responses=formats("The vocabulary terms, in the format requested in the Accept header.", {
    "application/n-triples": f'<{GLOSSARY}VHP0000023> <https://schema.org/name> "Adverse Outcome Pathway" .\n',
    "text/turtle": f'<{GLOSSARY}VHP0000023> a <https://schema.org/DefinedTerm> ;\n    <https://schema.org/name> "Adverse Outcome Pathway" .\n'}))
@blueprint.doc(description=(
    "Return the vocabulary terms linked from the records, in N-Triples (the default) or Turtle. The source and the "
    "licence of each vocabulary are described at /.well-known/void."
))
def dump_terms():
    """Download the vocabulary terms in use."""
    media = request.accept_mimetypes.best_match(["application/n-triples", "text/turtle"]) or "application/n-triples"
    return data(documents.published_terms(), media)


@blueprint.get("/shapes.ttl", tags=["downloads"])
@blueprint.doc(responses=formats("The shapes, in Turtle.", {"text/turtle": """@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

[] a sh:NodeShape ;
    sh:targetClass schema:SoftwareApplication ;
    sh:property [ sh:path schema:name ; sh:name "Name" ; sh:datatype xsd:string ; sh:maxCount 1 ] .
"""}))
@blueprint.doc(description=(
    "Return the shapes in Turtle, with the fields of each kind of record, their JSON-LD names and their allowed "
    "values."
))
def model_shapes():
    """Get the SHACL shapes of the model."""
    return Response(shapes().serialize(format="turtle"), mimetype="text/turtle")


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

    # Errors are returned in JSON by flask-smorest. For pages requested by browsers, an HTML error page is returned
    # with the same status code.
    @app.errorhandler(HTTPException)
    def error_page(problem: HTTPException):
        if request.path.startswith("/api/") or not any(media == "text/html" for media, _ in request.accept_mimetypes):
            return api.handle_http_exception(problem)
        return render_template("error.html", error=problem, page_title=f"{problem.code} {problem.name} — VHP4Safety",
                               meta_description=problem.description or problem.name), problem.code
    api.spec.components.security_scheme("token", {"type": "http", "scheme": "bearer", "description": "A write token, sent as `Authorization: Bearer <token>`. Make tokens at `/account/tokens/`. A token is valid for the kinds chosen for it, for 90 days by default."})
    api.spec.components.schema("Record", component={"x-jsonld-context": documents.context(settings())}, schema=Record)
    api.spec.components.schema("FacetValue", schema=FacetValue)
    api.register_blueprint(blueprint)
    for tag in TAGS:
        api.spec.tag(tag)
