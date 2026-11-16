"""Helpers of the parsers."""

import importlib
import re
import unicodedata
from functools import cache
from pathlib import Path

import yaml

from linkeddata.parsers.mapping import extract_doi_from_text
from linkeddata.profile import MODEL_DIR, settings

SOURCES = Path(__file__).parent.parent / "sources"
# The address of the platform in upstream files. Its addresses are read under the base, so that the records of a
# test site are linked on that site.
UPSTREAM = "https://platform.vhp4safety.nl/"
# The terms of the glossary are shown on its site at other addresses than in its file.
GLOSSARY_SITE = "https://glossary.vhp4safety.nl/#"
GLOSSARY = "https://vhp4safety.github.io/glossary#"

# The upstream codes of the regulatory questions, with the addresses of the questions.
QUESTIONS = {
    "reg_q_1a": "casestudies/kidney/Q1",
    "reg_q_1b": "casestudies/kidney/Q2",
    "reg_q_2a": "casestudies/parkinson/Q1",
    "reg_q_2b": "casestudies/parkinson/Q2",
    "reg_q_3a": "casestudies/thyroid/Q1",
    "reg_q_3b": "casestudies/thyroid/Q2",
}

MISSING = {"", "_No response_", "No response", "NA", "Unknown", "Unknown at this timepoint", "no_url", "[TODO]", "[DRAFT]"}


MARKUP = re.compile(r"<\s*/?[a-zA-Z][^>]*>")


def marked(value):
    """Return a text, with the platform addresses of its links if it has markup. The pages show its markup."""
    return str(value).replace(UPSTREAM, settings()["base"]) if MARKUP.search(str(value)) else str(value)


def present(value) -> bool:
    """Return False for an empty value or an upstream placeholder."""
    return value is not None and str(value).strip() not in MISSING and not str(value).strip().startswith("[DRAFT]")


def link(address: str) -> dict:
    return {"@id": address.removeprefix(UPSTREAM)}


def web_link(value: str):
    """Return a link for a web address or a Markdown link, else the text."""
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
    """Return a text in the form used to compare names."""
    return " ".join(str(text).casefold().replace("-", " ").replace("_", " ").split()).rstrip("/")


@cache
def terms(source: str) -> dict[str, set[str]]:
    """Return the terms of a model vocabulary by their names and addresses."""
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
    """Return a link to the term named by a text, else web_link() of the text."""
    label = f"{str(text).strip()} ({qualifier})" if qualifier else str(text).strip()
    matched = terms(source).get(spelled(label), set())
    if len(matched) == 1:
        return link(next(iter(matched)))
    return web_link(text)


def licence(text):
    """Return a link to the SPDX licence named in a text, else web_link() of the text."""
    return term(re.sub(r"\s+licen[cs]e$", "", str(text).strip(), flags=re.IGNORECASE), "spdx")


def publication(value) -> dict | None:
    """Return the row of the publication of a DOI, or None."""
    doi = extract_doi_from_text(str(value))
    if doi is None:
        return None
    return {"@id": "publications/" + slug(doi), "@type": "ScholarlyArticle", "sameAs": link("https://doi.org/" + doi),
            "identifier": link("https://doi.org/" + doi)}


def slug(text: str) -> str:
    """Return an identifier made from a name, without accents."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
