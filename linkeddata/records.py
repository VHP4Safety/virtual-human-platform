"""The records, as the pages read them and as editors write them on the platform.

A record written on the platform replaces what a source gives for the same address, and the
imports leave it as it is. Every change made on the platform is kept as a revision, with who made it.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, select

from linkeddata import database, rdf
from linkeddata.database import PLATFORM, Record, Revision, now
from linkeddata.model import DASH, profile, property_shapes, settings


def version() -> str:
    """The version of a record: when it was last written, to the microsecond, so that two writes differ."""
    return datetime.now(timezone.utc).isoformat()


def address(path: str) -> str:
    return settings()["base"] + path.strip("/")


def get(iri: str) -> Record | None:
    with database.session() as db:
        return db.get(Record, iri)


def of_kind(kind: str) -> list[Record]:
    """The records that have a page under /<kind>/ and are not removed."""
    statement = select(Record).where(Record.iri.startswith(address(kind) + "/"), Record.removed_at.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))


def removed(kind: str) -> set[str]:
    """The identifiers of the removed records of a kind; the earlier addresses of moved records are not removed records."""
    prefix = address(kind) + "/"
    statement = select(Record.iri).where(Record.iri.startswith(prefix), Record.removed_at.is_not(None), Record.moved_to.is_(None))
    with database.session() as db:
        return {iri.removeprefix(prefix) for iri in db.scalars(statement)}


def moved(kind: str) -> set[str]:
    """The identifiers of the earlier addresses of records of a kind that moved."""
    prefix = address(kind) + "/"
    statement = select(Record.iri).where(Record.iri.startswith(prefix), Record.moved_to.is_not(None))
    with database.session() as db:
        return {iri.removeprefix(prefix) for iri in db.scalars(statement)}


def names(iris: list[str]) -> dict[str, str]:
    """The names of the records at these addresses."""
    with database.session() as db:
        return dict(db.execute(select(Record.iri, Record.name).where(Record.iri.in_(iris))).all())


def used_values(kind: str, field: str) -> list[str]:
    """The values that the records of a class have in a field with several values, most used first."""
    counts = {}
    with database.session() as db:
        for values in db.scalars(select(getattr(Record, field)).where(Record.type == kind, Record.removed_at.is_(None))):
            for value in values or []:
                counts[value] = counts.get(value, 0) + 1
    return sorted(counts, key=lambda value: (-counts[value], value))


def choices(kind: str, field: str) -> list[Record]:
    """The records that a field with several values can link to: all records of the classes that the
    records of *kind* link to in it, such as the steps of the glossary for "about"."""
    used = used_values(kind, field)
    with database.session() as db:
        classes = set(db.scalars(select(Record.type).where(Record.iri.in_(used))))
        statement = select(Record).where(Record.type.in_(classes), Record.removed_at.is_(None))
        return list(db.scalars(statement.order_by(Record.source, Record.iri)))


def duplicates(row: dict) -> dict[str, list[str]]:
    """The fields whose value another record of the class already has, where the application profile
    asks for a value that no other record has (dash:uniqueValueForClass)."""
    found = {}
    for path, nodes in property_shapes(profile(), row["type"]).items():
        for node in nodes:
            field = rdf.field_of_property(row["type"], path)
            value = row.get(field)
            if profile().value(node, DASH.uniqueValueForClass) is None or not isinstance(value, str) or not value:
                continue
            statement = select(Record).where(
                Record.type == row["type"],
                func.lower(getattr(Record, field)) == value.lower(),
                Record.iri != row["iri"],
                Record.removed_at.is_(None),
            )
            with database.session() as db:
                other = db.scalars(statement).first()
            if other is not None:
                path_of_other = "/" + other.iri.removeprefix(settings()["base"])
                found.setdefault(field, []).append(f"{other.name or other.iri} ({path_of_other}) has the same value.")
    return found


def document_of(iri: str) -> str | None:
    """The record at this address in JSON-LD as it is now; None when there is none."""
    found = rdf.graph([iri])
    if len(found) == 0:
        return None
    return json.dumps(rdf.document(found), indent=2)


def save(row: dict, document: dict, name: str, orcid: str, replace: bool = True) -> Revision:
    """The record of a row, checked with rdf.check, is written on the platform with its revision.
    It replaces the record at its address, unless *replace* is False."""
    previous = document_of(row["iri"]) if replace else None
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
    previous = document_of(iri)
    with database.session() as db, db.begin():
        record = db.get(Record, iri)
        record.removed_at = now()
        record.source = PLATFORM
        record.updated_at = version()
        revision = Revision(record_iri=iri, action="Removed", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def earlier_addresses(iri: str) -> list[str]:
    """The addresses that a record had before it moved to *iri*."""
    with database.session() as db:
        return list(db.scalars(select(Record.iri).where(Record.moved_to == iri)))


def move(old: str, new: str, name: str, orcid: str) -> Revision:
    """The record moves to a new address. The old address forwards to it, the record keeps the old one
    among its other addresses (sameAs), and so do the addresses it had before."""
    previous = document_of(old)
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
    document = document_of(new)
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
    document = document_of(iri)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=iri, action="Restored", document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def remove(iri: str, name: str, orcid: str) -> Revision:
    """The record and its address are removed; its revisions are kept."""
    previous = document_of(iri)
    with database.session() as db, db.begin():
        db.execute(delete(Record).where(Record.iri == iri))
        revision = Revision(record_iri=iri, action="Removed permanently", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def history(limit: int) -> list[Revision]:
    with database.session() as db:
        return list(db.scalars(select(Revision).order_by(Revision.id.desc()).limit(limit)))
