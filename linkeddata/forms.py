"""The editor's form for a class, read from the model's shapes: one field for each property shape of
the class. The application profile gives their section (sh:group), order, name, explanation, and
required, recommended or fixed values, and the editor of each (dash:editor); the shapes made from the
vocabularies explain the fields that the profile leaves out. Otherwise, what an editor enters in a
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


def allowed(graph: Graph, nodes: list) -> dict:
    """The classes that the values of some shapes link to (their sh:class, else those in their sh:or),
    the terms of the vocabularies that their sh:or lists with sh:in, and the kinds of their other values:
    datatypes, or "IRI" for web addresses."""
    direct = []
    alternatives = []
    terms = []
    kinds = []
    for node in nodes:
        options = [node]
        for listed in graph.objects(node, SH["or"]):
            options.extend(Collection(graph, listed))
        for option in options:
            for value in graph.objects(option, SH["class"]):
                (direct if option == node else alternatives).append(str(value))
            for value in graph.objects(option, SH.datatype):
                kinds.append(str(value))
            if option != node:
                for listed in graph.objects(option, SH["in"]):
                    for value in Collection(graph, listed):
                        terms.append(str(value))
            if graph.value(option, SH.nodeKind) in (SH.IRI, SH.BlankNodeOrIRI):
                kinds.append("IRI")
    return {"targets": direct or alternatives, "terms": terms, "values": kinds}


@cache
def form(kind: str) -> list[dict]:
    """The fields of the form for a class: those the profile orders come first, in its order, and
    the others follow by name."""
    every = shapes()
    in_profile = property_shapes(profile(), kind)
    ordered = []
    others = []
    for iri, nodes in property_shapes(every, kind).items():
        # The profile's shape comes first, so that its names and explanations are read before those of the vocabularies.
        mine = in_profile.get(iri, [])
        nodes = mine + [node for node in nodes if node not in mine]
        known = allowed(every, nodes)
        fixed = []
        for node in nodes:
            for value in every.objects(node, SH.hasValue):
                fixed.append(str(value))
        local = iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        name = first(every, nodes, SH.name) or local
        required = first(every, nodes, SH.minCount)
        order = first(every, nodes, SH.order)
        group = term(every, nodes, SH.group)
        listed = term(every, nodes, SH["in"])
        options = [str(value) for value in Collection(every, listed)] if listed is not None else []
        several = first(every, nodes, SH.maxCount) != 1
        datatypes = []
        for value in known["values"]:
            if value != "IRI" and value not in datatypes:
                datatypes.append(value)
        found = {
            "name": rdf.term(iri),
            "iri": iri,
            "property": curie(iri),
            # A name the profile gives is kept; the name of a property of the vocabularies is made readable.
            "label": readable(name) if name == local else name,
            "help": plain(first(every, nodes, SH.description) or ""),
            "required": bool(required) and first(every, nodes, SH.severity) != str(SH.Warning),
            "recommended": bool(required) and first(every, nodes, SH.severity) == str(SH.Warning),
            "message": first(every, nodes, SH.message) or "",
            "pattern": first(every, nodes, SH.pattern) or "",
            "options": options,
            "class": known["targets"][0] if known["targets"] else "",
            "classes": known["targets"],
            "terms": known["terms"],
            "datatypes": datatypes,
            "links": bool(known["targets"] or known["terms"]) or "IRI" in known["values"],
            "texts": any(value != "IRI" for value in known["values"]),
            "section": str(every.value(group, RDFS.label) or "More") if group is not None else "More",
            "section_order": int(every.value(group, SH.order) or 99) if group is not None else 99,
            "several": several,
            "fixed": fixed,
            "entry": entry(
                known,
                fixed,
                first(every, nodes, DASH.singleLine) is not False,
                str(first(every, nodes, SH.nodeKind)) == str(SH.IRI),
                str(first(every, nodes, DASH.editor) or ""),
                several,
                options,
            ),
        }
        if order is None:
            others.append(found)
        else:
            ordered.append(((found["section_order"], found["section"], order), found))
    ordered.sort(key=lambda pair: pair[0])
    others.sort(key=lambda found: found["label"])
    fields = []
    for _, found in ordered:
        fields.append(found)
    return fields + others


def shaped(document: dict, kind: str) -> dict:
    """A record's document with the values of each field that takes several as a list, also when it has one."""
    found = dict(document)
    for field in form(kind):
        if field["several"] and field["name"] in found and not isinstance(found[field["name"]], list):
            found[field["name"]] = [found[field["name"]]]
    return found
