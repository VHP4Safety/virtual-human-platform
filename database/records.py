"""The records, as the pages and the editor read them."""

from sqlalchemy import select

import database
from database.tables import Record
from linkeddata.model import settings, terms


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
    """The names of the records at these addresses, and the labels of the terms of the vocabularies."""
    with database.session() as db:
        found = dict(db.execute(select(Record.iri, Record.name).where(Record.iri.in_(iris))).all())
    others = []
    for iri in iris:
        if iri not in found:
            others.append(iri)
    for iri, term in terms(others).items():
        found[iri] = term["name"]
    return found


def earlier_addresses(iri: str) -> list[str]:
    """The addresses that a record had before it moved to *iri*."""
    with database.session() as db:
        return list(db.scalars(select(Record.iri).where(Record.moved_to == iri)))
