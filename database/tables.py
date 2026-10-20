"""Database tables of the records, revisions, notes, sources and tokens."""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PLATFORM = "platform"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class Record(Base):
    """Record or part with an address, with its class, source, dates and name."""

    __tablename__ = "records"
    iri: Mapped[str] = mapped_column(primary_key=True, doc="The record's address.")
    type: Mapped[str] = mapped_column(index=True, doc="The record's class.")
    source: Mapped[str] = mapped_column(index=True, doc='The source it is imported from, or "platform".')
    updated_at: Mapped[str] = mapped_column(default=now, doc="When the record was last written, in UTC (ISO 8601).")
    removed_at: Mapped[str | None] = mapped_column(doc="When the record was removed.")
    moved_to: Mapped[str | None] = mapped_column(doc="Where this earlier address forwards to.")
    name: Mapped[str | None] = mapped_column(doc="The record's name.")
    part_of: Mapped[str | None] = mapped_column(index=True, doc="The record holding this part, such as a question's case study.")


class Revision(Base):
    """Change made on the platform, with the record before and after it."""

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
    """A write token, with the hash of its secret only."""

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
    name: Mapped[str] = mapped_column(primary_key=True, doc="The source's name.")
    url: Mapped[str] = mapped_column(doc="The addresses of its files, separated by spaces.")
    fetched_at: Mapped[str] = mapped_column(doc="The last fetch, in UTC (ISO 8601).")
    sha256: Mapped[str] = mapped_column(doc="The SHA-256 of the last fetched files.")
    problem: Mapped[str | None] = mapped_column(doc="Why the last import was not stored, if so.")


class Note(Base):
    """Value of a source that does not fit the model, from the checks of the last import."""

    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True, doc="The note's number.")
    source: Mapped[str] = mapped_column(index=True, doc='The record\'s source, or "platform".')
    iri: Mapped[str] = mapped_column(doc="The record's address.")
    field: Mapped[str] = mapped_column(doc="The address of the field's property.")
    value: Mapped[str] = mapped_column(doc="The value that does not fit; empty when a value is missing.")
    reason: Mapped[str] = mapped_column(doc="Why it does not fit, as the checks say.")
    component: Mapped[str | None] = mapped_column(doc="The SHACL constraint the value breaks, such as sh:NodeKindConstraintComponent.")
