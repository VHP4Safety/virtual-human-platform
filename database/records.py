"""Read and write records."""

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
from linkeddata.profile import fields, hierarchy, settings, shapes_text, terms

# HTML texts that cannot be parsed are already reported with the checks.
logging.getLogger("rdflib.term").setLevel(logging.ERROR)


def address(path: str) -> str:
    """Return the address of the record at a page path."""
    whole = re.fullmatch(r"(https?):/+(.*)", path)
    if whole:
        return whole.group(1) + "://" + whole.group(2)
    return settings()["base"] + path.strip("/")


def path(iri: str) -> str:
    """Return the page path of the record at iri."""
    return iri.removeprefix(settings()["base"])


def get(iri: str) -> Record | None:
    with database.session() as db:
        return db.get(Record, iri)


def of_kind(kind: str) -> list[Record]:
    """Return the records under /<kind>/ that are not removed."""
    statement = select(Record).where(Record.iri.startswith(address(kind) + "/"), Record.removed_at.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))


def search(text: str, classes: list[str], within: str = "", limit: int | None = 20, among=None) -> list[Record]:
    """Return sorted by name the records of classes with text in the name or the address."""
    every = set(classes)
    for of_class in classes:
        every |= {str(sub) for sub in hierarchy().transitive_subjects(RDFS.subClassOf, URIRef(of_class))}
    statement = select(Record).where(Record.type.in_(every), Record.removed_at.is_(None), Record.moved_to.is_(None))
    if text:
        statement = statement.where(Record.name.icontains(text, autoescape=True) | Record.iri.contains(text, autoescape=True))
    if within:
        statement = statement.where(Record.iri.startswith(within))
    if among is not None:
        statement = statement.where(Record.iri.in_(among))
    with database.session() as db:
        return list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri).limit(limit)))


def parts_of(iri: str) -> list[str]:
    """Return the addresses of the parts of the record at iri."""
    with database.session() as db:
        return list(db.scalars(select(Record.iri).where(Record.part_of == iri, Record.removed_at.is_(None))))


def latest_change() -> str:
    """Return the time of the last change of a record, in UTC."""
    with database.session() as db:
        found = db.execute(select(func.max(Record.updated_at), func.max(Record.removed_at))).one()
    return max([value for value in found if value] or [""])


def with_pages() -> list[tuple[str, str]]:
    """Return the address and the time of the last change of each record with a page."""
    with database.session() as db:
        return list(db.execute(select(Record.iri, Record.updated_at).where(
            Record.iri.startswith(settings()["base"]), Record.part_of.is_(None), Record.removed_at.is_(None),
            Record.moved_to.is_(None)).order_by(Record.iri)).all())


def kept(iris: list[str]) -> list[Record]:
    """Return the records and parts at iris that are not removed or moved."""
    with database.session() as db:
        return list(db.scalars(select(Record).where(Record.iri.in_(iris), Record.removed_at.is_(None), Record.moved_to.is_(None))))


def names(iris: list[str]) -> dict[str, str]:
    """Return the names of the records and terms at iris."""
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
    """Return the addresses of the record at iri before it was moved."""
    with database.session() as db:
        return list(db.scalars(select(Record.iri).where(Record.moved_to == iri)))


def kinds_of(term: str) -> list[Record]:
    """Return the kinds of the glossary term term, sorted by address."""
    named = get(term)
    return kinds_named(named.name) if named is not None and named.name else []


def kinds_named(name: str) -> list[Record]:
    """Return the kinds of the glossary term of a name, which the glossary names "<kind> (<name>)", sorted by address."""
    statement = select(Record).where(Record.name.endswith(f" ({name})"), Record.removed_at.is_(None), Record.moved_to.is_(None))
    with database.session() as db:
        return list(db.scalars(statement.order_by(Record.iri)))


@cache
def tables() -> dict:
    """Return the release tables by name."""
    found = {}
    for name, columns in sql_tables.layout(shapes_text()).columns().items():
        found[name] = table(name, *[column(name_of_column) for name_of_column in columns])
    return found


def read(records: list[str]) -> Graph:
    """Return the statements of the records at records."""
    if not records:
        return Graph()
    found = {}
    with database.engine().connect() as connection:
        for name, of_table in tables().items():
            result = connection.execute(select(of_table).where(of_table.c.record.in_(records)))
            listed = result.all()
            if listed:
                found[name] = pd.DataFrame(listed, columns=list(result.keys()), dtype="string")
    return sql_tables.from_tables(found, shapes_text())


# The address of <record>#<field>-<n> (skolemized bnodes).
PART = re.compile(r"^(?P<record>[^#]+)#[A-Za-z_][A-Za-z0-9_]*-[0-9]+$")


def class_of(found: Graph, node) -> str:
    """Return the class of node."""
    given = sorted(str(value) for value in found.objects(node, RDF.type))
    kinds = set(settings()["kinds"].values())
    return next((value for value in given if value in kinds), given[0] if given else "")


def is_part(found: Graph, node) -> bool:
    """Return True if node is a part of a record in found."""
    return isinstance(node, BNode) or (isinstance(node, URIRef) and PART.match(str(node)) is not None and (node, None, None) in found)


def blank_parts(found: Graph, record: str) -> Graph:
    """Return found with the part addresses of record as blank nodes."""
    blanks = {}

    def blank(node):
        match = PART.match(str(node)) if isinstance(node, URIRef) else None
        if match and match["record"] == record:
            return blanks.setdefault(node, BNode())
        return node

    changed = Graph()
    for subject, predicate, value in found:
        changed.add((blank(subject), predicate, blank(value)))
    return changed


def delete(db, record: str) -> None:
    """Delete the rows of the record at record in the session db."""
    for of_table in tables().values():
        db.execute(of_table.delete().where(of_table.c.record == record))


def save(db, found: Graph, record: str, before: Graph | None = None) -> None:
    """Replace the rows of the record at record with the statements in found."""
    if before is None:
        before = read([record])
    delete(db, record)
    for name, frame in sql_tables.tables(found, shapes_text(), empty=False, skolem=True, before=before).items():
        frame["record"] = record
        frame.to_sql(name, db.connection(), index=False, if_exists="append")


def described(found: Graph, iri: str | BNode) -> Graph:
    """Return the statements of the node at iri and of its parts."""
    own = Graph()
    nodes = [iri if isinstance(iri, BNode) else URIRef(iri)]
    # Part addresses are under the record or under a part with an address, such as casestudies/kidney#hasPart-1 and
    # casestudies/kidney/Q1#hasPart-2.
    record = str(iri).split("#")[0] if PART.match(str(iri)) else str(iri)

    def owned(value) -> bool:
        match = PART.match(str(value)) if isinstance(value, URIRef) else None
        return match is not None and (match["record"] == record or match["record"].startswith(record + "/"))
    seen = set()
    while nodes:
        node = nodes.pop()
        if node in seen:
            continue
        seen.add(node)
        for statement in found.triples((node, None, None)):
            own.add(statement)
            value = statement[2]
            if isinstance(value, BNode) or owned(value) or (isinstance(value, URIRef) and str(value).startswith(str(node) + "/")):
                nodes.append(value)
    return own


def rows(found: Graph, iri: str, kind: str, source: str) -> list[dict]:
    """Return the rows of the records table for the record at iri and its parts."""
    listed = {iri: kind}
    # A part address (<record>#<field>-<n>) has no row and no page.
    for subject in described(found, iri).subjects():
        if isinstance(subject, URIRef) and not PART.match(str(subject)) and str(subject) not in listed and found.value(subject, RDF.type) is not None:
            listed[str(subject)] = class_of(found, subject)
    found_rows = []
    for subject, of_class in listed.items():
        name = found.value(URIRef(subject), SDO.name)
        found_rows.append({"iri": subject, "type": of_class, "source": source, "name": str(name) if name is not None else None,
                           "part_of": None if subject == iri else iri})
    return found_rows


def graph(iris: list[str]) -> Graph:
    """Return the records at iris that are not removed, with their parts."""
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
    """Return found with the class and the name of each linked record."""
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


@cache
def within(of_class: str) -> list[str]:
    """Return of_class and the classes below it in the vocabularies, such as a ResearchProject for an Organization."""
    return [of_class, *sorted({str(below) for below in hierarchy().transitive_subjects(RDFS.subClassOf, URIRef(of_class))} - {of_class})]


def sources(of_class: str, path: str) -> list[dict]:
    """Return the tables and columns of the values of a field of of_class."""
    rest = tables()[sql_tables.STATEMENTS]
    found = []
    in_statements = False
    for each in within(of_class):
        # The values of a class without a table of its own are in the table of statements.
        of_layout = sql_tables.layout(shapes_text()).classes.get(each)
        if of_layout is None:
            in_statements = True
        elif path in of_layout.several:
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
    """Return each node of of_class with each value of the field path."""
    selects = []
    for source in sources(of_class, path):
        selects.append(select(source["table"].c.iri, source["value"]).where(source["where"]))
    with database.engine().connect() as connection:
        return list(connection.execute(selects[0] if len(selects) == 1 else union_all(*selects)).all())


def places() -> list[tuple]:
    """Return each table and column with values in the layout, with its property."""
    found = [(tables()[sql_tables.STATEMENTS], "value", None)]
    for of_layout in sql_tables.layout(shapes_text()).classes.values():
        own = tables()[of_layout.name]
        for path, name in of_layout.single.items():
            found.append((own, name, path))
        for path, name in of_layout.several.items():
            found.append((tables()[of_layout.field_table(name)], "value", path))
    return found


def united(selects: list) -> set[tuple]:
    """Return the rows of the union of selects."""
    found = set()
    with database.engine().connect() as connection:
        for first in range(0, len(selects), 400):
            found.update(connection.execute(union_all(*selects[first:first + 400])).all())
    return found


def naming(iri: str) -> set[tuple[str, str]]:
    """Return the nodes with iri as a value, with the property of the value."""
    selects = []
    for of_table, name, path in places():
        property_of = of_table.c.property if path is None else literal(path)
        selects.append(select(of_table.c.iri, property_of).where(of_table.c[name] == iri))
    return united(selects)


def linking(iri: str) -> set[str]:
    """Return the addresses of the records that link to iri."""
    selects = []
    for of_table, name, _ in places():
        selects.append(select(of_table.c.record).where(of_table.c[name] == iri))
    return {row[0] for row in united(selects)} - {iri}


def nodes_with(of_class: str, path: str, wanted: list[str]):
    """Return the select of the nodes of of_class with one of the wanted values of a field."""
    selects = []
    for source in sources(of_class, path):
        selects.append(select(source["table"].c.iri).where(source["value"].in_(wanted), source["where"]))
    return selects[0] if len(selects) == 1 else union_all(*selects)


def chosen(of_class: str, filters: dict, search: str = ""):
    """Return the select of the records of of_class found by filters and search."""
    statement = select(Record.iri, Record.name).where(
        Record.type.in_(within(of_class)), Record.removed_at.is_(None), Record.moved_to.is_(None), Record.part_of.is_(None))
    if search:
        statement = statement.where(or_(Record.name.icontains(search, autoescape=True), Record.iri.contains(search, autoescape=True)))
    for path, wanted in filters.items():
        statement = statement.where(Record.iri.in_(nodes_with(of_class, path, wanted)))
    return statement


def page(of_class: str, filters: dict, search: str, first: int, size: int) -> tuple[int, list[str]]:
    """Return the number of records found and the addresses of one page of them."""
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
    """Return the number of records found for each value of each field in paths."""
    every = chosen(of_class, filters, search).with_only_columns(Record.iri).cte("chosen").prefix_with("MATERIALIZED")
    branches = []
    for number, path in enumerate(paths):
        records = every
        if path in filters:
            others = dict(filters)
            del others[path]
            records = chosen(of_class, others, search).with_only_columns(Record.iri).cte(f"chosen_but_{number}").prefix_with("MATERIALIZED")
        for source in sources(of_class, path):
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
    """Return True if a listing can be filtered by field: a field of links or listed values, or of several texts or links, such as keywords."""
    return bool(field["values"] or field["links"] or (field["open"] and not field["single"])) and not field["part"] and not field["fixed"]


def filters(of_class: str, given: dict) -> dict:
    """Return the requested values of each filter field of of_class, by property."""
    found = {}
    for field in fields(of_class):
        if browsed(field) and given.get(field["name"]):
            found[field["iri"]] = given[field["name"]]
    return found


def counted(of_class: str, given: dict) -> dict:
    """Return the values of each filter field of of_class with their counts, by field name."""
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
        # Count list values when they are not in a record.
        values = {}
        for value in field["values"]:
            values[(value, field["iris"])] = 0
        for key, count in counts[field["iri"]].items():
            values[key] = values.get(key, 0) + count
        listed = []
        for (value, iri), count in values.items():
            # Value fits if it is an IRI and if it is in the list of the field.
            fits = iri == field["iris"] and (value in field["values"] or not field["values"])
            listed.append({"value": value, "name": (named.get(value) if iri else None) or value, "count": count, "fits": fits})
        # List values that fit first, then the most used values, then the values by name.
        listed.sort(key=lambda value: (not value["fits"], -value["count"], value["name"]))
        found[field["name"]] = listed
    return found
