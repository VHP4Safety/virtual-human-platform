"""Write tokens are given to editors, and the editors are listed by ORCID iD in PLATFORM_EDITORS. The secret of a
token is shown once, and only its hash is kept. A token expires after 90 days by default, can be revoked, and is
limited to some kinds of records."""

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import database
from database.tables import Token, now
from linkeddata.model import settings

PREFIX = "vhp_"
DEFAULT_DAYS = 90


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create(orcid: str, name: str, kinds: list[str], days: int = DEFAULT_DAYS) -> str:
    """A new token is made. The secret is given back and is not kept."""
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
    if token is None or token.revoked_at or token.expires_at < now():
        return None
    return token


def bearer(header: str) -> str | None:
    """The secret is read from an Authorization header ("Bearer <secret>"). None is given for another header."""
    return header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else None


def find(secret: str | None) -> Token | None:
    """The token of a secret is given when it is neither revoked nor expired."""
    if not secret:
        return None
    with database.session() as db:
        return usable(db.scalars(select(Token).where(Token.token_hash == hash_token(secret))).first())


def check(secret: str, kind: str) -> Token | None:
    """The token of a secret is given when it is valid and may write records of *kind*. The time of use is kept."""
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
    """The editor logged in with an ORCID iD is given here, when logged in through ORCID or with a valid write token."""
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
