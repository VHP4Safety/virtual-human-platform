"""Parser of the case studies' content files of ui-casestudy-config (a workaround, see
linkeddata/parsers): the regulatory questions of each case study, at the address of their page."""

import json


def parse(files: dict[str, bytes]) -> list[dict]:
    rows = []
    for case, content in files.items():
        questions = (json.loads(content).get("step1Contents") or {}).get("questions") or []
        for question in questions:
            if question.get("type") != "regulatory-question" or not question.get("value"):
                continue
            row = {
                "@id": f"casestudies/{case}/{question['value']}",
                "@type": "Question",
                "label": f"{case.capitalize()}, {question.get('label') or question['value']}",
            }
            if question.get("description"):
                row["text"] = question["description"]
            rows.append(row)
    return rows
