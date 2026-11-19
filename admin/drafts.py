"""Draft terms: the status of a term that waits for its vocabulary, and its contributors, the people who wrote it."""

import re

import requests
from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, SDO, VOID

import database
from admin import tokens, writes
from admin.editor import GLOSSARY_TABLE
from database import records

# The namespace of the VHP4Safety glossary. A new term of the record editor is a draft term of the glossary.
GLOSSARY = "https://vhp4safety.github.io/glossary#"
PERSON = str(SDO.Person)
GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z\d](?:[A-Za-z\d-]{0,38}))/?$")
# The fields of the text of a term. A writer who changes one of them is a contributor. A writer who only sets the
# identifier of a draft, as the glossary repository does with its term code and its glossary address, is not.
TEXT = [SDO.name, SDO.description, SDO.alternateName, SDO.inDefinedTermSet, GLOSSARY_TABLE, RDFS.isDefinedBy]


def kept_nodes(of_class: str, path: str, wanted: list[str]) -> list[str]:
    """Return the addresses of the records of of_class with one of the wanted values of a field, without the removed and
    moved records and the parts."""
    with database.engine().connect() as connection:
        found = sorted(connection.execute(records.nodes_with(of_class, path, wanted)).scalars())
    return sorted(record.iri for record in records.kept(found) if record.part_of is None)


def vocabulary(namespace: str) -> str | None:
    """Return the address of the vocabulary record with the namespace, or None."""
    found = kept_nodes(str(SDO.DefinedTermSet), str(VOID.uriSpace), [namespace])
    return found[0] if found else None


def person(orcid: str | None) -> str | None:
    """Return the address of the person record with the ORCID iD, or None. Only the ORCID iD is compared, never the name,
    as ORCID checks the iD of a sign-in, and a write token is made only after a sign-in."""
    if not orcid:
        return None
    found = kept_nodes(PERSON, str(SDO.sameAs), [f"https://orcid.org/{orcid}"])
    return found[0] if found else None


def github(orcid: str) -> str | None:
    """Return the GitHub account in the public ORCID record of the ORCID iD, or None if it has none or cannot be read."""
    address = tokens.orcid_base().replace("://", "://pub.", 1) + f"/v3.0/{orcid}/researcher-urls"
    try:
        response = requests.get(address, headers={"Accept": "application/json"}, timeout=10)
        listed = (response.json().get("researcher-url") or []) if response.ok else []
    except (requests.RequestException, ValueError):
        return None
    for url in listed:
        matched = GITHUB.match(str(((url or {}).get("url") or {}).get("value") or "").strip())
        if matched:
            return "https://github.com/" + matched.group(1)
    return None


def own_person(who) -> str | None:
    """Return the person record of the writer, by the ORCID iD of the sign-in or of the write token. If no person record
    has the ORCID iD, add one with the name of the sign-in, the ORCID iD, and the GitHub account of the public ORCID
    record. A person record of the same name without the ORCID iD is not used, as a name does not identify a person."""
    if not who.orcid:
        return None
    found = person(who.orcid)
    if found is not None:
        return found
    same_as = [f"https://orcid.org/{who.orcid}"] + [account for account in [github(who.orcid)] if account]
    name = who.name or who.orcid
    address = writes.free(records.address(f"people/{writes.slug(name)}"), set())
    writes.save(writes.document(PERSON, address, {"name": name, "sameAs": [{"@id": one} for one in same_as]}), PERSON, who.name, who.orcid)
    return address


def drafted(found: Graph, address: str, who, stored: bool) -> None:
    """Set the status and the contributors of the term at address in found.

    A term at a platform address in a vocabulary of another namespace, such as the glossary, is not yet in its
    vocabulary, so it is a draft. The contributors of a draft are its stored contributors and the writer if the writer
    changes its text, so that a draft is not credited to a person who did not write it. The person of the writer is
    added only if stored is True, not for a preview."""
    node = URIRef(address)
    if (node, RDF.type, SDO.DefinedTerm) not in found:
        return
    of_set = found.value(node, SDO.inDefinedTermSet)
    space = records.graph([str(of_set)]).value(of_set, VOID.uriSpace) if isinstance(of_set, URIRef) else None
    outside = space is not None and records.path(str(space)) == str(space)
    if outside and records.path(address) != address and found.value(node, SDO.creativeWorkStatus) is None:
        found.add((node, SDO.creativeWorkStatus, Literal("Draft")))
    if str(found.value(node, SDO.creativeWorkStatus) or "") != "Draft":
        return
    kept = records.graph([address]) if records.get(address) is not None else Graph()
    before = set(kept.objects(node, DCTERMS.contributor))
    for value in list(found.objects(node, DCTERMS.contributor)):
        if value not in before:
            found.remove((node, DCTERMS.contributor, value))
            if isinstance(value, BNode):
                found.remove((value, None, None))
    if all(set(found.objects(node, field)) == set(kept.objects(node, field)) for field in TEXT):
        return
    writer = own_person(who) if stored else person(who.orcid)
    if writer is not None:
        found.add((node, DCTERMS.contributor, URIRef(writer)))
