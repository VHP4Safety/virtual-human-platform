"""Parser of the tutorials of the VHP4Safety documentation."""

import json
import re
import unicodedata

from linkeddata.parsers import link, present, slug

SITE = "https://docs.vhp4safety.nl/en/latest/"
TUTORIAL = re.compile(r"tutorials/([^/]+)/([^/]+)\.(md|rst)")
# Folders without tutorials: the page of the videos, which is read from the source of the videos.
LEFT_OUT = {"peertube"}
# The sections of the documentation format (tutorials/documentation_format.md), in order.
FORMAT = ["Introduction", "Accessing the Tool", "Tool Functionalities", "Interpreting the Output", "Summary"]
FORMAT_PAGE = SITE + "tutorials/documentation_format.html"
DATE = "http://www.w3.org/2001/XMLSchema#date"
# The files next to a tutorial that are stored as its parts.
FILES = (".ipynb", ".r", ".R", ".py", ".Rmd")
# An underline of a reStructuredText heading.
UNDERLINE = re.compile(r"([=\-~^\"'`#*+])\1{2,}\s*")


def tutorials(tree: dict) -> dict[str, str]:
    """Return the source file of each tutorial in the tree, by folder name."""
    found = {}
    for entry in tree["tree"]:
        written = TUTORIAL.fullmatch(entry["path"])
        if written is None or written.group(1) in LEFT_OUT:
            continue
        if written.group(1) in found and written.group(3) != "md":
            continue
        found[written.group(1)] = entry["path"]
    return found


def documents(contents: dict, addresses: dict) -> dict[str, str]:
    """Return the source of each tutorial and its latest change, by path."""
    found = {"repository": addresses["repository"]}
    for path in tutorials(json.loads(contents["docs"])).values():
        found[path] = addresses["source"] + path
        found[path + "#changes"] = addresses["changes"] + path + "&per_page=1"
    return found


def anchor(heading: str) -> str:
    """Return the identifier of a heading, as made by docutils."""
    plain = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"[^a-z0-9]+", "-", plain)
    return re.sub(r"^[-0-9]+|-+$", "", plain)


def plain(text: str) -> str:
    """Return a Markdown text as plain text."""
    text = re.sub(r"<sup>.*?</sup>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]+", "", text)
    return " ".join(text.split())


def headings(text: str, rst: bool) -> list[tuple[int, str]]:
    """Return the headings of a source by level, outside code blocks."""
    found = []
    fenced = False
    lines = text.splitlines()
    levels = []
    for number, line in enumerate(lines):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if not rst:
            written = re.match(r"(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if written:
                found.append((len(written.group(1)), plain(written.group(2))))
            continue
        below = lines[number + 1] if number + 1 < len(lines) else ""
        underline = UNDERLINE.fullmatch(below)
        if line.strip() and underline and len(below.strip()) >= len(line.strip()):
            if underline.group(1) not in levels:
                levels.append(underline.group(1))
            found.append((levels.index(underline.group(1)) + 1, plain(line)))
    return found


def heading_at(lines: list[str], number: int, rst: bool) -> bool:
    """Return True if a line of a source is a heading, a heading underline or a rule."""
    line = lines[number]
    if UNDERLINE.fullmatch(line):
        return True
    if not rst:
        return re.match(r"#{1,6}\s", line) is not None
    below = lines[number + 1] if number + 1 < len(lines) else ""
    return bool(line.strip()) and UNDERLINE.fullmatch(below) is not None


def names(line: str) -> list[str]:
    """Return the names in an authors line."""
    text = re.sub(r"^Authors?:\s*", "", plain(line), flags=re.IGNORECASE)
    return [name.strip() for name in re.split(r",|;|\band\b", text) if name.strip()]


def opening(text: str, rst: bool) -> tuple[list[str], str]:
    """Return the authors and the first paragraph of a tutorial."""
    lines = text.splitlines()
    authors = []
    paragraph = []
    titled = False
    for number, line in enumerate(lines):
        stripped = line.strip()
        if heading_at(lines, number, rst):
            if UNDERLINE.fullmatch(stripped) and not paragraph:
                continue
            if not titled:
                titled = True
                continue
            heading = re.sub(r"^[#\s0-9.]+", "", stripped).lower()
            if paragraph or not heading.startswith("introduction"):
                break
            continue
        if not titled or not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("<", "![")):
            continue
        if not paragraph and not authors and stripped.startswith("**"):
            authors = names(stripped)
            continue
        paragraph.append(stripped)
    return authors, plain(" ".join(paragraph))


def author(name: str, others: dict) -> dict:
    """Return the link to the record of an author, and add its row to others."""
    if "team" in name.lower():
        address = "organizations/" + slug(name)
        others.setdefault(address, {"@id": address, "@type": "Organization", "name": name})
    else:
        address = "people/" + slug(name)
        others.setdefault(address, {"@id": address, "@type": "Person", "name": name})
    return link(address)


def follows(found: list[tuple[int, str]]) -> bool:
    """Return True if the sections of a tutorial follow the documentation format."""
    named = [re.sub(r"^[0-9.]+\s*", "", heading) for level, heading in found if level == 2]
    position = 0
    for heading in named:
        if position < len(FORMAT) and heading.startswith(FORMAT[position]):
            position += 1
    return position == len(FORMAT)


def parse(contents: dict[str, bytes]) -> list[dict]:
    tree = json.loads(contents["docs"])
    # Without the response for the repository, the files of the tutorials are left out, as their addresses require its branch.
    files = None
    if "repository" in contents:
        repository = json.loads(contents["repository"])
        files = "/".join([repository["html_url"], "blob", repository["default_branch"]]) + "/"
    rows = []
    others = {}
    for name, path in tutorials(tree).items():
        if path not in contents:
            continue
        rst = path.endswith(".rst")
        text = contents[path].decode("utf-8")
        found = headings(text, rst)
        authors, description = opening(text, rst)
        page = SITE + re.sub(r"\.(md|rst)$", ".html", path)
        row = {"@id": "training/" + slug(name), "@type": "LearningResource", "name": found[0][1] if found else name,
               "description": description, "url": link(page), "mentions": link("tools/" + name),
               "learningResourceType": "tutorial",
               "author": [author(given, others) for given in authors]}
        if follows(found):
            row["dct:conformsTo"] = link(FORMAT_PAGE)
        changes = json.loads(contents.get(path + "#changes", b"[]"))
        if changes:
            row["dateModified"] = {"@value": changes[0]["commit"]["committer"]["date"][:10], "@type": DATE}
        sections = []
        for level, heading in found[1:]:
            if level <= 3 and present(heading):
                sections.append({"@type": "WebPageElement", "name": heading, "url": link(page + "#" + anchor(heading)), "position": len(sections) + 1})
        row["mainEntityOfPage"] = {"@type": "WebPage", "url": link(page), "hasPart": sections}
        parts = []
        folder = path.rsplit("/", 1)[0] + "/"
        for entry in tree["tree"]:
            if files is not None and entry["path"].startswith(folder) and entry["path"].endswith(FILES):
                parts.append({"@type": "DigitalDocument", "name": entry["path"].rsplit("/", 1)[1], "url": link(files + entry["path"])})
        row["hasPart"] = parts
        rows.append(row)
    return rows + list(others.values())
