"""Records as JSON-LD documents, compacted with the platform's context: https://schema.org/name is "name",
and http://purl.org/dc/terms/conformsTo is "dct:conformsTo". Pages use the same names, with lists where the
profile takes several values."""

import json
from functools import cache

from pyld import jsonld
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SDO, SH

import database
from database import records
from database.tables import Record
from linkeddata import patches, storage
from linkeddata.model import profile, settings


def context(config: dict) -> dict:
    """The JSON-LD context: schema.org terms unprefixed, other vocabularies prefixed, and names for the
    glossary's properties."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    terms.update(config.get("terms", {}))
    return terms


def term(iri: str) -> str:
    """The name of a property or class in the platform's JSON-LD."""
    for name, named in settings().get("terms", {}).items():
        if iri == named:
            return name
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            if prefix == "schema":
                return iri.removeprefix(namespace)
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


def expand(name: str) -> str:
    """The property of a field: "name" is https://schema.org/name, "dct:conformsTo" the property of dct."""
    if name in settings().get("terms", {}):
        return settings()["terms"][name]
    prefixes = settings()["prefixes"]
    prefix, _, local = name.partition(":")
    if local and prefix in prefixes:
        return prefixes[prefix] + local
    return prefixes["schema"] + name


def stored_values(found: Graph, iri: str, name: str) -> list[str]:
    """The values of a field of the record at *iri* in *found*: link addresses and texts."""
    values = []
    for value in found.objects(URIRef(iri), URIRef(expand(name))):
        values.append(str(value))
    return values


def values(document: dict, name: str) -> list:
    """The values of a field of a document: link addresses, texts and numbers."""
    given = document.get(name)
    found = []
    for item in given if isinstance(given, list) else [] if given is None else [given]:
        if isinstance(item, dict):
            item = item.get("@id", item.get("@value"))
        if item is not None:
            found.append(item)
    return found


def links(document: dict) -> list[str]:
    """The addresses that a document links to."""
    found = []
    for name, given in document.items():
        if name.startswith("@"):
            continue
        for item in given if isinstance(given, list) else [given]:
            if isinstance(item, dict) and "@id" in item:
                found.append(item["@id"])
    return found


def statements(document: dict) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


def document(found: Graph, iri: str | None = None, named: bool = False) -> dict:
    """The JSON-LD document of the record at *iri*, with its nodes without an address, and, when *named*, the
    class and name of each record it links to that *found* gives (as a read gives them); without *iri*, of all
    the statements."""
    if iri is None:
        expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
        return jsonld.compact(expanded, context(settings()))
    own = storage.described(found, iri)
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
    """The current JSON-LD of the record at this address; None when there is none."""
    with database.session() as db:
        record = db.get(Record, iri)
    if record is None or record.removed_at:
        return None
    return json.dumps(document(storage.read([iri])), indent=2)


@cache
@cache
def page_context(of_class: str) -> dict:
    """The context of a record's page: the platform's names, and a list for each field that takes several
    values."""
    return {**context(settings()), **patches.context(profile(), of_class, term)}


@cache
def private() -> set[URIRef]:
    """The properties of fields kept off the pages (form:private true in the profile)."""
    graph = profile()
    marked = URIRef(dict(graph.namespaces())["form"] + "private")
    found = set()
    for field in graph.subjects(marked, Literal(True)):
        found.add(graph.value(field, SH.path))
    return found


@cache
def published_as() -> dict[URIRef, URIRef]:
    """The properties of fields whose values the pages give another class too (form:publishedAs), by class."""
    graph = profile()
    marked = URIRef(dict(graph.namespaces())["form"] + "publishedAs")
    found = {}
    for field, of_class in graph.subject_objects(marked):
        found[graph.value(field, SH.path)] = of_class
    return found


def typed(found: Graph) -> Graph:
    """The statements with the values of fields published as another class having that class too."""
    for predicate, of_class in published_as().items():
        for value in list(found.objects(None, predicate)):
            if isinstance(value, URIRef):
                found.add((value, RDF.type, of_class))
    return found


def public(found: Graph) -> Graph:
    """The statements as pages show them: the values of private fields, such as email addresses, are taken
    out, and values of fields published as another class have that class too."""
    for predicate in private():
        found.remove((None, predicate, None))
    return typed(found)


def linked(record: Record) -> Graph:
    """A record's data as its page gives it: the record with its parts, and the class and name of each record it
    links to; private fields are taken out."""
    return public(storage.with_names(storage.graph([record.iri])))


# The published statements, made again when a record changes.
PUBLISHED = {}


def published() -> Graph:
    """Every record with a page, with its parts, and the records elsewhere that they link to, such as
    vocabulary terms; private fields are taken out."""
    latest = records.latest_change()
    if PUBLISHED.get("latest") != latest:
        own = []
        for iri, _ in records.with_pages():
            own.append(iri)
        found = storage.graph(own)
        linked = set()
        for value in found.objects():
            if isinstance(value, URIRef) and not str(value).startswith(settings()["base"]):
                linked.add(str(value))
        found += storage.graph(sorted(linked))
        PUBLISHED.update(latest=latest, graph=public(found))
    return PUBLISHED["graph"]


def view(record: Record) -> dict:
    """The record with the profile's field names, with its linked records embedded so their names can be shown."""
    statements = public(storage.linked_graph(record)).serialize(format="nt")
    expanded = jsonld.from_rdf(statements, {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": page_context(record.type), "@id": record.iri, "@embed": "@always"})
    found = framed["@graph"][0] if "@graph" in framed else framed
    found.pop("@context", None)
    return addresses(found)


def addresses(found):
    """A framed document whose links to nodes without statements, such as web pages, are addresses."""
    if isinstance(found, list):
        return [addresses(value) for value in found]
    if isinstance(found, dict):
        if list(found) == ["id"]:
            return found["id"]
        return {key: addresses(value) for key, value in found.items()}
    return found
