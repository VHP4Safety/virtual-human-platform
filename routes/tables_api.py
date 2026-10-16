"""The platform's tables as rows, with flask-smorest: the tables of the model's release
(database/v1/tables.sql), in which the records are kept, and the records, notes and sources tables. A
table is read a page at a time (page, page_size; the X-Pagination header gives the counts), and filtered by
the value of any of its columns. The rows of removed records are left out.

In the tables of the release, a class has a table with a column for each field that takes one value, and
each field that takes several values has a table of its own. Each row's schema carries the JSON-LD type and
context that make the row linked data (x-jsonld-type, x-jsonld-context): a column of values maps to its
property, and the column "iri" to the node it describes.
"""

import re

from flask_smorest import Blueprint
from marshmallow import EXCLUDE
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from rdfsolve.client.sql_tables import layout
from sqlalchemy import MetaData, create_engine, func, select

import database
from database.tables import Note, Record, Source
from linkeddata import storage
from linkeddata.model import TABLES
from routes import limiter

SH = "http://www.w3.org/ns/shacl#"

blueprint = Blueprint("tables", __name__, url_prefix="/api/tables", description="The rows of the platform's tables.")
limiter.limit("300 per minute")(blueprint)


def release_tables() -> MetaData:
    """The tables of the release, as its SQL makes them."""
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.connection.executescript(TABLES.read_text(encoding="utf-8"))
    found = MetaData()
    found.reflect(engine)
    return found


def contexts() -> dict[str, dict]:
    """The JSON-LD type and context of the rows of each table."""
    found = {
        "records": {"x-jsonld-context": {"iri": "@id", "type": "@type", "name": "https://schema.org/name"}},
        "notes": {"x-jsonld-type": SH + "ValidationResult", "x-jsonld-context": {
            "iri": SH + "focusNode", "field": SH + "resultPath", "value": SH + "value", "reason": SH + "resultMessage", "component": SH + "sourceConstraintComponent"}},
        "statements": {"x-jsonld-context": {"iri": "@id"}},
    }
    for of_class in layout(storage.profile()).classes.values():
        context = {"iri": "@id", "type": "@type"}
        for path, name in of_class.single.items():
            context[name] = path
        found[of_class.name] = {"x-jsonld-type": of_class.iri, "x-jsonld-context": context}
        for path, name in of_class.several.items():
            found[of_class.field_table(name)] = {"x-jsonld-context": {"iri": "@id", "value": path}}
    return found


def camel(name: str) -> str:
    words = []
    for word in re.split(r"_+", name):
        words.append(word[:1].upper() + word[1:])
    return "".join(words)


def schemas(table) -> tuple[type, type]:
    """The schema of a row of a table, and of the filters of its query."""
    row = type(camel(table.name), (SQLAlchemyAutoSchema,), {"Meta": type("Meta", (), {"table": table, "include_fk": True})})
    filters = type(camel(table.name) + "Query", (SQLAlchemyAutoSchema,), {"Meta": type("Meta", (), {"table": table, "include_fk": True, "unknown": EXCLUDE})})
    return row, filters


def view_of(table):
    def rows(filters, pagination_parameters):
        conditions = []
        for name, value in filters.items():
            conditions.append(table.c[name] == value)
        removed = select(Record.iri).where(Record.removed_at.is_not(None))
        if "record" in table.c:
            conditions.append(table.c.record.not_in(removed))
        elif "iri" in table.c and table.name != "records":
            conditions.append(table.c.iri.not_in(removed))
        with database.engine().connect() as connection:
            pagination_parameters.item_count = connection.scalar(select(func.count()).select_from(table).where(*conditions))
            statement = select(table).where(*conditions).order_by(*table.c)
            page = statement.offset(pagination_parameters.first_item).limit(pagination_parameters.page_size)
            return connection.execute(page).mappings().all()

    rows.__name__ = f"rows_{table.name}"
    rows.__doc__ = f"The rows of {table.name}"
    return rows


def register(api) -> None:
    """The rows of the tables, in the platform's API."""
    extensions = contexts()
    every = [*release_tables().sorted_tables, Record.__table__, Note.__table__, Source.__table__]
    for table in every:
        row, filters = schemas(table)
        api.spec.components.schema(camel(table.name), component=extensions.get(table.name, {}), schema=row)
        view = blueprint.paginate()(blueprint.response(200, row(many=True))(blueprint.arguments(filters(partial=True), location="query")(view_of(table))))
        blueprint.route(f"/{table.name}", endpoint=f"rows_{table.name}", methods=["GET"])(view)
    api.register_blueprint(blueprint)
