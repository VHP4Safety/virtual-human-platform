"""The platform's database: one SQLite file in PLATFORM_STATE, used through SQLAlchemy. The file and its
tables (tables.py) are made on first use.
"""

import os
import sqlite3
import threading
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, StaticPool, create_engine, event
from sqlalchemy.orm import Session

from database.tables import Base
from linkeddata.profile import RELEASE, TABLES

STATE_DIR = Path(os.environ.get("PLATFORM_STATE", "instance"))
_engines = {}
# The engine is made once, by the first request of any thread.
_making = threading.Lock()
# An in-memory copy used instead of the database, such as for a page preview.
_copy: ContextVar[Engine | None] = ContextVar("copy", default=None)


def columns(connection: sqlite3.Connection) -> dict[str, list[str]]:
    """The columns of each table of a database, by table name."""
    found = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        found[name] = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
    return found


def differences(path: Path) -> list[str]:
    """How the tables of the database at *path* differ from the release's, apart from those of tables.py; a
    database of another release is migrated before use."""
    with closing(sqlite3.connect(":memory:")) as release:
        release.executescript(TABLES.read_text(encoding="utf-8"))
        expected = columns(release)
    with closing(sqlite3.connect(path)) as kept:
        found = columns(kept)
    for name in Base.metadata.tables:
        found.pop(name, None)
    problems = []
    for name in sorted(set(expected) | set(found)):
        if expected.get(name) != found.get(name):
            problems.append(f"{path}, table {name}: columns {found.get(name)}, release {RELEASE} has {expected.get(name)}.")
    return problems


def engine() -> Engine:
    """The database engine; the file and tables are made on first use. A database whose tables differ from
    the release's is refused."""
    if _copy.get() is not None:
        return _copy.get()
    path = STATE_DIR / "platform.sqlite"
    with _making:
        if path not in _engines:
            if path.exists():
                problems = differences(path)
                if problems:
                    raise RuntimeError(" ".join(problems))
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            made = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
            event.listen(made, "connect", write_ahead_log)
            Base.metadata.create_all(made)
            with made.begin() as connection:
                for statement in TABLES.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        connection.exec_driver_sql(statement)
            _engines[path] = made
    return _engines[path]


def write_ahead_log(connection, _record) -> None:
    """SQLite's write-ahead log, so pages are read while a record is written."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def backup(keep: int = 14) -> Path:
    """A copy of the database in use, by SQLite's online backup; the latest *keep* copies are kept in
    PLATFORM_STATE/backups."""
    engine()
    folder = STATE_DIR / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"platform-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.sqlite"
    with closing(sqlite3.connect(STATE_DIR / "platform.sqlite")) as source, closing(sqlite3.connect(target)) as copy:
        source.backup(copy)
    for old in sorted(folder.glob("platform-*.sqlite"))[:-keep]:
        old.unlink()
    return target


@contextmanager
def copied():
    """Within this context, an in-memory copy of the database is used, and dropped at its end."""
    engine()
    copy = sqlite3.connect(":memory:", check_same_thread=False)
    with closing(sqlite3.connect(STATE_DIR / "platform.sqlite")) as source:
        source.backup(copy)
    made = create_engine("sqlite://", creator=lambda: copy, poolclass=StaticPool)
    token = _copy.set(made)
    try:
        yield
    finally:
        _copy.reset(token)
        made.dispose()
        copy.close()


def session() -> Session:
    return Session(engine(), expire_on_commit=False)
