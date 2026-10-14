"""Records as linked data, and linked data as records.

pandas reads the rows of the records table through SQLAlchemy, and rdfsolve makes records of the
model from them (from_table), checking them against the approved schema. The other way, rdfsolve
gives the records of converted data as a table (Results.table), which becomes rows. The fields are
the columns of the records table that rdfsolve finds in the model for the record's class.
"""

from functools import cache

import pandas as pd
from rdflib import Graph, Literal, URIRef
from sqlalchemy import JSON, select

from linkeddata import database
from linkeddata.database import Record
from linkeddata.document import compact
from linkeddata.model import contract_client, settings


@cache
def client():
    return contract_client()


@cache
def fields(kind: str) -> pd.DataFrame:
    """The columns of the records table that are fields of *kind*, with what rdfsolve says they take:
    "values" lists the datatypes of their texts, and "links" tells whether they take addresses."""
    known = client().fields(client().model(kind)).set_index("field")
    return known.loc[known.index.intersection(Record.__table__.columns.keys())]


def several(field: str) -> bool:
    """Whether the column of a field holds several values (a JSON column)."""
    return isinstance(Record.__table__.columns[field].type, JSON)


def field_of(kind: str, name: str) -> str:
    """The field of *kind* that a name stands for ("conformsTo", "dct:conformsTo" or "conforms_to")."""
    field = client().field_name(client().model(kind), name)
    if field not in fields(kind).index:
        raise ValueError(f"The platform does not keep the field {name!r}.")
    return field


def row(iri: str, kind: str, source: str, values: dict[str, list]) -> dict:
    """A row of the records table, from a list of values for each field."""
    found = {"iri": iri, "type": kind, "source": source}
    for field, items in values.items():
        if several(field):
            found[field] = list(items)
        elif len(items) > 1:
            raise ValueError(f"{field}: the platform keeps one value.")
        else:
            found[field] = items[0] if items else None
    return found


def fitting(terms, field: pd.Series) -> list[str]:
    """The values of a field that fit the model: addresses where it links, texts where it has texts.
    The others are left out, as the checks of the import report them."""
    kept = []
    if not isinstance(terms, list):
        return kept
    texts = any(value != "IRI" for value in field["values"])
    for term in terms:
        if isinstance(term, URIRef) and field["links"]:
            kept.append(str(term))
        elif isinstance(term, Literal) and texts:
            kept.append(str(term))
    return kept


def rows(results, kind: str, source: str) -> list[dict]:
    """The rows of the records of *kind* in an rdfsolve selection."""
    taken = fields(kind)
    found = []
    for record in results.table(*taken.index).to_dict("records"):
        values = {}
        for field in taken.index:
            values[field] = fitting(record[field], taken.loc[field])
        found.append(row(str(record["Identifier"]), kind, source, values))
    return found


def linked(table: pd.DataFrame) -> Graph:
    """The rows of a table as linked data; rdfsolve raises ValueError for a row that does not fit."""
    graph = Graph()
    for kind, rows_of_kind in table.groupby("type"):
        taken = {}
        for field in fields(kind).index:
            if field in rows_of_kind.columns:
                taken[field] = field
        graph += client().to_graph(client().from_table(kind, rows_of_kind, id_column="iri", **taken))
    for prefix, namespace in settings()["prefixes"].items():
        graph.bind(prefix, namespace)
    return graph


def check(new: dict) -> Graph:
    """A new row as linked data, checked against the approved schema."""
    return linked(pd.DataFrame([new]))


def graph(iris: list[str]) -> Graph:
    """The records at these addresses that are not removed, as linked data."""
    statement = select(Record).where(Record.iri.in_(iris), Record.removed_at.is_(None))
    with database.engine().connect() as connection:
        table = pd.read_sql(statement, connection)
    return linked(table)


def document(found: Graph) -> dict:
    return compact(found.serialize(format="nt"), settings())
