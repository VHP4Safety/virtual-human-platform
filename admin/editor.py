"""What the record editor shows: how many records of each kind there are and how complete they are, the
records of a kind, and the graph from which shacl-form builds the form of a kind: the model's shapes, with
the class hierarchy of the vocabularies, and the records and vocabulary terms that a field can link to,
with their names."""

from rdflib import RDF, RDFS, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH
from sqlalchemy import func, select

import database
from database.tables import PLATFORM, Note, Record
from linkeddata import fields, storage
from linkeddata.model import hierarchy, settings, shapes, terms


def counts() -> list[dict]:
    """For each kind: its records, those written on the platform, those removed, their notes, and how many
    of the kind's fields they fill, on average."""
    found = []
    with database.session() as db:
        for name, kind in settings()["kinds"].items():
            of_kind = select(Record.iri).where(Record.type == kind)
            listed = listing(name)
            filled = 0
            for item in listed:
                filled += item["filled"]
            found.append({
                "kind": name,
                "records": db.scalar(select(func.count()).select_from(Record).where(Record.type == kind, Record.removed_at.is_(None))),
                "edited": db.scalar(select(func.count()).select_from(Record).where(Record.type == kind, Record.source == PLATFORM)),
                "removed": db.scalar(select(func.count()).select_from(Record).where(Record.type == kind, Record.removed_at.is_not(None))),
                "notes": db.scalar(select(func.count()).select_from(Note).where(Note.iri.in_(of_kind))),
                "complete": round(100 * filled / (len(listed) * len(fields.of(kind)))) if listed else 0,
            })
    return found


def listing(kind: str) -> list[dict]:
    """The records of a kind, the removed ones too, by name, each with how many of the kind's fields it
    fills and how many of its values do not fit the model."""
    of_kind = fields.of(settings()["kinds"][kind])
    with database.session() as db:
        statement = select(Record).where(Record.type == settings()["kinds"][kind], Record.moved_to.is_(None))
        listed = list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri)))
        noted = dict(db.execute(select(Note.iri, func.count()).where(Note.iri.in_([record.iri for record in listed])).group_by(Note.iri)).all())
    found = storage.read([record.iri for record in listed])
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
    """The node shape of a kind's class in the model's shapes, from which the form is built."""
    return str(shapes().value(None, SH.targetClass, URIRef(settings()["kinds"][kind])))


def form_graph() -> Graph:
    """The model's shapes, the class hierarchy, and every record and listed term (sh:in) with its name."""
    found = Graph() + shapes() + hierarchy()
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.removed_at.is_(None), Record.moved_to.is_(None))):
            found.add((URIRef(iri), RDF.type, URIRef(kind)))
            found.add((URIRef(iri), RDFS.label, Literal(name or iri)))
    listed = []
    for collection in shapes().objects(None, SH["in"]):
        for value in Collection(shapes(), collection):
            if isinstance(value, URIRef):
                listed.append(str(value))
    for iri, term in terms(listed).items():
        found.add((URIRef(iri), RDFS.label, Literal(term["name"])))
    return found
