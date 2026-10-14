"""Rows of the records table as linked data with rdfsolve, and linked data as rows."""

import pyoxigraph as ox
import pytest
from sqlalchemy import insert

from linkeddata import database, rdf
from linkeddata.database import Record
from linkeddata.imports import records_of

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
TERM = "https://schema.org/DefinedTerm"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"


def test_fields_are_the_columns_that_the_model_has():
    assert set(rdf.fields(TOOL).index) == {"name", "description", "citation", "url", "image", "about", "conforms_to"}
    assert "citation" not in rdf.fields(TERM).index
    assert rdf.field_of(TOOL, "dct:conformsTo") == "conforms_to"
    with pytest.raises(ValueError):
        rdf.field_of(TOOL, "softwareVersion")


def test_rows_as_linked_data():
    with database.session() as db, db.begin():
        db.execute(insert(Record), [
            rdf.row(BASE + "tools/t", TOOL, "tools", {"name": ["T"], "url": ["https://t.org/"], "about": [STEP]}),
            rdf.row(STEP, TERM, "glossary", {"name": ["Toxicodynamics"]}),
        ])
    document = rdf.document(rdf.graph([BASE + "tools/t", STEP]))
    nodes = {node["@id"]: node for node in document["@graph"]}
    assert nodes[BASE + "tools/t"]["url"] == {"@id": "https://t.org/"}
    assert nodes[STEP]["name"] == "Toxicodynamics"
    with pytest.raises(ValueError, match="url"):
        rdf.check(rdf.row(BASE + "tools/u", TOOL, "platform", {"url": ["not a link"]}))
    with pytest.raises(ValueError, match="one value"):
        rdf.row(BASE + "tools/u", TOOL, "platform", {"name": ["U", "V"]})


def test_linked_data_as_rows():
    data = ox.Dataset(ox.parse(f"""
        @prefix schema: <https://schema.org/> .
        <{BASE}tools/t> a schema:SoftwareApplication ; schema:name "T" ;
            schema:url <https://t.org/> ; schema:about <{STEP}>, "Other" .
    """.encode(), format=ox.RdfFormat.TURTLE))
    [row] = records_of(data, [TOOL], "tools")
    assert row["iri"] == BASE + "tools/t"
    assert (row["name"], row["url"], row["about"], row["source"]) == ("T", "https://t.org/", [STEP], "tools")


def test_the_application_profile():
    with pytest.raises(rdf.NotFitting) as problem:
        rdf.check(rdf.row(BASE + "tools/u", TOOL, "platform", {"name": ["U"], "url": ["javascript:alert(1)"]}))
    assert problem.value.problems["url"] == ["A web address starts with https:// or http://."]
    with pytest.raises(rdf.NotFitting) as problem:
        rdf.check(rdf.row(BASE + "tools/u", TOOL, "platform", {"name": ["U"]}))
    assert problem.value.problems["description"] == ["Describe the tool in a few sentences."]
    assert "conforms_to" in problem.value.problems


def test_the_publication_to_cite_is_a_doi():
    fitting = {
        "name": ["U"],
        "description": ["Does U."],
        "url": ["https://u.org/"],
        "conforms_to": ["https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE"],
    }
    for citation in ["a text about a paper", "https://example.org/paper"]:
        with pytest.raises(rdf.NotFitting) as problem:
            rdf.check(rdf.row(BASE + "tools/u", TOOL, "platform", {**fitting, "citation": [citation]}))
        assert problem.value.problems == {"citation": ["Give the publication's DOI as a web address, starting with https://doi.org/10."]}
    rdf.check(rdf.row(BASE + "tools/u", TOOL, "platform", {**fitting, "citation": ["https://doi.org/10.5281/zenodo.1234567"]}))
