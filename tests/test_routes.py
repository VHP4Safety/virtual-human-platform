"""Tests of the pages and the API."""

import io
import json
import re

import pytest
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from PIL import Image as Picture

from admin import tokens, writes
from database.records import browsed
from linkeddata import schemas
from linkeddata.profile import fields, settings
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
    assert "keywords" in [parameter["$ref"].rsplit(".", 1)[-1] for parameter in site.get("/api/docs/openapi.json").json["paths"]["/api/tools"]["get"]["parameters"] if "$ref" in parameter]
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
    for name in ("index", "search", "openapi", "documentation", "dump", "terms", "shapes", "void", "catalog", "llms", "kinds"):
        for address in found[name].values() if name == "kinds" else [found[name]]:
            assert site.get(local(address)).status_code == 200, address


def test_llms(site):
    """llms.txt says what the platform holds and where to start, and each of its links on the platform works."""
    add_records()
    answer = site.get("/llms.txt")
    text = answer.data.decode()
    assert (answer.status_code, answer.mimetype) == (200, "text/markdown") and text.startswith("# ")
    assert "search first" in text and all(kind in text for kind in settings()["kinds"])
    links = re.findall(r"\]\(([^)]+)\)", text)
    assert len(links) >= 8 and BASE + "api/tools/t" in links
    for link in links:
        if link.startswith(BASE):
            assert site.get(local(link)).status_code == 200, link


def test_agents_line(site):
    """The text of each page and of each Markdown page names the entry points, as agents read the text, not the headers."""
    add_records()
    for path in ("/tools", "/tools/t"):
        text = BeautifulSoup(site.get(path).data, "html.parser").get_text(" ")
        assert all(BASE + end in text for end in ("llms.txt", "api/search?text=T", "api/docs/openapi.json", "api/dump")), path
    markdown = site.get("/tools/t.md").data.decode()
    assert all(BASE + end in markdown for end in ("llms.txt", "api/search?text=T", "api/docs/openapi.json", "api/dump")), markdown[-400:]


def operations(spec: dict) -> list[tuple[str, str, dict]]:
    """Return the method, the path and the description of each operation of an OpenAPI document."""
    return [(method, path, operation) for path, methods in spec["paths"].items() for method, operation in methods.items() if method != "parameters"]


def test_operations_named(site):
    """Each operation has an operationId, a summary and a description, as tool generators make one tool per operation."""
    found = operations(site.get("/api/docs/openapi.json").json)
    ids = [operation.get("operationId") for _, _, operation in found]
    assert all(ids) and len(set(ids)) == len(ids), ids
    for method, path, operation in found:
        assert operation.get("summary") and operation.get("description"), f"{method} {path}"


def described(schema: dict) -> bool:
    """Return True if a JSON schema names its fields: properties, a reference, typed values of a map, items that do, or
    a choice of schemas that do."""
    if schema.get("type") == "array":
        return described(schema.get("items") or {})
    if "anyOf" in schema:
        return all(described(choice) for choice in schema["anyOf"])
    return bool(schema.get("properties") or schema.get("$ref") or isinstance(schema.get("additionalProperties"), dict))


def test_responses_described(site):
    """Each JSON response has a schema with its fields, so that an agent knows them before the call."""
    for method, path, operation in operations(site.get("/api/docs/openapi.json").json):
        for code, response in operation["responses"].items():
            for media, content in (response.get("content") or {}).items():
                if "json" in media:
                    assert described(content.get("schema") or {}), f"{method} {path} {code} {media}"


def test_start_described(site):
    """The description of the API says where to start: search first, then read the record, with real addresses."""
    add_records()
    text = site.get("/api/docs/openapi.json").json["info"]["description"]
    assert text.index("GET /api/search?text=T") < text.index("GET /api/tools/t") < text.index("GET /api/tools?keywords=") < text.index("GET /api/tools/facets")


def test_fields_described(site):
    """Each kind has its operations, a schema with each field of its profile, and a filter for each field that filters."""
    spec = site.get("/api/docs/openapi.json").json
    for kind, of_class in settings()["kinds"].items():
        schema = spec["components"]["schemas"][schemas.kind_name(of_class)]
        assert {field["name"] for field in fields(of_class)} <= set(schema["properties"]), kind
        listed = {spec["components"]["parameters"][parameter["$ref"].rsplit("/", 1)[-1]]["name"]
                  for parameter in spec["paths"][f"/api/{kind}"]["get"]["parameters"] if "$ref" in parameter}
        assert listed == {field["name"] for field in fields(of_class) if browsed(field)}, kind
        assert set(spec["paths"][f"/api/{kind}/facets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["propertyNames"]["enum"]) == listed
        assert "$ref" in spec["paths"][f"/api/{kind}"]["post"]["requestBody"]["content"]["application/ld+json"]["schema"]


def test_examples_work(site):
    """The examples of the description are taken from the stored records, so that each one works on this platform."""
    add_records()
    spec = site.get("/api/docs/openapi.json").json
    assert "aopwikiapi" not in json.dumps(spec)
    assert spec["components"]["schemas"]["SoftwareApplication"]["examples"][0]["@id"] == BASE + "tools/t"
    reading = spec["paths"]["/api/{path}"]
    for example in reading["parameters"][0]["examples"].values():
        assert site.get("/api/" + example["value"]).status_code == 200, example
    assert "Does T." in reading["get"]["responses"]["200"]["content"]["text/turtle"]["example"]
    search = spec["paths"]["/api/search"]["get"]
    text = next(parameter["example"] for parameter in search["parameters"] if parameter["name"] == "text")
    assert site.get("/api/search", query_string={"text": text}).json["@graph"] == search["responses"]["200"]["content"]["application/ld+json"]["example"]["@graph"]
    for address in re.findall(r"`GET (/api/[^`]+)`", spec["info"]["description"]):
        if "<" not in address:
            assert site.get(address).status_code == 200, address


@pytest.mark.parametrize("copy", [False, True])
def test_copy_not_indexed(site, monkeypatch, copy):
    """A copy at another address, such as a test site, is kept out of search indexes and training sets; the platform is not."""
    add_records()
    monkeypatch.setitem(settings(), "copy", copy)
    for path in ("/tools", "/tools/t", "/api/search?text=t", "/llms.txt"):
        assert (site.get(path).headers.get("X-Robots-Tag") == "noindex") == copy, path
    assert ('<meta name="robots" content="noindex" />' in site.get("/tools").data.decode()) == copy
    robots = site.get("/robots.txt").data.decode()
    assert ("User-agent: ClaudeBot\nUser-agent: GPTBot\nUser-agent: Google-Extended\nUser-agent: CCBot\nDisallow: /\n" in robots) == copy
    # Search crawlers still read the pages, to see the noindex header.
    assert "User-agent: *\nAllow: /\n" in robots
    # The canonical link of a page of a copy points to the page on the platform itself.
    if copy:
        monkeypatch.setitem(settings(), "base", "https://copy.example/")
    assert BeautifulSoup(site.get("/tools").data, "html.parser").find("link", rel="canonical")["href"] == BASE + "tools"


def test_docs_page(site):
    """The documentation page of the API names the OpenAPI description in its text, as agents do not run its script."""
    page = BeautifulSoup(site.get("/api/docs/").data, "html.parser")
    for script in page.find_all("script"):
        script.decompose()
    text = page.get_text(" ")
    assert all(BASE + end in text for end in ("api/docs/openapi.json", "api/search?text=", "llms.txt")), text
    assert page.find("link", rel="service-desc")["href"] == "/api/docs/openapi.json"


def test_rate_limit(site):
    """Over the limit of the API, the answer is 429 with Retry-After and a hint, and the limit is in the description."""
    from routes import records_api

    try:
        answers = [site.get("/api/search", query_string={"text": "x"}) for _ in range(301)]
        refused = answers[-1]
        assert refused.status_code == 429 and refused.headers.get("Retry-After") and refused.mimetype == "application/problem+json"
        assert answers[0].headers.get("X-RateLimit-Limit") == "300"
    finally:
        records_api.limiter.reset()
    assert records_api.LIMIT in site.get("/api/docs/openapi.json").json["info"]["description"]


def test_registries_open(site):
    """The registries are searched without a token, with a lower limit, as each search is sent on to a registry."""
    from routes import records_api

    assert site.get("/api/registries").status_code == 200
    empty = site.get("/api/registries/terms", query_string={"text": " ", "namespace": "http://purl.obolibrary.org/obo/UBERON_"})
    assert (empty.status_code, empty.json["terms"]) == (200, [])
    assert empty.headers.get("X-RateLimit-Limit") == records_api.REGISTRY_LIMIT.split()[0]
    records_api.limiter.reset()


def test_problem_details(site):
    """An error of the API is a problem detail (RFC 9457) that says what to try next, with the fields the editor reads."""
    missing = site.get("/api/tools/nothing-here")
    assert (missing.status_code, missing.mimetype) == (404, "application/problem+json")
    assert (missing.json["status"], missing.json["title"]) == (404, "Not Found") and BASE + "api/search?text=" in missing.json["hint"]
    refused = site.put(NEW, json={"@type": "SoftwareApplication", **FITTING})
    assert refused.status_code == 401 and refused.json["message"] and "token" in refused.json["hint"]
    wrong = site.get("/api/search", query_string={"limit": "many"})
    assert wrong.status_code == 422 and wrong.json["errors"] and BASE + "api/docs/openapi.json" in wrong.json["hint"]
