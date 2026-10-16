"""What the record editor shows: how many records of each kind there are and how complete they are, the
records of a kind, and the graph from which shacl-form builds the form of a kind: the application profile,
with the class hierarchy of the vocabularies, and the records and vocabulary terms that a field lists, with
their names."""

from rdflib import RDF, RDFS, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH
from sqlalchemy import func, select

import database
from database.tables import PLATFORM, Note, Record
from linkeddata import fields, storage
from linkeddata.model import hierarchy, profile, settings, terms


def counts() -> list[dict]:
    """For each kind: its records, those written on the platform, those removed, their notes, and how many
    of the kind's fields they fill, on average."""
    found = []
    with database.session() as db:
        for name, kind in settings()["kinds"].items():
            records_of_kind = select(Record.iri).where(Record.type == kind)
            of_kind = select(Record.iri).where(Record.iri.in_(records_of_kind) | Record.part_of.in_(records_of_kind))
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
    fills and how many of its values, or of its parts' values, do not fit the model."""
    of_kind = fields.of(settings()["kinds"][kind])
    with database.session() as db:
        statement = select(Record).where(Record.type == settings()["kinds"][kind], Record.moved_to.is_(None))
        listed = list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri)))
        holder = func.coalesce(Record.part_of, Record.iri)
        noted = dict(db.execute(select(holder, func.count()).select_from(Note).join(Record, Record.iri == Note.iri).where(holder.in_([record.iri for record in listed])).group_by(holder)).all())
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
    """The node shape of a kind's class in the profile, from which the form is built."""
    return str(fields.shape_of(settings()["kinds"][kind]))


def form_graph() -> Graph:
    """The profile, the class hierarchy, and every record and listed term (sh:in) with its name."""
    found = Graph() + profile() + hierarchy()
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.removed_at.is_(None), Record.moved_to.is_(None))):
            found.add((URIRef(iri), RDF.type, URIRef(kind)))
            found.add((URIRef(iri), RDFS.label, Literal(name or iri)))
    listed = []
    for collection in profile().objects(None, SH["in"]):
        for value in Collection(profile(), collection):
            if isinstance(value, URIRef):
                listed.append(str(value))
    for iri, term in terms(listed).items():
        found.add((URIRef(iri), RDFS.label, Literal(term["name"])))
    return found


def links() -> list[str]:
    """The properties of the fields that link to records: those of sh:class, or of sh:or of classes, whose
    values are not parts."""
    graph = profile()
    found = set()
    for field in graph.objects(None, SH.property):
        alternatives = list(graph.objects(field, SH["or"]))
        linked = graph.value(field, SH["class"]) is not None or bool(alternatives)
        part = graph.value(field, SH.node) is not None or graph.value(field, SH.nodeKind) == SH.BlankNode
        if linked and not part:
            found.add(str(graph.value(field, SH.path)))
    return sorted(found)
