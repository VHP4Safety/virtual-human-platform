"""The fields of a class, read from the model's shapes: the application profile's names, sections (sh:group)
and order first, then the fields that only the vocabularies give, by name."""

import re
from functools import cache

from rdflib.namespace import SH

from linkeddata import documents
from linkeddata.model import profile, property_shapes, shapes


def first(nodes: list, predicate):
    """The first value of a predicate in some shapes."""
    for node in nodes:
        found = shapes().value(node, predicate)
        if found is not None:
            return found
    return None


@cache
def of(kind: str) -> list[dict]:
    """Each field of a class: its name in JSON-LD, property, label, whether it is required, and the values
    the model fixes."""
    every = shapes()
    in_profile = property_shapes(profile(), kind)
    found = []
    for iri, nodes in property_shapes(every, kind).items():
        # The profile's shape comes first, so that its names are read before those of the vocabularies.
        nodes = in_profile.get(iri, []) + nodes
        group = first(nodes, SH.group)
        order = first(nodes, SH.order)
        local = re.split(r"[/#]", iri)[-1]
        name = first(nodes, SH.name)
        fixed = []
        for node in nodes:
            for value in every.objects(node, SH.hasValue):
                fixed.append(str(value))
        found.append({
            "name": documents.term(iri),
            "iri": iri,
            # A property of the vocabularies is named in words: "conformsTo" is "Conforms to".
            "label": str(name) if name is not None and str(name) != local else re.sub(r"(?<=[a-z])(?=[A-Z])", " ", local).capitalize(),
            "required": first(nodes, SH.minCount) is not None and first(nodes, SH.severity) != SH.Warning,
            "fixed": fixed,
            "position": (order is None, int(every.value(group, SH.order) or 99) if group is not None else 99, str(group), int(order or 0)),
        })
    found.sort(key=lambda field: (field["position"], field["label"]))
    return found
