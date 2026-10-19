"""Parser of the models of the Zenodo community vhp4safety (a workaround, see linkeddata/parsers): the record
search gives each model's record, and its RO-Crate (the zip whose name says "ro-crate") gives the model's
metadata (ro-crate-metadata.json) and, where its makers wrote one, a PBPK description (pbpk-model-metadata.json).
- The crate is read as linked data: expanded with RO-Crate's context (ro-crate-py's copy), its fields by name
  and web addresses written as text taken as links. A model is each main entity of
  the crate, at models/<crate's name> ("oppbkmodelr" for oppbkmodelr-ro-crate-v1.0.1.zip), or at models/<its
  name> when the crate has several; its fields are the entity's, as the crate states them, then the crate's
  for those it lacks. The entities only the crate holds, such as a language, are the model's parts; people,
  organisations, grants (by their number) and publications (by their DOI) are records of their own; other
  entities, such as a taxon, are linked. Requirements are texts ("RStudio 1.4.1717"), as schema.org has them;
  identifiers such as "CAS:15663-27-1" are identifier and value. The crate's chemicals and taxa are the model's.
- From the Zenodo record: its DOI, date and page; its keywords, license and creators where the crate has none.
- The PBPK description gives ROBOT's fields the crate does not have, in either of its two layouts: the PBPK
  Model Reporting Template of Tan et al. (2020, https://doi.org/10.1016/j.yrtph.2020.104673), with a part per
  model, or a curated layout of one model. Its lists become parts where ROBOT has them (compartments,
  connections, parameters, chemicals' roles); inputs and outputs are formal parameters, as RO-Crate gives
  them; routes and scenarios tell the domain of applicability, and processes the structure, as the template's
  narrative fields do."""

import json
import re
from importlib.resources import files

from pyld import jsonld

from linkeddata.parsers import licence, link, present, publication, slug, term

DATE = "http://www.w3.org/2001/XMLSchema#date"
DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"
CRATE = re.compile(r"(.+?)-ro-crate", re.IGNORECASE)
# The crate's own addresses (#r-4.1.0, models/x.mmd) are read under this one.
LOCAL = "crate:/"
RO_CRATE = json.loads((files("rocrate") / "data" / "ro-crate.jsonld").read_text())["@context"]
# A "a -> b (how)" or "a <-> b (how)" connection of a structure.
CONNECTION = re.compile(r"(.+?)\s*(<->|->)\s*(.+?)(?:\s*\((.+)\))?$")
# The fields that link to records or terms; entities only the crate holds stay in it.
LINKS = ("about", "citation", "funding", "creator", "author", "contributor", "license", "keywords", "codeRepository")


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


def listed(value) -> list:
    return value if isinstance(value, list) else [value] if present(value) else []


def named(iri: str) -> str:
    """A term's name: its address after the last / or #."""
    return re.split(r"[/#]", iri)[-1]


def entities(crate: dict) -> dict[str, dict]:
    """The crate's entities by address, as linked data."""
    contexts = []
    for context in listed(crate.get("@context")):
        contexts.append(RO_CRATE if isinstance(context, str) and context.startswith("https://w3id.org/ro/crate/") else context)
    found = {}
    for node in jsonld.flatten({**crate, "@context": contexts}, None, {"base": LOCAL}):
        found[node["@id"]] = node
    return found


def kinds(node: dict) -> list[str]:
    return [named(kind) for kind in node.get("@type", [])]


def values(node: dict, field: str) -> list:
    """A field's values, by its name in schema.org or another vocabulary."""
    for iri, given in node.items():
        if iri not in ("@id", "@type") and named(iri) == field:
            return given
    return []


def text(node: dict, field: str) -> str:
    for value in values(node, field):
        if "@value" in value and present(value["@value"]):
            return str(value["@value"])
    return ""


def record(nodes: dict, node: dict, others: dict) -> dict | None:
    """The link to the record an entity is, adding its row: a person, organisation, grant or publication."""
    iri = node["@id"]
    found = kinds(node)
    if "Person" in found and text(node, "name"):
        address = "people/" + slug(text(node, "name"))
        row = others.setdefault(address, {"@id": address, "@type": "Person", "name": text(node, "name")})
        if iri.startswith("https://orcid.org/"):
            row["same_as"] = link(iri)
        for affiliation in values(node, "affiliation"):
            organisation = record(nodes, nodes.get(affiliation.get("@id"), {"@id": affiliation.get("@id", ""), "@type": ["Organization"]}), others)
            if organisation is not None:
                row["affiliation"] = organisation
        return link(address)
    if "Organization" in found and text(node, "name"):
        address = "organizations/" + slug(text(node, "name"))
        row = others.setdefault(address, {"@id": address, "@type": "Organization", "name": text(node, "name")})
        if iri.startswith(("http://", "https://")):
            row["same_as"] = link(iri)
        return link(address)
    if "Grant" in found and text(node, "identifier"):
        address = "grants/" + slug(text(node, "identifier"))
        row = others.setdefault(address, {"@id": address, "@type": "Grant", "name": text(node, "name") or text(node, "identifier"),
                                          "identifier": text(node, "identifier")})
        for url in values(node, "url"):
            row["url"] = link(url.get("@id") or url.get("@value"))
        for funder in values(node, "funder"):
            row["funder"] = converted(nodes, funder, others, frozenset({iri}))
        return link(address)
    article = publication(iri) if {"ScholarlyArticle", "Article"} & set(found) else None
    if article is not None:
        others.setdefault(article["@id"], article)
        return link(article["@id"])
    return None


def fields(nodes: dict, node: dict, others: dict, seen: frozenset = frozenset()) -> dict:
    """An entity's fields by name, as the crate states them: entities only the crate holds as parts, records
    as links to them, other entities as links."""
    row = {}
    for iri, given in node.items():
        if iri in ("@id", "@type"):
            continue
        for value in given:
            row.setdefault(named(iri), []).append(converted(nodes, value, others, seen | {node["@id"]}))
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
    """A requirement as a text: its name and version ("RStudio 1.4.1717")."""
    if not isinstance(part, dict) or "@id" in part:
        return str(part.get("@id") if isinstance(part, dict) else part)
    return " ".join(str(value) for value in (part.get("name") or [""])[:1] + (part.get("version") or [])[:1] if present(value))


def identifiers(row: dict) -> None:
    """Identifiers such as "CAS:15663-27-1" or "PubChem CID 2730" as identifier and value."""
    found = []
    for value in row.pop("identifier", []):
        kind, _, given = str(value).rpartition(":") if ":" in str(value) else str(value).rpartition(" ")
        found.append({"@type": "PropertyValue", "propertyID": kind, "value": given} if isinstance(value, str) and kind and given else value)
    if found:
        row["identifier"] = found


def weight(row: dict) -> None:
    """A molecular weight in g/mol, as its number."""
    for value in row.get("molecularWeight", []):
        given = re.fullmatch(r"([0-9.]+)\s*(g/mol)?", str(value).strip())
        if given:
            row["molecularWeight"] = [{"@value": given.group(1), "@type": DECIMAL}]


def number(value):
    return {"@value": str(value), "@type": DECIMAL} if isinstance(value, (int, float)) and not isinstance(value, bool) else value


def sentence(heading: str, items) -> str:
    found = [str(item) for item in listed(items) if present(item)]
    return f"{heading}: {'; '.join(found)}." if found else ""


def fill(row: dict, field: str, value) -> None:
    """A field the crate does not give, from the PBPK description."""
    if field not in row and present(value) and value != []:
        row[field] = value


def connections(given) -> list[dict]:
    """Connections ("blood <-> fat (perfusion-limited distribution)"), both ways for <->."""
    found = []
    for value in listed(given):
        written = CONNECTION.fullmatch(str(value).strip())
        if written is None:
            found.append({"@type": "Connection", "description": str(value)})
            continue
        source, way, target, how = written.groups()
        for start, end in [(source, target)] + ([(target, source)] if way == "<->" else []):
            found.append({"@type": "Connection", "sourceCompartment": start, "targetCompartment": end, **({"description": how} if how else {})})
    return found


def implementations(paths) -> list[dict]:
    found = []
    for path in listed(paths):
        part = {"@type": "Implementation", "implementationLocation": str(path)}
        if str(path).lower().endswith(".r"):
            part["implementationType"] = "R script"
        elif str(path).lower().endswith(".py"):
            part["implementationType"] = "Python script"
        found.append(part)
    return found


def roles(row: dict, named_roles: dict[str, list]) -> None:
    """The roles in the model of the chemicals the PBPK description names."""
    for chemical in row.get("hasChemical", []):
        for name in chemical.get("name", []):
            if str(name).casefold() in named_roles and "chemicalRole" not in chemical:
                chemical["chemicalRole"] = named_roles[str(name).casefold()]


def template(row: dict, described: dict, model: dict) -> None:
    """ROBOT's fields from the PBPK Model Reporting Template (Tan et al. 2020), for one of its models."""
    general = described.get("general_model_information") or {}
    fill(row, "intendedUse", sentence("Intended applications", general.get("intended_application")))
    fill(row, "alternateName", model.get("model_name"))
    fill(row, "mathematicalRepresentation", listed(model.get("mathematical_representation")))
    structure = model.get("structure") or {}
    fill(row, "modelStructureDescription", " ".join(part for part in (
        f"{structure['type']}." if present(structure.get("type")) else "", sentence("Renal clearance", structure.get("renal_clearance"))) if part))
    fill(row, "structuralCompartments", [{"@type": "Compartment", "name": str(name)} for name in listed(structure.get("compartments"))])
    fill(row, "connections", connections(structure.get("connections")))
    fill(row, "implementation", implementations(model.get("implementation_files")))
    system = described.get("biological_system_description") or {}
    species = system.get("species") or {}
    if system:
        fill(row, "hasBiologicalSystem", [{
            "@type": "BiologicalSystem", "species": link(species["ncbi_taxonomy"]) if present(species.get("ncbi_taxonomy")) else species.get("name"),
            "lifeStage": system.get("life_stage"), "physiologicalScope": system.get("physiological_scope"),
            "populationDescription": " ".join(str(part) for part in (system.get("population_description"), sentence("Sex", system.get("sex")),
                                                                      model.get("default_subject")) if present(part))}])
    chemical = described.get("chemical_description") or {}
    if present(chemical.get("name")):
        roles(row, {str(chemical["name"]).casefold(): listed(chemical.get("role"))})
        for part in row.get("hasChemical", []):
            if str(chemical["name"]).casefold() in [str(name).casefold() for name in part.get("name", [])]:
                weighed = (chemical.get("molecular_weight_model_value") or {}).get("value")
                fill(part, "physicochemicalNotes", " ".join(part for part in (
                    f"logP {chemical['logP']}." if present(chemical.get("logP")) else "", f"pKa {chemical['pKa']}." if present(chemical.get("pKa")) else "",
                    f"Molecular weight in the model: {weighed} g/mol." if present(weighed) else "") if part))
    parameters = []
    for parameter in listed(model.get("parameters")):
        notes = " ".join(part for part in (sentence("Value expression", parameter.get("value_expression")), str(parameter.get("notes") or "")) if part)
        parameters.append({"@type": "Parameter", "name": parameter.get("name"), "propertyID": parameter.get("symbol"), "value": number(parameter.get("value")),
                           "unitText": parameter.get("unit"), "parameterCategory": parameter.get("category"), "sourceReference": parameter.get("source_reference"),
                           "notes": notes or None})
    fill(row, "hasParameter", parameters)
    calibration = model.get("calibration") or {}
    if calibration:
        performed = calibration.get("performed")
        fill(row, "hasCalibration", [{"@type": "Calibration", "description": calibration.get("description"),
                                      "notes": f"Performed: {'yes' if performed is True else 'no' if performed is False else performed}."}])
    evaluated = described.get("model_evaluation_and_validation") or {}
    evaluations = []
    if present(model.get("evaluation_summary")) or evaluated.get("pharmacokinetic_evaluation_data"):
        data = []
        for found in listed(evaluated.get("pharmacokinetic_evaluation_data")):
            data.append(f"{found.get('reference')}: " + "; ".join(str(found[key]) for key in ("population", "dose", "follow_up", "data") if present(found.get(key))))
        evaluations.append({"@type": "Evaluation", "name": "Pharmacokinetic evaluation", "description": evaluated.get("data_extraction"),
                            "evaluationData": " ".join(f"{line}." for line in data), "outcome": model.get("evaluation_summary")})
    qivive = evaluated.get("qivive_and_benchmark_dose") or {}
    if qivive:
        evaluations.append({"@type": "Evaluation", "name": "QIVIVE and benchmark dose", "evaluationData": qivive.get("in_vitro_sources"),
                            "description": " ".join(part for part in (sentence("Dose metrics", qivive.get("dose_metrics")),
                                                                      sentence("Benchmark response", qivive.get("benchmark_response")),
                                                                      sentence("Software", qivive.get("software"))) if part),
                            "outcome": qivive.get("key_result")})
    fill(row, "hasEvaluation", evaluations)
    sensitivity = evaluated.get("local_sensitivity_analysis") or {}
    if sensitivity:
        fill(row, "hasSUVAnalysis", [{"@type": "SUVAnalysis", "analysisType": "Sensitivity analysis", "method": sentence("Local sensitivity analysis", sensitivity.get("perturbation")),
                                      "outcome": sensitivity.get("key_result"),
                                      "notes": " ".join(part for part in (sentence("Scenario", sensitivity.get("scenario")), sentence("Output", sensitivity.get("output")),
                                                                          sentence("Substantial influence", sensitivity.get("substantial_influence_threshold"))) if part)}])
    scenarios = []
    for scenario in listed(described.get("simulation_scenarios")):
        scenarios.append(sentence(scenario.get("name", "Scenario"), [(key.replace("_", " ") + " " if key != "description" else "")
                                                                    + (", ".join(map(str, value)) if isinstance(value, list) else str(value))
                                                                    for key, value in scenario.items() if key != "name" and present(value)]))
        for output in listed(scenario.get("outputs")):
            if {"@type": "FormalParameter", "name": str(output)} not in row.setdefault("output", []):
                row["output"].append({"@type": "FormalParameter", "name": str(output)})
    fill(row, "applicabilityDomain", sentence("Route of administration", model.get("route_of_administration")))
    fill(row, "reproducibilityInstructions", " ".join(scenarios))
    fill(row, "limitations", " ".join(str(line) for line in listed(described.get("limitations_and_uncertainties"))))


def curated(row: dict, described: dict) -> None:
    """ROBOT's fields from the curated layout of one model."""
    model = described.get("model") or {}
    fill(row, "intendedUse", model.get("purpose"))
    types = [str(kind) for kind in listed(model.get("model_type"))]
    fill(row, "applicationCategory", types[:1])
    if any("ordinary differential equation" in kind.lower() for kind in types):
        fill(row, "mathematicalRepresentation", "Ordinary differential equations")
    fill(row, "hasBiologicalSystem", [{"@type": "BiologicalSystem", "species": str(species)} for species in listed(model.get("species"))])
    fill(row, "structuralCompartments", [{"@type": "Compartment", "name": str(name)}
                                         for name in listed(model.get("gastrointestinal_structure")) + listed(model.get("systemic_compartments"))])
    fill(row, "modelStructureDescription", " ".join(part for part in (sentence("Processes", model.get("processes")),
                                                                      sentence("Modelled entities", model.get("modelled_entity_classes")),
                                                                      sentence("Partition coefficient methods", model.get("partition_methods"))) if part))
    fill(row, "input", [{"@type": "FormalParameter", "name": str(name)} for name in listed(model.get("inputs"))])
    fill(row, "output", [{"@type": "FormalParameter", "name": str(name)} for name in listed(model.get("outputs"))])
    fill(row, "applicabilityDomain", " ".join(part for part in (sentence("Exposure routes", model.get("exposure_routes")),
                                                                sentence("Exposure pattern", model.get("exposure_pattern"))) if part))
    fill(row, "implementation", implementations((described.get("implementation") or {}).get("entry_points")))
    evaluation = described.get("evaluation") or {}
    roles(row, {str(name).casefold(): ["Parent compound"] for name in listed(evaluation.get("parent_pesticides"))})
    if evaluation:
        metrics = []
        for key, value in (evaluation.get("reported_results") or {}).items():
            metrics.append({"@type": "PerformanceMetric", "name": key.replace("_", " "), "value": str(value)})
        fill(row, "hasEvaluation", [{"@type": "Evaluation", "description": evaluation.get("criteria"), "performanceMetrics": metrics,
                                     "evaluationData": sentence("Observables", evaluation.get("observables"))}])
    fill(row, "limitations", " ".join(str(line) for line in listed(described.get("limitations"))))


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
        mains = [nodes[main["@id"]] for main in values(root, "mainEntity") if main.get("@id") in nodes]
        described = json.loads(contents[f"{key}/pbpk-model-metadata.json"]) if f"{key}/pbpk-model-metadata.json" in contents else {}
        found = CRATE.match(crate_file["key"])
        metadata = hit["metadata"]
        chemicals = []
        for node in nodes.values():
            if {"MolecularEntity", "ChemicalSubstance"} & set(kinds(node)):
                chemical = {"@type": ["Chemical", *kinds(node)], **fields(nodes, node, others)}
                chemical.setdefault("sameAs", []).append(link(node["@id"]))
                identifiers(chemical)
                weight(chemical)
                chemicals.append(chemical)
        taxa = [link(node["@id"]) for node in nodes.values() if "Taxon" in kinds(node)]
        for main in mains:
            reported = [model for model in listed(described.get("models")) if main["@id"].removeprefix(LOCAL) in listed(model.get("implementation_files"))]
            name = (reported[0].get("model_name") if reported else "") or text(main, "name") or metadata["title"]
            row = {"@id": "models/" + slug(found.group(1) if found and len(mains) == 1 else name), "@type": "Model", **fields(nodes, main, others)}
            for field in ("license", "citation", "funding", "about", "creator", "author", "keywords"):
                fill(row, field, [converted(nodes, value, others, frozenset({LOCAL})) for value in values(root, field)])
            for field in LINKS:
                if field in row:
                    row[field] = [value for value in row[field] if not isinstance(value, dict) or "@id" in value]
            for cited in row.get("citation", []):
                article = publication(cited.get("@id", "")) if isinstance(cited, dict) else None
                if article is not None:
                    others.setdefault(article["@id"], article)
                    cited["@id"] = article["@id"]
            fill(row, "name", [metadata["title"]])
            row["softwareRequirements"] = [version_of(part) for part in row.get("softwareRequirements", [])]
            row["license"] = [licence(value["@id"]) for value in row.get("license", []) if isinstance(value, dict) and "@id" in value]
            if not any(str(value.get("@id", "")).startswith("https://spdx.org/") for value in row["license"]) and isinstance(metadata.get("license"), dict):
                row["license"] = [licence(metadata["license"]["id"])]
            fill(row, "keywords", metadata.get("keywords") or [])
            row["keywords"] = [term(keyword, "glossary") if isinstance(keyword, str) else keyword for keyword in row.get("keywords", [])]
            row["page"] = link(hit["links"]["self_html"])
            if present(hit.get("doi")):
                row["doi"] = link("https://doi.org/" + hit["doi"])
            if present(metadata.get("publication_date")):
                row["published"] = {"@value": metadata["publication_date"], "@type": DATE}
            if "creator" not in row and "author" not in row:
                for creator in metadata.get("creators") or []:
                    last, _, first = str(creator.get("name", "")).partition(", ")
                    person = {"@id": "zenodo", "@type": ["Person"], "https://schema.org/name": [{"@value": f"{first} {last}" if first else last}]}
                    if present(creator.get("orcid")):
                        person["@id"] = "https://orcid.org/" + creator["orcid"]
                    row.setdefault("creator", []).append(record(nodes, person, others))
            fill(row, "hasChemical", [json.loads(json.dumps(chemical)) for chemical in chemicals])
            if reported:
                template(row, described, reported[0])
            elif "model" in described:
                curated(row, described)
            fill(row, "hasBiologicalSystem", [{"@type": "BiologicalSystem", "species": taxon} for taxon in taxa])
            rows.append(row)
    return rows + list(others.values())
