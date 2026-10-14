"""Write tokens, made as ToxTempAssistant makes its workspace tokens: the secret is shown once and only
its hash is kept; a token expires (after 90 days unless set otherwise), can be revoked, and lists the
kinds of records it may write."""

import hashlib
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFIX = "vhp_"
DEFAULT_DAYS = 90
STATE_DIR = Path(os.environ.get("PLATFORM_STATE", "instance"))
TABLE = """
CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY,
    token_hash TEXT UNIQUE NOT NULL,
    prefix TEXT NOT NULL,
    orcid TEXT NOT NULL,
    name TEXT NOT NULL,
    kinds TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
)
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def database() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STATE_DIR / "accounts.sqlite")
    db.row_factory = sqlite3.Row
    db.execute(TABLE)
    return db


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create(orcid: str, name: str, kinds: list[str], days: int = DEFAULT_DAYS) -> str:
    """A new token; the secret it returns is not kept anywhere."""
    secret = PREFIX + secrets.token_urlsafe(32)
    with closing(database()) as db:
        db.execute(
            "INSERT INTO tokens (token_hash, prefix, orcid, name, kinds, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hash_token(secret), secret[:8], orcid, name, ",".join(kinds), now().isoformat(), (now() + timedelta(days=days)).isoformat()),
        )
        db.commit()
    return secret


def check(secret: str, kind: str) -> dict | None:
    """The token of the secret when it is valid and may write records of *kind*; None otherwise."""
    with closing(database()) as db:
        token = db.execute("SELECT * FROM tokens WHERE token_hash = ?", (hash_token(secret),)).fetchone()
        if token is None or token["revoked_at"] or token["expires_at"] < now().isoformat():
            return None
        if kind not in token["kinds"].split(","):
            return None
        db.execute("UPDATE tokens SET last_used_at = ? WHERE id = ?", (now().isoformat(), token["id"]))
        db.commit()
        return dict(token)


def tokens_of(orcid: str) -> list[dict]:
    with closing(database()) as db:
        rows = db.execute("SELECT * FROM tokens WHERE orcid = ? ORDER BY created_at DESC", (orcid,)).fetchall()
    return [dict(row) for row in rows]


def revoke(token_id: int, orcid: str) -> bool:
    with closing(database()) as db:
        changed = db.execute(
            "UPDATE tokens SET revoked_at = ? WHERE id = ? AND orcid = ? AND revoked_at IS NULL",
            (now().isoformat(), token_id, orcid),
        ).rowcount
        db.commit()
    return changed == 1
