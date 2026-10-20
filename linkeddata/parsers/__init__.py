"""Helpers of the parsers. A parser is a temporary workaround for an upstream file that is not clean linked data.
It reads the file and gives rows in the terms of the model, which are read with the JSON-LD context of the platform.
An address is written as {"@id": ...}, under the base of the platform when it has no scheme. A text that is a label
or code of a term of a model vocabulary is written as the address of the term (term). Placeholders are left out, and
unreadable values are given as text, for the checks to report."""

import importlib
import re
import unicodedata
from functools import cache
from pathlib import Path

import yaml

from linkeddata.profile import MODEL_DIR

SOURCES = Path(__file__).parent.parent / "sources"
# The glossary's site gives its terms at other addresses than its file.
GLOSSARY_SITE = "https://glossary.vhp4safety.nl/#"
GLOSSARY = "https://vhp4safety.github.io/glossary#"

# The upstream codes of the regulatory questions, and the questions' addresses.
QUESTIONS = {
    "reg_q_1a": "casestudies/kidney/Q1",
    "reg_q_1b": "casestudies/kidney/Q2",
    "reg_q_2a": "casestudies/parkinson/Q1",
    "reg_q_2b": "casestudies/parkinson/Q2",
    "reg_q_3a": "casestudies/thyroid/Q1",
    "reg_q_3b": "casestudies/thyroid/Q2",
}

MISSING = {"", "_No response_", "No response", "NA", "Unknown", "Unknown at this timepoint", "no_url", "[TODO]", "[DRAFT]"}


HTML = "http://www.w3.org/1999/02/22-rdf-syntax-ns#HTML"
MARKUP = re.compile(r"<\s*/?[a-zA-Z][^>]*>")


def marked(value):
    """A text, typed as HTML (rdf:HTML) when it has markup such as <p> or <b>."""
    return {"@value": str(value), "@type": HTML} if MARKUP.search(str(value)) else str(value)


def present(value) -> bool:
    """False for empty values and upstream placeholders."""
    return value is not None and str(value).strip() not in MISSING and not str(value).strip().startswith("[DRAFT]")


def link(address: str) -> dict:
    return {"@id": address}


def web_link(value: str):
    """A link for a web address or a Markdown link ([text](address)), with glossary site addresses at the
    glossary's own; other texts as they are."""
    text = str(value).strip()
    written = re.fullmatch(r"\[[^\]]*\]\((https?://[^)\s]+)\)", text)
    if written:
        text = written.group(1)
    if text.startswith(GLOSSARY_SITE):
        text = GLOSSARY + text.removeprefix(GLOSSARY_SITE)
    if text.startswith(("http://", "https://")):
        return link(text)
    return text


def spelled(text: str) -> str:
    """A text as names are compared: lower case, hyphens, underscores and spaces as one space, no trailing
    slash."""
    return " ".join(str(text).casefold().replace("-", " ").replace("_", " ").split()).rstrip("/")


@cache
def terms(source: str) -> dict[str, set[str]]:
    """The terms of a model vocabulary (a source of a pinned file, such as the glossary), by label, code,
    other names and other addresses, as spelled() compares them."""
    spec = yaml.safe_load((SOURCES / f"{source}.yaml").read_text(encoding="utf-8"))
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    found = {}
    for row in parser.parse((MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()):
        if row.get("@type") == "DefinedTerm":
            names = [row.get("name"), row.get("termCode")] + list(row.get("alternateName") or [])
            for address in row.get("sameAs") or []:
                names.append(address["@id"])
            for text in names:
                if text:
                    found.setdefault(spelled(text), set()).add(row["@id"])
    return found


def term(text, source: str, qualifier: str = ""):
    """A link to the one term whose label (with a qualifier in brackets, when given), code, other name or
    other address is the text; else web_link() of the text."""
    label = f"{str(text).strip()} ({qualifier})" if qualifier else str(text).strip()
    matched = terms(source).get(spelled(label), set())
    if len(matched) == 1:
        return link(next(iter(matched)))
    return web_link(text)


def licence(text):
    """A link to the SPDX licence a text names by identifier, name or address, also with "license" at its
    end; else web_link() of the text."""
    return term(re.sub(r"\s+licen[cs]e$", "", str(text).strip(), flags=re.IGNORECASE), "spdx")


def publication(value) -> dict | None:
    """The row of the publication a DOI names (10.1234/x or https://doi.org/10.1234/x), at
    publications/<DOI>; None for other texts."""
    doi = str(value).strip().removeprefix("https://doi.org/")
    if not doi.startswith("10."):
        return None
    return {"@id": "publications/" + slug(doi), "@type": "ScholarlyArticle", "sameAs": link("https://doi.org/" + doi),
            "identifier": link("https://doi.org/" + doi)}


def slug(text: str) -> str:
    """An identifier made from a name, without accents: "Café" is "cafe"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
