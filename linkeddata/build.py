"""The build: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
joined with the platform's own records, checked with rdfsolve against the model, and written to an
Oxigraph store (one named graph per source) and, as one JSON-LD document per page, to SQLite."""

import fcntl
import hashlib
import importlib
import json
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pyoxigraph as ox
import requests
import yaml
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query

from linkeddata import records
from linkeddata.document import compact
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


def convert(spec: dict, data, base: str) -> tuple[ox.Dataset, list[str]]:
    """The statements of one source's data (parsed rows, or a received document) in the model,
    and the CONSTRUCT queries that made them."""
    rows = lift(data, base + "sources/" + spec["name"] + "#", base, spec.get("kinds"))
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


def documents(store: ox.Store, config: dict) -> list[tuple[str, str, str]]:
    """One JSON-LD document for each record under the base."""
    rows = []
    for solution in store.query(RECORDS, use_default_graph_as_union=True):
        record = solution["record"]
        if not record.value.startswith(config["base"]):
            continue
        page = list(store.query(PAGE, substitutions={ox.Variable("record"): record}, use_default_graph_as_union=True))
        statements = ox.serialize(page, format=ox.RdfFormat.N_TRIPLES).decode()
        rows.append((record.value, solution["type"].value, json.dumps(compact(statements, config), indent=2)))
    return rows


def write(path: Path, documents: list, sources: list[dict], notes: list[dict], gone: list) -> None:
    """The database is written next to the old one and then put in its place, so a reader never sees half a build."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(temporary)) as db:
        db.execute("CREATE TABLE documents (iri TEXT PRIMARY KEY, type TEXT NOT NULL, document TEXT NOT NULL)")
        db.execute("CREATE TABLE sources (name TEXT PRIMARY KEY, url TEXT, fetched TEXT, sha256 TEXT, queries TEXT)")
        db.execute("CREATE TABLE notes (iri TEXT, field TEXT, value TEXT, reason TEXT)")
        db.execute("CREATE TABLE gone (iri TEXT PRIMARY KEY, removed TEXT)")
        db.executemany("INSERT INTO documents VALUES (?, ?, ?)", documents)
        db.executemany("INSERT INTO sources VALUES (:name, :url, :fetched, :sha256, :queries)", sources)
        db.executemany("INSERT INTO notes VALUES (:iri, :field, :value, :reason)", notes)
        db.executemany("INSERT INTO gone VALUES (?, ?)", gone)
        db.commit()
    temporary.replace(path)


def own_records(base: str) -> tuple[ox.Dataset, list]:
    """The platform's own records, and the addresses of the removed ones."""
    data = ox.Dataset()
    for path in records.files(".jsonld"):
        for quad in ox.parse(path=path, format=ox.RdfFormat.JSON_LD):
            data.add(quad)
    gone = []
    for path in records.files(".gone"):
        address = base + str(path.relative_to(records.RECORDS_DIR).with_suffix(""))
        gone.append((address, json.loads(path.read_text(encoding="utf-8"))["removed"]))
    return data, gone


def build_once(out: Path, offline: bool) -> Path:
    config = settings()
    data, gone = own_records(config["base"])
    written = set()
    for quad in data:
        written.add(quad.subject)
    new_store = out / "rdf.tmp"
    shutil.rmtree(new_store, ignore_errors=True)
    store = ox.Store(str(new_store))
    everything = ox.Dataset()
    for quad in data:
        store.add(ox.Quad(quad.subject, quad.predicate, quad.object, ox.NamedNode(config["base"] + "records")))
        everything.add(quad)
    sources = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "url" not in spec:
            continue
        downloaded = out / "downloads" / spec["name"]
        if offline:
            content = downloaded.read_bytes()
        else:
            content = fetch(spec["url"])
            downloaded.parent.mkdir(parents=True, exist_ok=True)
            downloaded.write_bytes(content)
        parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
        converted, queries = convert(spec, parser.parse(content), config["base"])
        graph = ox.NamedNode(config["base"] + "sources/" + spec["name"])
        for quad in converted:
            # A record written through the platform replaces what a source gives for the same address.
            if quad.subject in written:
                continue
            store.add(ox.Quad(quad.subject, quad.predicate, quad.object, graph))
            everything.add(quad)
        sources.append({
            "name": spec["name"],
            "url": spec["url"],
            "fetched": datetime.fromtimestamp(downloaded.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(content).hexdigest(),
            "queries": "\n\n".join(queries),
        })
        print(f"{spec['name']}: {len(converted)} statements")
    notes = check(everything, config["classes"])
    print(f"{len(notes)} notes")
    database = out / "platform.sqlite"
    write(database, documents(store, config), sources, notes, gone)
    store.flush()
    del store
    shutil.rmtree(out / "rdf", ignore_errors=True)
    new_store.rename(out / "rdf")
    return database


def build(out: Path, offline: bool = False) -> Path | None:
    """One build at a time: a build asked for while another runs is done by the running one when it ends."""
    out.mkdir(parents=True, exist_ok=True)
    pending = out / "pending"
    with open(out / "build.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        while True:
            pending.unlink(missing_ok=True)
            database = build_once(out, offline)
            if not pending.exists():
                return database


def request_build(out: Path) -> None:
    """A build with the sources downloaded by the last build is started in the background."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "pending").touch()
    subprocess.Popen([sys.executable, "-m", "linkeddata", "build", "--offline", "--out", str(out)], start_new_session=True)
