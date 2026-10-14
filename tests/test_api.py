"""The write API."""

import pytest
from flask import Flask

from linkeddata import api, records, tokens

ORCID = "0000-0001-6487-1655"
TOOL = {"name": "AOP Builder", "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}


@pytest.fixture(autouse=True)
def limits():
    api._requests.clear()


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(api.blueprint)
    return app.test_client()


def bearer(*kinds: str) -> dict:
    return {"Authorization": "Bearer " + tokens.create(ORCID, "Julia Meerman", list(kinds))}


def test_writing_a_record(client):
    assert client.put("/api/tools/aop-builder", json=TOOL).status_code == 401
    assert client.put("/api/tools/aop-builder", json=TOOL, headers=bearer("casestudies")).status_code == 401
    headers = bearer("tools")
    response = client.put("/api/tools/aop-builder", json=TOOL, headers=headers)
    assert response.status_code == 201
    assert response.json == {"@id": "https://platform.vhp4safety.nl/tools/aop-builder"}
    record = records.get("https://platform.vhp4safety.nl/tools/aop-builder")
    assert (record.name, record.url, record.source) == ("AOP Builder", "https://github.com/VHP4Safety/aop-builder", "platform")
    assert client.put("/api/tools/aop-builder", json=TOOL, headers=headers).status_code == 200
    assert [revision.action for revision in records.history(5)] == ["Changed", "Added"]


def test_a_record_that_does_not_fit_the_model(client):
    response = client.put("/api/tools/x", json={"name": "X", "url": "not a link"}, headers=bearer("tools"))
    assert response.status_code == 422
    assert "url" in response.json["error"]
    assert records.get("https://platform.vhp4safety.nl/tools/x") is None
    response = client.put("/api/tools/x", json={"name": "X", "softwareVersion": "1"}, headers=bearer("tools"))
    assert response.status_code == 422


def test_new_identifiers(client):
    headers = bearer("tools")
    assert client.post("/api/tools", json=TOOL, headers=headers).json["@id"].endswith("/tools/aop-builder")
    assert client.post("/api/tools", json=TOOL, headers=headers).json["@id"].endswith("/tools/aop-builder-2")
    assert client.post("/api/tools", json={}, headers=headers).status_code == 400


def test_removing_a_record(client):
    headers = bearer("tools")
    client.put("/api/tools/x", json={"name": "X"}, headers=headers)
    assert client.delete("/api/tools/x", headers=headers).status_code == 204
    assert client.put("/api/tools/x", json={"name": "X"}, headers=headers).status_code == 409
    assert client.delete("/api/tools/x?permanent=true", headers=headers).status_code == 204
    assert client.put("/api/tools/x", json={"name": "X"}, headers=headers).status_code == 201


def test_kinds_that_are_not_written_through_the_api(client):
    assert client.put("/api/methods/x", json={"name": "X"}, headers=bearer("methods")).status_code == 404
