"""The corrections made to the records when the platform first goes live, after the first import, as
launch.yaml lists them. A correction moves values of a field to another field, or replaces a piece of text
in the values of a field, anywhere in a record and its parts. Each is saved as a revision of its record,
named with why it was made, and the record is from then on a record of the platform, which imports leave as
it is; what the checks still find in it is told, for editors to fix."""

from pathlib import Path

import yaml
from rdflib import Graph, Literal, URIRef

from admin import writes
from database import records
from linkeddata import checks, documents, storage

CORRECTIONS = Path(__file__).parent / "launch.yaml"
NAME = "VHP4Safety launch"


def corrected(found: Graph, correction: dict) -> int:
    """How many values a correction changed in the statements of a record, which it changes."""
    changed = 0
    for move in correction.get("move") or []:
        field = URIRef(documents.expand(move["field"]))
        to = URIRef(documents.expand(move["to"]))
        for subject, value in list(found.subject_objects(field)):
            if str(value) in move["values"]:
                found.remove((subject, field, value))
                found.add((subject, to, value))
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
    """Every correction of launch.yaml is made and saved; what could not be made is given back."""
    problems = []
    for correction in yaml.safe_load(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]:
        iri = records.address(correction["record"])
        record = records.get(iri)
        if record is None:
            problems.append(f"{correction['record']}: there is no such record.")
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
