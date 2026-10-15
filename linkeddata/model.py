"""The data model: the vocabularies, classes and application profile of one model version."""

import hashlib
import json
from functools import cache
from pathlib import Path

import requests
import yaml
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SH
from rdfsolve.schema_models import MinedSchema

MODEL_DIR = Path(__file__).parent / "model" / "v1"
# The vocabulary of SHACL forms, which the application profile uses to guide the editor.
DASH = Namespace("http://datashapes.org/dash#")


@cache
def settings() -> dict:
    return yaml.safe_load((MODEL_DIR / "model.yaml").read_text(encoding="utf-8"))


def vocabularies(config: dict) -> list[Path]:
    """The vocabulary files, kept in the model folder; only `python -m linkeddata model` downloads them."""
    files = []
    for name in config["vocabularies"]:
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            raise FileNotFoundError(f"The vocabulary {path} is missing: run python -m linkeddata model.")
        files.append(path)
    return files


def download_vocabularies() -> list[str]:
    """The missing vocabulary files are downloaded from their pinned addresses. What does not match its
    SHA-256 in model.yaml is given back."""
    problems = []
    for name, pinned in settings()["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            response = requests.get(pinned["url"], timeout=60)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        found = hashlib.sha256(path.read_bytes()).hexdigest()
        if found != pinned.get("sha256"):
            problems.append(f"{path} has SHA-256 {found}, where model.yaml pins {pinned.get('sha256')}.")
    return problems


def write_schema() -> Path:
    """The approved schema is generated from the vocabularies and the profile."""
    config = settings()
    schema = MinedSchema.from_vocabulary(vocabularies(config), config["classes"], profile=MODEL_DIR / "profile.ttl")
    path = MODEL_DIR / "schema.json"
    path.write_text(json.dumps(schema.to_dict(), indent=1) + "\n", encoding="utf-8")
    return path


@cache
def profile() -> Graph:
    """The application profile: required, fixed and single values, and the guidance of the editor's form."""
    return Graph().parse(MODEL_DIR / "profile.ttl", format="turtle")


def curie(iri: str) -> str:
    """An address written with the model's prefixes: https://schema.org/name is schema:name."""
    for prefix, namespace in settings()["prefixes"].items():
        if iri.startswith(namespace):
            return prefix + ":" + iri.removeprefix(namespace)
    return iri


def property_shapes(graph: Graph, kind: str) -> dict[str, list]:
    """The property shapes of the node shapes that target a class, by the address of their path."""
    found = {}
    for shape in graph.subjects(SH.targetClass, URIRef(kind)):
        for prop in graph.objects(shape, SH.property):
            found.setdefault(str(graph.value(prop, SH.path)), []).append(prop)
    return found


@cache
def shapes() -> Graph:
    """The checks of the model: the approved schema's value types of the fields the profile has, with the
    profile's rules."""
    schema = MinedSchema.from_json(MODEL_DIR / "schema.json")
    return Graph().parse(data=schema.to_shacl(properties="profile"), format="turtle")


@cache
def vocabulary(path: Path) -> Graph:
    return Graph().parse(path, format="json-ld" if path.suffix == ".jsonld" else "turtle")


@cache
def ontology() -> Graph:
    """The vocabularies of the model, for the class hierarchy the checks need."""
    graph = Graph()
    for path in vocabularies(settings()):
        graph += vocabulary(path)
    return graph


def terms(iris: list[str]) -> dict[str, dict]:
    """The terms of the vocabularies at these addresses, such as the steps of the glossary, with their label,
    their description, and the title of their vocabulary."""
    found = {}
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

