"""Parser of the affiliation matching of the Research Organization Registry."""

import json
import re

from linkeddata.parsers import link


def plain(name: str) -> str:
    """Return a name in lower case, without an acronym in brackets or a leading The."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name.strip())
    return re.sub(r"^the\s+", "", name, flags=re.IGNORECASE).casefold()


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    for iri, content in sorted(contents.items()):
        for item in json.loads(content).get("items", []):
            organization = item.get("organization") or {}
            names = set()
            for name in organization.get("names", []):
                names.add(plain(name["value"]))
            if item.get("chosen") and plain(item.get("substring", "")) in names:
                rows.append({"@id": iri, "sameAs": link(organization["id"])})
    return rows
