"""Editors log in with ORCID, as in ToxTempAssistant, and manage their write tokens.

The login uses ORCID's OAuth with the /authenticate scope (the sandbox when FLASK_DEBUG=1). ORCID
gives the editor's ORCID iD and name; nothing else is kept. Editors are the ORCID iDs listed in
PLATFORM_EDITORS. The application's credentials are ORCID_CLIENT_ID and ORCID_CLIENT_SECRET, and its
redirect URI at ORCID is <platform>/orcid/callback/. An editor who was given a write token can also
log in with it; such a login ends when the token is revoked or expires, and only writes the kinds of
records of the token.

The editor page writes through the write API with the editor's login: its requests carry the form
token of the session in the X-Form-Token header, which pages of other sites cannot send.
"""

import hmac
import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from linkeddata import tokens
from linkeddata.model import settings

blueprint = Blueprint("account", __name__)


@dataclass
class Editor:
    name: str
    orcid: str
    kinds: list[str]


def orcid_base() -> str:
    return "https://sandbox.orcid.org" if os.environ.get("FLASK_DEBUG") == "1" else "https://orcid.org"


def editors() -> set[str]:
    return {orcid.strip() for orcid in os.environ.get("PLATFORM_EDITORS", "").split(",") if orcid.strip()}


def callback_address() -> str:
    return url_for("account.orcid_callback", _external=True)


def form_token() -> str:
    """The token that the account forms send back, so that other sites cannot send them."""
    if "form_token" not in session:
        session["form_token"] = secrets.token_urlsafe(32)
    return session["form_token"]


def check_form() -> None:
    if not hmac.compare_digest(request.form.get("form_token", ""), session.get("form_token", "")):
        abort(400)


def local_path(address: str | None) -> str | None:
    """The address when it is a path on this site, so that a login never sends the editor elsewhere."""
    if address and address.startswith("/") and not address.startswith("//") and "\\" not in address:
        return address
    return None


def current_editor() -> Editor | None:
    """The editor of this session: logged in with ORCID, or with a write token that is still valid."""
    orcid = session.get("orcid")
    if not orcid or orcid not in editors():
        return None
    kinds = list(settings().get("writable", {}))
    if "token_id" in session:
        token = tokens.active(session["token_id"])
        if token is None:
            return None
        kinds = token.kinds.split(",")
    return Editor(session.get("name", orcid), orcid, kinds)


def editor_of_request(kind: str) -> Editor | None:
    """The editor of a request of the editor page, when they may write records of *kind*."""
    editor = current_editor()
    if editor is None or kind not in editor.kinds or "form_token" not in session:
        return None
    if not hmac.compare_digest(request.headers.get("X-Form-Token", ""), session["form_token"]):
        return None
    return editor


@blueprint.get("/login/")
def login():
    if current_editor() is not None:
        return redirect(local_path(request.args.get("next")) or url_for("admin.admin"))
    return render_template(
        "account/login.html",
        next=local_path(request.args.get("next")) or "",
        orcid_ready=bool(os.environ.get("ORCID_CLIENT_ID")),
        form_token=form_token(),
        page_title="Log in — VHP4Safety",
    )


@blueprint.post("/login/token/")
def token_login():
    check_form()
    token = tokens.find(request.form.get("token", "").strip())
    if token is None or token.orcid not in editors():
        return render_template(
            "account/login.html",
            next=local_path(request.form.get("next")) or "",
            orcid_ready=bool(os.environ.get("ORCID_CLIENT_ID")),
            form_token=form_token(),
            problem="This token is not valid, or it does not belong to an editor of the platform.",
            page_title="Log in — VHP4Safety",
        ), 403
    session.clear()
    session["orcid"] = token.orcid
    session["name"] = token.name
    session["token_id"] = token.id
    return redirect(local_path(request.form.get("next")) or url_for("admin.admin"))


@blueprint.get("/login/orcid/")
def orcid_login():
    # The state is checked on the way back, so that a login cannot be started by another site.
    session["orcid_state"] = secrets.token_urlsafe(32)
    session["after_login"] = local_path(request.args.get("next"))
    query = urlencode({
        "client_id": os.environ.get("ORCID_CLIENT_ID", ""),
        "response_type": "code",
        "scope": "/authenticate",
        "redirect_uri": callback_address(),
        "state": session["orcid_state"],
    })
    return redirect(f"{orcid_base()}/oauth/authorize?{query}")


@blueprint.get("/orcid/callback/")
def orcid_callback():
    state = session.pop("orcid_state", "")
    after_login = session.pop("after_login", None)
    if not state or not hmac.compare_digest(request.args.get("state", ""), state):
        return "The login was not started here.", 400
    code = request.args.get("code")
    if not code:
        return "No code provided.", 400
    response = requests.post(
        f"{orcid_base()}/oauth/token",
        data={
            "client_id": os.environ.get("ORCID_CLIENT_ID", ""),
            "client_secret": os.environ.get("ORCID_CLIENT_SECRET", ""),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_address(),
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if response.status_code != 200 or not response.json().get("orcid"):
        return "Failed to authenticate with ORCID.", 400
    session.clear()
    session["orcid"] = response.json()["orcid"]
    session["name"] = response.json().get("name") or session["orcid"]
    return redirect(after_login or url_for("account.account_tokens"))


@blueprint.get("/logout/")
def logout():
    session.clear()
    return redirect("/")


@blueprint.route("/account/tokens/", methods=["GET", "POST"])
def account_tokens():
    if "orcid" not in session:
        return redirect(url_for("account.login", next=request.path))
    page = {"form_token": form_token(), "editor": current_editor(), "page_title": "Write tokens — VHP4Safety"}
    if page["editor"] is None:
        return render_template("account/tokens.html", tokens=[], kinds=[], **page)
    # Tokens are made by editors who logged in with ORCID, so that a token never makes another.
    if "token_id" in session:
        return render_template("account/tokens.html", tokens=[], kinds=[], with_token=True, **page)
    kinds = list(settings().get("writable", {}))
    secret = None
    if request.method == "POST":
        check_form()
        chosen = []
        for kind in request.form.getlist("kinds"):
            if kind in kinds:
                chosen.append(kind)
        days = min(max(request.form.get("days", tokens.DEFAULT_DAYS, type=int), 1), 365)
        if chosen:
            secret = tokens.create(session["orcid"], session["name"], chosen, days)
    return render_template(
        "account/tokens.html",
        tokens=tokens.tokens_of(session["orcid"]),
        kinds=kinds,
        secret=secret,
        days=tokens.DEFAULT_DAYS,
        **page,
    )


@blueprint.post("/account/tokens/<int:token_id>/revoke/")
def revoke_token(token_id: int):
    if "orcid" not in session or "token_id" in session:
        return redirect(url_for("account.login", next=url_for("account.account_tokens")))
    check_form()
    tokens.revoke(token_id, session["orcid"])
    return redirect(url_for("account.account_tokens"))
