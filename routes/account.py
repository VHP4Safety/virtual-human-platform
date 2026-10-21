"""Editor sign-in with ORCID, and write tokens."""

import hmac
import os
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from admin import tokens
from linkeddata import pages
from linkeddata.profile import settings

blueprint = Blueprint("account", __name__)


@blueprint.context_processor
def named_kinds() -> dict:
    """Return the names of the kinds of records for the editor pages."""
    return {"kind_names": pages.kind_names}


def callback_address() -> str:
    return url_for("account.orcid_callback", _external=True)


def form_token() -> str:
    """Return the token of the account forms of the session."""
    if "form_token" not in session:
        session["form_token"] = secrets.token_urlsafe(32)
    return session["form_token"]


def check_form() -> None:
    if not hmac.compare_digest(request.form.get("form_token", ""), session.get("form_token", "")):
        abort(400)


def local_path(address: str | None) -> str | None:
    """Return the address if it is a path on this site, so that a sign-in does not redirect elsewhere."""
    if address and address.isprintable() and address.startswith("/") and not address.startswith("//") and "\\" not in address:
        return address
    return None


def current_editor() -> tokens.Editor | None:
    """Return the editor of the session, signed in with ORCID or a valid write token."""
    return tokens.editor(session.get("orcid"), session.get("name"), session.get("token_id"))


def editor_of_request(kind: str) -> tokens.Editor | None:
    """Return the editor of a request of an editor page, if kind may be written."""
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
    if token is None:
        return render_template(
            "account/login.html",
            next=local_path(request.form.get("next")) or "",
            orcid_ready=bool(os.environ.get("ORCID_CLIENT_ID")),
            form_token=form_token(),
            problem="Invalid or expired token.",
            page_title="Log in — VHP4Safety",
        ), 403
    session.clear()
    session["orcid"] = token.orcid
    session["name"] = token.name
    session["token_id"] = token.id
    return redirect(local_path(request.form.get("next")) or url_for("admin.admin"))


@blueprint.get("/login/orcid/")
def orcid_login():
    # The state is checked on return, so that a sign-in cannot be started by another site.
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
    # Tokens are made only after a sign-in with ORCID, so that no token is made with a token.
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
