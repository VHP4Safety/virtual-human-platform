"""Changes made on the platform, for editors. Each revision keeps the record before and after; a change
is shown field by field, and as a diagram of the record's statements, with those added and removed."""

from operator import itemgetter

from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SDO

from database import records
from database.tables import Revision
from linkeddata import documents, fields


def statements(document: str | None) -> Graph:
    graph = Graph()
    if document:
        graph.parse(data=document, format="json-ld")
    return graph


def key(graph: Graph, value) -> str:
    """A value as compared: a link or a text ("X" and "X"^^xsd:string are the same), or a part (a node
    without an address) by the values it holds."""
    if not isinstance(value, BNode):
        return ("link " if isinstance(value, URIRef) else "text ") + str(value)
    held = []
    for predicate, given in graph.predicate_objects(value):
        held.append(f"{predicate} {key(graph, given)}")
    return "part " + " ".join(sorted(held))


def edge_order(edge: dict) -> tuple:
    """An edge's place: by its field's order, removed values first, then by value."""
    return edge["order"], edge["status"] != "removed", edge["value"]


def compared(before: Graph, after: Graph, old, new, kind: str | None) -> list[dict]:
    """The edges from a node to its values before (*old* in *before*) and after (*new* in *after*): added,
    removed or kept, each with its field's label. A part is shown with its own edges, compared in the same way."""
    form = fields.of(kind) if kind is not None else []
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
            "label": labels.get(str(predicate), documents.term(str(predicate))),
            "property": documents.term(str(predicate)),
            "value": str(value),
            "link": isinstance(value, URIRef),
            "status": status,
            "order": order.get(str(predicate), len(form)),
        }
        if isinstance(value, BNode) or str(value).startswith(f"{old or new}/"):
            part = graph.value(value, RDF.type)
            edge["value"] = str(graph.value(value, SDO.name) or "")
            edge["type"] = documents.term(str(part)) if part is not None else ""
            edge["link"] = False
            if isinstance(value, BNode):
                edge["parts"] = compared(graph, graph, value if status != "added" else None, value if status != "removed" else None, str(part) if part is not None else None)
            else:
                edge["parts"] = compared(before, after, value if (value, None, None) in before else None, value if (value, None, None) in after else None, str(part) if part is not None else None)
        edges.append(edge)
    edges.sort(key=edge_order)
    return edges


def linked(edges: list[dict]) -> list[str]:
    """The addresses that some edges and their parts link to."""
    found = []
    for edge in edges:
        if edge["link"]:
            found.append(edge["value"])
        found.extend(linked(edge.get("parts", [])))
    return found


def named(edges: list[dict], names: dict[str, str]) -> None:
    for edge in edges:
        edge["name"] = names.get(edge["value"]) if edge["link"] else None
        named(edge.get("parts", []), names)


def edges(before: Graph, after: Graph, record: URIRef) -> dict:
    """The statements about a record before and after a change, as edges from the record to each value."""
    kind = after.value(record, RDF.type) or before.value(record, RDF.type)
    found = compared(before, after, record, record, str(kind) if kind is not None else None)
    names = records.names(linked(found) + [str(record)])
    named(found, names)
    name = after.value(record, SDO.name) or before.value(record, SDO.name) or names.get(str(record))
    return {
        "record": str(record),
        "record_name": str(name or record),
        "type": documents.term(str(kind)) if kind is not None else "",
        "edges": found,
    }


def triples(graph: Graph) -> list[str]:
    lines = []
    for line in graph.serialize(format="nt").splitlines():
        if line.strip():
            lines.append(line)
    return sorted(lines)


def compare(revision: Revision) -> dict:
    """What a revision changed: each field's values before and after, and the statements added and removed."""
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
        "fields": sorted(changed.values(), key=itemgetter("order")),
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
