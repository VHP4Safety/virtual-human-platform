"""Reads and writes of the records.

Store the statements of each record in the release tables, made from the profile with rdfsolve. Select the records of
the listing pages and their facet counts in SQL."""

import logging
import re
from functools import cache

import pandas as pd
from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.namespace import SDO
from rdfsolve.client import sql_tables
from sqlalchemy import column, func, literal, or_, select, table, true, union_all

import database
from database.tables import Record
from linkeddata.profile import fields, hierarchy, profile_text, settings, terms

# HTML texts that cannot be parsed are reported by the checks, so the rdflib warning on each read is turned off.
logging.getLogger("rdflib.term").setLevel(logging.ERROR)


def address(path: str) -> str:
    """Return the address of a record from the path of its page, under the base address. Keep a full address
    elsewhere, such as an ontology term, and read https:/... as https://...."""
    whole = re.fullmatch(r"(https?):/+(.*)", path)
    if whole:
        return whole.group(1) + "://" + whole.group(2)
    return settings()["base"] + path.strip("/")


def path(iri: str) -> str:
    """Return the path of a record under the base address (the inverse of address()). Keep an address elsewhere."""
    return iri.removeprefix(settings()["base"])


def get(iri: str) -> Record | None:
    with database.session() as db:
        return db.get(Record, iri)


def of_kind(kind: str) -> list[Record]:
    """Return the records with a page under /<kind>/ that are not removed."""
    statement = select(Record).where(Record.iri.startswith(address(kind) + "/"), Record.removed_at.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))


def search(text: str, classes: list[str], within: str = "", parts: bool = True, limit: int | None = 20, among=None) -> list[Record]:
    """Return the records of these classes and their subclasses with *text* in the name or the address, sorted by
    name. Include parts unless *parts* is false. Limit the addresses to those that start with *within*, such as a
    vocabulary namespace, and to those *among* a select of addresses."""
    every = set(classes)
    for of_class in classes:
        every |= {str(sub) for sub in hierarchy().transitive_subjects(RDFS.subClassOf, URIRef(of_class))}
    statement = select(Record).where(Record.type.in_(every), Record.removed_at.is_(None), Record.moved_to.is_(None))
    if text:
        statement = statement.where(func.lower(Record.name).contains(text.lower()) | Record.iri.contains(text))
    if within:
        statement = statement.where(Record.iri.startswith(within))
    if among is not None:
        statement = statement.where(Record.iri.in_(among))
    if not parts:
        statement = statement.where(Record.part_of.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri).limit(limit)))


def parts_of(iri: str) -> list[str]:
    """Return the addresses of the parts of a record, such as the questions and steps of a case study."""
    with database.session() as db:
        return list(db.scalars(select(Record.iri).where(Record.part_of == iri, Record.removed_at.is_(None))))


def latest_change() -> str:
    """Return the time when a record was last written, removed or moved, in UTC (ISO 8601)."""
    with database.session() as db:
        found = db.execute(select(func.max(Record.updated_at), func.max(Record.removed_at))).one()
    return max([value for value in found if value] or [""])


def with_pages() -> list[tuple[str, str]]:
    """Return the address and the time of the last change of each record with a page on the platform. Leave out
    parts, removed or moved records, and records outside the base address."""
    with database.session() as db:
        return list(db.execute(select(Record.iri, Record.updated_at).where(
            Record.iri.startswith(settings()["base"]), Record.part_of.is_(None), Record.removed_at.is_(None),
            Record.moved_to.is_(None)).order_by(Record.iri)).all())


def kept(iris: list[str]) -> list[Record]:
    """Return the records and parts at these addresses that are not removed or moved."""
    with database.session() as db:
        return list(db.scalars(select(Record).where(Record.iri.in_(iris), Record.removed_at.is_(None), Record.moved_to.is_(None))))


def names(iris: list[str]) -> dict[str, str]:
    """Return the names of the records at these addresses, and the labels of vocabulary terms."""
    with database.session() as db:
        found = dict(db.execute(select(Record.iri, Record.name).where(Record.iri.in_(iris))).all())
    others = []
    for iri in iris:
        if iri not in found:
            others.append(iri)
    for iri, term in terms(others).items():
        found[iri] = term["name"]
    return found


def earlier_addresses(iri: str) -> list[str]:
    """Return the addresses of a record before it was moved to *iri*."""
    with database.session() as db:
        return list(db.scalars(select(Record.iri).where(Record.moved_to == iri)))


def kinds_of(term: str) -> list[Record]:
    """Return the kinds of a term in the glossary, named "<name> (<name of the term>)", sorted by address."""
    named = get(term)
    if named is None or not named.name:
        return []
    statement = select(Record).where(Record.name.endswith(f" ({named.name})"), Record.removed_at.is_(None), Record.moved_to.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))


@cache
def tables() -> dict:
    """Return the release tables by name, as SQLAlchemy tables, with the columns of the rdfsolve layout of the
    profile."""
    found = {}
    for name, columns in sql_tables.layout(profile_text()).columns().items():
        found[name] = table(name, *[column(name_of_column) for name_of_column in columns])
    return found


def read(records: list[str]) -> Graph:
    """Read the statements of these records from their rows. Pass only the tables with rows to rdfsolve."""
    if not records:
        return Graph()
    found = {}
    with database.engine().connect() as connection:
        for name, of_table in tables().items():
            result = connection.execute(select(of_table).where(of_table.c.record.in_(records)))
            listed = result.all()
            if listed:
                found[name] = pd.DataFrame(listed, columns=list(result.keys()), dtype="string")
    return sql_tables.from_tables(found, profile_text())


def delete(db, record: str) -> None:
    """Delete the rows of a record in the session *db*."""
    for of_table in tables().values():
        db.execute(of_table.delete().where(of_table.c.record == record))


def save(db, found: Graph, record: str) -> None:
    """Replace the rows of a record in the session *db*, with the statements of its parts."""
    delete(db, record)
    for name, frame in sql_tables.tables(found, profile_text(), empty=False).items():
        frame["record"] = record
        frame.to_sql(name, db.connection(), index=False, if_exists="append")


def described(found: Graph, iri: str | BNode) -> Graph:
    """Return the statements of the record at *iri*, or of a node without an address, with the statements of its
    parts at any depth. Parts are nodes without an address and addresses under the record address
    (casestudies/kidney/Q1)."""
    own = Graph()
    nodes = [iri if isinstance(iri, BNode) else URIRef(iri)]
    seen = set()
    while nodes:
        node = nodes.pop()
        if node in seen:
            continue
        seen.add(node)
        for statement in found.triples((node, None, None)):
            own.add(statement)
            value = statement[2]
            if isinstance(value, BNode) or (isinstance(value, URIRef) and str(value).startswith(str(node) + "/")):
                nodes.append(value)
    return own


def rows(found: Graph, iri: str, kind: str, source: str) -> list[dict]:
    """Return the rows of the records table for a record and its parts with an address, each with a class and a
    name."""
    listed = {iri: kind}
    for subject in described(found, iri).subjects():
        if isinstance(subject, URIRef) and str(subject) not in listed and found.value(subject, RDF.type) is not None:
            listed[str(subject)] = str(found.value(subject, RDF.type))
    found_rows = []
    for subject, of_class in listed.items():
        name = found.value(URIRef(subject), SDO.name)
        found_rows.append({"iri": subject, "type": of_class, "source": source, "name": str(name) if name is not None else None,
                           "part_of": None if subject == iri else iri})
    return found_rows


def graph(iris: list[str]) -> Graph:
    """Return the records at these addresses that are not removed, as linked data. Read parts from their records."""
    with database.session() as db:
        listed = list(db.execute(select(Record.iri, Record.part_of).where(Record.iri.in_(iris), Record.removed_at.is_(None))))
    held = read(sorted({part_of or iri for iri, part_of in listed}))
    found = Graph()
    for iri, _ in listed:
        found += described(held, iri)
    for prefix, namespace in settings()["prefixes"].items():
        found.bind(prefix, namespace)
    return found


def with_names(found: Graph) -> Graph:
    """Add the class and the name of each linked record to the statements, so that links are shown with names. Do not
    name an address in sameAs, as it is not a record."""
    linked = set()
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != SDO.sameAs and (value, None, None) not in found:
            linked.add(str(value))
    named = Graph() + found
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.iri.in_(linked))):
            named.add((URIRef(iri), RDF.type, URIRef(kind)))
            if name:
                named.add((URIRef(iri), SDO.name, Literal(name)))
    for prefix, namespace in settings()["prefixes"].items():
        named.bind(prefix, namespace)
    return named


def within(of_class: str) -> list[str]:
    """Return the class and its subclasses in the profile. The records of these classes are of the kind of the
    class."""
    return sql_tables.layout(profile_text()).within(of_class, hierarchy())


def sources(of_class: str, path: str) -> list[dict]:
    """Return the places of the values of a field, for the class and its subclasses.

    A place is a field table, a column of the class table, or the statements table. Each place has a value column, a
    term column ("@id" for an IRI) and a row condition."""
    rest = tables()[sql_tables.STATEMENTS]
    found = []
    in_statements = False
    for each in within(of_class):
        of_layout = sql_tables.layout(profile_text()).classes[each]
        if path in of_layout.several:
            own = tables()[of_layout.field_table(of_layout.several[path])]
            found.append({"table": own, "value": own.c.value, "term": own.c.term, "where": true()})
        elif path in of_layout.single:
            own = tables()[of_layout.name]
            name = of_layout.single[path]
            found.append({"table": own, "value": own.c[name], "term": own.c[name + sql_tables.TERM_SUFFIX], "where": own.c[name].is_not(None)})
            in_statements = True
        else:
            in_statements = True
    if in_statements:
        found.append({"table": rest, "value": rest.c.value, "term": rest.c.term, "where": rest.c.property == path})
    return found


def values(of_class: str, path: str) -> list[tuple[str, str]]:
    """Return each node of a class with each of its values of a field."""
    selects = []
    for source in sources(of_class, path):
        selects.append(select(source["table"].c.iri, source["value"]).where(source["where"]))
    with database.engine().connect() as connection:
        return list(connection.execute(selects[0] if len(selects) == 1 else union_all(*selects)).all())


def naming(iri: str) -> set[tuple[str, str]]:
    """Return the nodes with *iri* as a value of a field, each with the property of the field. Make one select of
    each table and column with values in the rdfsolve layout."""
    rest = tables()[sql_tables.STATEMENTS]
    selects = [select(rest.c.iri, rest.c.property).where(rest.c.value == iri)]
    for of_layout in sql_tables.layout(profile_text()).classes.values():
        own = tables()[of_layout.name]
        for path, name in of_layout.single.items():
            selects.append(select(own.c.iri, literal(path)).where(own.c[name] == iri))
        for path, name in of_layout.several.items():
            listed = tables()[of_layout.field_table(name)]
            selects.append(select(listed.c.iri, literal(path)).where(listed.c.value == iri))
    found = set()
    with database.engine().connect() as connection:
        # Up to 500 selects are allowed in one SQLite union.
        for first in range(0, len(selects), 400):
            found.update(connection.execute(union_all(*selects[first:first + 400])).all())
    return found


def nodes_with(of_class: str, path: str, wanted: list[str]):
    """Return the select of the nodes of a class with one of the wanted values of a field."""
    selects = []
    for source in sources(of_class, path):
        selects.append(select(source["table"].c.iri).where(source["value"].in_(wanted), source["where"]))
    return selects[0] if len(selects) == 1 else union_all(*selects)


def chosen(of_class: str, filters: dict, search: str = ""):
    """Return the select of the records of a class and its subclasses.

    Leave out removed and moved records and parts. Select the records with *search* in the name or the address, and
    with a value of each field in *filters* (property: values)."""
    statement = select(Record.iri, Record.name).where(
        Record.type.in_(within(of_class)), Record.removed_at.is_(None), Record.moved_to.is_(None), Record.part_of.is_(None))
    if search:
        statement = statement.where(or_(Record.name.icontains(search, autoescape=True), Record.iri.contains(search, autoescape=True)))
    for path, wanted in filters.items():
        statement = statement.where(Record.iri.in_(nodes_with(of_class, path, wanted)))
    return statement


def page(of_class: str, filters: dict, search: str, first: int, size: int) -> tuple[int, list[str]]:
    """Return the number of records found by *filters* and *search*, and the addresses of one page of them, sorted
    by name."""
    statement = chosen(of_class, filters, search).add_columns(func.count().over().label("total"))
    statement = statement.order_by(func.lower(Record.name).nulls_last(), Record.iri).limit(size).offset(first)
    found = []
    total = 0
    with database.engine().connect() as connection:
        for row in connection.execute(statement):
            found.append(row.iri)
            total = row.total
        if not found and first:
            # For a page after the last page, no row is returned, so the count is selected separately.
            total = connection.scalar(select(func.count()).select_from(chosen(of_class, filters, search).subquery()))
    return total, found


def facets(of_class: str, paths: list[str], filters: dict, search: str = "") -> dict[str, dict[tuple[str, bool], int]]:
    """Count the records found for each value of each field in *paths*, by the value and by whether it is an IRI.
    Do not apply the filter of a field to the counts of that field, so that each count is the number of records
    found with that value."""
    # The records are found once (MATERIALIZED), not once per field.
    every = chosen(of_class, filters, search).with_only_columns(Record.iri).cte("chosen").prefix_with("MATERIALIZED")
    branches = []
    for number, path in enumerate(paths):
        records = every
        if path in filters:
            others = dict(filters)
            del others[path]
            records = chosen(of_class, others, search).with_only_columns(Record.iri).cte(f"chosen_but_{number}").prefix_with("MATERIALIZED")
        for source in sources(of_class, path):
            # A node has a value once per place (the keys of the tables), so its rows are counted.
            iri = (source["term"] == "@id").label("iri")
            branches.append(select(literal(path).label("path"), source["value"].label("value"), iri, func.count().label("records"))
                            .where(source["table"].c.iri.in_(select(records.c.iri)), source["where"]).group_by(source["value"], iri))
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
    """Return True if a listing can be filtered by a field.

    Such a field has a list of values (sh:in) or links to records or terms (sh:class, sh:or). It has no parts and no
    fixed values."""
    return bool(field["values"] or field["classes"]) and not field["part"] and not field["fixed"]


def filters(of_class: str, given: dict) -> dict:
    """Return the requested values of each filter field, by the property of the field. Read the values from
    *given* by the field name."""
    found = {}
    for field in fields(of_class):
        if browsed(field) and given.get(field["name"]):
            found[field["iri"]] = given[field["name"]]
    return found


def counted(of_class: str, given: dict) -> dict:
    """Return the values of each filter field, by field name.

    Each value has a name, the number of records found with the filters and the search of *given*, and a flag for
    whether it fits the field."""
    browsed_fields = [field for field in fields(of_class) if browsed(field)]
    counts = facets(of_class, [field["iri"] for field in browsed_fields], filters(of_class, given), given["search"])
    every = []
    for field in browsed_fields:
        every.extend(field["values"])
        for value, iri in counts[field["iri"]]:
            if iri:
                every.append(value)
    named = names(every)
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
            # A value fits if it is an IRI where an IRI is required, and if it is in the list of the field.
            fits = iri == field["iris"] and (value in field["values"] or not field["values"])
            listed.append({"value": value, "name": (named.get(value) if iri else None) or value, "count": count, "fits": fits})
        # The values that fit are listed first, then the most used values, then the values by name.
        listed.sort(key=lambda value: (not value["fits"], -value["count"], value["name"]))
        found[field["name"]] = listed
    return found
