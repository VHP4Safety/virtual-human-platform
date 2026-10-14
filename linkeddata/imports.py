"""The imports: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
checked against the model, and stored as records in place of those the source gave before. Records
written on the platform are left as they are. `python -m linkeddata import` runs every import, for
example every night."""

import hashlib
import importlib
from datetime import datetime, timezone
from pathlib import Path

import pyoxigraph as ox
import pyshacl
import requests
import yaml
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query
from rdflib import RDF
from rdflib.namespace import SH
from sqlalchemy import delete, insert, select

from linkeddata import database, rdf
from linkeddata.database import PLATFORM, Note, Record, Source
from linkeddata.lift import lift
from linkeddata.model import MODEL_DIR, ontology, profile, settings, shapes

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
                "component": violation.component,
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


def known_types(source: str) -> list[ox.Quad]:
    """The classes of the records of the other sources, so that links to them are checked against their class."""
    with database.session() as db:
        found = db.execute(select(Record.iri, Record.type).where(Record.source != source)).all()
    quads = []
    for iri, kind in found:
        quads.append(ox.Quad(ox.NamedNode(iri), TYPE, ox.NamedNode(kind)))
    return quads


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


def files_of(spec: dict) -> dict[str, str]:
    """The files of a source by name: the one at its url, or those listed under its files."""
    if "files" in spec:
        return dict(spec["files"])
    return {spec["name"]: spec["url"]}


def download(spec: dict, offline: bool) -> dict[str, bytes]:
    """The files of a source by name, fetched, or as the last import fetched them when *offline*."""
    folder = database.STATE_DIR / "downloads" / spec["name"]
    contents = {}
    for name, url in files_of(spec).items():
        path = folder / name
        if not offline:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(fetch(url))
        contents[name] = path.read_bytes()
    return contents


def import_source(spec: dict, offline: bool) -> None:
    config = settings()
    contents = download(spec, offline)
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    # A source of one file gives its parser the file; a source of several gives them by name.
    parsed = parser.parse(contents if "files" in spec else contents[spec["name"]])
    data, queries = convert(spec, parsed, config["base"])
    notes = check(ox.Dataset([*data, *known_types(spec["name"])]), config["classes"])
    rows = records_of(data, config["classes"], spec["name"])
    checksum = hashlib.sha256()
    for name in sorted(contents):
        checksum.update(contents[name])
    folder = database.STATE_DIR / "downloads" / spec["name"]
    source = Source(
        name=spec["name"],
        url=" ".join(files_of(spec).values()),
        fetched_at=datetime.fromtimestamp(folder.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
        sha256=checksum.hexdigest(),
        queries="\n\n".join(queries),
    )
    store(source, rows, notes)
    print(f"{spec['name']}: {len(rows)} records, {len(notes)} notes")


def specs() -> list[dict]:
    """The sources that are fetched (they have a url or files), as their files in sources/ describe them."""
    found = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "url" in spec or "files" in spec:
            found.append(spec)
    return found


def check_written() -> None:
    """The records written on the platform are checked again against the application profile, which
    may have changed since they were written; what no longer fits is noted for the data quality page."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.source == PLATFORM, Record.removed_at.is_(None))))
    notes = {}
    conforms, results, _ = pyshacl.validate(rdf.graph(iris), shacl_graph=profile())
    for result in results.subjects(RDF.type, SH.ValidationResult):
        note = {
            "iri": str(results.value(result, SH.focusNode)),
            "field": str(results.value(result, SH.resultPath)),
            "value": str(results.value(result, SH.value) or ""),
            "reason": str(results.value(result, SH.resultMessage)),
            "component": str(results.value(result, SH.sourceConstraintComponent)),
        }
        notes[(note["iri"], note["field"], note["value"], note["reason"])] = note
    with database.session() as db, db.begin():
        db.execute(delete(Note).where(Note.source == PLATFORM))
        for note in notes.values():
            db.add(Note(source=PLATFORM, **note))
    print(f"{PLATFORM}: {len(iris)} records, {len(notes)} notes")


def import_all(offline: bool = False) -> None:
    """Every source that is fetched is imported, with *offline* from its last download, and the records
    written on the platform are checked again."""
    for spec in specs():
        import_source(spec, offline)
    check_written()
