"""Parser of the case studies of ui-casestudy-config."""

import json
import re
from html import unescape

from linkeddata.parsers import UPSTREAM, link, marked, present, slug, term, web_link

# The item kinds that are pages one level down.
PAGES = {"process-flow-step", "workflow step", "workflow-step", "workflow substep"}
# Some tags have typographic quotes around their attribute values.
TAG = re.compile(r"<[a-zA-Z][^>]*>")
STRAIGHT = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})
# The inputs and outputs of a page are listed in a separate section, as <li><strong>Input:</strong> ...
PARAMETERS = re.compile(r"<strong>\s*(Input|Output)\s*:?\s*</strong>(.*?)(?=</?li|</ul>|$)", re.S | re.I)
PLACEHOLDER = re.compile(r"plac\w*holder", re.I)
# A link to a dataset page of the platform, such as <a href="https://platform.vhp4safety.nl/data/20306850">.
DATASET = re.compile(rf'href="(?:{re.escape(UPSTREAM)}|/)data/([^"/?#]+)"')


def straight(tag) -> str:
    return tag.group(0).translate(STRAIGHT)


def html(value):
    """Return an HTML text with straight quotes in its tags."""
    return marked(TAG.sub(straight, str(value)))


def parameters(row: dict, description) -> None:
    """Add the inputs and outputs of a section to the row of a page."""
    for kind, given in PARAMETERS.findall(TAG.sub(straight, str(description or ""))):
        field = "bioschemas:input" if kind.lower() == "input" else "bioschemas:output"
        for dataset in DATASET.findall(given):
            row.setdefault(field, []).append(link(f"data/{dataset}"))
        name = " ".join(unescape(re.sub(r"<[^>]+>", " ", given)).split())
        if present(name) and not PLACEHOLDER.search(name):
            parameter = {"@type": "bioschemas:FormalParameter", "name": name}
            if TAG.search(given):
                parameter["description"] = html(given.strip())
            row.setdefault(field, []).append(parameter)


def text(row: dict, content) -> None:
    """Set the text or the sections of the row of a page."""
    if isinstance(content, str) and present(content):
        row["text"] = html(content)
    elif isinstance(content, list):
        for position, section in enumerate(content, start=1):
            if isinstance(section, dict) and str(section.get("section") or "").strip().lower() == "input and resulting output":
                parameters(row, section.get("description"))
            elif isinstance(section, dict):
                found = {"@type": "WebPageElement", "position": position, "name": section.get("section")}
                if present(section.get("description")):
                    found["text"] = html(section["description"])
                row.setdefault("hasPart", []).append(found)


def item_link(item: dict) -> dict | None:
    """Return the platform page of the tool, method or dataset of an item, or None."""
    if not present(item.get("id")):
        return None
    route = "data" if item.get("type") == "data" else item.get("route") or "tools"
    return link(f"{route}/{item['id']}")


def at(levels: list[dict], depth: int, path: list[str]) -> dict:
    """Return the node of a page at path in the levels of the content."""
    node = levels[depth] if depth < len(levels) else {}
    for key in path:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}


def key_of(below: dict, item: dict):
    """Return the key of the page linked from an item."""
    for given in (item.get("value"), item.get("label")):
        if present(given) and isinstance(below.get(given), dict):
            return given
    return item.get("value")


def step(levels: list[dict], depth: int, path: list[str], item: dict, address: str, position: int, made: set) -> list[dict]:
    """Return the rows of the page linked from an item and of the pages below it."""
    node = at(levels, depth, path)
    row = {"@id": address, "@type": "HowTo", "name": item.get("label") or node.get("navTitle"), "position": position}
    # A disabled page has no content yet: in schema.org, its status in the lifecycle of the work is Incomplete.
    if present(item.get("state")):
        row["creativeWorkStatus"] = "Incomplete" if item["state"] == "disabled" else item["state"]
    if present(item.get("description")):
        row["disambiguatingDescription"] = item["description"]
    if present(item.get("glossaryUrl")):
        row["additionalType"] = web_link(item["glossaryUrl"])
    return [row] + fill(row, node, levels, depth, path, made)


def fill(row: dict, node: dict, levels: list[dict], depth: int, path: list[str], made: set) -> list[dict]:
    """Return the rows of the pages below a page, and fill in the row of the page."""
    if present(node.get("navTitle")) and node["navTitle"] != row.get("name"):
        row["headline"] = node["navTitle"]
    if present(node.get("navDescription")):
        row["description"] = node["navDescription"]
    text(row, node.get("content"))
    below = at(levels, depth + 1, path)
    rows = []
    for entry in (node.get("steps") or []) + (node.get("tools") or []):
        found = key_of(below, entry)
        if entry.get("type") in PAGES and present(found):
            child = f"{row['@id']}/{slug(found)}"
            row.setdefault("step", []).append(link(child))
            if child not in made:
                made.add(child)
                rows.extend(step(levels, depth + 1, path + [found], entry, child, len(row["step"]), made))
            continue
        used = item_link(entry) or entry.get("label")
        if present(used):
            part = {"@type": "HowToSupply" if entry.get("type") == "data" else "HowToTool", "item": used,
                    "position": len(row.get("tool", [])) + len(row.get("supply", [])) + 1}
            for field, given in (("name", entry.get("label")), ("description", entry.get("description"))):
                if present(given):
                    part[field] = given
            row.setdefault("supply" if entry.get("type") == "data" else "tool", []).append(part)
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
        row = {"@id": address, "@type": "bioschemas_draft:Study", "name": about.get("name") or first.get("navTitle")}
        if present(first.get("navTitle")) and first["navTitle"] != row["name"]:
            row["headline"] = first["navTitle"]
        for field, given in (("description", about.get("description")), ("abstract", first.get("navDescription"))):
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
            row["studySubject"] = link(prefixes[prefix] + local if prefix in prefixes else condition)
        levels = []
        while f"step{len(levels) + 2}Contents" in data:
            levels.append(data[f"step{len(levels) + 2}Contents"])
        made = set()
        asked = 0
        for question in first.get("questions") or []:
            if question.get("type") != "regulatory-question" or not present(question.get("value")):
                continue
            here = f"{address}/{question['value']}"
            asked += 1
            row.setdefault("hasPart", []).append(link(here))
            found = {"@id": here, "@type": "HowTo", "name": question.get("label"), "position": asked}
            if present(question.get("description")):
                found["text"] = html(question["description"])
            rows.append(found)
            rows.extend(fill(found, at(levels, 0, [question["value"]]), levels, 0, [question["value"]], made))
        rows.append(row)
    return rows
