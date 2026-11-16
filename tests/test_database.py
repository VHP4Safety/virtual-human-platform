"""Tests of the database."""

import io

import pytest
from PIL import Image as Picture
from sqlalchemy import Engine, event, text

import database
from admin import writes
from database import export, images, records

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"


@pytest.mark.parametrize("journal", ["wal", "delete"])
def test_journal(journal, monkeypatch):
    monkeypatch.setattr(database, "JOURNAL", journal)
    writes.save(writes.document(TOOL, BASE + "tools/x", {"name": "X"}), TOOL, "Test Editor", "0000-0002-1825-0097")
    with database.engine().connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == journal
    # The rollback journal leaves no shared memory file, which is not safe on a network file system.
    assert (database.STATE_DIR / "platform.sqlite-shm").exists() == (journal == "wal")


def test_read_during_write(monkeypatch):
    """An import reads records on another connection in its write, which is larger than the page cache."""
    monkeypatch.setattr(database, "JOURNAL", "delete")
    writes.save(writes.document(TOOL, BASE + "tools/x", {"name": "X"}), TOOL, "Test Editor", "0000-0002-1825-0097")
    with database.session() as db, db.begin():
        db.execute(text("CREATE TABLE filler (data BLOB)"))
        db.execute(text("INSERT INTO filler VALUES (randomblob(8000000))"))
        assert len(records.read([BASE + "tools/x"]))


def test_read_in_one_transaction():
    """The tables of a read are read in one transaction, not each table in a transaction of its own."""
    writes.save(writes.document(TOOL, BASE + "tools/x", {"name": "X"}), TOOL, "Test Editor", "0000-0002-1825-0097")
    outside = []

    def listen(connection, cursor, statement, *_):
        if statement.startswith("SELECT") and not cursor.connection.in_transaction:
            outside.append(statement)

    event.listen(database.engine(), "before_cursor_execute", listen)
    try:
        assert len(records.read([BASE + "tools/x"]))
    finally:
        event.remove(database.engine(), "before_cursor_execute", listen)
    assert not outside
    # The transaction ends with the read, so that a write is not kept waiting.
    writes.save(writes.document(TOOL, BASE + "tools/y", {"name": "Y"}), TOOL, "Test Editor", "0000-0002-1825-0097")


def test_tables_in_one_transaction():
    """The tables of a database are made in one transaction, not one transaction for each statement."""
    outside = []

    def listen(connection, cursor, statement, *_):
        if statement.lstrip().upper().startswith("CREATE") and not cursor.connection.in_transaction:
            outside.append(statement)

    event.listen(Engine, "before_cursor_execute", listen)
    try:
        made = database.engine()
    finally:
        event.remove(Engine, "before_cursor_execute", listen)
    assert not outside
    with made.connect() as connection:
        found = {name for (name,) in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"records", "revisions", "tokens"} <= found and len(found) > 250


def test_backup():
    for _ in range(3):
        copy = database.backup(keep=2)
    assert len(list(copy.parent.glob("platform-*.sqlite"))) == 2


def test_images():
    picture = io.BytesIO()
    Picture.new("RGB", (3000, 20), (230, 0, 126)).save(picture, format="PNG")
    address = images.store(io.BytesIO(picture.getvalue()), "Test Editor", "0000-0002-1825-0097")
    with Picture.open(images.folder() / address.removeprefix(BASE + "images/")) as saved:
        assert (saved.format, saved.width) == ("WEBP", 2000)
    assert images.store(io.BytesIO(picture.getvalue()), "Test Editor", "0000-0002-1825-0097") == address
    with pytest.raises(ValueError):
        images.store(io.BytesIO(b"<svg/>"), "Test Editor", "0000-0002-1825-0097")


def test_export():
    writes.save(writes.document(TOOL, BASE + "tools/x", {"name": "X"}), TOOL, "Test Editor", "0000-0002-1825-0097")
    assert export.export()
    assert '"name": "X"' in (export.RECORDS_DIR / "tools" / "x.jsonld").read_text()
    assert not export.export()
    writes.retire(BASE + "tools/x", "Test Editor", "0000-0002-1825-0097")
    assert export.export() and not (export.RECORDS_DIR / "tools" / "x.jsonld").exists()
