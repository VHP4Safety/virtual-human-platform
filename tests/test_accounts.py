"""The ORCID login and the token page, on the platform with its network calls replaced."""

from urllib.parse import parse_qs, urlparse

import pytest

from linkeddata import accounts, tokens

ORCID = "0000-0001-6487-1655"


@pytest.fixture
def site(monkeypatch):
    import app as platform

    monkeypatch.setattr(platform, "get_json_dict", lambda url, timeout=5: {})
    monkeypatch.setattr(platform, "get_repository_data", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(platform, "get_casestudies", lambda: {})
    monkeypatch.setattr(platform, "get_process_flow_steps", lambda: {})
    monkeypatch.setenv("ORCID_CLIENT_ID", "APP-TEST")
    return platform.app.test_client()


def log_in(site, monkeypatch) -> None:
    class Answer:
        status_code = 200

        def json(self):
            return {"orcid": ORCID, "name": "Julia Meerman"}

    monkeypatch.setattr(accounts.requests, "post", lambda *a, **k: Answer())
    location = site.get("/login/orcid/").headers["Location"]
    state = parse_qs(urlparse(location).query)["state"][0]
    assert site.get(f"/orcid/callback/?code=c&state={state}").status_code == 302


def test_orcid_login(site, monkeypatch):
    location = site.get("/login/orcid/").headers["Location"]
    assert location.startswith("https://orcid.org/oauth/authorize?")
    query = parse_qs(urlparse(location).query)
    assert query["scope"] == ["/authenticate"]
    assert query["client_id"] == ["APP-TEST"]
    assert site.get("/orcid/callback/?code=c&state=forged").status_code == 400
    log_in(site, monkeypatch)
    with site.session_transaction() as session:
        assert session["orcid"] == ORCID


def test_token_page(site, monkeypatch):
    assert site.get("/account/tokens/").status_code == 302
    log_in(site, monkeypatch)
    assert b"not on the list of editors" in site.get("/account/tokens/").data
    monkeypatch.setenv("PLATFORM_EDITORS", ORCID)
    assert b"Create token" in site.get("/account/tokens/").data
    assert site.post("/account/tokens/", data={"kinds": "tools"}).status_code == 400
    with site.session_transaction() as session:
        form_token = session["form_token"]
    page = site.post("/account/tokens/", data={"kinds": "tools", "days": "30", "form_token": form_token})
    assert b"vhp_" in page.data
    assert tokens.tokens_of(ORCID)[0].kinds == "tools"
