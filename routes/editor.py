"""The pages of the record editor are served here. The forms are made by shacl-form from the shapes of the model,
and the records are written through the records API. The data quality page and the sources page are served here too."""

import json

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for
from sqlalchemy import func, select

import database
from admin import editor, writes
from database import records
from database.tables import PLATFORM, Note, Record, Source
from linkeddata import checks, pages
from linkeddata.imports import files_of, specs
from linkeddata.profile import settings, shape_of
from routes.account import current_editor, form_token

blueprint = Blueprint("admin", __name__)


@blueprint.context_processor
def named_kinds() -> dict:
    """The names of the kinds of records are given to the pages of the editor, such as "Case Studies"."""
    return {"kind_names": pages.kind_names}
sources_blueprint = Blueprint("sources", __name__)


def logged_in(kind: str | None = None):
    """The editor of the request is given here. A 404 error is given when the editor may not write records of *kind*."""
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
    """The data quality page is served here to editors."""
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
        shape=str(shape_of(record.type)) if record is not None else editor.root_shape(kind),
        values=f"<{selected}> a <{settings()['kinds'][kind]}> ; <https://schema.org/name> {json.dumps(name)} ." if name and record is None else "",
        links=editor.links(),
        mixed=editor.mixed(),
        ordered=editor.ordered(),
        classes={of_class: name for name, of_class in settings()["kinds"].items()},
        form_token=form_token(),
        page_title=f"{pages.kind_names()[kind]} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@blueprint.get("/admin/form.ttl")
def form():
    """The graph for the forms is served here. The profile is given with the names of the records and the listed terms."""
    if logged_in() is None:
        abort(401)
    return Response(editor.form_graph().serialize(format="turtle"), mimetype="text/turtle")


@sources_blueprint.get("/sources")
def sources():
    """The sources are listed with their files, the last import, and the counts of their records and notes."""
    with database.session() as db:
        fetched = {source.name: source for source in db.scalars(select(Source))}
        counts = dict(db.execute(select(Record.source, func.count()).where(Record.removed_at.is_(None)).group_by(Record.source)).all())
        noted = dict(db.execute(select(Note.source, func.count()).group_by(Note.source)).all())
    found = []
    for spec in specs():
        found.append({
            "name": spec["name"],
            "title": spec.get("title", spec["name"]),
            "files": files_of(spec),
            "parser": spec["module"].replace(".", "/") + ".py",
            "fetched": fetched.get(spec["name"]),
            "records": counts.get(spec["name"], 0),
            "notes": noted.get(spec["name"], 0),
        })
    return render_template(
        "records/sources.html",
        sources=found,
        written=counts.get(PLATFORM, 0),
        page_title="Sources — VHP4Safety",
        meta_description="The sources of the records of the VHP4Safety platform, and how each source is read into the model.",
    )
