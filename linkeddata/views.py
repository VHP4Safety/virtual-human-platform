"""Records as the dictionaries that the page templates read. The JSON-LD context of a template, in a
file next to it (methods/method.context.jsonld for methods/method.html), names the properties of a
record with the keys that the template uses; the records it links to are embedded, so that their
names can be shown."""

import json
from functools import cache
from pathlib import Path

from pyld import jsonld

from database.tables import Record
from linkeddata import rdf

TEMPLATES = Path(__file__).parent.parent / "templates"


@cache
def context(template: str) -> dict:
    return json.loads((TEMPLATES / f"{template}.context.jsonld").read_text(encoding="utf-8"))


def view(record: Record, template: str) -> dict:
    """The record with the keys of *template*, and the records it links to embedded in it."""
    statements = rdf.linked_graph(record).serialize(format="nt")
    expanded = jsonld.from_rdf(statements, {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": context(template), "@id": record.iri, "@embed": "@always"})
    found = framed["@graph"][0] if "@graph" in framed else framed
    found.pop("@context", None)
    return found
