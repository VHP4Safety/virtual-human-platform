"""The record editor: per kind, a list of records and a form built by shacl-form from the model's shapes,
which writes through the records API with the editor's login."""

import json

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for

from admin import editor, writes
from database import records
from database.tables import PLATFORM
from linkeddata import checks, fields
from linkeddata.model import settings
from routes.account import current_editor, form_token

blueprint = Blueprint("admin", __name__)


def logged_in(kind: str | None = None):
    """The requesting editor; 404 for one not allowed to write *kind*."""
    found = current_editor()
    if found is not None and kind is not None and (kind not in settings()["kinds"] or kind not in found.kinds):
        abort(404)
    return found


@blueprint.get("/admin/")
def admin():
    if logged_in() is None:
        return redirect(url_for("account.login", next=request.path))
    return render_template("admin/kinds.html", kinds=editor.counts(), page_title="VHP4Safety editor")


@blueprint.get("/admin/quality")
def data_quality():
    """Record completeness, and the checks' notes on imported and written records."""
    if logged_in() is None:
        return redirect(url_for("account.login", next=request.path))
    return render_template("records/quality.html", **checks.report(), written=PLATFORM, page_title="Data quality — VHP4Safety editor")


@blueprint.get("/admin/<kind>/")
def edit(kind: str):
    if logged_in(kind) is None:
        return redirect(url_for("account.login", next=request.path))
    listed = editor.listing(kind)
    selected = request.args.get("record") or ""
    # A new record's address is made from its name, as in the API.
    name = request.args.get("new", "").strip()
    if name:
        selected = writes.free(records.address(f"{kind}/{writes.slug(name)}"), set())
    record = records.get(selected) if selected else None
    response = Response(render_template(
        "admin/records.html",
        kind=kind,
        kinds=list(settings()["kinds"]),
        records=listed,
        selected=selected,
        base=settings()["base"],
        record=record,
        shape=str(fields.shape_of(record.type)) if record is not None else editor.root_shape(kind),
        values=f"<{selected}> a <{settings()['kinds'][kind]}> ; <https://schema.org/name> {json.dumps(name)} ." if name and record is None else "",
        links=editor.links(),
        mixed=editor.mixed(),
        classes={of_class: name for name, of_class in settings()["kinds"].items()},
        form_token=form_token(),
        page_title=f"{kind.capitalize()} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@blueprint.get("/admin/form.ttl")
def form():
    """The graph the forms are built from: the profile, with the names of records and listed terms."""
    if logged_in() is None:
        abort(401)
    return Response(editor.form_graph().serialize(format="turtle"), mimetype="text/turtle")



