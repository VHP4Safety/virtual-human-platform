"""The write API."""

import io

import pytest
from flask import Flask
from PIL import Image as Picture

from linkeddata import api, changes, images, records, tokens

ORCID = "0000-0002-1825-0097"
BASE = "https://platform.vhp4safety.nl/"
TOOL = {
    "name": "AOP Builder",
    "description": "Builds AOPs from the literature.",
    "url": {"@id": "https://github.com/VHP4Safety/aop-builder"},
}


@pytest.fixture(autouse=True)
def limits(monkeypatch):
    api._requests.clear()
    monkeypatch.setenv("PLATFORM_EDITORS", ORCID)


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.register_blueprint(api.blueprint)
    app.register_blueprint(changes.blueprint)
    app.register_blueprint(images.blueprint)
    return app.test_client()


def bearer(*kinds: str) -> dict:
    return {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", list(kinds))}


def png(width: int = 30, height: int = 20) -> bytes:
    output = io.BytesIO()
    Picture.new("RGB", (width, height), (230, 0, 126)).save(output, format="PNG")
    return output.getvalue()


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
    assert client.get(response.json["change"] + ".json").status_code == 401
    change = client.get(response.json["change"] + ".json", headers=headers).json
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


def test_a_preview_saves_nothing(client):
    headers = bearer("tools")
    client.put("/api/tools/x", json=TOOL, headers=headers)
    response = client.put("/api/tools/x?preview=true", json={"name": TOOL["name"], "url": TOOL["url"], "citation": "a text"}, headers=headers)
    assert response.status_code == 200
    statuses = {(edge["label"], edge["status"]) for edge in response.json["edges"]}
    assert ("Description", "removed") in statuses and ("Name", "kept") in statuses
    assert set(response.json["fields"]) == {"description", "citation"}
    assert records.get(BASE + "tools/x").description == TOOL["description"]
    assert [revision.action for revision in records.history(5)] == ["Added"]


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
    assert client.get(response.json["change"] + ".json", headers=headers).json["action"] == "Removed"
    assert client.put("/api/tools/x", json=TOOL, headers=headers).status_code == 409
    assert client.delete("/api/tools/x?permanent=true", headers=headers).status_code == 200
    assert client.put("/api/tools/x", json=TOOL, headers=headers).status_code == 201


def test_kinds_that_are_not_written_through_the_api(client):
    assert client.put("/api/methods/x", json={"name": "X"}, headers=bearer("methods")).status_code == 404


def test_uploading_an_image(client):
    assert client.post("/api/images", data={"image": (io.BytesIO(png()), "logo.png")}).status_code == 401
    headers = bearer("tools")
    response = client.post("/api/images", data={"image": (io.BytesIO(png()), "logo.png")}, headers=headers)
    assert response.status_code == 201
    address = response.json["@id"]
    assert address.startswith(BASE + "images/") and address.endswith(".webp")
    served = client.get("/" + address.removeprefix(BASE))
    assert served.mimetype == "image/webp"
    assert served.headers["Content-Security-Policy"] == "default-src 'none'"
    assert client.put("/api/tools/x", json={**TOOL, "image": address}, headers=headers).status_code == 201
    refused = client.post("/api/images", data={"image": (io.BytesIO(b"<svg onload='alert(1)'/>"), "logo.svg")}, headers=headers)
    assert refused.status_code == 422
    assert client.post("/api/images", data={}, headers=headers).status_code == 400
    assert client.get("/images/../platform.sqlite").status_code == 404


def test_uploads_are_limited(client, monkeypatch):
    monkeypatch.setattr(images, "MAX_BYTES", 100)
    response = client.post("/api/images", data={"image": (io.BytesIO(png()), "logo.png")}, headers=bearer("tools"))
    assert response.status_code == 413


def test_a_record_changed_since_it_was_read_is_not_replaced(client):
    headers = bearer("tools")
    read = client.put("/api/tools/x", json=TOOL, headers=headers).json["version"]
    assert client.put("/api/tools/x", json={**TOOL, "name": "B"}, headers={**headers, "If-Match": f'"{read}"'}).status_code == 200
    stale = client.put("/api/tools/x", json={**TOOL, "name": "C"}, headers={**headers, "If-Match": f'"{read}"'})
    assert stale.status_code == 412
    assert records.get(BASE + "tools/x").name == "B"
    assert client.delete("/api/tools/x", headers={**headers, "If-Match": f'"{read}"'}).status_code == 412


def test_restoring_a_removed_record(client):
    headers = bearer("tools")
    client.put("/api/tools/x", json=TOOL, headers=headers)
    client.delete("/api/tools/x", headers=headers)
    assert client.post("/api/tools/x/restore", headers=headers).status_code == 200
    record = records.get(BASE + "tools/x")
    assert record.removed_at is None and record.name == TOOL["name"]
    assert records.history(1)[0].action == "Restored"
    assert client.post("/api/tools/x/restore", headers=headers).status_code == 404


def test_moving_a_record(client):
    headers = bearer("tools")
    client.put("/api/tools/old-name", json=TOOL, headers=headers)
    response = client.post("/api/tools/old-name/move", json={"to": "new-name"}, headers=headers)
    assert response.status_code == 200 and response.json["@id"] == BASE + "tools/new-name"
    moved = records.get(BASE + "tools/new-name")
    assert (moved.name, moved.same_as) == (TOOL["name"], [BASE + "tools/old-name"])
    assert records.get(BASE + "tools/old-name").moved_to == BASE + "tools/new-name"
    assert client.put("/api/tools/old-name", json=TOOL, headers=headers).status_code == 409
    client.post("/api/tools/new-name/move", json={"to": "newest-name"}, headers=headers)
    assert records.get(BASE + "tools/old-name").moved_to == BASE + "tools/newest-name"
    assert set(records.get(BASE + "tools/newest-name").same_as) == {BASE + "tools/old-name", BASE + "tools/new-name"}
    back = client.post("/api/tools/newest-name/move", json={"to": "old-name"}, headers=headers)
    assert back.status_code == 200
    assert records.get(BASE + "tools/old-name").moved_to is None
    assert records.get(BASE + "tools/newest-name").moved_to == BASE + "tools/old-name"
    client.put("/api/tools/other", json=TOOL, headers=headers)
    assert client.post("/api/tools/other/move", json={"to": "old-name"}, headers=headers).status_code == 409
