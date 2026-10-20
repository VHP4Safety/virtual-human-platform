"""What the record editor shows: counts and completeness per kind, the records of a kind, and the graph
shacl-form builds forms from (the profile, the vocabularies' class hierarchy, and named records and terms)."""

from rdflib import RDF, RDFS, XSD, BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SDO, SH
from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Note, Record
from linkeddata.profile import fields, hierarchy, jsonld_name, profile_graph, settings, shape_of, terms


def counts() -> list[dict]:
    """Per kind: its records, those written on the platform, those removed, their notes, and the average
    share of fields filled."""
    found = []
    with database.session() as db:
        for name, kind in settings()["kinds"].items():
            records_of_kind = select(Record.iri).where(Record.type.in_(records.within(kind)))
            of_kind = select(Record.iri).where(Record.iri.in_(records_of_kind) | Record.part_of.in_(records_of_kind))
            listed = listing(name)
            filled = 0
            for item in listed:
                filled += item["filled"]
            found.append({
                "kind": name,
                "records": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.removed_at.is_(None))),
                "edited": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.source == PLATFORM)),
                "removed": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.removed_at.is_not(None))),
                "notes": db.scalar(select(func.count()).select_from(Note).where(Note.iri.in_(of_kind))),
                "complete": round(100 * filled / (len(listed) * len(fields(kind)))) if listed else 0,
            })
    return found


def listing(kind: str) -> list[dict]:
    """A kind's records, removed ones too, by name, each with its filled fields and its notes (parts
    included)."""
    of_kind = fields(settings()["kinds"][kind])
    with database.session() as db:
        statement = select(Record).where(Record.type.in_(records.within(settings()["kinds"][kind])), Record.moved_to.is_(None))
        listed = list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri)))
        holder = func.coalesce(Record.part_of, Record.iri)
        noted = dict(db.execute(select(holder, func.count()).select_from(Note).join(Record, Record.iri == Note.iri).where(holder.in_([record.iri for record in listed])).group_by(holder)).all())
    found = records.read([record.iri for record in listed])
    rows = []
    for record in listed:
        given = set()
        for predicate in found.predicates(URIRef(record.iri)):
            given.add(str(predicate))
        filled = 0
        for field in of_kind:
            if field["iri"] in given:
                filled += 1
        rows.append({"record": record, "filled": filled, "fields": len(of_kind), "notes": noted.get(record.iri, 0)})
    return rows


def root_shape(kind: str) -> str:
    """The node shape of a kind's class in the profile, from which the form is built."""
    return str(shape_of(settings()["kinds"][kind]))


def form_graph() -> Graph:
    """The profile, the class hierarchy, every record and listed term (sh:in) with its name, and each term's
    vocabulary. An sh:or of
    classes gets two more choices, a text and an address, so the form shows a bare name or an address that is
    no record; neither takes a value (an empty sh:in), so the form flags it with the field's message."""
    found = Graph() + profile_graph() + hierarchy()
    for alternatives in list(found.objects(None, SH["or"])):
        listed = Collection(found, alternatives)
        classes = 0
        for alternative in listed:
            if found.value(alternative, SH["class"]) is not None:
                classes += 1
        if classes == len(listed):
            text = BNode()
            found.add((text, SH.datatype, XSD.string))
            found.add((text, RDFS.label, Literal("Text")))
            found.add((text, SH["in"], RDF.nil))
            listed.append(text)
            address = BNode()
            found.add((address, SH.nodeKind, SH.IRI))
            found.add((address, RDFS.label, Literal("Address")))
            found.add((address, SH["in"], RDF.nil))
            listed.append(address)
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.removed_at.is_(None), Record.moved_to.is_(None))):
            found.add((URIRef(iri), RDF.type, URIRef(kind)))
            found.add((URIRef(iri), RDFS.label, Literal(name or iri)))
    # Each term's vocabulary, so a term is shown in its own.
    for iri, vocabulary in records.values(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet)):
        found.add((URIRef(iri), SDO.inDefinedTermSet, URIRef(vocabulary)))
    listed = []
    for collection in profile_graph().objects(None, SH["in"]):
        for value in Collection(profile_graph(), collection):
            if isinstance(value, URIRef):
                listed.append(str(value))
    for iri, term in terms(listed).items():
        found.add((URIRef(iri), RDFS.label, Literal(term["name"])))
    return found


def mixed() -> list[str]:
    """The properties of fields whose sh:or offers a link or another value, such as an address."""
    graph = profile_graph()
    found = []
    for field in graph.objects(None, SH.property):
        for alternatives in graph.objects(field, SH["or"]):
            listed = list(graph.items(alternatives))
            classes = 0
            for alternative in listed:
                if graph.value(alternative, SH["class"]) is not None:
                    classes += 1
            if 0 < classes < len(listed):
                found.append(str(graph.value(field, SH.path)))
    return found


def links() -> dict[str, dict[str, str]]:
    """The properties of fields that link to records (sh:class, or sh:or of classes, without parts), each
    with its classes by label: the sh:or choice's, else the class shape's, else the class's own name."""
    graph = profile_graph()
    found = {}
    for field in graph.objects(None, SH.property):
        if graph.value(field, SH.node) is not None or graph.value(field, SH.nodeKind) == SH.BlankNode:
            continue
        named = []
        for of_class in graph.objects(field, SH["class"]):
            named.append((of_class, None))
        for alternatives in graph.objects(field, SH["or"]):
            for alternative in graph.items(alternatives):
                for of_class in graph.objects(alternative, SH["class"]):
                    named.append((of_class, graph.value(alternative, RDFS.label)))
        for of_class, label in named:
            label = label or graph.value(graph.value(None, SH.targetClass, of_class), RDFS.label) or jsonld_name(str(of_class)).split(":")[-1]
            found.setdefault(str(graph.value(field, SH.path)), {}).setdefault(str(of_class), str(label))
    return found
