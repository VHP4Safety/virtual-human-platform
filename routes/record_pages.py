"""The records on the platform's pages.

A record's address answers with its data when JSON-LD, Turtle or N-Triples is asked for, by the Accept
header or a .jsonld, .ttl or .nt ending (/tools/pathvisio.ttl), and with its page in Markdown for
text/markdown or a .md ending. Its page links to that data with FAIR
Signposting (Link headers): cite-as, type, describedby, and the shapes it is checked with
(ldp:constrainedBy). A removed record's address answers 410 Gone; an earlier address of a moved record
forwards (301). A record without a page of its own is shown on a general record page.
"""

import json
import re
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, g, redirect, render_template, request, url_for
from rdflib import Graph
from rdflib.namespace import SDO

from database import records
from database.tables import Record
from linkeddata import catalogue, documents, markdown, outline, pages
from linkeddata.model import settings

FORMATS = {".jsonld": "application/ld+json", ".ttl": "text/turtle", ".nt": "application/n-triples"}
FORMAT_NAMES = {".jsonld": "JSON-LD", ".ttl": "Turtle", ".nt": "N-Triples"}
# A page in Markdown, for readers of plain text such as agents.
MARKDOWN = ".md"
OFFERED = ["text/html", *FORMATS.values(), "application/json", "text/markdown"]
SERIALIZATIONS = {"text/turtle": "turtle", "application/n-triples": "nt"}

blueprint = Blueprint("pages", __name__)
# A page also changes with the code that makes it, as after a new release.
STARTED = datetime.now(timezone.utc).replace(microsecond=0)


def page_path(record: Record) -> str:
    return "/" + record.iri.removeprefix(settings()["base"])


def data(found: Graph, media: str, iri: str | None = None) -> Response:
    """Statements in JSON-LD (the document of the record at *iri*, when it is given, with the names of the records
    it links to), also when plain JSON is asked for, Turtle or N-Triples."""
    if media in ("application/ld+json", "application/json"):
        body = json.dumps(documents.document(found, iri, named=True), indent=2)
    else:
        body = found.serialize(format=SERIALIZATIONS[media])
    return Response(body, mimetype=media, headers={"Vary": "Accept"})


def not_acceptable() -> Response:
    """The formats an address answers in, when none of those asked for (Accept) is one of them."""
    lines = ["None of the formats asked for is given here. This address answers in:", "- text/html"]
    for ending, media in FORMATS.items():
        lines.append(f"- {media}, or with the ending {ending}")
    lines.append("- application/json (its JSON-LD)")
    lines.append(f"- text/markdown, or with the ending {MARKDOWN}")
    return Response("\n".join(lines) + "\n", status=406, content_type="text/plain; charset=utf-8", headers={"Vary": "Accept"})


def markdown_of(record: Record) -> Response:
    """A record's page in Markdown, with links to its data."""
    formats = {}
    for ending, name in FORMAT_NAMES.items():
        formats[name] = record.iri + ending
    body = markdown.record(outline.outline(record), formats, settings()["license"])
    return Response(body, content_type=markdown.MEDIA, headers={"Vary": "Accept"})


@blueprint.before_app_request
def negotiate():
    """A record's data is sent when asked for; otherwise its page is made as usual."""
    if request.endpoint in ("static", "images.image") or request.path.startswith("/api/"):
        return None
    path = request.path.strip("/")
    media = None
    for ending, ending_media in {**FORMATS, MARKDOWN: "text/markdown"}.items():
        if path.endswith(ending):
            path = path.removesuffix(ending)
            media = ending_media
    # A request without Accept takes the page; one asking only for other formats is told those given.
    if media is None:
        media = request.accept_mimetypes.best_match(OFFERED) if request.accept_mimetypes else "text/html"
    # A kind's page (/tools) lists its records as the API does, in the formats the API answers.
    if path in settings()["kinds"] and media is None:
        return not_acceptable()
    if path in settings()["kinds"] and media != "text/html":
        g.listing = path
        g.media = media
        return current_app.view_functions[f"api.list_{path}"]()
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
    if media != "text/html":
        return data(documents.linked(record), media)
    # A record with no page of its own is shown on the general record page.
    if request.url_rule is None:
        return record_page(record)
    return None


@blueprint.after_app_request
def link_data(response):
    links = []
    if "record" in g:
        links = [f'<{g.record.iri}>; rel="cite-as"', f'<{g.record.type}>; rel="type"']
        for ending, media in FORMATS.items():
            links.append(f'<{page_path(g.record)}{ending}>; rel="describedby"; type="{media}"')
        links.append(f'<{url_for("api.model_shapes")}>; rel="http://www.w3.org/ns/ldp#constrainedBy"; type="text/turtle"')
        links.append(f'<{page_path(g.record)}{MARKDOWN}>; rel="alternate"; type="text/markdown"')
        response.headers["Vary"] = "Accept"
    # The records' licence, on their pages, their data and the API.
    if "record" in g or "listing" in g or request.path.startswith("/api/"):
        links.append(f'<{settings()["license"]}>; rel="license"')
    if links:
        given = response.headers.get("Link")
        response.headers["Link"] = ", ".join(([given] if given else []) + links)
    if "record" in g and request.method in ("GET", "HEAD") and response.status_code == 200:
        conditional(response)
    # Scripts of other sites may read public data; without credentials, so as visitors.
    if request.method in ("GET", "HEAD") and (request.path.startswith("/api/") or "listing" in g or ("record" in g and response.mimetype != "text/html")):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "Link, ETag, Last-Modified, X-Pagination"
    return response


def conditional(response) -> None:
    """A record's page or data answers 304 Not Modified when nothing changed since the client's copy: no record
    (as a page shows the records it links to and those that name it), and not the platform itself."""
    latest = records.latest_change()
    changed = max(datetime.fromisoformat(latest) if latest else STARTED, STARTED)
    response.set_etag(f"{latest}-{int(STARTED.timestamp())}-{response.mimetype}", weak=True)
    response.last_modified = changed
    response.make_conditional(request)


@blueprint.app_context_processor
def record_context() -> dict:
    """The page record's JSON-LD and data addresses, for the page head."""
    if "record" not in g:
        return {}
    formats = {}
    for ending, media in FORMATS.items():
        formats[media] = page_path(g.record) + ending
    try:
        document = documents.document(documents.linked(g.record), g.record.iri)
    except ValueError as problem:
        current_app.logger.warning("The record %s does not fit the model: %s", g.record.iri, problem)
        document = None
    return {"record_document": document, "record_formats": formats, "record_markdown": page_path(g.record) + MARKDOWN}


@blueprint.app_template_filter("short_iri")
def short_iri(iri: str) -> str:
    """An address written with the model's prefixes: https://schema.org/name is name."""
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            if prefix == "schema":
                return iri.removeprefix(namespace)
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


@blueprint.app_template_filter("issue_tracker")
def issue_tracker(addresses) -> str:
    """Where to ask about something on GitHub: an issue itself, or the issues of the first repository among the
    addresses; empty when none is on GitHub."""
    for address in addresses or []:
        found = re.match(r"https://github\.com/([^/]+)/([^/#?]+)(/issues/\d+)?", str(address))
        if found and found.group(3):
            return found.group(0)
        if found:
            return f"https://github.com/{found.group(1)}/{found.group(2).removesuffix('.git')}/issues"
    return ""


@blueprint.app_template_filter("page_link")
def page_link(iri: str) -> str:
    """A platform address as a path on this server, so it works on every copy of the platform."""
    if iri.startswith(settings()["base"]):
        return "/" + iri.removeprefix(settings()["base"])
    return iri


def record_page(record: Record):
    """A record's page: a platform page's own (templates/records/page.html), or the general record page."""
    if record.type in catalogue.within(str(SDO.WebPage)):
        found = pages.page(record)
        return render_template("records/page.html", page=found, page_title=f"{found['name']} — VHP4Safety",
                               meta_description=found["description"][:160] or f"{found['name']}, a page of the VHP4Safety Virtual Human Platform.")
    found = outline.outline(record)
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
