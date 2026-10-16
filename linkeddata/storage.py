"""Where records are kept: their statements as rows of the tables of the model's release
(database/v1/tables.sql). rdfsolve gives the rows of a graph, which pandas writes, and makes the graph
again from them (rdfsolve.client.sql_tables). Every row names the record it belongs to, its parts
included (the nodes without an address that it holds, and those at addresses under its own), so a record
is read and removed by its address."""

from functools import cache

import pandas as pd
from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SDO
from rdfsolve.client.sql_tables import from_tables, layout, tables
from sqlalchemy import bindparam, select, text

import database
from database.tables import Record
from linkeddata.model import MODEL_DIR, settings


@cache
def profile() -> str:
    """The application profile, whose prefixes name the tables and their columns."""
    return (MODEL_DIR / "profile.ttl").read_text(encoding="utf-8")


def names() -> list[str]:
    return list(layout(profile()).columns())


def read(records: list[str]) -> Graph:
    """The statements of these records, made from their rows."""
    if not records:
        return Graph()
    found = {}
    with database.engine().connect() as connection:
        for name in names():
            query = text(f'SELECT * FROM "{name}" WHERE record IN :records').bindparams(bindparam("records", expanding=True))
            found[name] = pd.read_sql(query, connection, params={"records": list(records)}, dtype="string")
    return from_tables(found, profile())


def delete(db, record: str) -> None:
    """The rows of a record are removed in the session *db*."""
    for name in names():
        db.execute(text(f'DELETE FROM "{name}" WHERE record = :record'), {"record": record})


def save(db, found: Graph, record: str) -> None:
    """The statements of a record and of its parts are written in the session *db*, in place of the rows it
    had; every row names the record."""
    delete(db, record)
    for name, frame in tables(found, profile()).items():
        if len(frame):
            frame["record"] = record
            frame.to_sql(name, db.connection(), index=False, if_exists="append")


def described(found: Graph, iri: str | BNode) -> Graph:
    """The statements of the record at *iri* (or of a node without an address) in *found*, with those of
    its parts at any depth: the nodes without an address that it holds, and those at addresses under its
    own (casestudies/kidney/Q1 is part of casestudies/kidney)."""
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
    """The rows of a record and of its parts with addresses in the records table, which lists each with its
    class and name."""
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
    """The records at these addresses that are not removed, as linked data; a part of a record is read from
    the record that holds it."""
    with database.session() as db:
        kept = list(db.execute(select(Record.iri, Record.part_of).where(Record.iri.in_(iris), Record.removed_at.is_(None))))
    held = read(sorted({part_of or iri for iri, part_of in kept}))
    found = Graph()
    for iri, _ in kept:
        found += described(held, iri)
    for prefix, namespace in settings()["prefixes"].items():
        found.bind(prefix, namespace)
    return found


def linked_graph(record: Record) -> Graph:
    """The record and the records it links to, as linked data."""
    found = graph([record.iri])
    linked = []
    for value in found.objects(URIRef(record.iri), None):
        if isinstance(value, URIRef):
            linked.append(str(value))
    return found + graph(linked)
