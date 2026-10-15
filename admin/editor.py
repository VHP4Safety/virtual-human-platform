"""What the record editor shows: how many records of each kind there are, the records of a kind, and the
graph from which shacl-form builds the form of a kind: the model's shapes, with the class hierarchy of the
vocabularies, and the records and vocabulary terms that a field can link to, with their names."""

from rdflib import RDF, RDFS, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH
from sqlalchemy import func, select

import database
from database.tables import PLATFORM, Note, Record
from linkeddata.model import hierarchy, settings, shapes, terms


def counts() -> list[dict]:
    """For each kind: its records, those written on the platform, those removed, and their notes."""
    found = []
    with database.session() as db:
        for name, kind in settings()["kinds"].items():
            of_kind = select(Record.iri).where(Record.type == kind)
            found.append({
                "kind": name,
                "records": db.scalar(select(func.count()).select_from(Record).where(Record.type == kind, Record.removed_at.is_(None))),
                "edited": db.scalar(select(func.count()).select_from(Record).where(Record.type == kind, Record.source == PLATFORM)),
                "removed": db.scalar(select(func.count()).select_from(Record).where(Record.type == kind, Record.removed_at.is_not(None))),
                "notes": db.scalar(select(func.count()).select_from(Note).where(Note.iri.in_(of_kind))),
            })
    return found


def listing(kind: str) -> list[Record]:
    """The records of a kind, the removed ones too, by name."""
    with database.session() as db:
        statement = select(Record).where(Record.type == settings()["kinds"][kind], Record.moved_to.is_(None))
        return list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri)))


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
