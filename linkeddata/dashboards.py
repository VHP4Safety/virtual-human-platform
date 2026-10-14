"""Pages about the data. /data-quality shows how complete the records are and what the checks of the
imports found; /sources shows where the records come from and how each source becomes the model."""

import pandas as pd
from flask import Blueprint, render_template
from sqlalchemy import func, select

from linkeddata import database, forms, rdf, records
from linkeddata.database import PLATFORM, Note, Record, Source
from linkeddata.imports import files_of, specs
from linkeddata.model import settings

blueprint = Blueprint("dashboards", __name__)
# What breaking each SHACL constraint means for a curator, by the name of the constraint.
CONSTRAINTS = {
    "NodeKindConstraintComponent": "A text where a link (a web address) is expected.",
    "ClassConstraintComponent": "A link to something of which the platform does not know the kind.",
    "DatatypeConstraintComponent": "A value of the wrong type.",
    "MinCountConstraintComponent": "A required value is missing.",
    "MaxCountConstraintComponent": "Several values where the platform takes one.",
    "HasValueConstraintComponent": "A value that the platform sets is missing or different.",
}


def filled(values) -> int:
    """How many of the values are given: a text that is not empty, or a list that is not empty."""
    count = 0
    for value in values:
        if isinstance(value, (str, list)) and value:
            count += 1
    return count


def field_labels() -> dict[tuple[str, str], str]:
    """The name of each field on the platform, by its class and the address of its property."""
    labels = {}
    for kind in settings()["classes"]:
        known = rdf.fields(kind)
        for field in forms.form(kind):
            labels[(kind, known.loc[field["name"], "property"])] = field["label"]
    return labels


def meaning(component: str | None) -> str:
    name = (component or "").replace("#", ":").rsplit(":", 1)[-1]
    return CONSTRAINTS.get(name, "A value that does not fit the model.")


@blueprint.get("/data-quality")
def data_quality():
    with database.engine().connect() as connection:
        table = pd.read_sql(select(Record).where(Record.removed_at.is_(None)), connection)
        notes = pd.read_sql(select(Note).order_by(Note.field, Note.reason, Note.iri), connection)
    labels = field_labels()
    types = dict(zip(table["iri"], table["type"]))
    classes = []
    for kind, rows in table.groupby("type"):
        completeness = []
        for field in forms.form(kind):
            completeness.append({"field": field["label"], "required": field["required"], "records": filled(rows[field["name"]])})
        classes.append({"type": kind, "records": len(rows), "fields": completeness})
    groups = []
    for (field, component), rows in notes.groupby(["field", notes["component"].fillna("")]):
        kind = types.get(rows["iri"].iloc[0], "")
        groups.append({
            "field": labels.get((kind, field), field),
            "meaning": meaning(component),
            "reason": rows["reason"].iloc[0],
            "notes": rows.to_dict("records"),
        })
    groups.sort(key=lambda group: -len(group["notes"]))
    return render_template(
        "records/quality.html",
        classes=classes,
        groups=groups,
        notes=len(notes),
        names=records.names(list(notes["iri"])),
        written=PLATFORM,
        page_title="Data quality — VHP4Safety",
        meta_description="How complete the records of the VHP4Safety platform are, and what the checks of the model found.",
    )


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


@blueprint.get("/sources")
def sources():
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
    return render_template(
        "records/sources.html",
        sources=found,
        written=counts.get(PLATFORM, 0),
        page_title="Sources — VHP4Safety",
        meta_description="Where the records of the VHP4Safety platform come from, and how each source becomes the platform's model.",
    )
