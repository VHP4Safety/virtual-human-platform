"""Launch of the platform.

Import all sources once, including the sources of this folder. Then make the corrections of launch.yaml. Each
correction moves or replaces values of a field, or moves the record to another address (to), where it is merged with
the record at that address, if there is one. Store it as a revision with its reason. After a correction, the record
belongs to the platform, and later imports keep it unchanged."""

from pathlib import Path

import yaml
from rdflib import RDF, BNode, Graph, Literal, URIRef

from admin import writes
from database import records
from linkeddata import checks, documents
from linkeddata.imports import import_all

CORRECTIONS = Path(__file__).parent / "launch.yaml"
NAME = "VHP4Safety launch"


def corrected(found: Graph, correction: dict) -> int:
    """Apply a correction to the statements of a record, in place, and return the number of changed values."""
    changed = 0
    for move in correction.get("move") or []:
        field = URIRef(documents.expand(move["field"]))
        to = URIRef(documents.expand(move["to"]))
        for subject, value in list(found.subject_objects(field)):
            # A value, or the part with the value, such as a use of a tool with that text as its item.
            held = [str(given) for predicate, given in found.predicate_objects(value) if predicate != RDF.type] if isinstance(value, BNode) else [str(value)]
            if set(held) & set(move["values"]):
                found.remove((subject, field, value))
                # A text that is an address, such as a website in an email field.
                if move.get("address") and isinstance(value, Literal):
                    value = URIRef(str(value))
                found.add((subject, to, value))
                if "as" in move:
                    found.set((value, RDF.type, URIRef(documents.expand(move["as"]))))
                changed += 1
    for replace in correction.get("replace") or []:
        field = URIRef(documents.expand(replace["field"]))
        for subject, value in list(found.subject_objects(field)):
            if isinstance(value, Literal) and replace["from"] in str(value):
                found.remove((subject, field, value))
                found.add((subject, field, Literal(str(value).replace(replace["from"], replace["to"]), lang=value.language, datatype=value.datatype)))
                changed += 1
    return changed


def launch() -> list[str]:
    """Import all sources, then make and store all corrections of launch.yaml. Return what could not be imported or
    made. Refuse a database with imported records."""
    problems = import_all(once=True)
    for correction in yaml.safe_load(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]:
        iri = records.address(correction["record"])
        record = records.get(iri)
        if record is None:
            problems.append(f"{correction['record']}: no such record.")
            continue
        found = records.graph([iri])
        changed = corrected(found, correction)
        name = f"{NAME}: {correction['why']}"
        if "to" in correction:
            new = records.address(correction["to"])
            kept = records.get(new)
            kind = kept.type if kept is not None else documents.expand(correction["as"]) if "as" in correction else record.type
            writes.merge(found, iri, new, kind, name, "")
            print(f"{correction['record']}: moved to {correction['to']} ({correction['why']})")
            continue
        if not changed:
            problems.append(f"{correction['record']}: nothing to correct ({correction['why']})")
            continue
        document = documents.document(found, iri)
        writes.save(document, record.type, name, "")
        _, wrong, _ = checks.checked(document)
        print(f"{correction['record']}: corrected ({correction['why']}); {len(wrong)} fields still do not fit")
    return problems
