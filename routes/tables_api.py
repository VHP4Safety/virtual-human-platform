"""The platform's tables as rows: the tables of the model's release (database/v1/tables.sql), in which the
records are kept, and the records, notes and sources tables. A table is read a page at a time, filtered
by any of its columns; the rows of removed records are left out.

In the tables of the release, a class has a table with a column for each field that takes one value, and
each field that takes several values has a table of its own. Each row's schema carries the JSON-LD type
and context that make the row linked data (x-jsonld-type, x-jsonld-context): a column of values maps to
its property, and the column "iri" to the node it describes.
"""

import re
from functools import cache

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, create_model
from rdfsolve.client.sql_tables import layout
from spectree import Response, SpecTree
from sqlalchemy import column, func, select, table

import database
from database.tables import Note, Record, Source
from linkeddata import forms, storage
from linkeddata.model import RELEASE, settings
from routes import records_api

SH = "http://www.w3.org/ns/shacl#"
# What the columns that every table of the release has hold.
COLUMNS = {
    "record": "The address of the record that the row belongs to.",
    "iri": "The address of the node that the row describes; _: and a label for a node without an address.",
    "type": "The node's class.",
    "property": "The property of the statement.",
    "value": "The value.",
    "term": "How the value is written: @id a link, @blank a node without an address, empty a text, @ and a "
            "language tag a text in that language, else the value's datatype.",
}

blueprint = Blueprint("tables_api", __name__)
blueprint.before_request(records_api.limit)
document = SpecTree(
    "flask",
    title=f"{settings()['title']}: tables",
    version=RELEASE,
    description=__doc__,
    path="api/docs/tables",
    mode="strict",
    annotations=False,
    naming_strategy=lambda model: model.__name__,
    nested_naming_strategy=lambda parent, child: child,
)


@blueprint.record_once
def register(state) -> None:
    document.register(state.app)


@cache
def tables() -> dict[str, dict]:
    """Every table that the API gives: its columns with what each holds, and the JSON-LD type and context of
    its rows."""
    found = {}
    for kind in settings()["kinds"].values():
        explained = {}
        for field in forms.form(kind):
            explained[field["iri"]] = f"{field['label']}: {field['help']}".strip(": ")
        of_class = layout(storage.profile()).classes.get(kind)
        if of_class is None:
            continue
        columns = {"record": COLUMNS["record"], "iri": COLUMNS["iri"], "type": COLUMNS["type"]}
        context = {"iri": "@id", "type": "@type"}
        for path, name in of_class.single.items():
            columns[name] = explained.get(path, path)
            columns[name + "__term"] = COLUMNS["term"]
            context[name] = path
        found[of_class.name] = {"columns": columns, "x-jsonld-type": kind, "x-jsonld-context": context}
        for path, name in of_class.several.items():
            columns = {"record": COLUMNS["record"], "iri": COLUMNS["iri"], "value": explained.get(path, path), "term": COLUMNS["term"]}
            found[of_class.field_table(name)] = {"columns": columns, "x-jsonld-context": {"iri": "@id", "value": path}}
    columns = {}
    for name in ("record", "iri", "property", "value", "term"):
        columns[name] = COLUMNS[name]
    found["statements"] = {"columns": columns, "x-jsonld-context": {"iri": "@id"}}
    for model, extensions in (
        (Record, {"x-jsonld-context": {"iri": "@id", "type": "@type", "name": "https://schema.org/name"}}),
        (Note, {"x-jsonld-type": SH + "ValidationResult", "x-jsonld-context": {
            "iri": SH + "focusNode", "field": SH + "resultPath", "value": SH + "value", "reason": SH + "resultMessage", "component": SH + "sourceConstraintComponent"}}),
        (Source, {}),
    ):
        columns = {}
        for found_column in model.__table__.columns:
            columns[found_column.name] = found_column.doc or found_column.name
        found[model.__tablename__] = {"columns": columns, **extensions}
    return found


def camel(name: str) -> str:
    return "".join(word[:1].upper() + word[1:] for word in re.split(r"_+", name))


def models(name: str) -> tuple[type[BaseModel], type[BaseModel]]:
    """The query of a table, and a page of its rows."""
    given = tables()[name]
    cells = {}
    filters = {
        "limit": (int, Field(records_api.PAGE, ge=1, le=records_api.LARGEST_PAGE, description="How many rows a page gives.")),
        "offset": (int, Field(0, ge=0, description="How many rows come before this page.")),
    }
    for found_column, explanation in given["columns"].items():
        cells[found_column] = (str | int | None, Field(None, description=explanation))
        filters[found_column] = (list[str] | None, Field(None, description=f"Rows whose {found_column} is one of these values."))
    extensions = {}
    for key in ("x-jsonld-type", "x-jsonld-context"):
        if key in given:
            extensions[key] = given[key]
    row = create_model(camel(name), __config__=ConfigDict(json_schema_extra=extensions), **cells)
    page = create_model(camel(name) + "Page", total=(int, Field(description="How many rows the query gives.")), rows=(list[row], ...))
    return create_model(camel(name) + "Query", __config__=ConfigDict(extra="forbid"), **filters), page


def rows(name: str):
    """The rows of a table, a page at a time.

    A row is given when each column of the query has one of the values given for it; repeat a parameter
    for several values."""
    columns = list(tables()[name]["columns"])
    found = table(name, *[column(each) for each in columns])
    given = request.context.query.model_dump(exclude_none=True)
    conditions = []
    for key, values in given.items():
        if key in columns:
            conditions.append(found.c[key].in_(values))
    removed = select(Record.iri).where(Record.removed_at.is_not(None))
    if "record" in columns:
        conditions.append(found.c.record.not_in(removed))
    elif "iri" in columns and name != "records":
        conditions.append(found.c.iri.not_in(removed))
    with database.engine().connect() as connection:
        total = connection.scalar(select(func.count()).select_from(found).where(*conditions))
        statement = select(found).where(*conditions).order_by(*found.c).limit(given["limit"]).offset(given["offset"])
        page = connection.execute(statement).mappings().all()
    found_rows = []
    for row in page:
        found_rows.append(dict(row))
    return jsonify({"total": total, "rows": found_rows})


for name in tables():
    query, page = models(name)
    view = document.validate(query=query, resp=records_api.answers(HTTP_200=(page, "A page of the rows, with how many the query gives.")), tags=["tables"])(rows)
    blueprint.add_url_rule(f"/api/tables/{name}", f"rows_{name}", view, methods=["GET"], defaults={"name": name})
