"""Editor login with ORCID, as in ToxTempAssistant, and write tokens.

- The login uses ORCID's OAuth with the /authenticate scope (the sandbox when FLASK_DEBUG=1); only the
  ORCID iD and name are kept.
- Editors are the ORCID iDs in PLATFORM_EDITORS. The credentials are ORCID_CLIENT_ID and
  ORCID_CLIENT_SECRET; the redirect URI is <platform>/orcid/callback/.
- A login with a write token ends when the token is revoked or expires, and writes only its kinds.
- The editor page writes through the write API; its requests carry the session's form token in the
  X-Form-Token header, which other sites cannot send.
"""

import hmac
import os
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from admin import tokens
from linkeddata.profile import settings

blueprint = Blueprint("account", __name__)


def callback_address() -> str:
    return url_for("account.orcid_callback", _external=True)


def form_token() -> str:
    """The token sent back by the account forms, so other sites cannot send them."""
    if "form_token" not in session:
        session["form_token"] = secrets.token_urlsafe(32)
    return session["form_token"]


def check_form() -> None:
    if not hmac.compare_digest(request.form.get("form_token", ""), session.get("form_token", "")):
        abort(400)


def local_path(address: str | None) -> str | None:
    """The address when it is a path on this site, so a login never leads elsewhere."""
    if address and address.startswith("/") and not address.startswith("//") and "\\" not in address:
        return address
    return None


def current_editor() -> tokens.Editor | None:
    """The session's editor, logged in with ORCID or a valid write token."""
    return tokens.editor(session.get("orcid"), session.get("name"), session.get("token_id"))


def editor_of_request(kind: str) -> tokens.Editor | None:
    """The editor of an editor page request, when allowed to write *kind*."""
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
    if token is None or token.orcid not in tokens.editors():
        return render_template(
            "account/login.html",
            next=local_path(request.form.get("next")) or "",
            orcid_ready=bool(os.environ.get("ORCID_CLIENT_ID")),
            form_token=form_token(),
            problem="Invalid token, or not an editor's.",
            page_title="Log in — VHP4Safety",
        ), 403
    session.clear()
    session["orcid"] = token.orcid
    session["name"] = token.name
    session["token_id"] = token.id
    return redirect(local_path(request.form.get("next")) or url_for("admin.admin"))


@blueprint.get("/login/orcid/")
def orcid_login():
    # The state is checked on return, so another site cannot start a login.
    session["orcid_state"] = secrets.token_urlsafe(32)
    session["after_login"] = local_path(request.args.get("next"))
    query = urlencode({
        "client_id": os.environ.get("ORCID_CLIENT_ID", ""),
        "response_type": "code",
        "scope": "/authenticate",
        "redirect_uri": callback_address(),
        "state": session["orcid_state"],
    })
    return redirect(f"{tokens.orcid_base()}/oauth/authorize?{query}")


@blueprint.get("/orcid/callback/")
def orcid_callback():
    state = session.pop("orcid_state", "")
    after_login = session.pop("after_login", None)
    if not state or not hmac.compare_digest(request.args.get("state", ""), state):
        return "Login not started here.", 400
    code = request.args.get("code")
    if not code:
        return "No code provided.", 400
    response = requests.post(
        f"{tokens.orcid_base()}/oauth/token",
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
        return "ORCID login failed.", 400
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
    # Only ORCID logins make tokens, so a token never makes another.
    if "token_id" in session:
        return render_template("account/tokens.html", tokens=[], kinds=[], with_token=True, **page)
    kinds = list(settings()["kinds"])
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
