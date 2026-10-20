"""Records are checked against the model here with pyshacl. The data quality page is also made here from the notes
of the checks."""

import pyshacl
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SH
from sqlalchemy import select

import database
from database import records
from database.tables import Note, Record
from linkeddata import documents, storage
from linkeddata.profile import fields, hierarchy, jsonld_name, official_fields, settings, shapes

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
    """This error is given for a record that does not fit the model. The message tells the problems of each field."""

    def __init__(self, problems: dict[str, list[str]]):
        messages = []
        for field, found in problems.items():
            for message in found:
                messages.append(f"{field}: {message}")
        super().__init__(" ".join(messages))


def meaning(component: str | None) -> str:
    """The message for a SHACL constraint component is given here."""
    name = (component or "").replace("#", ":").rsplit(":", 1)[-1]
    return CONSTRAINTS.get(name, "Does not fit the model.")


def official(result, results: Graph) -> tuple | None:
    """The property and the reason of a result of an official shape are given here, such as "Required by Bioschemas
    Person 0.3-DRAFT.". Such a result is a note or a recommendation, never a refusal. None is given for a result of
    the shapes of the model."""
    if results.value(result, SH.sourceShape) not in official_fields():
        return None
    shape, path, needs = official_fields()[results.value(result, SH.sourceShape)]
    named = "Bioschemas " + " ".join(str(shape).split("/")[-2:]) if "bioschemas.org/profiles/" in str(shape) else "schema.org"
    if "MinCount" not in str(results.value(result, SH.sourceConstraintComponent)):
        return path, f"{meaning(str(results.value(result, SH.sourceConstraintComponent)))[:-1]} for {named}."
    return path, f"{'Required' if needs else 'Recommended'} by {named}."


def validate(found: Graph) -> Graph:
    """Statements are checked with the shapes of the model. The class and the name of each linked record are added
    first, so that a link is checked against the class of that record."""
    validated = documents.typed(storage.with_names(found))
    _, results, _ = pyshacl.validate(validated, shacl_graph=shapes(), ont_graph=hierarchy())
    return results


def notes(found: Graph) -> list[dict]:
    """The notes of the checks are made for the records in *found*, one note for each record, field and value.
    Linked records that are given with their class only are not reported."""
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
        path, reason = official(result, results) or (results.value(result, SH.resultPath), " ".join(messages))
        note = {
            "iri": str(focus),
            "field": str(path or ""),
            "value": str(results.value(result, SH.value) or ""),
            "reason": reason,
            "component": str(results.value(result, SH.sourceConstraintComponent)),
        }
        key = (note["iri"], note["field"], note["value"])
        # The profile's message is kept over a vocabulary's.
        if key not in noted or every.value(results.value(result, SH.sourceShape), SH.message) is not None:
            noted[key] = note
    return list(noted.values())


def checked(new: dict) -> tuple[Graph, dict[str, list[str]], dict[str, list[str]]]:
    """A record document is converted to statements and checked. The problems and the recommendations are given by
    field. A value that does not fit a field of sh:Warning severity is a recommendation, with the message of the
    profile. A field of a part is named by the fields that lead to it (regulatoryQuestion > step > name)."""
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
            trail.insert(0, jsonld_name(str(predicate)))
            node = holder
        if node != record:
            continue
        form = {}
        for field in fields(str(found.value(focus, RDF.type))):
            form[field["iri"]] = field
        given = official(result, results)
        path = str(given[0] if given else results.value(result, SH.resultPath))
        field = " > ".join(trail + [jsonld_name(path)])
        message = form[path]["message"] if path in form and form[path]["message"] else meaning(str(results.value(result, SH.sourceConstraintComponent)))
        warning = form[path]["warning"] if path in form else results.value(result, SH.resultSeverity) != SH.Violation
        if given:
            message, warning = given[1], True
        found_in = warnings if warning else problems
        if message not in found_in.setdefault(field, []):
            found_in[field].append(message)
    # Only web addresses are taken, so a link never runs a script (javascript:) or opens a file.
    for _, predicate, value in found:
        if isinstance(value, URIRef) and predicate != RDF.type and not str(value).startswith(("https://", "http://")):
            field = jsonld_name(str(predicate))
            if field not in problems:
                problems[field] = ["Only https:// or http:// addresses."]
    return found, problems, warnings


def named(of_class: str, path: str) -> str:
    """The labels of a field path are given here, such as "Regulatory questions › Process flow steps › Title" for
    "regulatoryQuestion > step > name"."""
    names = []
    for term in path.split(" > "):
        found = None
        for field in fields(of_class):
            if field["name"] == term:
                found = field
        if found is None:
            names.append(term)
            continue
        names.append(found["label"])
        if found["classes"]:
            of_class = found["classes"][0]
    return " › ".join(names)


def report() -> dict:
    """The data quality page is made here. The filled fields of each kind of records are counted, and the notes of
    the checks are grouped by field and constraint."""
    with database.session() as db:
        kept = list(db.scalars(select(Record).where(Record.removed_at.is_(None))))
        notes = list(db.scalars(select(Note).order_by(Note.field, Note.reason, Note.iri)))
    labels = {}
    for kind in settings()["kinds"].values():
        for field in fields(kind):
            labels[(kind, field["iri"])] = field["label"]
    types = {}
    of_class = {}
    for record in kept:
        types[record.iri] = record.type
        of_class.setdefault(record.type, []).append(record)
    statements = storage.read(list(types))
    classes = []
    for kind in sorted(of_class):
        completeness = []
        for field in fields(kind):
            filled = 0
            for record in of_class[kind]:
                if documents.stored_values(statements, record.iri, field["name"]):
                    filled += 1
            completeness.append({"field": field["label"], "required": field["required"], "records": filled})
        classes.append({"type": kind, "records": len(of_class[kind]), "fields": completeness})
    grouped = {}
    for note in notes:
        grouped.setdefault((note.field, note.component or ""), []).append(note)
    groups = []
    for (field, component), noted in grouped.items():
        groups.append({
            "field": labels.get((types.get(noted[0].iri, ""), field), field),
            "meaning": meaning(component),
            "reason": noted[0].reason,
            "notes": noted,
        })
    groups.sort(key=lambda group: -len(group["notes"]))
    iris = []
    for note in notes:
        iris.append(note.iri)
    return {"classes": classes, "groups": groups, "notes": len(notes), "names": records.names(iris)}
