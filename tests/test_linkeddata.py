"""Records as linked data: their documents and checks, the forms read from the model, and an import."""

import json

import pytest
from sqlalchemy import select

import database
from admin import writes
from database import records
from database.tables import Note, Source
from linkeddata import forms, imports, rdf
from linkeddata.model import settings

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"


def test_rdf():
    fitting = writes.document(TOOL, BASE + "tools/t", {"name": "T", "description": "Does T.", "url": "https://t.org/"})
    found = rdf.check(fitting)
    assert rdf.document(found, BASE + "tools/t")["url"] == {"@id": "https://t.org/"}
    with pytest.raises(rdf.NotFitting) as problem:
        rdf.check(writes.document(TOOL, BASE + "tools/t", {"name": "T", "url": "not a link"}))
    assert set(problem.value.problems) == {"url", "description"}


def test_forms():
    for kind in settings()["classes"]:
        for field in forms.form(kind):
            assert field["label"] and field["entry"], (kind, field["name"])


def test_imports(monkeypatch, tmp_path):
    rules = (imports.SOURCES_DIR / "tools.yaml").read_text()
    monkeypatch.setattr(imports, "SOURCES_DIR", tmp_path / "sources")
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "tools.yaml").write_text(rules)
    folder = database.STATE_DIR / "downloads" / "tools"
    folder.mkdir(parents=True)
    tools = {
        "aop-builder": {"id": "aop-builder", "service": "AOP-Builder", "description": "Builds AOPs.", "stage": STEP},
        "x": {"id": "x", "service": "X", "stage": "Other"},
    }
    (folder / "tools").write_text(json.dumps(tools))
    (folder / "aop-builder").write_text(json.dumps({"provider": {"name": "Example Institute", "contact": {"name": "Test Author"}}}))
    assert imports.import_all(offline=True) == []
    tool = records.get(BASE + "tools/aop-builder")
    assert (tool.name, rdf.values(tool.document, "about")) == ("AOP-Builder", [STEP])
    assert records.get(BASE + "people/test-author").name == "Test Author"
    with database.session() as db:
        assert db.get(Source, "tools").queries.startswith("# title: tools: Tool")
        assert (BASE + "tools/x", "Other") in [(note.iri, note.value) for note in db.scalars(select(Note))]
    assert rdf.values(records.get(BASE + "tools/x").document, "about") == ["Other"]
