"""The records, as the pages and the editor read them."""

import re

from rdflib import RDFS, URIRef
from sqlalchemy import func, select

import database
from database.tables import Record
from linkeddata.model import hierarchy, settings, terms


def address(path: str) -> str:
    """A record's address from its page's path: a path under the base address, or a whole address
    elsewhere, such as an ontology term (https:/... is read as https://...)."""
    whole = re.fullmatch(r"(https?):/+(.*)", path)
    if whole:
        return whole.group(1) + "://" + whole.group(2)
    return settings()["base"] + path.strip("/")


def path(iri: str) -> str:
    """A record's path under the base address (the inverse of address()); an address elsewhere as it is."""
    return iri.removeprefix(settings()["base"])


def get(iri: str) -> Record | None:
    with database.session() as db:
        return db.get(Record, iri)


def of_kind(kind: str) -> list[Record]:
    """The records that have a page under /<kind>/ and are not removed."""
    statement = select(Record).where(Record.iri.startswith(address(kind) + "/"), Record.removed_at.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))


def search(text: str, classes: list[str], within: str = "", parts: bool = True, limit: int | None = 20, among=None) -> list[Record]:
    """The records of these classes or their subclasses (parts too, unless *parts* is false) whose name or
    address has *text*, whose address starts with *within*, such as a vocabulary namespace, and that are
    *among* a select of addresses, such as a vocabulary's terms; by name."""
    every = set(classes)
    for of_class in classes:
        every |= {str(sub) for sub in hierarchy().transitive_subjects(RDFS.subClassOf, URIRef(of_class))}
    statement = select(Record).where(Record.type.in_(every), Record.removed_at.is_(None), Record.moved_to.is_(None))
    if text:
        statement = statement.where(func.lower(Record.name).contains(text.lower()) | Record.iri.contains(text))
    if within:
        statement = statement.where(Record.iri.startswith(within))
    if among is not None:
        statement = statement.where(Record.iri.in_(among))
    if not parts:
        statement = statement.where(Record.part_of.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri).limit(limit)))


def latest_change() -> str:
    """When a record was last written, removed or moved, in UTC (ISO 8601)."""
    with database.session() as db:
        found = [db.scalar(select(func.max(Record.updated_at))), db.scalar(select(func.max(Record.removed_at)))]
    return max([value for value in found if value] or [""])


def with_pages() -> list[tuple[str, str]]:
    """The address and last change of each record with a page on the platform: not a part, not removed or
    moved, at the platform's base."""
    with database.session() as db:
        return list(db.execute(select(Record.iri, Record.updated_at).where(
            Record.iri.startswith(settings()["base"]), Record.part_of.is_(None), Record.removed_at.is_(None),
            Record.moved_to.is_(None)).order_by(Record.iri)).all())


def kept(iris: list[str]) -> list[Record]:
    """The records and parts at these addresses that are not removed or moved."""
    with database.session() as db:
        return list(db.scalars(select(Record).where(Record.iri.in_(iris), Record.removed_at.is_(None), Record.moved_to.is_(None))))


def names(iris: list[str]) -> dict[str, str]:
    """The names of the records at these addresses, and the labels of vocabulary terms."""
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


def kinds_of(term: str) -> list[Record]:
    """The terms named as kinds of a term, the glossary's way: "<name> (<term's name>)"; by address."""
    named = get(term)
    if named is None or not named.name:
        return []
    statement = select(Record).where(Record.name.endswith(f" ({named.name})"), Record.removed_at.is_(None), Record.moved_to.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))
