"""Records written on the platform, each change with its revision.

A record written on the platform replaces what a source gives for the same address, and the
imports leave it as it is. Every change made on the platform is kept as a revision, with who made it.
The body of a write gives the record's fields, as the write API describes it."""

import json
import re
from datetime import datetime, timezone

from sqlalchemy import delete, insert, select

import database
from database.tables import PLATFORM, Record, Revision, now
from linkeddata import forms, rdf


def version() -> str:
    """The version of a record: when it was last written, to the microsecond, so that two writes differ."""
    return datetime.now(timezone.utc).isoformat()


def values(kind: str, body: dict) -> dict[str, list]:
    """The fields of a request's body, named as in the database, each with a list of values. The
    values that the application profile fixes are set by the platform."""
    found = {}
    for name, value in body.items():
        if name.startswith("@"):
            continue
        items = []
        for item in value if isinstance(value, list) else [value]:
            # A link is {"@id": ...}, with a "name" when it is a page that the record gives with its title.
            if isinstance(item, dict) and "@id" in item and set(item) <= {"@id", "name"}:
                items.append(item["@id"])
            else:
                items.append(item)
        found[rdf.field_of(kind, name)] = items
    for field in forms.form(kind):
        if field["fixed"]:
            found[field["name"]] = field["fixed"]
    return found


def titled(kind: str, body: dict) -> list[tuple[str, str, str]]:
    """The pages that a request's body gives with their titles, in the fields the profile edits as
    details (dash:DetailsEditor): (class, address, title)."""
    found = []
    for field in forms.form(kind):
        if field["entry"] != "details":
            continue
        for item in body.get(field["name"]) or []:
            if isinstance(item, dict) and isinstance(item.get("@id"), str) and isinstance(item.get("name"), str) and item["name"].strip():
                found.append((field["class"], item["@id"], item["name"].strip()))
    return found


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "record"


def together(*found: dict[str, list[str]]) -> dict[str, list[str]]:
    """The messages of several checks, by field."""
    joined = {}
    for messages in found:
        for field, listed in messages.items():
            joined.setdefault(field, []).extend(listed)
    return joined


def name_things(found: list[tuple[str, str, str]]) -> None:
    """The things a record links to with their titles, such as its guides: (class, address, name).
    A thing the platform does not know yet is added; a known one takes the new name."""
    with database.session() as db, db.begin():
        for kind, iri, name in found:
            thing = db.get(Record, iri)
            if thing is None:
                db.add(Record(iri=iri, type=kind, source=PLATFORM, name=name))
            elif thing.name != name:
                thing.name = name
                thing.source = PLATFORM
                thing.updated_at = version()


def save(row: dict, document: dict, name: str, orcid: str, replace: bool = True) -> Revision:
    """The record of a row, checked with rdf.check, is written on the platform with its revision.
    It replaces the record at its address, unless *replace* is False."""
    previous = rdf.document_of(row["iri"]) if replace else None
    with database.session() as db, db.begin():
        created = db.get(Record, row["iri"]) is None
        if replace:
            db.execute(delete(Record).where(Record.iri == row["iri"]))
        db.execute(insert(Record), [{**row, "source": PLATFORM, "updated_at": version()}])
        revision = Revision(
            record_iri=row["iri"],
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
    previous = rdf.document_of(iri)
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
    previous = rdf.document_of(old)
    with database.session() as db, db.begin():
        record = db.get(Record, old)
        moved = {}
        for column in Record.__table__.columns:
            moved[column.name] = getattr(record, column.name)
        same_as = list(record.same_as or [])
        if old not in same_as:
            same_as.append(old)
        if new in same_as:
            same_as.remove(new)
        # A record can move back to one of its earlier addresses; that address then stops forwarding.
        db.execute(delete(Record).where(Record.iri == new, Record.moved_to == old))
        db.execute(insert(Record), [{**moved, "iri": new, "source": PLATFORM, "updated_at": version(), "same_as": same_as}])
        record.removed_at = now()
        record.moved_to = new
        record.source = PLATFORM
        record.updated_at = version()
        for earlier in db.scalars(select(Record).where(Record.moved_to == old)):
            earlier.moved_to = new
    document = rdf.document_of(new)
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
    document = rdf.document_of(iri)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=iri, action="Restored", document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def remove(iri: str, name: str, orcid: str) -> Revision:
    """The record and its address are removed; its revisions are kept."""
    previous = rdf.document_of(iri)
    with database.session() as db, db.begin():
        db.execute(delete(Record).where(Record.iri == iri))
        revision = Revision(record_iri=iri, action="Removed permanently", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision
