"""A record as a detached RO-Crate 1.2 (https://w3id.org/ro/crate/1.2), at <record's address>/ro-crate-metadata.json,
made with ro-crate-py: the crate's root is the record's address followed by /ro-crate/, its main entity the record (a
file on the web, at its address), with its parts; the people, organisations, publications, grants and terms it
links to are entities of the crate, as their public data gives them. The root takes the record's name, description,
license and date of publication (else its last change), and is published by the platform's publisher. Files are
linked where they are (such as Zenodo or GitHub), not copied. Names are the platform's JSON-LD names (schema.org's
unprefixed; pbpk: for the PBPK terms of ROBOT's form), under RO-Crate's context and the platform's prefixes."""

from pyld import jsonld
from rdflib import RDF, Literal, URIRef
from rdflib.namespace import SDO
from rocrate.rocrate import ROCrate

from database import records
from database.tables import Record
from linkeddata import documents, storage, void
from linkeddata.model import settings

PROFILE = "https://w3id.org/ro/crate/1.2"


def crate(record: Record) -> dict:
    found = documents.linked(record)
    node = URIRef(record.iri)
    linked = set()
    for value in found.objects():
        if isinstance(value, URIRef) and (value, SDO.name, None) in found and value != node:
            linked.add(str(value))
    found += documents.public(storage.with_names(storage.graph(sorted(linked))))
    publisher = records.get(void.platform()["publisher"]["@id"]) if void.platform()["publisher"] else None
    if publisher is not None:
        # A project is an organisation; RO-Crate asks for the publisher's type to say so.
        for kind in (publisher.type, str(SDO.Organization)):
            found.add((URIRef(publisher.iri), RDF.type, URIRef(kind)))
        found.add((URIRef(publisher.iri), SDO.name, Literal(publisher.name or publisher.iri)))
    own = documents.context(settings())
    expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
    made = ROCrate(version="1.2", root_dataset_id=record.iri + "/ro-crate/")
    made.metadata.extra_terms = {name: value for name, value in own.items() if name != "@vocab"}
    for entity in jsonld.flatten(expanded, own).get("@graph", []):
        if entity["@id"] == record.iri:
            types = entity["@type"] if isinstance(entity["@type"], list) else [entity["@type"]]
            made.add_file(record.iri, properties={**entity, "@type": ["File", *types]})
        else:
            made.add_jsonld(entity)
    root = made.root_dataset
    root["mainEntity"] = {"@id": record.iri}
    for name in ("name", "description", "license"):
        given = found.value(node, SDO[name])
        if given is not None:
            root[name] = {"@id": str(given)} if isinstance(given, URIRef) else str(given)
    root["datePublished"] = str(found.value(node, SDO.datePublished) or record.updated_at[:10])
    if publisher is not None:
        root["publisher"] = {"@id": publisher.iri}
    return made.metadata.generate()
