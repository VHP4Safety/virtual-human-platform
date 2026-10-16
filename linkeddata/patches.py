"""Stand-ins for calls that rdfsolve does not have yet. Each has the name and the signature that its
rdfsolve proposal gives the call, and is called where the platform calls rdfsolve once rdfsolve has it;
then the stand-in goes, and its caller calls rdfsolve."""

from dataclasses import dataclass, field

from rdflib import RDF, BNode, Graph, URIRef
from rdfsolve.client.sql_tables import layout


@dataclass
class Merged:
    """A record with the statements of another source merged into it: the statements that were added, and
    the values that the record kept where the other source gives another (subject, property, kept, offered)."""

    graph: Graph
    added: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)


def key(graph: Graph, node) -> str:
    """A value as merging compares it: a node without an address by the values that it holds."""
    if not isinstance(node, BNode):
        return str(node)
    held = []
    for predicate, value in graph.predicate_objects(node):
        held.append(str(predicate) + " " + key(graph, value))
    held.sort()
    return "part " + " ".join(held)


def described(graph: Graph, node: BNode) -> list:
    """The statements of a node without an address, and of the nodes without an address that it holds."""
    found = []
    nodes = [node]
    seen = set()
    while nodes:
        current = nodes.pop()
        if current in seen:
            continue
        seen.add(current)
        for statement in graph.triples((current, None, None)):
            found.append(statement)
            if isinstance(statement[2], BNode):
                nodes.append(statement[2])
    return found


# rdfsolve proposal P5: rdfsolve.client.sql_tables.merge(current, added, profile) -> Merged
def merge(current: Graph, added: Graph, profile) -> Merged:
    """*current* with the statements of *added* about its subjects that have an address. A field that takes
    one value (sh:maxCount 1 in *profile*) keeps the value it has, and a different value is a conflict; a part
    that *current* holds with the same values is not added again, so that merging twice adds nothing."""
    classes = layout(profile).classes
    merged = Merged(Graph())
    merged.graph += current
    parts = set()
    for subject, predicate, value in current:
        if isinstance(value, BNode):
            parts.add((subject, predicate, key(current, value)))
    for subject, predicate, value in sorted(added):
        if not isinstance(subject, URIRef) or (predicate == RDF.type and (subject, RDF.type, None) in current):
            continue
        if isinstance(value, BNode):
            if (subject, predicate, key(added, value)) not in parts:
                for statement in [(subject, predicate, value)] + described(added, value):
                    merged.graph.add(statement)
                    merged.added.append(statement)
            continue
        of_class = str(current.value(subject, RDF.type) or added.value(subject, RDF.type))
        given = list(current.objects(subject, predicate))
        if of_class in classes and str(predicate) in classes[of_class].single and given:
            if value not in given:
                merged.conflicts.append((str(subject), str(predicate), str(given[0]), str(value)))
            continue
        if (subject, predicate, value) not in merged.graph:
            merged.graph.add((subject, predicate, value))
            merged.added.append((subject, predicate, value))
    return merged
