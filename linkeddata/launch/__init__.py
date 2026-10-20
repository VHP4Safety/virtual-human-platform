"""The import made once when the platform goes live, of every source, those of this folder too, and the corrections of
launch.yaml. A correction moves or replaces values of a field. It is saved as a revision named with its reason;
the record then belongs to the platform and is not changed by imports."""

from pathlib import Path

import yaml
from rdflib import RDF, BNode, Graph, Literal, URIRef

from admin import writes
from database import records
from linkeddata import checks, documents, storage
from linkeddata.imports import import_all

CORRECTIONS = Path(__file__).parent / "launch.yaml"
NAME = "VHP4Safety launch"


def corrected(found: Graph, correction: dict) -> int:
    """The count of values a correction changes in a record's statements, which are changed in place."""
    changed = 0
    for move in correction.get("move") or []:
        field = URIRef(documents.expand(move["field"]))
        to = URIRef(documents.expand(move["to"]))
        for subject, value in list(found.subject_objects(field)):
            # A value, or a part that holds it, such as a tool's use whose item is that text.
            held = [str(given) for predicate, given in found.predicate_objects(value) if predicate != RDF.type] if isinstance(value, BNode) else [str(value)]
            if set(held) & set(move["values"]):
                found.remove((subject, field, value))
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
    """Every source is imported, then every correction of launch.yaml is made and saved; what could not be
    imported or made is given back."""
    problems = import_all(once=True)
    for correction in yaml.safe_load(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]:
        iri = records.address(correction["record"])
        record = records.get(iri)
        if record is None:
            problems.append(f"{correction['record']}: no such record.")
            continue
        found = storage.graph([iri])
        if not corrected(found, correction):
            problems.append(f"{correction['record']}: nothing to correct ({correction['why']})")
            continue
        document = documents.document(found, iri)
        writes.save(document, record.type, f"{NAME}: {correction['why']}", "")
        _, wrong, _ = checks.checked(document)
        print(f"{correction['record']}: corrected ({correction['why']}); {len(wrong)} fields still do not fit")
    return problems
