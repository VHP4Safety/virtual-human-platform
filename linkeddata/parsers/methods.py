"""Parser of the cloud catalogue's methods_index.json (a workaround, see linkeddata/parsers)."""

import json

from linkeddata.parsers import link, present

GLOSSARY = "https://vhp4safety.github.io/glossary#"
# The catalogue names the safety assessment step of a method in free text.
STEPS = {
    "Chemical characteristics and Hazard Identification": GLOSSARY + "VHP0000153",
    "Exposure": GLOSSARY + "VHP0000154",
    "Toxicokinetics": GLOSSARY + "VHP0000155",
    "Kinetics": GLOSSARY + "VHP0000155",
    "Toxicodynamics": GLOSSARY + "VHP0000156",
    "Adverse Outcome": GLOSSARY + "VHP0000158",
}
KEY_EVENTS = "relevant_aop_wiki_key_event(s)_to_the_assay_content"
AOPS = "relevant_aop_wiki_adverse_outcome_pathway(s)_to_the_assay_content"


def parts(value) -> list[str]:
    """The values of a text that lists several, separated by commas."""
    if not present(value):
        return []
    found = []
    for part in str(value).split(","):
        if present(part):
            found.append(part.strip())
    return found


def aop_wiki_links(value, prefix: str, namespace: str) -> list:
    """Links for AOP-Wiki numbers written as "KE177" or "AOP464"; other text is passed on."""
    found = []
    for part in parts(value):
        number = part.removeprefix(prefix).strip()
        if number.isdigit():
            found.append(link(namespace + number))
        else:
            found.append(part)
    return found


def parse(content: bytes) -> list[dict]:
    rows = []
    for entry in json.loads(content).values():
        row = {"@id": "methods/" + entry["id"], "@type": "Method", "method": entry["method"]}
        if present(entry.get("method_description_content")):
            row["description"] = entry["method_description_content"]
        if present(entry.get("citation_content")):
            row["citation"] = entry["citation_content"]
        key_events = aop_wiki_links(entry.get(KEY_EVENTS), "KE", "https://identifiers.org/aop.events/")
        if key_events:
            row["key_events"] = key_events
        aops = aop_wiki_links(entry.get(AOPS), "AOP", "https://identifiers.org/aop/")
        if aops:
            row["aops"] = aops
        stages = []
        for stage in parts(entry.get("vhp4safety_workflow_stage_content")):
            if stage in STEPS:
                stages.append(link(STEPS[stage]))
            else:
                stages.append(stage)
        if stages:
            row["stages"] = stages
        rows.append(row)
    return rows
