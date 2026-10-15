"""Records as linked data. Each record is kept as a JSON-LD document, compacted with the platform's
context (document.py), so that its fields are named as in JSON-LD: https://schema.org/name is "name",
and http://purl.org/dc/terms/conformsTo is "dct:conformsTo". pyshacl checks a record against the
model's shapes before it is written.
"""

import json

import pyshacl
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SH
from sqlalchemy import select

import database
from database.tables import Record
from linkeddata.document import compact
from linkeddata.model import DASH, property_shapes, settings, shapes

# What breaking each SHACL constraint means for a curator, by the name of the constraint.
CONSTRAINTS = {
    "NodeKindConstraintComponent": "A text where a link (a web address) is expected.",
    "ClassConstraintComponent": "A link to something of which the platform does not know the kind.",
    "DatatypeConstraintComponent": "A value of the wrong type.",
    "OrConstraintComponent": "A value of a kind that this field does not take.",
    "MinCountConstraintComponent": "A required value is missing.",
    "MaxCountConstraintComponent": "Several values where the platform takes one.",
    "HasValueConstraintComponent": "A value that the platform sets is missing or different.",
}


class NotFitting(ValueError):
    """A record that does not fit the model, with what is wrong with each of its fields."""

    def __init__(self, problems: dict[str, list[str]]):
        self.problems = problems
        messages = []
        for field, found in problems.items():
            for message in found:
                messages.append(f"{field}: {message}")
        super().__init__(" ".join(messages))


def meaning(component: str | None) -> str:
    name = (component or "").replace("#", ":").rsplit(":", 1)[-1]
    return CONSTRAINTS.get(name, "A value that does not fit the model.")


def term(iri: str) -> str:
    """The name of a property or class in the platform's JSON-LD."""
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            if prefix == "schema":
                return iri.removeprefix(namespace)
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


def values(document: dict, name: str) -> list:
    """The values of a field of a document: the addresses of links, and texts or numbers."""
    given = document.get(name)
    found = []
    for item in given if isinstance(given, list) else [] if given is None else [given]:
        if isinstance(item, dict):
            item = item.get("@id", item.get("@value"))
        if item is not None:
            found.append(item)
    return found


def links(document: dict) -> list[str]:
    """The addresses that a document links to."""
    found = []
    for name, given in document.items():
        if name.startswith("@"):
            continue
        for item in given if isinstance(given, list) else [given]:
            if isinstance(item, dict) and "@id" in item:
                found.append(item["@id"])
    return found


def document(found: Graph, iri: str | None = None) -> dict:
    """The JSON-LD document of the record at *iri*: its own statements in *found*; without *iri*, of
    all the statements, such as those of a record and the records it links to."""
    own = found
    if iri is not None:
        own = Graph()
        for statement in found.triples((URIRef(iri), None, None)):
            own.add(statement)
    return compact(own.serialize(format="nt"), settings())


def row(document: dict, kind: str, source: str) -> dict:
    """The row of the records table that keeps a document."""
    names = values(document, "name")
    return {"iri": document["@id"], "type": kind, "source": source, "name": names[0] if names else None, "document": document}


def statements(document: dict) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


def graph(iris: list[str]) -> Graph:
    """The records at these addresses that are not removed, as linked data."""
    found = Graph()
    with database.session() as db:
        for record in db.scalars(select(Record).where(Record.iri.in_(iris), Record.removed_at.is_(None))):
            found += statements(record.document)
    for prefix, namespace in settings()["prefixes"].items():
        found.bind(prefix, namespace)
    return found


def linked_graph(record: Record) -> Graph:
    """The record and the records it links to, such as the terms of the glossary, as linked data."""
    return graph([record.iri, *links(record.document)])


def document_of(iri: str) -> str | None:
    """The record at this address in JSON-LD as it is now; None when there is none."""
    with database.session() as db:
        record = db.get(Record, iri)
    if record is None or record.removed_at:
        return None
    return json.dumps(record.document, indent=2)


def checked(new: dict) -> tuple[Graph, dict[str, list[str]], dict[str, list[str]]]:
    """A record's document as linked data, what is wrong with each of its fields, and what is only
    recommended. pyshacl checks it against the model's shapes, with the class of each record it links
    to; results of sh:Warning severity are recommendations."""
    found = statements(new)
    validated = Graph() + found
    with database.session() as db:
        for iri, kind in db.execute(select(Record.iri, Record.type).where(Record.iri.in_(links(new)))):
            validated.add((URIRef(iri), RDF.type, URIRef(kind)))
    every = shapes()
    _, results, _ = pyshacl.validate(validated, shacl_graph=every)
    problems = {}
    warnings = {}
    for result in results.subjects(RDF.type, SH.ValidationResult):
        if results.value(result, SH.focusNode) != URIRef(new["@id"]):
            continue
        field = term(str(results.value(result, SH.resultPath)))
        # The profile's message for the field, or what the broken constraint means.
        if every.value(results.value(result, SH.sourceShape), SH.message) is not None:
            message = str(results.value(result, SH.resultMessage))
        else:
            message = meaning(str(results.value(result, SH.sourceConstraintComponent)))
        found_in = problems if results.value(result, SH.resultSeverity) == SH.Violation else warnings
        if message not in found_in.setdefault(field, []):
            found_in[field].append(message)
    # Only web addresses are kept, so that a link on a page never runs a script (javascript:) or opens a file.
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != RDF.type and not str(value).startswith(("https://", "http://")):
            field = term(str(predicate))
            if field not in problems:
                problems[field] = ["A web address starts with https:// or http://."]
    return found, problems, warnings


def check(new: dict) -> Graph:
    """A record's document as linked data; NotFitting tells what is wrong with each field when it does not fit."""
    found, problems, _ = checked(new)
    if problems:
        raise NotFitting(problems)
    return found


def duplicates(new: dict, kind: str) -> dict[str, list[str]]:
    """The fields whose value another record of the class already has, where the model asks for a
    value that no other record has (dash:uniqueValueForClass)."""
    every = shapes()
    unique = []
    for path, nodes in property_shapes(every, kind).items():
        for node in nodes:
            if every.value(node, DASH.uniqueValueForClass) is not None:
                unique.append(term(path))
    found = {}
    with database.session() as db:
        others = list(db.scalars(select(Record).where(Record.type == kind, Record.iri != new["@id"], Record.removed_at.is_(None))))
    for field in unique:
        given = values(new, field)
        if not given or not isinstance(given[0], str):
            continue
        for other in others:
            if given[0].lower() in [str(value).lower() for value in values(other.document, field)]:
                path_of_other = "/" + other.iri.removeprefix(settings()["base"])
                found.setdefault(field, []).append(f"{other.name or other.iri} ({path_of_other}) has the same value; check that this is not a duplicate.")
                break
    return found
