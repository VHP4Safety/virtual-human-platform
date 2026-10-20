"""Parser of the BioStudies collection VHP4Safety, a workaround (see linkeddata/parsers).

Source: the search results, and the file of each study (api/v1/studies/<accession>), read with the BioStudies
client (biostudies_search).

- Values: the attributes of the sections of a study. Read the address or the ontology term of a value from the
  qualifiers of its attribute (valqual).
- Terms: link identifiers such as NCBITaxon_9606 at their address, with labels from the Ontology Lookup Service
  (sources/ols.yaml).
- Authors and organisations: separate rows. The authors are kept in their order, as a list.
- Funding: a grant row for each funding section (agency and grant number).
- Files: the files of the study and its sections, at their addresses on the BioStudies FTP site, in their order.
- Experimental design: a LabProtocol part with the biological models (BioSample), the chemicals (ChemicalSubstance,
  in their order) and the other sections, such as exposures and endpoint readouts (LabProtocol parts, in their order,
  with their sections below). Every attribute is kept as a value (PropertyValue) with its BioStudies name as
  identifier type, its ontology term and its page. Bioassays and AOP events anywhere in the study are also linked
  from the dataset as assays and topics."""

import json
import re

import requests

from linkeddata.parsers import QUESTIONS, licence, link, present, publication, slug, web_link
from linkeddata.parsers.biostudies_search import BioStudiesExtractor
from linkeddata.parsers.zenodo import size

STUDIES = "https://www.ebi.ac.uk/biostudies/studies/"
DATE = "http://www.w3.org/2001/XMLSchema#date"
# Ontologies whose terms are not at purl.obolibrary.org.
ONTOLOGIES = {"BAO": "http://www.bioassayontology.org/bao#", "ENM": "http://purl.enanomapper.org/onto/"}
COLLECTION = "VHP4Safety"
# Sections that are read as authors, organisations, funding and publications, not as parts of the design.
SEPARATE = {"author", "organisation", "organization", "funding", "publication"}


def fetched(spec: dict) -> dict[str, bytes]:
    """Return the studies of the collection, read with the BioStudies client: the search results, and the file of
    each study by its accession."""
    client = BioStudiesExtractor(collection=COLLECTION)
    listing = client.list_studies(page_size=100)
    if listing.get("error"):
        raise requests.RequestException(listing["error"])
    if listing["total"] > len(listing["hits"]):
        raise ValueError("more studies than one search page")
    contents = {spec["name"]: json.dumps(listing).encode()}
    for hit in listing["hits"]:
        study = client.get_study_metadata(hit["accession"])
        if study.get("error"):
            print(f"{spec['name']}: {hit['accession']} not fetched ({study['error']})")
            continue
        contents[hit["accession"]] = json.dumps(study["raw_data"]).encode()
    return contents


def qualifiers(attribute: dict) -> dict:
    """Return the qualifiers of an attribute that have a value, by name (URL, Ontology, TermId)."""
    found = {}
    for qualifier in attribute.get("valqual") or []:
        if present(qualifier.get("value")):
            found[qualifier.get("name")] = qualifier["value"]
    return found


def page_of(attribute: dict):
    """Return the page of an attribute (its URL qualifier) as a link, or None."""
    given = qualifiers(attribute).get("URL")
    found = web_link(given) if given else None
    return found if isinstance(found, dict) else None


def term_of(attribute: dict):
    """Return the ontology term of an attribute (its TermId qualifier) as a link, or None. A term identifier is a
    prefix and a code (NCBITaxon_9606, OBI:0001271)."""
    found = re.fullmatch(r"([A-Za-z]+)[_:](\w+)", qualifiers(attribute).get("TermId", ""))
    if not found:
        return None
    prefix, code = found.groups()
    return link(ONTOLOGIES.get(prefix, "http://purl.obolibrary.org/obo/") + prefix + "_" + code)


def value_of(attribute: dict):
    """Return the value of an attribute: its page, else its ontology term, else its text."""
    return page_of(attribute) or term_of(attribute) or attribute["value"]


def children(section: dict) -> list[dict]:
    """Return the sections just below a section, in their order. Read a table of sections as a list of sections."""
    found = []
    for part in section.get("subsections") or []:
        found.extend(part if isinstance(part, list) else [part])
    return found


def sections(section: dict) -> list[dict]:
    """Return the sections below a section, at any depth."""
    found = []
    for each in children(section):
        found.append(each)
        found.extend(sections(each))
    return found


def value(attribute: dict) -> dict:
    """Return an attribute as a value (PropertyValue): its name as identifier type, its text, and from its
    qualifiers its page (URL), its unit, its ontology term (valueReference) and its other qualifiers, such as the
    concentration of a positive control (valueReference, each a PropertyValue)."""
    found = {"@type": "PropertyValue", "propertyID": attribute.get("name"), "value": attribute["value"]}
    if page_of(attribute):
        found["url"] = page_of(attribute)
    if term_of(attribute):
        found["valueReference"] = [term_of(attribute)]
    # A page or a term that is no address (such as "[DRAFT] method URL") is kept as a qualifier, as given.
    for qualifier in attribute.get("valqual") or []:
        name, given = qualifier.get("name"), qualifier.get("value")
        if not present(given) or (name == "URL" and page_of(attribute)) or (name in ("Ontology", "TermId") and term_of(attribute)):
            continue
        if name == "Unit":
            found["unitText"] = given
        else:
            found.setdefault("valueReference", []).append({"@type": "PropertyValue", "propertyID": name, "value": given})
    return found


def values_of(section: dict) -> list[dict]:
    """Return the attributes of a section that have a value, as values, each with its place (position)."""
    found = []
    for attribute in section.get("attributes") or []:
        if present(attribute.get("value")):
            found.append({**value(attribute), "position": len(found) + 1})
    return found


def protocol(section: dict) -> dict:
    """Return a section as a LabProtocol part: its type as name and section, its attributes as values, and the
    sections below it, in their order."""
    found = {"@type": "bioschemas_draft:LabProtocol", "name": section.get("type"), "additionalType": section.get("type"),
             "bioschemas_draft:additionalProperty": values_of(section)}
    below = [protocol(part) for part in children(section)]
    if below:
        found["hasPart"] = {"@list": below}
    return found


def sample(section: dict) -> dict:
    """Return a biological model section as a BioSample: the cell line as name, the RRID as identifier, the
    description, every attribute as a value, and the sections below it, such as the cell line preparation."""
    named = given(section)
    found = {"@type": "bioschemas:BioSample", "name": named.get("Cell line") or section.get("type"),
             "bioschemas:additionalProperty": values_of(section)}
    if present(named.get("Description")):
        found["description"] = named["Description"]
    found["identifier"] = [item for item in values_of(section) if item["propertyID"] == "RRID"]
    found["subjectOf"] = [protocol(part) for part in children(section)]
    return found


def chemical(section: dict) -> dict:
    """Return a chemical section as a ChemicalSubstance: the chemical as name, the other attributes as identifiers,
    and the compound page of its CompoundCloud identifier."""
    named = given(section)
    found = {"@type": "ChemicalSubstance", "name": named.get("Chemical") or section.get("type"),
             "identifier": [item for item in values_of(section) if item["propertyID"] != "Chemical"]}
    if present(named.get("CompoundCloudID")):
        found["sameAs"] = link("compound/" + named["CompoundCloudID"])
    return found


def files_of(key: str, section: dict) -> list[dict]:
    """Return the files of a study and its sections at their download addresses, in their order, each once."""
    client = BioStudiesExtractor()
    found = {}

    def walk(part: dict) -> None:
        for given in part.get("files") or []:
            for each in given if isinstance(given, list) else [given]:
                path = each.get("path") or each.get("name") or each.get("filename")
                address = client.build_biostudies_https_file_url(key, path) if path else None
                if address and path not in found:
                    found[path] = {"@type": "DataDownload", "name": path, "contentUrl": link(address), "position": len(found) + 1}
                    if isinstance(each.get("size"), int):
                        found[path]["contentSize"] = size(each["size"])
        for below in children(part):
            walk(below)

    walk(section)
    return list(found.values())


def design(section: dict, attributes: list[dict]) -> dict:
    """Return the experimental design of a study as a LabProtocol part, with the attributes of the study as its
    values."""
    samples, chemicals, parts = [], [], []
    for part in children(section):
        kind = str(part.get("type")).lower()
        if kind in SEPARATE:
            continue
        if kind == "biological model information":
            samples.append({**sample(part), "position": len(samples) + 1})
        elif kind == "chemical information":
            chemicals.append(chemical(part))
        else:
            parts.append(protocol(part))
    found = {"@type": "bioschemas_draft:LabProtocol", "name": "Experimental design",
             "bioschemas_draft:additionalProperty": values_of({"attributes": attributes})}
    if samples:
        found["bioschemas_draft:bioSample"] = samples
    if chemicals:
        found["bioschemas_draft:reagent"] = {"@list": chemicals}
    if parts:
        found["hasPart"] = {"@list": parts}
    return found


def given(section: dict) -> dict:
    """Return the attributes of a section that have a value, by name."""
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
                # The question is identified by the code; the address next to the code is sometimes that of the case study.
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
                # An assay with a link to the page of a method is read as that method; its term is the assay.
                page = page_of(attribute)
                if page and page["@id"].startswith("methods/"):
                    row.setdefault("measurementMethod", []).append(page)
                if term_of(attribute) or not page:
                    row.setdefault("measurementTechnique", []).append(term_of(attribute) or value_of(attribute))
            elif name in ("Organ", "Tissue", "AOP", "AOP event") and isinstance(value_of(attribute), dict):
                row.setdefault("about", []).append(value_of(attribute))
        organisations = {}
        authors = []
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
                authors.append(link(person))
            elif str(part.get("type")).lower() == "publication" and present(values.get("DOI")):
                cited = publication(values["DOI"])
                if cited:
                    others.setdefault(cited["@id"], cited)
                    row.setdefault("citation", []).append(link(cited["@id"]))
            elif str(part.get("type")).lower() == "funding" and present(values.get("Grant_id")):
                grant = "grants/" + slug(values["Grant_id"])
                found = others.setdefault(grant, {"@id": grant, "@type": "MonetaryGrant", "name": values["Grant_id"], "identifier": values["Grant_id"]})
                if present(values.get("Agency")):
                    agency = "organizations/" + slug(values["Agency"])
                    others.setdefault(agency, {"@id": agency, "@type": "Organization", "name": values["Agency"]})
                    found["funder"] = link(agency)
                row.setdefault("funding", []).append(link(grant))
            # Bioassays and AOP events of any section are also the assays and the topics of the dataset.
            for attribute in part.get("attributes") or []:
                if not present(attribute.get("value")):
                    continue
                if attribute.get("name") == "Bioassay" and term_of(attribute) and term_of(attribute) not in row.get("measurementTechnique", []):
                    row.setdefault("measurementTechnique", []).append(term_of(attribute))
                elif attribute.get("name") == "AOP event" and isinstance(value_of(attribute), dict) and value_of(attribute) not in row.get("about", []):
                    row.setdefault("about", []).append(value_of(attribute))
        if authors:
            row["creator"] = {"@list": authors}
        row["hasPart"] = design(section, (study.get("attributes") or []) + (section.get("attributes") or []))
        if files_of(key, section):
            row["distribution"] = files_of(key, section)
        rows.append(row)
    return rows + list(others.values())
