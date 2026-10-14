"""Records written on the platform: saving, removing, and their revisions."""

from linkeddata import records
from linkeddata.database import PLATFORM

ORCID = "0000-0002-1825-0097"
IRI = "https://platform.vhp4safety.nl/tools/x"


def row(**fields) -> dict:
    return {"iri": IRI, "type": "https://schema.org/SoftwareApplication", "source": PLATFORM, **fields}


def test_records():
    assert records.save(row(name="X", about=["https://example.org/a"]), {"name": "X"}, "Test Editor", ORCID).action == "Added"
    assert records.save(row(name="Y"), {"name": "Y"}, "Test Editor", ORCID).action == "Changed"
    record = records.get(IRI)
    assert (record.name, record.about) == ("Y", [])
    assert [record.iri for record in records.of_kind("tools")] == [IRI]
    records.retire(IRI, "Test Editor", ORCID)
    assert records.get(IRI).removed_at
    assert records.of_kind("tools") == []
    assert records.removed("tools") == {"x"}
    records.remove(IRI, "Test Editor", ORCID)
    assert records.get(IRI) is None
    history = records.history(10)
    assert [revision.action for revision in history] == ["Removed permanently", "Removed", "Changed", "Added"]
    assert (history[0].name, history[0].orcid) == ("Test Editor", ORCID)
    assert '"name": "Y"' in history[2].document
    assert '"name": "X"' in history[2].previous
