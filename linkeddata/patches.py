"""Stand-ins for calls that rdfsolve does not have yet, with the names and signatures of their rdfsolve
proposals. Each is replaced by its rdfsolve call once that exists."""

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import requests
from rdflib import RDF, RDFS, BNode, Graph, URIRef
from rdflib.namespace import SH
from rdfsolve.client.sql_tables import STATEMENTS, TERM_SUFFIX, layout
from rdfsolve.ontology.service import Ontologies
from rdfsolve.schema_models.core import MinedSchema
from rdfsolve.schema_models.void_model import VoidClassPartition, VoidDatatypePartition, VoidPropertyPartition
from sqlalchemy import column, func, literal, select, table, union_all


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


# rdfsolve issue 15: MinedSchema.from_vocabulary sorts the texts of terms by term and predicate only, so two
# texts of one term from two vocabularies come in either order, and so does the schema's identifier.
def from_vocabulary(vocabularies, classes, profile) -> MinedSchema:
    """MinedSchema.from_vocabulary, with the texts of each term sorted, and the identifier of the content
    made as rdfsolve makes it."""
    schema = MinedSchema.from_vocabulary(vocabularies, classes, profile=profile)
    for texts in (schema.enrichment.definitions, schema.enrichment.labels):
        texts.sort(key=lambda found: (found.term_iri, found.predicate, found.text.value, found.text.language or ""))
    content = schema.model_dump_json(exclude={"about"})
    schema.about.schema_id = str(uuid5(NAMESPACE_URL, "rdfsolve:vocabulary:" + sha256(content.encode()).hexdigest()))
    return schema


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



# rdfsolve issue 17: layout(profile) reads a node shape's own property shapes only, not those of the shapes it
# builds on (a node-level sh:node, such as an AboutPage's on WebPage).
def inherited(profile: str) -> str:
    """The profile, with each class's node shape given the property shapes of the shapes it builds on."""
    graph = Graph(bind_namespaces="none").parse(data=profile, format="turtle")
    added = False
    for shape in set(graph.subjects(SH.targetClass, None)):
        built_on = list(graph.objects(shape, SH.node))
        while built_on:
            other = built_on.pop()
            for found in graph.objects(other, SH.property):
                graph.add((shape, SH.property, found))
                added = True
            built_on.extend(graph.objects(other, SH.node))
    return graph.serialize(format="turtle") if added else profile


# rdfsolve proposal P8: Layout.within(of_class, hierarchy) -> list[str]
def within(of_class: str, profile: str, hierarchy: Graph) -> list[str]:
    """The profile's classes that are of_class or below it in the vocabularies' class hierarchy."""
    found = [of_class]
    for other in layout(profile).classes:
        if other != of_class and URIRef(of_class) in hierarchy.transitive_objects(URIRef(other), RDFS.subClassOf):
            found.append(other)
    return found


# rdfsolve issue 20 (proposal): Layout.void(connection, records) -> list[VoidClassPartition]
def void_partitions(profile: str, connection, records, left_out: set[str], name) -> list[VoidClassPartition]:
    """The class partitions of the rows of some records (*records*, a select of their addresses), as rdfsolve's
    VoID models give them: per class with rows, its entities (nodes with an address) and a property partition
    per property, with its triples, the classes of the nodes its values are, and the datatypes of its texts.
    Properties in *left_out*, such as private fields, are not counted; *name* makes a partition's address from
    the IRIs it partitions by."""
    shapes = layout(profile)
    tables = {}
    for table_name, columns in shapes.columns().items():
        tables[table_name] = table(table_name, *[column(found) for found in columns])
    # The class of each node, to partition the values that are nodes by their class.
    classes = dict(connection.execute(union_all(*[select(tables[of_layout.name].c.iri, tables[of_layout.name].c.type) for of_layout in shapes.classes.values()])).all())
    rest = tables[STATEMENTS]
    found = []
    for of_class, of_layout in sorted(shapes.classes.items()):
        own = tables[of_layout.name]
        total, entities = connection.execute(select(func.count(), func.count().filter(~own.c.iri.startswith("_:"))).where(own.c.record.in_(records))).one()
        if not total:
            continue
        counted = {}
        sources = []
        for path, held in of_layout.single.items():
            sources.append((path, own, own.c[held], own.c[held + TERM_SUFFIX], own.c[held].is_not(None)))
        for path, held in of_layout.several.items():
            listed = tables[of_layout.field_table(held)]
            sources.append((path, listed, listed.c.value, listed.c.term, None))
        for path, source, value, term, condition in sources:
            statement = select(literal(path), term, value, func.count()).where(source.c.record.in_(records)).group_by(term, value)
            if condition is not None:
                statement = statement.where(condition)
            counted.setdefault(path, []).extend(connection.execute(statement).all())
        # Values that are no field of the class, or more than one of a single field, are in the statements table.
        statement = (select(rest.c.property, rest.c.term, rest.c.value, func.count()).select_from(rest.join(own, own.c.iri == rest.c.iri))
                     .where(rest.c.record.in_(records), rest.c.property != str(RDF.type)).group_by(rest.c.property, rest.c.term, rest.c.value))
        for row in connection.execute(statement):
            counted.setdefault(row[0], []).append(row)
        properties = []
        for path, rows in sorted(counted.items()):
            if path in left_out or not rows:
                continue
            linked = {}
            datatypes = {}
            for _, kind, value, count in rows:
                if kind in ("@id", "@blank"):
                    of_value = classes.get(value)
                    if of_value:
                        linked[of_value] = linked.get(of_value, 0) + count
                else:
                    datatype = str(RDF.langString) if kind.startswith("@") else kind or "http://www.w3.org/2001/XMLSchema#string"
                    datatypes[datatype] = datatypes.get(datatype, 0) + count
            properties.append(VoidPropertyPartition(
                uri=name(of_class, path), property_uri=path, triples=sum(row[3] for row in rows),
                class_partitions=[VoidClassPartition(uri=name(of_class, path, of_value), class_uri=of_value, triples=count) for of_value, count in sorted(linked.items())],
                datatype_partitions=[VoidDatatypePartition(uri=name(of_class, path, datatype), datatype_uri=datatype, triples=count) for datatype, count in sorted(datatypes.items())]))
        found.append(VoidClassPartition(uri=name(of_class), class_uri=of_class, entities=entities, property_partitions=properties))
    return found

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
