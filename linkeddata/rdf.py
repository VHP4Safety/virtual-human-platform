"""Records as linked data, and linked data as records.

pandas reads the rows of the records table through SQLAlchemy, and rdfsolve makes records of the
model from them (from_table), checking them against the approved schema. The other way, rdfsolve
gives the records of converted data as a table (Results.table), which becomes rows. The fields are
the columns of the records table that rdfsolve finds in the model for the record's class.
"""

from functools import cache

import pandas as pd
import pyshacl
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SH
from sqlalchemy import JSON, select

from linkeddata import database
from linkeddata.database import Record
from linkeddata.document import compact
from linkeddata.model import contract_client, profile, settings


class NotFitting(ValueError):
    """A record that does not fit the model, with what is wrong with each of its fields."""

    def __init__(self, problems: dict[str, list[str]]):
        self.problems = problems
        messages = []
        for field, found in problems.items():
            for message in found:
                messages.append(f"{field}: {message}")
        super().__init__(" ".join(messages))


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


def field_of_property(kind: str, iri: str) -> str:
    known = fields(kind)
    for field in known.index:
        if known.loc[field, "property"] == iri:
            return field
    return iri


def check(new: dict) -> Graph:
    """A new row as linked data. rdfsolve checks the type of each value against the approved schema,
    and pyshacl checks the record against the application profile (required, single and fixed values)."""
    try:
        found = linked(pd.DataFrame([new]))
    except ValueError:
        problems = {}
        for field in fields(new["type"]).index:
            if not new.get(field):
                continue
            try:
                linked(pd.DataFrame([{"iri": new["iri"], "type": new["type"], field: new[field]}]))
            except ValueError as problem:
                reason = str(problem.__cause__ or problem).removeprefix(field + ": ")
                problems[field] = [f"This value does not fit the field ({reason})."]
        raise NotFitting(problems)
    problems = {}
    # Only web addresses are kept, so that a link on a page never runs a script (javascript:) or opens a file.
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != RDF.type and not str(value).startswith(("https://", "http://")):
            field = field_of_property(new["type"], str(predicate))
            problems.setdefault(field, []).append("A web address starts with https:// or http://.")
    if problems:
        raise NotFitting(problems)
    conforms, results, _ = pyshacl.validate(found, shacl_graph=profile())
    if not conforms:
        for result in results.subjects(RDF.type, SH.ValidationResult):
            field = field_of_property(new["type"], str(results.value(result, SH.resultPath)))
            problems.setdefault(field, []).append(str(results.value(result, SH.resultMessage)))
        raise NotFitting(problems)
    return found


def graph(iris: list[str]) -> Graph:
    """The records at these addresses that are not removed, as linked data."""
    statement = select(Record).where(Record.iri.in_(iris), Record.removed_at.is_(None))
    with database.engine().connect() as connection:
        table = pd.read_sql(statement, connection)
    return linked(table)


def document(found: Graph) -> dict:
    return compact(found.serialize(format="nt"), settings())
