"""The write API."""

import pytest
from flask import Flask

from linkeddata import api, changes, records, tokens

ORCID = "0000-0002-1825-0097"
BASE = "https://platform.vhp4safety.nl/"
TOOL = {
    "name": "AOP Builder",
    "description": "Builds AOPs from the literature.",
    "url": {"@id": "https://github.com/VHP4Safety/aop-builder"},
}


@pytest.fixture(autouse=True)
def limits():
    api._requests.clear()


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.register_blueprint(api.blueprint)
    app.register_blueprint(changes.blueprint)
    return app.test_client()


def bearer(*kinds: str) -> dict:
    return {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", list(kinds))}


def test_writing_a_record(client):
    assert client.put("/api/tools/aop-builder", json=TOOL).status_code == 401
    assert client.put("/api/tools/aop-builder", json=TOOL, headers=bearer("casestudies")).status_code == 401
    headers = bearer("tools")
    response = client.put("/api/tools/aop-builder", json=TOOL, headers=headers)
    assert response.status_code == 201
    assert response.json["@id"] == BASE + "tools/aop-builder"
    record = records.get(BASE + "tools/aop-builder")
    assert (record.name, record.url, record.source) == ("AOP Builder", "https://github.com/VHP4Safety/aop-builder", "platform")
    assert record.conforms_to == ["https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE"]
    response = client.put("/api/tools/aop-builder", json={**TOOL, "name": "AOP-Builder"}, headers=headers)
    assert response.status_code == 200
    change = client.get(response.json["change"] + ".json").json
    assert [(field["field"], field["before"], field["after"]) for field in change["fields"]] == [("Name", ["AOP Builder"], ["AOP-Builder"])]
    assert any('"AOP-Builder"' in line for line in change["added"])


def test_a_record_that_does_not_fit_the_model(client):
    headers = bearer("tools")
    response = client.put("/api/tools/x", json={"name": "X", "url": "not a link"}, headers=headers)
    assert response.status_code == 422
    assert set(response.json["fields"]) == {"url"}
    response = client.put("/api/tools/x", json={"name": "X"}, headers=headers)
    assert response.json["fields"] == {
        "description": ["Describe the tool in a few sentences."],
        "url": ["Add the address of the tool's website."],
    }
    response = client.put("/api/tools/x", json={**TOOL, "url": "javascript:alert(1)"}, headers=headers)
    assert response.json["fields"] == {"url": ["A web address starts with https:// or http://."]}
    assert client.put("/api/tools/x", json={**TOOL, "softwareVersion": "1"}, headers=headers).status_code == 422
    assert records.get(BASE + "tools/x") is None


def test_new_identifiers(client):
    headers = bearer("tools")
    assert client.post("/api/tools", json=TOOL, headers=headers).json["@id"].endswith("/tools/aop-builder")
    assert client.post("/api/tools", json=TOOL, headers=headers).json["@id"].endswith("/tools/aop-builder-2")
    assert client.post("/api/tools", json={}, headers=headers).status_code == 400


def test_removing_a_record(client):
    headers = bearer("tools")
    client.put("/api/tools/x", json=TOOL, headers=headers)
    response = client.delete("/api/tools/x", headers=headers)
    assert response.status_code == 200
    assert client.get(response.json["change"] + ".json").json["action"] == "Removed"
    assert client.put("/api/tools/x", json=TOOL, headers=headers).status_code == 409
    assert client.delete("/api/tools/x?permanent=true", headers=headers).status_code == 200
    assert client.put("/api/tools/x", json=TOOL, headers=headers).status_code == 201


def test_kinds_that_are_not_written_through_the_api(client):
    assert client.put("/api/methods/x", json={"name": "X"}, headers=bearer("methods")).status_code == 404

