"""Editors log in with ORCID, as in ToxTempAssistant, and manage their write tokens.

The login uses ORCID's OAuth with the /authenticate scope (the sandbox when FLASK_DEBUG=1). ORCID
gives the editor's ORCID iD and name; nothing else is kept. Editors are the ORCID iDs listed in
PLATFORM_EDITORS. The application's credentials are ORCID_CLIENT_ID and ORCID_CLIENT_SECRET, and its
redirect URI at ORCID is <platform>/orcid/callback/.
"""

import hmac
import os
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from linkeddata import tokens
from linkeddata.model import settings

blueprint = Blueprint("account", __name__)


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


@blueprint.get("/login/orcid/")
def orcid_login():
    # The state is checked on the way back, so that a login cannot be started by another site.
    session["orcid_state"] = secrets.token_urlsafe(32)
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
    return redirect(url_for("account.account_tokens"))


@blueprint.get("/logout/")
def logout():
    session.clear()
    return redirect("/")


@blueprint.route("/account/tokens/", methods=["GET", "POST"])
def account_tokens():
    if "orcid" not in session:
        return redirect(url_for("account.orcid_login"))
    if session["orcid"] not in editors():
        return render_template("account/tokens.html", editor=False, tokens=[], kinds=[], form_token=form_token())
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
        editor=True,
        tokens=tokens.tokens_of(session["orcid"]),
        kinds=kinds,
        secret=secret,
        days=tokens.DEFAULT_DAYS,
        form_token=form_token(),
    )


@blueprint.post("/account/tokens/<int:token_id>/revoke/")
def revoke_token(token_id: int):
    if "orcid" not in session:
        return redirect(url_for("account.orcid_login"))
    check_form()
    tokens.revoke(token_id, session["orcid"])
    return redirect(url_for("account.account_tokens"))
