"""Records written on the platform: saving, removing, and their revisions."""

from linkeddata import records
from linkeddata.database import PLATFORM

ORCID = "0000-0001-6487-1655"
IRI = "https://platform.vhp4safety.nl/tools/x"


def row(**fields) -> dict:
    return {"iri": IRI, "type": "https://schema.org/SoftwareApplication", "source": PLATFORM, **fields}


def test_records():
    assert records.save(row(name="X", about=["https://example.org/a"]), {"name": "X"}, "Julia Meerman", ORCID)
    assert not records.save(row(name="Y"), {"name": "Y"}, "Julia Meerman", ORCID)
    record = records.get(IRI)
    assert (record.name, record.about) == ("Y", [])
    assert [record.iri for record in records.of_kind("tools")] == [IRI]
    records.retire(IRI, "Julia Meerman", ORCID)
    assert records.get(IRI).removed_at
    assert records.of_kind("tools") == []
    assert records.removed("tools") == {"x"}
    records.remove(IRI, "Julia Meerman", ORCID)
    assert records.get(IRI) is None
    history = records.history(10)
    assert [revision.action for revision in history] == ["Removed permanently", "Removed", "Changed", "Added"]
    assert (history[0].name, history[0].orcid) == ("Julia Meerman", ORCID)
    assert '"name": "Y"' in history[2].document
