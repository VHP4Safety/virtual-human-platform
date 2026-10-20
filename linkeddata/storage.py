"""Record storage: statements as rows of the release's tables (database/v1/tables.sql), converted both
ways by rdfsolve (rdfsolve.client.sql_tables) and written by pandas. Each row names its record, parts
included (nodes without an address, and addresses under the record's), so a record is read and removed by
its address."""

import logging
from functools import cache

import pandas as pd
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import SDO
from rdfsolve.client.sql_tables import from_tables, layout, tables
from sqlalchemy import bindparam, column, select, table, text

import database
from database.tables import Record
from linkeddata.model import profile_text, settings

# An HTML text that does not parse is flagged by the checks; rdflib's warning on each read is left out.
logging.getLogger("rdflib.term").setLevel(logging.ERROR)


@cache
def profile() -> str:
    """The application profile, whose prefixes name the tables and columns."""
    return profile_text()


def names() -> list[str]:
    return list(layout(profile()).columns())


@cache
def reading() -> dict:
    """For each table of the release, the select of some records' rows."""
    found = {}
    for name, columns in layout(profile()).columns().items():
        of_table = table(name, *[column(name_of_column) for name_of_column in columns])
        found[name] = select(of_table).where(of_table.c.record.in_(bindparam("records", expanding=True)))
    return found


def read(records: list[str]) -> Graph:
    """The statements of these records, from their rows; only tables with rows are given to rdfsolve."""
    if not records:
        return Graph()
    found = {}
    with database.engine().connect() as connection:
        for name, statement in reading().items():
            result = connection.execute(statement, {"records": list(records)})
            rows = result.all()
            if rows:
                found[name] = pd.DataFrame(rows, columns=list(result.keys()), dtype="string")
    return from_tables(found, profile())


def delete(db, record: str) -> None:
    """A record's rows are removed in the session *db*."""
    for name in names():
        db.execute(text(f'DELETE FROM "{name}" WHERE record = :record'), {"record": record})


def save(db, found: Graph, record: str) -> None:
    """A record's statements, its parts' included, replace its rows in the session *db*."""
    delete(db, record)
    for name, frame in tables(found, profile(), empty=False).items():
        frame["record"] = record
        frame.to_sql(name, db.connection(), index=False, if_exists="append")


def described(found: Graph, iri: str | BNode) -> Graph:
    """The statements of the record at *iri* (or of a node without an address), with its parts' at any
    depth: nodes without an address, and addresses under its own (casestudies/kidney/Q1)."""
    own = Graph()
    nodes = [iri if isinstance(iri, BNode) else URIRef(iri)]
    seen = set()
    while nodes:
        node = nodes.pop()
        if node in seen:
            continue
        seen.add(node)
        for statement in found.triples((node, None, None)):
            own.add(statement)
            value = statement[2]
            if isinstance(value, BNode) or (isinstance(value, URIRef) and str(value).startswith(str(node) + "/")):
                nodes.append(value)
    return own


def rows(found: Graph, iri: str, kind: str, source: str) -> list[dict]:
    """The records table's rows of a record and its addressed parts, each with its class and name."""
    listed = {iri: kind}
    for subject in described(found, iri).subjects():
        if isinstance(subject, URIRef) and str(subject) not in listed and found.value(subject, RDF.type) is not None:
            listed[str(subject)] = str(found.value(subject, RDF.type))
    found_rows = []
    for subject, of_class in listed.items():
        name = found.value(URIRef(subject), SDO.name)
        found_rows.append({"iri": subject, "type": of_class, "source": source, "name": str(name) if name is not None else None,
                           "part_of": None if subject == iri else iri})
    return found_rows


def graph(iris: list[str]) -> Graph:
    """The records at these addresses that are not removed, as linked data; parts are read from their records."""
    with database.session() as db:
        kept = list(db.execute(select(Record.iri, Record.part_of).where(Record.iri.in_(iris), Record.removed_at.is_(None))))
    held = read(sorted({part_of or iri for iri, part_of in kept}))
    found = Graph()
    for iri, _ in kept:
        found += described(held, iri)
    for prefix, namespace in settings()["prefixes"].items():
        found.bind(prefix, namespace)
    return found


def with_names(found: Graph) -> Graph:
    """The statements with the class and name of the records they link to, so the links are named. An address
    of the same thing elsewhere (sameAs) is an address, not a record to name."""
    linked = set()
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != SDO.sameAs and (value, None, None) not in found:
            linked.add(str(value))
    named = Graph() + found
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.iri.in_(linked))):
            named.add((URIRef(iri), RDF.type, URIRef(kind)))
            if name:
                named.add((URIRef(iri), SDO.name, Literal(name)))
    for prefix, namespace in settings()["prefixes"].items():
        named.bind(prefix, namespace)
    return named
