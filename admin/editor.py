"""Data of the record editor."""

from functools import lru_cache

from rdflib import RDF, RDFS, XSD, BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SDO, SH, VOID
from rdfsolve.iris import local_name
from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Note, Record, Source
from linkeddata import pages
from linkeddata.profile import DASH, FORM, fields, hierarchy, jsonld_name, readable, settings, shape_fields, shape_of, terms

# A text field is edited as a long text if a stored value of its property is longer than this, or in HTML.
LONG = 100


def counts() -> list[dict]:
    """Return the counts of records, platform records, removed records, missing values and notes of each kind."""
    found = []
    with database.session() as db:
        for name, kind in settings()["kinds"].items():
            records_of_kind = select(Record.iri).where(Record.type.in_(records.within(kind)))
            of_kind = select(Record.iri).where(Record.iri.in_(records_of_kind) | Record.part_of.in_(records_of_kind))
            listed = listing(name)
            filled = 0
            for item in listed:
                filled += item["filled"]
            missing = dict(db.execute(select(Note.severity, func.count()).where(Note.iri.in_(of_kind), Note.component.endswith("MinCountConstraintComponent"))
                                      .group_by(Note.severity)).all())
            found.append({
                "kind": name,
                "records": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.removed_at.is_(None))),
                "edited": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.source == PLATFORM)),
                "removed": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.removed_at.is_not(None))),
                "notes": db.scalar(select(func.count()).select_from(Note).where(Note.iri.in_(of_kind))),
                "required": missing.get("Violation", 0),
                "recommended": missing.get("Warning", 0),
                "complete": round(100 * filled / (len(listed) * len(fields(kind)))) if listed else 0,
            })
    return found


def failed() -> list[Source]:
    """Return the sources whose last import was not stored."""
    with database.session() as db:
        return list(db.scalars(select(Source).where(Source.problem.is_not(None)).order_by(Source.name)))


def listing(kind: str) -> list[dict]:
    """Return the records of a kind by name, with the numbers of filled fields and notes."""
    of_kind = fields(settings()["kinds"][kind])
    with database.session() as db:
        statement = select(Record).where(Record.type.in_(records.within(settings()["kinds"][kind])), Record.moved_to.is_(None))
        listed = list(db.scalars(statement.order_by(func.lower(Record.name), Record.iri)))
        holder = func.coalesce(Record.part_of, Record.iri)
        noted = dict(db.execute(select(holder, func.count()).select_from(Note).join(Record, Record.iri == Note.iri).where(holder.in_([record.iri for record in listed])).group_by(holder)).all())
    found = records.read([record.iri for record in listed])
    rows = []
    for record in listed:
        given = set()
        for predicate in found.predicates(URIRef(record.iri)):
            given.add(str(predicate))
        filled = 0
        for field in of_kind:
            if field["iri"] in given:
                filled += 1
        rows.append({"record": record, "filled": filled, "fields": len(of_kind), "notes": noted.get(record.iri, 0)})
    return rows


def root_shape(kind: str) -> str:
    """Return the node shape of the form of a kind."""
    return str(shape_of(settings()["kinds"][kind]))


def form_graph() -> Graph:
    """Return the graph of the forms, records and terms for shacl-form: a node shape for each class of records and each part."""
    found = Graph() + hierarchy()
    with database.session() as db:
        classes = set(db.scalars(select(Record.type).distinct())) | set(settings()["kinds"].values())
    done = set()
    for of_class in sorted(classes):
        form(found, shape_of(of_class), fields(of_class), done, of_class)
    longer(found)
    lists(found)
    for alternatives in list(found.objects(None, SH["or"])):
        listed = Collection(found, alternatives)
        classes = 0
        for alternative in listed:
            if found.value(alternative, SH["class"]) is not None:
                classes += 1
        if classes == len(listed):
            text = BNode()
            found.add((text, SH.datatype, XSD.string))
            found.add((text, RDFS.label, Literal("Text")))
            found.add((text, SH["in"], RDF.nil))
            listed.append(text)
            address = BNode()
            found.add((address, SH.nodeKind, SH.IRI))
            found.add((address, RDFS.label, Literal("Address")))
            found.add((address, SH["in"], RDF.nil))
            listed.append(address)
    # shacl-form matches a link with a choice of classes (sh:or) by the class of the record only, not by its
    # superclasses. So each record is also given the linked classes above its class, such as Organization for a
    # research project.
    linked = set(found.objects(None, SH["class"]))
    above = {}
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.removed_at.is_(None), Record.moved_to.is_(None))):
            if kind not in above:
                above[kind] = linked & set(found.transitive_objects(URIRef(kind), RDFS.subClassOf))
            for of_class in above[kind] | {URIRef(kind)}:
                found.add((URIRef(iri), RDF.type, of_class))
            found.add((URIRef(iri), RDFS.label, Literal(name or iri)))
    # The vocabulary of each term is added, so that each term is listed under its vocabulary.
    for iri, vocabulary in records.values(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet)):
        found.add((URIRef(iri), SDO.inDefinedTermSet, URIRef(vocabulary)))
    listed = []
    for collection in found.objects(None, SH["in"]):
        for value in Collection(found, collection):
            if isinstance(value, URIRef):
                listed.append(str(value))
    for iri, term in terms(listed).items():
        found.add((URIRef(iri), RDFS.label, Literal(term["name"])))
    return found


def form(found: Graph, node: URIRef, given: list[dict], done: set, of_class: str = "") -> None:
    """Add to found the node shape of a form with the fields given, and the node shapes of their parts."""
    if node in done:
        return
    done.add(node)
    found.add((node, RDF.type, SH.NodeShape))
    if of_class:
        found.add((node, SH.targetClass, URIRef(of_class)))
    groups = {}
    for place, field in enumerate(given, start=1):
        if field["read_only"]:
            continue
        shape = BNode()
        found.add((node, SH.property, shape))
        found.add((shape, SH.name, Literal(field["label"])))
        found.add((shape, SH.order, Literal(place)))
        if field["description"]:
            found.add((shape, SH.description, Literal(field["description"])))
        if field["group"]:
            group = groups.setdefault(field["group"], URIRef(f"{node}-group-{len(groups) + 1}"))
            found.add((group, RDF.type, SH.PropertyGroup))
            found.add((group, RDFS.label, Literal(field["group"])))
            found.add((group, SH.order, Literal(list(groups).index(field["group"]) + 1)))
            found.add((shape, SH.group, group))
        if field["required"] or field["recommended"]:
            found.add((shape, SH.minCount, Literal(1)))
        if field["recommended"]:
            found.add((shape, SH.severity, SH.Warning))
        # The values of a list field are the members of a list, described by the field of the members.
        constrained = shape
        if field["list"]:
            constrained = BNode()
            found.add((shape, SH.path, URIRef(field["iri"])))
            found.add((shape, SH.maxCount, Literal(1)))
            found.add((shape, SH.node, DASH.ListShape))
            found.add((shape, SH.property, constrained))
            rest = BNode()
            found.add((rest, SH.zeroOrMorePath, RDF.rest))
            found.add((constrained, SH.path, Collection(found, BNode(), [rest, RDF.first]).uri))
        else:
            found.add((shape, SH.path, URIRef(field["iri"])))
            if field["single"]:
                found.add((shape, SH.maxCount, Literal(1)))
        values(found, constrained, field, done)


def values(found: Graph, shape, field: dict, done: set) -> None:
    """Add to found the values of a field of a form: listed values, parts, links, addresses or texts."""
    if field["values"]:
        listed = [URIRef(value) if field["iris"] else Literal(value) for value in field["values"]]
        found.add((shape, SH["in"], Collection(found, BNode(), listed).uri))
        return
    choices = []
    for of_class, node in field["parts"].items():
        choice = BNode()
        found.add((choice, SH["class"], URIRef(of_class)))
        found.add((choice, SH.node, URIRef(node)))
        found.add((choice, SH.nodeKind, SH.IRI if of_class in field["addressed"] else SH.BlankNodeOrIRI))
        found.add((choice, RDFS.label, Literal(readable(local_name(of_class)))))
        choices.append(choice)
        form(found, URIRef(node), shape_fields(node), done)
    for of_class, label in field["links"].items():
        choice = BNode()
        found.add((choice, SH["class"], URIRef(of_class)))
        found.add((choice, RDFS.label, Literal(label)))
        choices.append(choice)
    if len(choices) == 1:
        for predicate, value in list(found.predicate_objects(choices[0])):
            if predicate != RDFS.label:
                found.add((shape, predicate, value))
    elif choices:
        found.add((shape, SH["or"], Collection(found, BNode(), choices).uri))
    elif field["address"]:
        found.add((shape, SH.nodeKind, SH.IRI))
    else:
        found.add((shape, SH.datatype, URIRef(field["datatype"] or XSD.string)))
        if field["pattern"]:
            found.add((shape, SH.pattern, Literal(field["pattern"])))
        if field["long"]:
            found.add((shape, DASH.singleLine, Literal(False)))


def longer(found: Graph) -> None:
    """Make each text field of found with a property of long texts a field of a long text."""
    long = {URIRef(path) for path in long_texts(records.latest_change())}
    for shape in list(found.subjects(SH.datatype, XSD.string)):
        if found.value(shape, SH.path) in long:
            found.add((shape, DASH.singleLine, Literal(False)))


@lru_cache(maxsize=4)
def long_texts(latest: str) -> list[str]:
    """Return the properties of long texts: of the long text fields of the profiles, or with a stored value that is long or in HTML."""
    found = {field["iri"] for field in every_field() if field["long"]}
    with database.session() as db:
        stored = records.read(list(db.scalars(select(Record.iri).where(Record.removed_at.is_(None), Record.part_of.is_(None)))))
    for _, predicate, value in stored:
        if isinstance(value, Literal) and (len(str(value)) > LONG or pages.MARKUP.search(str(value))):
            found.add(str(predicate))
    return sorted(found)


def lists(found: Graph) -> None:
    """Write each list field in found as the list cell shape that shacl-form edits."""
    for field in list(found.subjects(SH.node, DASH.ListShape)):
        # The cell shape has an address, such as form:Dataset-creator, as it refers to itself.
        holder = jsonld_name(str(found.value(None, SH.property, field))).split(":")[-1]
        name = f"{holder}-{jsonld_name(str(found.value(field, SH.path))).split(':')[-1]}"
        cell = FORM[name]
        first = BNode()
        for member in list(found.objects(field, SH.property)):
            path = found.value(member, SH.path)
            if isinstance(path, BNode) and list(found.items(path))[-1:] == [RDF.first]:
                for predicate, value in list(found.predicate_objects(member)):
                    found.remove((member, predicate, value))
                    if predicate == SH["or"] and all(found.value(choice, SH["class"]) is not None for choice in found.items(value)):
                        union = FORM[f"{name}-member"]
                        names = []
                        for choice in found.items(value):
                            found.add((found.value(choice, SH["class"]), RDFS.subClassOf, union))
                            names.append(str(found.value(choice, RDFS.label) or jsonld_name(str(found.value(choice, SH["class"])))))
                        found.add((union, RDFS.label, Literal(" or ".join(names[:1] + [other.lower() for other in names[1:]]))))
                        found.add((first, SH["class"], union))
                    elif predicate != SH.path:
                        found.add((first, predicate, value))
                found.remove((field, SH.property, member))
        found.remove((field, SH.node, DASH.ListShape))
        found.add((field, SH.node, cell))
        found.add((first, SH.path, RDF.first))
        found.add((first, SH.minCount, Literal(1)))
        found.add((first, SH.maxCount, Literal(1)))
        rest, end, more = BNode(), BNode(), BNode()
        found.add((end, SH.hasValue, RDF.nil))
        found.add((more, SH.node, cell))
        found.add((rest, SH.path, RDF.rest))
        found.add((rest, SH.minCount, Literal(1)))
        found.add((rest, SH.maxCount, Literal(1)))
        found.add((rest, SH["or"], Collection(found, BNode(), [end, more]).uri))
        found.add((cell, RDF.type, SH.NodeShape))
        found.add((cell, SH.property, first))
        found.add((cell, SH.property, rest))


def draft_vocabulary(record: Record | None) -> str | None:
    """Return the namespace of the vocabulary of a draft term, or None."""
    if record is None or record.type != str(SDO.DefinedTerm):
        return None
    found = records.graph([record.iri])
    if str(found.value(URIRef(record.iri), SDO.creativeWorkStatus) or "") != "Draft":
        return None
    vocabulary = found.value(URIRef(record.iri), SDO.inDefinedTermSet)
    space = records.graph([str(vocabulary)]).value(vocabulary, VOID.uriSpace) if vocabulary is not None else None
    return str(space or "")


def every_field() -> list[dict]:
    """Return the fields of the forms of all classes of records and of their parts."""
    with database.session() as db:
        classes = set(db.scalars(select(Record.type).distinct())) | set(settings()["kinds"].values())
    found, nodes = [], set()
    pending = [fields(of_class) for of_class in sorted(classes)]
    while pending:
        for field in pending.pop():
            found.append(field)
            for node in field["parts"].values():
                if node not in nodes:
                    nodes.add(node)
                    pending.append(shape_fields(node))
    return found


def ordered() -> dict[str, list[str]]:
    """Return the properties of the fields whose parts have a position, with their labels."""
    found = {}
    for field in every_field():
        for node in field["parts"].values():
            if any(own["iri"] == str(SDO.position) for own in shape_fields(node)):
                found.setdefault(field["iri"], set()).add(field["label"])
    return {path: sorted(names) for path, names in sorted(found.items())}


def mixed() -> list[str]:
    """Return the properties of the fields with a choice of a link or another value."""
    return sorted({field["iri"] for field in every_field() if field["links"] and (field["texts"] or field["parts"])})


def links() -> dict[str, dict[str, str]]:
    """Return the properties of the link fields, with the label of each class."""
    found = {}
    for field in every_field():
        if field["links"] and not field["parts"]:
            for of_class, label in field["links"].items():
                found.setdefault(field["iri"], {}).setdefault(of_class, label)
    return found
