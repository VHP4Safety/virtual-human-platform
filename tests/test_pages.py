"""The records on the platform's pages: their data, removed records, the general record page, the
tools pages and the dashboards, on the platform with its network calls replaced."""

import json

import pytest
from sqlalchemy import insert

from linkeddata import database, rdf, records
from linkeddata.database import Record

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"
ORCID = "0000-0002-1825-0097"


@pytest.fixture
def site(monkeypatch):
    import app as platform

    monkeypatch.setattr(platform, "get_json_dict", lambda url, timeout=5: {})
    monkeypatch.setattr(platform, "get_service_detail", lambda tool_id, timeout=5: {})
    monkeypatch.setattr(platform, "get_repository_data", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(platform, "get_casestudies", lambda: {})
    steps = {STEP: {"label": "Toxicodynamics", "slug": "toxicodynamics", "description": ""}}
    monkeypatch.setattr(platform, "get_process_flow_steps", lambda: steps)
    with database.session() as db, db.begin():
        db.execute(insert(Record), [
            rdf.row(BASE + "tools/t", TOOL, "platform", {"name": ["T"], "description": ["Does T."], "url": ["https://t.org/"], "about": [STEP]}),
            rdf.row(BASE + "tools/old", TOOL, "platform", {"name": ["Old"]}),
            rdf.row(BASE + "methods/m", "https://bioschemas.org/draft_terms/LabProtocol", "methods", {"name": ["M"]}),
            rdf.row(STEP, "https://schema.org/DefinedTerm", "glossary", {"name": ["Toxicodynamics"]}),
        ])
    records.retire(BASE + "tools/old", "Test Editor", ORCID)
    return platform.app.test_client()


def test_data_of_a_record(site):
    response = site.get("/tools/t.jsonld")
    assert response.mimetype == "application/ld+json"
    nodes = {node["@id"]: node for node in json.loads(response.data)["@graph"]}
    assert nodes[BASE + "tools/t"]["about"] == {"@id": STEP}
    assert nodes[STEP]["name"] == "Toxicodynamics"
    response = site.get("/tools/t", headers={"Accept": "text/turtle"})
    assert response.mimetype == "text/turtle"
    assert b"schema:SoftwareApplication" in response.data
    assert site.get("/tools/t.nt").mimetype == "application/n-triples"


def test_tool_pages(site):
    page = site.get("/tools").data.decode()
    assert "Does T." in page
    assert "Old" not in page
    response = site.get("/tools/t")
    page = response.data.decode()
    assert response.status_code == 200
    assert "Toxicodynamics" in page
    assert f'"@id": "{BASE}tools/t"' in page.replace("\\u0026", "&")
    assert '<link rel="alternate" type="text/turtle" href="/tools/t.ttl" />' in page
    assert 'rel="alternate"; type="application/ld+json"' in response.headers["Link"]


def test_removed_record(site):
    assert site.get("/tools/old").status_code == 410
    assert site.get("/tools/old.jsonld").status_code == 410


def test_record_with_no_page_of_its_own(site):
    response = site.get("/methods/m")
    assert response.status_code == 200
    assert "<h1><span class=\"text-vhpblue\">M</span></h1>" in response.data.decode()
    assert site.get("/methods/nothing").status_code == 404


def test_dashboards(site):
    page = site.get("/data-quality").data.decode()
    assert "SoftwareApplication" in page
    assert "1 of 1" in page
    assert site.get("/changes").headers["Location"].startswith("/login/")
    assert "How its fields become the platform" in site.get("/sources").data.decode()


def test_sitemap_leaves_out_the_pages_for_editors(site):
    sitemap = site.get("/sitemap.xml").data.decode()
    assert "/data-quality<" in sitemap
    assert "/login/orcid" not in sitemap
    assert "/account/tokens" not in sitemap


def test_an_earlier_address_forwards_to_the_record(site):
    revision = records.move(BASE + "tools/t", BASE + "tools/renamed", "Test Editor", ORCID)
    assert revision.action == "Moved"
    response = site.get("/tools/t")
    assert (response.status_code, response.headers["Location"]) == (301, "/tools/renamed")
    assert site.get("/tools/t.jsonld").headers["Location"] == "/tools/renamed.jsonld"
    assert site.get("/tools/renamed").status_code == 200
    assert "Does T." in site.get("/tools").data.decode()
    assert site.get("/tools").data.decode().count("Does T.") == 1
