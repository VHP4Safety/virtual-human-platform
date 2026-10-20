"""Pages and data of the records.

- Data: JSON-LD, Turtle or N-Triples, at the address of a record, requested with the Accept header or with a
  .jsonld, .ttl or .nt extension (/tools/pathvisio.ttl).
- Markdown: the page in Markdown, for text/markdown or a .md extension.
- Signposting: Link headers on each page, as in FAIR Signposting (cite-as, type, describedby, and the shapes of the
  checks with ldp:constrainedBy).
- Removed records: 410 Gone. Earlier addresses of moved records: redirect (301).
- Records without a page of their own: shown on a general record page.
"""

import json
import re
from datetime import datetime, timezone

from flask import Blueprint, Response, abort, current_app, g, redirect, render_template, request, url_for
from markupsafe import Markup
from rdfsolve._uri import prefix_map
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
# The platform pages with their earlier templates; their texts are read from the records.
PAGE_TEMPLATES = {"safety_assessment_workflow": "safety_assessment_workflow.html", "legal/privacypolicy": "legal/privacypolicy.html",
                  "legal/terms_of_service": "legal/terms_of_service.html"}
# A page is also changed by a change of the code, such as a new release.
STARTED = datetime.now(timezone.utc).replace(microsecond=0)


def data(found: Graph, media: str, iri: str | None = None) -> Response:
    """Return statements in JSON-LD, Turtle or N-Triples.

    Also return JSON-LD if plain JSON is requested. With *iri*, return the document of that record, with the names
    of the linked records."""
    if media in ("application/ld+json", "application/json"):
        body = json.dumps(documents.document(found, iri, named=True), indent=2)
    else:
        # The namespaces of the properties and the classes are named: by the prefixes of the profile, and the others
        # by rdfsolve (glossary for https://vhp4safety.github.io/glossary#), so that none is written as ns1.
        # rdfsolve gap: prefix_map is imported from rdfsolve.iris once the rdfsolve pin includes its export (9770523).
        terms = {str(term) for term in found.predicates()} | {str(term) for term in found.objects(None, RDF.type)}
        for prefix, namespace in prefix_map(terms, settings()["prefixes"]).items():
            found.bind(prefix, namespace, override=True, replace=True)
        body = found.serialize(format=SERIALIZATIONS[media])
    return Response(body, mimetype=media, headers={"Vary": "Accept"})


def not_acceptable() -> Response:
    """Return the formats of an address, if none of the requested formats (Accept) is available."""
    lines = ["None of the formats asked for is given here. This address answers in:", "- text/html"]
    for ending, media in FORMATS.items():
        lines.append(f"- {media}, or with the ending {ending}")
    lines.append("- application/json (its JSON-LD)")
    lines.append(f"- text/markdown, or with the ending {MARKDOWN}")
    return Response("\n".join(lines) + "\n", status=406, content_type="text/plain; charset=utf-8", headers={"Vary": "Accept"})


def markdown_of(record: Record) -> Response:
    """Return the page of a record in Markdown, with links to its data."""
    formats = {}
    for ending, name in FORMAT_NAMES.items():
        formats[name] = record.iri + ending
    body = pages.markdown(record, formats, void.platform()["license"])
    return Response(body, content_type=pages.MEDIA, headers={"Vary": "Accept"})


def listing_page(kind: str):
    """Return the page of the records of a kind, found by name and filtered by the filter fields
    (templates/records/listing.html). List tools, methods and data as in the cloud catalogue (templates/tools,
    templates/methods, templates/data), and models as the data."""
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
    """Return the data of a record if it is requested; otherwise continue with the page."""
    if request.endpoint in ("static", "images.image") or request.path.startswith("/api/"):
        return None
    # An address with a slash at the end and without a page of its own is redirected to the address without the
    # slash (/casestudies/ to /casestudies), so that each page has one address.
    if request.url_rule is None and len(request.path) > 1 and request.path.endswith("/"):
        target = request.path.rstrip("/")
        if request.query_string:
            target += "?" + request.query_string.decode()
        return redirect(target, code=308)
    path = request.path.strip("/")
    media = None
    for ending, ending_media in {**FORMATS, MARKDOWN: "text/markdown"}.items():
        if path.endswith(ending):
            path = path.removesuffix(ending)
            media = ending_media
    # The page is returned for a request without Accept; for a request of other formats only, the formats are listed.
    if media is None:
        media = request.accept_mimetypes.best_match(OFFERED) if request.accept_mimetypes else "text/html"
    # At the page of a kind (/tools), the records are listed as in the API, in the formats of the API.
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
        # The data of the platform record is the VoID description of its dataset; another record is one document with its parts.
        if record.iri == settings()["base"]:
            return data(void.described(), media)
        return data(documents.linked(record), media, record.iri)
    # A record with no page of its own is shown on the general record page.
    if request.url_rule is None:
        return record_page(record)
    return None


@blueprint.get("/<path:path>/ro-crate-metadata.json")
def ro_crate(path: str):
    """Return a record as a detached RO-Crate (linkeddata/crates.py)."""
    record = records.get(records.address(path))
    if record is None or record.removed_at or record.moved_to:
        abort(404)
    body = json.dumps(crates.crate(record), indent=2)
    return Response(body, mimetype="application/ld+json", headers={"Access-Control-Allow-Origin": "*",
                    "Link": f'<{crates.PROFILE}>; rel="profile", <{record.iri}>; rel="cite-as"'})


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


# The next parts of the address of a case study are used for its page (app.py), so the address of its crate is routed here.
@blueprint.get("/casestudies/<case>/ro-crate-metadata.json")
def case_study_crate(case: str):
    return ro_crate("casestudies/" + case)


@blueprint.after_app_request
def link_data(response):
    links = []
    if "record" in g:
        links = [f'<{g.record.iri}>; rel="cite-as"', f'<{g.record.type}>; rel="type"']
        for ending, media in FORMATS.items():
            links.append(f'<{page_link(g.record.iri)}{ending}>; rel="describedby"; type="{media}"')
        links.append(f'<{page_link(g.record.iri)}/ro-crate-metadata.json>; rel="describedby"; type="application/ld+json"; profile="{crates.PROFILE}"')
        links.append(f'<{url_for("records.model_shapes")}>; rel="http://www.w3.org/ns/ldp#constrainedBy"; type="text/turtle"')
        links.append(f'<{page_link(g.record.iri)}{MARKDOWN}>; rel="alternate"; type="text/markdown"')
        response.headers["Vary"] = "Accept"
    # The licence of the records, from the catalogue of the platform, on their pages, their data and the API, and the
    # dataset of a record (VoID).
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
    """Return 304 Not Modified for the page or the data of a record that is not changed.

    As the linked records and the records that name a record are shown on its page, return 304 only if no record was
    changed after the copy of the client. Leave out the platform record."""
    latest = records.latest_change()
    changed = max(datetime.fromisoformat(latest) if latest else STARTED, STARTED)
    response.set_etag(f"{latest}-{int(STARTED.timestamp())}-{response.mimetype}", weak=True)
    response.last_modified = changed
    response.make_conditional(request)


@blueprint.app_context_processor
def publisher_context() -> dict:
    """Give the publisher of the platform and the licence of the records to all pages."""
    return {"publisher_document": void.platform()["publisher"], "records_license": void.platform()["license"]}


@blueprint.app_context_processor
def record_context() -> dict:
    """Return the JSON-LD of the record of the page, with the names of the linked records, and its data addresses,
    for the page head."""
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
    return {"record_document": document, "record_formats": formats, "record_markdown": page_link(g.record.iri) + MARKDOWN,
            "record_crate": page_link(g.record.iri) + "/ro-crate-metadata.json"}


# An address written with the prefixes of the model: name for https://schema.org/name.
blueprint.add_app_template_filter(jsonld_name, "short_iri")


@blueprint.app_template_filter("issue_tracker")
def issue_tracker(addresses) -> str:
    """Return the GitHub address for questions: an issue, or the issues of the first repository among the addresses,
    or an empty text if no address is on GitHub."""
    for address in addresses or []:
        found = re.match(r"https://github\.com/([^/]+)/([^/#?]+)(/issues/\d+)?", str(address))
        if found and found.group(3):
            return found.group(0)
        if found:
            return f"https://github.com/{found.group(1)}/{found.group(2).removesuffix('.git')}/issues"
    return ""


@blueprint.app_template_filter("page_link")
def page_link(iri: str) -> str:
    """Return a platform address as a path on this server, so that the link is valid on each copy of the platform."""
    return pages.local(iri)


def record_page(record: Record):
    """Return the page of a record.

    Show tools, methods, datasets and models as in the cloud catalogue (templates/tools, templates/methods,
    templates/data). Show platform pages with templates/records/page.html, or with their earlier template. Show
    other records on the general record page."""
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
