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
        # The limit is one count for all operations of the API.
        assert site.get("/api/tools").status_code == 429
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


def test_written_formats(site):
    """A record is read from JSON-LD or Turtle only, with a context only from the body: the node at the address, or the one
    node without an address."""
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", ["tools"])}
    record = json.dumps({"@type": "SoftwareApplication", **FITTING})
    assert site.put(NEW, data=record, content_type="application/x-www-form-urlencoded", headers=bearer).status_code == 415
    assert site.post("/api/tools", data=record, content_type="text/plain", headers=bearer).status_code == 415
    own = {"@context": {"@vocab": "https://schema.org/"}, "@type": "SoftwareApplication", "name": "Own", "description": "Does O."}
    for context in ("http://127.0.0.1:9/context.jsonld", 5, [{"@import": "http://127.0.0.1:9/context.jsonld"}]):
        assert site.put(NEW, json={**own, "@context": context}, headers=bearer).status_code == 422, context
    assert site.put(NEW, json={**own, "@id": "https://example.org/other"}, headers=bearer).status_code == 422
    assert site.put(NEW, json=own, headers=bearer).status_code == 201 and "Does O." in site.get(NEW, headers={"Accept": "text/turtle"}).data.decode()
    assert site.post("/api/tools", json=own, headers=bearer).json["@id"] == BASE + "tools/own"
    blank = '[] a <https://schema.org/SoftwareApplication> ; <https://schema.org/name> "Blank" .'
    assert site.put("/api/tools/blank", data=blank, content_type="text/turtle", headers=bearer).status_code == 201
    assert site.get("/api/tools/blank").json["name"] == "Blank"
    for path in (NEW, "/api/tools"):
        assert site.open(path, method="PUT" if path == NEW else "POST", data="<a> <b", content_type="text/turtle", headers=bearer).status_code == 422
    assert site.put(NEW, json={"@type": "SoftwareApplication", "name": "\ud800"}, headers=bearer).status_code == 422


def test_kind_and_address(site):
    """A record keeps the kind of its class, at <kind>/<name>; only a term of a vocabulary is at its own address elsewhere."""
    add_records()
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", list(settings()["kinds"]))}
    person = {"@type": "Person", "name": "P"}
    for path, method in (("/api/tools", "POST"), ("/api/tools/t", "PUT"), ("/api/tools/p", "PUT")):
        assert site.open(path, method=method, json=person, headers=bearer).status_code == 422, path
    assert site.post("/api/tools", json={**person, "@type": ["Person", "SoftwareApplication"]}, headers=bearer).status_code == 422
    for path in ("tools", "admin", "foo/u", "tools/a b", "tools/facets", "tools/U", "https://github.com/x/y"):
        assert site.put("/api/" + path, json={"@type": "SoftwareApplication", "name": "U"}, headers=bearer).status_code == 422, path
    # A new record without a class, or with the class of schema.org in http, has the class of the kind of its address.
    assert site.put("/api/tools/untyped", json={"name": "U"}, headers=bearer).status_code == 201
    assert site.put("/api/tools/http", json={"@type": "http://schema.org/SoftwareApplication", "name": "H"}, headers=bearer).status_code == 201
    term = {"@type": "DefinedTerm", "name": "Term"}
    assert site.put("/api/https://example.org/term", json=term, headers=bearer).status_code == 201
    assert site.put("/api/https://example.org/a term", json=term, headers=bearer).status_code == 422
    assert site.post("/api/terms", json={**term, "@id": BASE + "tools/term"}, headers=bearer).status_code == 422
    for to in ("tools/a b", "https://example.org/x", "people/t", "tools/facets", "tools/t#x", "tools/../people/t", "tools/t"):
        assert site.post("/api/move", json={"record": "tools/t", "to": to}, headers=bearer).status_code in (409, 422), to
    assert site.get("/api/tools/t").status_code == 200


def test_token_of_other_kind(site):
    """A write without a valid token is refused with 401, and with a token for other kinds with 403, naming the kind."""
    secret = tokens.create(ORCID, "Test Editor", ["tools"])
    person = {"@type": "Person", "name": "P"}
    refused = site.put("/api/people/p", json=person)
    assert refused.status_code == 401 and refused.headers["WWW-Authenticate"] == "Bearer"
    other = site.put("/api/people/p", json=person, headers={"Authorization": "Bearer " + secret})
    assert other.status_code == 403 and "people" in other.json["message"]
    assert site.put(NEW, json={"@type": "SoftwareApplication", **FITTING}, headers={"Authorization": "bearer " + secret}).status_code == 201


def test_links_only_web(site):
    """A link field takes only http and https addresses, and a page links no other value, such as javascript:."""
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", ["tools"])}
    for value in ("javascript:alert(document.domain)", {"@id": "javascript:alert(1)"}, "data:text/html,x", " JavaScript:alert(1)"):
        assert site.put(NEW, json={"@type": "SoftwareApplication", "name": "J", "url": value}, headers=bearer).status_code == 422, value
    # A text stored before, or imported, is shown but not linked.
    writes.save(writes.document(TOOL, BASE + "tools/j", {"name": "J", "url": "javascript:alert(1)"}), TOOL, "Test Editor", ORCID)
    page = site.get("/tools/j").data.decode()
    assert "J" in page and 'href="javascript:' not in page.replace(" ", "").lower()


def test_bounds(site):
    """Numbers and texts out of their bounds, which the description gives, are refused with 422."""
    namespace = "http://purl.obolibrary.org/obo/UBERON_"
    for path, query in (("/api/tools", {"page": "461168601842738792"}), ("/api/tools", {"page_size": "201"}), ("/api/tools", {"search": "x" * 201}),
                        ("/api/search", {"limit": "99999999999999999999"}), ("/api/search", {"limit": "0"}), ("/api/search", {"limit": "-1"}),
                        ("/api/registries/terms", {"text": "x" * 201, "namespace": namespace})):
        assert site.get(path, query_string=query).status_code == 422, query
    assert site.get("/tools", query_string={"page": "99999999999999999999"}).status_code == 200
    spec = site.get("/api/docs/openapi.json").json
    limit = next(given for given in spec["paths"]["/api/search"]["get"]["parameters"] if given["name"] == "limit")
    assert (limit["schema"]["minimum"], limit["schema"]["maximum"]) == (1, 200)
    page = next(given for given in spec["paths"]["/api/tools"]["get"]["parameters"] if given.get("name") == "page")
    assert page["schema"]["maximum"] and "content" in spec["paths"]["/api/tools"]["get"]["responses"]["200"]["headers"]["X-Pagination"]


def test_read_written_back(site):
    """What the API returns for a record is taken back in a write, in JSON-LD and in Turtle, with the fields that records
    of the kind have outside the profile; the values added on output, such as mainEntityOfPage, are not stored."""
    from database import records
    from linkeddata.documents import context

    writes.save(writes.document(PERSON, BASE + "people/p", {"name": "P"}), PERSON, "Test Editor", ORCID)
    writes.save({"@context": context(settings()), "@id": BASE + "tools/i", "@type": "SoftwareApplication", "name": "I",
                 "image": {"@id": "https://i.org/i.png"}, "author": {"@id": BASE + "people/p"}}, TOOL, "Test Editor", ORCID)
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", list(settings()["kinds"]))}
    for media in ("application/ld+json", "text/turtle"):
        read = site.get("/api/tools/i", headers={"Accept": media}).data
        for query in ("?preview=true", ""):
            answer = site.put("/api/tools/i" + query, data=read, content_type=media, headers=bearer)
            assert answer.status_code == 200, (media, query, answer.json)
    stored = records.graph([BASE + "tools/i"])
    assert "i.png" in stored.serialize(format="nt") and "mainEntityOfPage" not in stored.serialize(format="nt")
    vocabulary = "https://schema.org/DefinedTermSet"
    writes.save({"@context": context(settings()), "@id": BASE + "vocabularies/v", "@type": "DefinedTermSet", "name": "V",
                 "void:uriSpace": "https://v.org/"}, vocabulary, "Test Editor", ORCID)
    assert site.post("/api/vocabularies", json={"name": "W", "void:uriSpace": "https://w.org/"}, headers=bearer).status_code == 201


def test_filters(site):
    """A filter of a list field finds the members of the lists, and a filter that the kind has not is refused. The values
    added on output and the parts of records are not offered as filters."""
    dataset = "https://schema.org/Dataset"
    writes.save(writes.document(PERSON, BASE + "people/p", {"name": "P"}), PERSON, "Test Editor", ORCID)
    writes.save(writes.document(dataset, BASE + "data/d", {"name": "D", "creator": {"@list": [{"@id": BASE + "people/p"}]}}), dataset, "Test Editor", ORCID)
    writes.save(writes.document(TOOL, BASE + "tools/h", {"name": "H", "softwareHelp": {"@type": "CreativeWork", "name": "Help"}}), TOOL, "Test Editor", ORCID)
    assert [record["name"] for record in site.get("/api/data", query_string={"creator": BASE + "people/p"}).json["@graph"]] == ["D"]
    assert [value["value"] for value in site.get("/api/data/facets").json["creator"] if value["count"]] == [BASE + "people/p"]
    assert not [value for value in site.get("/api/tools/facets").json["softwareHelp"] if value["count"]]
    assert "mainEntityOfPage" not in site.get("/api/people/facets").json
    for path in ("/api/people", "/api/people/facets"):
        unknown = site.get(path, query_string={"affiliation": "x"})
        assert unknown.status_code == 422 and "affiliation" in unknown.json["message"], path


def test_search_details(site):
    """The search ignores the case of any letter, takes the start of an address as it is, and returns JSON-LD; each class
    that a record is read with is in the description of getRecord."""
    writes.save(writes.document(PERSON, BASE + "people/v", {"name": "Véronique"}), PERSON, "Test Editor", ORCID)
    writes.save(writes.document("https://schema.org/AboutPage", BASE + "about", {"name": "About"}), "https://schema.org/AboutPage", "Test Editor", ORCID)
    for text in ("VÉRONIQUE", "véronique"):
        assert [found["name"] for found in site.get("/api/search", query_string={"text": text}).json["@graph"]] == ["Véronique"], text
        assert site.get("/api/people", query_string={"search": text}).json["@graph"][0]["name"] == "Véronique", text
    for within in ("%", "_", BASE.upper()):
        assert site.get("/api/search", query_string={"within": within}).json["@graph"] == [], within
    assert site.get("/api/search", query_string={"within": BASE + "people/"}).json["@graph"][0]["name"] == "Véronique"
    assert site.get("/api/search", query_string={"text": "\x00"}).status_code == 422
    assert site.get("/api/search").mimetype == "application/ld+json"
    mapping = site.get("/api/docs/openapi.json").json["paths"]["/api/{path}"]["get"]["responses"]["200"]["content"]["application/ld+json"]["schema"]["discriminator"]["mapping"]
    assert mapping["AboutPage"] == mapping["WebPage"]


def test_errors_described(site):
    """The errors are described as the problem details that they are, with 404 and 410 of a record and 429 of each
    operation; a 405 names the allowed methods."""
    spec = site.get("/api/docs/openapi.json").json
    assert "Error" not in spec["components"]["schemas"] and set(spec["components"]["schemas"]["ProblemDetails"]["required"]) <= set(site.get("/api/tools/none").json)
    for response in spec["components"]["responses"].values():
        assert list(response["content"]) == ["application/problem+json"]
    assert {"404", "410"} <= set(spec["paths"]["/api/{path}"]["get"]["responses"])
    assert all("429" in operation["responses"] for _, _, operation in operations(spec))
    assert "GET" in site.post("/api/search").headers["Allow"]


def test_linked_names(site):
    """A linked record that is removed gives no name, a moved one the name at its new address, and a record removed
    permanently leaves the data of the pages that link it."""
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", list(settings()["kinds"]))}
    for path, name in (("people/p", "P"), ("people/r", "Rita")):
        writes.save(writes.document(PERSON, BASE + path, {"name": name}), PERSON, "Test Editor", ORCID)
    writes.save(writes.document(TOOL, BASE + "tools/l", {"name": "L", "author": [{"@id": BASE + "people/p"}, {"@id": BASE + "people/r"}]}), TOOL, "Test Editor", ORCID)
    site.put("/api/people/p", json={"@type": "Person", "name": "Q"}, headers=bearer)
    site.post("/api/move", json={"record": "people/p", "to": "people/q"}, headers=bearer)
    assert {author.get("name") for author in site.get("/api/tools/l").json["author"]} == {"Q", "Rita"}
    site.delete("/api/people/q", headers=bearer)
    assert {author.get("name") for author in site.get("/api/tools/l").json["author"]} == {None, "Rita"}
    assert "Rita" in site.get("/tools/l").data.decode()
    site.delete("/api/people/r?permanent=true", headers=bearer)
    assert "Rita" not in site.get("/tools/l").data.decode()


def test_write_states(site):
    """A write is refused with 412 for a version that is not the stored one, or with If-None-Match: * at a taken address,
    with 409 naming the new address of a moved record and with 410 for a removed one; If-Match: * and a list of versions
    are taken, a part is restored with its record only, POST previews too, and a blank name is reported as missing."""
    add_records()
    bearer = {"Authorization": "Bearer " + tokens.create(ORCID, "Test Editor", list(settings()["kinds"]))}
    assert site.put("/api/tools/t", json=FITTING, headers={**bearer, "If-Match": "*"}).status_code == 200
    version = site.get("/api/tools/t").headers["ETag"]
    assert site.put("/api/tools/t", json=FITTING, headers={**bearer, "If-Match": f'"other", {version}'}).status_code == 200
    assert site.put("/api/tools/t", json=FITTING, headers={**bearer, "If-None-Match": "*"}).status_code == 412
    assert site.put("/api/tools/fresh", json=FITTING, headers={**bearer, "If-None-Match": "*"}).status_code == 201
    assert site.post("/api/tools?preview=true", json={"name": "Preview"}, headers=bearer).status_code == 200
    assert site.get("/api/tools/preview").status_code == 404
    blank = site.put("/api/tools/blank", json={"name": " "}, headers=bearer)
    assert blank.status_code == 201 and "name" in blank.json["warnings"]
    assert site.get(blank.json["change"], headers=bearer).status_code == 200
    site.post("/api/move", json={"record": "tools/fresh", "to": "tools/moved"}, headers=bearer)
    moved = site.put("/api/tools/fresh", json=FITTING, headers=bearer)
    assert moved.status_code == 409 and BASE + "tools/moved" in moved.json["message"]
    assert [site.delete("/api/tools/moved", headers=bearer).status_code for _ in range(2)] == [200, 410]
    study = {"@type": "bioschemas_draft:Study", "name": "C", "hasPart": {"@type": "HowTo", "name": "Q"}}
    assert site.put("/api/casestudies/c", json=study, headers=bearer).status_code == 201
    site.delete("/api/casestudies/c", headers=bearer)
    assert site.post("/api/restore", json={"record": "casestudies/c/q"}, headers=bearer).status_code == 409


def signed_in(site, kinds: list[str]) -> str:
    """Sign in to the test site with a new write token for kinds, and return the form token of the session."""
    site.get("/login/")
    with site.session_transaction() as session:
        form_token = session["form_token"]
    site.post("/login/token/", data={"token": tokens.create(ORCID, "Test Editor", kinds), "form_token": form_token})
    return form_token


def test_editor_kinds(site):
    """The editor lists the kinds of the token only, and opens a record with the kind of its class."""
    writes.save(writes.document(PERSON, BASE + "people/p", {"name": "P"}), PERSON, "Test Editor", ORCID)
    signed_in(site, ["tools"])
    listed = site.get("/admin/").data.decode()
    assert "/admin/tools/" in listed and "/admin/people/" not in listed
    opened = site.get("/admin/tools/", query_string={"record": BASE + "people/p"})
    assert opened.status_code == 302 and opened.headers["Location"].startswith("/admin/people/")
    assert site.get(opened.headers["Location"]).status_code == 404


def test_form_token_kept(site):
    """A sign-out and a new sign-in keep the form token of the session, so that an editor page opened before still saves."""
    form_token = signed_in(site, ["tools"])
    site.get("/logout/")
    assert signed_in(site, ["tools"]) == form_token
    assert site.put(NEW, json={"@type": "SoftwareApplication", **FITTING}, headers={"X-Form-Token": form_token}).status_code == 201
