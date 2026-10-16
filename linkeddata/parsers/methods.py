"""Parser of the cloud catalogue's methods (a workaround, see linkeddata/parsers): methods_index.json
lists the methods, and the detail file of each method (docs/methods/<id>.json) describes it. Values
are passed on as the catalogue writes them; the checks of the import note those that do not fit."""

import json
import re

from linkeddata.parsers import link, present, publication, slug, term, web_link

AOPS = "relevant_aop_wiki_adverse_outcome_pathway(s)_to_the_assay_content"
KEY_EVENTS = "relevant_aop_wiki_key_event(s)_to_the_assay_content"
ISSUES = "https://github.com/VHP4Safety/cloud/issues/"
# The codes of AOP-Wiki's key events (KE1825) and pathways (AOP464), and the addresses that they stand for.
AOP_WIKI = {"KE": "https://identifiers.org/aop.events/", "AOP": "https://identifiers.org/aop/"}


def parts(value) -> list[str]:
    """The values of a text that lists several, separated by commas."""
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
        detail = {**entry, **(json.loads(contents[key]) if key in contents else {})}
        row = {"@id": "methods/" + entry["id"], "@type": "Method"}
        for field, given in (("method", "method"), ("description", "method_description_content"), ("assay", "assay_name_content"),
                             ("catalog_number", "catalog_number_content")):
            if present(detail.get(given)):
                row[field] = detail[given]
        if present(detail.get("data_producer_content")):
            person = "people/" + slug(detail["data_producer_content"])
            others.setdefault(person, {"@id": person, "@type": "Person", "name": str(detail["data_producer_content"]).strip()})
            row["data_producer"] = link(person)
        if present(detail.get("citation_content")):
            cited = publication(detail["citation_content"])
            if cited:
                others.setdefault(cited["@id"], cited)
                row["citation"] = link(cited["@id"])
            else:
                row["citation"] = detail["citation_content"]
        for field, given in (("url", "catalog_webpage_url"), ("sop", "available_sop_or_protocol_url")):
            if present(detail.get(given)):
                row[field] = web_link(detail[given])
        steps = []
        for part in parts(detail.get("vhp4safety_workflow_stage_content")):
            steps.append(term(part, "glossary", "Process Flow Step"))
        if steps:
            row["steps"] = steps
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
            row["types"] = types
        # A method answers the regulatory question of a case study, at the address of the question's page.
        if present(detail.get("case_study_content")) and present(detail.get("regulatory_question_content")):
            row["question"] = link(f"casestudies/{detail['case_study_content']}/{detail['regulatory_question_content']}")
        if about:
            row["about"] = about
        if present(detail.get("issue_number")):
            row["issue"] = link(ISSUES + str(detail["issue_number"]))
        if present(detail.get("vendor_content")):
            vendor = "organizations/" + slug(detail["vendor_content"])
            others.setdefault(vendor, {"@id": vendor, "@type": "Organization", "name": detail["vendor_content"]})
            row["vendor"] = link(vendor)
        rows.append(row)
    return rows + list(others.values())
