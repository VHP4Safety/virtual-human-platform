"""Parser of NWO's open project data (NWOpen API, CC0; a workaround, see linkeddata/parsers): each followed project,
by the platform's address of its grant. The grant takes the project's title, identifier and award (in euros), and
NWO as its funder, with NWO's ROR and funder DOI as the API states them; each output with a DOI is a publication
funded by the grant."""

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
        funder = {"@id": "organizations/" + slug(FUNDER), "@type": "Organization", "name": FUNDER, "same_as": []}
        for identifier in (meta.get("ror_id"), meta.get("funder")):
            if present(identifier):
                funder["same_as"].append(link(identifier))
        others[funder["@id"]] = funder
        for project in found.get("projects") or []:
            grant = {"@id": address, "@type": "Grant", "name": project.get("title"), "identifier": project.get("project_id"),
                     "funder": link(funder["@id"])}
            if present(project.get("award_amount")):
                grant["amount"] = {"@type": "Amount", "value": {"@value": str(project["award_amount"]), "@type": DECIMAL}, "currency": "EUR"}
            rows.append(grant)
            for output in project.get("products") or []:
                article = publication(str(output.get("url_open_access") or "").replace("https://www.doi.org/", "https://doi.org/"))
                if article is None:
                    continue
                article = others.setdefault(article["@id"], article)
                if present(output.get("title")):
                    article.setdefault("title", output["title"])
                if present(output.get("year")):
                    article.setdefault("year", {"@value": str(output["year"]), "@type": DATE})
                article.setdefault("grants", []).append(link(address))
    return rows + list(others.values())
