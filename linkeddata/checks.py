"""The checks of records against the model: pyshacl checks every record in the same way, with the model's
shapes, the class of each record it links to, and the class hierarchy of the vocabularies. A record
written on the platform is refused when it does not fit; the values of the sources that do not fit are
kept and noted."""

import pyshacl
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SH
from sqlalchemy import select

import database
from database.tables import Record
from linkeddata import documents
from linkeddata.model import hierarchy, shapes

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


def validate(found: Graph) -> Graph:
    """The results of the model's checks of some statements."""
    validated = Graph() + found
    linked = []
    for value in found.objects():
        if isinstance(value, URIRef):
            linked.append(str(value))
    with database.session() as db:
        for iri, kind in db.execute(select(Record.iri, Record.type).where(Record.iri.in_(linked))):
            validated.add((URIRef(iri), RDF.type, URIRef(kind)))
    _, results, _ = pyshacl.validate(validated, shacl_graph=shapes(), ont_graph=hierarchy())
    return results


def notes(found: Graph) -> list[dict]:
    """What the checks find in the records described in *found*, one note for each record, field, value and
    constraint. The records they link to, given with their class only, are not reported."""
    described = set()
    for subject, predicate in found.subject_predicates():
        if predicate != RDF.type:
            described.add(subject)
    every = shapes()
    results = validate(found)
    noted = {}
    for result in results.subjects(RDF.type, SH.ValidationResult):
        focus = results.value(result, SH.focusNode)
        if focus not in described:
            continue
        messages = []
        for message in results.objects(result, SH.resultMessage):
            messages.append(str(message))
        note = {
            "iri": str(focus),
            "field": str(results.value(result, SH.resultPath) or ""),
            "value": str(results.value(result, SH.value) or ""),
            "reason": " ".join(messages),
            "component": str(results.value(result, SH.sourceConstraintComponent)),
        }
        key = (note["iri"], note["field"], note["value"], note["component"])
        # A value can break the shapes of a class and of its superclass alike; the profile's message is kept.
        if key not in noted or every.value(results.value(result, SH.sourceShape), SH.message) is not None:
            noted[key] = note
    return list(noted.values())


def checked(new: dict) -> tuple[Graph, dict[str, list[str]], dict[str, list[str]]]:
    """A record's document as linked data, what is wrong with each of its fields, and what is only
    recommended; results of sh:Warning severity are recommendations."""
    found = documents.statements(new)
    every = shapes()
    results = validate(found)
    problems = {}
    warnings = {}
    for result in results.subjects(RDF.type, SH.ValidationResult):
        if results.value(result, SH.focusNode) != URIRef(new["@id"]):
            continue
        field = documents.term(str(results.value(result, SH.resultPath)))
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
            field = documents.term(str(predicate))
            if field not in problems:
                problems[field] = ["A web address starts with https:// or http://."]
    return found, problems, warnings


def check(new: dict) -> Graph:
    """A record's document as linked data; NotFitting tells what is wrong with each field when it does not fit."""
    found, problems, _ = checked(new)
    if problems:
        raise NotFitting(problems)
    return found
