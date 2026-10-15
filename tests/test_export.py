"""The export of the records written on the platform to the records repository."""

from admin import writes
from database import export

ORCID = "0000-0002-1825-0097"
IRI = "https://platform.vhp4safety.nl/tools/x"
TOOL = "https://schema.org/SoftwareApplication"


def test_export():
    writes.save(writes.document(TOOL, IRI, {"name": "X"}), TOOL, "Test Editor", ORCID)
    assert export.export()
    assert '"name": "X"' in (export.RECORDS_DIR / "tools" / "x.jsonld").read_text()
    assert not export.export()
    writes.retire(IRI, "Test Editor", ORCID)
    assert export.export()
    assert not (export.RECORDS_DIR / "tools" / "x.jsonld").exists()
    assert export.git("log", "--format=%s").splitlines() == ["Records exported", "Records exported"]
