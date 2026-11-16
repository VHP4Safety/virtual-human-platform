"""Tests of the linked data of the records."""

import json

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SDO
from sqlalchemy import select

import database
from admin import writes
from database import records
from database.tables import Note, Source
from linkeddata import checks, documents, imports, pages
from linkeddata.profile import download_vocabularies, official_problems, tables_problems, terms_problems

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"


def test_rdf():
    fitting = writes.document(TOOL, BASE + "tools/t", {"name": "T", "description": "Does T.", "url": {"@id": "https://t.org/"}})
    found, problems, _ = checks.checked(fitting)
    assert not problems and documents.document(found, BASE + "tools/t")["url"] == {"@id": "https://t.org/"}
    _, problems, warnings = checks.checked(writes.document(TOOL, BASE + "tools/t", {"name": "T", "url": "not a link"}))
    assert (set(problems), "url" in warnings) == ({"description"}, True)


def test_fields():
    assert download_vocabularies() + terms_problems() + tables_problems() + official_problems() == []


def test_dataset_reads_nothing(monkeypatch):
    """A dataset of a listing is made from the steps and the questions that the listing reads once for all its datasets."""
    def read(*_):
        raise AssertionError("read for one dataset")

    for name in ("steps", "questions"):
        monkeypatch.setattr(pages, name, read)
    monkeypatch.setattr(records, "graph", read)
    node = URIRef(BASE + "data/d")
    found = Graph()
    found.add((node, SDO.name, Literal("D")))
    found.add((node, SDO.keywords, URIRef(STEP)))
    shown = pages.dataset(found, node, {STEP: {"label": "Step"}}, set())
    assert (shown["title"], shown["metadata"]["flow_step"]) == ("D", ["Step"])


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
    assert (tool.name, documents.stored_values(found, tool.iri, "keywords")) == ("AOP-Builder", [STEP])
    assert records.get(BASE + "people/test-author").name == "Test Author"
    assert (records.get(BASE + "people/test-lab"), records.get(BASE + "organizations/test-lab").type) == (None, "https://schema.org/Organization")
    with database.session() as db:
        assert db.get(Source, "tools").fetched_at
        assert (BASE + "tools/x", str(SDO.description)) in [(note.iri, note.field) for note in db.scalars(select(Note))]
    assert documents.stored_values(found, BASE + "tools/x", "keywords") == ["Other"]
