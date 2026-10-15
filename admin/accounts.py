"""Editors: the ORCID iDs listed in PLATFORM_EDITORS, and the kinds of records each may write."""

import os
from dataclasses import dataclass

from admin import tokens
from linkeddata.model import settings


@dataclass
class Editor:
    name: str
    orcid: str
    kinds: list[str]


def orcid_base() -> str:
    return "https://sandbox.orcid.org" if os.environ.get("FLASK_DEBUG") == "1" else "https://orcid.org"


def editors() -> set[str]:
    return {orcid.strip() for orcid in os.environ.get("PLATFORM_EDITORS", "").split(",") if orcid.strip()}


def editor(orcid: str | None, name: str | None, token_id: int | None) -> Editor | None:
    """The editor who logged in with this ORCID iD: with ORCID, or with a write token that is still valid."""
    if not orcid or orcid not in editors():
        return None
    kinds = list(settings()["kinds"])
    if token_id is not None:
        token = tokens.active(token_id)
        if token is None:
            return None
        kinds = token.kinds.split(",")
    return Editor(name if name is not None else orcid, orcid, kinds)
