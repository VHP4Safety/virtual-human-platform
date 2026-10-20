"""Data of the record editor."""

from rdflib import RDF, RDFS, XSD, BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SDO, SH, VOID
from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Note, Record
from linkeddata.profile import DASH, FORM, PARTS, fields, hierarchy, jsonld_name, profile_graph, settings, shape_of, terms


def counts() -> list[dict]:
    """Return the counts of records, platform records, removed records and notes of each kind."""
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
    """Return the node shape of the class of a kind."""
    return str(shape_of(settings()["kinds"][kind]))


def form_graph() -> Graph:
    """Return the graph of the shapes, records and terms for shacl-form."""
    found = Graph() + profile_graph() + hierarchy()
    for field in list(found.subjects(DASH.readOnly, Literal(True))):
        found.remove((None, SH.property, field))
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
    for collection in profile_graph().objects(None, SH["in"]):
        for value in Collection(profile_graph(), collection):
            if isinstance(value, URIRef):
                listed.append(str(value))
    for iri, term in terms(listed).items():
        found.add((URIRef(iri), RDFS.label, Literal(term["name"])))
    return found


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


def ordered() -> dict[str, list[str]]:
    """Return the properties of the fields whose parts have a position, with their labels."""
    graph = profile_graph()
    found = {}
    for field in graph.objects(None, SH.property):
        node = graph.value(field, SH.node)
        if node is not None and any(graph.value(own, SH.path) == SDO.position for own in graph.objects(node, SH.property)):
            found.setdefault(str(graph.value(field, SH.path)), set()).add(str(graph.value(field, SH.name) or ""))
    return {path: sorted(names) for path, names in sorted(found.items())}


def mixed() -> list[str]:
    """Return the properties of the fields with a choice of a link or another value."""
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
    """Return the properties of the link fields, with the label of each class."""
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
