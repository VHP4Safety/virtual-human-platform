"""Every test has its own database and records repository, in a temporary folder."""

import pytest

import database
from database import export


@pytest.fixture(autouse=True)
def folders(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(export, "RECORDS_DIR", tmp_path / "records")
