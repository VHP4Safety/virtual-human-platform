"""Parser of the Zenodo community vhp4safety (a workaround, see linkeddata/parsers): the dataset search
gives each record's metadata. "Last, First" creators are written "First Last", as in other sources; DOIs,
ORCID iDs, licenses and affiliations (as organisations) are linked at their addresses."""

import json

from linkeddata.parsers import licence, link, marked, present, publication, slug, term

DATE = "http://www.w3.org/2001/XMLSchema#date"
LICENSES = "https://zenodo.org/api/vocabularies/licenses/"


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
        if present(hit.get("doi")):
            row["sameAs"] = link("https://doi.org/" + hit["doi"])
            row["identifier"] = link("https://doi.org/" + hit["doi"])
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
        rows.append(row)
    return rows + list(others.values())
