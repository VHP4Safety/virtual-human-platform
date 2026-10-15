"""Records in the tables of the model's release (database/v1/tables.sql). rdfsolve gives the statements of
a record as tables that follow the application profile, which pandas writes to the database, and makes
the statements again from the rows (rdfsolve.client.sql_tables). `python -m linkeddata model` writes
the tables of the release from the profile.
"""

import sqlite3
from functools import cache

import pandas as pd
from rdflib import Graph
from rdfsolve.client.sql_tables import from_tables, layout, tables
from sqlalchemy import bindparam, text

import database
from linkeddata.model import MODEL_DIR


@cache
def profile() -> Graph:
    """The application profile with only the prefixes it declares, which name the tables and their columns."""
    return Graph(bind_namespaces="none").parse(MODEL_DIR / "profile.ttl", format="turtle")


@cache
def names() -> list[str]:
    return list(layout(profile()).columns())


def generate() -> str:
    """The tables of the release, as SQL: a node's address is the key of the table of its class."""
    statements = []
    with sqlite3.connect(":memory:") as connection:
        for name, columns in layout(profile()).columns().items():
            frame = pd.DataFrame(columns=columns, dtype="string")
            several = name.endswith("__values") or name == "statements"
            schema = pd.io.sql.get_schema(frame, name, keys=None if several else "iri", con=connection)
            statements.append(schema.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1) + ";")
            if several:
                statements.append(f'CREATE INDEX IF NOT EXISTS "{name}__iri" ON "{name}" (iri);')
    database.TABLES.parent.mkdir(parents=True, exist_ok=True)
    database.TABLES.write_text("\n\n".join(statements) + "\n", encoding="utf-8")
    return str(database.TABLES)


def delete(db, record: str) -> None:
    """The rows of a record are removed in the session *db*."""
    for name in names():
        db.execute(text(f'DELETE FROM "{name}" WHERE iri = :iri'), {"iri": record})


def save(db, found: Graph, record: str) -> None:
    """The statements of a record are written in the session *db*, in place of the rows it had."""
    delete(db, record)
    for name, frame in tables(found, profile()).items():
        if len(frame):
            frame.to_sql(name, db.connection(), index=False, if_exists="append")


def graph(records: list[str]) -> Graph:
    """The statements of these records, made from their rows."""
    if not records:
        return Graph()
    read = {}
    with database.engine().connect() as connection:
        for name in names():
            query = text(f'SELECT * FROM "{name}" WHERE iri IN :records').bindparams(bindparam("records", expanding=True))
            read[name] = pd.read_sql(query, connection, params={"records": list(records)}, dtype="string")
    return from_tables(read, profile())
