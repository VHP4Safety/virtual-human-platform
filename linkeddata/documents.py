"""Records as JSON-LD documents, compacted with the platform's context, so that their fields are named as
in JSON-LD: https://schema.org/name is "name", and http://purl.org/dc/terms/conformsTo is "dct:conformsTo".
A page template reads a record with the keys of its own JSON-LD context."""

import json
from functools import cache
from pathlib import Path

from pyld import jsonld
from rdflib import BNode, Graph, URIRef

import database
from database.tables import Record
from linkeddata import storage
from linkeddata.model import settings

TEMPLATES = Path(__file__).parent.parent / "templates"


def context(config: dict) -> dict:
    """The JSON-LD context: schema.org terms without a prefix, other vocabularies with theirs."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    return terms


def term(iri: str) -> str:
    """The name of a property or class in the platform's JSON-LD."""
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            if prefix == "schema":
                return iri.removeprefix(namespace)
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


def expand(name: str) -> str:
    """The property of a field: "name" is https://schema.org/name, "dct:conformsTo" the property of dct."""
    prefixes = settings()["prefixes"]
    prefix, _, local = name.partition(":")
    if local and prefix in prefixes:
        return prefixes[prefix] + local
    return prefixes["schema"] + name


def stored_values(found: Graph, iri: str, name: str) -> list[str]:
    """The values of a field of the record at *iri* in *found*: the addresses of links, and texts."""
    values = []
    for value in found.objects(URIRef(iri), URIRef(expand(name))):
        values.append(str(value))
    return values


def values(document: dict, name: str) -> list:
    """The values of a field of a document: the addresses of links, and texts or numbers."""
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


def described(found: Graph, iri: str) -> Graph:
    """The statements of the record at *iri* in *found*, with those of the nodes without an address (blank
    nodes) that it holds, at any depth."""
    own = Graph()
    nodes = [URIRef(iri)]
    seen = set()
    while nodes:
        node = nodes.pop()
        if node in seen:
            continue
        seen.add(node)
        for statement in found.triples((node, None, None)):
            own.add(statement)
            if isinstance(statement[2], BNode):
                nodes.append(statement[2])
    return own


def document(found: Graph, iri: str | None = None) -> dict:
    """The JSON-LD document of the record at *iri*, with the nodes it holds without an address in it; without
    *iri*, of all the statements, such as those of a record and the records it links to."""
    if iri is None:
        expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
        return jsonld.compact(expanded, context(settings()))
    expanded = jsonld.from_rdf(described(found, iri).serialize(format="nt"), {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": context(settings()), "@id": iri})
    if "@graph" in framed:
        return {"@context": framed["@context"], **framed["@graph"][0]} if framed["@graph"] else {"@context": framed["@context"]}
    return framed


def document_of(iri: str) -> str | None:
    """The record at this address in JSON-LD as it is now; None when there is none."""
    with database.session() as db:
        record = db.get(Record, iri)
    if record is None or record.removed_at:
        return None
    return json.dumps(document(storage.read([iri])), indent=2)


@cache
def template_context(template: str) -> dict:
    """The JSON-LD context of a page template, in a file next to it (methods/method.context.jsonld for
    methods/method.html), which names the properties of a record with the keys that the template uses."""
    return json.loads((TEMPLATES / f"{template}.context.jsonld").read_text(encoding="utf-8"))


def view(record: Record, template: str) -> dict:
    """The record with the keys of *template*, and the records it links to embedded in it, so that their
    names can be shown."""
    statements = storage.linked_graph(record).serialize(format="nt")
    expanded = jsonld.from_rdf(statements, {"format": "application/n-quads"})
    framed = jsonld.frame(expanded, {"@context": template_context(template), "@id": record.iri, "@embed": "@always"})
    found = framed["@graph"][0] if "@graph" in framed else framed
    found.pop("@context", None)
    return found
