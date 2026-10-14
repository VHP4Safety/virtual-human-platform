"""The login of editors and the record editor, on the platform with its network calls replaced."""

import json

import pytest
from sqlalchemy import insert

from linkeddata import api, database, rdf, records, tokens
from linkeddata.database import Record

BASE = "https://platform.vhp4safety.nl/"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"
ORCID = "0000-0002-1825-0097"
TOOL = {"name": "T", "description": "Does T.", "url": "https://t.org/", "about": [STEP]}


@pytest.fixture
def site(monkeypatch):
    import app as platform

    monkeypatch.setattr(platform, "get_json_dict", lambda url, timeout=5: {})
    monkeypatch.setattr(platform, "get_process_flow_steps", lambda: {})
    monkeypatch.setenv("PLATFORM_EDITORS", ORCID)
    api._requests.clear()
    with database.session() as db, db.begin():
        db.execute(insert(Record), [
            rdf.row(BASE + "tools/t", "https://schema.org/SoftwareApplication", "tools", {"name": ["T"], "about": [STEP]}),
            rdf.row(BASE + "tools/old", "https://schema.org/SoftwareApplication", "platform", {"name": ["Old"]}),
            rdf.row(STEP, "https://schema.org/DefinedTerm", "glossary", {"name": ["Toxicodynamics"]}),
        ])
    records.retire(BASE + "tools/old", "Test Editor", ORCID)
    return platform.app.test_client()


def log_in(site, secret: str):
    site.get("/login/")
    with site.session_transaction() as session:
        form_token = session["form_token"]
    return site.post("/login/token/", data={"token": secret, "form_token": form_token, "next": "/admin/"})


def test_the_editor_needs_a_login(site):
    assert site.get("/admin/").headers["Location"] == "/login/?next=/admin/"
    page = site.get("/login/").data.decode()
    assert "Log in with the token" in page
    assert '<ul class="nav editor-nav">' in page


def test_logging_in_with_a_token(site):
    stranger = tokens.create("0000-0002-0000-0000", "Somebody", ["tools"])
    assert log_in(site, stranger).status_code == 403
    assert log_in(site, "vhp_wrong").status_code == 403
    secret = tokens.create(ORCID, "Test Editor", ["tools"])
    assert log_in(site, secret).headers["Location"] == "/admin/"
    assert site.get("/admin/").headers["Location"].endswith("/admin/tools/")
    response = site.get("/admin/tools/")
    assert response.headers["X-Robots-Tag"] == "noindex"
    page = response.data.decode()
    data = json.loads(page.split('<script type="application/json" id="editor-data">')[1].split("</script>")[0])
    assert [field["name"] for field in data["fields"]][:3] == ["name", "description", "url"]
    assert data["choices"]["about"] == [
        {"title": "Steps of the safety assessment", "options": [{"iri": STEP, "name": "Toxicodynamics", "description": ""}]}
    ]
    found = {record["identifier"]: record for record in data["records"]}
    assert found["old"]["removed"]
    assert "Test Editor" in page
    tokens.revoke(tokens.tokens_of(ORCID)[0].id, ORCID)
    assert site.get("/admin/tools/").headers["Location"].startswith("/login/")


def test_the_editor_writes_with_the_login(site):
    log_in(site, tokens.create(ORCID, "Test Editor", ["tools"]))
    site.get("/admin/tools/")
    assert site.put("/api/tools/new", json=TOOL).status_code == 401
    with site.session_transaction() as session:
        form_token = session["form_token"]
    response = site.put("/api/tools/new", json=TOOL, headers={"X-Form-Token": form_token})
    assert response.status_code == 201
    assert records.history(1)[0].name == "Test Editor"
    change = site.get(response.json["change"]).data.decode()
    assert "Added" in change and "Does T." in change
    assert site.put("/api/tools/new", json=TOOL, headers={"X-Form-Token": "forged"}).status_code == 401


def test_a_token_login_does_not_make_tokens(site):
    log_in(site, tokens.create(ORCID, "Test Editor", ["tools"]))
    assert b"logged in with a write token" in site.get("/account/tokens/").data
