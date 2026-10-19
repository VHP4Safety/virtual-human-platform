"""Stand-ins for calls that rdfsolve does not have yet, with the names and signatures of their rdfsolve
proposals. Each is replaced by its rdfsolve call once that exists."""

from dataclasses import dataclass, field
from pathlib import Path

import requests
from rdflib import RDF, BNode, Graph, URIRef
from rdfsolve.client.sql_tables import layout
from rdfsolve.ontology.service import Ontologies


@dataclass
class Merged:
    """A record merged with another source's statements: the statements added, and the values kept where
    the other source gives others (subject, property, kept, offered)."""

    graph: Graph
    added: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)


def key(graph: Graph, node) -> str:
    """A value as merging compares it: a node without an address by the values it holds."""
    if not isinstance(node, BNode):
        return str(node)
    held = []
    for predicate, value in graph.predicate_objects(node):
        held.append(str(predicate) + " " + key(graph, value))
    held.sort()
    return "part " + " ".join(held)


def described(graph: Graph, node: BNode) -> list:
    """The statements of a node without an address, and of such nodes it holds."""
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
    """*current* with the statements of *added* about its subjects with an address. A single-valued field
    (sh:maxCount 1 in *profile*) keeps its value, and a different one is a conflict; a part already held with
    the same values is not added again, so a second merge adds nothing."""
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


# rdfsolve proposal P7: rdfsolve.client.sql_tables.context(profile, of_class, term) -> dict
def context(profile: Graph, of_class: str, term) -> dict:
    """JSON-LD term definitions for records of a class, from the profile: each property named by *term*,
    and a list (@set) where several values are taken. The class's own count is used; a property only of
    linked records is a list unless every class takes one value."""
    classes = layout(profile).classes
    single = set()
    several = set()
    for found in classes.values():
        single.update(found.single)
        several.update(found.several)
    own = classes.get(of_class)
    terms = {"id": "@id", "type": "@type"}
    for iri in sorted(single | several):
        if own is not None and (iri in own.single or iri in own.several):
            listed = iri in own.several
        else:
            listed = iri in several
        definition = {"@id": iri}
        if listed:
            definition["@container"] = "@set"
        terms[term(iri)] = definition
    return terms


OBO = "http://purl.obolibrary.org/obo/"
ENTITY = "http://www.wikidata.org/entity/"
# Vocabulary registries, by rdfsolve's service name.
REGISTRIES = {"ols": "Ontology Lookup Service (EMBL-EBI)", "ontobee": "Ontobee", "wikidata": "Wikidata"}


def listed(registry: str, cache: Path) -> list[dict]:
    """Every vocabulary of a registry: identifier, title, term namespace, description and code prefix."""
    if registry == "wikidata":
        return [{"id": "wikidata", "title": "Wikidata", "namespace": ENTITY, "description": "The items of Wikidata.", "prefix": ""}]
    provider = Ontologies(registry, cache=cache)
    found = []
    try:
        if registry == "ols":
            def read():
                return provider._json("/ontologies", size=1000)["_embedded"]["ontologies"]
            for ontology in provider._request("vocabularies", registry, read) or []:
                config = ontology.get("config") or {}
                prefix = config.get("preferredPrefix") or ontology["ontologyId"].upper()
                bases = config.get("baseUris") or [OBO + prefix + "_"]
                found.append({"id": ontology["ontologyId"], "title": config.get("title") or prefix, "namespace": bases[0],
                              "description": config.get("description") or "", "prefix": prefix})
        else:
            def read():
                return provider._sparql("PREFIX owl: <http://www.w3.org/2002/07/owl#> PREFIX dc: <http://purl.org/dc/elements/1.1/> "
                                        "SELECT DISTINCT ?graph ?title WHERE { GRAPH ?graph { ?o a owl:Ontology . OPTIONAL { ?o dc:title ?title } } }")
            for row in provider._request("vocabularies", registry, read) or []:
                prefix = row["graph"]["value"].rstrip("/").split("/")[-1]
                found.append({"id": prefix, "title": row.get("title", {}).get("value") or prefix, "namespace": OBO + prefix + "_", "description": "", "prefix": prefix})
    finally:
        provider.close()
    return found


# rdfsolve issue 11 (P6): Service(<registry>).vocabularies(text)
def vocabularies(registry: str, text: str, cache: Path) -> list[dict]:
    """The vocabularies of a registry (ols, ontobee or wikidata) whose identifier or title has the text."""
    found = []
    for vocabulary in listed(registry, cache):
        if text.casefold() in (vocabulary["id"] + " " + vocabulary["title"]).casefold():
            found.append(vocabulary)
    return found


# rdfsolve issue 11: Vocabulary(namespace, service=Service(<registry>)).search(text)
def terms(registry: str, text: str, namespace: str, cache: Path) -> list[dict]:
    """The terms at a namespace that a registry finds by name: address, label, definition and code."""
    found = []
    if registry == "wikidata":
        answer = requests.get("https://www.wikidata.org/w/api.php", timeout=8, headers={"User-Agent": "VHP4Safety platform"},
                              params={"action": "wbsearchentities", "search": text, "language": "en", "limit": 12, "format": "json"})
        answer.raise_for_status()
        for item in answer.json().get("search", []):
            found.append({"@id": ENTITY + item["id"], "name": item.get("label") or item["id"], "description": item.get("description") or "", "code": item["id"]})
        return found
    ontology = None
    prefix = ""
    for vocabulary in listed(registry, cache):
        if vocabulary["namespace"] == namespace:
            ontology = vocabulary["id"]
            prefix = vocabulary["prefix"] + ":"
    provider = Ontologies(registry, cache=cache)
    try:
        for term in provider.search(text, ontology=ontology if registry == "ols" else None, exact=False):
            if term["iri"].startswith(namespace):
                found.append({"@id": term["iri"], "name": term.get("label") or term["iri"], "description": " ".join(term.get("description") or []),
                              "code": prefix + term["iri"].removeprefix(namespace)})
    finally:
        provider.close()
    return found


def serving(namespace: str, cache: Path) -> str | None:
    """The registry that has the vocabulary at a namespace: OLS, else Wikidata, else Ontobee."""
    for registry in ("ols", "wikidata", "ontobee"):
        for vocabulary in listed(registry, cache):
            if vocabulary["namespace"] == namespace:
                return registry
    return None
