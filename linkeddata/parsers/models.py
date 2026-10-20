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

import copy
import json
import re
from importlib.resources import files

from pyld import jsonld
from rdfsolve.iris import local_name

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
# The fields of the crate's root that a model takes when its own entity lacks them.
SHARED = ("license", "citation", "funding", "about", "creator", "author", "keywords")


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
    """A value as a list: a list as it is, one value in a list, nothing as an empty list."""
    if isinstance(value, list):
        return value
    if present(value):
        return [value]
    return []


def joined(*parts) -> str:
    """The parts that are given, as one text."""
    return " ".join(str(part) for part in parts if present(part))


def sentence(heading: str, items) -> str:
    """A heading and its items as a sentence ("Processes: a; b."), or nothing without items."""
    given = [str(item) for item in listed(items) if present(item)]
    if not given:
        return ""
    return f"{heading}: {'; '.join(given)}."


def fill(row: dict, field: str, value) -> None:
    """A field the crate does not give, from the PBPK description."""
    if field not in row and present(value) and value != []:
        row[field] = value


def entities(crate: dict) -> dict[str, dict]:
    """The crate's entities by address, as linked data."""
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
    """A field's values, by its name in schema.org or another vocabulary."""
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
    """The link to the record an entity is, adding its row: a person, organisation, grant or publication."""
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
    """An entity's fields by name, as the crate states them: entities only the crate holds as parts, records
    as links to them, other entities as links."""
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
    """A requirement as a text: its name and version ("RStudio 1.4.1717"), or its address."""
    if not isinstance(part, dict):
        return str(part)
    if "@id" in part:
        return part["@id"]
    return joined(*part.get("name", [])[:1], *part.get("version", [])[:1])


def identifiers(row: dict) -> None:
    """Identifiers such as "CAS:15663-27-1" or "PubChem CID 2730" as identifier and value."""
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
    """A molecular weight in g/mol, as its number."""
    for value in row.get("molecularWeight", []):
        given = re.fullmatch(r"([0-9.]+)\s*(g/mol)?", str(value).strip())
        if given:
            row["molecularWeight"] = [{"@value": given.group(1), "@type": DECIMAL}]


def number(value):
    """A number as a decimal; other values as they are."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return {"@value": str(value), "@type": DECIMAL}


def named_parts(kind: str, names) -> list[dict]:
    """A part of a kind for each name, such as a compartment or an input."""
    return [{"@type": kind, "name": str(name)} for name in listed(names)]


def connections(given) -> list[dict]:
    """Connections ("blood <-> fat (perfusion-limited distribution)"), both ways for <->."""
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
    """The roles in the model of the chemicals the PBPK description names."""
    for chemical in row.get("pbpk:hasChemical", []):
        for name in chemical.get("name", []):
            if str(name).casefold() in named_roles and "pbpk:chemicalRole" not in chemical:
                chemical["pbpk:chemicalRole"] = named_roles[str(name).casefold()]


def system(described: dict, model: dict) -> list[dict]:
    """The template's biological system, with the model's default subject in its population."""
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
    """The roles and physicochemical notes the template gives its chemical."""
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
    """The model's pharmacokinetic evaluation against the template's studies, and its QIVIVE."""
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
    """The template's simulation scenarios as sentences; their outputs are the model's outputs."""
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
    """ROBOT's fields from the PBPK Model Reporting Template (Tan et al. 2020), for one of its models."""
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
    """ROBOT's fields from the curated layout of one model."""
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
    """The crate's chemicals, with their identifiers as identifier and value and their weight as a number."""
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
    """A model's row: its entity's fields, then the crate's it lacks; its links to records and terms, its
    citations as publications and its requirements as texts."""
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
    # The crate's authors are the model's creators in the profile.
    row.setdefault("creator", []).extend(row.pop("author", []))
    return row


def zenodo(row: dict, hit: dict, nodes: dict, others: dict) -> None:
    """The fields of the model's Zenodo record: its page, DOI and date; its name, license, keywords and
    creators where the crate has none."""
    metadata = hit["metadata"]
    fill(row, "name", [metadata["title"]])
    licences = [licence(value["@id"]) for value in row.get("license", []) if isinstance(value, dict) and "@id" in value]
    row["license"] = licences
    if not any(str(value.get("@id", "")).startswith("https://spdx.org/") for value in licences) and isinstance(metadata.get("license"), dict):
        row["license"] = [licence(metadata["license"]["id"])]
    fill(row, "keywords", metadata.get("keywords") or [])
    keywords = []
    for keyword in row.get("keywords", []):
        keywords.append(term(keyword, "glossary") if isinstance(keyword, str) else keyword)
    row["keywords"] = keywords
    row["isBasedOn"] = link(hit["links"]["self_html"])
    if present(hit.get("doi")):
        row["sameAs"] = link("https://doi.org/" + hit["doi"])
    if present(metadata.get("publication_date")):
        row["datePublished"] = {"@value": metadata["publication_date"], "@type": DATE}
    if "creator" in row or "author" in row:
        return
    for creator in metadata.get("creators") or []:
        last, _, first = str(creator.get("name", "")).partition(", ")
        person = {"@id": "zenodo", "@type": ["Person"], "https://schema.org/name": [{"@value": f"{first} {last}" if first else last}]}
        if present(creator.get("orcid")):
            person["@id"] = "https://orcid.org/" + creator["orcid"]
        row.setdefault("creator", []).append(record(nodes, person, others))


def reported(described: dict, main: dict) -> dict | None:
    """The template's model whose files include the crate's main entity."""
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
