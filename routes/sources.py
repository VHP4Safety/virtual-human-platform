"""The /sources page: where the records come from and how each source becomes the model."""

from flask import Blueprint, render_template
from sqlalchemy import func, select

import database
from database.tables import PLATFORM, Note, Record, Source
from linkeddata.imports import files_of, specs

blueprint = Blueprint("sources", __name__)


@blueprint.get("/sources")
def sources():
    """The sources are listed with their files, the last import, and the counts of their records and notes."""
    with database.session() as db:
        fetched = {source.name: source for source in db.scalars(select(Source))}
        counts = dict(db.execute(select(Record.source, func.count()).where(Record.removed_at.is_(None)).group_by(Record.source)).all())
        noted = dict(db.execute(select(Note.source, func.count()).group_by(Note.source)).all())
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
        })
    return render_template(
        "records/sources.html",
        sources=found,
        written=counts.get(PLATFORM, 0),
        page_title="Sources — VHP4Safety",
        meta_description="Where the VHP4Safety platform's records come from, and how each source becomes its model.",
    )
