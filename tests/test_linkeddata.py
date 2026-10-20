"""Records as linked data: documents, checks, fields from the model, and an import."""

import json

import pytest
from sqlalchemy import select

import database
from admin import writes
from database import records
from database.tables import Note, Source
from linkeddata import checks, documents, fields, imports, model, storage
from linkeddata.model import settings

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"


def test_rdf():
    fitting = writes.document(TOOL, BASE + "tools/t", {"name": "T", "description": "Does T.", "url": {"@id": "https://t.org/"}})
    found = checks.check(fitting)
    assert documents.document(found, BASE + "tools/t")["url"] == {"@id": "https://t.org/"}
    with pytest.raises(checks.NotFitting) as problem:
        checks.check(writes.document(TOOL, BASE + "tools/t", {"name": "T", "installUrl": "not a link"}))
    assert set(problem.value.problems) == {"installUrl", "description"}


def test_fields():
    assert model.download_vocabularies() + model.terms_problems() + model.tables_problems() == []
    for kind in settings()["kinds"].values():
        for field in fields.of(kind):
            assert field["label"], (kind, field["name"])


def test_imports(monkeypatch, tmp_path):
    rules = (imports.SOURCES_DIR / "tools.yaml").read_text()
    monkeypatch.setattr(imports, "SOURCES_DIR", tmp_path / "sources")
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "tools.yaml").write_text(rules)
    tools = {
        "aop-builder": {"id": "aop-builder", "service": "AOP-Builder", "description": "Builds AOPs.", "stage": STEP},
        "x": {"id": "x", "service": "X", "stage": "Other"},
    }
    files = {
        "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/service_index.json": tools,
        "https://cloud.vhp4safety.nl/service/aop-builder.json": {"provider": {"name": "Example Institute", "contact": {"name": "Test Author"}}},
        "https://cloud.vhp4safety.nl/service/x.json": {},
    }
    monkeypatch.setattr(imports, "fetch", lambda url: json.dumps(files[url]).encode())
    assert imports.import_all() == []
    tool = records.get(BASE + "tools/aop-builder")
    found = storage.graph([BASE + "tools/aop-builder", BASE + "tools/x"])
    assert (tool.name, documents.stored_values(found, tool.iri, "processFlowStep")) == ("AOP-Builder", [STEP])
    assert records.get(BASE + "people/test-author").name == "Test Author"
    with database.session() as db:
        assert db.get(Source, "tools").queries.startswith("# title: tools: Tool")
        assert (BASE + "tools/x", "Other") in [(note.iri, note.value) for note in db.scalars(select(Note))]
    assert documents.stored_values(found, BASE + "tools/x", "processFlowStep") == ["Other"]
