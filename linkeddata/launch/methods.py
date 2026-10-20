"""Parser of the methods of the cloud catalogue."""

import json
import re

from linkeddata.parsers import link, present, publication, slug, term, web_link

AOPS = "relevant_aop_wiki_adverse_outcome_pathway(s)_to_the_assay_content"
KEY_EVENTS = "relevant_aop_wiki_key_event(s)_to_the_assay_content"
ISSUES = "https://github.com/VHP4Safety/cloud/issues/"
# The address bases of AOP-Wiki key event (KE1825) and pathway (AOP464) codes.
AOP_WIKI = {"KE": "https://identifiers.org/aop.events/", "AOP": "https://identifiers.org/aop/"}


def parts(value) -> list[str]:
    """Return the comma-separated values of a text."""
    if not present(value):
        return []
    found = []
    for part in str(value).split(","):
        if present(part):
            found.append(part.strip())
    return found


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    others = {}
    for key, entry in json.loads(contents["methods"]).items():
        detail = dict(entry)
        if key in contents:
            detail.update(json.loads(contents[key]))
        row = {"@id": "methods/" + entry["id"], "@type": "bioschemas_draft:LabProtocol"}
        for field, given in (("name", "method"), ("description", "method_description_content"), ("alternateName", "assay_name_content"),
                             ("identifier", "catalog_number_content")):
            if present(detail.get(given)):
                row[field] = detail[given]
        if present(detail.get("data_producer_content")):
            person = "people/" + slug(detail["data_producer_content"])
            others.setdefault(person, {"@id": person, "@type": "Person", "name": str(detail["data_producer_content"]).strip()})
            row["creator"] = link(person)
        if present(detail.get("citation_content")):
            cited = publication(detail["citation_content"])
            if cited:
                others.setdefault(cited["@id"], cited)
                row["citation"] = link(cited["@id"])
            else:
                row["citation"] = detail["citation_content"]
        for field, given in (("url", "catalog_webpage_url"), ("subjectOf", "available_sop_or_protocol_url")):
            if present(detail.get(given)):
                row[field] = web_link(detail[given])
        steps = []
        for part in parts(detail.get("vhp4safety_workflow_stage_content")):
            steps.append(term(part, "glossary", "Process Flow Step"))
        if steps:
            row["processFlowStep"] = steps
        about = []
        for part in parts(detail.get("workflow_substage_content")):
            about.append(term(part, "glossary"))
        for part in parts(detail.get(KEY_EVENTS)) + parts(detail.get(AOPS)):
            code = re.fullmatch(r"(KE|AOP)\s*(\d+)", part)
            about.append(link(AOP_WIKI[code.group(1)] + code.group(2)) if code else web_link(part))
        types = []
        for given in ("type_url", "ontology_term_url", "ontology_term_content"):
            if present(detail.get(given)):
                types.append(web_link(detail[given]))
        if types:
            row["additionalType"] = types
        # The question is linked at its page's address.
        if present(detail.get("case_study_content")) and present(detail.get("regulatory_question_content")):
            row["regulatoryQuestion"] = link(f"casestudies/{detail['case_study_content']}/{detail['regulatory_question_content']}")
        if about:
            row["about"] = about
        if present(detail.get("issue_number")):
            row["isBasedOn"] = link(ISSUES + str(detail["issue_number"]))
        if present(detail.get("vendor_content")):
            vendor = "organizations/" + slug(detail["vendor_content"])
            others.setdefault(vendor, {"@id": vendor, "@type": "Organization", "name": detail["vendor_content"]})
            row["provider"] = link(vendor)
        rows.append(row)
    return rows + list(others.values())
