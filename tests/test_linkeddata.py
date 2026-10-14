"""The parsers, the rdfsolve conversion and checks, and the SQLite file, on small inputs without network access."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pyoxigraph as ox
import yaml

from linkeddata.build import check, convert, documents, write
from linkeddata.model import settings
from linkeddata.parsers import glossary, methods, tools

SOURCES = Path(__file__).parent.parent / "linkeddata" / "sources"
BASE = "https://platform.vhp4safety.nl/"
SCHEMA = "https://schema.org/"
GLOSSARY = "https://vhp4safety.github.io/glossary#"

TOOLS = {
    "aop-builder": {
        "id": "aop-builder",
        "service": "AOP-Builder",
        "description": "Builds AOPs.",
        "main_url": "https://github.com/VHP4Safety/aop-builder",
        "png_file_name": "aopbuilder.png",
        "stage": GLOSSARY + "VHP0000156",
        "reg_q_2a": "true",
        "reg_q_2b": "false",
    },
    "x": {
        "id": "x",
        "service": "X",
        "main_url": "no_url",
        "png_file_name": "https://github.com/VHP4Safety/ui-design/blob/main/static/images/logo.png",
        "stage": "Other",
    },
}


def turtle(text: str) -> ox.Dataset:
    return ox.Dataset(ox.parse(text.encode(), format=ox.RdfFormat.TURTLE))


def objects(data: ox.Dataset, subject: str, predicate: str) -> set:
    found = set()
    for quad in data.quads_for_subject(ox.NamedNode(subject)):
        if quad.predicate == ox.NamedNode(predicate):
            found.add(quad.object)
    return found


def test_tools_parser():
    rows = tools.parse(json.dumps(TOOLS).encode())
    assert rows[0] == {
        "@id": "tools/aop-builder",
        "@type": "Tool",
        "service": "AOP-Builder",
        "description": "Builds AOPs.",
        "main_url": {"@id": "https://github.com/VHP4Safety/aop-builder"},
        "logo": {"@id": "https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/aopbuilder.png"},
        "stage": {"@id": GLOSSARY + "VHP0000156"},
        "questions": [{"@id": "casestudies/parkinson/Q1"}],
    }
    assert rows[1] == {"@id": "tools/x", "@type": "Tool", "service": "X", "stage": "Other"}


def test_methods_parser():
    entry = {
        "id": "m",
        "method": "M",
        "relevant_aop_wiki_key_event(s)_to_the_assay_content": "KE177, KE1547",
        "relevant_aop_wiki_adverse_outcome_pathway(s)_to_the_assay_content": "AOP464",
        "vhp4safety_workflow_stage_content": "AOP, Adverse Outcome",
        "citation_content": "_No response_",
    }
    row = methods.parse(json.dumps({"m": entry}).encode())[0]
    assert row["key_events"] == [
        {"@id": "https://identifiers.org/aop.events/177"},
        {"@id": "https://identifiers.org/aop.events/1547"},
    ]
    assert row["aops"] == [{"@id": "https://identifiers.org/aop/464"}]
    assert row["stages"] == ["AOP", {"@id": GLOSSARY + "VHP0000158"}]
    assert "citation" not in row


def test_glossary_parser():
    turtle = f"""
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        <{GLOSSARY}VHP0000156> rdfs:label "Toxicodynamics (Process Flow Step)"@en-US .
        <{GLOSSARY}VHP0000999> rdfs:label "Not a step"@en-US .
    """
    assert glossary.parse(turtle.encode()) == [
        {"@id": GLOSSARY + "VHP0000156", "@type": "Term", "code": "VHP0000156", "label": "Toxicodynamics"}
    ]


def test_conversion():
    spec = yaml.safe_load((SOURCES / "tools.yaml").read_text(encoding="utf-8"))
    data, queries = convert(spec, tools.parse(json.dumps(TOOLS).encode()), BASE)
    assert objects(data, BASE + "tools/aop-builder", SCHEMA + "about") == {
        ox.NamedNode(GLOSSARY + "VHP0000156"),
        ox.NamedNode(BASE + "casestudies/parkinson/Q1"),
    }
    assert objects(data, BASE + "tools/aop-builder", SCHEMA + "name") == {ox.Literal("AOP-Builder")}
    assert objects(data, BASE + "tools/x", SCHEMA + "about") == {ox.Literal("Other")}
    assert queries[0].startswith("# title: tools: Tool")


def test_checks_report_values_that_do_not_fit():
    data = turtle(f"""
        @prefix schema: <https://schema.org/> .
        <{BASE}tools/a> a schema:SoftwareApplication ; schema:name "A" ; schema:url <https://example.org/a> .
        <{BASE}tools/b> a schema:SoftwareApplication ; schema:name "B" ; schema:url "not a link" .
    """)
    notes = check(data, ["https://schema.org/SoftwareApplication"])
    assert [(note["iri"], note["field"], note["value"]) for note in notes] == [
        (BASE + "tools/b", SCHEMA + "url", "not a link")
    ]


def test_documents_and_database(tmp_path):
    store = ox.Store()
    store.extend(turtle(f"""
        @prefix schema: <https://schema.org/> .
        <{BASE}tools/t> a schema:SoftwareApplication ; schema:name "T" ; schema:about <{GLOSSARY}VHP0000156> .
        <{GLOSSARY}VHP0000156> schema:name "Toxicodynamics" .
    """))
    rows = documents(store, settings())
    assert [iri for iri, _, _ in rows] == [BASE + "tools/t"]
    write(tmp_path / "platform.sqlite", rows, [], [], [])
    with closing(sqlite3.connect(tmp_path / "platform.sqlite")) as db:
        document = db.execute("SELECT document FROM documents").fetchone()[0]
    nodes = {node["@id"]: node for node in json.loads(document)["@graph"]}
    assert nodes[GLOSSARY + "VHP0000156"]["name"] == "Toxicodynamics"


TOXTEMP = {
    "@id": "methods/alamar-blue",
    "@type": "ToxTemp",
    "format_version": 2,
    "metadata": {
        "creation_date": "2026-10-01T10:00:00+02:00",
        "authors": [
            {"credited": True, "name": "Julia Meerman", "organization": "RIVM", "orcid_id": "0000-0001-6487-1655", "email": None}
        ],
    },
    "investigation": {"id": 1, "title": "Parkinson", "description": "", "submission_date": "2026-01-01"},
    "study": {"id": 2, "title": "Cell models", "description": "", "submission_date": "2026-01-01"},
    "assay": {"id": 3, "title": "Alamar blue assay", "description": "Mitochondrial activity.", "version": "1.2"},
    "history": [],
    "sections": [
        {
            "id": 5,
            "title": "5. Test method exposure scheme and endpoints",
            "subsections": [
                {
                    "id": 56,
                    "title": "5.6 Positive controls",
                    "questions": [
                        {
                            "id": 560,
                            "question_text": "Which positive controls are used?",
                            "answer": {"text": "Rotenone", "accepted": True, "llm_abstained": False, "source_documents": []},
                        }
                    ],
                }
            ],
        }
    ],
}


def only(data: ox.Dataset, subject, predicate: str):
    """The one object of a subject (an address or a blank node) for a predicate."""
    found = []
    for quad in data.quads_for_subject(subject):
        if quad.predicate == ox.NamedNode(predicate):
            found.append(quad.object)
    assert len(found) == 1, found
    return found[0]


def test_toxtemp():
    spec = yaml.safe_load((SOURCES / "toxtemp.yaml").read_text(encoding="utf-8"))
    data, _ = convert(spec, TOXTEMP, BASE)
    method = ox.NamedNode(BASE + "methods/alamar-blue")
    assert only(data, method, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type").value == "https://bioschemas.org/draft_terms/LabProtocol"
    assert only(data, method, SCHEMA + "name").value == "Alamar blue assay"
    section = only(data, method, SCHEMA + "hasPart")
    subsection = only(data, section, SCHEMA + "hasPart")
    assert only(data, subsection, SCHEMA + "name").value == "5.6 Positive controls"
    question = only(data, subsection, SCHEMA + "hasPart")
    assert only(data, question, SCHEMA + "name").value == "Which positive controls are used?"
    answer = only(data, question, SCHEMA + "suggestedAnswer")
    assert only(data, answer, SCHEMA + "text").value == "Rotenone"
    author = only(data, method, SCHEMA + "author")
    assert only(data, author, SCHEMA + "identifier").value == "0000-0001-6487-1655"
