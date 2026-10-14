"""The data model: the vocabularies, classes and application profile of one model version."""

import json
from pathlib import Path

import requests
import yaml
from rdflib import Graph
from rdfsolve.schema_models import MinedSchema

MODEL_DIR = Path(__file__).parent / "model" / "v1"


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


def shapes() -> Graph:
    """The checks of the model: the approved schema's value types, made active (the profile is part of it)."""
    schema = MinedSchema.from_json(MODEL_DIR / "schema.json")
    return Graph().parse(data=schema.to_shacl(activate_observed=True), format="turtle")


def ontology() -> Graph:
    """The vocabularies of the model, for the class hierarchy the checks need."""
    graph = Graph()
    for path in vocabularies(settings()):
        graph.parse(path, format="json-ld" if path.suffix == ".jsonld" else "turtle")
    return graph
