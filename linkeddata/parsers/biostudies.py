"""Parser of the BioStudies collection VHP4Safety (a workaround, see linkeddata/parsers). The search lists
the studies; each study's file (api/v1/studies/<accession>) has sections of attributes, whose qualifiers
(valqual) give a value's address or ontology term. Term identifiers (NCBITaxon_9606) are linked at their
address, with labels from the Ontology Lookup Service (sources/ols.yaml). Authors and organisations are
rows of their own."""

import json
import re

from linkeddata.parsers import QUESTIONS, licence, link, present, publication, slug, web_link

STUDIES = "https://www.ebi.ac.uk/biostudies/studies/"
DATE = "http://www.w3.org/2001/XMLSchema#date"
# Ontologies whose terms are not at purl.obolibrary.org.
ONTOLOGIES = {"BAO": "http://www.bioassayontology.org/bao#"}


def keys(index: bytes) -> list[str]:
    """The accessions of the studies on the search's one page."""
    found = json.loads(index)
    if found.get("totalHits", 0) > len(found.get("hits", [])):
        raise ValueError("more studies than one search page")
    return [hit["accession"] for hit in found["hits"]]


def value_of(attribute: dict):
    """An attribute's value: the address from its qualifiers (URL or ontology term), or its text."""
    qualifiers = {}
    for qualifier in attribute.get("valqual") or []:
        if present(qualifier.get("value")):
            qualifiers[qualifier.get("name")] = qualifier["value"]
    if "URL" in qualifiers:
        return web_link(qualifiers["URL"])
    # A term identifier is a prefix and a code (NCBITaxon_9606, OBI:0001271); others are kept as text.
    found = re.fullmatch(r"([A-Za-z]+)[_:](\w+)", qualifiers.get("TermId", ""))
    if found:
        prefix, code = found.groups()
        return link(ONTOLOGIES.get(prefix, "http://purl.obolibrary.org/obo/") + prefix + "_" + code)
    return attribute["value"]


def sections(section: dict) -> list[dict]:
    """The sections below a section, at any depth; a table of sections is a list of them."""
    found = []
    for part in section.get("subsections") or []:
        for each in part if isinstance(part, list) else [part]:
            found.append(each)
            found.extend(sections(each))
    return found


def given(section: dict) -> dict:
    """The attributes of a section that have a value, by name."""
    found = {}
    for attribute in section.get("attributes") or []:
        if present(attribute.get("value")):
            found[attribute.get("name")] = attribute["value"]
    return found


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    others = {}
    for key, content in contents.items():
        if key == "biostudies":
            continue
        study = json.loads(content)
        section = study.get("section") or {}
        row = {"@id": "data/" + key, "@type": "Dataset", "isBasedOn": link(STUDIES + key)}
        for attribute in (study.get("attributes") or []) + (section.get("attributes") or []):
            name = attribute.get("name")
            if not present(attribute.get("value")):
                continue
            if name == "Title":
                row["name"] = attribute["value"]
            elif name == "Description":
                row["description"] = attribute["value"]
            elif name == "ReleaseDate":
                row["datePublished"] = {"@value": attribute["value"], "@type": DATE}
            elif name == "DOI":
                row["sameAs"] = link("https://doi.org/" + attribute["value"])
                row["identifier"] = link("https://doi.org/" + attribute["value"])
            elif name == "Regulatory Question":
                # The code names the question; the address next to it is sometimes the case study's.
                code = attribute["value"]
                row.setdefault("regulatoryQuestion", []).append(link(QUESTIONS[code]) if code in QUESTIONS else value_of(attribute))
            elif name == "Case study":
                row.setdefault("isPartOf", []).append(value_of(attribute))
            elif name == "Process Flow Step":
                row.setdefault("processFlowStep", []).append(value_of(attribute))
            elif name == "Organism":
                row.setdefault("about", []).append(value_of(attribute))
            elif name == "License":
                stated = value_of(attribute)
                row["license"] = licence(stated["@id"] if isinstance(stated, dict) else stated)
            elif name == "Bioassay":
                found = value_of(attribute)
                # An assay that links to a method's page is that method.
                if isinstance(found, dict) and found["@id"].startswith("methods/"):
                    row.setdefault("measurementMethod", []).append(found)
                else:
                    row.setdefault("measurementTechnique", []).append(found)
        organisations = {}
        for part in sections(section):
            values = given(part)
            if str(part.get("type")).lower() in ("organisation", "organization") and present(values.get("Name")):
                organisation = "organizations/" + slug(values["Name"])
                others.setdefault(organisation, {"@id": organisation, "@type": "Organization", "name": values["Name"]})
                if present(values.get("RORID")):
                    others[organisation]["sameAs"] = web_link(values["RORID"])
                organisations[part.get("accno")] = organisation
        for part in sections(section):
            values = given(part)
            if str(part.get("type")).lower() == "author" and present(values.get("Name")):
                person = "people/" + slug(values["Name"])
                found = others.setdefault(person, {"@id": person, "@type": "Person", "name": values["Name"]})
                if present(values.get("E-mail")):
                    found["email"] = values["E-mail"]
                if present(values.get("ORCID")):
                    found["sameAs"] = link("https://orcid.org/" + values["ORCID"])
                if values.get("affiliation") in organisations:
                    found["affiliation"] = link(organisations[values["affiliation"]])
                row.setdefault("creator", []).append(link(person))
            elif str(part.get("type")).lower() == "publication" and present(values.get("DOI")):
                cited = publication(values["DOI"])
                if cited:
                    others.setdefault(cited["@id"], cited)
                    row.setdefault("citation", []).append(link(cited["@id"]))
        rows.append(row)
    return rows + list(others.values())
