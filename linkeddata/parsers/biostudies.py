"""Parser of the BioStudies collection VHP4Safety (a workaround, see linkeddata/parsers). The search of the
collection lists its studies, and the file of each study (api/v1/studies/<accession>) describes it in
sections of attributes, whose qualifiers (valqual) give the address of a value or its ontology term. Terms
given by their identifier (NCBITaxon_9606) are put at their address, and are rows of terms, with the text
of the attribute as their label and their ontology as their vocabulary; the authors and organisations of a
study are the rows of people and organisations it links to."""

import json
import re

from linkeddata.parsers import QUESTIONS, link, present, publication, slug, web_link

STUDIES = "https://www.ebi.ac.uk/biostudies/studies/"
PLATFORM = "https://platform.vhp4safety.nl/"
DATE = "http://www.w3.org/2001/XMLSchema#date"
# Ontologies whose terms are not at purl.obolibrary.org.
ONTOLOGIES = {"BAO": "http://www.bioassayontology.org/bao#"}


def keys(index: bytes) -> list[str]:
    """The accessions of the studies that the search lists, which gives one page of them."""
    found = json.loads(index)
    if found.get("totalHits", 0) > len(found.get("hits", [])):
        raise ValueError("the collection has more studies than one page of its search")
    return [hit["accession"] for hit in found["hits"]]


def value_of(attribute: dict, others: dict):
    """An attribute's value: the address its qualifiers give (its URL, or its ontology term, which is noted in
    *others* with its label and its ontology), or its text."""
    qualifiers = {}
    for qualifier in attribute.get("valqual") or []:
        if present(qualifier.get("value")):
            qualifiers[qualifier.get("name")] = qualifier["value"]
    if "URL" in qualifiers:
        return web_link(qualifiers["URL"])
    # A term identifier is an ontology's prefix and a code (NCBITaxon_9606, OBI:0001271); others are kept as text.
    found = re.fullmatch(r"([A-Za-z]+)[_:](\w+)", qualifiers.get("TermId", ""))
    if found:
        prefix, code = found.groups()
        namespace = ONTOLOGIES.get(prefix, "http://purl.obolibrary.org/obo/") + prefix + "_"
        vocabulary = "vocabularies/" + slug(prefix)
        others.setdefault(vocabulary, {"@id": vocabulary, "@type": "Vocabulary", "name": qualifiers.get("Ontology") or prefix, "namespace": link(namespace)})
        others.setdefault(namespace + code, {"@id": namespace + code, "@type": "Term", "label": attribute["value"], "code": prefix + "_" + code, "vocabulary": link(vocabulary)})
        return link(namespace + code)
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
        row = {"@id": "data/" + key, "@type": "Dataset", "page": link(STUDIES + key)}
        for attribute in (study.get("attributes") or []) + (section.get("attributes") or []):
            name = attribute.get("name")
            if not present(attribute.get("value")):
                continue
            if name == "Title":
                row["title"] = attribute["value"]
            elif name == "Description":
                row["description"] = attribute["value"]
            elif name == "ReleaseDate":
                row["published"] = {"@value": attribute["value"], "@type": DATE}
            elif name == "DOI":
                row["doi"] = link("https://doi.org/" + attribute["value"])
            elif name == "Regulatory Question":
                # The question's code names it; the address next to it is sometimes that of its case study.
                code = attribute["value"]
                row.setdefault("questions", []).append(link(QUESTIONS[code]) if code in QUESTIONS else value_of(attribute, others))
            elif name == "Case study":
                row.setdefault("cases", []).append(value_of(attribute, others))
            elif name == "Process Flow Step":
                row.setdefault("steps", []).append(value_of(attribute, others))
            elif name == "Organism":
                row.setdefault("topics", []).append(value_of(attribute, others))
            elif name == "License":
                row["license"] = value_of(attribute, others)
            elif name == "Bioassay":
                found = value_of(attribute, others)
                # An assay is a method of the platform when it links to the method's page.
                if isinstance(found, dict) and found["@id"].startswith(PLATFORM + "methods/"):
                    row.setdefault("methods", []).append(link(found["@id"].removeprefix(PLATFORM)))
                else:
                    row.setdefault("assays", []).append(found)
        organisations = {}
        for part in sections(section):
            values = given(part)
            if str(part.get("type")).lower() in ("organisation", "organization") and present(values.get("Name")):
                organisation = "organizations/" + slug(values["Name"])
                others.setdefault(organisation, {"@id": organisation, "@type": "Organization", "name": values["Name"]})
                if present(values.get("RORID")):
                    others[organisation]["same_as"] = web_link(values["RORID"])
                organisations[part.get("accno")] = organisation
        for part in sections(section):
            values = given(part)
            if str(part.get("type")).lower() == "author" and present(values.get("Name")):
                person = "people/" + slug(values["Name"])
                found = others.setdefault(person, {"@id": person, "@type": "Person", "name": values["Name"]})
                if present(values.get("E-mail")):
                    found["email"] = values["E-mail"]
                if present(values.get("ORCID")):
                    found["same_as"] = link("https://orcid.org/" + values["ORCID"])
                if values.get("affiliation") in organisations:
                    found["affiliation"] = link(organisations[values["affiliation"]])
                row.setdefault("creators", []).append(link(person))
            elif str(part.get("type")).lower() == "publication" and present(values.get("DOI")):
                cited = publication(values["DOI"])
                if cited:
                    others.setdefault(cited["@id"], cited)
                    row.setdefault("references", []).append(link(cited["@id"]))
        rows.append(row)
    return rows + list(others.values())
