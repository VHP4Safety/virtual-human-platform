"""The fields of the records, as the application profile gives them: the property shapes of the node shape
of a class, with those of the shapes it builds on (sh:node), by their section (sh:group) and order. The
vocabularies' shapes only check values; the fields, their names and their order are the profile's."""

from functools import cache

from rdflib import URIRef
from rdflib.namespace import SH

from linkeddata import documents
from linkeddata.model import profile, settings


def shape_of(kind: str) -> URIRef | None:
    """The node shape of a class in the profile."""
    return profile().value(None, SH.targetClass, URIRef(kind))


@cache
def of(kind: str) -> list[dict]:
    """Each field of a class: its name in JSON-LD, property, label, whether it is required, whether a value
    that does not fit is only a warning (sh:Warning), the profile's message, the values the model fixes, whether its values are parts of the record that holds them (the values of a class without a
    kind of its own that fit its shape, sh:node, or nodes without an address, sh:nodeKind sh:BlankNode), and
    whether those parts have addresses of their own (sh:nodeKind sh:IRI)."""
    graph = profile()
    kinds = set(settings()["kinds"].values())
    shape = shape_of(kind)
    shapes = [shape] + list(graph.objects(shape, SH.node)) if shape is not None else []
    found = []
    for node in shapes:
        for field in graph.objects(node, SH.property):
            path = str(graph.value(field, SH.path))
            group = graph.value(field, SH.group)
            name = graph.value(field, SH.name)
            fixed = []
            for value in graph.objects(field, SH.hasValue):
                fixed.append(str(value))
            found.append({
                "name": documents.term(path),
                "iri": path,
                "label": str(name) if name is not None else documents.term(path),
                "required": graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) != SH.Warning,
                "warning": graph.value(field, SH.severity) == SH.Warning,
                "message": str(graph.value(field, SH.message) or ""),
                "fixed": fixed,
                "part": graph.value(field, SH.nodeKind) == SH.BlankNode or (
                    graph.value(field, SH.node) is not None and str(graph.value(field, SH["class"])) not in kinds),
                "addressed": graph.value(field, SH.nodeKind) == SH.IRI,
                "position": (int(graph.value(group, SH.order) or 0) if group is not None else 0, str(group or ""), int(graph.value(field, SH.order) or 0)),
            })
    found.sort(key=lambda field: field["position"])
    return found
