"""Checks of the records against the model, with pyshacl, and the content of the data quality page."""

import re

import pyshacl
from rdflib import RDF, BNode, Graph, URIRef
from rdflib.namespace import DCTERMS, RDFS, SDO, SH
from sqlalchemy import select

import database
from database import records
from database.tables import Note, Record, Source
from linkeddata import documents
from linkeddata.profile import fields, hierarchy, jsonld_name, official_fields, profile_graph, settings, shape_of, shapes

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
    """Return the property and the reason of a result of an official shape, such as "Required by Bioschemas Person
    0.3-DRAFT.". Report such a result as a note or a recommendation, and do not refuse a write for it. Return None
    for a result of the shapes of the model."""
    if results.value(result, SH.sourceShape) not in official_fields():
        return None
    shape, path, needs = official_fields()[results.value(result, SH.sourceShape)]
    named = "Bioschemas " + " ".join(str(shape).split("/")[-2:]) if "bioschemas.org/profiles/" in str(shape) else "schema.org"
    if "MinCount" not in str(results.value(result, SH.sourceConstraintComponent)):
        return path, f"{meaning(str(results.value(result, SH.sourceConstraintComponent)))[:-1]} for {named}."
    return path, f"{'Required' if needs else 'Recommended'} by {named}."


# The reasons of the results of official shapes, as official() writes them.
OFFICIAL = re.compile(r"(by|for) (Bioschemas .+|schema\.org)\.$")
# The properties that are added when a record is published (documents.typed()), so they are no gaps of the profile.
PUBLISHED = {RDF.type, SDO.url, SDO.mainEntityOfPage, DCTERMS.conformsTo}


def record_of(found: Graph, node):
    """Return the record of a node: the node if it has an address, else the record above it. A part address
    (<record>#<field>-<n>) gives its record."""
    match = records.PART.match(str(node)) if isinstance(node, URIRef) else None
    if match:
        return URIRef(match["record"])
    seen = set()
    while isinstance(node, BNode) and node not in seen:
        seen.add(node)
        node = next(found.subjects(None, node), node)
    return node


def in_form(found: Graph, node, path) -> bool:
    """Return True if *path* is a field of the node shape of a class of *node*, so that it can be filled in the
    editor."""
    for of_class in found.objects(node, RDF.type):
        for field in fields(str(of_class)):
            if field["iri"] == str(path):
                return True
    return False


def gaps() -> list[dict]:
    """Return, for each node shape that declares an official profile (dct:conformsTo), the fields of that profile
    that are not in the node shape.

    Such fields cannot be filled in the editor, so they are not reported for records. Add a field to the profile to
    check it."""
    graph = profile_graph()
    found = []
    for shape, conformed in sorted(graph.subject_objects(DCTERMS.conformsTo)):
        own = set()
        for of_class in graph.objects(shape, SH.targetClass):
            own.update(field["iri"] for field in fields(str(of_class)))
        missing = {}
        for official_shape, path, needs in official_fields().values():
            if official_shape == conformed and path not in PUBLISHED and str(path) not in own:
                missing[jsonld_name(str(path))] = missing.get(jsonld_name(str(path))) or needs
        if missing:
            found.append({"kind": str(graph.value(shape, RDFS.label) or shape), "profile": " ".join(str(conformed).split("/")[-2:]),
                          "required": sorted(name for name, needs in missing.items() if needs),
                          "recommended": sorted(name for name, needs in missing.items() if not needs)})
    return found


def validate(found: Graph) -> Graph:
    """Check statements with the shapes of the model. Add the class and the name of each linked record first, so
    that a link is checked against the class of that record."""
    validated = documents.typed(records.with_names(found))
    _, results, _ = pyshacl.validate(validated, shacl_graph=shapes(), ont_graph=hierarchy())
    return results


def notes(found: Graph) -> list[dict]:
    """Make the notes of the checks for the records in *found*.

    Make one note for each record, field and value. Do not report linked records with their class only. Of several
    results for the same record, field and value, choose in this order: the most severe result, a result with a
    message in the profile, a result of a shape of the class of the record, then by constraint and reason. So the
    notes are the same on each run."""
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
        # An official result is noted only for a field of the form, as other fields cannot be filled (gaps()).
        if given and not in_form(found, focus, given[0]):
            continue
        path, reason = given or (results.value(result, SH.resultPath), " ".join(messages))
        note = {
            "iri": str(record_of(found, focus)),
            "field": str(path or ""),
            "value": str(results.value(result, SH.value) or ""),
            "reason": reason,
            "component": str(results.value(result, SH.sourceConstraintComponent)),
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
    """Convert a record document to statements and check them. Return the problems and the recommendations by
    field. A value that does not fit a field of sh:Warning severity is a recommendation, with the message of the
    profile. Name a field of a part by the path of fields to it (regulatoryQuestion > step > name)."""
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
        if given and not in_form(found, focus, given[0]):
            continue
        path = str(given[0] if given else results.value(result, SH.resultPath))
        field = " > ".join(trail + [jsonld_name(path)])
        message = form[path]["message"] if path in form and form[path]["message"] else meaning(str(results.value(result, SH.sourceConstraintComponent)))
        warning = form[path]["warning"] if path in form else results.value(result, SH.resultSeverity) != SH.Violation
        if given:
            message, warning = given[1], True
        found_in = warnings if warning else problems
        if message not in found_in.setdefault(field, []):
            found_in[field].append(message)
    return found, problems, warnings


def named(of_class: str, path: str) -> str:
    """Return the labels of a field path, such as "Regulatory questions › Process flow steps › Title" for
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
    """Return the content of the data quality page.

    Summarise each kind of records, group the notes of the checks by kind, field and problem, and list the failed
    imports, the gaps of the profile (gaps()) and the draft terms that their vocabularies do not have yet."""
    with database.session() as db:
        kept = list(db.scalars(select(Record).where(Record.removed_at.is_(None), Record.moved_to.is_(None), Record.part_of.is_(None))))
        notes = list(db.scalars(select(Note).order_by(Note.iri, Note.field)))
        failed = []
        for source in db.scalars(select(Source).order_by(Source.name)):
            if source.problem:
                failed.append({"name": source.name, "problem": source.problem})
    graph = profile_graph()
    paths = {}
    for path, of_class in settings()["kinds"].items():
        for within in records.within(of_class):
            paths.setdefault(within, path)
    kind_of = {}
    for record in kept:
        kind_of[record.iri] = paths.get(record.type, "")
    statements = records.read(list(kind_of))
    # A field of a part, such as a compartment of a model, is named by the label of its field in any shape.
    every = {}
    for of_class in set(graph.objects(None, SH.targetClass)):
        for field in fields(str(of_class)):
            every.setdefault(field["iri"], field["label"])
    summary = []
    noted = []
    for path, of_class in settings()["kinds"].items():
        listed = {iri for iri, kind in kind_of.items() if kind == path}
        if not listed:
            continue
        name = str(graph.value(shape_of(of_class), RDFS.label) or path)
        labels = {}
        messages = {}
        missing = []
        for field in fields(of_class):
            labels[field["iri"]] = field["label"]
            messages[field["iri"]] = field["message"]
            if field["required"]:
                empty = len([iri for iri in listed if not documents.stored_values(statements, iri, field["name"])])
                if empty:
                    missing.append({"field": field["label"], "records": empty})
        own = [note for note in notes if note.iri in listed]
        summary.append({"path": path, "name": name, "records": len(listed), "noted": len({note.iri for note in own}), "notes": len(own),
                        "missing": missing})
        groups = {}
        for note in own:
            problem = note.reason if OFFICIAL.search(note.reason) else messages.get(note.field) or meaning(note.component)
            groups.setdefault((labels.get(note.field) or every.get(note.field) or jsonld_name(note.field), problem), []).append(note)
        if groups:
            noted.append({"path": path, "name": name, "groups": [{"field": field, "reason": reason, "notes": found}
                                                              for (field, reason), found in sorted(groups.items(), key=lambda item: -len(item[1]))]})
    drafts = sorted({iri for iri, value in records.values(str(SDO.DefinedTerm), str(SDO.creativeWorkStatus)) if str(value) == "Draft"})
    return {"summary": summary, "noted": noted, "notes": len(notes), "failed": failed, "gaps": gaps(),
            "names": records.names(sorted({note.iri for note in notes} | set(drafts))),
            "drafts": [record.iri for record in records.kept(drafts)]}
