"""Parser of the cloud catalogue's service_index.json (a workaround, see linkeddata/parsers)."""

import json

from linkeddata.parsers import link, present, web_link

# The catalogue marks the regulatory questions of a tool with yes/no flags.
QUESTIONS = {
    "reg_q_1a": "casestudies/kidney/Q1",
    "reg_q_1b": "casestudies/kidney/Q2",
    "reg_q_2a": "casestudies/parkinson/Q1",
    "reg_q_2b": "casestudies/parkinson/Q2",
    "reg_q_3a": "casestudies/thyroid/Q1",
    "reg_q_3b": "casestudies/thyroid/Q2",
}
# The catalogue gives this logo to tools that have none.
PLACEHOLDER_LOGO = "https://github.com/VHP4Safety/ui-design/blob/main/static/images/logo.png"
LOGOS = "https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/"


def parse(content: bytes) -> list[dict]:
    rows = []
    for entry in json.loads(content).values():
        row = {"@id": "tools/" + entry["id"], "@type": "Tool", "service": entry["service"]}
        if present(entry.get("description")):
            row["description"] = entry["description"]
        if present(entry.get("main_url")):
            row["main_url"] = web_link(entry["main_url"])
        logo = entry.get("png_file_name")
        if present(logo) and logo != PLACEHOLDER_LOGO:
            row["logo"] = link(LOGOS + logo)
        if present(entry.get("stage")):
            row["stage"] = web_link(entry["stage"])
        questions = []
        for flag, question in QUESTIONS.items():
            if str(entry.get(flag)).lower() == "true":
                questions.append(link(question))
        if questions:
            row["questions"] = questions
        rows.append(row)
    return rows
