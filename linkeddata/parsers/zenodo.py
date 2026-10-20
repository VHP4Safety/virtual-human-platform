"""Parser of the Zenodo community vhp4safety, a workaround (see linkeddata/parsers).

Source: the dataset search, with the metadata of each record.

- Creators: write "Last, First" as "First Last", as in other sources.
- Links: DOIs, ORCID iDs, licences, and affiliations as organisations.
- DOI: the address of the record elsewhere if Zenodo registered it, and else a cited publication.
- Files: the downloads of the record, with names, sizes and checksums, in the form of the Zenodo JSON-LD export.
- Authors: in their order, as a list.
- Version, and grants as funding: a grant row with title, acronym, number, project page and funder."""

import json
import mimetypes

from linkeddata.parsers import licence, link, marked, present, publication, slug, term, web_link

DATE = "http://www.w3.org/2001/XMLSchema#date"
LICENSES = "https://zenodo.org/api/vocabularies/licenses/"


# Zenodo licence identifiers that are not SPDX identifiers.
LICENCES = {"cc-zero": "CC0-1.0"}


def size(given: int) -> str:
    """Return the size of a file as shown by Zenodo, such as 3.1 MB."""
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if given >= scale:
            return f"{given / scale:.1f} {unit}"
    return f"{given} bytes"


def download(given: dict) -> dict:
    """Return a file of a Zenodo record at its download address, with its format from its name, as in the JSON-LD
    export of Zenodo, and its checksum (md5:..., as Zenodo gives it) in SPDX terms."""
    found = {"@type": "DataDownload", "name": given["key"], "contentUrl": link(given["links"]["self"]), "contentSize": size(given["size"])}
    media, _ = mimetypes.guess_type(given["key"])
    if media:
        found["encodingFormat"] = media
    algorithm, _, checksum = str(given.get("checksum") or "").partition(":")
    if checksum:
        found["spdx:checksum"] = {"@type": "spdx:Checksum", "spdx:algorithm": {"@id": "spdx:checksumAlgorithm_" + algorithm}, "spdx:checksumValue": checksum}
    return found


def doi_of(row: dict, hit: dict, others: dict) -> None:
    """Add the DOI of a Zenodo record to its row: as its address elsewhere if Zenodo registered the DOI
    (10.5281/zenodo.*), and else as a cited publication. A depositor can give the DOI of an article in place of a
    DOI of the record."""
    # A DOI that Zenodo hides (10.5281/zenodo.***) is no DOI.
    if not present(hit.get("doi")) or "*" in str(hit["doi"]):
        return
    if str(hit["doi"]).startswith("10.5281/"):
        row["sameAs"] = link("https://doi.org/" + hit["doi"])
        row["identifier"] = link("https://doi.org/" + hit["doi"])
        return
    cited = publication(hit["doi"])
    if cited:
        others.setdefault(cited["@id"], cited)
        if link(cited["@id"]) not in row.setdefault("citation", []):
            row["citation"].append(link(cited["@id"]))


def grant_row(row: dict, grant: dict, others: dict) -> None:
    """Add a grant of a Zenodo record to its funding, as a grant row: its title, acronym, number, project page and
    funder."""
    if not present(grant.get("code")):
        return
    address = "grants/" + slug(grant["code"])
    found = others.setdefault(address, {"@id": address, "@type": "MonetaryGrant", "name": grant.get("title") or grant["code"], "identifier": grant["code"]})
    if present(grant.get("acronym")):
        found["alternateName"] = grant["acronym"]
    if present(grant.get("url")):
        found["url"] = web_link(grant["url"])
    funder = (grant.get("funder") or {}).get("name")
    if present(funder):
        organisation = "organizations/" + slug(funder)
        others.setdefault(organisation, {"@id": organisation, "@type": "Organization", "name": funder})
        found["funder"] = link(organisation)
    row.setdefault("funding", []).append(link(address))


def parse(content: bytes) -> list[dict]:
    found = json.loads(content)["hits"]
    if found["total"] > len(found["hits"]):
        raise ValueError("more datasets than one search page")
    rows = []
    others = {}
    for hit in found["hits"]:
        metadata = hit["metadata"]
        row = {"@id": f"data/{hit['id']}", "@type": "Dataset", "name": metadata.get("title"), "isBasedOn": link(hit["links"]["self_html"])}
        if present(metadata.get("description")):
            row["description"] = marked(metadata["description"])
        if present(metadata.get("publication_date")):
            row["datePublished"] = {"@value": metadata["publication_date"], "@type": DATE}
        doi_of(row, hit, others)
        for keyword in metadata.get("keywords") or []:
            if present(keyword):
                row.setdefault("keywords", []).append(term(keyword, "glossary"))
        if isinstance(metadata.get("license"), dict) and present(metadata["license"].get("id")):
            given = licence(LICENCES.get(metadata["license"]["id"], metadata["license"]["id"]))
            row["license"] = given if isinstance(given, dict) else link(LICENSES + metadata["license"]["id"])
        authors = []
        for creator in metadata.get("creators") or []:
            if not present(creator.get("name")):
                continue
            last, _, first = str(creator["name"]).partition(", ")
            name = f"{first} {last}" if first else last
            person = "people/" + slug(name)
            found_person = others.setdefault(person, {"@id": person, "@type": "Person", "name": name})
            if present(creator.get("orcid")):
                found_person["sameAs"] = link("https://orcid.org/" + creator["orcid"])
            if present(creator.get("affiliation")):
                organisation = "organizations/" + slug(creator["affiliation"])
                others.setdefault(organisation, {"@id": organisation, "@type": "Organization", "name": creator["affiliation"]})
                found_person["affiliation"] = link(organisation)
            authors.append(link(person))
        # The authors are kept in their order, as a list.
        if authors:
            row["creator"] = {"@list": authors}
        # Each related DOI is a linked publication, whatever the relation. The DOIs of the record are left out.
        own = {str(hit.get("doi")), str(hit.get("conceptdoi"))}
        for related in metadata.get("related_identifiers") or []:
            if related.get("scheme") == "doi" and related.get("identifier") not in own:
                cited = publication(related.get("identifier", ""))
                if cited:
                    others.setdefault(cited["@id"], cited)
                    row.setdefault("citation", []).append(link(cited["@id"]))
        if present(metadata.get("version")):
            row["version"] = metadata["version"]
        for grant in metadata.get("grants") or []:
            grant_row(row, grant, others)
        # The files are kept in their order.
        for given in hit.get("files") or []:
            row.setdefault("distribution", []).append({**download(given), "position": len(row.get("distribution", [])) + 1})
        rows.append(row)
    return rows + list(others.values())
