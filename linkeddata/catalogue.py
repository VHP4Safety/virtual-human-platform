"""The records of a kind in SQL, for the API's catalogues: a page of records filtered by field values and by
name, and the count of each value of the browsable fields (facets). The queries follow rdfsolve's layout of
the profile: a single-valued field is a column of its class's table, a multi-valued field has its own table,
and the rest, with extra values of single-valued fields, is in the statements table."""

from functools import cache

from rdfsolve.client.sql_tables import STATEMENTS, TERM_SUFFIX, layout
from sqlalchemy import column, func, literal, or_, select, table, union_all

import database
from database import records as stored
from database.tables import Record
from linkeddata import fields, storage
from linkeddata.model import hierarchy

RECORDS = Record.__table__


@cache
def tables() -> dict:
    """The release's tables by name, with their columns, from rdfsolve's layout of the profile."""
    found = {}
    for name, columns in layout(storage.profile()).columns().items():
        found[name] = table(name, *[column(name_of_column) for name_of_column in columns])
    return found


def within(of_class: str) -> list[str]:
    """The class and its subclasses that the profile has, whose records are of its kind too."""
    return layout(storage.profile()).within(of_class, hierarchy())


def sources(of_class: str, path: str) -> list[dict]:
    """Where a field's values are, for the class and its subclasses: each one's own table, or its column of
    the class's table, and the statements table; each with its value column, term column (an IRI's is "@id")
    and row condition."""
    rest = tables()[STATEMENTS]
    found = []
    in_statements = False
    for each in within(of_class):
        of_layout = layout(storage.profile()).classes[each]
        if path in of_layout.several:
            own = tables()[of_layout.field_table(of_layout.several[path])]
            found.append({"table": own, "value": own.c.value, "term": own.c.term, "where": None})
        elif path in of_layout.single:
            own = tables()[of_layout.name]
            name = of_layout.single[path]
            found.append({"table": own, "value": own.c[name], "term": own.c[name + TERM_SUFFIX], "where": own.c[name].is_not(None)})
            in_statements = True
        else:
            in_statements = True
    if in_statements:
        found.append({"table": rest, "value": rest.c.value, "term": rest.c.term, "where": rest.c.property == path})
    return found


def values(of_class: str, path: str) -> list[tuple[str, str]]:
    """Each node of a class with each of its values of a field."""
    selects = []
    for source in sources(of_class, path):
        found = select(source["table"].c.iri, source["value"])
        if source["where"] is not None:
            found = found.where(source["where"])
        selects.append(found)
    with database.engine().connect() as connection:
        return list(connection.execute(selects[0] if len(selects) == 1 else union_all(*selects)).all())


def naming(iri: str) -> set[tuple[str, str]]:
    """The nodes whose fields hold an address, each with the field's property: one select of each table
    and column that holds values, as rdfsolve's layout places them."""
    rest = tables()[STATEMENTS]
    selects = [select(rest.c.iri, rest.c.property).where(rest.c.value == iri)]
    for of_layout in layout(storage.profile()).classes.values():
        own = tables()[of_layout.name]
        for path, name in of_layout.single.items():
            selects.append(select(own.c.iri, literal(path)).where(own.c[name] == iri))
        for path, name in of_layout.several.items():
            listed = tables()[of_layout.field_table(name)]
            selects.append(select(listed.c.iri, literal(path)).where(listed.c.value == iri))
    found = set()
    with database.engine().connect() as connection:
        # SQLite takes up to 500 selects in one union.
        for first in range(0, len(selects), 400):
            found.update(connection.execute(union_all(*selects[first:first + 400])).all())
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
    """The select of the records of a class and its subclasses that are not removed, moved or parts, whose
    name or address has *search*, and that have a value of each field of *filters* (property: values)."""
    statement = select(RECORDS.c.iri, RECORDS.c.name).where(
        RECORDS.c.type.in_(within(of_class)), RECORDS.c.removed_at.is_(None), RECORDS.c.moved_to.is_(None), RECORDS.c.part_of.is_(None))
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


def browsed(field: dict) -> bool:
    """Whether a catalogue is browsed by a field: a list (sh:in), or links to records or terms (sh:class,
    sh:or), without parts or fixed values."""
    return bool(field["values"] or field["classes"]) and not field["part"] and not field["fixed"]


def filters(of_class: str, given: dict) -> dict:
    """The values asked for of each browsed field, by its name in *given*, by the field's property."""
    found = {}
    for field in fields.of(of_class):
        if browsed(field) and given.get(field["name"]):
            found[field["iri"]] = given[field["name"]]
    return found


def ranked(value: dict) -> tuple:
    """A facet value's place: values that fit first, then the most used, then by name."""
    return (not value["fits"], -value["count"], value["name"])


def counted(of_class: str, given: dict) -> dict:
    """Each browsed field's values, by the field's name, with their names and counts of records found (as
    filtered and searched in *given*), and whether they fit the field."""
    browsed_fields = [field for field in fields.of(of_class) if browsed(field)]
    counts = facets(of_class, [field["iri"] for field in browsed_fields], filters(of_class, given), given["search"])
    every = []
    for field in browsed_fields:
        every.extend(field["values"])
        for value, iri in counts[field["iri"]]:
            if iri:
                every.append(value)
    names = stored.names(every)
    found = {}
    for field in browsed_fields:
        # List values are counted even when no record has them.
        values = {}
        for value in field["values"]:
            values[(value, field["iris"])] = 0
        for key, count in counts[field["iri"]].items():
            values[key] = values.get(key, 0) + count
        listed = []
        for (value, iri), count in values.items():
            # A value fits as an IRI where IRIs belong, and as one of the field's list.
            fits = iri == field["iris"] and (value in field["values"] or not field["values"])
            listed.append({"value": value, "name": (names.get(value) if iri else None) or value, "count": count, "fits": fits})
        listed.sort(key=ranked)
        found[field["name"]] = listed
    return found
