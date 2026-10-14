"""Pages about the data. /data-quality shows how complete the records are and what the checks of the
imports found; /sources shows where the records come from and the changes made on the platform."""

import pandas as pd
from flask import Blueprint, render_template
from sqlalchemy import func, select

from linkeddata import database, rdf, records
from linkeddata.database import Note, Record, Source

blueprint = Blueprint("dashboards", __name__)


def filled(values) -> int:
    """How many of the values are given: a text that is not empty, or a list that is not empty."""
    count = 0
    for value in values:
        if isinstance(value, (str, list)) and value:
            count += 1
    return count


@blueprint.get("/data-quality")
def data_quality():
    with database.engine().connect() as connection:
        table = pd.read_sql(select(Record).where(Record.removed_at.is_(None)), connection)
        notes = pd.read_sql(select(Note).order_by(Note.field, Note.reason, Note.iri), connection)
    classes = []
    for kind, rows in table.groupby("type"):
        known = rdf.fields(kind)
        completeness = []
        for field in known.index:
            completeness.append({"field": known.loc[field, "label"], "records": filled(rows[field])})
        completeness.sort(key=lambda item: -item["records"])
        classes.append({"type": kind, "records": len(rows), "fields": completeness})
    groups = []
    for (field, reason), rows in notes.groupby(["field", "reason"]):
        groups.append({"field": field, "reason": reason, "notes": rows.to_dict("records")})
    groups.sort(key=lambda group: -len(group["notes"]))
    return render_template(
        "records/quality.html",
        classes=classes,
        groups=groups,
        notes=len(notes),
        page_title="Data quality — VHP4Safety",
        meta_description="How complete the records of the VHP4Safety platform are, and what the checks of the model found.",
    )


@blueprint.get("/sources")
def sources():
    with database.session() as db:
        found = list(db.scalars(select(Source).order_by(Source.name)))
        counts = db.execute(
            select(Record.source, Record.type, func.count()).where(Record.removed_at.is_(None)).group_by(Record.source, Record.type)
        ).all()
    return render_template(
        "records/sources.html",
        sources=found,
        counts=counts,
        changes=records.history(25),
        page_title="Sources — VHP4Safety",
        meta_description="Where the records of the VHP4Safety platform come from, how they are converted, and the changes made on the platform.",
    )
