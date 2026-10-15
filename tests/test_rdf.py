"""Records as JSON-LD documents, linked data as records, and the checks of the model."""

import pyoxigraph as ox
import pytest
from rdflib import URIRef
from rdflib.namespace import SDO
from sqlalchemy import insert

import database
from admin import writes
from database.tables import Record
from linkeddata import forms, rdf
from linkeddata.imports import records_of

BASE = "https://platform.vhp4safety.nl/"
TOOL = "https://schema.org/SoftwareApplication"
TERM = "https://schema.org/DefinedTerm"
STEP = "https://vhp4safety.github.io/glossary#VHP0000156"


def test_the_fields_of_a_class_are_those_of_its_shapes():
    assert {"name", "url", "about", "provider", "maintainer", "softwareHelp", "creativeWorkStatus", "dct:conformsTo"} <= {field["name"] for field in forms.form(TOOL)}
    assert "citation" not in {field["name"] for field in forms.form(TERM)}
    with pytest.raises(ValueError, match="applicationCategory"):
        writes.document(TOOL, BASE + "tools/u", {"applicationCategory": "1"})


def test_documents_as_linked_data():
    tool = writes.document(TOOL, BASE + "tools/t", {"name": "T", "url": "https://t.org/", "about": [STEP]})
    assert tool["url"] == {"@id": "https://t.org/"}
    with database.session() as db, db.begin():
        db.execute(insert(Record), [rdf.row(tool, TOOL, "tools"), rdf.row(writes.document(TERM, STEP, {"name": "Toxicodynamics"}), TERM, "glossary")])
    found = rdf.graph([BASE + "tools/t", STEP])
    assert (URIRef(BASE + "tools/t"), SDO.url, URIRef("https://t.org/")) in found
    assert str(found.value(URIRef(STEP), SDO.name)) == "Toxicodynamics"
    with pytest.raises(ValueError, match="url"):
        rdf.check(writes.document(TOOL, BASE + "tools/u", {"url": "not a link"}))
    with pytest.raises(ValueError, match="one value"):
        writes.document(TOOL, BASE + "tools/u", {"name": ["U", "V"]})


def test_linked_data_as_records():
    data = ox.Dataset(ox.parse(f"""
        @prefix schema: <https://schema.org/> .
        <{BASE}tools/t> a schema:SoftwareApplication ; schema:name "T" ;
            schema:url <https://t.org/> ; schema:about <{STEP}>, "Other" .
    """.encode(), format=ox.RdfFormat.TURTLE))
    [row] = records_of(data, [TOOL], "tools")
    assert (row["iri"], row["name"], row["source"]) == (BASE + "tools/t", "T", "tools")
    assert (rdf.values(row["document"], "url"), rdf.values(row["document"], "about")) == (["https://t.org/"], [STEP])


def test_the_application_profile():
    with pytest.raises(rdf.NotFitting) as problem:
        rdf.check(writes.document(TOOL, BASE + "tools/u", {"name": "U", "url": {"@id": "javascript:alert(1)"}}))
    assert problem.value.problems["url"] == ["A web address starts with https:// or http://."]
    document = writes.document(TOOL, BASE + "tools/u", {"name": "U"})
    document.pop("dct:conformsTo")
    with pytest.raises(rdf.NotFitting) as problem:
        rdf.check(document)
    assert problem.value.problems["description"] == ["Describe the tool in a few sentences."]
    assert "dct:conformsTo" in problem.value.problems


def test_the_publication_to_cite_is_a_doi():
    fitting = {"name": "U", "description": "Does U.", "url": "https://u.org/"}
    for citation in ["a text about a paper", "https://example.org/paper"]:
        with pytest.raises(rdf.NotFitting) as problem:
            rdf.check(writes.document(TOOL, BASE + "tools/u", {**fitting, "citation": citation}))
        assert problem.value.problems == {"citation": ["Give the publication's DOI as a web address, starting with https://doi.org/10."]}
    rdf.check(writes.document(TOOL, BASE + "tools/u", {**fitting, "citation": "https://doi.org/10.5281/zenodo.1234567"}))
