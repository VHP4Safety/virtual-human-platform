"""JSON-LD documents of the records, compacted with the context of the platform.

Write https://schema.org/name as "name", and http://purl.org/dc/terms/conformsTo as "dct:conformsTo". Use the same
names in the pages, with lists for the fields with several values."""

import json
from functools import cache, lru_cache

from pyld import jsonld
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, SDO, SH, VOID

import database
from database import records
from database.tables import Record
from linkeddata.profile import profile_graph, required, settings


def context(config: dict) -> dict:
    """Return the JSON-LD context of the platform.

    The schema.org terms have no prefix, and the terms of other vocabularies have a prefix. The properties of the
    glossary have names."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    terms.update(config.get("terms", {}))
    return terms


def expand(name: str) -> str:
    """Return the property of a field name: https://schema.org/name for "name", and
    http://purl.org/dc/terms/conformsTo for "dct:conformsTo"."""
    if name in settings().get("terms", {}):
        return settings()["terms"][name]
    prefixes = settings()["prefixes"]
    prefix, _, local = name.partition(":")
    if local and prefix in prefixes:
        return prefixes[prefix] + local
    return prefixes["schema"] + name


def stored_values(found: Graph, iri: str, name: str) -> list[str]:
    """Return the values of a field of the record at *iri* in *found*, as link addresses and texts."""
    values = []
    for value in found.objects(URIRef(iri), URIRef(expand(name))):
        values.append(str(value))
    return values


def values(document: dict, name: str) -> list:
    """Return the values of a field of a document, as link addresses, texts and numbers."""
    given = document.get(name)
    found = []
    if isinstance(given, list):
        items = given
    elif given is None:
        items = []
    else:
        items = [given]
    for item in items:
        if isinstance(item, dict):
            item = item.get("@id", item.get("@value"))
        if item is not None:
            found.append(item)
    return found


def statements(document: dict) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


def document(found: Graph, iri: str | None = None, named: bool = False) -> dict:
    """Return the JSON-LD document of the record at *iri*, with its nodes without an address. If *named* is true,
    include the class and the name of each linked record in *found*. Without *iri*, include all the statements."""
    if iri is None:
        expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
        return jsonld.compact(expanded, context(settings()))
    own = records.described(found, iri)
    if named:
        for value in set(own.objects()):
            if isinstance(value, URIRef) and (value, None, None) not in own:
                for predicate in (RDF.type, SDO.name):
                    for given in found.objects(value, predicate):
                        own.add((value, predicate, given))
    expanded = jsonld.from_rdf(own.serialize(format="nt"), {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": context(settings()), "@id": iri})
    if "@graph" in framed:
        return {"@context": framed["@context"], **framed["@graph"][0]} if framed["@graph"] else {"@context": framed["@context"]}
    return framed


def document_of(iri: str) -> str | None:
    """Return the current JSON-LD of the record at this address, or None if there is no record."""
    with database.session() as db:
        record = db.get(Record, iri)
    if record is None or record.removed_at:
        return None
    return json.dumps(document(records.read([iri])), indent=2)


@cache
def private() -> set[URIRef]:
    """Return the properties of the private fields, which are not shown on the pages (form:private true in the
    profile)."""
    graph = profile_graph()
    marked = URIRef(dict(graph.namespaces())["form"] + "private")
    found = set()
    for field in graph.subjects(marked, Literal(True)):
        found.add(graph.value(field, SH.path))
    return found


@cache
def published_as() -> dict[URIRef, URIRef]:
    """Return the properties of the fields whose values are published with another class (form:publishedAs), with
    that class."""
    graph = profile_graph()
    marked = URIRef(dict(graph.namespaces())["form"] + "publishedAs")
    found = {}
    for field, of_class in graph.subject_objects(marked):
        found[graph.value(field, SH.path)] = of_class
    return found


def typed(found: Graph) -> Graph:
    """Prepare the statements for publication. Give the values of the fields with form:publishedAs that class.
    State each record as the main entity of its page, and use the page as its web address (schema:url) if none is
    given. State the official profile of the class of a node (dct:conformsTo) only if all the fields required by
    that profile are given."""
    for predicate, of_class in published_as().items():
        for value in list(found.objects(None, predicate)):
            if isinstance(value, URIRef):
                found.add((value, RDF.type, of_class))
    for node in set(found.subjects(RDF.type, None)):
        if isinstance(node, URIRef) and str(node).startswith(settings()["base"]):
            found.add((node, SDO.mainEntityOfPage, node))
            if found.value(node, SDO.url) is None:
                found.add((node, SDO.url, node))
    for of_class, (official, fields) in required().items():
        for node in set(found.subjects(RDF.type, of_class)):
            if fields <= set(found.predicates(node, None)):
                found.add((node, DCTERMS.conformsTo, official))
    return found


def public(found: Graph) -> Graph:
    """Return the statements as shown on the pages. Remove the values of private fields, such as email addresses,
    and give the values of the fields with form:publishedAs that class."""
    for predicate in private():
        found.remove((None, predicate, None))
    return typed(found)


@lru_cache(maxsize=256)
def page_document(iri: str, latest: str) -> dict:
    """Return the JSON-LD of a record for its page, with the names of the linked records. Cache the document until
    a record is changed (*latest*, records.latest_change())."""
    return document(linked(records.get(iri)), iri, named=True)


def linked(record: Record) -> Graph:
    """Return the data of a record as published on its page.

    The data has the parts of the record, the class and the name of each linked record, and the dataset of the
    platform (void:inDataset). Remove private fields."""
    found = public(records.with_names(records.graph([record.iri])))
    if record.iri != settings()["base"]:
        found.add((URIRef(record.iri), VOID.inDataset, URIRef(settings()["base"])))
    return found


# The published statements, made again when a record is changed.
PUBLISHED = {}


def published_all() -> dict:
    """Return the records with a page, with their parts, and the linked records outside the platform, such as
    vocabulary terms. Remove private fields."""
    latest = records.latest_change()
    if PUBLISHED.get("latest") != latest:
        own = []
        for iri, _ in records.with_pages():
            own.append(iri)
        found = records.graph(own)
        linked = set()
        for value in found.objects():
            if isinstance(value, URIRef) and not str(value).startswith(settings()["base"]):
                linked.add(str(value))
        PUBLISHED.update(latest=latest, records=public(found), terms=public(records.graph(sorted(linked))))
    return PUBLISHED


def published() -> Graph:
    """Return all records with a page, with their parts. Remove private fields."""
    return published_all()["records"]


def published_terms() -> Graph:
    """Return the records outside the platform that are linked from the records with a page, such as vocabulary
    terms."""
    return published_all()["terms"]
