"""Parser of ui-casestudy-config (a workaround, see linkeddata/parsers). Its RO-Crate describes each case
study, and the content file of a case study holds the pages of its interface, one level after the other:
the case study with its regulatory questions (step1Contents), the page of each question with its process
flow steps (step2Contents), and the steps and their parts below (step3Contents and on). Each page has a
title, a summary, a text in sections, and a list of items: the pages one level down, at addresses under its
own, and the tools, methods and data it uses, which are linked by the id of their record on the platform
(an item without one is kept as its label)."""

import json

from linkeddata.parsers import link, present, slug, term, web_link

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


def at(levels: list[dict], depth: int, path: list[str]) -> dict:
    """The node of a page at *path* of the content's levels."""
    node = levels[depth] if depth < len(levels) else {}
    for key in path:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}


def step(levels: list[dict], depth: int, path: list[str], item: dict, address: str, position: int) -> list[dict]:
    """The page of a step that an item leads to, at *path* of the content's levels, and the pages below it."""
    node = at(levels, depth, path)
    row = {"@id": address, "@type": "Workflow", "title": node.get("navTitle") or item.get("label"), "position": position}
    if present(item.get("state")):
        row["status"] = item["state"]
    if present(item.get("glossaryUrl")):
        row["about"] = web_link(item["glossaryUrl"])
    return [row] + fill(row, node, levels, depth, path)


def fill(row: dict, node: dict, levels: list[dict], depth: int, path: list[str]) -> list[dict]:
    """The summary, text and items of a page from its node of the content: the pages one level down, at
    addresses under its own, and the tools and data it lists. Gives the rows of the pages below."""
    if present(node.get("navDescription")):
        row["summary"] = node["navDescription"]
    text(row, node.get("content"))
    rows = []
    for entry in (node.get("steps") or []) + (node.get("tools") or []):
        if entry.get("type") in PAGES and present(entry.get("value")):
            child = f"{row['@id']}/{slug(entry['value'])}"
            row.setdefault("steps", []).append(link(child))
            rows.extend(step(levels, depth + 1, path + [entry["value"]], entry, child, len(row["steps"])))
            continue
        used = item_link(entry) or entry.get("label")
        if present(used):
            row.setdefault("supplies" if entry.get("type") == "data" else "tools", []).append(used)
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
        for field, given in (("description", about.get("description")), ("intro", first.get("navDescription"))):
            if present(given):
                row[field] = given
        keywords = about.get("keywords") or []
        for keyword in keywords if isinstance(keywords, list) else str(keywords).split(","):
            if present(keyword):
                row.setdefault("keywords", []).append(term(keyword, "glossary"))
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
            row.setdefault("questions", []).append(link(here))
            found = {"@id": here, "@type": "Question", "label": question.get("label"), "position": len(row["questions"])}
            if present(question.get("description")):
                found["text"] = question["description"]
            node = at(levels, 0, [question["value"]])
            if present(node.get("navTitle")):
                found["headline"] = node["navTitle"]
            rows.append(found)
            rows.extend(fill(found, node, levels, 0, [question["value"]]))
        rows.append(row)
    return rows
