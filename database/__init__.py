"""Database of the platform, one SQLite file in PLATFORM_STATE."""

import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from database.tables import Base
from linkeddata.profile import RELEASE, TABLES

STATE_DIR = Path(os.environ.get("PLATFORM_STATE", "instance"))
_engines = {}
# The engine is made once, by the first request of any thread.
_making = threading.Lock()
# An in-memory copy that is used in place of the database, such as for a page preview.


def columns(connection: sqlite3.Connection) -> dict[str, list[str]]:
    """Return the columns of each table of a database, by table name."""
    found = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        found[name] = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
    return found


def differences(path: Path) -> list[str]:
    """Return the differences between the tables of the database at path and the release tables."""
    with closing(sqlite3.connect(":memory:")) as release:
        release.executescript(TABLES.read_text(encoding="utf-8"))
        expected = columns(release)
    with closing(sqlite3.connect(path)) as kept:
        found = columns(kept)
    for name in Base.metadata.tables:
        found.pop(name, None)
    problems = []
    # Columns are compared by name, so that their order does not matter, such as after columns are added.
    for name in sorted(set(expected) | set(found)):
        if sorted(expected.get(name) or []) != sorted(found.get(name) or []) or (name in expected) != (name in found):
            problems.append(f"{path}, table {name}: columns {found.get(name)}, release {RELEASE} has {expected.get(name)}.")
    return problems


def engine() -> Engine:
    """Return the database engine and write the file and the tables on first use."""
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
    """Use the write-ahead log of SQLite, so that pages are read while a record is written."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def backup(keep: int = 14) -> Path:
    """Copy the database to PLATFORM_STATE/backups, keep the latest copies, and return the path."""
    engine()
    folder = STATE_DIR / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"platform-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.sqlite"
    with closing(sqlite3.connect(STATE_DIR / "platform.sqlite")) as source, closing(sqlite3.connect(target)) as copy:
        source.backup(copy)
    for old in sorted(folder.glob("platform-*.sqlite"))[:-keep]:
        old.unlink()
    return target


def session() -> Session:
    return Session(engine(), expire_on_commit=False)
