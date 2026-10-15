"""The records on the platform's pages.

The address of a record answers with its data when JSON-LD, Turtle or N-Triples is asked for, with
the Accept header or with a .jsonld, .ttl or .nt ending (/tools/pathvisio.ttl), and its page links
to that data. The address of a removed record answers 410 Gone, and an earlier address of a record
that moved forwards to its address (301). A record with no page of its own is shown on a general
record page.
"""

import json

from flask import Blueprint, Response, current_app, g, redirect, render_template, request

from database import records
from database.tables import Record
from linkeddata import forms, rdf
from linkeddata.model import settings

FORMATS = {".jsonld": "application/ld+json", ".ttl": "text/turtle", ".nt": "application/n-triples"}
SERIALIZATIONS = {"text/turtle": "turtle", "application/n-triples": "nt"}

blueprint = Blueprint("pages", __name__)


def page_path(record: Record) -> str:
    return "/" + record.iri.removeprefix(settings()["base"])


def data(record: Record, media: str) -> Response:
    found = rdf.linked_graph(record)
    if media == "application/ld+json":
        body = json.dumps(rdf.document(found), indent=2)
    else:
        body = found.serialize(format=SERIALIZATIONS[media])
    return Response(body, mimetype=media, headers={"Vary": "Accept"})


@blueprint.before_app_request
def negotiate():
    """The data of a record is sent when it is asked for; otherwise its page is made as usual."""
    if request.endpoint in ("static", "images.image") or request.path.startswith("/api/"):
        return None
    path = request.path.strip("/")
    media = None
    for ending, ending_media in FORMATS.items():
        if path.endswith(ending):
            path = path.removesuffix(ending)
            media = ending_media
    if media is None:
        media = request.accept_mimetypes.best_match(["text/html", *FORMATS.values()], "text/html")
    record = records.get(records.address(path))
    if record is None:
        return None
    if record.moved_to:
        ending = request.path.removeprefix("/" + path) if request.path.startswith("/" + path) else ""
        target = page_link(record.moved_to) + ending
        if request.query_string:
            target += "?" + request.query_string.decode()
        return redirect(target, code=301)
    if record.removed_at:
        return render_template("records/gone.html", record=record, page_title="Removed — VHP4Safety"), 410
    if media != "text/html":
        return data(record, media)
    g.record = record
    return None


@blueprint.after_app_request
def link_data(response):
    if "record" in g:
        links = []
        for ending, media in FORMATS.items():
            links.append(f'<{page_path(g.record)}{ending}>; rel="alternate"; type="{media}"')
        response.headers["Link"] = ", ".join(links)
        response.headers["Vary"] = "Accept"
    return response


@blueprint.app_context_processor
def record_context() -> dict:
    """The JSON-LD of the page's record and the addresses of its data, for the head of the page."""
    if "record" not in g:
        return {}
    formats = {}
    for ending, media in FORMATS.items():
        formats[media] = page_path(g.record) + ending
    try:
        document = rdf.document(rdf.linked_graph(g.record))
    except ValueError as problem:
        current_app.logger.warning("The record %s does not fit the model: %s", g.record.iri, problem)
        document = None
    return {"record_document": document, "record_formats": formats}


@blueprint.app_template_filter("short_iri")
def short_iri(iri: str) -> str:
    """An address written with the model's prefixes: https://schema.org/name is name."""
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            if prefix == "schema":
                return iri.removeprefix(namespace)
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


@blueprint.app_template_filter("page_link")
def page_link(iri: str) -> str:
    """The link to a platform address on this server, so that it works on every copy of the platform."""
    if iri.startswith(settings()["base"]):
        return "/" + iri.removeprefix(settings()["base"])
    return iri


@blueprint.app_errorhandler(404)
def record_page(error):
    """A record with no page of its own is shown on the general record page."""
    if "record" not in g:
        return error
    record = g.record
    shown = []
    links = []
    for field in forms.form(record.type):
        value = getattr(record, field["name"])
        if value:
            shown.append({"name": field["name"], "label": field["label"], "values": value if isinstance(value, list) else [value]})
        if field["several"]:
            links.extend(value or [])
    name = record.name or record.iri
    return render_template(
        "records/record.html",
        record=record,
        fields=shown,
        names=records.names(links),
        page_title=f"{name} — VHP4Safety",
        meta_description=(record.description or "")[:160] or f"{name}, a record of the VHP4Safety Virtual Human Platform.",
    )
