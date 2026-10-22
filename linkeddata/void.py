"""VoID description of the data of the platform."""

import re
from collections import Counter
from urllib.parse import urlsplit

from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, FOAF, SDO, VOID
from rdfsolve.client.sql_tables import layout
from rdfsolve.iris import local_name
from rdfsolve.ontology.terms import namespace
from sqlalchemy import select

import database
from database import records
from database.tables import Record
from linkeddata import documents
from linkeddata.profile import jsonld_name, settings, shapes_text

DESCRIPTION = ".well-known/void"
# The fields of the catalogue record, with their terms in the general metadata of VoID.
GENERAL = {SDO.name: DCTERMS.title, SDO.alternateName: DCTERMS.alternative, SDO.abstract: DCTERMS.abstract,
           SDO.description: DCTERMS.description, SDO.publisher: DCTERMS.publisher, SDO.license: DCTERMS.license,
           SDO.about: DCTERMS.subject, SDO.subjectOf: FOAF.page}
# The formats that are returned at the address of a record (https://www.w3.org/ns/formats/).
FORMATS = ["http://www.w3.org/ns/formats/Turtle", "http://www.w3.org/ns/formats/N-Triples", "http://www.w3.org/ns/formats/JSON-LD"]

PLATFORM = {}


def platform() -> dict:
    """Return the name, abstract, licence and publisher of the platform."""
    latest = records.latest_change()
    if PLATFORM.get("latest") != latest:
        found = records.graph([settings()["base"]])
        node = URIRef(settings()["base"])
        publisher = records.get(str(found.value(node, SDO.publisher) or ""))
        PLATFORM.update(latest=latest, name=str(found.value(node, SDO.name) or ""), abstract=str(found.value(node, SDO.abstract) or ""),
                        license=str(found.value(node, SDO.license) or ""),
                        publisher=documents.document(documents.linked(publisher), publisher.iri, named=True) if publisher is not None else None)
    return PLATFORM


def general(void: Graph, dataset: URIRef) -> None:
    """Add the platform record to the description."""
    record = records.get(str(dataset))
    if record is None:
        return
    own = documents.linked(record)
    void += own
    for field, term in GENERAL.items():
        for value in own.objects(dataset, field):
            void.add((dataset, term, value))
    for publisher in own.objects(dataset, SDO.publisher):
        held = records.graph([str(publisher)])
        for role in held.objects(publisher, SDO.member):
            for organisation in held.objects(role, SDO.member):
                void.add((dataset, DCTERMS.contributor, organisation))


def name(*iris: str) -> URIRef:
    """Return the address of a partition in the description."""
    parts = []
    for iri in iris:
        parts.append(re.sub(r"[^A-Za-z0-9]+", "-", jsonld_name(iri)).strip("-"))
    return URIRef(records.address(DESCRIPTION) + "#" + "_".join(parts))


def partitions(void: Graph, dataset: URIRef, base: str) -> None:
    """Add a partition for each class of the records and parts."""
    named = {}
    for part in void.objects(dataset, VOID.classPartition):
        named[void.value(part, VOID["class"])] = part
    published = select(Record.iri).where(Record.iri.startswith(base), Record.part_of.is_(None), Record.removed_at.is_(None), Record.moved_to.is_(None))
    left_out = {str(field) for field in documents.private()}
    with database.engine().connect() as connection:
        found = layout(shapes_text()).void(connection, published, name=lambda *iris: str(name(*iris)), left_out=left_out)
    for partition in found:
        void.add((dataset, VOID.classPartition, partition.to_rdf(void)))
        given = named.pop(URIRef(partition.class_uri), None)
        if given is not None:
            for field, term in ((SDO.name, DCTERMS.title), (SDO.description, DCTERMS.description), (SDO.position, SDO.position)):
                for value in void.objects(given, field):
                    void.add((URIRef(partition.uri), term, value))
            void.remove((dataset, VOID.classPartition, given))
            void.remove((given, None, None))


def linksets(void: Graph, dataset: URIRef, found: Graph, base: str) -> None:
    """Add a linkset for each registry of the sameAs addresses."""
    counted = Counter()
    for subject, value in found.subject_objects(SDO.sameAs):
        if isinstance(subject, URIRef) and str(subject).startswith(base) and isinstance(value, URIRef) and not str(value).startswith(base):
            counted[urlsplit(str(value)).netloc] += 1
    for site, count in sorted(counted.items()):
        target = URIRef(records.address(DESCRIPTION) + "#" + site)
        void.add((target, RDF.type, VOID.Dataset))
        void.add((target, FOAF.homepage, URIRef(f"https://{site}/")))
        linkset = URIRef(records.address(DESCRIPTION) + "#links-" + site)
        void.add((dataset, VOID.subset, linkset))
        void.add((linkset, RDF.type, VOID.Linkset))
        void.add((linkset, VOID.subjectsTarget, dataset))
        void.add((linkset, VOID.objectsTarget, target))
        void.add((linkset, VOID.linkPredicate, SDO.sameAs))
        void.add((linkset, VOID.triples, Literal(count)))


def terms(void: Graph, dataset: URIRef) -> None:
    """Add the linked vocabulary terms as a dataset."""
    found = documents.published_terms()
    subset = URIRef(records.address(DESCRIPTION) + "#terms")
    void.add((dataset, VOID.subset, subset))
    void.add((subset, RDF.type, VOID.Dataset))
    void.add((subset, DCTERMS.title, Literal("Vocabulary terms that the records link to")))
    void.add((subset, VOID.dataDump, URIRef(records.address("api/dump/terms"))))
    void.add((subset, VOID.triples, Literal(len(found))))
    void.add((subset, VOID.entities, Literal(len(set(found.subjects(RDF.type, None))))))
    counted = Counter(found.objects(None, SDO.inDefinedTermSet))
    held = records.graph(sorted(str(vocabulary) for vocabulary in counted))
    for vocabulary, count in sorted(counted.items()):
        part = URIRef(records.address(DESCRIPTION) + "#terms-" + local_name(str(vocabulary)))
        void.add((subset, VOID.subset, part))
        void.add((part, RDF.type, VOID.Dataset))
        void.add((part, DCTERMS.source, vocabulary))
        void.add((part, VOID.entities, Literal(count)))
        for field, term in ((SDO.name, DCTERMS.title), (SDO.license, DCTERMS.license), (VOID.uriSpace, VOID.uriSpace)):
            for value in held.objects(vocabulary, field):
                void.add((part, term, value))


DESCRIBED = {}


def described() -> Graph:
    """Return the VoID description."""
    latest = records.latest_change()
    if DESCRIBED.get("latest") != latest:
        DESCRIBED.update(latest=latest, graph=description())
    return DESCRIBED["graph"]


def description() -> Graph:
    base = settings()["base"]
    dataset = URIRef(base)
    found = documents.published()
    void = Graph()
    for prefix, address in {"void": VOID, "dct": DCTERMS, "foaf": FOAF, **settings()["prefixes"]}.items():
        void.bind(prefix, address)
    description = URIRef(records.address(DESCRIPTION))
    void.add((description, RDF.type, VOID.DatasetDescription))
    void.add((description, FOAF.primaryTopic, dataset))
    general(void, dataset)
    void.add((description, DCTERMS.title, Literal(f"VoID description of {void.value(dataset, DCTERMS.title) or base}")))
    void.add((dataset, RDF.type, VOID.Dataset))
    void.add((dataset, FOAF.homepage, dataset))
    void.add((dataset, VOID.uriSpace, Literal(base)))
    void.add((dataset, VOID.dataDump, URIRef(records.address("api/dump"))))
    for found_format in FORMATS:
        void.add((dataset, VOID.feature, URIRef(found_format)))
    if records.latest_change():
        void.add((dataset, DCTERMS.modified, Literal(records.latest_change()[:10], datatype=XSD.date)))
    void.add((dataset, VOID.triples, Literal(len(found))))
    entities = set()
    used = set()
    for subject, predicate, value in found:
        if isinstance(subject, URIRef) and str(subject).startswith(base) and predicate == RDF.type:
            entities.add(subject)
        if predicate != RDF.type:
            used.add(namespace(str(predicate)))
        elif isinstance(value, URIRef):
            used.add(namespace(str(value)))
    void.add((dataset, VOID.entities, Literal(len(entities))))
    for vocabulary in sorted(used):
        void.add((dataset, VOID.vocabulary, URIRef(vocabulary)))
    partitions(void, dataset, base)
    linksets(void, dataset, found, base)
    terms(void, dataset)
    return void
