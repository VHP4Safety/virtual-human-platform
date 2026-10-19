"""Parser of the VHP4Safety courses on GitHub (a workaround, see linkeddata/parsers): each course's repository tree
at a pinned commit, the repository itself (its description, topics, licence and default branch), its README and
its agenda (agenda/*.md).
- A course is a training material at training/<repository>, a Bioschemas Course: its name is its agenda's first
  heading, else its repository's name; its description is the repository's, else its README's introduction; its
  topics are keywords, and a DOI in its README is its DOI.
- From its agenda: its authors (the line of names under the title, without titles such as PhD), its dates ("21 &
  22 May, 2025") as a time it was given, and its learning aims as what it teaches.
- Its materials are its files: slides, notebooks, data and chapters (R Markdown), at their addresses on GitHub;
  literature, archived and temporary files are left out."""

import json
import re
from datetime import datetime

from linkeddata.parsers import licence, link, present, slug, term

PROFILE = "https://bioschemas.org/profiles/Course/1.0-RELEASE"
DATE = "http://www.w3.org/2001/XMLSchema#date"
MATERIALS = (".pptx", ".ipynb", ".Rmd", ".xlsx", ".csv")
LEFT_OUT = ("literature/", "old_archive/", "~$")
DOI = re.compile(r"https://doi\.org/(10\.\d{4,}/[^\s)\]]+)")
# Dates of a course: "21 & 22 May, 2025", or "21 May, 2025".
DATES = re.compile(r"(\d{1,2})(?:\s*(?:&|-|–|and)\s*(\d{1,2}))?\s+([A-Z][a-z]+),?\s+(\d{4})")
TITLES = re.compile(r",?\s*\b(PhD|MSc|MD|Prof\.?|Dr\.?)$")


def courses(contents: dict) -> list[str]:
    """The repositories whose trees are given, by name."""
    return [name for name, content in contents.items() if "/" not in name and "#" not in name and b'"tree"' in content]


def agenda_of(tree: dict) -> str | None:
    for entry in tree["tree"]:
        if re.fullmatch(r"agenda/[^/]+\.md", entry["path"]):
            return entry["path"]
    return None


def documents(contents: dict, addresses: dict) -> dict[str, str]:
    """Each course's repository by its name and "#repository", its README and its agenda by its name and path."""
    found = {}
    for name in courses(contents):
        found[name + "#repository"] = addresses["repositories"] + name
        found[name + "/README.md"] = addresses[name] + "README.md"
        agenda = agenda_of(json.loads(contents[name]))
        if agenda is not None:
            found[name + "/" + agenda] = addresses[name] + agenda
    return found


def plain(text: str) -> str:
    """A Markdown text without its links' addresses and its emphasis."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return " ".join(re.sub(r"[*_`]+", "", text).split())


def introduction(readme: str) -> str:
    """The README's first paragraph under an "Introduction" heading."""
    given = []
    reading = False
    for line in readme.splitlines():
        if re.match(r"#+\s+Introduction", line):
            reading = True
            continue
        if reading and line.startswith("#"):
            break
        if reading and line.strip():
            given.append(line.strip())
        elif reading and given:
            break
    return plain(" ".join(given))


def given_dates(line: str) -> dict | None:
    """The time a course was given, from a line such as "21 & 22 May, 2025"."""
    written = DATES.search(line)
    if written is None:
        return None
    first, last, month, year = written.groups()
    try:
        start = datetime.strptime(f"{first} {month} {year}", "%d %B %Y").date()
        end = datetime.strptime(f"{last or first} {month} {year}", "%d %B %Y").date()
    except ValueError:
        return None
    return {"@type": "Given", "startDate": {"@value": start.isoformat(), "@type": DATE}, "endDate": {"@value": end.isoformat(), "@type": DATE}}


def agenda(row: dict, text: str, others: dict) -> None:
    """The name, authors, dates and learning aims of a course's agenda."""
    aims = False
    for line in text.splitlines():
        written = re.match(r"(#+)\s+(.+)", line)
        if written and len(written.group(1)) == 1 and "name" not in row:
            row["name"] = plain(written.group(2))
            continue
        if written:
            heading = plain(written.group(2))
            aims = heading.lower().startswith("learning aims")
            if "author" not in row and ";" in heading:
                row["author"] = []
                for name in heading.split(";"):
                    name = TITLES.sub("", name.strip())
                    others.setdefault("people/" + slug(name), {"@id": "people/" + slug(name), "@type": "Person", "name": name})
                    row["author"].append(link("people/" + slug(name)))
            elif "hasCourseInstance" not in row and given_dates(heading):
                row["hasCourseInstance"] = [given_dates(heading)]
            continue
        if aims and re.match(r"\s*[-*]\s+", line):
            row.setdefault("teaches", []).append(plain(re.sub(r"^\s*[-*]\s+", "", line)))


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    others = {}
    for name in courses(contents):
        if name + "#repository" not in contents:
            print(f"courses: {name} left out, without its repository's answer")
            continue
        tree = json.loads(contents[name])
        repository = json.loads(contents[name + "#repository"])
        files = "/".join([repository["html_url"], "blob", repository["default_branch"]]) + "/"
        readme = contents.get(name + "/README.md", b"").decode("utf-8")
        row = {"@id": "training/" + slug(name), "@type": "Course", "url": link(repository["html_url"]),
               "learningResourceType": "course", "conformsTo": link(PROFILE)}
        path = agenda_of(tree)
        if path is not None and name + "/" + path in contents:
            agenda(row, contents[name + "/" + path].decode("utf-8"), others)
        row.setdefault("name", repository["name"])
        description = repository.get("description") or introduction(readme)
        if present(description):
            row["description"] = description
        row["keywords"] = [term(topic, "glossary") for topic in repository.get("topics") or []]
        spdx = (repository.get("license") or {}).get("spdx_id")
        if present(spdx) and spdx != "NOASSERTION":
            row["license"] = licence(spdx)
        found = DOI.search(readme)
        if found:
            row["sameAs"] = link("https://doi.org/" + found.group(1))
        parts = []
        for entry in tree["tree"]:
            if entry["type"] == "blob" and entry["path"].endswith(MATERIALS) and not any(part in entry["path"] for part in LEFT_OUT):
                parts.append({"@type": "File", "name": entry["path"].rsplit("/", 1)[-1], "url": link(files + entry["path"])})
        row["hasPart"] = parts
        rows.append(row)
    return rows + list(others.values())
