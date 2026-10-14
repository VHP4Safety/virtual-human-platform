"""The changes made on the platform. Each revision keeps the record as it was before and after the
change; a change is shown field by field, and, for developers, as the statements (triples) it added
and removed. /changes lists them, /changes/<number> shows one, and /changes/<number>.json gives it
to the editor page."""

from flask import Blueprint, abort, jsonify, render_template, request
from rdflib import RDF, Graph, URIRef
from sqlalchemy import select

from linkeddata import database, forms, rdf, records
from linkeddata.database import Revision

blueprint = Blueprint("changes", __name__)
LISTED = 100


def statements(document: str | None) -> Graph:
    graph = Graph()
    if document:
        graph.parse(data=document, format="json-ld")
    return graph


def triples(graph: Graph) -> list[str]:
    lines = []
    for line in graph.serialize(format="nt").splitlines():
        if line.strip():
            lines.append(line)
    return sorted(lines)


def compare(revision: Revision) -> dict:
    """What a revision changed: the values of each field before and after, and the triples it added and removed."""
    before = statements(revision.previous)
    after = statements(revision.document)
    record = URIRef(revision.record_iri)
    kind = after.value(record, RDF.type) or before.value(record, RDF.type)
    form = forms.form(str(kind)) if kind is not None else []
    fields = []
    for predicate in set(before.predicates(record)) | set(after.predicates(record)):
        if predicate == RDF.type:
            continue
        old = sorted(str(value) for value in before.objects(record, predicate))
        new = sorted(str(value) for value in after.objects(record, predicate))
        if old == new:
            continue
        name = rdf.field_of_property(str(kind), str(predicate)) if kind is not None else str(predicate)
        found = {"field": str(predicate), "entry": "text", "order": len(form), "before": old, "after": new}
        for position, field in enumerate(form):
            if field["name"] == name:
                found.update({"field": field["label"], "entry": field["entry"], "order": position})
        fields.append(found)
    fields.sort(key=lambda found: found["order"])
    return {
        "number": revision.id,
        "record": revision.record_iri,
        "action": revision.action,
        "name": revision.name,
        "orcid": revision.orcid,
        "date": revision.created_at,
        "fields": fields,
        "added": triples(after - before),
        "removed": triples(before - after),
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
        statement = statement.where(Revision.record_iri == record)
    with database.session() as db:
        found = [compare(revision) for revision in db.scalars(statement)]
    return render_template(
        "changes/changes.html",
        changes=found,
        record=record,
        names=link_names(found),
        page_title="Changes — VHP4Safety",
        meta_description="The changes made to the records of the VHP4Safety platform, by whom and when.",
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
        page_title=f"Change {number} — VHP4Safety",
        meta_description=f"{found['action']} {found['record']} by {found['name']}.",
    )


@blueprint.get("/changes/<int:number>.json")
def change_data(number: int):
    return jsonify(compare(revision_or_404(number)))
