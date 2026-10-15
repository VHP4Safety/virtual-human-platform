"""Parser of ui-casestudy-config (a workaround, see linkeddata/parsers). Its RO-Crate describes each case
study, and the content file of a case study holds the pages of its interface, one level after the other:
the case study with its regulatory questions (step1Contents), the process flow steps of each question
(step2Contents), and the steps and their parts below (step3Contents and on). Each page has a title, a
summary, a text in sections, and a list of items: the pages one level down, the tools it uses, and the data
it uses."""

import json

from linkeddata.parsers import link, present, slug

# The kinds of the items of a page that are pages one level down; tools and data are not.
PAGES = {"process-flow-step", "workflow step", "workflow-step", "workflow substep"}


def text(row: dict, content) -> None:
    """The text of a page: in HTML, or in sections, each with its heading and its text in HTML."""
    if isinstance(content, str) and present(content):
        row["content"] = content
    elif isinstance(content, list):
        for position, section in enumerate(content, start=1):
            if isinstance(section, dict):
                found = {"@type": "Section", "position": position, "title": section.get("section"), "text": section.get("description")}
                row.setdefault("sections", []).append(found)


def item_link(item: dict) -> dict | None:
    """The page on the platform of a tool, a method or a dataset that an item names by its id."""
    if not present(item.get("id")):
        return None
    route = "data" if item.get("type") == "data" else item.get("route") or "tools"
    return link(f"{route}/{item['id']}")


def pages(levels: list[dict], depth: int, path: list[str], item: dict, address: str, parent: str) -> list[dict]:
    """The page that an item leads to, at *path* of the content's levels, and the pages below it."""
    node = levels[depth] if depth < len(levels) else {}
    for key in path:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    node = node if isinstance(node, dict) else {}
    row = {"@id": address, "@type": "Workflow", "parent": link(parent), "title": node.get("navTitle") or item.get("label")}
    for field, given in (("summary", node.get("navDescription")), ("status", item.get("state"))):
        if present(given):
            row[field] = given
    text(row, node.get("content"))
    if present(item.get("glossaryUrl")):
        row["about"] = link(item["glossaryUrl"])
    rows = [row]
    for entry in (node.get("steps") or []) + (node.get("tools") or []):
        if entry.get("type") in PAGES and present(entry.get("value")):
            child = f"{address}/{slug(entry['value'])}"
            row.setdefault("steps", []).append(link(child))
            rows.extend(pages(levels, depth + 1, path + [entry["value"]], entry, child, address))
            continue
        used = {"@type": "Data" if entry.get("type") == "data" else "Tool", "label": entry.get("label")}
        if present(entry.get("description")):
            used["description"] = entry["description"]
        if item_link(entry):
            used["page"] = item_link(entry)
        row.setdefault("supplies" if used["@type"] == "Data" else "tools", []).append(used)
    return rows


def parse(files: dict[str, bytes]) -> list[dict]:
    crate = json.loads(files["crate"])
    prefixes = {}
    for given in crate["@context"] if isinstance(crate["@context"], list) else [crate["@context"]]:
        if isinstance(given, dict):
            prefixes.update(given)
    described = {}
    for node in crate["@graph"]:
        if present(node.get("identifier")):
            described[node["identifier"]] = node
    rows = []
    for case, content in files.items():
        if case == "crate":
            continue
        data = json.loads(content)
        about = described.get(case, {})
        address = f"casestudies/{case}"
        first = data.get("step1Contents") or {}
        row = {"@id": address, "@type": "CaseStudy", "name": about.get("name") or first.get("navTitle")}
        for field, given in (("description", about.get("description")), ("keywords", about.get("keywords")), ("intro", first.get("navDescription"))):
            if present(given):
                row[field] = given
        text(row, first.get("content"))
        condition = (about.get("about") or {}).get("@id", "")
        prefix, _, local = condition.partition(":")
        if condition:
            row["about"] = link(prefixes[prefix] + local if prefix in prefixes else condition)
        levels = []
        while f"step{len(levels) + 2}Contents" in data:
            levels.append(data[f"step{len(levels) + 2}Contents"])
        for question in first.get("questions") or []:
            if question.get("type") != "regulatory-question" or not present(question.get("value")):
                continue
            here = f"{address}/{question['value']}"
            found = {"@id": here, "@type": "Question", "label": question.get("label"), "case": link(address)}
            if present(question.get("description")):
                found["text"] = question["description"]
            if levels and question["value"] in levels[0]:
                found["workflow"] = link(f"{here}/workflow")
                rows.extend(pages(levels, 0, [question["value"]], {}, f"{here}/workflow", here))
            rows.append(found)
        rows.append(row)
    return rows
