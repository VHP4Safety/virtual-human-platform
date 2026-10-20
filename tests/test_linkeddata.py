"""Records as linked data: documents, checks, fields from the model, and an import."""

import json

from sqlalchemy import select

import database
from admin import writes
from database import records
from database.tables import Note, Source
from linkeddata import checks, documents, imports
from linkeddata.profile import download_vocabularies, fields, settings, tables_problems, terms_problems

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"


def test_rdf():
    fitting = writes.document(TOOL, BASE + "tools/t", {"name": "T", "description": "Does T.", "url": {"@id": "https://t.org/"}})
    found, problems, _ = checks.checked(fitting)
    assert not problems and documents.document(found, BASE + "tools/t")["url"] == {"@id": "https://t.org/"}
    _, problems, _ = checks.checked(writes.document(TOOL, BASE + "tools/t", {"name": "T", "installUrl": "not a link"}))
    assert set(problems) == {"installUrl", "description"}


def test_fields():
    assert download_vocabularies() + terms_problems() + tables_problems() == []
    for kind in settings()["kinds"].values():
        for field in fields(kind):
            assert field["label"], (kind, field["name"])


def test_imports(monkeypatch, tmp_path):
    rules = (imports.LAUNCH_DIR / "tools.yaml").read_text()
    monkeypatch.setattr(imports, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(imports, "LAUNCH_DIR", tmp_path / "launch")
    (tmp_path / "launch").mkdir()
    (tmp_path / "launch" / "tools.yaml").write_text(rules)
    tools = {
        "aop-builder": {"id": "aop-builder", "service": "AOP-Builder", "description": "Builds AOPs.", "stage": STEP},
        "x": {"id": "x", "service": "X", "stage": "Other"},
    }
    files = {
        "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/service_index.json": tools,
        "https://cloud.vhp4safety.nl/service/aop-builder.json": {"provider": {"name": "Example Institute", "contact": {"name": "Test Author"}}},
        "https://cloud.vhp4safety.nl/service/x.json": {"provider": {"name": "Test Lab", "url": "https://lab.example/", "contact": {"name": "Test Lab"}}},
    }
    monkeypatch.setattr(imports, "fetch", lambda url: json.dumps(files[url]).encode())
    assert imports.import_all(once=True) == []
    tool = records.get(BASE + "tools/aop-builder")
    found = records.graph([BASE + "tools/aop-builder", BASE + "tools/x"])
    assert (tool.name, documents.stored_values(found, tool.iri, "processFlowStep")) == ("AOP-Builder", [STEP])
    assert records.get(BASE + "people/test-author").name == "Test Author"
    assert (records.get(BASE + "people/test-lab"), records.get(BASE + "organizations/test-lab").type) == (None, "https://schema.org/Organization")
    with database.session() as db:
        assert db.get(Source, "tools").fetched_at
        assert (BASE + "tools/x", "Other") in [(note.iri, note.value) for note in db.scalars(select(Note))]
    assert documents.stored_values(found, BASE + "tools/x", "processFlowStep") == ["Other"]
