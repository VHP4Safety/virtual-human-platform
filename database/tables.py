"""The database tables.

The records table has one row per record: its address, class, source, dates, and name for lists and links.
What a record says is kept in the release's tables (v1/tables.sql), one per profile class, written by
`python -m linkeddata model`.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PLATFORM = "platform"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class Record(Base):
    """A thing known by its address, such as a tool, a method, or a linked organisation or person, with its
    class and name. Parts with addresses of their own, such as case study questions, are listed too, with
    their record; they are written with it."""

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
    """A change made on the platform, as in ToxTempAssistant: the record in JSON-LD before and after, by
    whom, and when."""

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
    """An uploaded image, kept as a file named after the SHA-256 of its content."""

    __tablename__ = "images"
    sha256: Mapped[str] = mapped_column(primary_key=True)
    width: Mapped[int]
    height: Mapped[int]
    size: Mapped[int]
    name: Mapped[str]
    orcid: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Source(Base):
    """A source as its last import fetched it, with the rdfsolve queries that convert it."""

    __tablename__ = "sources"
    name: Mapped[str] = mapped_column(primary_key=True, doc="The source's name.")
    url: Mapped[str] = mapped_column(doc="The addresses of its files, separated by spaces.")
    fetched_at: Mapped[str] = mapped_column(doc="The last fetch, in UTC (ISO 8601).")
    sha256: Mapped[str] = mapped_column(doc="The SHA-256 of the last fetched files.")
    queries: Mapped[str] = mapped_column(doc="The rdfsolve CONSTRUCT queries that convert it into the model.")
    problem: Mapped[str | None] = mapped_column(doc="Why the last import was not stored, if so.")


class Note(Base):
    """A source value that does not fit the model, found by the checks of its last import."""

    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True, doc="The note's number.")
    source: Mapped[str] = mapped_column(index=True, doc='The record\'s source, or "platform".')
    iri: Mapped[str] = mapped_column(doc="The record's address.")
    field: Mapped[str] = mapped_column(doc="The address of the field's property.")
    value: Mapped[str] = mapped_column(doc="The value that does not fit; empty when a value is missing.")
    reason: Mapped[str] = mapped_column(doc="Why it does not fit, as the checks say.")
    component: Mapped[str | None] = mapped_column(doc="The SHACL constraint the value breaks, such as sh:NodeKindConstraintComponent.")
