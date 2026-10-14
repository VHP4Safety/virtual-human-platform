"""The records repository: saving, removing and the commits, in a temporary folder."""

import json

import pytest

from linkeddata import records

ORCID = "0000-0001-6487-1655"


@pytest.fixture(autouse=True)
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(records, "RECORDS_DIR", tmp_path / "records")


def test_records():
    records.save("tools", "x", {"name": "X"}, "Julia Meerman", ORCID)
    assert json.loads(records.record_path("tools", "x").read_text()) == {"name": "X"}
    assert f"Changed-by: Julia Meerman https://orcid.org/{ORCID}" in records.git("log", "-1", "--format=%B")
    records.retire("tools", "x", "Julia Meerman", ORCID)
    assert not records.record_path("tools", "x").exists()
    assert records.taken("tools", "x")
    records.remove("tools", "x", "Julia Meerman", ORCID)
    assert not records.taken("tools", "x")
    assert records.git("log", "--format=%s").splitlines() == [
        "Removed tools/x permanently",
        "Removed tools/x",
        "Added tools/x",
    ]
