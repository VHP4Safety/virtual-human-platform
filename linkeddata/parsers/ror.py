"""Parser of the affiliation matching of the Research Organization Registry, a workaround (see linkeddata/parsers).

- For each organisation requested by name, keep the organisation chosen by ROR with confidence, if one of its names
  is the requested name.
- Leave out a department matched to its university, as only institutions are in ROR."""

import json
import re

from linkeddata.parsers import link


def plain(name: str) -> str:
    """Return a name in the form used for comparison: without an acronym in brackets or a leading "The", in lower
    case."""
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
