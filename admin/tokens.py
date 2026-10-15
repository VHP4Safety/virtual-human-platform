"""Write tokens, made as ToxTempAssistant makes its workspace tokens: the secret is shown once and only
its hash is kept; a token expires (after 90 days unless set otherwise), can be revoked, and lists the
kinds of records it may write."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import database
from database.tables import Token, now

PREFIX = "vhp_"
DEFAULT_DAYS = 90


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create(orcid: str, name: str, kinds: list[str], days: int = DEFAULT_DAYS) -> str:
    """A new token; the secret it returns is not kept anywhere."""
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


def find(secret: str) -> Token | None:
    """The token of the secret when it is neither revoked nor expired."""
    with database.session() as db:
        return usable(db.scalars(select(Token).where(Token.token_hash == hash_token(secret))).first())


def active(token_id: int) -> Token | None:
    """The token with this id when it is neither revoked nor expired."""
    with database.session() as db:
        return usable(db.get(Token, token_id))


def check(secret: str, kind: str) -> Token | None:
    """The token of the secret when it is valid and may write records of *kind*; None otherwise."""
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
