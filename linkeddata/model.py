"""The data model: the vocabularies, classes and application profile of one model version."""

import json
from functools import cache
from pathlib import Path

import requests
import yaml
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import SH
from rdfsolve.schema_models import MinedSchema

MODEL_DIR = Path(__file__).parent / "model" / "v1"
# The vocabulary of SHACL forms, which the application profile uses to guide the editor.
DASH = Namespace("http://datashapes.org/dash#")


def settings() -> dict:
    return yaml.safe_load((MODEL_DIR / "model.yaml").read_text(encoding="utf-8"))


def vocabularies(config: dict) -> list[Path]:
    """The vocabulary files, kept in the model folder and downloaded when one is missing."""
    files = []
    for name, url in config["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        files.append(path)
    return files


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
    """The checks of the model: the approved schema's value types of the fields the profile has, and the
    application profile next to them. They are not merged, so that a recommendation of the profile
    (sh:Warning) never makes a value of the wrong type a recommendation too."""
    schema = MinedSchema.from_json(MODEL_DIR / "schema.json")
    paths = [str(path) for path in profile().objects(None, SH.path) if isinstance(path, URIRef)]
    generated = schema.model_copy(update={"shape_profile": None}).to_shacl(properties=paths)
    return Graph().parse(data=generated, format="turtle") + profile()


@cache
def ontology() -> Graph:
    """The vocabularies of the model, for the class hierarchy the checks need."""
    graph = Graph()
    for path in vocabularies(settings()):
        graph.parse(path, format="json-ld" if path.suffix == ".jsonld" else "turtle")
    return graph

