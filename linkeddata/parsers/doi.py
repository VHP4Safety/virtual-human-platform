"""Parser of the doi.org citations of the records."""

import json

from linkeddata.parsers import marked, present

XSD = "http://www.w3.org/2001/XMLSchema#"


def published(issued) -> dict | None:
    """Return the issue date of a citation, as precise as its date parts."""
    parts = []
    for part in ((issued or {}).get("date-parts") or [[]])[0]:
        if not isinstance(part, int):
            break
        parts.append(part)
    if len(parts) >= 3:
        return {"@value": f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}", "@type": XSD + "date"}
    if len(parts) == 2:
        return {"@value": f"{parts[0]:04d}-{parts[1]:02d}", "@type": XSD + "gYearMonth"}
    if len(parts) == 1:
        return {"@value": f"{parts[0]:04d}", "@type": XSD + "gYear"}
    return None


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    for iri, content in sorted(contents.items()):
        if not content.strip():
            continue
        found = json.loads(content)
        row = {"@id": iri, "@type": "ScholarlyArticle"}
        if present(found.get("title")):
            row["name"] = marked(found["title"])
        date = published(found.get("issued"))
        if date:
            row["datePublished"] = date
        journal = found.get("container-title")
        if isinstance(journal, list):
            journal = journal[0] if journal else None
        if present(journal):
            row["isPartOf"] = {"@type": "Periodical", "name": journal}
            issns = []
            for issn in found.get("ISSN") or []:
                if present(issn):
                    issns.append(issn)
            if issns:
                row["isPartOf"]["issn"] = issns
        rows.append(row)
    return rows
