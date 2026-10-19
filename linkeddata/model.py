"""The data model: the vocabularies, classes and application profile of one model version."""

import hashlib
import json
from functools import cache
from pathlib import Path

import requests
import yaml
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SH, VOID
from rdfsolve.client.sql_tables import layout
from rdfsolve.schema_models import MinedSchema

from linkeddata import patches

# The served release: its model is in model/<release>, its tables in database/<release>.
RELEASE = "v1"
MODEL_DIR = Path(__file__).parent / "model" / RELEASE
# The release's tables, written from its profile by `python -m linkeddata model`.
TABLES = Path(__file__).parent.parent / "database" / RELEASE / "tables.sql"


FORM = Namespace("https://platform.vhp4safety.nl/model/v1/form#")
SOURCES_DIR = Path(__file__).parent / "sources"


@cache
def settings() -> dict:
    """The model's settings, as its profile states them: its title and the address space of its records (the
    ontology's label and void:uriSpace), the files it is built from (owl:imports, each with form:file and
    form:sha256) and those its sources read (pinned in sources/<name>.yaml), its kinds of records (node shapes
    with form:path, in sh:order), the prefixes of its JSON-LD (sh:declare) and the JSON-LD names of other
    vocabularies' properties (form:term)."""
    graph = profile()
    header = graph.value(None, RDF.type, OWL.Ontology)
    files = {}
    for imported in graph.objects(header, OWL.imports):
        files[str(graph.value(imported, FORM.file))] = {"url": str(imported), "sha256": str(graph.value(imported, FORM.sha256))}
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "pinned" in spec:
            files[spec["vocabulary"]] = {"url": spec["pinned"]["url"], "sha256": str(spec["pinned"]["sha256"])}
    kinds = []
    for shape, path in graph.subject_objects(FORM.path):
        kinds.append((int(graph.value(shape, SH.order) or 0), str(path), str(graph.value(shape, SH.targetClass))))
    prefixes = {}
    for declared in graph.objects(header, SH.declare):
        prefixes[str(graph.value(declared, SH.prefix))] = str(graph.value(declared, SH.namespace))
    terms = {}
    for iri, name in graph.subject_objects(FORM["term"]):
        terms[str(name)] = str(iri)
    return {"title": str(graph.value(header, RDFS.label)), "base": str(graph.value(header, VOID.uriSpace)), "vocabularies": files,
            "kinds": {path: of_class for _, path, of_class in sorted(kinds)}, "prefixes": prefixes, "terms": dict(sorted(terms.items()))}


def vocabularies(config: dict) -> list[Path]:
    """The RDF vocabulary files of the model folder; only `python -m linkeddata model` downloads them. A pinned
    file of another format, such as a JSON licence list, is read by its source only."""
    files = []
    for name in config["vocabularies"]:
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run python -m linkeddata model.")
        if path.suffix in (".ttl", ".jsonld"):
            files.append(path)
    return files


def pinned_problems() -> list[str]:
    """The vocabulary files that are missing or do not match the SHA-256 the profile or their source pins."""
    problems = []
    for name, pinned in settings()["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            problems.append(f"{path} is missing: run python -m linkeddata model.")
            continue
        found = hashlib.sha256(path.read_bytes()).hexdigest()
        if found != pinned.get("sha256"):
            problems.append(f"{path} has SHA-256 {found}, where it is pinned as {pinned.get('sha256')}.")
    return problems


def download_vocabularies() -> list[str]:
    """Missing vocabulary files are downloaded from their pinned addresses; mismatches are given back."""
    for name, pinned in settings()["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            response = requests.get(pinned["url"], timeout=60)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
    return pinned_problems()


def approved_schema() -> dict:
    """The approved schema of the profile's classes, from the vocabularies and the profile."""
    config = settings()
    classes = sorted({str(kind) for kind in profile().objects(None, SH.targetClass)})
    # The profile is a vocabulary too: it declares the platform's own terms, such as its PBPK ones.
    return patches.from_vocabulary(vocabularies(config) + [MODEL_DIR / "profile.ttl"], classes, MODEL_DIR / "profile.ttl").to_dict()


def write_schema() -> Path:
    path = MODEL_DIR / "schema.json"
    path.write_text(json.dumps(approved_schema(), indent=1) + "\n", encoding="utf-8")
    return path


def schema_problems() -> list[str]:
    """Whether schema.json is the approved schema."""
    if (MODEL_DIR / "schema.json").read_text(encoding="utf-8") != json.dumps(approved_schema(), indent=1) + "\n":
        return [f"{MODEL_DIR / 'schema.json'} is out of date: run python -m linkeddata model, review and commit it."]
    return []


def tables_sql() -> str:
    return layout(patches.inherited((MODEL_DIR / "profile.ttl").read_text(encoding="utf-8"))).ddl()


def write_tables() -> Path:
    TABLES.parent.mkdir(parents=True, exist_ok=True)
    TABLES.write_text(tables_sql(), encoding="utf-8")
    return TABLES


def tables_problems() -> list[str]:
    """Whether the release's SQL is what the profile gives."""
    if not TABLES.exists() or TABLES.read_text(encoding="utf-8") != tables_sql():
        return [f"{TABLES} is out of date: run python -m linkeddata model, review and commit it."]
    return []


@cache
def profile() -> Graph:
    """The application profile: required, fixed and single values, and the form's guidance."""
    return Graph().parse(MODEL_DIR / "profile.ttl", format="turtle")


@cache
def shapes() -> Graph:
    """The model's checks: the approved schema's value types of the profile's fields, with its rules."""
    schema = MinedSchema.from_json(MODEL_DIR / "schema.json")
    return Graph().parse(data=schema.to_shacl(properties="profile"), format="turtle")


@cache
def vocabulary(path: Path) -> Graph:
    return Graph().parse(path, format="json-ld" if path.suffix == ".jsonld" else "turtle")


@cache
def hierarchy() -> Graph:
    """The vocabularies' class hierarchy (rdfs:subClassOf), so a link to a subclass's record fits."""
    graph = Graph()
    for path in vocabularies(settings()):
        for statement in vocabulary(path).triples((None, RDFS.subClassOf, None)):
            graph.add(statement)
    return graph


def terms(iris: list[str]) -> dict[str, dict]:
    """The vocabulary terms at these addresses, such as the glossary's steps, with label, description and
    vocabulary title."""
    found = {}
    if not iris:
        return found
    for path in vocabularies(settings()):
        graph = vocabulary(path)
        title = path.stem
        for node in graph.subjects(RDF.type, OWL.Ontology):
            title = str(graph.value(node, DCTERMS.title) or title)
        for iri in iris:
            label = graph.value(URIRef(iri), RDFS.label)
            if label is None or iri in found:
                continue
            description = graph.value(URIRef(iri), DC.description) or graph.value(URIRef(iri), RDFS.comment)
            found[iri] = {"name": str(label), "description": str(description or ""), "title": title}
    return found

