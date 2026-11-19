"""Serve the record editor pages."""

import json

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for
from rdflib.namespace import SDO

from admin import drafts, editor, writes
from database import records
from linkeddata import crates, documents, pages
from linkeddata.profile import settings, shape_of
from routes.account import current_editor, form_token

blueprint = Blueprint("admin", __name__)


@blueprint.context_processor
def named_kinds() -> dict:
    """Return the names of the kinds of records for the editor pages."""
    return {"kind_names": pages.kind_names}


def logged_in(kind: str | None = None):
    """Return the editor of the request, or abort with 404 if kind may not be written."""
    found = current_editor()
    if found is not None and kind is not None and (kind not in settings()["kinds"] or kind not in found.kinds):
        abort(404)
    return found


@blueprint.get("/admin/")
def admin():
    found = logged_in()
    if found is None:
        return redirect(url_for("account.login", next=request.path))
    # The kinds that the editor may write are listed, such as tools only for a token of tools.
    kinds = [counted for counted in editor.counts() if counted["kind"] in found.kinds]
    return render_template("admin/kinds.html", kinds=kinds, failed=editor.failed(), page_title="VHP4Safety editor")


@blueprint.get("/admin/<kind>/")
def edit(kind: str):
    found = logged_in(kind)
    if found is None:
        return redirect(url_for("account.login", next=request.path))
    selected = request.args.get("record") or ""
    # The address of a new record is made from its name, as in the API.
    name = request.args.get("new", "").strip()
    if name:
        selected = writes.free(records.address(f"{kind}/{writes.slug(name)}"), set())
    record = records.get(selected) if selected else None
    # A record is edited with the kind of its class, and with the rights of that kind.
    of_kind = next((other for other, of_class in settings()["kinds"].items() if record is not None and record.type in records.within(of_class)), kind)
    if of_kind != kind:
        return redirect(url_for("admin.edit", kind=of_kind, record=selected))
    listed = editor.listing(kind)
    values = f"<{selected}> a <{settings()['kinds'][kind]}> ; <https://schema.org/name> {json.dumps(name)} ." if name and record is None else ""
    draft_vocabulary = editor.draft_vocabulary(record)
    # A new term is a draft term of the glossary, until another vocabulary is chosen.
    glossary = drafts.vocabulary(drafts.GLOSSARY) if values and settings()["kinds"][kind] == str(SDO.DefinedTerm) else None
    if glossary is not None:
        values = values[:-1] + f'; <{SDO.inDefinedTermSet}> <{glossary}> ; <{SDO.creativeWorkStatus}> "Draft" .'
        draft_vocabulary = drafts.GLOSSARY
    response = Response(render_template(
        "admin/records.html",
        kind=kind,
        kinds=[other for other in settings()["kinds"] if other in found.kinds],
        records=listed,
        selected=selected,
        base=settings()["base"],
        record=record,
        shape=str(shape_of(record.type)) if record is not None else editor.root_shape(kind),
        values=values,
        links=editor.links(),
        mixed=editor.mixed(),
        ordered=editor.ordered(),
        long=editor.long_texts(records.latest_change()),
        classes={of_class: name for name, of_class in settings()["kinds"].items()},
        form_token=form_token(),
        # A model has the RO-Crate in Zenodo while it is an imported record, and else a draft crate.
        crate=("zenodo" if crates.zenodo(record) is not None else "draft") if crates.of_models(record) else None,
        read_only=record is not None and kind in settings()["read only in the editor"],
        draft_vocabulary=draft_vocabulary,
        draft_table=editor.draft_table(record),
        person=drafts.person(found.orcid),
        context=documents.context(settings()),
        page_title=f"{pages.kind_names()[kind]} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@blueprint.get("/admin/form.ttl")
def form():
    """Return the graph of the shapes, records and terms for the forms."""
    if logged_in() is None:
        abort(401)
    return Response(editor.form_graph().serialize(format="turtle"), mimetype="text/turtle")
