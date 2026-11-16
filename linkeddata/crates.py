"""RO-Crates of the models."""

from pathlib import Path

from pyld import jsonld
from rdflib import RDF, Literal, URIRef
from rdflib.namespace import SDO
from rocrate.rocrate import ROCrate

import database
from database import records
from database.tables import PLATFORM, Record
from linkeddata import documents, void
from linkeddata.profile import settings

PROFILE = "https://w3id.org/ro/crate/1.2"
ARTIFACT = "https://platform.vhp4safety.nl/model/v1/pbpk#artifactLocation"


def kept() -> Path:
    """Return the folder of the crates kept at import."""
    return database.STATE_DIR / "crates"


def of_models(record: Record | None) -> bool:
    """Return True if the record is a model that is not removed or moved."""
    return (record is not None and not record.removed_at and not record.moved_to
            and record.type in records.within(settings()["kinds"]["models"]))


def zenodo(record: Record) -> bytes | None:
    """Return the Zenodo crate of an imported model, or None."""
    if record.source == PLATFORM:
        return None
    source = str(records.graph([record.iri]).value(URIRef(record.iri), SDO.isBasedOn) or "")
    if not source.startswith("https://zenodo.org/records/"):
        return None
    copy = kept() / f"{source.rstrip('/').rsplit('/', 1)[-1]}.json"
    return copy.read_bytes() if copy.is_file() else None


def file_name(record: Record) -> str:
    """Return the file name of the detached crate of a record."""
    return records.path(record.iri).rsplit("/", 1)[-1] + "-ro-crate-metadata.json"


def crate(record: Record) -> dict:
    """Return the draft crate of a model."""
    node = URIRef(record.iri)
    found = documents.public(records.graph([record.iri]))
    referred = sorted({str(value) for _, predicate, value in found
                       if predicate != RDF.type and isinstance(value, URIRef) and (value, SDO.name, None) not in found})
    # The licence of the metadata file is named too, as a creative work, as RO-Crate asks of a licence.
    if void.platform()["license"] and (URIRef(void.platform()["license"]), SDO.name, None) not in found:
        referred.append(void.platform()["license"])
        found.add((URIRef(void.platform()["license"]), RDF.type, SDO.CreativeWork))
    classes = {}
    for linked in records.kept(referred):
        classes[linked.iri] = linked.type
    for iri, name in records.names(referred).items():
        if not name:
            continue
        if found.value(URIRef(iri), RDF.type) is None:
            found.add((URIRef(iri), RDF.type, URIRef(classes.get(iri, str(SDO.DefinedTerm)))))
        found.add((URIRef(iri), SDO.name, Literal(name)))
    # The files of the model are data entities at their addresses.
    files = []
    for part in list(found.objects(node, SDO.hasPart)):
        address = found.value(part, URIRef(ARTIFACT)) or found.value(part, SDO.contentUrl)
        if address is None or not str(address).startswith(("https://", "http://")):
            continue
        for predicate, value in found.predicate_objects(part):
            if predicate not in (RDF.type, URIRef(ARTIFACT), SDO.contentUrl):
                found.add((URIRef(str(address)), predicate, value))
        found.add((URIRef(str(address)), RDF.type, SDO.MediaObject))
        found.remove((node, SDO.hasPart, part))
        found.remove((part, None, None))
        found.add((node, SDO.hasPart, URIRef(str(address))))
        files.append(str(address))
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
    entities = jsonld.flatten(expanded, own).get("@graph", [])
    local = {}
    for entity in entities:
        if entity["@id"].startswith("_:"):
            local[entity["@id"]] = f"#part-{len(local) + 1}"
    for entity in entities:
        entity = relabelled(entity, local)
        types = entity.get("@type", [])
        types = types if isinstance(types, list) else [types]
        if entity["@id"] in files or entity["@id"] == record.iri:
            made.add_file(entity["@id"], properties={**entity, "@type": ["File", *types]})
        # A tool without a known version is linked by address only, as a version is required by RO-Crate for each
        # SoftwareApplication.
        elif "SoftwareApplication" in types and "softwareVersion" not in entity and entity["@id"].startswith("http"):
            continue
        else:
            if "softwareVersion" in entity:
                entity.setdefault("version", entity["softwareVersion"])
            made.add_jsonld(entity)
    root["mainEntity"] = {"@id": record.iri}
    root["creativeWorkStatus"] = "Draft"
    name = str(found.value(node, SDO.name) or record.name or record.iri)
    root["name"] = name
    by = publisher.name if publisher is not None else "the platform"
    root["description"] = str(found.value(node, SDO.description) or f"Draft RO-Crate of {name}, made by {by} from its record.")
    if found.value(node, SDO.license) is not None:
        root["license"] = {"@id": str(found.value(node, SDO.license))}
    root["datePublished"] = str(found.value(node, SDO.datePublished) or record.updated_at[:10])
    if publisher is not None:
        root["publisher"] = {"@id": publisher.iri}
    if void.platform()["license"]:
        made.metadata["license"] = {"@id": void.platform()["license"]}
    return made.metadata.generate()


def relabelled(value, local: dict):
    """Return a JSON-LD value with local addresses for the nodes without an address."""
    if isinstance(value, dict):
        return {key: (local.get(given, given) if key == "@id" else relabelled(given, local)) for key, given in value.items()}
    if isinstance(value, list):
        return [relabelled(given, local) for given in value]
    return value
