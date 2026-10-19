"""A record as a detached RO-Crate 1.2 (https://w3id.org/ro/crate/1.2), at <record's address>/ro-crate-metadata.json:
its metadata file describes a research object whose root is the record's address followed by a slash, and whose
main entity is the record, with its parts; the people, organisations, publications, grants and terms it links to
are entities of the crate, as their public data gives them. Files are linked where they are (such as Zenodo or
GitHub), not copied. Names are the platform's JSON-LD names (schema.org's unprefixed; pbpk: for the PBPK terms of
ROBOT's form), under RO-Crate's context and the platform's prefixes."""

from pyld import jsonld
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO

from database.tables import Record
from linkeddata import documents, storage
from linkeddata.model import settings

PROFILE = "https://w3id.org/ro/crate/1.2"
CONTEXT = "https://w3id.org/ro/crate/1.2/context"


def crate(record: Record) -> dict:
    found = documents.linked(record)
    linked = set()
    for value in found.objects():
        if isinstance(value, URIRef) and (value, SDO.name, None) in found and value != URIRef(record.iri):
            linked.add(str(value))
    found += documents.public(storage.graph(sorted(linked)))
    root = URIRef(record.iri + "/")
    found.add((root, RDF.type, SDO.Dataset))
    found.add((root, SDO.mainEntity, URIRef(record.iri)))
    for field in (SDO.name, SDO.description, SDO.license, SDO.datePublished):
        for value in found.objects(URIRef(record.iri), field):
            found.add((root, field, value))
    own = documents.context(settings())
    expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
    flattened = jsonld.flatten(expanded, own)
    entities = [{"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "conformsTo": {"@id": PROFILE}, "about": {"@id": str(root)}}]
    entities += flattened.get("@graph", [])
    extension = {}
    for name, value in own.items():
        if name != "@vocab":
            extension[name] = value
    return {"@context": [CONTEXT, extension], "@graph": entities}
