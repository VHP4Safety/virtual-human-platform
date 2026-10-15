"""The record editor's data: for each kind of record an editor may write, its records and a form built
from the model (see linkeddata/forms.py). A field that links to things offers, as choices, the records
of the classes that the other records link to in it, grouped by the source they come from."""

from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Record
from linkeddata import forms, rdf
from linkeddata.imports import specs
from linkeddata.model import curie, settings


def used_values(kind: str, field: str) -> list[str]:
    """The values that the records of a class have in a field, most used first."""
    counts = {}
    with database.session() as db:
        for document in db.scalars(select(Record.document).where(Record.type == kind, Record.removed_at.is_(None))):
            for value in rdf.values(document, field):
                counts[value] = counts.get(value, 0) + 1
    return sorted(counts, key=lambda value: (-counts[value], value))


def linkable(kind: str, field: dict) -> list[Record]:
    """The records that a field can link to: those of the classes that the model names for it, or else
    those that the records of *kind* already link to in it."""
    with database.session() as db:
        if field["classes"]:
            statement = select(Record).where(Record.type.in_(field["classes"]))
        else:
            statement = select(Record).where(Record.iri.in_(used_values(kind, field["name"])))
        statement = statement.where(Record.removed_at.is_(None))
        return list(db.scalars(statement.order_by(Record.source, func.lower(Record.name))))


def shown(document: dict, field: dict):
    """The values of a field as the editor shows them: a list for a field with several values, else one value."""
    found = rdf.values(document, field["name"])
    if field["several"]:
        return found
    return found[0] if found else None


def page(kind: str) -> dict:
    """What the editor page of a kind shows: its records, the removed ones too, and the records each field
    can link to, grouped by the source they come from."""
    writable = settings().get("writable", {})
    fields = forms.form(writable[kind])
    found = []
    for record in records.of_kind(kind):
        values = {}
        for field in fields:
            values[field["name"]] = shown(record.document, field)
        found.append({
            "identifier": record.iri.rsplit("/", 1)[-1],
            "edited": record.source == PLATFORM,
            "removed": False,
            "version": record.updated_at,
            "values": values,
        })
    for identifier in sorted(records.removed(kind)):
        removed = records.get(records.address(f"{kind}/{identifier}"))
        values = {}
        for field in fields:
            values[field["name"]] = shown(removed.document, field)
        found.append({"identifier": identifier, "edited": True, "removed": True, "version": removed.updated_at, "values": values})
    titles = {}
    for spec in specs():
        titles[spec["name"]] = spec.get("title", spec["name"])
    choices = {}
    titled = []
    for field in fields:
        if field["entry"] == "details":
            for record in found:
                titled.extend(record["values"].get(field["name"]) or [])
        if field["entry"] in ("links", "choice"):
            # The groups that the records use most come first.
            used = used_values(writable[kind], field["name"])
            groups = {}
            rank = {}
            for choice in linkable(writable[kind], field):
                title = titles.get(choice.source, choice.source)
                descriptions = rdf.values(choice.document, "description")
                groups.setdefault(title, []).append({"iri": choice.iri, "name": choice.name or choice.iri, "description": descriptions[0] if descriptions else ""})
                if choice.iri in used:
                    rank[title] = min(rank.get(title, len(used)), used.index(choice.iri))
            ordered = sorted(groups, key=lambda title: rank.get(title, len(used)))
            choices[field["name"]] = [{"title": title, "options": groups[title]} for title in ordered]
    return {
        "kind": kind,
        "type": curie(writable[kind]),
        "base": settings()["base"],
        "fields": fields,
        "records": found,
        "choices": choices,
        "names": records.names(titled),
    }
