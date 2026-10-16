"""Parser of ui-casestudy-config (a workaround, see linkeddata/parsers). Its RO-Crate describes the case
studies; each one's content file holds its pages level by level: the case study with its questions
(step1Contents), each question's page with its process flow steps (step2Contents), and the steps and their
parts below (step3Contents on). Each page has a title, a summary, a text in sections, and items: the pages
one level down, under its address, and the tools, methods and data it uses, linked by their platform id (or
kept as a label without one)."""

import json
import re

from linkeddata.parsers import link, marked, present, slug, term, web_link

# The item kinds that are pages one level down.
PAGES = {"process-flow-step", "workflow step", "workflow-step", "workflow substep"}
# Some tags have typographic quotes around their attribute values.
TAG = re.compile(r"<[a-zA-Z][^>]*>")
STRAIGHT = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})


def straight(tag) -> str:
    return tag.group(0).translate(STRAIGHT)


def html(value):
    """An HTML text with straight quotes in its tags, typed as HTML when it has tags."""
    return marked(TAG.sub(straight, str(value)))


def text(row: dict, content) -> None:
    """A page's text: in HTML, or in sections, each with a heading and an HTML text."""
    if isinstance(content, str) and present(content):
        row["content"] = html(content)
    elif isinstance(content, list):
        for position, section in enumerate(content, start=1):
            if isinstance(section, dict):
                found = {"@type": "Section", "position": position, "title": section.get("section")}
                if present(section.get("description")):
                    found["text"] = html(section["description"])
                row.setdefault("sections", []).append(found)


def item_link(item: dict) -> dict | None:
    """The platform page of the tool, method or dataset an item names by its id."""
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


def step(levels: list[dict], depth: int, path: list[str], item: dict, address: str, position: int, made: set) -> list[dict]:
    """The page an item leads to, at *path* of the levels, and the pages below it."""
    node = at(levels, depth, path)
    row = {"@id": address, "@type": "Workflow", "title": node.get("navTitle") or item.get("label"), "position": position}
    if present(item.get("state")):
        row["status"] = item["state"]
    if present(item.get("glossaryUrl")):
        row["about"] = web_link(item["glossaryUrl"])
    return [row] + fill(row, node, levels, depth, path, made)


def fill(row: dict, node: dict, levels: list[dict], depth: int, path: list[str], made: set) -> list[dict]:
    """A page's summary, text and items from its node: the pages one level down, under its address, and the
    tools and data it lists. The rows of the pages below are given back. A page that two items lead to is
    made once (*made*), with the first one's title and position."""
    if present(node.get("navDescription")):
        row["summary"] = node["navDescription"]
    text(row, node.get("content"))
    rows = []
    for entry in (node.get("steps") or []) + (node.get("tools") or []):
        if entry.get("type") in PAGES and present(entry.get("value")):
            child = f"{row['@id']}/{slug(entry['value'])}"
            row.setdefault("steps", []).append(link(child))
            if child not in made:
                made.add(child)
                rows.extend(step(levels, depth + 1, path + [entry["value"]], entry, child, len(row["steps"]), made))
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
                row[field] = html(given)
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
        made = set()
        for question in first.get("questions") or []:
            if question.get("type") != "regulatory-question" or not present(question.get("value")):
                continue
            here = f"{address}/{question['value']}"
            row.setdefault("questions", []).append(link(here))
            found = {"@id": here, "@type": "Question", "label": question.get("label"), "position": len(row["questions"])}
            if present(question.get("description")):
                found["text"] = html(question["description"])
            node = at(levels, 0, [question["value"]])
            if present(node.get("navTitle")):
                found["headline"] = node["navTitle"]
            rows.append(found)
            rows.extend(fill(found, node, levels, 0, [question["value"]], made))
        rows.append(row)
    return rows
