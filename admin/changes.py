"""The changes made on the platform, for editors. Each revision keeps the record as it was before and
after the change. A change is shown field by field, and as linked data: a diagram of the statements
about the record, with those the change added and removed."""

from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO

from database import records
from database.tables import Revision
from linkeddata import fields
from linkeddata.model import curie


def statements(document: str | None) -> Graph:
    graph = Graph()
    if document:
        graph.parse(data=document, format="json-ld")
    return graph


def edges(before: Graph, after: Graph, record: URIRef) -> dict:
    """The statements about a record before and after a change, as edges from the record to each value:
    added, removed, or kept. Each edge is named by the field of the record's form."""
    kind = after.value(record, RDF.type) or before.value(record, RDF.type)
    form = fields.of(str(kind)) if kind is not None else []
    labels = {}
    order = {}
    for position, field in enumerate(form):
        labels[field["iri"]] = field["label"]
        order[field["iri"]] = position
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
        found.append({
            "label": labels.get(str(predicate), curie(str(predicate))),
            "property": curie(str(predicate)),
            "value": value,
            "link": link,
            "status": status,
            "order": order.get(str(predicate), len(form)),
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
    changed = {}
    for edge in graph["edges"]:
        if edge["status"] == "kept":
            continue
        field = changed.setdefault(edge["label"], {"field": edge["label"], "order": edge["order"], "before": [], "after": []})
        field["before" if edge["status"] == "removed" else "after"].append(edge["value"])
    for edge in graph["edges"]:
        if edge["status"] == "kept" and edge["label"] in changed:
            changed[edge["label"]]["before"].append(edge["value"])
            changed[edge["label"]]["after"].append(edge["value"])
    return {
        "number": revision.id,
        "action": revision.action,
        "name": revision.name,
        "orcid": revision.orcid,
        "date": revision.created_at,
        "fields": sorted(changed.values(), key=lambda field: field["order"]),
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
