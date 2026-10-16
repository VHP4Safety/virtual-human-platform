"""What the data pages show: record completeness, the checks' notes, and how each source becomes the model."""

from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Note, Record, Source
from linkeddata import checks, documents, fields, storage
from linkeddata.imports import files_of, specs
from linkeddata.model import settings

def field_labels() -> dict[tuple[str, str], str]:
    """Each field's label, by class and property."""
    labels = {}
    for kind in settings()["kinds"].values():
        for field in fields.of(kind):
            labels[(kind, field["iri"])] = field["label"]
    return labels


def report() -> dict:
    """The completeness of each class's records, and the checks' notes by field and constraint."""
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
        for field in fields.of(kind):
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
    """How a source becomes the model, from its rules: each source field and the field it fills."""
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
    """Each source with its files, fetch, records, notes and mapping; and the count of platform records."""
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
