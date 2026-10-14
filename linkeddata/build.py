"""The build: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
checked with rdfsolve against the model, and written to an Oxigraph store (one named graph per
source) and, as one JSON-LD document per page, to SQLite."""

import hashlib
import importlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pyoxigraph as ox
import requests
import yaml
from pyld import jsonld
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query

from linkeddata.lift import lift
from linkeddata.model import ontology, settings, shapes

SOURCES_DIR = Path(__file__).parent / "sources"
TARGET = "VHP4Safety model v1"
RECORDS = "SELECT DISTINCT ?record ?type WHERE { ?record a ?type }"
# A record's page: its statements and the names of what it links to.
PAGE = """
CONSTRUCT { ?record ?predicate ?value . ?value <https://schema.org/name> ?name . }
WHERE { ?record ?predicate ?value . OPTIONAL { ?value <https://schema.org/name> ?name } }
"""


def fetch(url: str) -> bytes:
    response = requests.get(url, timeout=60, headers={"User-Agent": "VHP4Safety platform build"})
    response.raise_for_status()
    return response.content


def convert(spec: dict, content: bytes, base: str) -> tuple[ox.Dataset, list[str]]:
    """The statements of one source in the model, and the CONSTRUCT queries that made them."""
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    rows = lift(parser.parse(content), base + "sources/" + spec["name"] + "#", base)
    with SchemaMiner.from_graph(rows, delay=0) as miner:
        source = Client(miner.mine(dataset_name=spec["name"]), rows)
    statements = ox.Dataset()
    queries = []
    for kind, arguments in spec["rules"].items():
        rules = []
        for argument in arguments:
            rules.append(Rule.between(client=source, focus=kind, **argument))
        queries.append(write_query(rules, title=f"{spec['name']}: {kind}", source=source, target=TARGET))
        for quad in Profile(spec["name"], rules).run(source):
            statements.add(quad)
    return statements, queries


def check(data: ox.Dataset, classes: list[str]) -> list[dict]:
    """The records of each class of the model, extracted with rdfsolve and checked against the model."""
    with SchemaMiner.from_graph(data, delay=0) as miner:
        mined = miner.mine(dataset_name="platform")
    client = Client(mined, data)
    model_shapes = shapes()
    vocabulary = ontology()
    notes = []
    for kind in classes:
        fields = []
        for pattern in mined.patterns:
            if pattern.subject_class == kind and (kind, pattern.property_uri) not in fields:
                fields.append((kind, pattern.property_uri))
        if not fields:
            continue
        extraction = client.extract(mined.select(fields=fields), root_class=kind)
        for violation in extraction.assess(model_shapes, ontology=vocabulary, inference="rdfs").violations:
            notes.append({
                "iri": violation.focus.value if violation.focus else "",
                "field": violation.path.value if violation.path else "",
                "value": violation.value.value if violation.value else "",
                "reason": " ".join(violation.messages),
            })
    return notes


def context(config: dict) -> dict:
    """The JSON-LD context: schema.org terms without a prefix, other vocabularies with theirs."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    return terms


def documents(store: ox.Store, config: dict) -> list[tuple[str, str, str]]:
    """One JSON-LD document for each record under the base."""
    rows = []
    for solution in store.query(RECORDS, use_default_graph_as_union=True):
        record = solution["record"]
        if not record.value.startswith(config["base"]):
            continue
        page = list(store.query(PAGE, substitutions={ox.Variable("record"): record}, use_default_graph_as_union=True))
        statements = ox.serialize(page, format=ox.RdfFormat.N_TRIPLES).decode()
        document = jsonld.compact(jsonld.from_rdf(statements, {"format": "application/n-quads"}), context(config))
        rows.append((record.value, solution["type"].value, json.dumps(document, indent=2)))
    return rows


def write(path: Path, documents: list[tuple[str, str, str]], sources: list[dict], notes: list[dict]) -> None:
    """The database is written next to the old one and then put in its place, so a reader never sees half a build."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(temporary)) as db:
        db.execute("CREATE TABLE documents (iri TEXT PRIMARY KEY, type TEXT NOT NULL, document TEXT NOT NULL)")
        db.execute("CREATE TABLE sources (name TEXT PRIMARY KEY, url TEXT, fetched TEXT, sha256 TEXT, queries TEXT)")
        db.execute("CREATE TABLE notes (iri TEXT, field TEXT, value TEXT, reason TEXT)")
        db.executemany("INSERT INTO documents VALUES (?, ?, ?)", documents)
        db.executemany("INSERT INTO sources VALUES (:name, :url, :fetched, :sha256, :queries)", sources)
        db.executemany("INSERT INTO notes VALUES (:iri, :field, :value, :reason)", notes)
        db.commit()
    temporary.replace(path)


def build(out: Path) -> Path:
    config = settings()
    out.mkdir(parents=True, exist_ok=True)
    new_store = out / "rdf.tmp"
    shutil.rmtree(new_store, ignore_errors=True)
    store = ox.Store(str(new_store))
    everything = ox.Dataset()
    sources = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        content = fetch(spec["url"])
        converted, queries = convert(spec, content, config["base"])
        graph = ox.NamedNode(config["base"] + "sources/" + spec["name"])
        for quad in converted:
            store.add(ox.Quad(quad.subject, quad.predicate, quad.object, graph))
            everything.add(quad)
        sources.append({
            "name": spec["name"],
            "url": spec["url"],
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(content).hexdigest(),
            "queries": "\n\n".join(queries),
        })
        print(f"{spec['name']}: {len(converted)} statements")
    notes = check(everything, config["classes"])
    print(f"{len(notes)} notes")
    database = out / "platform.sqlite"
    write(database, documents(store, config), sources, notes)
    store.flush()
    del store
    shutil.rmtree(out / "rdf", ignore_errors=True)
    new_store.rename(out / "rdf")
    return database
