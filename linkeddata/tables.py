"""Records in the tables of the model's release (database/v1/tables.sql). rdfsolve gives the statements of
a record as tables that follow the application profile, which pandas writes to the database, and makes
the statements again from the rows (rdfsolve.client.sql_tables). Every row names the record it belongs
to, nested nodes included, so a record is read and removed by its address. `python -m linkeddata model`
writes the tables of the release from the profile.
"""

from functools import cache

import pandas as pd
from rdflib import Graph
from rdfsolve.client.sql_tables import from_tables, layout, tables
from sqlalchemy import bindparam, column, or_, select, table, text

import database
from database.tables import Record
from linkeddata.model import MODEL_DIR


@cache
def profile() -> str:
    """The application profile, whose prefixes name the tables and their columns."""
    return (MODEL_DIR / "profile.ttl").read_text(encoding="utf-8")


def names() -> list[str]:
    return list(layout(profile()).columns())


def having(kind: str, path: str, values: list[str]):
    """The condition that a record of the class *kind* has one of *values* in the field of the property *path*,
    wherever the tables keep it: in the column of a single field, in the table of a field that takes several
    values, or among the statements that are not fields of a class."""
    conditions = []
    found = layout(profile()).classes.get(kind)
    if found is not None and path in found.single:
        name = found.single[path]
        own = table(found.name, column("iri"), column(name))
        conditions.append(Record.iri.in_(select(own.c.iri).where(own.c[name].in_(values))))
    if found is not None and path in found.several:
        several = table(found.field_table(found.several[path]), column("iri"), column("value"))
        conditions.append(Record.iri.in_(select(several.c.iri).where(several.c.value.in_(values))))
    rest = table("statements", column("iri"), column("property"), column("value"))
    conditions.append(Record.iri.in_(select(rest.c.iri).where(rest.c.property == path, rest.c.value.in_(values))))
    return or_(*conditions)


def sql() -> str:
    """The tables of the release, as SQL."""
    return layout(profile()).ddl()


def generate() -> str:
    database.TABLES.parent.mkdir(parents=True, exist_ok=True)
    database.TABLES.write_text(sql(), encoding="utf-8")
    return str(database.TABLES)


def problems() -> list[str]:
    """Whether the release's SQL is what the profile gives."""
    if not database.TABLES.exists() or database.TABLES.read_text(encoding="utf-8") != sql():
        return [f"{database.TABLES} is not what profile.ttl gives: run python -m linkeddata model, review the change and commit it."]
    return []


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


def graph(records: list[str]) -> Graph:
    """The statements of these records, made from their rows."""
    if not records:
        return Graph()
    read = {}
    with database.engine().connect() as connection:
        for name in names():
            query = text(f'SELECT * FROM "{name}" WHERE record IN :records').bindparams(bindparam("records", expanding=True))
            read[name] = pd.read_sql(query, connection, params={"records": list(records)}, dtype="string")
    return from_tables(read, profile())
