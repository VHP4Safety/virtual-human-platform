"""The records of a kind in SQL, for the API's catalogues: a page of records filtered by field values and by
name, and the count of each value of the browsable fields (facets). The queries follow rdfsolve's layout of
the profile: a single-valued field is a column of its class's table, a multi-valued field has its own table,
and the rest, with extra values of single-valued fields, is in the statements table."""

from functools import cache

from rdfsolve.client.sql_tables import STATEMENTS, TERM_SUFFIX, layout
from sqlalchemy import column, func, literal, or_, select, table, union_all

import database
from database.tables import Record
from linkeddata import storage

RECORDS = Record.__table__


@cache
def tables() -> dict:
    """The release's tables by name, with their columns, from rdfsolve's layout of the profile."""
    found = {}
    for name, columns in layout(storage.profile()).columns().items():
        found[name] = table(name, *[column(name_of_column) for name_of_column in columns])
    return found


def sources(of_class: str, path: str) -> list[dict]:
    """Where a field's values are: its own table, or its column of the class's table and the statements
    table; each with its value column, term column (an IRI's is "@id") and row condition."""
    of_layout = layout(storage.profile()).classes[of_class]
    rest = tables()[STATEMENTS]
    in_statements = {"table": rest, "value": rest.c.value, "term": rest.c.term, "where": rest.c.property == path}
    if path in of_layout.several:
        own = tables()[of_layout.field_table(of_layout.several[path])]
        found = [{"table": own, "value": own.c.value, "term": own.c.term, "where": None}]
    elif path in of_layout.single:
        own = tables()[of_layout.name]
        name = of_layout.single[path]
        found = [{"table": own, "value": own.c[name], "term": own.c[name + TERM_SUFFIX], "where": own.c[name].is_not(None)}, in_statements]
    else:
        found = [in_statements]
    return found


def holders(of_class: str, path: str, wanted: list[str]):
    """The select of the nodes of a class that have one of the wanted values of a field."""
    selects = []
    for source in sources(of_class, path):
        found = select(source["table"].c.iri).where(source["value"].in_(wanted))
        if source["where"] is not None:
            found = found.where(source["where"])
        selects.append(found)
    return selects[0] if len(selects) == 1 else union_all(*selects)


def chosen(of_class: str, filters: dict, search: str = ""):
    """The select of a class's records that are not removed, moved or parts, whose name or address has
    *search*, and that have a value of each field of *filters* (property: values)."""
    statement = select(RECORDS.c.iri, RECORDS.c.name).where(
        RECORDS.c.type == of_class, RECORDS.c.removed_at.is_(None), RECORDS.c.moved_to.is_(None), RECORDS.c.part_of.is_(None))
    if search:
        statement = statement.where(or_(RECORDS.c.name.icontains(search, autoescape=True), RECORDS.c.iri.contains(search, autoescape=True)))
    for path, wanted in filters.items():
        statement = statement.where(RECORDS.c.iri.in_(holders(of_class, path, wanted)))
    return statement


def page(of_class: str, filters: dict, search: str, first: int, size: int) -> tuple[int, list[str]]:
    """The count of records that *filters* and *search* find, and the addresses of a page of them, by name."""
    statement = chosen(of_class, filters, search).add_columns(func.count().over().label("total"))
    statement = statement.order_by(func.lower(RECORDS.c.name).nulls_last(), RECORDS.c.iri).limit(size).offset(first)
    found = []
    total = 0
    with database.engine().connect() as connection:
        for row in connection.execute(statement):
            found.append(row.iri)
            total = row.total
        if not found and first:
            # A page after the last one has no row to give the count.
            total = connection.scalar(select(func.count()).select_from(chosen(of_class, filters, search).subquery()))
    return total, found


def facets(of_class: str, paths: list[str], filters: dict, search: str = "") -> dict[str, dict[tuple[str, bool], int]]:
    """For each field of *paths*, the count of found records per value, by the value and whether it is an
    IRI. A field's own filter is left out of its counts, so each count is what that value would find."""
    # The records are found once (MATERIALIZED), not once per field.
    every = chosen(of_class, filters, search).with_only_columns(RECORDS.c.iri).cte("chosen").prefix_with("MATERIALIZED")
    branches = []
    for number, path in enumerate(paths):
        records = every
        if path in filters:
            others = {}
            for other, wanted in filters.items():
                if other != path:
                    others[other] = wanted
            records = chosen(of_class, others, search).with_only_columns(RECORDS.c.iri).cte(f"chosen_but_{number}").prefix_with("MATERIALIZED")
        for source in sources(of_class, path):
            # A node has a value once per place (the tables' keys), so its rows are counted.
            iri = (source["term"] == "@id").label("iri")
            found = (select(literal(path).label("path"), source["value"].label("value"), iri, func.count().label("records"))
                     .where(source["table"].c.iri.in_(select(records.c.iri))).group_by(source["value"], iri))
            if source["where"] is not None:
                found = found.where(source["where"])
            branches.append(found)
    counted = {}
    for path in paths:
        counted[path] = {}
    if not branches:
        return counted
    with database.engine().connect() as connection:
        for path, value, iri, records in connection.execute(union_all(*branches)):
            counted[path][(value, bool(iri))] = counted[path].get((value, bool(iri)), 0) + records
    return counted
