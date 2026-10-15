"""The tables of the database.

The records table has one row per record: its address, class, source and dates, and its name for lists
and links. What a record says is kept in the tables of the model's release (v1/tables.sql), one for
each class of the application profile, which `python -m linkeddata model` writes.
"""

from datetime import datetime, timezone

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
    name: Mapped[str] = mapped_column(primary_key=True, doc="The source's name.")
    url: Mapped[str] = mapped_column(doc="The addresses of its files, separated by spaces.")
    fetched_at: Mapped[str] = mapped_column(doc="When its last import fetched it, in UTC (ISO 8601).")
    sha256: Mapped[str] = mapped_column(doc="The SHA-256 of the files its last import fetched.")
    queries: Mapped[str] = mapped_column(doc="The rdfsolve CONSTRUCT queries that convert it into the model.")
    problem: Mapped[str | None] = mapped_column(doc="Why the last import of the source was not stored, when it was not.")


class Note(Base):
    """A value of a source that does not fit the model, found by the checks of its last import."""

    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True, doc="The note's number.")
    source: Mapped[str] = mapped_column(index=True, doc='The source of the record, or "platform" for a record written on the platform.')
    iri: Mapped[str] = mapped_column(doc="The record's address.")
    field: Mapped[str] = mapped_column(doc="The address of the field's property.")
    value: Mapped[str] = mapped_column(doc="The value that does not fit; empty when a value is missing.")
    reason: Mapped[str] = mapped_column(doc="Why it does not fit, as the checks say it.")
    component: Mapped[str | None] = mapped_column(doc="The SHACL constraint the value breaks, such as sh:NodeKindConstraintComponent.")
