"""Write tokens and editor sign-ins."""

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import database
from database.tables import Token, now
from linkeddata.profile import settings

PREFIX = "vhp_"
DEFAULT_DAYS = 90


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create(orcid: str, name: str, kinds: list[str], days: int = DEFAULT_DAYS) -> str:
    """Create a token and return its secret."""
    secret = PREFIX + secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    with database.session() as db, db.begin():
        db.add(Token(
            token_hash=hash_token(secret),
            prefix=secret[:8],
            orcid=orcid,
            name=name,
            kinds=",".join(kinds),
            expires_at=expires.isoformat(timespec="seconds"),
        ))
    return secret


def usable(token: Token | None) -> Token | None:
    """Return the token if it is not revoked or expired and its ORCID iD is an editor, else None."""
    if token is None or token.revoked_at or token.expires_at < now() or token.orcid not in editors():
        return None
    return token


def bearer(header: str) -> str | None:
    """Return the secret of a Bearer Authorization header, or None."""
    return header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else None


def find(secret: str | None) -> Token | None:
    """Return the token of a secret if it is usable, else None."""
    if not secret:
        return None
    with database.session() as db:
        return usable(db.scalars(select(Token).where(Token.token_hash == hash_token(secret))).first())


def check(secret: str, kind: str) -> Token | None:
    """Return the token of a secret, if it is valid for records of kind, and store the time of use."""
    token = find(secret)
    if token is None or kind not in token.kinds.split(","):
        return None
    with database.session() as db, db.begin():
        db.get(Token, token.id).last_used_at = now()
    return token


def tokens_of(orcid: str) -> list[Token]:
    with database.session() as db:
        return list(db.scalars(select(Token).where(Token.orcid == orcid).order_by(Token.id.desc())))


def revoke(token_id: int, orcid: str) -> bool:
    with database.session() as db, db.begin():
        token = db.get(Token, token_id)
        if token is None or token.orcid != orcid or token.revoked_at:
            return False
        token.revoked_at = now()
        return True


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
    """Return the signed-in editor, if signed in through ORCID or with a valid write token."""
    if not orcid or orcid not in editors():
        return None
    kinds = list(settings()["kinds"])
    if token_id is not None:
        with database.session() as db:
            token = usable(db.get(Token, token_id))
        if token is None:
            return None
        kinds = token.kinds.split(",")
    return Editor(name if name is not None else orcid, orcid, kinds)
