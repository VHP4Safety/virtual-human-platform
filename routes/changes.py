"""The changes made on the platform, for editors.

    /changes                      the latest changes, or those of one record (?record=<address>)
    /changes/<number>             one change
    /changes/<number>.json        one change, for the record editor and programs
    /changes/<number>.nt          the statements it added and removed, in N-Triples
    /changes/record.json?record=  a record's current statements, for the record editor
"""

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for
from rdflib import URIRef
from sqlalchemy import select

import database
from admin import accounts, tokens
from admin.changes import compare, edges, link_names, statements
from database import records
from database.tables import Revision
from linkeddata import documents
from routes.account import current_editor

blueprint = Blueprint("changes", __name__)
LISTED = 100


def allowed() -> bool:
    """Editors see the changes, logged in or with a write token."""
    if current_editor() is not None:
        return True
    token = tokens.find(tokens.bearer(request.headers.get("Authorization", "")))
    return token is not None and token.orcid in accounts.editors()


@blueprint.before_request
def editors_only():
    if allowed():
        return None
    if request.path.endswith((".json", ".nt")):
        return jsonify({"error": "Editors only."}), 401
    return redirect(url_for("account.login", next=request.full_path.rstrip("?")))


@blueprint.get("/changes")
def changes():
    statement = select(Revision).order_by(Revision.id.desc()).limit(LISTED)
    record = request.args.get("record")
    if record:
        statement = statement.where(Revision.record_iri.in_([record, *records.earlier_addresses(record)]))
    with database.session() as db:
        found = [compare(revision) for revision in db.scalars(statement)]
    return render_template(
        "changes/changes.html",
        changes=found,
        record=record,
        names=link_names(found),
        page_title="Changes — VHP4Safety editor",
    )


def revision_or_404(number: int) -> Revision:
    with database.session() as db:
        revision = db.get(Revision, number)
    if revision is None:
        abort(404)
    return revision


@blueprint.get("/changes/<int:number>")
def change(number: int):
    found = compare(revision_or_404(number))
    return render_template(
        "changes/change.html",
        change=found,
        names=link_names([found]),
        page_title=f"Change {number} — VHP4Safety editor",
    )


@blueprint.get("/changes/<int:number>.json")
def change_data(number: int):
    return jsonify(compare(revision_or_404(number)))


@blueprint.get("/changes/<int:number>.nt")
def change_statements(number: int):
    found = compare(revision_or_404(number))
    lines = ["# Added"] + found["added"] + ["", "# Removed"] + found["removed"]
    return Response("\n".join(lines) + "\n", mimetype="application/n-triples")


@blueprint.get("/changes/record.json")
def record_data():
    """A record's current statements, as a change that keeps them all."""
    document = documents.document_of(request.args.get("record", ""))
    if document is None:
        abort(404)
    now = statements(document)
    return jsonify(edges(now, now, URIRef(request.args["record"])))
