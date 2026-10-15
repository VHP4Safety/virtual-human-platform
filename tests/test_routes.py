"""The platform's pages and API, served without network calls."""

import io
import json
from urllib.parse import parse_qs, quote, urlparse

from PIL import Image as Picture

from admin import tokens, writes
from routes import account

ORCID = "0000-0002-1825-0097"
BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"
FITTING = {"name": "T", "description": "Does T.", "url": "https://t.org/", "about": [STEP]}


def add_records():
    writes.save(writes.document(TOOL, BASE + "tools/t", FITTING), TOOL, "Test Editor", ORCID)


def test_account(site, monkeypatch):
    class Answer:
        status_code = 200

        def json(self):
            return {"orcid": ORCID, "name": "Test Editor"}

    monkeypatch.setattr(account.requests, "post", lambda *a, **k: Answer())
    state = parse_qs(urlparse(site.get("/login/orcid/").headers["Location"]).query)["state"][0]
    assert site.get(f"/orcid/callback/?code=c&state={state}").headers["Location"] == "/account/tokens/"
    site.get("/account/tokens/")
    with site.session_transaction() as session:
        form_token = session["form_token"]
    assert "vhp_" in site.post("/account/tokens/", data={"kinds": "tools", "days": "30", "form_token": form_token}).data.decode()


def test_editor_and_changes(site):
    add_records()
    site.get("/login/")
    with site.session_transaction() as session:
        form_token = session["form_token"]
    secret = tokens.create(ORCID, "Test Editor", ["tools"])
    assert site.post("/login/token/", data={"token": secret, "form_token": form_token, "next": "/admin/"}).status_code == 302
    page = site.get("/admin/tools/").data.decode()
    with site.session_transaction() as session:
        form_token = session["form_token"]
    data = json.loads(page.split('<script type="application/json" id="editor-data">')[1].split("</script>")[0])
    assert {option["iri"]: option["name"] for option in data["choices"]["about"][0]["options"]}[STEP] == "Toxicodynamics (Process Flow Step)"
    answer = site.put("/api/tools/t", json={**FITTING, "about": []}, headers={"X-Form-Token": form_token}).json
    change = site.get(answer["change"] + ".json").json
    assert [(edge["status"], edge["name"]) for edge in change["edges"] if edge["status"] != "kept"] == [("removed", "Toxicodynamics (Process Flow Step)")]


def test_api(site):
    add_records()
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", ["tools"])}
    created = site.put("/api/tools/new", json=FITTING, headers=bearer)
    assert created.status_code == 201
    refused = site.put("/api/tools/new", json={"name": "N", "url": "not a link"}, headers=bearer)
    assert refused.status_code == 422 and set(refused.json["fields"]) == {"url", "description"}
    assert set(site.put("/api/tools/t?preview=true", json={"name": "Z"}, headers=bearer).json["fields"]) == {"description"}
    stale = {**bearer, "If-Match": "an older version"}
    assert site.put("/api/tools/new", json=FITTING, headers=stale).status_code == 412
    assert site.post("/api/tools/new/move", json={"to": "renamed"}, headers=bearer).status_code == 200
    assert site.get("/tools/new").status_code == 301
    picture = io.BytesIO()
    Picture.new("RGB", (30, 20)).save(picture, format="PNG")
    picture.seek(0)
    image = site.post("/api/images", data={"image": (picture, "logo.png")}, headers=bearer).json["@id"]
    assert "immutable" in site.get(image.removeprefix(BASE[:-1])).headers["Cache-Control"]


def test_reads(site):
    add_records()
    page = site.get(f"/api/tools?about={quote(STEP)}").json
    assert [member["@id"] for member in page["hydra:member"]] == [BASE + "tools/t"]
    assert page["hydra:member"][0]["about"] == [{"@id": STEP}]
    assert site.get("/api/tools?nothing=1").status_code == 400
    assert site.get("/api/openapi.json").json["paths"]["/api/tools/{identifier}"]["put"]["security"] == [{"token": []}]


def test_pages(site):
    add_records()
    assert json.loads(site.get("/tools/t.jsonld").data)["about"] == {"@id": STEP}
    assert b"schema:SoftwareApplication" in site.get("/tools/t", headers={"Accept": "text/turtle"}).data
    assert "Does T." in site.get("/tools").data.decode()
    writes.retire(BASE + "tools/t", "Test Editor", ORCID)
    assert site.get("/tools/t").status_code == 410


def test_data(site):
    add_records()
    assert site.get("/data-quality").status_code == 200
    assert site.get("/sources").status_code == 200
