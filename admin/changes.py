"""Comparison of a record before and after a change, for the change pages and the editor preview."""

from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SDO

from database import records
from linkeddata.profile import fields, jsonld_name


def statements(document: str | None) -> Graph:
    graph = Graph()
    if document:
        graph.parse(data=document, format="json-ld")
    return graph


def key(graph: Graph, value, within: frozenset = frozenset()) -> str:
    """Return the comparison key of a value in graph."""
    if not isinstance(value, BNode) and not (within and value not in within and records.is_part(graph, value)):
        return ("link " if isinstance(value, URIRef) else "text ") + str(value)
    held = []
    for predicate, given in graph.predicate_objects(value):
        held.append(f"{predicate} {key(graph, given, within | {value})}")
    return "part " + ("" if isinstance(value, BNode) else str(value) + " ") + " ".join(sorted(held))


def compared(before: Graph, after: Graph, old, new, kind: str | None, names: dict[str, str]) -> list[dict]:
    """Return the edges from a node to its values, each marked as added, removed or kept."""
    form = fields(kind) if kind is not None else []
    labels = {}
    order = {}
    for position, field in enumerate(form):
        labels[field["iri"]] = field["label"]
        order[field["iri"]] = position
    values = {}
    for graph, node, status in ((before, old, "removed"), (after, new, "added")):
        if node is None:
            continue
        for predicate, value in graph.predicate_objects(node):
            if predicate != RDF.type:
                found = (predicate, key(graph, value))
                values[found] = ("kept" if found in values else status, graph, value)
    edges = []
    for (predicate, _), (status, graph, value) in values.items():
        edge = {
            "label": labels.get(str(predicate), jsonld_name(str(predicate))),
            "property": jsonld_name(str(predicate)),
            "value": str(value),
            "link": isinstance(value, URIRef),
            "status": status,
            "order": order.get(str(predicate), len(form)),
        }
        if records.is_part(graph, value) or str(value).startswith(f"{old or new}/"):
            part = graph.value(value, RDF.type)
            edge["value"] = str(graph.value(value, SDO.name) or "")
            edge["type"] = jsonld_name(str(part)) if part is not None else ""
            edge["link"] = False
            if isinstance(value, BNode):
                edge["parts"] = compared(graph, graph, value if status != "added" else None, value if status != "removed" else None, str(part) if part is not None else None, names)
            else:
                edge["parts"] = compared(before, after, value if (value, None, None) in before else None, value if (value, None, None) in after else None, str(part) if part is not None else None, names)
        edge["name"] = names.get(edge["value"]) if edge["link"] else None
        edges.append(edge)
    # The edges are sorted by field, with the removed values first.
    edges.sort(key=lambda edge: (edge["order"], edge["status"] != "removed", edge["value"]))
    return edges


def edges(before: Graph, after: Graph, record: URIRef) -> dict:
    """Return the statements of a record before and after a change, as edges."""
    kind = records.class_of(after, record) or records.class_of(before, record) or None
    linked = [str(record)]
    for value in set(before.objects()) | set(after.objects()):
        if isinstance(value, URIRef):
            linked.append(str(value))
    names = records.names(linked)
    found = compared(before, after, record, record, str(kind) if kind is not None else None, names)
    name = after.value(record, SDO.name) or before.value(record, SDO.name) or names.get(str(record))
    return {
        "record": str(record),
        "record_name": str(name or record),
        "type": jsonld_name(str(kind)) if kind is not None else "",
        "edges": found,
    }
