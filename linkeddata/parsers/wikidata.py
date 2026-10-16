"""Parser of an answer of Wikidata's API for some items (wbgetentities, with their English labels,
descriptions and aliases), such as the levels of technology readiness (a workaround, see
linkeddata/parsers): the first item is a vocabulary, and the others are its terms, at their addresses in
Wikidata. A term's first alias is its code, and its other aliases are its other names."""

import json

from linkeddata.parsers import link, present, slug

ENTITY = "http://www.wikidata.org/entity/"


def english(item: dict, field: str) -> list[str]:
    """The English texts of a field of an item: its label, its description, or its aliases."""
    given = item.get(field, {}).get("en", [])
    found = []
    for text in given if isinstance(given, list) else [given]:
        if present(text.get("value")):
            found.append(text["value"])
    return found


def parse(content: bytes) -> list[dict]:
    items = list(json.loads(content)["entities"].values())
    if not items:
        return []
    vocabulary = "vocabularies/" + slug(english(items[0], "labels")[0])
    rows = [{"@id": vocabulary, "@type": "Vocabulary", "name": english(items[0], "labels")[0], "namespace": link(ENTITY)}]
    for description in english(items[0], "descriptions"):
        rows[0]["description"] = description
    for item in items[1:]:
        row = {"@id": ENTITY + item["id"], "@type": "Term", "vocabulary": link(vocabulary)}
        for label in english(item, "labels"):
            row["label"] = label
        for description in english(item, "descriptions"):
            row["definition"] = description
        aliases = english(item, "aliases")
        if aliases:
            row["code"] = aliases[0]
        if aliases[1:]:
            row["alternate"] = aliases[1:]
        rows.append(row)
    return rows
