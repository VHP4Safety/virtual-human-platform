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
from linkeddata.document import context
from linkeddata.model import settings


def version() -> str:
    """The version of a record: when it was last written, to the microsecond, so that two writes differ."""
    return datetime.now(timezone.utc).isoformat()


def document(kind: str, address: str, body: dict) -> dict:
    """The JSON-LD document of a request's body: its fields, named as the form of *kind* names them. A
    link is {"@id": ...}, or a web address in a field that takes links. The values that the model fixes
    are set by the platform."""
    fields = {}
    for field in forms.form(kind):
        fields[field["name"]] = field
    found = {"@context": context(settings()), "@id": address, "@type": rdf.term(kind)}
    for name, value in body.items():
        if name.startswith("@"):
            continue
        if name not in fields:
            raise ValueError(f"The platform does not keep the field {name!r}.")
        items = []
        for item in value if isinstance(value, list) else [value]:
            # A link is {"@id": ...}, with a "name" when it is a page that the record gives with its title.
            if isinstance(item, dict) and "@id" in item and set(item) <= {"@id", "name"}:
                items.append({"@id": item["@id"]})
            elif fields[name]["links"] and isinstance(item, str) and item.startswith(("https://", "http://")):
                items.append({"@id": item})
            else:
                items.append(item)
        if not items:
            continue
        if len(items) > 1 and not fields[name]["several"]:
            raise ValueError(f"{name}: the platform keeps one value.")
        found[name] = items if fields[name]["several"] else items[0]
    for name, field in fields.items():
        if field["fixed"]:
            found[name] = [{"@id": value} for value in field["fixed"]]
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
                document = {"@context": context(settings()), "@id": iri, "@type": rdf.term(kind), "name": name}
                db.add(Record(iri=iri, type=kind, source=PLATFORM, name=name, document=document))
            elif thing.name != name:
                thing.name = name
                thing.document = {**thing.document, "name": name}
                thing.source = PLATFORM
                thing.updated_at = version()


def save(document: dict, kind: str, name: str, orcid: str, replace: bool = True) -> Revision:
    """A record's document, checked with rdf.check, is written on the platform with its revision.
    It replaces the record at its address, unless *replace* is False."""
    iri = document["@id"]
    previous = rdf.document_of(iri) if replace else None
    with database.session() as db, db.begin():
        created = db.get(Record, iri) is None
        if replace:
            db.execute(delete(Record).where(Record.iri == iri))
        db.execute(insert(Record), [{**rdf.row(document, kind, PLATFORM), "updated_at": version()}])
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
        same_as = rdf.values(record.document, "sameAs")
        if old not in same_as:
            same_as.append(old)
        if new in same_as:
            same_as.remove(new)
        document = {**record.document, "@id": new, "sameAs": [{"@id": address} for address in same_as]}
        # A record can move back to one of its earlier addresses; that address then stops forwarding.
        db.execute(delete(Record).where(Record.iri == new, Record.moved_to == old))
        db.execute(insert(Record), [{**moved, "iri": new, "source": PLATFORM, "updated_at": version(), "document": document}])
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
