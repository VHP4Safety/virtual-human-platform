"""The changes made on the platform, for editors. Each revision keeps the record as it was before and
after the change. A change is shown field by field, and as linked data: a diagram of the statements
about the record, with those the change added and removed.

    /changes                      the latest changes, or those of one record (?record=<address>)
    /changes/<number>             one change
    /changes/<number>.json        one change, for the record editor and programs
    /changes/<number>.nt          the statements it added and removed, in N-Triples
    /changes/record.json?record=  the statements about a record as it is now, for the record editor
"""

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO
from sqlalchemy import select

from linkeddata import accounts, database, forms, rdf, records, tokens
from linkeddata.database import Revision
from linkeddata.model import curie

blueprint = Blueprint("changes", __name__)
LISTED = 100


def allowed() -> bool:
    """Editors see the changes, logged in or with a write token."""
    if accounts.current_editor() is not None:
        return True
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = tokens.find(header.removeprefix("Bearer ").strip())
        return token is not None and token.orcid in accounts.editors()
    return False


@blueprint.before_request
def editors_only():
    if allowed():
        return None
    if request.path.endswith((".json", ".nt")):
        return jsonify({"error": "The changes are shown to editors of the platform."}), 401
    return redirect(url_for("account.login", next=request.full_path.rstrip("?")))


def statements(document: str | None) -> Graph:
    graph = Graph()
    if document:
        graph.parse(data=document, format="json-ld")
    return graph


def edges(before: Graph, after: Graph, record: URIRef) -> dict:
    """The statements about a record before and after a change, as edges from the record to each value:
    added, removed, or kept. Each edge is named by the field of the record's form."""
    kind = after.value(record, RDF.type) or before.value(record, RDF.type)
    form = forms.form(str(kind)) if kind is not None else []
    labels = {}
    entries = {}
    order = {}
    for position, field in enumerate(form):
        labels[field["name"]] = field["label"]
        entries[field["name"]] = field["entry"]
        order[field["name"]] = position
    # A value is compared as a link or a text, so that "X" and "X"^^xsd:string are the same value.
    old = set()
    for predicate, value in before.predicate_objects(record):
        old.add((predicate, isinstance(value, URIRef), str(value)))
    new = set()
    for predicate, value in after.predicate_objects(record):
        new.add((predicate, isinstance(value, URIRef), str(value)))
    found = []
    for predicate, link, value in old | new:
        if predicate == RDF.type:
            continue
        status = "kept" if (predicate, link, value) in old and (predicate, link, value) in new else ("added" if (predicate, link, value) in new else "removed")
        field = rdf.field_of_property(str(kind), str(predicate)) if kind is not None else str(predicate)
        found.append({
            "label": labels.get(field, curie(str(predicate))),
            "property": curie(str(predicate)),
            "value": value,
            "link": link,
            "entry": entries.get(field, "text"),
            "status": status,
            "order": order.get(field, len(form)),
        })
    found.sort(key=lambda edge: (edge["order"], edge["status"] != "removed", edge["value"]))
    values = [edge["value"] for edge in found if edge["link"]]
    names = records.names(values + [str(record)])
    for edge in found:
        edge["name"] = names.get(edge["value"]) if edge["link"] else None
    name = after.value(record, SDO.name) or before.value(record, SDO.name) or names.get(str(record))
    return {
        "record": str(record),
        "record_name": str(name or record),
        "type": curie(str(kind)) if kind is not None else "",
        "edges": found,
    }


def triples(graph: Graph) -> list[str]:
    lines = []
    for line in graph.serialize(format="nt").splitlines():
        if line.strip():
            lines.append(line)
    return sorted(lines)


def compare(revision: Revision) -> dict:
    """What a revision changed: the values of each field before and after, and the statements it added and removed."""
    before = statements(revision.previous)
    after = statements(revision.document)
    record = URIRef(revision.record_iri)
    graph = edges(before, after, record)
    fields = {}
    for edge in graph["edges"]:
        if edge["status"] == "kept":
            continue
        field = fields.setdefault(edge["label"], {"field": edge["label"], "order": edge["order"], "entry": edge["entry"], "before": [], "after": []})
        field["before" if edge["status"] == "removed" else "after"].append(edge["value"])
    for edge in graph["edges"]:
        if edge["status"] == "kept" and edge["label"] in fields:
            fields[edge["label"]]["before"].append(edge["value"])
            fields[edge["label"]]["after"].append(edge["value"])
    return {
        "number": revision.id,
        "action": revision.action,
        "name": revision.name,
        "orcid": revision.orcid,
        "date": revision.created_at,
        "fields": sorted(fields.values(), key=lambda field: field["order"]),
        "added": triples(after - before),
        "removed": triples(before - after),
        **graph,
    }


def link_names(changes: list[dict]) -> dict[str, str]:
    values = []
    for change in changes:
        for field in change["fields"]:
            values.extend(field["before"] + field["after"])
        values.append(change["record"])
    return records.names(values)


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
    """The statements about a record as it is now, all kept, in the form of a change."""
    document = records.document_of(request.args.get("record", ""))
    if document is None:
        abort(404)
    now = statements(document)
    return jsonify(edges(now, now, URIRef(request.args["record"])))
