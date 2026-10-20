"""Writes of records on the platform, with a revision for each change.

A record written on the platform replaces an imported record at the same address. Keep it unchanged at later
imports. Store each change as a revision, with its author."""

import json
import re
from datetime import datetime, timezone

from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SDO
from sqlalchemy import delete, insert, select

import database
from database import records
from database.tables import PLATFORM, Record, Revision, now
from linkeddata import documents
from linkeddata.documents import context
from linkeddata.profile import fields, jsonld_name, settings


def version() -> str:
    """Return the version of a record: the time of its last write, to the microsecond, so that two writes have
    different versions."""
    return datetime.now(timezone.utc).isoformat()


def class_of(kind: str, body: dict) -> str:
    """Return the class of a written record.

    The class is the @type of the body if it is the class of the kind or a subclass, such as AboutPage for pages.
    Otherwise, use the class of the kind."""
    given = body.get("@type")
    for name in given if isinstance(given, list) else [given]:
        if not isinstance(name, str):
            continue
        of_class = name if name.startswith(("http://", "https://")) else documents.expand(name)
        if of_class in records.within(kind):
            return of_class
    return kind


def document(kind: str, address: str, body: dict) -> dict:
    """Convert a request body to a JSON-LD document, with the fixed values of the model. Refuse unknown fields."""
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


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "record"


def part(found: Graph, node: BNode) -> bool:
    """Return True if a node is in a field of parts."""
    for holder, predicate in found.subject_predicates(node):
        for field in fields(str(found.value(holder, RDF.type))):
            if field["iri"] == str(predicate) and field["part"]:
                return True
    return False


def free(base: str, taken: set) -> str:
    """Return a free address: *base*, or *base*-2, *base*-3 and so on if *base* is in *taken*. <kind>/facets is
    reserved for the API."""
    iri, number = base, 1
    while iri in taken or records.get(iri) is not None or iri.endswith("/facets"):
        number += 1
        iri = f"{base}-{number}"
    taken.add(iri)
    return iri


def renamed(found: Graph, node, iri: str) -> None:
    """Give the node the address *iri* in *found*."""
    for predicate, value in list(found.predicate_objects(node)):
        found.remove((node, predicate, value))
        found.add((URIRef(iri), predicate, value))
    for subject, predicate in list(found.subject_predicates(node)):
        found.remove((subject, predicate, node))
        found.add((subject, predicate, URIRef(iri)))


def addressed(found: Graph) -> None:
    """Give an address to each new part that requires one (sh:nodeKind sh:IRI).

    Make the address from the name, under the address of the node above the part. An example is a new step of a
    question, at casestudies/kidney/Q1/exposure."""
    taken = set()
    pending = True
    while pending:
        pending = False
        for holder, predicate, node in list(found):
            if not isinstance(node, BNode) or not isinstance(holder, URIRef):
                continue
            for field in fields(str(found.value(holder, RDF.type))):
                if field["iri"] == str(predicate) and field["addressed"]:
                    renamed(found, node, free(f"{holder}/{slug(str(found.value(node, SDO.name) or 'page'))}", taken))
                    pending = True


def separate(found: Graph) -> list[tuple[str, str, Graph]]:
    """Separate the new records that are sent as nodes without an address, such as a person added in the form.
    Make each node of the class of a kind, if not in a field of parts, a record at <kind>/<name>, linked from the
    record. Remove its statements from *found*, and return them with its class."""
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
    """Store a checked record document at its address, in place of the old record, with a revision."""
    iri = document["@id"]
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        created = db.get(Record, iri) is None
        db.execute(delete(Record).where((Record.iri == iri) | (Record.part_of == iri)))
        found = documents.statements(document)
        records.save(db, found, iri)
        db.execute(insert(Record), [{**row, "updated_at": version()} for row in records.rows(found, iri, kind, PLATFORM)])
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
    """Remove the record, and keep its address, so that it is not used again."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        for record in db.scalars(select(Record).where((Record.iri == iri) | (Record.part_of == iri))):
            record.removed_at = now()
            record.source = PLATFORM
            record.updated_at = version()
        revision = Revision(record_iri=iri, action="Removed", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision


def move(old: str, new: str, name: str, orcid: str) -> Revision:
    """Move the record and its parts with an address to a new address. Redirect the old and the earlier addresses
    to the new addresses, and store the old address in sameAs."""
    previous = documents.document_of(old)

    def moved(node):
        if isinstance(node, URIRef) and (str(node) == old or str(node).startswith(old + "/")):
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
        db.execute(insert(Record), [{**row, "updated_at": version()} for row in records.rows(found, new, record.type, PLATFORM)])
        for kept in db.scalars(select(Record).where((Record.iri == old) | (Record.part_of == old))):
            kept.removed_at = now()
            kept.moved_to = str(moved(URIRef(kept.iri)))
            kept.source = PLATFORM
            kept.updated_at = version()
        for earlier in db.scalars(select(Record).where(Record.moved_to == old)):
            earlier.moved_to = new
    document = documents.document_of(new)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=new, action="Moved", previous=previous, document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def restore(iri: str, name: str, orcid: str) -> Revision:
    """Restore a removed record as it was before the removal."""
    with database.session() as db, db.begin():
        for record in db.scalars(select(Record).where((Record.iri == iri) | (Record.part_of == iri))):
            record.removed_at = None
            record.updated_at = version()
    document = documents.document_of(iri)
    with database.session() as db, db.begin():
        revision = Revision(record_iri=iri, action="Restored", document=document, name=name, orcid=orcid)
        db.add(revision)
    return revision


def remove(iri: str, name: str, orcid: str) -> Revision:
    """Remove the record and its address, and keep its revisions."""
    previous = documents.document_of(iri)
    with database.session() as db, db.begin():
        records.delete(db, iri)
        db.execute(delete(Record).where((Record.iri == iri) | (Record.part_of == iri)))
        revision = Revision(record_iri=iri, action="Removed permanently", previous=previous, name=name, orcid=orcid)
        db.add(revision)
    return revision
