"""What the pages about the data show: how complete the records are, what the checks of the imports
found, and where the records come from and how each source becomes the model."""

from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Note, Record, Source
from linkeddata import checks, documents, forms, storage
from linkeddata.imports import files_of, specs
from linkeddata.model import settings

def field_labels() -> dict[tuple[str, str], str]:
    """The name of each field on the platform, by its class and the address of its property."""
    labels = {}
    for kind in settings()["kinds"].values():
        for field in forms.form(kind):
            labels[(kind, field["iri"])] = field["label"]
    return labels


def report() -> dict:
    """How complete the records of each class are, and the notes of the checks grouped by field and constraint."""
    with database.session() as db:
        kept = list(db.scalars(select(Record).where(Record.removed_at.is_(None))))
        notes = list(db.scalars(select(Note).order_by(Note.field, Note.reason, Note.iri)))
    labels = field_labels()
    types = {}
    of_class = {}
    for record in kept:
        types[record.iri] = record.type
        of_class.setdefault(record.type, []).append(record)
    statements = storage.read(list(types))
    classes = []
    for kind in sorted(of_class):
        completeness = []
        for field in forms.form(kind):
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
            "meaning": checks.meaning(component),
            "reason": noted[0].reason,
            "notes": noted,
        })
    groups.sort(key=lambda group: -len(group["notes"]))
    iris = []
    for note in notes:
        iris.append(note.iri)
    return {"classes": classes, "groups": groups, "notes": len(notes), "names": records.names(iris)}


def mapping(spec: dict, labels: dict) -> list[dict]:
    """How a source becomes the model, read from its rules: each field of the source and the field it fills."""
    rows = []
    for kind, arguments in spec["rules"].items():
        target = ""
        for argument in arguments:
            if argument["predicate"] == "a":
                target = argument["value"]
        for argument in arguments:
            if argument["predicate"] == "a":
                rows.append({"kind": kind, "source": f"each {kind}", "platform": "is a", "value": target})
            elif "object" in argument:
                rows.append({"kind": kind, "source": argument["object"], "platform": labels.get((target, argument["predicate"]), argument["predicate"]), "value": ""})
            else:
                rows.append({"kind": kind, "source": "", "platform": labels.get((target, argument["predicate"]), argument["predicate"]), "value": argument["value"]})
    return rows


def sources() -> tuple[list[dict], int]:
    """Each source with its files, when it was fetched, its records and notes, and how it becomes the model;
    and how many records were written on the platform."""
    with database.session() as db:
        fetched = {source.name: source for source in db.scalars(select(Source))}
        counts = dict(db.execute(select(Record.source, func.count()).where(Record.removed_at.is_(None)).group_by(Record.source)).all())
        noted = dict(db.execute(select(Note.source, func.count()).group_by(Note.source)).all())
    labels = field_labels()
    found = []
    for spec in specs():
        found.append({
            "name": spec["name"],
            "title": spec.get("title", spec["name"]),
            "files": files_of(spec),
            "parser": spec["parser"],
            "fetched": fetched.get(spec["name"]),
            "records": counts.get(spec["name"], 0),
            "notes": noted.get(spec["name"], 0),
            "mapping": mapping(spec, labels),
        })
    return found, counts.get(PLATFORM, 0)
