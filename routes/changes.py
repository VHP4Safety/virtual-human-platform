"""Pages of the changes made on the platform."""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from rdflib import URIRef
from sqlalchemy import select

import database
from admin.changes import edges, statements
from database import records
from database.tables import Revision
from routes.account import current_editor

blueprint = Blueprint("changes", __name__)


@blueprint.before_request
def editors_only():
    if current_editor() is None:
        return redirect(url_for("account.login", next=request.full_path.rstrip("?")))
    return None


@blueprint.get("/changes")
def changes():
    statement = select(Revision).order_by(Revision.id.desc()).limit(100)
    record = request.args.get("record")
    if record:
        statement = statement.where(Revision.record_iri.in_([record, *records.earlier_addresses(record)]))
    with database.session() as db:
        found = list(db.scalars(statement))
    names = records.names([revision.record_iri for revision in found])
    return render_template("changes/changes.html", changes=found, record=record, names=names, page_title="Changes — VHP4Safety editor")


@blueprint.get("/changes/<int:number>")
def change(number: int):
    with database.session() as db:
        revision = db.get(Revision, number)
    if revision is None:
        abort(404)
    graph = edges(statements(revision.previous), statements(revision.document), URIRef(revision.record_iri))
    return render_template("changes/change.html", change=revision, graph=graph, page_title=f"Change {number} — VHP4Safety editor")
