"""Parser of the tutorials of the VHP4Safety documentation (https://docs.vhp4safety.nl; a workaround, see
linkeddata/parsers): the repository's tree at a pinned commit gives the tutorials, tutorials/<name>/<file>.md (or
.rst), and the files beside them; each tutorial's source and latest change, and the repository, are read.
- A tutorial is a training material at training/<name>, its folder's name, which is the service identifier of
  the tool it teaches (tools/<name>), as the documentation names its folders.
- Its title is its first heading; its authors the bold line under it ("**Author:** A, B"; a team is an
  organisation); its description its first paragraph, before its first section other than its introduction,
  without HTML blocks such as a notebook's badge. Its sections (the headings below the title, outside code) are
  its outline, each at its address on the documentation site with the anchor Sphinx gives it (docutils'
  identifiers: "3.1 Free-Text Search" is #free-text-search).
- It follows the documentation's format (tutorials/documentation_format.md) when its sections are the format's.
- Its notebooks and scripts are its files, at their addresses on GitHub; its date is its latest change's."""

import json
import re
import unicodedata

from linkeddata.parsers import link, present, slug

SITE = "https://docs.vhp4safety.nl/en/latest/"
TUTORIAL = re.compile(r"tutorials/([^/]+)/([^/]+)\.(md|rst)")
# Folders of the tutorials that hold none: the videos' page, which the videos' own source gives.
LEFT_OUT = {"peertube"}
# The sections of the documentation's format (tutorials/documentation_format.md), in order.
FORMAT = ["Introduction", "Accessing the Tool", "Tool Functionalities", "Interpreting the Output", "Summary"]
FORMAT_PAGE = SITE + "tutorials/documentation_format.html"
DATE = "http://www.w3.org/2001/XMLSchema#date"
# The files beside a tutorial that are its parts.
FILES = (".ipynb", ".r", ".R", ".py", ".Rmd")
# An underline of a reStructuredText heading.
UNDERLINE = re.compile(r"([=\-~^\"'`#*+])\1{2,}\s*")


def tutorials(tree: dict) -> dict[str, str]:
    """Each tutorial's source by its folder's name: its Markdown file, else its reStructuredText one."""
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
    """Each tutorial's source by its path, its latest change by its path and "#changes", and the repository."""
    found = {"repository": addresses["repository"]}
    for path in tutorials(json.loads(contents["docs"])).values():
        found[path] = addresses["source"] + path
        found[path + "#changes"] = addresses["changes"] + path + "&per_page=1"
    return found


def anchor(heading: str) -> str:
    """A heading's identifier as docutils makes it: lower case, other characters as -, no leading digits."""
    plain = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"[^a-z0-9]+", "-", plain)
    return re.sub(r"^[-0-9]+|-+$", "", plain)


def plain(text: str) -> str:
    """A Markdown text without its links' addresses, its emphasis, its footnote marks and other HTML."""
    text = re.sub(r"<sup>.*?</sup>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]+", "", text)
    return " ".join(text.split())


def headings(text: str, rst: bool) -> list[tuple[int, str]]:
    """The headings of a source, by level (1 is the title), outside code blocks."""
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
    """Whether a line of a source is a heading, a heading's underline or a rule."""
    line = lines[number]
    if UNDERLINE.fullmatch(line):
        return True
    if not rst:
        return re.match(r"#{1,6}\s", line) is not None
    below = lines[number + 1] if number + 1 < len(lines) else ""
    return bool(line.strip()) and UNDERLINE.fullmatch(below) is not None


def names(line: str) -> list[str]:
    """The names of an authors' line ("**Author:** A, B and C")."""
    text = re.sub(r"^Authors?:\s*", "", plain(line), flags=re.IGNORECASE)
    return [name.strip() for name in re.split(r",|;|\band\b", text) if name.strip()]


def opening(text: str, rst: bool) -> tuple[list[str], str]:
    """The authors and the first paragraph a tutorial opens with, before its first section other than its
    introduction."""
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
    """The link to an author's record, adding its row: a team is an organisation, anyone else a person."""
    if "team" in name.lower():
        address = "organizations/" + slug(name)
        others.setdefault(address, {"@id": address, "@type": "Organization", "name": name})
    else:
        address = "people/" + slug(name)
        others.setdefault(address, {"@id": address, "@type": "Person", "name": name})
    return link(address)


def follows(found: list[tuple[int, str]]) -> bool:
    """Whether the sections below the title are the documentation format's, in order."""
    named = [re.sub(r"^[0-9.]+\s*", "", heading) for level, heading in found if level == 2]
    position = 0
    for heading in named:
        if position < len(FORMAT) and heading.startswith(FORMAT[position]):
            position += 1
    return position == len(FORMAT)


def parse(contents: dict[str, bytes]) -> list[dict]:
    tree = json.loads(contents["docs"])
    # Without the repository's answer, the tutorials' files are left out: their addresses need its branch.
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
        parts = []
        for level, heading in found[1:]:
            if level <= 3 and present(heading):
                parts.append({"@type": "WebPageElement", "name": heading, "url": link(page + "#" + anchor(heading)), "position": len(parts) + 1})
        folder = path.rsplit("/", 1)[0] + "/"
        for entry in tree["tree"]:
            if files is not None and entry["path"].startswith(folder) and entry["path"].endswith(FILES):
                parts.append({"@type": "DigitalDocument", "name": entry["path"].rsplit("/", 1)[1], "url": link(files + entry["path"])})
        row["hasPart"] = parts
        rows.append(row)
    return rows + list(others.values())
