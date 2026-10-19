"""Checks of records against the model with pyshacl: the model's shapes, the class of each linked record,
and the vocabularies' class hierarchy. A record written on the platform is refused when it does not fit;
misfitting source values are kept and noted."""

import pyshacl
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SH

from linkeddata import documents, fields, storage
from linkeddata.model import hierarchy, shapes

# Messages by SHACL constraint.
CONSTRAINTS = {
    "NodeKindConstraintComponent": "Web address expected.",
    "ClassConstraintComponent": "Unknown kind of link.",
    "DatatypeConstraintComponent": "Wrong type.",
    "OrConstraintComponent": "Wrong kind.",
    "MinCountConstraintComponent": "Missing.",
    "MaxCountConstraintComponent": "Only one value.",
    "HasValueConstraintComponent": "Fixed value missing or wrong.",
    "NodeConstraintComponent": "Part or link does not fit.",
}


class NotFitting(ValueError):
    """A record that does not fit the model, with the problems of each field."""

    def __init__(self, problems: dict[str, list[str]]):
        self.problems = problems
        messages = []
        for field, found in problems.items():
            for message in found:
                messages.append(f"{field}: {message}")
        super().__init__(" ".join(messages))


def meaning(component: str | None) -> str:
    name = (component or "").replace("#", ":").rsplit(":", 1)[-1]
    return CONSTRAINTS.get(name, "Does not fit the model.")


def validate(found: Graph) -> Graph:
    """The model's check results for some statements, with the class and name of the records they link to,
    so a link is checked against its record's class, and the classes their values are published as."""
    validated = documents.typed(storage.with_names(found))
    _, results, _ = pyshacl.validate(validated, shacl_graph=shapes(), ont_graph=hierarchy())
    return results


def notes(found: Graph) -> list[dict]:
    """The checks' notes on the records in *found*, one per record, field and value. Linked records, given
    with their class only, are not reported."""
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
        key = (note["iri"], note["field"], note["value"])
        # The profile's message is kept over a vocabulary's.
        if key not in noted or every.value(results.value(result, SH.sourceShape), SH.message) is not None:
            noted[key] = note
    return list(noted.values())


def checked(new: dict) -> tuple[Graph, dict[str, list[str]], dict[str, list[str]]]:
    """A record's document as linked data, its problems by field, and its recommendations. Any value that
    breaks a field of sh:Warning severity is a recommendation, with the profile's message. A part's field is
    named by the fields that lead to it (regulatoryQuestion > step > name)."""
    found = documents.statements(new)
    record = URIRef(new["@id"])
    results = validate(found)
    holders = {}
    for holder, predicate, node in found:
        if node != record and node not in holders and (node, None, None) in found:
            holders[node] = (holder, predicate)
    problems = {}
    warnings = {}
    for result in results.subjects(RDF.type, SH.ValidationResult):
        focus = results.value(result, SH.focusNode)
        trail = []
        node = focus
        while node != record and node in holders and len(trail) < len(holders):
            holder, predicate = holders[node]
            trail.insert(0, documents.term(str(predicate)))
            node = holder
        if node != record:
            continue
        form = {}
        for field in fields.of(str(found.value(focus, RDF.type))):
            form[field["iri"]] = field
        path = str(results.value(result, SH.resultPath))
        field = " > ".join(trail + [documents.term(path)])
        message = form[path]["message"] if path in form and form[path]["message"] else meaning(str(results.value(result, SH.sourceConstraintComponent)))
        warning = form[path]["warning"] if path in form else results.value(result, SH.resultSeverity) != SH.Violation
        found_in = warnings if warning else problems
        if message not in found_in.setdefault(field, []):
            found_in[field].append(message)
    # Only web addresses are taken, so a link never runs a script (javascript:) or opens a file.
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != RDF.type and not str(value).startswith(("https://", "http://")):
            field = documents.term(str(predicate))
            if field not in problems:
                problems[field] = ["Only https:// or http:// addresses."]
    return found, problems, warnings


def named(of_class: str, path: str) -> str:
    """A field's labels (Regulatory questions › Process flow steps › Title) from its JSON-LD names
    (regulatoryQuestion > step > name)."""
    names = []
    for term in path.split(" > "):
        found = None
        for field in fields.of(of_class):
            if field["name"] == term:
                found = field
        if found is None:
            names.append(term)
            continue
        names.append(found["label"])
        if found["classes"]:
            of_class = found["classes"][0]
    return " › ".join(names)


def check(new: dict) -> Graph:
    """A record's document as linked data; NotFitting is raised with each field's problems."""
    found, problems, _ = checked(new)
    if problems:
        raise NotFitting(problems)
    return found
