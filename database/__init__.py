"""The platform's database: one SQLite file in PLATFORM_STATE, read and written through SQLAlchemy.
The tables are in tables.py; the file and its tables are made when it is first used.
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from database.tables import Base
from linkeddata.model import RELEASE

STATE_DIR = Path(os.environ.get("PLATFORM_STATE", "instance"))
# The tables of the model's release, which `python -m linkeddata model` writes from its profile.
TABLES = Path(__file__).parent / RELEASE / "tables.sql"
_engines = {}


def columns(connection: sqlite3.Connection) -> dict[str, list[str]]:
    """The columns of each table of a database, by table name."""
    found = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        found[name] = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
    return found


def differences(path: Path) -> list[str]:
    """How the tables of the database at *path* differ from those of the model's release, apart from the
    tables of tables.py; a database of another release is moved to this one before the platform uses it."""
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
            problems.append(f"{path}, table {name}: the database has the columns {found.get(name)}, release {RELEASE} has {expected.get(name)}.")
    return problems


def engine() -> Engine:
    """The engine of the database; the file and its tables are made on first use. A database whose tables
    are not those of the model's release is refused."""
    path = STATE_DIR / "platform.sqlite"
    if path not in _engines:
        if path.exists():
            problems = differences(path)
            if problems:
                raise RuntimeError(" ".join(problems))
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        made = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
        event.listen(made, "connect", write_ahead_log)
        Base.metadata.create_all(made)
        if TABLES.exists():
            with made.begin() as connection:
                for statement in TABLES.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        connection.exec_driver_sql(statement)
        _engines[path] = made
    return _engines[path]


def write_ahead_log(connection, _record) -> None:
    """With SQLite's write-ahead log, pages are read while a record is written."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def backup(keep: int = 14) -> Path:
    """A copy of the database, made while it is in use with SQLite's online backup; the latest *keep*
    copies are kept in PLATFORM_STATE/backups."""
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
