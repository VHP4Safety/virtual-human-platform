"""The records, as the pages read them and as editors write them on the platform.

A record written on the platform replaces what a source gives for the same address, and the
imports leave it as it is. Every change made on the platform is kept as a revision, with who made it.
"""

import json

from sqlalchemy import delete, insert, select

from linkeddata import database, rdf
from linkeddata.database import PLATFORM, Record, Revision, now
from linkeddata.model import settings


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
    """The identifiers of the removed records of a kind."""
    prefix = address(kind) + "/"
    statement = select(Record.iri).where(Record.iri.startswith(prefix), Record.removed_at.is_not(None))
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
        db.execute(insert(Record), [{**row, "source": PLATFORM, "updated_at": now()}])
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
        revision = Revision(record_iri=iri, action="Removed", previous=previous, name=name, orcid=orcid)
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
