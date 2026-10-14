"""The imports: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
checked against the model, and stored as records in place of those the source gave before. Records
written on the platform are left as they are. `python -m linkeddata import` runs every import, for
example every night."""

import hashlib
import importlib
from datetime import datetime, timezone
from pathlib import Path

import pyoxigraph as ox
import requests
import yaml
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query
from sqlalchemy import delete, insert, select

from linkeddata import database, rdf
from linkeddata.database import PLATFORM, Note, Record, Source
from linkeddata.lift import lift
from linkeddata.model import MODEL_DIR, ontology, settings, shapes

SOURCES_DIR = Path(__file__).parent / "sources"
TARGET = "VHP4Safety model v1"
TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


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


def records_of(data: ox.Dataset, classes: list[str], source: str) -> list[dict]:
    """The rows of the records of each class in converted data, as rdfsolve reads them."""
    client = Client.open(MODEL_DIR / "schema.json", data)
    rows = []
    for kind in classes:
        iris = set()
        for quad in data.quads_for_predicate(TYPE):
            if quad.object == ox.NamedNode(kind):
                iris.add(quad.subject.value)
        if iris:
            selection = client.fetch(sorted(iris), *rdf.fields(kind).index, kind=kind)
            rows.extend(rdf.rows(selection, kind, source))
    return rows


def store(source: Source, rows: list[dict], notes: list[dict]) -> None:
    """The records of a source replace those it gave before, except the records written on the platform."""
    with database.session() as db, db.begin():
        written = set(db.scalars(select(Record.iri).where(Record.source == PLATFORM)))
        db.execute(delete(Record).where(Record.source == source.name))
        kept = {}
        for row in rows:
            if row["iri"] not in written:
                kept[row["iri"]] = row
        if kept:
            db.execute(insert(Record), list(kept.values()))
        db.execute(delete(Note).where(Note.source == source.name))
        for note in notes:
            db.add(Note(source=source.name, **note))
        db.merge(source)


def import_source(spec: dict, offline: bool) -> None:
    config = settings()
    downloaded = database.STATE_DIR / "downloads" / spec["name"]
    if offline:
        content = downloaded.read_bytes()
    else:
        content = fetch(spec["url"])
        downloaded.parent.mkdir(parents=True, exist_ok=True)
        downloaded.write_bytes(content)
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    data, queries = convert(spec, parser.parse(content), config["base"])
    notes = check(data, config["classes"])
    rows = records_of(data, config["classes"], spec["name"])
    source = Source(
        name=spec["name"],
        url=spec["url"],
        fetched_at=datetime.fromtimestamp(downloaded.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
        sha256=hashlib.sha256(content).hexdigest(),
        queries="\n\n".join(queries),
    )
    store(source, rows, notes)
    print(f"{spec['name']}: {len(rows)} records, {len(notes)} notes")


def import_all(offline: bool = False) -> None:
    """Every source that is fetched (it has a url) is imported; with *offline*, from its last download."""
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "url" in spec:
            import_source(spec, offline)
