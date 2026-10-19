"""Parser of the Research Organization Registry's affiliation matching (a workaround, see linkeddata/parsers):
for each organisation asked for by its name, the organisation that ROR chooses with confidence, when one of its
names is the asked name. ROR lists institutions, so a department matched to its university is left out, as it is
not the university."""

import json
import re

from linkeddata.parsers import link


def plain(name: str) -> str:
    """A name as compared: without an acronym in brackets or a leading "The", in lower case."""
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
                rows.append({"@id": iri, "@type": "Organization", "ror": link(organization["id"])})
    return rows
