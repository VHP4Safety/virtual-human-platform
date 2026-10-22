"""Writes of records on the platform, with a revision for each change."""

import json

from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SDO
from sqlalchemy import delete, insert, select

import database
from database import records
from database.tables import PLATFORM, Record, Revision, now
from linkeddata import documents, parsers
from linkeddata.documents import context
from linkeddata.profile import fields, jsonld_name, settings


def class_of(kind: str, body: dict) -> str:
    """Return the class of a record of kind written with body."""
    given = body.get("@type")
    for name in given if isinstance(given, list) else [given]:
        if not isinstance(name, str):
            continue
        of_class = name if name.startswith(("http://", "https://")) else documents.expand(name)
        if of_class in records.within(kind):
            return of_class
    return kind


def document(kind: str, address: str, body: dict) -> dict:
    """Return the request body as a JSON-LD document of kind at address."""
    known = {}
    for field in fields(kind):
        known[field["name"]] = field
    found = {"@context": context(settings()), "@id": address, "@type": jsonld_name(kind)}
    for name, value in body.items():
        if name.startswith("@"):
            continue
        if name not in known:
            raise ValueError(f"Unknown field {name!r}.")
        found[name] = value
    for name, field in known.items():
        if field["fixed"]:
            found[name] = [{"@id": value} for value in field["fixed"]]
    return found


def kept(found: Graph, iri: str, kind: str) -> None:
    """Add to found the stored values that it leaves out of the read-only fields and of the properties without a field."""
    node = URIRef(iri)
    stored = records.graph([iri])
    editable = {URIRef(field["iri"]) for field in fields(kind) if not field["read_only"]} | {RDF.type}
    for predicate in set(stored.predicates(node, None)) - editable:
        if (node, predicate, None) in found:
            continue
        for value in stored.objects(node, predicate):
            found.add((node, predicate, value))
            found += records.described(stored, value)


def classed(found: Graph, iri: str) -> None:
    """Give each part in found without a class its stored class or the class of its field."""
    stored = records.graph([iri])
    pending = True
    while pending:
        pending = False
        for holder, predicate, part in list(found):
            if predicate == RDF.type or not records.is_part(found, part) or found.value(part, RDF.type) is not None:
                continue
            given = list(stored.objects(part, RDF.type))
            for field in fields(records.class_of(found, holder)):
                if not given and field["iri"] == str(predicate) and len(field["classes"]) == 1:
                    given = [URIRef(field["classes"][0])]
            for of_class in given:
                found.add((part, RDF.type, of_class))
                pending = True


def slug(name: str) -> str:
    return parsers.slug(name)[:60] or "record"


def part(found: Graph, node: BNode) -> bool:
    """Return True if node is in a field of parts."""
    for holder, predicate in found.subject_predicates(node):
        for field in fields(records.class_of(found, holder)):
            if field["iri"] == str(predicate) and field["part"]:
                return True
    return False


def free(base: str, taken: set) -> str:
    """Return base, or base with the first free number, as a free address."""
    iri, number = base, 1
    while iri in taken or records.get(iri) is not None or iri.endswith("/facets"):
        number += 1
        iri = f"{base}-{number}"
    taken.add(iri)
    return iri


def renamed(found: Graph, node, iri: str) -> None:
    """Give node the address iri in found."""
    for predicate, value in list(found.predicate_objects(node)):
        found.remove((node, predicate, value))
        found.add((URIRef(iri), predicate, value))
    for subject, predicate in list(found.subject_predicates(node)):
        found.remove((subject, predicate, node))
        found.add((subject, predicate, URIRef(iri)))


def addressed(found: Graph) -> None:
    """Give an address to each new part in found that requires one."""
    taken = set()
    pending = True
    while pending:
        pending = False
        for holder, predicate, node in list(found):
            if not isinstance(node, BNode) or not isinstance(holder, URIRef):
                continue
            for field in fields(records.class_of(found, holder)):
                if field["iri"] == str(predicate) and records.class_of(found, node) in field["addressed"]:
                    renamed(found, node, free(f"{holder}/{slug(str(found.value(node, SDO.name) or 'page'))}", taken))
                    pending = True


def separate(found: Graph) -> list[tuple[str, str, Graph]]:
    """Remove the new records sent without an address from found, and return them."""
    kinds = {}
    for kind_name, kind in settings()["kinds"].items():
        kinds[URIRef(kind)] = kind_name
    created = []
    taken = set()
    for node, kind in list(found.subject_objects(RDF.type)):
        if not isinstance(node, BNode) or kind not in kinds or part(found, node):
            continue
        name = found.value(node, SDO.name)
        iri = free(records.address(f"{kinds[kind]}/{slug(str(name or kinds[kind]))}"), taken)
        own = Graph()
        for subject, predicate, value in records.described(found, node):
            found.remove((subject, predicate, value))
            own.add((URIRef(iri) if subject == node else subject, predicate, value))
        for subject, predicate in list(found.subject_predicates(node)):
            found.remove((subject, predicate, node))
            found.add((subject, predicate, URIRef(iri)))
        created.append((iri, str(kind), own))
    return created


def save(document: dict, kind: str, name: str, orcid: str) -> Revision:
    """Store document as the record of kind at its address, and return the revision."""
    iri = document["@id"]
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        created = db.get(Record, iri) is None
        db.execute(delete(Record).where((Record.iri == iri) | (Record.part_of == iri)))
        found = documents.statements(document)
        records.save(db, found, iri)
        db.execute(insert(Record), [{**row, "updated_at": now()} for row in records.rows(found, iri, kind, PLATFORM)])
        revision = Revision(
            record_iri=iri,
            action="Added" if created else "Changed",
            previous=previous,
            document=json.dumps(document, indent=2),
            name=name,
            orcid=orcid,
        )
        db.add(revision)
    return revision


def retire(iri: str, name: str, orcid: str) -> Revision:
    """Remove the record at iri, keep its address, and return the revision."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        for record in db.scalars(select(Record).where((Record.iri == iri) | (Record.part_of == iri))):
            record.removed_at = now()
            record.source = PLATFORM
            record.updated_at = now()
        revision = Revision(record_iri=iri, action="Removed", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def move(old: str, new: str, name: str, orcid: str) -> Revision:
    """Move the record at old and its parts to new, and return the revision."""
    previous = documents.document_of(old)

    def moved(node):
        if isinstance(node, URIRef) and (str(node) == old or str(node).startswith((old + "/", old + "#"))):
            return URIRef(new + str(node).removeprefix(old))
        return node

    with database.session() as db, db.begin():
        record = db.get(Record, old)
        found = Graph()
        for subject, prop, value in records.read([old]):
            found.add((moved(subject), prop, moved(value)))
        found.add((URIRef(new), SDO.sameAs, URIRef(old)))
        found.remove((URIRef(new), SDO.sameAs, URIRef(new)))
        # A record can be moved back to an earlier address. That address is then no longer redirected.
        db.execute(delete(Record).where(((Record.iri == new) | Record.iri.startswith(new + "/")), ((Record.moved_to == old) | Record.moved_to.startswith(old + "/"))))
        records.save(db, found, new)
        db.execute(insert(Record), [{**row, "updated_at": now()} for row in records.rows(found, new, record.type, PLATFORM)])
        for kept in db.scalars(select(Record).where((Record.iri == old) | (Record.part_of == old))):
            kept.removed_at = now()
            kept.moved_to = str(moved(URIRef(kept.iri)))
            kept.source = PLATFORM
            kept.updated_at = now()
        for earlier in db.scalars(select(Record).where(Record.moved_to == old)):
            earlier.moved_to = new
    document = documents.document_of(new)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=new, action="Moved", previous=previous, document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def merge(found: Graph, old: str, new: str, kind: str, name: str, orcid: str) -> Revision:
    """Merge the record at old into the record at new, and return the revision."""
    previous = documents.document_of(old)
    target = URIRef(new)
    single = {field["iri"] for field in fields(kind) if field["single"]}

    def moved(node):
        if isinstance(node, URIRef) and (str(node) == old or str(node).startswith(old + "/")):
            return URIRef(new + str(node).removeprefix(old))
        return node

    # The parts of the old record are numbered again under the new record.
    own = records.blank_parts(records.described(found, old), old)
    merged = records.graph([new])
    if not len(merged):
        merged.add((target, RDF.type, URIRef(kind)))
    for predicate, value in own.predicate_objects(URIRef(old)):
        if predicate == RDF.type or (str(predicate) in single and merged.value(target, predicate) is not None):
            continue
        merged.add((target, predicate, moved(value)))
        if isinstance(value, BNode) or moved(value) != value:
            for subject, prop, given in records.described(own, value):
                merged.add((moved(subject), prop, moved(given)))
    merged.add((target, SDO.sameAs, URIRef(old)))
    save(documents.document(merged, new), kind, name, orcid)
    for linking in records.kept(sorted(records.linking(old) - {new})):
        if linking.part_of is not None:
            continue
        relinked = Graph()
        for subject, predicate, value in records.graph([linking.iri]):
            relinked.add((subject, predicate, moved(value)))
        save(documents.document(relinked, linking.iri), linking.type, name, orcid)
    with database.session() as db, db.begin():
        for kept in db.scalars(select(Record).where((Record.iri == old) | (Record.part_of == old))):
            kept.removed_at = now()
            kept.moved_to = str(moved(URIRef(kept.iri)))
            kept.source = PLATFORM
            kept.updated_at = now()
        for earlier in db.scalars(select(Record).where(Record.moved_to == old)):
            earlier.moved_to = new
        revision = Revision(record_iri=old, action="Merged", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def restore(iri: str, name: str, orcid: str) -> Revision:
    """Restore the removed record at iri, and return the revision."""
    with database.session() as db, db.begin():
        for record in db.scalars(select(Record).where((Record.iri == iri) | (Record.part_of == iri))):
            record.removed_at = None
            record.updated_at = now()
    document = documents.document_of(iri)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=iri, action="Restored", document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def remove(iri: str, name: str, orcid: str) -> Revision:
    """Remove the record at iri and its address, and return the revision."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        records.delete(db, iri)
        db.execute(delete(Record).where((Record.iri == iri) | (Record.part_of == iri)))
        revision = Revision(record_iri=iri, action="Removed permanently", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision
