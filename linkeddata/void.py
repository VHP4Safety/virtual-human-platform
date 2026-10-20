"""The platform's data as one dataset, described with VoID (https://www.w3.org/TR/void/) at the platform's address,
for /.well-known/void and the platform's address in Turtle, JSON-LD or N-Triples:
- what it is: the platform's catalogue record, with its name, description, publisher, licence, subjects and pages
  in the Dublin Core and FOAF terms VoID asks for, and the publisher's partners as its contributors;
- how it is reached: its address space, its dump, the formats each record's address answers in;
- what it holds: its vocabularies, triples and entities (records and parts at its addresses), and a partition
  per class with its properties, the classes their values are and the datatypes of their texts (rdfsolve's VoID
  models, counted from the tables), with the catalogue's name and description of each kind of records;
- its links to other datasets: a linkset per registry that its records' sameAs addresses are at;
- the vocabulary terms its records link to: a dataset of its own with its dump, a part per vocabulary with
  the vocabulary's record as its source and its licence.
The document that says so is a void:DatasetDescription."""

import re
from collections import Counter
from urllib.parse import urlsplit

from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, FOAF, SDO, VOID
from rdfsolve.ontology.terms import namespace
from sqlalchemy import select

import database
from database import records
from database.tables import Record
from linkeddata import documents, patches, storage
from linkeddata.model import settings

DESCRIPTION = ".well-known/void"
# The catalogue's fields, as VoID's general metadata names them.
GENERAL = {SDO.name: DCTERMS.title, SDO.alternateName: DCTERMS.alternative, SDO.abstract: DCTERMS.abstract,
           SDO.description: DCTERMS.description, SDO.publisher: DCTERMS.publisher, SDO.license: DCTERMS.license,
           SDO.about: DCTERMS.subject, SDO.subjectOf: FOAF.page}
# The formats a record's address answers in (https://www.w3.org/ns/formats/).
FORMATS = ["http://www.w3.org/ns/formats/Turtle", "http://www.w3.org/ns/formats/N-Triples", "http://www.w3.org/ns/formats/JSON-LD"]

PLATFORM = {}


def platform() -> dict:
    """The platform's name, sentence and licence, from its catalogue record, and its publisher's JSON-LD document;
    empty until it has one."""
    latest = records.latest_change()
    if PLATFORM.get("latest") != latest:
        found = storage.graph([settings()["base"]])
        node = URIRef(settings()["base"])
        publisher = records.get(str(found.value(node, SDO.publisher) or ""))
        PLATFORM.update(latest=latest, name=str(found.value(node, SDO.name) or ""), abstract=str(found.value(node, SDO.abstract) or ""),
                        license=str(found.value(node, SDO.license) or ""),
                        publisher=documents.document(documents.linked(publisher), publisher.iri, named=True) if publisher is not None else None)
    return PLATFORM


def general(void: Graph, dataset: URIRef) -> None:
    """The catalogue record, as its page's data gives it, with its fields in VoID's terms too, and the
    publisher's partners as contributors."""
    record = records.get(str(dataset))
    if record is None:
        return
    own = documents.linked(record)
    void += own
    for field, term in GENERAL.items():
        for value in own.objects(dataset, field):
            void.add((dataset, term, value))
    for publisher in own.objects(dataset, SDO.publisher):
        held = storage.graph([str(publisher)])
        for role in held.objects(publisher, SDO.member):
            for organisation in held.objects(role, SDO.member):
                void.add((dataset, DCTERMS.contributor, organisation))


def name(*iris: str) -> URIRef:
    """A partition's address in the description, from the IRIs it partitions by (class, property, datatype)."""
    parts = []
    for iri in iris:
        parts.append(re.sub(r"[^A-Za-z0-9]+", "-", documents.term(iri)).strip("-"))
    return URIRef(records.address(DESCRIPTION) + "#" + "_".join(parts))


def partitions(void: Graph, dataset: URIRef, base: str) -> None:
    """A partition per class of the records and parts at the platform's addresses, with its entities and its
    properties (rdfsolve's VoID models, counted from the tables), and the name, description and position given in
    the catalogue for each kind of records; a kind without records is kept as the catalogue gives it."""
    named = {}
    for part in void.objects(dataset, VOID.classPartition):
        named[void.value(part, VOID["class"])] = part
    published = select(Record.iri).where(Record.iri.startswith(base), Record.part_of.is_(None), Record.removed_at.is_(None), Record.moved_to.is_(None))
    left_out = {str(field) for field in documents.private()}
    with database.engine().connect() as connection:
        found = patches.void_partitions(storage.profile(), connection, published, left_out, lambda *iris: str(name(*iris)))
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
    """A linkset per registry that the records' sameAs addresses are at, such as ORCID; the registry is a
    dataset of the description, with its site as its home page."""
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
    """The vocabulary terms that records link to, as a dataset with its dump and a part per vocabulary."""
    found = documents.published_terms()
    subset = URIRef(records.address(DESCRIPTION) + "#terms")
    void.add((dataset, VOID.subset, subset))
    void.add((subset, RDF.type, VOID.Dataset))
    void.add((subset, DCTERMS.title, Literal("Vocabulary terms that the records link to")))
    void.add((subset, VOID.dataDump, URIRef(records.address("api/dump/terms"))))
    void.add((subset, VOID.triples, Literal(len(found))))
    void.add((subset, VOID.entities, Literal(len(set(found.subjects(RDF.type, None))))))
    counted = Counter(found.objects(None, SDO.inDefinedTermSet))
    held = storage.graph(sorted(str(vocabulary) for vocabulary in counted))
    for vocabulary, count in sorted(counted.items()):
        part = URIRef(records.address(DESCRIPTION) + "#terms-" + patches.local_name(str(vocabulary)))
        void.add((subset, VOID.subset, part))
        void.add((part, RDF.type, VOID.Dataset))
        void.add((part, DCTERMS.source, vocabulary))
        void.add((part, VOID.entities, Literal(count)))
        for field, term in ((SDO.name, DCTERMS.title), (SDO.license, DCTERMS.license), (VOID.uriSpace, VOID.uriSpace)):
            for value in held.objects(vocabulary, field):
                void.add((part, term, value))


DESCRIBED = {}


def described() -> Graph:
    """The VoID description, made again when a record changes."""
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
