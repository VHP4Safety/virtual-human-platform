"""Fixtures with a database and a records repository in a temporary folder."""

import pytest

import database
from database import export


@pytest.fixture(autouse=True)
def folders(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(export, "RECORDS_DIR", tmp_path / "records")
    monkeypatch.setenv("PLATFORM_EDITORS", "0000-0002-1825-0097")


@pytest.fixture
def site():
    import app as platform

    return platform.app.test_client()
