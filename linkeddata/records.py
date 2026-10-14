"""The records, as the pages read them and as editors write them on the platform.

A record written on the platform replaces what a source gives for the same address, and the
imports leave it as it is. Every change made on the platform is kept as a revision, with who made it.
"""

import json

from sqlalchemy import delete, insert, select

from linkeddata import database
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


def save(row: dict, document: dict, name: str, orcid: str, replace: bool = True) -> bool:
    """The record of a row, checked with rdf.check, is written on the platform with its revision.
    It replaces the record at its address, unless *replace* is False; it returns True when it is new."""
    with database.session() as db, db.begin():
        created = db.get(Record, row["iri"]) is None
        if replace:
            db.execute(delete(Record).where(Record.iri == row["iri"]))
        db.execute(insert(Record), [{**row, "source": PLATFORM, "updated_at": now()}])
        db.add(Revision(
            record_iri=row["iri"],
            action="Added" if created else "Changed",
            document=json.dumps(document, indent=2),
            name=name,
            orcid=orcid,
        ))
    return created


def retire(iri: str, name: str, orcid: str) -> None:
    """The record is removed and its address is kept, so that it is never given to another record."""
    with database.session() as db, db.begin():
        record = db.get(Record, iri)
        record.removed_at = now()
        record.source = PLATFORM
        db.add(Revision(record_iri=iri, action="Removed", name=name, orcid=orcid))


def remove(iri: str, name: str, orcid: str) -> None:
    """The record and its address are removed; its revisions are kept."""
    with database.session() as db, db.begin():
        db.execute(delete(Record).where(Record.iri == iri))
        db.add(Revision(record_iri=iri, action="Removed permanently", name=name, orcid=orcid))


def history(limit: int) -> list[Revision]:
    with database.session() as db:
        return list(db.scalars(select(Revision).order_by(Revision.id.desc()).limit(limit)))
