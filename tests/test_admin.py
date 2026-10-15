"""What editors do: their write tokens, and the records they write with their revisions."""

from sqlalchemy import select

import database
from admin import accounts, tokens, writes
from database import records
from database.tables import Revision

ORCID = "0000-0002-1825-0097"
BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"


def test_tokens():
    secret = tokens.create(ORCID, "Test Editor", ["tools"])
    assert tokens.check(secret, "tools").orcid == ORCID
    assert tokens.check(secret, "methods") is None
    token = tokens.tokens_of(ORCID)[0]
    assert accounts.editor(ORCID, "Test Editor", token.id).kinds == ["tools"]
    assert tokens.revoke(token.id, ORCID)
    assert tokens.find(secret) is None and accounts.editor(ORCID, "Test Editor", token.id) is None


def test_writes():
    writes.save(writes.document(TOOL, BASE + "tools/x", {"name": "X"}), TOOL, "Test Editor", ORCID)
    writes.move(BASE + "tools/x", BASE + "tools/y", "Test Editor", ORCID)
    assert records.get(BASE + "tools/x").moved_to == BASE + "tools/y"
    writes.retire(BASE + "tools/y", "Test Editor", ORCID)
    writes.restore(BASE + "tools/y", "Test Editor", ORCID)
    assert [record.iri for record in records.of_kind("tools")] == [BASE + "tools/y"]
    writes.remove(BASE + "tools/y", "Test Editor", ORCID)
    with database.session() as db:
        actions = list(db.scalars(select(Revision.action).order_by(Revision.id.desc())))
    assert actions == ["Removed permanently", "Restored", "Removed", "Moved", "Added"]
