"""The record editor: for each kind of record an editor may write, a form built from the model (see
forms.py) that writes and removes records through the write API with the editor's login. A field that
links to things offers, as choices, the records of the classes that the other records link to in it,
grouped by the source they come from."""

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for

from linkeddata import accounts, forms, records
from linkeddata.database import PLATFORM
from linkeddata.imports import specs
from linkeddata.model import curie, settings

blueprint = Blueprint("admin", __name__)


@blueprint.get("/admin/")
def admin():
    editor = accounts.current_editor()
    if editor is None:
        return redirect(url_for("account.login", next=request.path))
    return redirect(url_for("admin.edit", kind=editor.kinds[0]))


@blueprint.get("/admin/<kind>/")
def edit(kind: str):
    editor = accounts.current_editor()
    if editor is None:
        return redirect(url_for("account.login", next=request.path))
    writable = settings().get("writable", {})
    if kind not in writable or kind not in editor.kinds:
        abort(404)
    fields = forms.form(writable[kind])
    found = []
    for record in records.of_kind(kind):
        values = {}
        for field in fields:
            values[field["name"]] = getattr(record, field["name"])
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
            values[field["name"]] = getattr(removed, field["name"])
        found.append({"identifier": identifier, "edited": True, "removed": True, "version": removed.updated_at, "values": values})
    titles = {}
    for spec in specs():
        titles[spec["name"]] = spec.get("title", spec["name"])
    choices = {}
    for field in fields:
        if field["entry"] == "links":
            # The groups that the records use most come first.
            used = records.used_values(writable[kind], field["name"])
            groups = {}
            rank = {}
            for choice in records.choices(writable[kind], field["name"]):
                title = titles.get(choice.source, choice.source)
                groups.setdefault(title, []).append({"iri": choice.iri, "name": choice.name or choice.iri, "description": choice.description or ""})
                if choice.iri in used:
                    rank[title] = min(rank.get(title, len(used)), used.index(choice.iri))
            ordered = sorted(groups, key=lambda title: rank.get(title, len(used)))
            choices[field["name"]] = [{"title": title, "options": groups[title]} for title in ordered]
    data = {
        "kind": kind,
        "type": curie(writable[kind]),
        "base": settings()["base"],
        "fields": fields,
        "records": found,
        "choices": choices,
    }
    response = make_response(render_template(
        "admin/records.html",
        kind=kind,
        kinds=[other for other in editor.kinds if other in writable],
        fields=fields,
        data=data,
        form_token=accounts.form_token(),
        page_title=f"{kind.capitalize()} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response
