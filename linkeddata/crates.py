"""Detached RO-Crate 1.2 (https://w3id.org/ro/crate/1.2) of each record, at <record address>/ro-crate-metadata.json,
made with ro-crate-py.

- Root: at the record address with /ro-crate/. Take the name, description, licence and publication date from the
  record. If they are missing, use the licence of the platform records and the date of the last change. Use the
  publisher of the platform as the publisher.
- Main entity: the record, with its parts.
- Other entities: the linked people, organisations, publications, grants and terms, with their public data.
- Datasets: add them also to the parts of the root.
- Files: link them at their location, such as Zenodo or GitHub. Do not copy them.
- Names: use the JSON-LD names of the platform, with the RO-Crate context and the prefixes of the platform."""

from pyld import jsonld
from rdflib import RDF, Literal, URIRef
from rdflib.namespace import SDO
from rocrate.rocrate import ROCrate

from database import records
from database.tables import Record
from linkeddata import documents, void
from linkeddata.profile import settings

PROFILE = "https://w3id.org/ro/crate/1.2"


def crate(record: Record) -> dict:
    found = documents.linked(record)
    node = URIRef(record.iri)
    linked = set()
    for value in found.objects():
        if isinstance(value, URIRef) and (value, SDO.name, None) in found and value != node:
            linked.add(str(value))
    found += documents.public(records.with_names(records.graph(sorted(linked))))
    publisher = records.get(void.platform()["publisher"]["@id"]) if void.platform()["publisher"] else None
    if publisher is not None:
        # A project is an organisation, and the Organization type of the publisher is required by RO-Crate.
        for kind in (publisher.type, str(SDO.Organization)):
            found.add((URIRef(publisher.iri), RDF.type, URIRef(kind)))
        found.add((URIRef(publisher.iri), SDO.name, Literal(publisher.name or publisher.iri)))
    own = documents.context(settings())
    expanded = jsonld.from_rdf(found.serialize(format="nt"), {"format": "application/n-quads"})
    made = ROCrate(version="1.2", root_dataset_id=record.iri + "/ro-crate/")
    made.metadata.extra_terms = {name: value for name, value in own.items() if name != "@vocab"}
    root = made.root_dataset
    for entity in jsonld.flatten(expanded, own).get("@graph", []):
        types = entity.get("@type", [])
        types = types if isinstance(types, list) else [types]
        if entity["@id"] == record.iri:
            made.add_file(record.iri, properties={**entity, "@type": ["File", *types]})
        # A tool without a known version is linked by address only, as a version is required by RO-Crate for each
        # SoftwareApplication.
        elif "SoftwareApplication" in types and "softwareVersion" not in entity and entity["@id"].startswith("http"):
            continue
        else:
            if "softwareVersion" in entity:
                entity.setdefault("version", entity["softwareVersion"])
            added = made.add_jsonld(entity)
            # A dataset is a data entity, so it is added to the parts of the root.
            if "Dataset" in types:
                root.append_to("hasPart", added)
    root["mainEntity"] = {"@id": record.iri}
    for name in ("name", "description", "license"):
        given = found.value(node, SDO[name])
        if given is not None:
            root[name] = {"@id": str(given)} if isinstance(given, URIRef) else str(given)
    if root.get("license") is None and void.platform()["license"]:
        root["license"] = {"@id": void.platform()["license"]}
    root["datePublished"] = str(found.value(node, SDO.datePublished) or record.updated_at[:10])
    if publisher is not None:
        root["publisher"] = {"@id": publisher.iri}
    return made.metadata.generate()
