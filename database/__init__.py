"""The platform's database: one SQLite file in PLATFORM_STATE, read and written through SQLAlchemy.
The tables are in tables.py; the file and its tables are made, or completed, when it is first used.
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session

from database.tables import Base

STATE_DIR = Path(os.environ.get("PLATFORM_STATE", "instance"))
_engines = {}


def add_missing_columns(made: Engine) -> None:
    """The columns that the tables have gained since the database was made are added to it."""
    found = inspect(made)
    with made.begin() as connection:
        for table in Base.metadata.sorted_tables:
            present = {column["name"] for column in found.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                kind = column.type.compile(made.dialect)
                default = " DEFAULT '[]'" if isinstance(column.type, JSON) else ""
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {kind}{default}'))


def engine() -> Engine:
    """The engine of the database; the file and its tables are made, or completed, on first use."""
    path = STATE_DIR / "platform.sqlite"
    if path not in _engines:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        made = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
        event.listen(made, "connect", write_ahead_log)
        Base.metadata.create_all(made)
        add_missing_columns(made)
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
