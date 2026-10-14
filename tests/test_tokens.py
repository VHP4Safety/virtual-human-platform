"""Write tokens, in a temporary folder."""

import json

import pytest

from linkeddata import tokens

ORCID = "0000-0001-6487-1655"


@pytest.fixture(autouse=True)
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "STATE_DIR", tmp_path / "state")


def test_tokens():
    secret = tokens.create(ORCID, "Julia Meerman", ["tools"])
    assert secret.startswith("vhp_")
    assert tokens.check(secret, "tools")["orcid"] == ORCID
    assert tokens.check(secret, "casestudies") is None
    assert tokens.check("vhp_wrong", "tools") is None
    token = tokens.tokens_of(ORCID)[0]
    assert secret not in json.dumps(token)
    assert tokens.revoke(token["id"], ORCID)
    assert tokens.check(secret, "tools") is None
    assert tokens.check(tokens.create(ORCID, "Julia Meerman", ["tools"], days=-1), "tools") is None
