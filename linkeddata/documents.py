"""Records as JSON-LD documents, compacted with the platform's context: https://schema.org/name is "name",
and http://purl.org/dc/terms/conformsTo is "dct:conformsTo". Page templates use their own contexts."""

import json
from functools import cache
from pathlib import Path

from pyld import jsonld
from rdflib import Graph, URIRef

import database
from database.tables import Record
from linkeddata import storage
from linkeddata.model import settings

TEMPLATES = Path(__file__).parent.parent / "templates"


def context(config: dict) -> dict:
    """The JSON-LD context: schema.org terms unprefixed, other vocabularies prefixed, and names for the
    glossary's properties."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    terms.update(config.get("terms", {}))
    return terms


def term(iri: str) -> str:
    """The name of a property or class in the platform's JSON-LD."""
    for name, named in settings().get("terms", {}).items():
        if iri == named:
            return name
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            if prefix == "schema":
                return iri.removeprefix(namespace)
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


def expand(name: str) -> str:
    """The property of a field: "name" is https://schema.org/name, "dct:conformsTo" the property of dct."""
    if name in settings().get("terms", {}):
        return settings()["terms"][name]
    prefixes = settings()["prefixes"]
    prefix, _, local = name.partition(":")
    if local and prefix in prefixes:
        return prefixes[prefix] + local
    return prefixes["schema"] + name


def stored_values(found: Graph, iri: str, name: str) -> list[str]:
    """The values of a field of the record at *iri* in *found*: link addresses and texts."""
    values = []
    for value in found.objects(URIRef(iri), URIRef(expand(name))):
        values.append(str(value))
    return values


def values(document: dict, name: str) -> list:
    """The values of a field of a document: link addresses, texts and numbers."""
    given = document.get(name)
    found = []
    for item in given if isinstance(given, list) else [] if given is None else [given]:
        if isinstance(item, dict):
            item = item.get("@id", item.get("@value"))
        if item is not None:
            found.append(item)
    return found


def links(document: dict) -> list[str]:
    """The addresses that a document links to."""
    found = []
    for name, given in document.items():
        if name.startswith("@"):
            continue
        for item in given if isinstance(given, list) else [given]:
            if isinstance(item, dict) and "@id" in item:
                found.append(item["@id"])
    return found


def statements(document: dict) -> Graph:
    return Graph().parse(data=json.dumps(document), format="json-ld")


def document(found: Graph, iri: str | None = None) -> dict:
    """The JSON-LD document of the record at *iri*, with its nodes without an address; without *iri*, of all
    the statements."""
    if iri is None:
        expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
        return jsonld.compact(expanded, context(settings()))
    expanded = jsonld.from_rdf(storage.described(found, iri).serialize(format="nt"), {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": context(settings()), "@id": iri})
    if "@graph" in framed:
        return {"@context": framed["@context"], **framed["@graph"][0]} if framed["@graph"] else {"@context": framed["@context"]}
    return framed


def document_of(iri: str) -> str | None:
    """The current JSON-LD of the record at this address; None when there is none."""
    with database.session() as db:
        record = db.get(Record, iri)
    if record is None or record.removed_at:
        return None
    return json.dumps(document(storage.read([iri])), indent=2)


@cache
def template_context(template: str) -> dict:
    """The JSON-LD context of a page template, in a file next to it (methods/method.context.jsonld for
    methods/method.html), with the keys the template uses."""
    return json.loads((TEMPLATES / f"{template}.context.jsonld").read_text(encoding="utf-8"))


def view(record: Record, template: str) -> dict:
    """The record with the keys of *template*, with its linked records embedded so their names can be shown."""
    statements = storage.linked_graph(record).serialize(format="nt")
    expanded = jsonld.from_rdf(statements, {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": template_context(template), "@id": record.iri, "@embed": "@always"})
    found = framed["@graph"][0] if "@graph" in framed else framed
    found.pop("@context", None)
    return found
