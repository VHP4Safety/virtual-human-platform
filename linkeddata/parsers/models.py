"""Parser of the models of the Zenodo community vhp4safety."""

import copy
import json
import re
from importlib.resources import files

from pyld import jsonld
from rdfsolve.iris import local_name

from linkeddata.parsers import licence, link, present, publication, slug, term
from linkeddata.parsers.zenodo import LICENCES, doi_of, download

DATE = "http://www.w3.org/2001/XMLSchema#date"
DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"
CRATE = re.compile(r"(.+?)-ro-crate", re.IGNORECASE)
# The local addresses of the crate (#r-4.1.0, models/x.mmd) are read under this base.
LOCAL = "crate:/"
RO_CRATE = json.loads((files("rocrate") / "data" / "ro-crate.jsonld").read_text())["@context"]
# A "a -> b (how)" or "a <-> b (how)" connection of a structure.
CONNECTION = re.compile(r"(.+?)\s*(<->|->)\s*(.+?)(?:\s*\((.+)\))?$")
# The fields with links to records or terms. Entities that are only in the crate are kept as parts.
LINKS = ("about", "citation", "funding", "creator", "author", "contributor", "license", "keywords", "codeRepository")
# The fields of the root of the crate that are used for a model if they are missing in its entity.
SHARED = ("license", "citation", "funding", "about", "creator", "author", "keywords")


def crate_of(hit: dict) -> dict | None:
    for found in hit.get("files") or []:
        if "ro-crate" in found["key"].lower() and found["key"].lower().endswith(".zip"):
            return found
    return None


def packages(index: bytes) -> dict[str, str]:
    """Return the crate zip of each model record in index, by record identifier."""
    hits = json.loads(index)["hits"]
    if hits["total"] > len(hits["hits"]):
        raise ValueError("more models than one search page")
    found = {}
    for hit in hits["hits"]:
        crate = crate_of(hit)
        if crate is not None:
            found[str(hit["id"])] = crate["links"]["self"]
    return found


def listed(value) -> list:
    """Return value as a list."""
    if isinstance(value, list):
        return value
    if present(value):
        return [value]
    return []


def joined(*parts) -> str:
    """Return the given parts as one text."""
    return " ".join(str(part) for part in parts if present(part))


def sentence(heading: str, items) -> str:
    """Return heading and items as one sentence, or an empty text without items."""
    given = [str(item) for item in listed(items) if present(item)]
    if not given:
        return ""
    return f"{heading}: {'; '.join(given)}."


def fill(row: dict, field: str, value) -> None:
    """Set field of row to value if it is not set."""
    if field not in row and present(value) and value != []:
        row[field] = value


def entities(crate: dict) -> dict[str, dict]:
    """Return the entities of crate by address."""
    contexts = []
    for context in listed(crate.get("@context")):
        if isinstance(context, str) and context.startswith("https://w3id.org/ro/crate/"):
            context = RO_CRATE
        contexts.append(context)
    found = {}
    for node in jsonld.flatten({**crate, "@context": contexts}, None, {"base": LOCAL}):
        found[node["@id"]] = node
    return found


def kinds(node: dict) -> list[str]:
    return [local_name(kind) for kind in node.get("@type", [])]


def values(node: dict, field: str) -> list:
    """Return the values of field of node."""
    for iri, given in node.items():
        if iri not in ("@id", "@type") and local_name(iri) == field:
            return given
    return []


def text(node: dict, field: str) -> str:
    for value in values(node, field):
        if "@value" in value and present(value["@value"]):
            return str(value["@value"])
    return ""


def record(nodes: dict, node: dict, others: dict) -> dict | None:
    """Return the link to the record of node, and add its row to others."""
    iri = node["@id"]
    found = kinds(node)
    name = text(node, "name")
    if "Person" in found and name:
        address = "people/" + slug(name)
        row = others.setdefault(address, {"@id": address, "@type": "Person", "name": name})
        if iri.startswith("https://orcid.org/"):
            row["sameAs"] = link(iri)
        for affiliation in values(node, "affiliation"):
            organisation = nodes.get(affiliation.get("@id"))
            if organisation is None:
                continue
            linked = record(nodes, organisation, others)
            if linked is not None:
                row["affiliation"] = linked
        return link(address)
    if "Organization" in found and name:
        address = "organizations/" + slug(name)
        row = others.setdefault(address, {"@id": address, "@type": "Organization", "name": name})
        if iri.startswith(("http://", "https://")):
            row["sameAs"] = link(iri)
        return link(address)
    if "Grant" in found and text(node, "identifier"):
        address = "grants/" + slug(text(node, "identifier"))
        row = others.setdefault(address, {"@id": address, "@type": "MonetaryGrant", "name": name or text(node, "identifier"),
                                          "identifier": text(node, "identifier")})
        for url in values(node, "url"):
            row["url"] = link(url.get("@id") or url.get("@value"))
        for funder in values(node, "funder"):
            row["funder"] = converted(nodes, funder, others, frozenset({iri}))
        return link(address)
    if "ScholarlyArticle" in found or "Article" in found:
        article = publication(iri)
        if article is not None:
            others.setdefault(article["@id"], article)
            return link(article["@id"])
    return None


def fields(nodes: dict, node: dict, others: dict, seen: frozenset = frozenset()) -> dict:
    """Return the fields of the entity node by name."""
    row = {}
    for iri, given in node.items():
        if iri in ("@id", "@type"):
            continue
        for value in given:
            row.setdefault(local_name(iri), []).append(converted(nodes, value, others, seen | {node["@id"]}))
    return row


def converted(nodes: dict, value: dict, others: dict, seen: frozenset):
    if "@value" in value:
        given = value["@value"]
        if isinstance(given, str) and re.fullmatch(r"https?://\S+", given):
            return link(given)
        return given
    iri = value["@id"]
    node = nodes.get(iri)
    if node is None or iri in seen:
        return link(iri)
    found = record(nodes, node, others)
    if found is not None:
        return found
    if not iri.startswith(LOCAL):
        return link(iri)
    return {"@type": kinds(node), **fields(nodes, node, others, seen)}


def version_of(part) -> str:
    """Return the requirement part as a text."""
    if not isinstance(part, dict):
        return str(part)
    if "@id" in part:
        return part["@id"]
    return joined(*part.get("name", [])[:1], *part.get("version", [])[:1])


def identifiers(row: dict) -> None:
    """Store the identifiers of row as identifier type and value."""
    found = []
    for value in row.pop("identifier", []):
        if isinstance(value, str):
            kind, _, given = value.rpartition(":" if ":" in value else " ")
            if kind and given:
                value = {"@type": "PropertyValue", "propertyID": kind, "value": given}
        found.append(value)
    if found:
        row["identifier"] = found


def weight(row: dict) -> None:
    """Store the molecular weight of row as a number."""
    for value in row.get("molecularWeight", []):
        given = re.fullmatch(r"([0-9.]+)\s*(g/mol)?", str(value).strip())
        if given:
            row["molecularWeight"] = [{"@value": given.group(1), "@type": DECIMAL}]


def number(value):
    """Return value as a decimal if it is a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return {"@value": str(value), "@type": DECIMAL}


def named_parts(kind: str, names) -> list[dict]:
    """Return a part of kind for each of names."""
    return [{"@type": kind, "name": str(name)} for name in listed(names)]


def connections(given) -> list[dict]:
    """Return the connections in given, in both directions for <->."""
    found = []
    for value in listed(given):
        written = CONNECTION.fullmatch(str(value).strip())
        if written is None:
            found.append({"@type": "pbpk:Connection", "description": str(value)})
            continue
        source, way, target, how = written.groups()
        ends = [(source, target)]
        if way == "<->":
            ends.append((target, source))
        for start, end in ends:
            part = {"@type": "pbpk:Connection", "pbpk:sourceCompartment": start, "pbpk:targetCompartment": end}
            if how:
                part["description"] = how
            found.append(part)
    return found


def implementations(paths) -> list[dict]:
    found = []
    for path in listed(paths):
        part = {"@type": "pbpk:Implementation", "pbpk:implementationLocation": str(path)}
        if str(path).lower().endswith(".r"):
            part["pbpk:implementationType"] = "R script"
        elif str(path).lower().endswith(".py"):
            part["pbpk:implementationType"] = "Python script"
        found.append(part)
    return found


def roles(row: dict, named_roles: dict[str, list]) -> None:
    """Add the roles of the chemicals in named_roles to row."""
    for chemical in row.get("pbpk:hasChemical", []):
        for name in chemical.get("name", []):
            if str(name).casefold() in named_roles and "pbpk:chemicalRole" not in chemical:
                chemical["pbpk:chemicalRole"] = named_roles[str(name).casefold()]


def system(described: dict, model: dict) -> list[dict]:
    """Return the biological system of the model in the template."""
    given = described.get("biological_system_description") or {}
    if not given:
        return []
    species = given.get("species") or {}
    part = {"@type": "pbpk:BiologicalSystem", "pbpk:species": species.get("name"), "pbpk:lifeStage": given.get("life_stage"),
            "pbpk:physiologicalScope": given.get("physiological_scope"),
            "pbpk:populationDescription": joined(given.get("population_description"), sentence("Sex", given.get("sex")), model.get("default_subject"))}
    if present(species.get("ncbi_taxonomy")):
        part["pbpk:species"] = link(species["ncbi_taxonomy"])
    return [part]


def chemical_notes(row: dict, described: dict) -> None:
    """Add the roles and physicochemical notes of the template to the chemicals of row."""
    chemical = described.get("chemical_description") or {}
    if not present(chemical.get("name")):
        return
    name = str(chemical["name"]).casefold()
    roles(row, {name: listed(chemical.get("role"))})
    notes = []
    if present(chemical.get("logP")):
        notes.append(f"logP {chemical['logP']}.")
    if present(chemical.get("pKa")):
        notes.append(f"pKa {chemical['pKa']}.")
    weighed = (chemical.get("molecular_weight_model_value") or {}).get("value")
    if present(weighed):
        notes.append(f"Molecular weight in the model: {weighed} g/mol.")
    for part in row.get("pbpk:hasChemical", []):
        for given in part.get("name", []):
            if str(given).casefold() == name:
                fill(part, "pbpk:physicochemicalNotes", " ".join(notes))


def parameters(model: dict) -> list[dict]:
    found = []
    for parameter in listed(model.get("parameters")):
        part = {"@type": "pbpk:Parameter", "name": parameter.get("name"), "propertyID": parameter.get("symbol"), "value": number(parameter.get("value")),
                "unitText": parameter.get("unit"), "pbpk:parameterCategory": parameter.get("category"), "pbpk:sourceReference": parameter.get("source_reference")}
        notes = joined(sentence("Value expression", parameter.get("value_expression")), parameter.get("notes"))
        if notes:
            part["pbpk:notes"] = notes
        found.append(part)
    return found


def calibration(model: dict) -> list[dict]:
    given = model.get("calibration") or {}
    if not given:
        return []
    performed = given.get("performed")
    if performed is True:
        performed = "yes"
    elif performed is False:
        performed = "no"
    return [{"@type": "pbpk:Calibration", "description": given.get("description"), "pbpk:notes": f"Performed: {performed}."}]


def evaluations(described: dict, model: dict) -> list[dict]:
    """Return the evaluations of the model in the template."""
    evaluated = described.get("model_evaluation_and_validation") or {}
    found = []
    studies = listed(evaluated.get("pharmacokinetic_evaluation_data"))
    if present(model.get("evaluation_summary")) or studies:
        lines = []
        for study in studies:
            details = []
            for key in ("population", "dose", "follow_up", "data"):
                if present(study.get(key)):
                    details.append(str(study[key]))
            lines.append(f"{study.get('reference')}: {'; '.join(details)}.")
        found.append({"@type": "pbpk:Evaluation", "name": "Pharmacokinetic evaluation", "description": evaluated.get("data_extraction"),
                      "pbpk:evaluationData": " ".join(lines), "pbpk:outcome": model.get("evaluation_summary")})
    qivive = evaluated.get("qivive_and_benchmark_dose") or {}
    if qivive:
        found.append({"@type": "pbpk:Evaluation", "name": "QIVIVE and benchmark dose", "pbpk:evaluationData": qivive.get("in_vitro_sources"),
                      "description": joined(sentence("Dose metrics", qivive.get("dose_metrics")), sentence("Benchmark response", qivive.get("benchmark_response")),
                                            sentence("Software", qivive.get("software"))),
                      "pbpk:outcome": qivive.get("key_result")})
    return found


def sensitivity(described: dict) -> list[dict]:
    given = (described.get("model_evaluation_and_validation") or {}).get("local_sensitivity_analysis") or {}
    if not given:
        return []
    return [{"@type": "pbpk:SUVAnalysis", "pbpk:analysisType": "Sensitivity analysis", "pbpk:method": sentence("Local sensitivity analysis", given.get("perturbation")),
             "pbpk:outcome": given.get("key_result"),
             "pbpk:notes": joined(sentence("Scenario", given.get("scenario")), sentence("Output", given.get("output")),
                             sentence("Substantial influence", given.get("substantial_influence_threshold")))}]


def scenarios(row: dict, described: dict) -> str:
    """Return the simulation scenarios of the template as sentences."""
    sentences = []
    for scenario in listed(described.get("simulation_scenarios")):
        details = []
        for key, value in scenario.items():
            if key == "name" or not present(value):
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if key == "description":
                details.append(str(value))
            else:
                details.append(f"{key.replace('_', ' ')} {value}")
        sentences.append(sentence(scenario.get("name", "Scenario"), details))
        for output in named_parts("bioschemas:FormalParameter", scenario.get("outputs")):
            if output not in row.setdefault("bioschemas:output", []):
                row["bioschemas:output"].append(output)
    return " ".join(sentences)


def template(row: dict, described: dict, model: dict) -> None:
    """Set the ROBOT fields of row from the PBPK Model Reporting Template."""
    general = described.get("general_model_information") or {}
    structure = model.get("structure") or {}
    kind = f"{structure['type']}." if present(structure.get("type")) else ""
    fill(row, "pbpk:intendedUse", sentence("Intended applications", general.get("intended_application")))
    fill(row, "alternateName", model.get("model_name"))
    fill(row, "pbpk:mathematicalRepresentation", listed(model.get("mathematical_representation")))
    fill(row, "pbpk:modelStructureDescription", joined(kind, sentence("Renal clearance", structure.get("renal_clearance"))))
    fill(row, "pbpk:structuralCompartments", named_parts("pbpk:Compartment", structure.get("compartments")))
    fill(row, "pbpk:connections", connections(structure.get("connections")))
    fill(row, "pbpk:implementation", implementations(model.get("implementation_files")))
    fill(row, "pbpk:hasBiologicalSystem", system(described, model))
    chemical_notes(row, described)
    fill(row, "pbpk:hasParameter", parameters(model))
    fill(row, "pbpk:hasCalibration", calibration(model))
    fill(row, "pbpk:hasEvaluation", evaluations(described, model))
    fill(row, "pbpk:hasSUVAnalysis", sensitivity(described))
    fill(row, "pbpk:reproducibilityInstructions", scenarios(row, described))
    fill(row, "pbpk:applicabilityDomain", sentence("Route of administration", model.get("route_of_administration")))
    fill(row, "pbpk:limitations", joined(*listed(described.get("limitations_and_uncertainties"))))


def curated(row: dict, described: dict) -> None:
    """Set the ROBOT fields of row from the curated layout of one model."""
    model = described.get("model") or {}
    evaluation = described.get("evaluation") or {}
    types = []
    for kind in listed(model.get("model_type")):
        types.append(str(kind))
        if "ordinary differential equation" in str(kind).lower():
            fill(row, "pbpk:mathematicalRepresentation", "Ordinary differential equations")
    fill(row, "pbpk:intendedUse", model.get("purpose"))
    fill(row, "applicationCategory", types[:1])
    fill(row, "pbpk:hasBiologicalSystem", [{"@type": "pbpk:BiologicalSystem", "pbpk:species": str(species)} for species in listed(model.get("species"))])
    fill(row, "pbpk:structuralCompartments", named_parts("pbpk:Compartment", listed(model.get("gastrointestinal_structure")) + listed(model.get("systemic_compartments"))))
    fill(row, "pbpk:modelStructureDescription", joined(sentence("Processes", model.get("processes")), sentence("Modelled entities", model.get("modelled_entity_classes")),
                                                  sentence("Partition coefficient methods", model.get("partition_methods"))))
    fill(row, "bioschemas:input", named_parts("bioschemas:FormalParameter", model.get("inputs")))
    fill(row, "bioschemas:output", named_parts("bioschemas:FormalParameter", model.get("outputs")))
    fill(row, "pbpk:applicabilityDomain", joined(sentence("Exposure routes", model.get("exposure_routes")), sentence("Exposure pattern", model.get("exposure_pattern"))))
    fill(row, "pbpk:implementation", implementations((described.get("implementation") or {}).get("entry_points")))
    roles(row, {str(name).casefold(): ["Parent compound"] for name in listed(evaluation.get("parent_pesticides"))})
    if evaluation:
        metrics = [{"@type": "pbpk:PerformanceMetric", "name": key.replace("_", " "), "value": str(value)} for key, value in (evaluation.get("reported_results") or {}).items()]
        fill(row, "pbpk:hasEvaluation", [{"@type": "pbpk:Evaluation", "description": evaluation.get("criteria"), "pbpk:performanceMetrics": metrics,
                                     "pbpk:evaluationData": sentence("Observables", evaluation.get("observables"))}])
    fill(row, "pbpk:limitations", joined(*listed(described.get("limitations"))))


def chemicals(nodes: dict, others: dict) -> list[dict]:
    """Return the chemicals of the crate with their identifiers and weights."""
    found = []
    for node in nodes.values():
        if "MolecularEntity" in kinds(node) or "ChemicalSubstance" in kinds(node):
            chemical = {"@type": kinds(node), **fields(nodes, node, others)}
            chemical.setdefault("sameAs", []).append(link(node["@id"]))
            identifiers(chemical)
            weight(chemical)
            found.append(chemical)
    return found


def model_row(nodes: dict, root: dict, main: dict, address: str, others: dict) -> dict:
    """Return the row of the model main at address."""
    row = {"@id": address, "@type": "SoftwareSourceCode", **fields(nodes, main, others)}
    for field in SHARED:
        fill(row, field, [converted(nodes, value, others, frozenset({LOCAL})) for value in values(root, field)])
    for field in LINKS:
        if field in row:
            row[field] = [value for value in row[field] if not isinstance(value, dict) or "@id" in value]
    for cited in row.get("citation", []):
        if isinstance(cited, dict):
            article = publication(cited.get("@id", ""))
            if article is not None:
                others.setdefault(article["@id"], article)
                cited["@id"] = article["@id"]
    row["softwareRequirements"] = [version_of(part) for part in row.get("softwareRequirements", [])]
    # The authors of the crate are stored as the creators of the model, as in the profile.
    row.setdefault("creator", []).extend(row.pop("author", []))
    return row


def zenodo(row: dict, hit: dict, nodes: dict, others: dict) -> None:
    """Add the fields of the Zenodo record hit to row."""
    metadata = hit["metadata"]
    fill(row, "name", [metadata["title"]])
    licences = [licence(value["@id"]) for value in row.get("license", []) if isinstance(value, dict) and "@id" in value]
    row["license"] = licences
    if not any(str(value.get("@id", "")).startswith("https://spdx.org/") for value in licences) and isinstance(metadata.get("license"), dict):
        row["license"] = [licence(LICENCES.get(metadata["license"]["id"], metadata["license"]["id"]))]
    fill(row, "keywords", metadata.get("keywords") or [])
    keywords = []
    for keyword in row.get("keywords", []):
        keywords.append(term(keyword, "glossary") if isinstance(keyword, str) else keyword)
    row["keywords"] = keywords
    row["isBasedOn"] = link(hit["links"]["self_html"])
    doi_of(row, hit, others)
    if present(metadata.get("publication_date")):
        row["datePublished"] = {"@value": metadata["publication_date"], "@type": DATE}
    for given in hit.get("files") or []:
        found = download(given)
        artifact = {"@type": "MediaObject", "name": found["name"], "pbpk:artifactLocation": given["links"]["self"], "contentSize": found["contentSize"]}
        if "encodingFormat" in found:
            artifact["encodingFormat"] = found["encodingFormat"]
        row.setdefault("hasPart", []).append(artifact)
    if "creator" in row or "author" in row:
        return
    for creator in metadata.get("creators") or []:
        last, _, first = str(creator.get("name", "")).partition(", ")
        person = {"@id": "zenodo", "@type": ["Person"], "https://schema.org/name": [{"@value": f"{first} {last}" if first else last}]}
        if present(creator.get("orcid")):
            person["@id"] = "https://orcid.org/" + creator["orcid"]
        row.setdefault("creator", []).append(record(nodes, person, others))


def reported(described: dict, main: dict) -> dict | None:
    """Return the model of the template with the main entity main in its files, or None."""
    for model in listed(described.get("models")):
        if main["@id"].removeprefix(LOCAL) in listed(model.get("implementation_files")):
            return model
    return None


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    others = {}
    for hit in json.loads(contents["models"])["hits"]["hits"]:
        crate_file = crate_of(hit)
        key = str(hit["id"])
        if crate_file is None or f"{key}/ro-crate-metadata.json" not in contents:
            continue
        nodes = entities(json.loads(contents[f"{key}/ro-crate-metadata.json"]))
        root = nodes.get(LOCAL, {"@id": LOCAL})
        described = {}
        if f"{key}/pbpk-model-metadata.json" in contents:
            described = json.loads(contents[f"{key}/pbpk-model-metadata.json"])
        mains = [nodes[main["@id"]] for main in values(root, "mainEntity") if main.get("@id") in nodes]
        crate_name = CRATE.match(crate_file["key"])
        found_chemicals = chemicals(nodes, others)
        taxa = [{"@type": "pbpk:BiologicalSystem", "pbpk:species": link(node["@id"])} for node in nodes.values() if "Taxon" in kinds(node)]
        for main in mains:
            model = reported(described, main)
            if crate_name and len(mains) == 1:
                name = crate_name.group(1)
            else:
                name = (model or {}).get("model_name") or text(main, "name") or hit["metadata"]["title"]
            row = model_row(nodes, root, main, "models/" + slug(name), others)
            zenodo(row, hit, nodes, others)
            fill(row, "pbpk:hasChemical", copy.deepcopy(found_chemicals))
            if model is not None:
                template(row, described, model)
            elif "model" in described:
                curated(row, described)
            fill(row, "pbpk:hasBiologicalSystem", taxa)
            rows.append(row)
    return rows + list(others.values())
