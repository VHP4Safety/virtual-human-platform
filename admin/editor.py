"""The record editor's data: for each kind of record an editor may write, its records and a form built
from the model (see linkeddata/forms.py). A field that links to things offers, as choices, the records
of the classes that the other records link to in it, grouped by the source they come from, and the terms
of the vocabularies that the model lists for it."""

from sqlalchemy import func, select

import database
from database import records
from database.tables import PLATFORM, Record
from linkeddata import documents, forms, storage
from linkeddata.imports import specs
from linkeddata.model import curie, settings, terms


def used_values(kind: str, field: str) -> list[str]:
    """The values that the records of a class have in a field, most used first."""
    counts = {}
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.type == kind, Record.removed_at.is_(None))))
    found = storage.read(iris)
    for iri in iris:
        for value in documents.stored_values(found, iri, field):
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


def shown(statements, iri: str, field: dict):
    """The values of a field as the editor shows them: a list for a field with several values, else one value."""
    found = documents.stored_values(statements, iri, field["name"])
    if field["several"]:
        return found
    return found[0] if found else None


def page(kind: str) -> dict:
    """What the editor page of a kind shows: its records, the removed ones too, and the records each field
    can link to, grouped by the source they come from."""
    kinds = settings()["kinds"]
    fields = forms.form(kinds[kind])
    found = []
    with database.session() as db:
        listed = list(db.scalars(select(Record).where(Record.type == kinds[kind], Record.moved_to.is_(None)).order_by(Record.iri)))
    statements = storage.read([record.iri for record in listed])
    for record in listed:
        values = {}
        for field in fields:
            values[field["name"]] = shown(statements, record.iri, field)
        found.append({
            "iri": record.iri,
            "identifier": record.iri.removeprefix(records.address(kind) + "/"),
            "edited": record.source == PLATFORM,
            "removed": bool(record.removed_at),
            "version": record.updated_at,
            "values": values,
        })
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
            used = used_values(kinds[kind], field["name"])
            groups = {}
            rank = {}
            choices_of_field = linkable(kinds[kind], field)
            described = storage.read([choice.iri for choice in choices_of_field])
            options = []
            for choice in choices_of_field:
                descriptions = documents.stored_values(described, choice.iri, "description")
                options.append((titles.get(choice.source, choice.source), {"iri": choice.iri, "name": choice.name or choice.iri, "description": descriptions[0] if descriptions else ""}))
            for iri, term in terms(field["terms"]).items():
                options.append((term["title"], {"iri": iri, "name": term["name"], "description": term["description"]}))
            for title, option in options:
                groups.setdefault(title, []).append(option)
                if option["iri"] in used:
                    rank[title] = min(rank.get(title, len(used)), used.index(option["iri"]))
            ordered = sorted(groups, key=lambda title: rank.get(title, len(used)))
            choices[field["name"]] = [{"title": title, "options": groups[title]} for title in ordered]
    return {
        "kind": kind,
        "type": curie(kinds[kind]),
        "base": settings()["base"],
        "fields": fields,
        "records": found,
        "choices": choices,
        "names": records.names(titled),
    }
