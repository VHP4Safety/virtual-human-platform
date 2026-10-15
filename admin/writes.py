"""Records written on the platform, each change with its revision.

A record written on the platform replaces what a source gives for the same address, and the
imports leave it as it is. Every change made on the platform is kept as a revision, with who made it.
The body of a write gives the record's fields, as the write API describes it."""

import json
import re
from datetime import datetime, timezone

from rdflib import Graph, URIRef
from rdflib.namespace import SDO
from sqlalchemy import delete, insert, select

import database
from database.tables import PLATFORM, Record, Revision, now
from linkeddata import documents, fields, storage
from linkeddata.documents import context
from linkeddata.model import settings


def version() -> str:
    """The version of a record: when it was last written, to the microsecond, so that two writes differ."""
    return datetime.now(timezone.utc).isoformat()


def document(kind: str, address: str, body: dict) -> dict:
    """The JSON-LD document of a request's body: its fields, named as the platform's JSON-LD context names
    them, and the values that the model fixes. A field that the class does not have is refused."""
    known = {}
    for field in fields.of(kind):
        known[field["name"]] = field
    found = {"@context": context(settings()), "@id": address, "@type": documents.term(kind)}
    for name, value in body.items():
        if name.startswith("@"):
            continue
        if name not in known:
            raise ValueError(f"The platform does not keep the field {name!r}.")
        found[name] = value
    for name, field in known.items():
        if field["fixed"]:
            found[name] = [{"@id": value} for value in field["fixed"]]
    return found


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "record"


def save(document: dict, kind: str, name: str, orcid: str) -> Revision:
    """A record's document, checked against the model, is written on the platform in place of the record at
    its address, with its revision."""
    iri = document["@id"]
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        created = db.get(Record, iri) is None
        db.execute(delete(Record).where(Record.iri == iri))
        found = documents.statements(document)
        storage.save(db, found, iri)
        db.execute(insert(Record), [{**storage.row(found, iri, kind, PLATFORM), "updated_at": version()}])
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
    """The record is removed and its address is kept, so that it is never given to another record."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        record = db.get(Record, iri)
        record.removed_at = now()
        record.source = PLATFORM
        record.updated_at = version()
        revision = Revision(record_iri=iri, action="Removed", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def move(old: str, new: str, name: str, orcid: str) -> Revision:
    """The record moves to a new address. The old address forwards to it, the record keeps the old one
    among its other addresses (sameAs), and so do the addresses it had before."""
    previous = documents.document_of(old)
    with database.session() as db, db.begin():
        record = db.get(Record, old)
        moved = {}
        for column in Record.__table__.columns:
            moved[column.name] = getattr(record, column.name)
        found = Graph()
        for _, prop, value in storage.read([old]).triples((URIRef(old), None, None)):
            found.add((URIRef(new), prop, value))
        found.add((URIRef(new), SDO.sameAs, URIRef(old)))
        found.remove((URIRef(new), SDO.sameAs, URIRef(new)))
        # A record can move back to one of its earlier addresses; that address then stops forwarding.
        db.execute(delete(Record).where(Record.iri == new, Record.moved_to == old))
        storage.save(db, found, new)
        db.execute(insert(Record), [{**moved, "iri": new, "source": PLATFORM, "updated_at": version()}])
        record.removed_at = now()
        record.moved_to = new
        record.source = PLATFORM
        record.updated_at = version()
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
        record = db.get(Record, iri)
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
        db.execute(delete(Record).where(Record.iri == iri))
        revision = Revision(record_iri=iri, action="Removed permanently", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision
