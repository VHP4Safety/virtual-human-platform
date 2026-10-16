"""Parser of the Zenodo community vhp4safety (a workaround, see linkeddata/parsers): the search of the
community's datasets gives the metadata of each record. A creator written "Last, First" is written
"First Last", as the other sources write people; the codes of DOIs, ORCID iDs and licenses are put at their
addresses, and so are the creators' affiliations, as organisations."""

import json

from linkeddata.parsers import link, present, publication, slug

DATE = "http://www.w3.org/2001/XMLSchema#date"
LICENSES = "https://zenodo.org/api/vocabularies/licenses/"


def parse(content: bytes) -> list[dict]:
    found = json.loads(content)["hits"]
    if found["total"] > len(found["hits"]):
        raise ValueError("the community has more datasets than one page of its search")
    rows = []
    others = {}
    for hit in found["hits"]:
        metadata = hit["metadata"]
        row = {"@id": f"data/{hit['id']}", "@type": "Dataset", "title": metadata.get("title"), "page": link(hit["links"]["self_html"])}
        if present(metadata.get("description")):
            row["description"] = metadata["description"]
        if present(metadata.get("publication_date")):
            row["published"] = {"@value": metadata["publication_date"], "@type": DATE}
        if present(hit.get("doi")):
            row["doi"] = link("https://doi.org/" + hit["doi"])
        if metadata.get("keywords"):
            row["keywords"] = metadata["keywords"]
        if isinstance(metadata.get("license"), dict) and present(metadata["license"].get("id")):
            row["license"] = link(LICENSES + metadata["license"]["id"])
        for creator in metadata.get("creators") or []:
            if not present(creator.get("name")):
                continue
            last, _, first = str(creator["name"]).partition(", ")
            name = f"{first} {last}" if first else last
            person = "people/" + slug(name)
            found_person = others.setdefault(person, {"@id": person, "@type": "Person", "name": name})
            if present(creator.get("orcid")):
                found_person["same_as"] = link("https://orcid.org/" + creator["orcid"])
            if present(creator.get("affiliation")):
                organisation = "organizations/" + slug(creator["affiliation"])
                others.setdefault(organisation, {"@id": organisation, "@type": "Organization", "name": creator["affiliation"]})
                found_person["affiliation"] = link(organisation)
            row.setdefault("creators", []).append(link(person))
        for related in metadata.get("related_identifiers") or []:
            if related.get("scheme") == "doi" and related.get("relation") in ("references", "cites", "isSupplementTo", "isDescribedBy"):
                cited = publication(related.get("identifier", ""))
                if cited:
                    others.setdefault(cited["@id"], cited)
                    row.setdefault("references", []).append(link(cited["@id"]))
        rows.append(row)
    return rows + list(others.values())
