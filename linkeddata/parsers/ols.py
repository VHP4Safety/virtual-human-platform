"""Parser of the Ontology Lookup Service responses."""

import json
import re

from linkeddata.parsers import link, present

OLS = "https://www.ebi.ac.uk/ols4/ontologies/"


def namespace_of(iri: str, ontology: dict) -> str:
    """Return the namespace of a term of an ontology."""
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
            rows[vocabulary] = {"@id": vocabulary, "@type": "DefinedTermSet", "name": ontology.get("title") or term["ontology_name"],
                                "void:uriSpace": namespace_of(iri, ontology), "url": link(OLS + term["ontology_name"])}
            if present(ontology.get("description")):
                rows[vocabulary]["description"] = ontology["description"]
        row = {"@id": iri, "@type": "DefinedTerm", "termCode": term.get("obo_id") or term.get("short_form"), "inDefinedTermSet": link(vocabulary)}
        if present(term.get("label")):
            row["name"] = term["label"]
        for definition in term.get("description") or []:
            if present(definition) and "description" not in row:
                row["description"] = definition
        rows[iri] = row
    return list(rows.values())
