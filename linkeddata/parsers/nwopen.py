"""Parser of the open project data of NWO."""

import json

from linkeddata.parsers import link, present, publication, slug

# The funder of every project of NWO's API.
FUNDER = "Dutch Research Council (NWO)"
DATE = "http://www.w3.org/2001/XMLSchema#gYear"
DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    others = {}
    for address, content in contents.items():
        found = json.loads(content)
        meta = found.get("meta") or {}
        funder = {"@id": "organizations/" + slug(FUNDER), "@type": "Organization", "name": FUNDER, "sameAs": []}
        for identifier in (meta.get("ror_id"), meta.get("funder")):
            if present(identifier):
                funder["sameAs"].append(link(identifier))
        others[funder["@id"]] = funder
        for project in found.get("projects") or []:
            grant = {"@id": address, "@type": "MonetaryGrant", "name": project.get("title"), "identifier": project.get("project_id"),
                     "funder": link(funder["@id"])}
            if present(project.get("award_amount")):
                grant["amount"] = {"@type": "MonetaryAmount", "value": {"@value": str(project["award_amount"]), "@type": DECIMAL}, "currency": "EUR"}
            rows.append(grant)
            for output in project.get("products") or []:
                article = publication(str(output.get("url_open_access") or "").replace("https://www.doi.org/", "https://doi.org/"))
                if article is None:
                    continue
                article = others.setdefault(article["@id"], article)
                if present(output.get("title")):
                    article.setdefault("name", output["title"])
                if present(output.get("year")):
                    article.setdefault("datePublished", {"@value": str(output["year"]), "@type": DATE})
                article.setdefault("funding", []).append(link(address))
    return rows + list(others.values())
