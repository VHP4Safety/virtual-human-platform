"""The editor's form for a class, read from the model. Its fields are the columns of the records table
that the class has. The application profile gives their section (sh:group), order, name, explanation,
and required, recommended or fixed values, and the editor of each (dash:editor); the shapes made from
the vocabularies explain the fields that the profile leaves out. Otherwise, what an editor enters in a
field follows from the values the model allows in it."""

import re
from functools import cache

from rdflib import Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDFS, SH

from linkeddata import rdf
from linkeddata.model import DASH, curie, profile, property_shapes, shapes

IMAGE = "https://schema.org/ImageObject"


def term(graph: Graph, nodes: list, predicate: URIRef):
    """The first value of a predicate in some shapes, as an RDF term."""
    for node in nodes:
        found = graph.value(node, predicate)
        if found is not None:
            return found
    return None


def first(graph: Graph, nodes: list, predicate: URIRef):
    """The first value of a predicate in some shapes, as a Python value."""
    found = term(graph, nodes, predicate)
    return found.toPython() if found is not None else None


def readable(label: str) -> str:
    """A field's name as words: "conformsTo" is "Conforms to"."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).lower()
    return words[:1].upper() + words[1:]


def plain(text: str) -> str:
    """A description from schema.org without its link markup: "[[URL]]" is "URL"."""
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)


def entry(known, fixed: list, single_line: bool, address: bool, editor: str | None, several: bool, options: list) -> str:
    """What the editor enters: a text, a longer text, a web address, a list of web addresses, one or
    several of the records a field links to, pages with their titles, one of a list of values, an
    image, or nothing, when the value is fixed. *address* is True when the profile only takes a web
    address, and *editor* is the DASH editor that the profile names."""
    if fixed:
        return "fixed"
    if IMAGE in known["targets"]:
        return "image"
    if options:
        return "select"
    if editor == str(DASH.DetailsEditor):
        return "details"
    if editor == str(DASH.InstancesSelectEditor):
        return "links" if several else "choice"
    if editor == str(DASH.URIEditor):
        return "addresses" if several else "address"
    if address:
        return "address"
    if any(value != "IRI" for value in known["values"]):
        return "text" if single_line else "long text"
    if known["targets"]:
        return "links"
    return "address"


@cache
def form(kind: str) -> list[dict]:
    """The fields of the form for a class: those the profile orders come first, in its order, and
    the others follow by name."""
    known = rdf.fields(kind)
    every = shapes()
    in_profile = property_shapes(profile(), kind)
    in_every = property_shapes(every, kind)
    ordered = []
    others = []
    for field in known.index:
        iri = known.loc[field, "property"]
        mine = in_profile.get(iri, [])
        fixed = []
        for node in mine:
            for value in profile().objects(node, SH.hasValue):
                fixed.append(str(value))
        description = first(profile(), mine, SH.description) or first(every, in_every.get(iri, []), SH.description)
        required = first(profile(), mine, SH.minCount)
        order = first(profile(), mine, SH.order)
        group = term(profile(), mine, SH.group)
        listed = term(profile(), mine, SH["in"])
        options = [str(value) for value in Collection(profile(), listed)] if listed is not None else []
        found = {
            "name": field,
            "property": curie(iri),
            "label": first(profile(), mine, SH.name) or readable(known.loc[field, "label"]),
            "help": plain(description or ""),
            "required": bool(required) and first(profile(), mine, SH.severity) != str(SH.Warning),
            "recommended": bool(required) and first(profile(), mine, SH.severity) == str(SH.Warning),
            "message": first(profile(), mine, SH.message) or "",
            "pattern": first(profile(), mine, SH.pattern) or "",
            "options": options,
            "class": str(first(profile(), mine, SH["class"]) or ""),
            "section": str(profile().value(group, RDFS.label) or "More") if group is not None else "More",
            "section_order": int(profile().value(group, SH.order) or 99) if group is not None else 99,
            "several": rdf.several(field),
            "fixed": fixed,
            "entry": entry(
                known.loc[field],
                fixed,
                first(profile(), mine, DASH.singleLine) is not False,
                str(first(profile(), mine, SH.nodeKind)) == str(SH.IRI),
                str(first(profile(), mine, DASH.editor) or ""),
                rdf.several(field),
                options,
            ),
        }
        if order is None:
            others.append(found)
        else:
            ordered.append(((found["section_order"], order), found))
    ordered.sort(key=lambda pair: pair[0])
    others.sort(key=lambda found: found["label"])
    fields = []
    for _, found in ordered:
        fields.append(found)
    return fields + others


def linked_classes(kind: str, field: str) -> list[str]:
    """The classes that the application profile says a field links to: its sh:class, or those in its sh:or."""
    path = rdf.fields(kind).loc[field, "property"]
    found = []
    for node in property_shapes(profile(), kind).get(path, []):
        for value in profile().objects(node, SH["class"]):
            found.append(str(value))
        for listed in profile().objects(node, SH["or"]):
            for alternative in Collection(profile(), listed):
                for value in profile().objects(alternative, SH["class"]):
                    found.append(str(value))
    return found
