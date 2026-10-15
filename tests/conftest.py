"""Every test has its own database and records repository in a temporary folder; the platform's pages
are served without network calls."""

import pytest

import database
from database import export


@pytest.fixture(autouse=True)
def folders(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(export, "RECORDS_DIR", tmp_path / "records")
    monkeypatch.setenv("PLATFORM_EDITORS", "0000-0002-1825-0097")


@pytest.fixture
def site(monkeypatch):
    import app as platform
    from routes import api

    api._requests.clear()
    monkeypatch.setattr(platform, "get_json_dict", lambda url, timeout=5: {})
    monkeypatch.setattr(platform, "get_service_detail", lambda tool_id, timeout=5: {})
    monkeypatch.setattr(platform, "get_repository_data", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(platform, "get_casestudies", lambda: {})
    monkeypatch.setattr(platform, "get_process_flow_steps", lambda: {})
    return platform.app.test_client()
