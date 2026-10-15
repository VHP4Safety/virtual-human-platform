"""Records written on the platform: saving, removing, and their revisions."""

from admin import editor, writes
from database import records
from linkeddata import rdf

ORCID = "0000-0002-1825-0097"
IRI = "https://platform.vhp4safety.nl/tools/x"
TOOL = "https://schema.org/SoftwareApplication"


def test_records():
    assert writes.save(writes.document(TOOL, IRI, {"name": "X", "about": ["https://example.org/a"]}), TOOL, "Test Editor", ORCID).action == "Added"
    assert writes.save(writes.document(TOOL, IRI, {"name": "Y"}), TOOL, "Test Editor", ORCID).action == "Changed"
    record = records.get(IRI)
    assert (record.name, rdf.values(record.document, "about")) == ("Y", [])
    assert [record.iri for record in records.of_kind("tools")] == [IRI]
    writes.retire(IRI, "Test Editor", ORCID)
    assert records.get(IRI).removed_at
    assert records.of_kind("tools") == []
    assert records.removed("tools") == {"x"}
    writes.remove(IRI, "Test Editor", ORCID)
    assert records.get(IRI) is None
    history = records.history(10)
    assert [revision.action for revision in history] == ["Removed permanently", "Removed", "Changed", "Added"]
    assert (history[0].name, history[0].orcid) == ("Test Editor", ORCID)
    assert '"name": "Y"' in history[2].document
    assert '"name": "X"' in history[2].previous
    assert editor.used_values(TOOL, "about") == []


def test_the_database_uses_the_write_ahead_log():
    from sqlalchemy import text

    import database

    with database.engine().connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_backups():
    import database

    writes.save(writes.document(TOOL, IRI, {"name": "X"}), TOOL, "Test Editor", ORCID)
    for _ in range(3):
        copy = database.backup(keep=2)
    assert copy.exists()
    assert len(list(copy.parent.glob("platform-*.sqlite"))) == 2
