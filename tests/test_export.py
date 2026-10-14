"""The export of the records written on the platform to the records repository."""

from linkeddata import export, records
from linkeddata.database import PLATFORM

ORCID = "0000-0001-6487-1655"
IRI = "https://platform.vhp4safety.nl/tools/x"


def test_export():
    row = {"iri": IRI, "type": "https://schema.org/SoftwareApplication", "source": PLATFORM, "name": "X"}
    records.save(row, {"@id": IRI, "name": "X"}, "Julia Meerman", ORCID)
    assert export.export()
    assert '"name": "X"' in (export.RECORDS_DIR / "tools" / "x.jsonld").read_text()
    assert not export.export()
    records.retire(IRI, "Julia Meerman", ORCID)
    assert export.export()
    assert not (export.RECORDS_DIR / "tools" / "x.jsonld").exists()
    assert export.git("log", "--format=%s").splitlines() == ["Records exported", "Records exported"]
