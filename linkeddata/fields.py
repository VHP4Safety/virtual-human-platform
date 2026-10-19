"""Record fields as the application profile gives them: the property shapes of a class's node shape and of
the shapes it builds on (sh:node), by section (sh:group) and order. The vocabularies' shapes only check values."""

from functools import cache
from operator import itemgetter

from rdflib import RDFS, Literal, URIRef
from rdflib.namespace import SH

from linkeddata import documents
from linkeddata.model import profile, settings


def shape_of(kind: str) -> URIRef | None:
    """The node shape of a class in the profile."""
    return profile().value(None, SH.targetClass, URIRef(kind))


@cache
def of(kind: str) -> list[dict]:
    """Each field of a class:
    - name (in JSON-LD), iri, label, description and message;
    - single (sh:maxCount 1), required, and warning or recommended (sh:Warning);
    - values (sh:in), classes (sh:class, sh:or), datatype, address (web addresses), pattern and fixed
      (sh:hasValue); iris when the values are IRIs, not literals or nodes without an address;
    - part when the values are parts of the record (sh:node of a class without a kind, or sh:nodeKind
      sh:BlankNode), and addressed when parts have addresses (sh:nodeKind sh:IRI);
    - position: section and order, and section, the label of the field's section (sh:group)."""
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
            values = []
            iris = graph.value(field, SH.nodeKind) == SH.IRI
            for listed in graph.objects(field, SH["in"]):
                for value in graph.items(listed):
                    values.append(str(value))
                    iris = iris or isinstance(value, URIRef)
            classes = []
            for of_class in graph.objects(field, SH["class"]):
                classes.append(str(of_class))
            for alternatives in graph.objects(field, SH["or"]):
                for alternative in graph.items(alternatives):
                    for of_class in graph.objects(alternative, SH["class"]):
                        classes.append(str(of_class))
            found.append({
                "name": documents.term(path),
                "iri": path,
                "label": str(name) if name is not None else documents.term(path),
                "description": str(graph.value(field, SH.description) or ""),
                "single": graph.value(field, SH.maxCount) == Literal(1),
                "values": values,
                "classes": classes,
                "datatype": str(graph.value(field, SH.datatype) or ""),
                "address": graph.value(field, SH.nodeKind) == SH.IRI,
                "iris": iris or (bool(classes) and graph.value(field, SH.nodeKind) != SH.BlankNode),
                "pattern": str(graph.value(field, SH.pattern) or ""),
                "required": graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) != SH.Warning,
                "warning": graph.value(field, SH.severity) == SH.Warning,
                "recommended": graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) == SH.Warning,
                "message": str(graph.value(field, SH.message) or ""),
                "fixed": fixed,
                "part": graph.value(field, SH.nodeKind) == SH.BlankNode or (
                    graph.value(field, SH.node) is not None and str(graph.value(field, SH["class"])) not in kinds),
                "addressed": graph.value(field, SH.nodeKind) == SH.IRI,
                "position": (int(graph.value(group, SH.order) or 0) if group is not None else 0, str(group or ""), int(graph.value(field, SH.order) or 0)),
                "section": str(graph.value(group, RDFS.label) or "") if group is not None else "",
            })
    found.sort(key=itemgetter("position"))
    return found
