"""Check records against the model."""

import pyshacl
from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import SH

from database import records
from linkeddata import documents
from linkeddata.profile import fields, hierarchy, jsonld_name, official_fields, shapes

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


def meaning(component: str | None) -> str:
    """Return the message for a SHACL constraint component."""
    name = (component or "").replace("#", ":").rsplit(":", 1)[-1]
    return CONSTRAINTS.get(name, "Does not fit the model.")


def official(result, results: Graph) -> tuple | None:
    """Return the property and the reason of a result of an official shape, or None."""
    if results.value(result, SH.sourceShape) not in official_fields():
        return None
    shape, path, needs = official_fields()[results.value(result, SH.sourceShape)]
    # A profile is named by its name and version, such as Bioschemas Dataset 1.0-RELEASE or PBPKModel 0.1-DRAFT.
    profile = str(shape).split("#")[0]
    named = ("Bioschemas " if "bioschemas.org/" in profile else "") + " ".join(profile.split("/")[-2:]) if "/profiles/" in profile else "schema.org"
    if "MinCount" not in str(results.value(result, SH.sourceConstraintComponent)):
        return path, f"{meaning(str(results.value(result, SH.sourceConstraintComponent)))[:-1]} for {named}."
    return path, f"{'Required' if needs else 'Recommended'} by {named}."


def record_of(found: Graph, node):
    """Return the record of a node, which is the node itself or the record above it."""
    match = records.PART.match(str(node)) if isinstance(node, URIRef) else None
    if match:
        return URIRef(match["record"])
    seen = set()
    while isinstance(node, BNode) and node not in seen:
        seen.add(node)
        node = next(found.subjects(None, node), node)
    return node


def in_form(found: Graph, node, path) -> bool:
    """Return True if path is a field of the node shape of a class of the node."""
    for of_class in found.objects(node, RDF.type):
        for field in fields(str(of_class)):
            if field["iri"] == str(path):
                return True
    return False


def validate(found: Graph) -> Graph:
    """Return the validation report of the statements in found."""
    validated = documents.typed(records.with_names(found))
    _, results, _ = pyshacl.validate(validated, shacl_graph=shapes(), ont_graph=hierarchy())
    return results


def notes(found: Graph) -> list[dict]:
    """Return the notes of the checks of the records in found."""
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
        given = official(result, results)
        # Note an official result only for a field of the form.
        if given and not in_form(found, focus, given[0]):
            continue
        path, reason = given or (results.value(result, SH.resultPath), " ".join(messages))
        note = {
            "iri": str(record_of(found, focus)),
            "field": str(path or ""),
            "value": str(results.value(result, SH.value) or ""),
            "reason": reason,
            "component": str(results.value(result, SH.sourceConstraintComponent)),
            "severity": str(results.value(result, SH.resultSeverity)).rsplit("#", 1)[-1],
        }
        key = (note["iri"], note["field"], note["value"])
        severity = [SH.Violation, SH.Warning, SH.Info].index(results.value(result, SH.resultSeverity))
        source = results.value(result, SH.sourceShape)
        # A shape of the class of the record is preferred to a shape of a superclass, such as CreativeWork.
        targets = set(every.objects(every.value(None, SH.property, source), SH.targetClass))
        rank = (severity, every.value(source, SH.message) is None, not targets & set(found.objects(focus, RDF.type)), note["component"], reason)
        if key not in noted or rank < noted[key][0]:
            noted[key] = (rank, note)
    kept = []
    for key in sorted(noted):
        kept.append(noted[key][1])
    return kept


def checked(new: dict) -> tuple[Graph, dict[str, list[str]], dict[str, list[str]]]:
    """Return the statements of a record document, with its problems and recommendations."""
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
        for field in fields(records.class_of(found, focus)):
            form[field["iri"]] = field
        given = official(result, results)
        if given and not in_form(found, focus, given[0]):
            continue
        path = str(given[0] if given else results.value(result, SH.resultPath))
        field = " > ".join(trail + [jsonld_name(path)])
        message = form[path]["message"] if path in form and form[path]["message"] else (given[1] if given else meaning(str(results.value(result, SH.sourceConstraintComponent))))
        warning = results.value(result, SH.resultSeverity) != SH.Violation
        found_in = warnings if warning else problems
        if message not in found_in.setdefault(field, []):
            found_in[field].append(message)
    return found, problems, warnings


def named(of_class: str, path: str) -> str:
    """Return the labels of a field path."""
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
