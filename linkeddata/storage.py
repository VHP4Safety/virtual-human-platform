"""Where records are kept: their statements as rows of the tables of the model's release
(database/v1/tables.sql). rdfsolve gives the rows of a graph, which pandas writes, and makes the graph
again from them (rdfsolve.client.sql_tables). Every row names the record it belongs to, nested nodes
included, so a record is read and removed by its address."""

from functools import cache

import pandas as pd
from rdflib import Graph, URIRef
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
    """The statements of a record are written in the session *db*, in place of the rows it had."""
    delete(db, record)
    for name, frame in tables(found, profile()).items():
        if len(frame):
            frame.to_sql(name, db.connection(), index=False, if_exists="append")


def row(found: Graph, iri: str, kind: str, source: str) -> dict:
    """The row of a record in the records table, which lists every record with its class and name."""
    name = found.value(URIRef(iri), SDO.name)
    return {"iri": iri, "type": kind, "source": source, "name": str(name) if name is not None else None}


def graph(iris: list[str]) -> Graph:
    """The records at these addresses that are not removed, as linked data."""
    with database.session() as db:
        kept = list(db.scalars(select(Record.iri).where(Record.iri.in_(iris), Record.removed_at.is_(None))))
    found = read(kept)
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
