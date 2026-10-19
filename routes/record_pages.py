"""The records on the platform's pages.

A record's address answers with its data when JSON-LD, Turtle or N-Triples is asked for, by the Accept
header or a .jsonld, .ttl or .nt ending (/tools/pathvisio.ttl). Its page links to that data with FAIR
Signposting (Link headers): cite-as, type, describedby, and the shapes it is checked with
(ldp:constrainedBy). A removed record's address answers 410 Gone; an earlier address of a moved record
forwards (301). A record without a page of its own is shown on a general record page.
"""

import json

from flask import Blueprint, Response, current_app, g, redirect, render_template, request, url_for
from rdflib import RDFS, Graph

from database import records
from database.tables import Record
from linkeddata import catalogue, documents, fields, storage
from linkeddata.model import profile, settings

FORMATS = {".jsonld": "application/ld+json", ".ttl": "text/turtle", ".nt": "application/n-triples"}
SERIALIZATIONS = {"text/turtle": "turtle", "application/n-triples": "nt"}

blueprint = Blueprint("pages", __name__)


def page_path(record: Record) -> str:
    return "/" + record.iri.removeprefix(settings()["base"])


def data(found: Graph, media: str, iri: str | None = None) -> Response:
    """Statements in JSON-LD (the document of the record at *iri*, when it is given), also when plain JSON is
    asked for, Turtle or N-Triples."""
    if media in ("application/ld+json", "application/json"):
        body = json.dumps(documents.document(found, iri), indent=2)
    else:
        body = found.serialize(format=SERIALIZATIONS[media])
    return Response(body, mimetype=media, headers={"Vary": "Accept"})


@blueprint.before_app_request
def negotiate():
    """A record's data is sent when asked for; otherwise its page is made as usual."""
    if request.endpoint in ("static", "images.image") or request.path.startswith("/api/"):
        return None
    path = request.path.strip("/")
    media = None
    for ending, ending_media in FORMATS.items():
        if path.endswith(ending):
            path = path.removesuffix(ending)
            media = ending_media
    if media is None:
        media = request.accept_mimetypes.best_match(["text/html", *FORMATS.values(), "application/json"], "text/html")
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
        return data(documents.public(storage.linked_graph(record)), media)
    g.record = record
    # A record with no page of its own is shown on the general record page.
    if request.url_rule is None:
        return record_page(record)
    return None


@blueprint.after_app_request
def link_data(response):
    if "record" in g:
        links = [f'<{g.record.iri}>; rel="cite-as"', f'<{g.record.type}>; rel="type"']
        for ending, media in FORMATS.items():
            links.append(f'<{page_path(g.record)}{ending}>; rel="describedby"; type="{media}"')
        links.append(f'<{url_for("api.model_shapes")}>; rel="http://www.w3.org/ns/ldp#constrainedBy"; type="text/turtle"')
        response.headers["Link"] = ", ".join(links)
        response.headers["Vary"] = "Accept"
    return response


@blueprint.app_context_processor
def record_context() -> dict:
    """The page record's JSON-LD and data addresses, for the page head."""
    if "record" not in g:
        return {}
    formats = {}
    for ending, media in FORMATS.items():
        formats[media] = page_path(g.record) + ending
    try:
        document = documents.document(documents.public(storage.linked_graph(g.record)))
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
    """A platform address as a path on this server, so it works on every copy of the platform."""
    if iri.startswith(settings()["base"]):
        return "/" + iri.removeprefix(settings()["base"])
    return iri


def named_on(record: Record) -> dict[str, list[dict]]:
    """The records that name this one, by the label of the field that names it on them; each with its
    name and kind."""
    fields_of = {}
    for holder, path in catalogue.naming(record.iri):
        fields_of.setdefault(holder, []).append(path)
    found = {}
    for holder in records.kept(list(fields_of)):
        if holder.iri == record.iri:
            continue
        labels = {}
        for field in fields.of(holder.type):
            labels[field["iri"]] = field["label"]
        kind = profile().value(fields.shape_of(holder.type), RDFS.label)
        for path in fields_of[holder.iri]:
            found.setdefault(labels.get(path) or documents.term(path), []).append({"iri": holder.iri, "name": holder.name or holder.iri, "kind": str(kind or "")})
    for listed in found.values():
        listed.sort(key=lambda item: item["name"].casefold())
    return found


def record_page(record: Record):
    statements = documents.public(storage.graph([record.iri]))
    shown = []
    links = []
    for field in fields.of(record.type):
        found = documents.stored_values(statements, record.iri, field["name"])
        if found:
            shown.append({"name": field["name"], "label": field["label"], "values": found})
            links.extend(found)
    descriptions = documents.stored_values(statements, record.iri, "description")
    images = documents.stored_values(statements, record.iri, "image")
    name = record.name or record.iri
    return render_template(
        "records/record.html",
        record={"iri": record.iri, "name": record.name, "description": descriptions[0] if descriptions else None, "image": images[0] if images else None},
        fields=shown,
        named_on=named_on(record),
        names=records.names(links),
        page_title=f"{name} — VHP4Safety",
        meta_description=(descriptions[0] if descriptions else "")[:160] or f"{name}, a record of the VHP4Safety Virtual Human Platform.",
    )
