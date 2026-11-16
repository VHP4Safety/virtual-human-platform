"""Tests of the pages and the API."""

import io
import json
from urllib.parse import parse_qs, urlparse

from PIL import Image as Picture

from admin import tokens, writes
from linkeddata.profile import settings
from routes import account

ORCID = "0000-0002-1825-0097"
BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
PERSON = "https://schema.org/Person"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"
FITTING = {"name": "T", "description": "Does T.", "url": {"@id": "https://t.org/"}, "keywords": [{"@id": STEP}]}
NEW = "/api/tools/new"


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


def test_unlisted_orcid(site, monkeypatch):
    """An ORCID sign-in proves the iD; an iD that is not in PLATFORM_EDITORS may not edit or make tokens."""
    class Answer:
        status_code = 200

        def json(self):
            return {"orcid": "0000-0001-0000-0001", "name": "Not An Editor"}

    monkeypatch.setattr(account.requests, "post", lambda *a, **k: Answer())
    state = parse_qs(urlparse(site.get("/login/orcid/").headers["Location"]).query)["state"][0]
    site.get(f"/orcid/callback/?code=c&state={state}")
    assert "not on the list of editors" in site.get("/account/tokens/").data.decode()
    with site.session_transaction() as session:
        form_token = session["form_token"]
    assert "vhp_" not in site.post("/account/tokens/", data={"kinds": "tools", "days": "30", "form_token": form_token}).data.decode()
    assert site.get("/admin/").status_code == 302
    assert site.put(NEW, json={"@type": "SoftwareApplication", **FITTING}, headers={"X-Form-Token": form_token}).status_code == 401


def test_removed_editor(site, monkeypatch):
    """An editor taken out of PLATFORM_EDITORS loses the sign-in and the tokens at the next request."""
    secret = tokens.create(ORCID, "Test Editor", ["tools"])
    site.get("/login/")
    with site.session_transaction() as session:
        form_token = session["form_token"]
    site.post("/login/token/", data={"token": secret, "form_token": form_token})
    assert site.get("/admin/").status_code == 200
    monkeypatch.setenv("PLATFORM_EDITORS", "0000-0001-0000-0001")
    assert site.get("/admin/").status_code == 302
    bearer = {"Authorization": "Bearer " + secret}
    assert site.put(NEW, json={"@type": "SoftwareApplication", **FITTING}, headers=bearer).status_code == 401


def test_editor_and_changes(site):
    add_records()
    site.get("/login/")
    with site.session_transaction() as session:
        form_token = session["form_token"]
    secret = tokens.create(ORCID, "Test Editor", ["tools", "people"])
    assert site.post("/login/token/", data={"token": secret, "form_token": form_token, "next": "/admin/"}).status_code == 302
    assert "Tools" in site.get("/admin/").data.decode()
    assert "<shacl-form" in site.get("/admin/tools/?record=" + BASE + "tools/t").data.decode()
    assert "Toxicodynamics (Process Flow Step)" in site.get("/admin/form.ttl").data.decode()
    with site.session_transaction() as session:
        form_token = session["form_token"]
    turtle = f'<{BASE}tools/t> a <{TOOL}> ; <https://schema.org/name> "T" ; <https://schema.org/description> "Does T." .'
    answer = site.put("/api/tools/t", data=turtle, content_type="text/turtle", headers={"X-Form-Token": form_token}).json
    change = site.get(answer["change"]).data.decode()
    assert "graph-removed" in change and "Toxicodynamics (Process Flow Step)" in change
    # A stored person is kept as it is in the editor, and changed with a write token.
    writes.save(writes.document(PERSON, BASE + "people/p", {"name": "P"}), PERSON, "Test Editor", ORCID)
    person = f'<{BASE}people/p> a <{PERSON}> ; <https://schema.org/name> "Q" .'
    assert site.put("/api/people/p", data=person, content_type="text/turtle", headers={"X-Form-Token": form_token}).status_code == 403
    assert site.put("/api/people/p", data=person, content_type="text/turtle", headers={"Authorization": "Bearer " + secret}).status_code == 200


def test_api(site):
    add_records()
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", ["tools"])}
    created = site.put(NEW, json={"@type": "SoftwareApplication", **FITTING}, headers=bearer)
    assert created.status_code == 201 and "Does T." in site.get(NEW, headers={"Accept": "text/turtle"}).data.decode()
    warned = site.put(NEW, json={"name": "N", "url": "not a link"}, headers=bearer)
    assert warned.status_code == 200 and {"url", "description"} <= set(warned.json["warnings"])
    assert "not a link" in site.get(NEW, headers={"Accept": "text/turtle"}).data.decode()
    stale = {**bearer, "If-Match": "an older version"}
    assert site.put(NEW, json=FITTING, headers=stale).status_code == 412
    assert site.post("/api/move", json={"record": "tools/new", "to": "tools/renamed"}, headers=bearer).status_code == 200
    assert site.get("/tools/new").status_code == 301
    picture = io.BytesIO()
    Picture.new("RGB", (30, 20)).save(picture, format="PNG")
    picture.seek(0)
    image = site.post("/api/images", data={"image": (picture, "logo.png")}, headers=bearer).json["@id"]
    assert "immutable" in site.get(image.removeprefix(BASE[:-1])).headers["Cache-Control"]


def test_pages(site):
    add_records()
    assert json.loads(site.get("/tools/t.jsonld").data)["keywords"] == {"@id": STEP}
    assert b"schema:SoftwareApplication" in site.get("/tools/t", headers={"Accept": "text/turtle"}).data
    assert "Does T." in site.get("/tools").data.decode()
    assert "<h1>Publications</h1>" in site.get("/publications").data.decode()
    assert site.get("/api/tools", query_string={"keywords": STEP}).json["@graph"][0]["name"] == "T"
    assert {"value": STEP, "count": 1} in [{"value": item["value"], "count": item["count"]} for item in site.get("/api/tools/facets").json["keywords"]]
    assert "tools" in site.get("/api/docs/openapi.json").json["paths"]["/api/{kind}"]["parameters"][0]["schema"]["enum"]
    writes.retire(BASE + "tools/t", "Test Editor", ORCID)
    assert site.get("/tools/t").status_code == 410



def local(address: str) -> str:
    """Return the path of an address of the platform, to request it from the test site."""
    return address.removeprefix(BASE[:-1])


def test_api_index(site):
    """The API catalog anchors the API at its index, which links the entry points of agents and scripts."""
    add_records()
    anchor = site.get("/.well-known/api-catalog").json["linkset"][0]["anchor"]
    for path in (local(anchor), "/api", "/api/"):
        answer = site.get(path)
        assert (answer.status_code, answer.mimetype) == (200, "application/json"), path
    found = site.get(local(anchor)).json
    assert set(found["kinds"]) == set(settings()["kinds"]) and found["start"].startswith("Search first")
    for name in ("search", "openapi", "documentation", "dump", "terms", "shapes", "void", "catalog", "kinds"):
        for address in found[name].values() if name == "kinds" else [found[name]]:
            assert site.get(local(address)).status_code == 200, address
