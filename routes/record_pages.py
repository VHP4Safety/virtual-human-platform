"""Pages and data of the records."""

import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from flask import Blueprint, Response, abort, current_app, g, redirect, render_template, request, url_for
from markupsafe import Markup
from rdfsolve.iris import prefix_map
from rdflib import RDF, Graph
from rdflib.namespace import SDO

from database import records
from database.tables import Record
from linkeddata import crates, documents, pages, void
from linkeddata.profile import jsonld_name, settings

FORMATS = {".jsonld": "application/ld+json", ".ttl": "text/turtle", ".nt": "application/n-triples"}
FORMAT_NAMES = {".jsonld": "JSON-LD", ".ttl": "Turtle", ".nt": "N-Triples"}
# A page in Markdown, for readers of plain text such as agents.
MARKDOWN = ".md"
OFFERED = ["text/html", *FORMATS.values(), "application/json", "text/markdown"]
SERIALIZATIONS = {"text/turtle": "turtle", "application/n-triples": "nt"}

blueprint = Blueprint("pages", __name__)
# The platform pages that are drawn with a template of their own. Their texts are read from the records.
PAGE_TEMPLATES = {"safety_assessment_workflow": "safety_assessment_workflow.html", "legal/privacypolicy": "legal/privacypolicy.html",
                  "legal/terms_of_service": "legal/terms_of_service.html"}
# A page is also changed by a change of the code, such as a new release.
STARTED = datetime.now(timezone.utc).replace(microsecond=0)


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


def not_acceptable() -> Response:
    """Return 406 with the formats of the address."""
    lines = ["None of the formats asked for is given here. This address answers in:", "- text/html"]
    for ending, media in FORMATS.items():
        lines.append(f"- {media}, or with the ending {ending}")
    lines.append("- application/json (its JSON-LD)")
    lines.append(f"- text/markdown, or with the ending {MARKDOWN}")
    return Response("\n".join(lines) + "\n", status=406, content_type="text/plain; charset=utf-8", headers={"Vary": "Accept"})


def markdown_of(record: Record) -> Response:
    """Return the page of a record in Markdown."""
    formats = {}
    for ending, name in FORMAT_NAMES.items():
        formats[name] = record.iri + ending
    body = pages.markdown(record, formats, void.platform()["license"])
    return Response(body, content_type=pages.MEDIA, headers={"Vary": "Accept"})


def listing_page(kind: str):
    """Return the listing page of a kind."""
    if kind in ("tools", "methods"):
        found = pages.catalogue_listing(kind, request.args)
        return render_template(f"{kind}/{kind}.html", **found, page_title=f"{pages.kind_names()[kind]} — VHP4Safety")
    if kind == "data":
        return render_template("data/data.html", **pages.data_listing(request.args), page_title=f"{pages.kind_names()[kind]} — VHP4Safety")
    if kind == "models":
        return render_template("data/data.html", **pages.model_listing(request.args), page_title=f"{pages.kind_names()[kind]} — VHP4Safety")
    page = records.get(records.address(kind))
    if page is not None and page.type in records.within(str(SDO.WebPage)):
        # A kind with a page record at its path, such as the training page, is listed as the items of that page.
        found = pages.page(page)
        _, iris = records.page(settings()["kinds"][kind], {}, "", 0, None)
        return render_template("records/page.html", page=found, listed=pages.items(iris), page_title=f"{found['name']} — VHP4Safety",
                               meta_description=found["description"][:160] or f"{found['name']}, a page of the VHP4Safety Virtual Human Platform.")
    found = pages.listing(kind, request.args)
    return render_template("records/listing.html", listing=found, page_title=f"{found['name'] or kind.capitalize()} — VHP4Safety")


@blueprint.before_app_request
def negotiate():
    """Return the data of a record if it is requested."""
    if request.endpoint in ("static", "images.image") or request.path.startswith("/api/"):
        return None
    # An address with a slash at the end and without a page of its own is redirected to the address without the
    # slash (/casestudies/ to /casestudies), so that each page has one address.
    if request.url_rule is None and len(request.path) > 1 and request.path.endswith("/"):
        target = "/" + quote(request.path.strip("/"))
        if request.query_string:
            target += "?" + request.query_string.decode()
        return redirect(target, code=308)
    path = request.path.strip("/")
    media = None
    for ending, ending_media in {**FORMATS, MARKDOWN: "text/markdown"}.items():
        if path.endswith(ending):
            path = path.removesuffix(ending)
            media = ending_media
    # The page is returned for a request without Accept. For a request of other formats only, the formats are listed.
    if media is None:
        media = request.accept_mimetypes.best_match(OFFERED) if request.accept_mimetypes else "text/html"
    # At the page of a kind (/tools), all records of the kind are given in the formats of the API, without pages.
    if path in settings()["kinds"] and media is None:
        return not_acceptable()
    if path in settings()["kinds"] and media != "text/html":
        g.listing = path
        g.media = media
        return current_app.view_functions["records.listed"](kind=path)
    # For a kind without a page of its own, the records are listed.
    if path in settings()["kinds"] and request.url_rule is None:
        return listing_page(path)
    record = records.get(records.address(path))
    if record is None:
        return None
    if media is None:
        return not_acceptable()
    if record.moved_to:
        ending = request.path.removeprefix("/" + path) if request.path.startswith("/" + path) else ""
        target = page_link(record.moved_to) + ending
        if request.query_string:
            target += "?" + request.query_string.decode()
        return redirect(target, code=301)
    if record.removed_at:
        return render_template("records/gone.html", record=record, page_title="Removed — VHP4Safety"), 410
    g.record = record
    if media == "text/markdown":
        return markdown_of(record)
    # The address of the platform is the address of its dataset, so its data is the VoID description.
    if media != "text/html":
        # The data of another record is one document with its parts.
        if record.iri == settings()["base"]:
            return data(void.described(), media)
        return data(documents.linked(record), media, record.iri)
    # A record with no page of its own is shown on the general record page.
    if request.url_rule is None:
        return record_page(record)
    return None


@blueprint.get("/<path:path>/ro-crate-metadata.json")
def ro_crate(path: str):
    """Return the RO-Crate of a model."""
    record = records.get(records.address(path))
    if not crates.of_models(record):
        abort(404)
    headers = {"Access-Control-Allow-Origin": "*", "Content-Disposition": f'inline; filename="{crates.file_name(record)}"'}
    given = crates.zenodo(record)
    if given is not None:
        return Response(given, mimetype="application/ld+json", headers=headers)
    headers["Link"] = f'<{crates.PROFILE}>; rel="profile", <{record.iri}>; rel="cite-as"'
    return Response(json.dumps(crates.crate(record), indent=2), mimetype="application/ld+json", headers=headers)


# The root of the draft crate of a model is at the model address with /ro-crate/ (linkeddata/crates.py).
@blueprint.get("/<path:path>/ro-crate/")
def crate_root(path: str):
    if not crates.of_models(records.get(records.address(path))):
        abort(404)
    return redirect(f"/{path}/ro-crate-metadata.json", code=303)


# The models are listed as the data, so the listing has an address of its own for its page links.
@blueprint.get("/models")
def models():
    return listing_page("models")


# The addresses of the model pages of the cloud catalogue are redirected to the models.
@blueprint.get("/models_page")
def models_page():
    return redirect("/models", code=301)


@blueprint.get("/model/<name>")
def model_page(name: str):
    return redirect("/models/" + name, code=301)


@blueprint.after_app_request
def link_data(response):
    links = []
    if "record" in g:
        links = [f'<{g.record.iri}>; rel="cite-as"', f'<{g.record.type}>; rel="type"']
        for ending, media in FORMATS.items():
            links.append(f'<{page_link(g.record.iri)}{ending}>; rel="describedby"; type="{media}"')
        if crates.of_models(g.record):
            links.append(f'<{page_link(g.record.iri)}/ro-crate-metadata.json>; rel="describedby"; type="application/ld+json"')
        links.append(f'<{url_for("records.model_shapes")}>; rel="http://www.w3.org/ns/ldp#constrainedBy"; type="text/turtle"')
        links.append(f'<{page_link(g.record.iri)}{MARKDOWN}>; rel="alternate"; type="text/markdown"')
        response.headers["Vary"] = "Accept"
    # The licence of the records is linked from their pages, their data and the API.
    if ("record" in g or "listing" in g or request.path.startswith("/api/")) and void.platform()["license"]:
        links.append(f'<{void.platform()["license"]}>; rel="license"')
    if "record" in g and g.record.iri != settings()["base"]:
        links.append(f'<{settings()["base"]}>; rel="http://rdfs.org/ns/void#inDataset"')
    if links:
        given = response.headers.get("Link")
        response.headers["Link"] = ", ".join(([given] if given else []) + links)
    if "record" in g and request.method in ("GET", "HEAD") and response.status_code == 200:
        conditional(response)
    # Public data may be read by scripts of other sites, without credentials, as visitors.
    if request.method in ("GET", "HEAD") and (request.path.startswith("/api/") or "listing" in g or ("record" in g and response.mimetype != "text/html")):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "Link, ETag, Last-Modified, X-Pagination"
    return response


def conditional(response) -> None:
    """Return 304 Not Modified if no record was changed since the request version."""
    latest = records.latest_change()
    changed = max(datetime.fromisoformat(latest) if latest else STARTED, STARTED)
    response.set_etag(f"{latest}-{int(STARTED.timestamp())}-{response.mimetype}", weak=True)
    response.last_modified = changed
    response.make_conditional(request)


@blueprint.app_context_processor
def publisher_context() -> dict:
    """Return the publisher of the platform and the licence of the records for the templates."""
    return {"publisher_document": void.platform()["publisher"], "records_license": void.platform()["license"]}


@blueprint.app_context_processor
def record_context() -> dict:
    """Return the JSON-LD and data addresses of the record of the page."""
    if "record" not in g:
        return {}
    formats = {}
    for ending, media in FORMATS.items():
        formats[media] = page_link(g.record.iri) + ending
    try:
        document = documents.page_document(g.record.iri, records.latest_change())
    except ValueError as problem:
        current_app.logger.warning("The record %s does not fit the model: %s", g.record.iri, problem)
        document = None
    found = {"record_document": document, "record_formats": formats, "record_markdown": page_link(g.record.iri) + MARKDOWN}
    # Only models have an RO-Crate. It is the crate in Zenodo, or a draft made from the record.
    if crates.of_models(g.record):
        found.update(record_crate=page_link(g.record.iri) + "/ro-crate-metadata.json", record_crate_draft=crates.zenodo(g.record) is None)
    return found


# An address written with a prefix of the model, such as name for https://schema.org/name.
blueprint.add_app_template_filter(jsonld_name, "short_iri")


@blueprint.app_template_filter("issue_tracker")
def issue_tracker(addresses) -> str:
    """Return the GitHub address for questions about a record, or an empty text."""
    for address in addresses or []:
        found = re.match(r"https://github\.com/([^/]+)/([^/#?]+)(/issues/\d+)?", str(address))
        if found and found.group(3):
            return found.group(0)
        if found:
            return f"https://github.com/{found.group(1)}/{found.group(2).removesuffix('.git')}/issues"
    return ""


@blueprint.app_template_filter("page_link")
def page_link(iri: str) -> str:
    """Return a platform address as a path on this server."""
    return pages.local(iri)


def record_page(record: Record):
    """Return the page of a record."""
    kind = records.path(record.iri).split("/", 1)[0]
    if kind == "tools" and record.part_of is None:
        details = pages.tool_details(record)
        return render_template("tools/tool.html", tool_json=details, tool_details=details, process_flow_steps=pages.steps(),
                               page_title=f"{details['service']} — VHP4Safety",
                               meta_description=details["description"][:160]
                               or f"{details['service']}, a tool in the VHP4Safety Virtual Human Platform.")
    if kind == "methods" and record.part_of is None:
        method = pages.method_json(record)
        return render_template("methods/method.html", method_json=method, method_details={}, page_title=f"{method['method']} — VHP4Safety",
                               meta_description=method["method_description_content"][:160]
                               or f"{method['method']}, a method in the VHP4Safety Virtual Human Platform.")
    if kind in ("data", "models") and record.part_of is None:
        found = pages.catalogue_details(record)
        filters = pages.catalogue_filters(kind, records.latest_change())
        description = Markup(found["norm_metadata"]["description"]).striptags()
        return render_template("data/data_details.html", data=found, kind=kind, reg_q_labels=filters["reg_q_labels"],
                               reg_q_urls=filters["reg_q_urls"], reg_q_steps=filters["reg_q_steps"],
                               outline=pages.outline(record) if kind == "models" else None, page_title=f"{found['title']} — VHP4Safety {kind}",
                               meta_description=description[:160] or f"{found['title']}: a record of the VHP4Safety {kind}.")
    if record.type in records.within(str(SDO.WebPage)):
        found = pages.page(record)
        steps = {term["iri"]: term for term in found["kinds"]}
        return render_template(PAGE_TEMPLATES.get(records.path(record.iri), "records/page.html"), page=found, process_flow_steps=steps,
                               page_title=f"{found['name']} — VHP4Safety",
                               meta_description=found["description"][:160] or f"{found['name']}, a page of the VHP4Safety Virtual Human Platform.")
    found = pages.outline(record)
    first = {}
    for field in found["fields"]:
        first[field["name"]] = field["values"][0]
    description = first.get("description", {}).get("text")
    image = first.get("image", {}).get("link")
    name = record.name or record.iri
    return render_template(
        "records/record.html",
        record={"iri": record.iri, "name": record.name, "description": description, "image": image},
        outline=found,
        page_title=f"{name} — VHP4Safety",
        meta_description=(description or "")[:160] or f"{name}, a record of the VHP4Safety Virtual Human Platform.",
    )
