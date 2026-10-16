"""Parser of Ontology Lookup Service answers (a workaround, see linkeddata/parsers): the ontologies, and
one answer per term the records are about, by its address. Rows are the terms, with label, definition and
code from their defining ontology, and those ontologies as vocabularies, with title, description and namespace."""

import json
import re

from linkeddata.parsers import link, present


def namespace_of(iri: str, ontology: dict) -> str:
    """A term's namespace: the base address of its ontology that it starts with, or else its address
    without the local name."""
    for base in ontology.get("baseUris") or []:
        if iri.startswith(base):
            return base
    return re.sub(r"[^#/_]+$", "", iri)


def parse(contents: dict[str, bytes]) -> list[dict]:
    ontologies = {}
    for ontology in json.loads(contents["ols"])["_embedded"]["ontologies"]:
        ontologies[ontology["ontologyId"]] = ontology.get("config") or {}
    rows = {}
    for iri, content in sorted(contents.items()):
        if iri == "ols":
            continue
        defining = []
        for term in (json.loads(content).get("_embedded") or {}).get("terms", []):
            if term.get("is_defining_ontology") and term.get("iri") == iri:
                defining.append(term)
        if not defining:
            continue
        term = defining[0]
        ontology = ontologies.get(term["ontology_name"], {})
        vocabulary = "vocabularies/" + term["ontology_name"]
        if vocabulary not in rows:
            rows[vocabulary] = {"@id": vocabulary, "@type": "Vocabulary", "name": ontology.get("title") or term["ontology_name"],
                                "namespace": link(namespace_of(iri, ontology))}
            if present(ontology.get("description")):
                rows[vocabulary]["description"] = ontology["description"]
        row = {"@id": iri, "@type": "Term", "code": term.get("obo_id") or term.get("short_form"), "vocabulary": link(vocabulary)}
        if present(term.get("label")):
            row["label"] = term["label"]
        for definition in term.get("description") or []:
            if present(definition) and "definition" not in row:
                row["definition"] = definition
        rows[iri] = row
    return list(rows.values())
