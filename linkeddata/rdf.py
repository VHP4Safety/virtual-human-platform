"""Records as linked data, and linked data as records.

pandas reads the rows of the records table through SQLAlchemy, and rdfsolve makes records of the
model from them (from_table), checking them against the approved schema. The other way, rdfsolve
gives the records of converted data as a table (Results.table), which becomes rows. The fields are
the columns of the records table that rdfsolve finds in the model for the record's class.
"""

import json
from functools import cache

import pandas as pd
import pyshacl
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SH
from rdfsolve.api import RecordError
from sqlalchemy import JSON, func, select

import database
from database.tables import Record
from linkeddata.document import compact
from linkeddata.model import DASH, contract_client, profile, property_shapes, settings


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
    """The rows of a table as linked data; rdfsolve raises RecordError for the values that do not fit.
    A web address is a link in a field that takes links."""
    graph = Graph()
    for kind, rows_of_kind in table.groupby("type"):
        taken = {}
        for field in fields(kind).index:
            if field in rows_of_kind.columns:
                taken[field] = field
        graph += client().to_graph(client().from_table(kind, rows_of_kind, id_column="iri", iri_strings=True, **taken))
    for prefix, namespace in settings()["prefixes"].items():
        graph.bind(prefix, namespace)
    return graph


def field_of_property(kind: str, iri: str) -> str:
    known = fields(kind)
    for field in known.index:
        if known.loc[field, "property"] == iri:
            return field
    return iri


def checked(new: dict) -> tuple[Graph | None, dict[str, list[str]], dict[str, list[str]]]:
    """A new row as linked data, what is wrong with each of its fields, and what is only recommended.
    rdfsolve checks the type of each value against the approved schema (when a value does not fit,
    there is no linked data), and pyshacl checks the record against the application profile (required,
    single and fixed values); results of sh:Warning severity are recommendations."""
    try:
        found = linked(pd.DataFrame([new]))
    except RecordError as error:
        problems = {}
        for problem in error.problems:
            reason = problem["reason"].removeprefix(f"{problem['field']}: ").splitlines()[0]
            problems.setdefault(problem["field"] or "iri", []).append(f"This value does not fit the field ({reason}).")
        return None, problems, {}
    problems = {}
    warnings = {}
    # The class of each record that a value links to is known to the platform, and the profile checks it.
    targets = []
    for value in found.objects():
        if isinstance(value, URIRef):
            targets.append(str(value))
    validated = Graph() + found
    with database.session() as db:
        for iri, kind in db.execute(select(Record.iri, Record.type).where(Record.iri.in_(targets))):
            validated.add((URIRef(iri), RDF.type, URIRef(kind)))
    _, results, _ = pyshacl.validate(validated, shacl_graph=profile())
    for result in results.subjects(RDF.type, SH.ValidationResult):
        if results.value(result, SH.focusNode) != URIRef(new["iri"]):
            continue
        field = field_of_property(new["type"], str(results.value(result, SH.resultPath)))
        message = str(results.value(result, SH.resultMessage))
        found_in = problems if results.value(result, SH.resultSeverity) == SH.Violation else warnings
        if message not in found_in.setdefault(field, []):
            found_in[field].append(message)
    # Only web addresses are kept, so that a link on a page never runs a script (javascript:) or opens a file.
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != RDF.type and not str(value).startswith(("https://", "http://")):
            field = field_of_property(new["type"], str(predicate))
            if field not in problems:
                problems[field] = ["A web address starts with https:// or http://."]
    return found, problems, warnings


def check(new: dict) -> Graph:
    """A new row as linked data; NotFitting tells what is wrong with each field when it does not fit."""
    found, problems, _ = checked(new)
    if problems:
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


def linked_graph(record: Record) -> Graph:
    """The record and the records it links to, such as the terms of the glossary, as linked data."""
    iris = [record.iri]
    for field in fields(record.type).index:
        if several(field):
            iris.extend(getattr(record, field))
    return graph(iris)


def document_of(iri: str) -> str | None:
    """The record at this address in JSON-LD as it is now; None when there is none."""
    found = graph([iri])
    if len(found) == 0:
        return None
    return json.dumps(document(found), indent=2)


def duplicates(row: dict) -> dict[str, list[str]]:
    """The fields whose value another record of the class already has, where the application profile
    asks for a value that no other record has (dash:uniqueValueForClass)."""
    found = {}
    for path, nodes in property_shapes(profile(), row["type"]).items():
        for node in nodes:
            field = field_of_property(row["type"], path)
            value = row.get(field)
            if profile().value(node, DASH.uniqueValueForClass) is None or not isinstance(value, str) or not value:
                continue
            statement = select(Record).where(
                Record.type == row["type"],
                func.lower(getattr(Record, field)) == value.lower(),
                Record.iri != row["iri"],
                Record.removed_at.is_(None),
            )
            with database.session() as db:
                other = db.scalars(statement).first()
            if other is not None:
                path_of_other = "/" + other.iri.removeprefix(settings()["base"])
                found.setdefault(field, []).append(f"{other.name or other.iri} ({path_of_other}) has the same value; check that this is not a duplicate.")
    return found
