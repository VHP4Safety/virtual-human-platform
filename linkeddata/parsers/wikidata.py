"""Parser of a Wikidata API response (wbgetentities, with English labels, descriptions and aliases), such as the
technology readiness levels, a workaround (see linkeddata/parsers).

- Vocabulary: the first item. It has no namespace, as all Wikidata items have the same namespace. Its name starts
  with a capital letter, as labels are in lower case on Wikidata.
- Terms: the other items. The first alias is the code, and the other aliases are other names."""

import json

from linkeddata.parsers import link, present, slug

ENTITY = "http://www.wikidata.org/entity/"


def english(item: dict, field: str) -> list[str]:
    """Return the English texts of a field of an item: labels, descriptions or aliases."""
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
    label = english(items[0], "labels")[0]
    vocabulary = "vocabularies/" + slug(label)
    rows = [{"@id": vocabulary, "@type": "DefinedTermSet", "name": label[:1].upper() + label[1:],
             "url": link("https://www.wikidata.org/wiki/" + items[0]["id"]), "sameAs": link(ENTITY + items[0]["id"])}]
    for description in english(items[0], "descriptions"):
        rows[0]["description"] = description
    for item in items[1:]:
        row = {"@id": ENTITY + item["id"], "@type": "DefinedTerm", "inDefinedTermSet": link(vocabulary)}
        for label in english(item, "labels"):
            row["name"] = label
        for description in english(item, "descriptions"):
            row["description"] = description
        aliases = english(item, "aliases")
        if aliases:
            row["termCode"] = aliases[0]
        if aliases[1:]:
            row["alternateName"] = aliases[1:]
        rows.append(row)
    return rows
