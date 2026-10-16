"""Parser of the answers of doi.org for the DOIs of the platform's records (a workaround, see
linkeddata/parsers): each answer is the citation of a record in CSL JSON, as Crossref or DataCite registered
it. Its rows are the records, with their title, the date of their publication (as precise as given: a date,
a year and a month, or a year), and their journal, as a part."""

import json

from linkeddata.parsers import present

XSD = "http://www.w3.org/2001/XMLSchema#"


def published(issued) -> dict | None:
    """The date of a citation's issue, as precise as its date parts are."""
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
        row = {"@id": iri, "@type": "Publication"}
        if present(found.get("title")):
            row["title"] = found["title"]
        date = published(found.get("issued"))
        if date:
            row["date"] = date
        journal = found.get("container-title")
        if isinstance(journal, list):
            journal = journal[0] if journal else None
        if present(journal):
            row["journal"] = {"@type": "Journal", "name": journal}
            issns = []
            for issn in found.get("ISSN") or []:
                if present(issn):
                    issns.append(issn)
            if issns:
                row["journal"]["issn"] = issns
        rows.append(row)
    return rows
