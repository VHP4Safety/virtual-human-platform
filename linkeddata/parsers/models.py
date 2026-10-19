"""Parser of the models of the Zenodo community vhp4safety (a workaround, see linkeddata/parsers): the record search
gives each model's record, and its RO-Crate (the zip whose name says "ro-crate") gives the model's own metadata
(ro-crate-metadata.json) and, where its makers wrote one, a curated PBPK description (pbpk-model-metadata.json).
- A model is at models/<name>, its name being the crate's ("oppbkmodelr" for oppbkmodelr-ro-crate-v1.0.1.zip).
- From the record: its creators (as Zenodo gives them), DOI, keywords, license, date and page. From the crate's
  main entity (the first, when a crate has several): its name, description, version, repository, languages,
  runtime, requirements, publications (DOIs), grants (by their number, as the platform's grant records are named)
  and topics (ontology terms); the crate's own name and description when it has several models.
- From the PBPK description, ROBOT's fields: the intended use, the kind of model and its mathematical
  representation, the species as biological systems, the compartments, and the model's structure (its processes,
  routes, inputs and outputs) as lists."""

import html
import json
import re

from linkeddata.parsers import licence, link, marked, present, publication, slug, term

DATE = "http://www.w3.org/2001/XMLSchema#date"
CRATE = re.compile(r"(.+?)-ro-crate", re.IGNORECASE)
# The PBPK description's lists that tell the model's structure, by their heading.
STRUCTURE = {"processes": "Processes", "exposure_routes": "Exposure routes", "modelled_entity_classes": "Modelled entities",
             "partition_methods": "Partition coefficient methods", "inputs": "Inputs", "outputs": "Outputs"}


def crate_of(hit: dict) -> dict | None:
    for found in hit.get("files") or []:
        if "ro-crate" in found["key"].lower() and found["key"].lower().endswith(".zip"):
            return found
    return None


def packages(index: bytes) -> dict[str, str]:
    """Each model record's crate zip, by the record's identifier."""
    found = {}
    for hit in json.loads(index)["hits"]["hits"]:
        crate = crate_of(hit)
        if crate is not None:
            found[str(hit["id"])] = crate["links"]["self"]
    return found


def nodes_of(crate: dict) -> dict:
    found = {}
    for node in crate.get("@graph") or []:
        found[node.get("@id")] = node
    return found


def listed(value) -> list:
    return value if isinstance(value, list) else [value] if value else []


def named(nodes: dict, value) -> str:
    """A crate node's name and version ("R 4.1.0"), or a text as it is."""
    if isinstance(value, dict):
        node = nodes.get(value.get("@id"), {})
        version = str(node.get("version") or "")
        return (str(node.get("name") or value.get("@id")) + (" " + version if version and "unreported" not in version else "")).strip()
    return str(value)


def structure(model: dict) -> str:
    parts = []
    for key, heading in STRUCTURE.items():
        values = [str(value) for value in listed(model.get(key)) if present(value)]
        if values:
            parts.append(f"<p>{heading}:</p><ul>" + "".join(f"<li>{html.escape(value)}</li>" for value in values) + "</ul>")
    if present(model.get("exposure_pattern")):
        parts.append(f"<p>Exposure pattern: {html.escape(str(model['exposure_pattern']))}</p>")
    return "".join(parts)


def pbpk(row: dict, described: dict) -> None:
    """ROBOT's fields from a curated PBPK description."""
    model = described.get("model") or {}
    if present(model.get("purpose")):
        row["purpose"] = model["purpose"]
    kinds = [str(kind) for kind in listed(model.get("model_type")) if present(kind)]
    if kinds:
        row["category"] = kinds[0]
        if any("ordinary differential equation" in kind.lower() for kind in kinds):
            row["representation"] = "Ordinary differential equations"
    for species in listed(model.get("species")):
        if present(species):
            row.setdefault("systems", []).append({"@type": "BiologicalSystem", "species": str(species)})
    for compartment in listed(model.get("systemic_compartments")) + listed(model.get("gastrointestinal_structure")):
        if present(compartment):
            row.setdefault("compartments", []).append({"@type": "Compartment", "name": str(compartment)})
    if structure(model):
        row["structure"] = marked(structure(model))


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    others = {}
    for hit in json.loads(contents["models"])["hits"]["hits"]:
        crate_file = crate_of(hit)
        key = str(hit["id"])
        if crate_file is None or f"{key}/ro-crate-metadata.json" not in contents:
            continue
        crate = json.loads(contents[f"{key}/ro-crate-metadata.json"])
        nodes = nodes_of(crate)
        root = nodes.get("./", {})
        mains = listed(root.get("mainEntity"))
        model = nodes.get(mains[0].get("@id"), {}) if mains else {}
        given = model if len(mains) == 1 else root
        found = CRATE.match(crate_file["key"])
        metadata = hit["metadata"]
        row = {"@id": "models/" + slug(found.group(1) if found else given.get("name") or metadata["title"]), "@type": "Model",
               "name": given.get("name") or metadata["title"], "page": link(hit["links"]["self_html"])}
        for field, value in (("description", given.get("description")), ("version", given.get("version") or root.get("version"))):
            if present(value):
                row[field] = value
        if present(hit.get("doi")):
            row["doi"] = link("https://doi.org/" + hit["doi"])
        if present(metadata.get("publication_date")):
            row["published"] = {"@value": metadata["publication_date"], "@type": DATE}
        for keyword in metadata.get("keywords") or []:
            if present(keyword):
                row.setdefault("keywords", []).append(term(keyword, "glossary"))
        if isinstance(metadata.get("license"), dict) and present(metadata["license"].get("id")):
            row["license"] = licence(metadata["license"]["id"])
        for repository in listed(model.get("codeRepository")):
            address = repository.get("@id") if isinstance(repository, dict) else repository
            if present(address):
                row.setdefault("repositories", []).append(link(address))
        for language in listed(model.get("programmingLanguage")):
            node = nodes.get(language.get("@id"), {}) if isinstance(language, dict) else {}
            row.setdefault("languages", []).append(str(node.get("name") or language.get("@id")) if isinstance(language, dict) else str(language))
        if present(model.get("runtimePlatform")):
            row["runtime"] = str(model["runtimePlatform"])
        for requirement in listed(model.get("softwareRequirements")):
            row.setdefault("requirements", []).append(named(nodes, requirement))
        for topic in listed(model.get("about")):
            if isinstance(topic, dict) and str(topic.get("@id", "")).startswith(("http://", "https://")):
                row.setdefault("topics", []).append(link(topic["@id"]))
        for cited in listed(model.get("citation")) + listed(root.get("citation")):
            article = publication(cited.get("@id", "") if isinstance(cited, dict) else cited)
            if article and link(article["@id"]) not in row.get("references", []):
                others.setdefault(article["@id"], article)
                row.setdefault("references", []).append(link(article["@id"]))
        for funding in listed(model.get("funding")) + listed(root.get("funding")):
            grant = nodes.get(funding.get("@id"), {}) if isinstance(funding, dict) else {}
            if present(grant.get("identifier")):
                address = "grants/" + slug(str(grant["identifier"]))
                found_grant = others.setdefault(address, {"@id": address, "@type": "Grant", "name": grant.get("name") or grant["identifier"],
                                                           "identifier": str(grant["identifier"])})
                if isinstance(grant.get("url"), dict):
                    found_grant["url"] = link(grant["url"]["@id"])
                if link(address) not in row.get("grants", []):
                    row.setdefault("grants", []).append(link(address))
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
        if f"{key}/pbpk-model-metadata.json" in contents:
            pbpk(row, json.loads(contents[f"{key}/pbpk-model-metadata.json"]))
        rows.append(row)
    return rows + list(others.values())
