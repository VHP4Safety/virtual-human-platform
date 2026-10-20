"""Pages of the record editor, and the data quality page. Make the forms with shacl-form from the shapes of the
model, and write the records through the records API."""

import json

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for

from admin import editor, writes
from database import records
from database.tables import PLATFORM
from linkeddata import checks, crates, pages
from linkeddata.profile import settings, shape_of
from routes.account import current_editor, form_token

blueprint = Blueprint("admin", __name__)


@blueprint.context_processor
def named_kinds() -> dict:
    """Give the names of the kinds of records to the pages of the editor, such as "Case Studies"."""
    return {"kind_names": pages.kind_names}


def logged_in(kind: str | None = None):
    """Return the editor of the request. Return a 404 error if records of *kind* may not be written by the editor."""
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
    """Show the data quality page to editors."""
    if logged_in() is None:
        return redirect(url_for("account.login", next=request.path))
    return render_template("records/quality.html", **checks.report(), written=PLATFORM, page_title="Data quality — VHP4Safety editor")


@blueprint.get("/admin/<kind>/")
def edit(kind: str):
    if logged_in(kind) is None:
        return redirect(url_for("account.login", next=request.path))
    listed = editor.listing(kind)
    selected = request.args.get("record") or ""
    # The address of a new record is made from its name, as in the API.
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
        shape=str(shape_of(record.type)) if record is not None else editor.root_shape(kind),
        values=f"<{selected}> a <{settings()['kinds'][kind]}> ; <https://schema.org/name> {json.dumps(name)} ." if name and record is None else "",
        links=editor.links(),
        mixed=editor.mixed(),
        ordered=editor.ordered(),
        classes={of_class: name for name, of_class in settings()["kinds"].items()},
        form_token=form_token(),
        # A model has the RO-Crate in Zenodo while it is an imported record, and else a draft crate.
        crate=("zenodo" if crates.zenodo(record) is not None else "draft") if crates.of_models(record) else None,
        draft_vocabulary=editor.draft_vocabulary(record),
        page_title=f"{pages.kind_names()[kind]} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@blueprint.get("/admin/form.ttl")
def form():
    """Return the graph for the forms: the profile with the names of the records and the listed terms."""
    if logged_in() is None:
        abort(401)
    return Response(editor.form_graph().serialize(format="turtle"), mimetype="text/turtle")
