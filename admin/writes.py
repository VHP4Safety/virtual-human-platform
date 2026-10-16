"""Records written on the platform, each change with its revision.

A record written on the platform replaces a source's record at the same address, and is left alone by
imports. Each change is kept as a revision, with its author. A write's body gives the record's fields."""

import json
import re
from datetime import datetime, timezone

from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SDO
from sqlalchemy import delete, insert, select

import database
from database import records
from database.tables import PLATFORM, Record, Revision, now
from linkeddata import documents, fields, storage
from linkeddata.documents import context
from linkeddata.model import settings


def version() -> str:
    """A record's version: its last write time, to the microsecond, so two writes differ."""
    return datetime.now(timezone.utc).isoformat()


def document(kind: str, address: str, body: dict) -> dict:
    """A request body as a JSON-LD document, with the values the model fixes; an unknown field is refused."""
    known = {}
    for field in fields.of(kind):
        known[field["name"]] = field
    found = {"@context": context(settings()), "@id": address, "@type": documents.term(kind)}
    for name, value in body.items():
        if name.startswith("@"):
            continue
        if name not in known:
            raise ValueError(f"Unknown field {name!r}.")
        found[name] = value
    for name, field in known.items():
        if field["fixed"]:
            found[name] = [{"@id": value} for value in field["fixed"]]
    return found


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "record"


def part(found: Graph, node: BNode) -> bool:
    """Whether a node is held in a field of parts."""
    for holder, predicate in found.subject_predicates(node):
        for field in fields.of(str(found.value(holder, RDF.type))):
            if field["iri"] == str(predicate) and field["part"]:
                return True
    return False


def free(base: str, taken: set) -> str:
    """A free address, not in *taken*: *base*, or *base*-2, -3, ...; <kind>/facets is kept for the API."""
    iri, number = base, 1
    while iri in taken or records.get(iri) is not None or iri.endswith("/facets"):
        number += 1
        iri = f"{base}-{number}"
    taken.add(iri)
    return iri


def renamed(found: Graph, node, iri: str) -> None:
    """The node is given the address *iri* in *found*."""
    for predicate, value in list(found.predicate_objects(node)):
        found.remove((node, predicate, value))
        found.add((URIRef(iri), predicate, value))
    for subject, predicate in list(found.subject_predicates(node)):
        found.remove((subject, predicate, node))
        found.add((subject, predicate, URIRef(iri)))


def addressed(found: Graph) -> None:
    """New parts with addresses of their own (sh:nodeKind sh:IRI), such as a new step of a question, are
    given one under their holder's, from their name (casestudies/kidney/Q1/exposure)."""
    taken = set()
    pending = True
    while pending:
        pending = False
        for holder, predicate, node in list(found):
            if not isinstance(node, BNode) or not isinstance(holder, URIRef):
                continue
            for field in fields.of(str(found.value(holder, RDF.type))):
                if field["iri"] == str(predicate) and field["addressed"]:
                    renamed(found, node, free(f"{holder}/{slug(str(found.value(node, SDO.name) or 'page'))}", taken))
                    pending = True


def separate(found: Graph) -> list[tuple[str, str, Graph]]:
    """New records held as nodes without an address, such as a person added in the form: a node of a
    kind's class, unless in a field of parts, becomes a record at <kind>/<name>, linked from the record.
    Their statements are taken out of *found*; each is given with its class."""
    kinds = {}
    for kind_name, kind in settings()["kinds"].items():
        kinds[URIRef(kind)] = kind_name
    created = []
    taken = set()
    for node, kind in list(found.subject_objects(RDF.type)):
        if not isinstance(node, BNode) or kind not in kinds or part(found, node):
            continue
        name = found.value(node, SDO.name)
        iri = free(records.address(f"{kinds[kind]}/{slug(str(name or kinds[kind]))}"), taken)
        own = Graph()
        for subject, predicate, value in storage.described(found, node):
            found.remove((subject, predicate, value))
            own.add((URIRef(iri) if subject == node else subject, predicate, value))
        for subject, predicate in list(found.subject_predicates(node)):
            found.remove((subject, predicate, node))
            found.add((subject, predicate, URIRef(iri)))
        created.append((iri, str(kind), own))
    return created


def save(document: dict, kind: str, name: str, orcid: str) -> Revision:
    """A checked record document replaces the record at its address, with a revision."""
    iri = document["@id"]
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        created = db.get(Record, iri) is None
        db.execute(delete(Record).where((Record.iri == iri) | (Record.part_of == iri)))
        found = documents.statements(document)
        storage.save(db, found, iri)
        db.execute(insert(Record), [{**row, "updated_at": version()} for row in storage.rows(found, iri, kind, PLATFORM)])
        revision = Revision(
            record_iri=iri,
            action="Added" if created else "Changed",
            previous=previous,
            document=json.dumps(document, indent=2),
            name=name,
            orcid=orcid,
        )
        db.add(revision)
    return revision


def retire(iri: str, name: str, orcid: str) -> Revision:
    """The record is removed; its address is kept, so it is never reused."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        for record in db.scalars(select(Record).where((Record.iri == iri) | (Record.part_of == iri))):
            record.removed_at = now()
            record.source = PLATFORM
            record.updated_at = version()
        revision = Revision(record_iri=iri, action="Removed", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def move(old: str, new: str, name: str, orcid: str) -> Revision:
    """The record and its addressed parts move to a new address. The old addresses, and earlier ones,
    forward to the new ones; the old one is kept in sameAs."""
    previous = documents.document_of(old)

    def moved(node):
        if isinstance(node, URIRef) and (str(node) == old or str(node).startswith(old + "/")):
            return URIRef(new + str(node).removeprefix(old))
        return node

    with database.session() as db, db.begin():
        record = db.get(Record, old)
        found = Graph()
        for subject, prop, value in storage.read([old]):
            found.add((moved(subject), prop, moved(value)))
        found.add((URIRef(new), SDO.sameAs, URIRef(old)))
        found.remove((URIRef(new), SDO.sameAs, URIRef(new)))
        # A record can move back to one of its earlier addresses; that address then stops forwarding.
        db.execute(delete(Record).where(((Record.iri == new) | Record.iri.startswith(new + "/")), ((Record.moved_to == old) | Record.moved_to.startswith(old + "/"))))
        storage.save(db, found, new)
        db.execute(insert(Record), [{**row, "updated_at": version()} for row in storage.rows(found, new, record.type, PLATFORM)])
        for kept in db.scalars(select(Record).where((Record.iri == old) | (Record.part_of == old))):
            kept.removed_at = now()
            kept.moved_to = str(moved(URIRef(kept.iri)))
            kept.source = PLATFORM
            kept.updated_at = version()
        for earlier in db.scalars(select(Record).where(Record.moved_to == old)):
            earlier.moved_to = new
    document = documents.document_of(new)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=new, action="Moved", previous=previous, document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def restore(iri: str, name: str, orcid: str) -> Revision:
    """A removed record is put back as it was when it was removed."""
    with database.session() as db, db.begin():
        for record in db.scalars(select(Record).where((Record.iri == iri) | (Record.part_of == iri))):
            record.removed_at = None
            record.updated_at = version()
    document = documents.document_of(iri)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=iri, action="Restored", document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def remove(iri: str, name: str, orcid: str) -> Revision:
    """The record and its address are removed; its revisions are kept."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        storage.delete(db, iri)
        db.execute(delete(Record).where((Record.iri == iri) | (Record.part_of == iri)))
        revision = Revision(record_iri=iri, action="Removed permanently", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision
