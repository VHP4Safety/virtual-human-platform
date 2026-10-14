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
    data, queries = convert(spec, json.dumps(TOOLS).encode(), BASE)
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
    write(tmp_path / "platform.sqlite", rows, [], [])
    with closing(sqlite3.connect(tmp_path / "platform.sqlite")) as db:
        document = db.execute("SELECT document FROM documents").fetchone()[0]
    nodes = {node["@id"]: node for node in json.loads(document)["@graph"]}
    assert nodes[GLOSSARY + "VHP0000156"]["name"] == "Toxicodynamics"
