"""Data of the record editor: the counts per kind, the records of a kind, and the graph for the forms of
shacl-form."""

from rdflib import RDF, RDFS, XSD, BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SDO, SH, VOID
from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Note, Record
from linkeddata.profile import PARTS, fields, hierarchy, jsonld_name, profile_graph, settings, shape_of, terms


def counts() -> list[dict]:
    """Count the records, the platform records, the removed records and the notes of each kind, with the average
    share of filled fields."""
    found = []
    with database.session() as db:
        for name, kind in settings()["kinds"].items():
            records_of_kind = select(Record.iri).where(Record.type.in_(records.within(kind)))
            of_kind = select(Record.iri).where(Record.iri.in_(records_of_kind) | Record.part_of.in_(records_of_kind))
            listed = listing(name)
            filled = 0
            for item in listed:
                filled += item["filled"]
            found.append({
                "kind": name,
                "records": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.removed_at.is_(None))),
                "edited": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.source == PLATFORM)),
                "removed": db.scalar(select(func.count()).select_from(Record).where(Record.type.in_(records.within(kind)), Record.removed_at.is_not(None))),
                "notes": db.scalar(select(func.count()).select_from(Note).where(Note.iri.in_(of_kind))),
                "complete": round(100 * filled / (len(listed) * len(fields(kind)))) if listed else 0,
            })
    return found


def listing(kind: str) -> list[dict]:
    """List the records of a kind by name, removed records included, with the numbers of filled fields and notes of
    each record and its parts."""
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
    """Return the node shape of the class of a kind, for its form."""
    return str(shape_of(settings()["kinds"][kind]))


def form_graph() -> Graph:
    """Return the graph for shacl-form: the profile, the class hierarchy, and the names of the records, the list
    terms (sh:in) and their vocabularies. Add two choices, a text and an address, to each sh:or of classes, so that a
    name or an address that is not a record is shown. Give both choices an empty sh:in, so that such a value is
    marked with the message of the field."""
    found = Graph() + profile_graph() + hierarchy()
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
    with database.session() as db:
        for iri, kind, name in db.execute(select(Record.iri, Record.type, Record.name).where(Record.removed_at.is_(None), Record.moved_to.is_(None))):
            found.add((URIRef(iri), RDF.type, URIRef(kind)))
            found.add((URIRef(iri), RDFS.label, Literal(name or iri)))
    # The vocabulary of each term is added, so that each term is listed under its vocabulary.
    for iri, vocabulary in records.values(str(SDO.DefinedTerm), str(SDO.inDefinedTermSet)):
        found.add((URIRef(iri), SDO.inDefinedTermSet, URIRef(vocabulary)))
    listed = []
    for collection in profile_graph().objects(None, SH["in"]):
        for value in Collection(profile_graph(), collection):
            if isinstance(value, URIRef):
                listed.append(str(value))
    for iri, term in terms(listed).items():
        found.add((URIRef(iri), RDFS.label, Literal(term["name"])))
    return found


def draft_vocabulary(record: Record | None) -> str | None:
    """Return the namespace of the vocabulary of a draft term (status Draft), or None for other records."""
    if record is None or record.type != str(SDO.DefinedTerm):
        return None
    found = records.graph([record.iri])
    if str(found.value(URIRef(record.iri), SDO.creativeWorkStatus) or "") != "Draft":
        return None
    vocabulary = found.value(URIRef(record.iri), SDO.inDefinedTermSet)
    space = records.graph([str(vocabulary)]).value(vocabulary, VOID.uriSpace) if vocabulary is not None else None
    return str(space or "")


def ordered() -> dict[str, list[str]]:
    """Return the properties of the fields whose parts have a position, such as steps and sections, with the labels
    of those fields, for the index of the case-study editor."""
    graph = profile_graph()
    found = {}
    for field in graph.objects(None, SH.property):
        node = graph.value(field, SH.node)
        if node is not None and any(graph.value(own, SH.path) == SDO.position for own in graph.objects(node, SH.property)):
            found.setdefault(str(graph.value(field, SH.path)), set()).add(str(graph.value(field, SH.name) or ""))
    return {path: sorted(names) for path, names in sorted(found.items())}


def mixed() -> list[str]:
    """Return the properties of the fields with an sh:or of a link and another value, such as an address."""
    graph = profile_graph()
    found = []
    for field in graph.objects(None, SH.property):
        for alternatives in graph.objects(field, SH["or"]):
            listed = list(graph.items(alternatives))
            classes = 0
            for alternative in listed:
                if graph.value(alternative, SH["class"]) is not None:
                    classes += 1
            if 0 < classes < len(listed):
                found.append(str(graph.value(field, SH.path)))
    return found


def links() -> dict[str, dict[str, str]]:
    """Return the properties of the fields with links to records (sh:class, or sh:or of classes, without parts),
    with the label of each class. Take the label from the sh:or choice, else from the class shape, else from the
    class."""
    graph = profile_graph()
    found = {}
    for field in graph.objects(None, SH.property):
        if graph.value(field, SH.node) is not None or graph.value(field, SH.nodeKind) in PARTS:
            continue
        named = []
        for of_class in graph.objects(field, SH["class"]):
            named.append((of_class, None))
        for alternatives in graph.objects(field, SH["or"]):
            for alternative in graph.items(alternatives):
                for of_class in graph.objects(alternative, SH["class"]):
                    named.append((of_class, graph.value(alternative, RDFS.label)))
        for of_class, label in named:
            label = label or graph.value(graph.value(None, SH.targetClass, of_class), RDFS.label) or jsonld_name(str(of_class)).split(":")[-1]
            found.setdefault(str(graph.value(field, SH.path)), {}).setdefault(str(of_class), str(label))
    return found
