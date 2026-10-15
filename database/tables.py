"""The tables of the database.

The records table has one row per record and one column per field of the model, named as rdfsolve
names the field (conforms_to for dct:conformsTo). A field with several values is a JSON column. To
keep a new field, a column of that name is added here; an existing database gets it when the platform
starts (columns are only ever added).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PLATFORM = "platform"


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
    # The address the record moved to, when this address is an earlier one; it forwards there.
    moved_to: Mapped[str | None]
    name: Mapped[str | None]
    description: Mapped[str | None]
    citation: Mapped[str | None]
    url: Mapped[str | None]
    image: Mapped[str | None]
    about: Mapped[list[str]] = mapped_column(JSON, default=list)
    conforms_to: Mapped[list[str]] = mapped_column(JSON, default=list)
    same_as: Mapped[list[str]] = mapped_column(JSON, default=list)
    install_url: Mapped[str | None]
    software_version: Mapped[str | None]
    license: Mapped[str | None]
    creative_work_status: Mapped[str | None]
    keywords: Mapped[str | None]
    release_notes: Mapped[str | None]
    email: Mapped[str | None]
    provider: Mapped[list[str]] = mapped_column(JSON, default=list)
    creator: Mapped[list[str]] = mapped_column(JSON, default=list)
    maintainer: Mapped[list[str]] = mapped_column(JSON, default=list)
    software_help: Mapped[list[str]] = mapped_column(JSON, default=list)
    subject_of: Mapped[list[str]] = mapped_column(JSON, default=list)
    video: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_based_on: Mapped[list[str]] = mapped_column(JSON, default=list)
    download_url: Mapped[list[str]] = mapped_column(JSON, default=list)


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
    # Why the last import of the source was not stored, when it was not.
    problem: Mapped[str | None]


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
