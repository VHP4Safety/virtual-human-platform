"""Define the tables for records, revisions, notes, sources, tokens and images."""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PLATFORM = "platform"


def now() -> str:
    """Return the current time in UTC, to the microsecond, as the version of a write."""
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Record(Base):
    """An individual record with its address, class and name."""

    __tablename__ = "records"
    iri: Mapped[str] = mapped_column(primary_key=True, doc="Address of the record.")
    type: Mapped[str] = mapped_column(index=True, doc="Class of the record.")
    source: Mapped[str] = mapped_column(index=True, doc='Source, external or "platform".')
    updated_at: Mapped[str] = mapped_column(default=now, doc="Date of last write in UTC (ISO 8601).")
    removed_at: Mapped[str | None] = mapped_column(doc="Date of removal.")
    moved_to: Mapped[str | None] = mapped_column(doc="New address if redirected (moved).")
    name: Mapped[str | None] = mapped_column(doc="The record name.")
    part_of: Mapped[str | None] = mapped_column(index=True, doc="For records part of other records.")


class Revision(Base):
    """A JSON-LD change, the before and after, author, and date."""

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
    """A write token. Only keeps the secret hash."""

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
    """An uploaded image, stored as a file named after the SHA-256 of its content."""

    __tablename__ = "images"
    sha256: Mapped[str] = mapped_column(primary_key=True)
    width: Mapped[int]
    height: Mapped[int]
    size: Mapped[int]
    name: Mapped[str]
    orcid: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Source(Base):
    """A source, as fetched at its last import."""

    __tablename__ = "sources"
    name: Mapped[str] = mapped_column(primary_key=True, doc="The source name.")
    url: Mapped[str] = mapped_column(doc="The file addresses, separated by spaces.")
    fetched_at: Mapped[str] = mapped_column(doc="The last fetch in UTC (ISO 8601).")
    sha256: Mapped[str] = mapped_column(doc="The SHA-256 of the last fetched files.")
    problem: Mapped[str | None] = mapped_column(doc="Why the last import was not stored.")


class Note(Base):
    """A source value not satisfying a constraint, found during last import."""

    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True, doc="Id for the note.")
    source: Mapped[str] = mapped_column(index=True, doc='The record source or "platform".')
    iri: Mapped[str] = mapped_column(doc="The record address.")
    field: Mapped[str] = mapped_column(doc="The address of the field property.")
    value: Mapped[str] = mapped_column(doc="The value that does not fit or empty when a value is missing.")
    reason: Mapped[str] = mapped_column(doc="Reason why the value does not fit coming from the checks.")
    component: Mapped[str | None] = mapped_column(doc="The SHACL constraint that did not pass, e.g. sh:NodeKindConstraintComponent.")
    severity: Mapped[str | None] = mapped_column(doc="The SHACL severity (Violation, Warning or Info).")
