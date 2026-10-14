"""Write tokens."""

from linkeddata import tokens

ORCID = "0000-0002-1825-0097"


def test_tokens():
    secret = tokens.create(ORCID, "Test Editor", ["tools"])
    assert secret.startswith("vhp_")
    assert tokens.check(secret, "tools").orcid == ORCID
    assert tokens.check(secret, "casestudies") is None
    assert tokens.check("vhp_wrong", "tools") is None
    token = tokens.tokens_of(ORCID)[0]
    assert secret not in str(vars(token))
    assert tokens.revoke(token.id, ORCID)
    assert tokens.check(secret, "tools") is None
    assert tokens.check(tokens.create(ORCID, "Test Editor", ["tools"], days=-1), "tools") is None
