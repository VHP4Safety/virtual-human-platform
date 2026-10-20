"""Parser of the Zenodo community vhp4safety, a workaround (see linkeddata/parsers).

Source: the dataset search, with the metadata of each record.

- Creators: write "Last, First" as "First Last", as in other sources.
- Links: DOIs, ORCID iDs, licences, and affiliations as organisations.
- DOI: the address of the record elsewhere if Zenodo registered it, and else a cited publication.
- Files: the downloads of the record, with names and sizes, in the form of the Zenodo JSON-LD export."""

import json
import mimetypes

from linkeddata.parsers import licence, link, marked, present, publication, slug, term

DATE = "http://www.w3.org/2001/XMLSchema#date"
LICENSES = "https://zenodo.org/api/vocabularies/licenses/"


def size(given: int) -> str:
    """Return the size of a file as shown by Zenodo, such as 3.1 MB."""
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if given >= scale:
            return f"{given / scale:.1f} {unit}"
    return f"{given} bytes"


def download(given: dict) -> dict:
    """Return a file of a Zenodo record at its download address, with its format from its name, as in the JSON-LD
    export of Zenodo."""
    found = {"@type": "DataDownload", "name": given["key"], "contentUrl": link(given["links"]["self"]), "contentSize": size(given["size"])}
    media, _ = mimetypes.guess_type(given["key"])
    if media:
        found["encodingFormat"] = media
    return found


def doi_of(row: dict, hit: dict, others: dict) -> None:
    """Add the DOI of a Zenodo record to its row: as its address elsewhere if Zenodo registered the DOI
    (10.5281/zenodo.*), and else as a cited publication. A depositor can give the DOI of an article in place of a
    DOI of the record."""
    if not present(hit.get("doi")):
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
            given = licence(metadata["license"]["id"])
            row["license"] = given if isinstance(given, dict) else link(LICENSES + metadata["license"]["id"])
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
            row.setdefault("creator", []).append(link(person))
        for related in metadata.get("related_identifiers") or []:
            if related.get("scheme") == "doi" and related.get("relation") in ("references", "cites", "isSupplementTo", "isDescribedBy"):
                cited = publication(related.get("identifier", ""))
                if cited:
                    others.setdefault(cited["@id"], cited)
                    row.setdefault("citation", []).append(link(cited["@id"]))
        for given in hit.get("files") or []:
            row.setdefault("distribution", []).append(download(given))
        rows.append(row)
    return rows + list(others.values())
