"""The record editor: every kind of record, and for each a list of its records and a form that shacl-form
builds from the model's shapes, which writes and removes records through the records API with the
editor's login."""

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for

from admin import editor
from database import records
from database.tables import PLATFORM
from linkeddata import quality
from linkeddata.model import settings
from routes.account import current_editor, form_token

blueprint = Blueprint("admin", __name__)


def logged_in(kind: str | None = None):
    """The editor who makes the request; one who may not write records of *kind* gets 404."""
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
    """How complete the records are, and what the checks of the imports and of the written records found."""
    if logged_in() is None:
        return redirect(url_for("account.login", next=request.path))
    return render_template("records/quality.html", **quality.report(), written=PLATFORM, page_title="Data quality — VHP4Safety editor")


@blueprint.get("/admin/<kind>/")
def edit(kind: str):
    if logged_in(kind) is None:
        return redirect(url_for("account.login", next=request.path))
    listed = editor.listing(kind)
    selected = request.args.get("record") or ""
    if request.args.get("new"):
        selected = records.address(f"{kind}/{request.args['new']}")
    record = records.get(selected) if selected else None
    response = Response(render_template(
        "admin/records.html",
        kind=kind,
        kinds=list(settings()["kinds"]),
        records=listed,
        selected=selected,
        base=settings()["base"],
        record=record,
        shape=editor.root_shape(kind),
        form_token=form_token(),
        page_title=f"{kind.capitalize()} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@blueprint.get("/admin/form.ttl")
def form():
    """The graph from which the forms are built: the profile and the names of the terms its fields list."""
    if logged_in() is None:
        abort(401)
    return Response(editor.form_graph().serialize(format="turtle"), mimetype="text/turtle")


@blueprint.get("/admin/linkable")
def linkable():
    """The records that a field can link to, for each node shape (shape=...), as shacl-form's link provider
    asks for them; with record=..., those records with their class and name."""
    if logged_in() is None:
        abort(401)
    if request.args.getlist("record"):
        return jsonify(editor.resources(request.args.getlist("record")))
    return jsonify(editor.linkable(request.args.getlist("shape")))
