"""The record editor: for each kind of record an editor may write, a form built from the model that
writes and removes records through the write API with the editor's login."""

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for

from admin.editor import page
from linkeddata.model import settings
from routes.account import current_editor, form_token

blueprint = Blueprint("admin", __name__)


@blueprint.get("/admin/")
def admin():
    editor = current_editor()
    if editor is None:
        return redirect(url_for("account.login", next=request.path))
    return redirect(url_for("admin.edit", kind=editor.kinds[0]))


@blueprint.get("/admin/<kind>/")
def edit(kind: str):
    editor = current_editor()
    if editor is None:
        return redirect(url_for("account.login", next=request.path))
    kinds = settings()["kinds"]
    if kind not in kinds or kind not in editor.kinds:
        abort(404)
    data = page(kind)
    response = make_response(render_template(
        "admin/records.html",
        kind=kind,
        kinds=[other for other in editor.kinds if other in kinds],
        fields=data["fields"],
        data=data,
        form_token=form_token(),
        page_title=f"{kind.capitalize()} — VHP4Safety editor",
    ))
    response.headers["X-Robots-Tag"] = "noindex"
    return response
