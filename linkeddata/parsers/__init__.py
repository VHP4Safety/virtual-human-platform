"""Parsers: a temporary workaround for upstream files that are not clean linked data.

The upstream files hold several values in one text, codes where addresses are meant, yes/no flags
where links are meant, and placeholders for missing values. Until the sources publish clean linked
data, one parser per file cleans it, and nothing else: how the rows become the model is decided by
the rules of the source (sources/<name>.yaml), not here.

A parser takes the downloaded file and returns rows. Each row keeps the upstream names of its
fields, and has its address ("@id", under the platform's base address when it has no scheme) and
its kind ("@type"). Addresses are written as {"@id": ...}. Placeholders are left out. A text that is
exactly the label or the code of a term of a vocabulary of the model, such as "pharmacovigilance" in the
VHP4Safety glossary, is written as the term's address (term). Values the parser cannot read are passed
on as plain text, so the checks of the build report them.
"""

import importlib
import re
import unicodedata
from functools import cache
from pathlib import Path

import yaml

from linkeddata.model import MODEL_DIR

SOURCES = Path(__file__).parent.parent / "sources"
# The glossary's site gives its terms at other addresses than the glossary's own file.
GLOSSARY_SITE = "https://glossary.vhp4safety.nl/#"
GLOSSARY = "https://vhp4safety.github.io/glossary#"

# The codes with which upstream files name the regulatory questions of the case studies, and the addresses of
# the questions.
QUESTIONS = {
    "reg_q_1a": "casestudies/kidney/Q1",
    "reg_q_1b": "casestudies/kidney/Q2",
    "reg_q_2a": "casestudies/parkinson/Q1",
    "reg_q_2b": "casestudies/parkinson/Q2",
    "reg_q_3a": "casestudies/thyroid/Q1",
    "reg_q_3b": "casestudies/thyroid/Q2",
}

MISSING = {"", "_No response_", "No response", "NA", "Unknown", "Unknown at this timepoint", "no_url", "[TODO]", "[DRAFT]"}


def present(value) -> bool:
    """False for empty values and for the placeholders that upstream files use for them."""
    return value is not None and str(value).strip() not in MISSING and not str(value).strip().startswith("[DRAFT]")


def link(address: str) -> dict:
    return {"@id": address}


def web_link(value: str):
    """A link for a web address, and for the link of a text written as a Markdown link ([text](address)); a
    term of the glossary at its site's address is linked at the glossary's own. Any other text is passed on
    as it is."""
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
    """A text as names are compared: in lower case, with hyphens, underscores and runs of spaces as one
    space, and without a slash at its end."""
    return " ".join(str(text).casefold().replace("-", " ").replace("_", " ").split()).rstrip("/")


@cache
def terms(source: str) -> dict[str, set[str]]:
    """The terms of a vocabulary of the model (a source of a pinned vocabulary file, such as the glossary),
    by their label, their code, their other names and their other addresses, as spelled() compares them, as
    the source's parser reads them."""
    spec = yaml.safe_load((SOURCES / f"{source}.yaml").read_text(encoding="utf-8"))
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    found = {}
    for row in parser.parse((MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()):
        if row.get("@type") == "Term":
            names = [row.get("label"), row.get("code")] + list(row.get("alternate") or [])
            for address in row.get("same_as") or []:
                names.append(address["@id"])
            for text in names:
                if text:
                    found.setdefault(spelled(text), set()).add(row["@id"])
    return found


def term(text, source: str, qualifier: str = ""):
    """A link to the term of a vocabulary whose label (followed by a qualifier in brackets, when given), code,
    other name or other address is the text, as spelled() compares them, when one term has it; another web
    address is linked as it is, and any other text is passed on as it is."""
    label = f"{str(text).strip()} ({qualifier})" if qualifier else str(text).strip()
    matched = terms(source).get(spelled(label), set())
    if len(matched) == 1:
        return link(next(iter(matched)))
    return web_link(text)


def publication(value) -> dict | None:
    """The row of the publication that a DOI names (10.1234/x, or https://doi.org/10.1234/x), at
    publications/<DOI>, with the DOI's address; None for any other text."""
    doi = str(value).strip().removeprefix("https://doi.org/")
    if not doi.startswith("10."):
        return None
    return {"@id": "publications/" + slug(doi), "@type": "Publication", "doi": link("https://doi.org/" + doi)}


def slug(text: str) -> str:
    """An identifier made from a name, with accents left out: "Café" is "cafe"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
