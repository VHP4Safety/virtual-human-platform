"""The platform's database: one SQLite file in PLATFORM_STATE, read and written through SQLAlchemy.

The records table has one row per record and one column per field of the model, named as rdfsolve
names the field (conforms_to for dct:conformsTo). A field with several values is a JSON column. To
keep a new field, a column of that name is added here (and to an existing database with ALTER TABLE).
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

STATE_DIR = Path(os.environ.get("PLATFORM_STATE", "instance"))
PLATFORM = "platform"
_engines = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class Record(Base):
    """A thing the platform knows by its address: a tool or a method, which has a page on the
    platform, or a term of the glossary that they link to."""

    __tablename__ = "records"
    iri: Mapped[str] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(index=True)
    # The source the record is imported from, or "platform" when it is written on the platform.
    source: Mapped[str] = mapped_column(index=True)
    updated_at: Mapped[str] = mapped_column(default=now)
    removed_at: Mapped[str | None]
    name: Mapped[str | None]
    description: Mapped[str | None]
    citation: Mapped[str | None]
    url: Mapped[str | None]
    image: Mapped[str | None]
    about: Mapped[list[str]] = mapped_column(JSON, default=list)
    conforms_to: Mapped[list[str]] = mapped_column(JSON, default=list)


class Revision(Base):
    """A change to a record made on the platform, as in ToxTempAssistant: the record in JSON-LD before
    and after the change, who made it, and when."""

    __tablename__ = "revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    record_iri: Mapped[str] = mapped_column(index=True)
    action: Mapped[str]
    previous: Mapped[str | None]
    document: Mapped[str | None]
    name: Mapped[str]
    orcid: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Token(Base):
    """A write token. Only the hash of its secret is kept."""

    __tablename__ = "tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(unique=True)
    prefix: Mapped[str]
    orcid: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    kinds: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)
    expires_at: Mapped[str]
    last_used_at: Mapped[str | None]
    revoked_at: Mapped[str | None]


class Image(Base):
    """An image uploaded to the platform, kept as a file named after the SHA-256 of its content."""

    __tablename__ = "images"
    sha256: Mapped[str] = mapped_column(primary_key=True)
    width: Mapped[int]
    height: Mapped[int]
    size: Mapped[int]
    name: Mapped[str]
    orcid: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Source(Base):
    """A source of records as its last import fetched it, with the rdfsolve queries that convert it."""

    __tablename__ = "sources"
    name: Mapped[str] = mapped_column(primary_key=True)
    url: Mapped[str]
    fetched_at: Mapped[str]
    sha256: Mapped[str]
    queries: Mapped[str]


class Note(Base):
    """A value of a source that does not fit the model, found by the checks of its last import."""

    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(index=True)
    iri: Mapped[str]
    field: Mapped[str]
    value: Mapped[str]
    reason: Mapped[str]
    # The SHACL constraint the value breaks, such as sh:NodeKindConstraintComponent.
    component: Mapped[str | None]


def engine() -> Engine:
    """The engine of the database; the file and its tables are made on first use."""
    path = STATE_DIR / "platform.sqlite"
    if path not in _engines:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _engines[path] = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
        Base.metadata.create_all(_engines[path])
    return _engines[path]


def session() -> Session:
    return Session(engine(), expire_on_commit=False)
