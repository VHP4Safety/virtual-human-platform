"""JSON-LD documents of the records."""

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
    """Return the JSON-LD context of the platform from config."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    terms.update(config.get("terms", {}))
    return terms


def expand(name: str) -> str:
    """Return the property of the field name name."""
    if name in settings().get("terms", {}):
        return settings()["terms"][name]
    prefixes = settings()["prefixes"]
    prefix, _, local = name.partition(":")
    if local and prefix in prefixes:
        return prefixes[prefix] + local
    return prefixes["schema"] + name


def stored_values(found: Graph, iri: str, name: str) -> list[str]:
    """Return the values of the field name of the record at iri, as texts."""
    values = []
    for value in found.objects(URIRef(iri), URIRef(expand(name))):
        values.append(str(value))
    return values


def statements(document: dict) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


def document(found: Graph, iri: str | None = None, named: bool = False) -> dict:
    """Return the JSON-LD document of the record at iri in found."""
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
    """Return the JSON-LD of the record at iri, or None."""
    with database.session() as db:
        record = db.get(Record, iri)
    if record is None or record.removed_at:
        return None
    return json.dumps(document(records.read([iri])), indent=2)


@cache
def private() -> set[URIRef]:
    """Return the properties of the private fields."""
    graph = profile_graph()
    marked = URIRef(dict(graph.namespaces())["form"] + "private")
    found = set()
    for field in graph.subjects(marked, Literal(True)):
        found.add(graph.value(field, SH.path))
    return found


@cache
def published_as() -> dict[URIRef, URIRef]:
    """Return the class of each field published as another class, by property."""
    graph = profile_graph()
    marked = URIRef(dict(graph.namespaces())["form"] + "publishedAs")
    found = {}
    for field, of_class in graph.subject_objects(marked):
        found[graph.value(field, SH.path)] = of_class
    return found


def typed(found: Graph) -> Graph:
    """Return found with the statements added for publication."""
    for predicate, of_class in published_as().items():
        for value in list(found.objects(None, predicate)):
            if isinstance(value, URIRef):
                found.add((value, RDF.type, of_class))
    # A part address (<record>#<field>-<n>) has no page of its own.
    for node in set(found.subjects(RDF.type, None)):
        if isinstance(node, URIRef) and str(node).startswith(settings()["base"]) and not records.PART.match(str(node)):
            found.add((node, SDO.mainEntityOfPage, node))
            if found.value(node, SDO.url) is None:
                found.add((node, SDO.url, node))
    for of_class, (official, fields) in required().items():
        for node in set(found.subjects(RDF.type, of_class)):
            if fields <= set(found.predicates(node, None)):
                found.add((node, DCTERMS.conformsTo, official))
    return found


def public(found: Graph) -> Graph:
    """Return found without private fields, as shown on the pages."""
    for predicate in private():
        found.remove((None, predicate, None))
    return typed(found)


@lru_cache(maxsize=256)
def page_document(iri: str, latest: str) -> dict:
    """Return the JSON-LD of the record at iri for its page, cached until latest changes."""
    return document(linked(records.get(iri)), iri, named=True)


def linked(record: Record) -> Graph:
    """Return the data of record as published on its page."""
    found = public(records.with_names(records.graph([record.iri])))
    if record.iri != settings()["base"]:
        found.add((URIRef(record.iri), VOID.inDataset, URIRef(settings()["base"])))
    return found


# The published statements, made again when a record is changed.
PUBLISHED = {}


def published_all() -> dict:
    """Return the records with a page and the terms they link to, without private fields."""
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
    """Return all records with a page, with their parts, without private fields."""
    return published_all()["records"]


def published_terms() -> Graph:
    """Return the terms and other outside records linked from the records with a page."""
    return published_all()["terms"]
