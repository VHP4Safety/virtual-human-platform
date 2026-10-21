"""Tests of the database."""

import io

import pytest
from PIL import Image as Picture
from sqlalchemy import text

import database
from admin import writes
from database import export, images

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"


def test_backup():
    with database.engine().connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
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
