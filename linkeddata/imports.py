"""The imports: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
checked against the model, and stored as records in place of those the source gave before. Records
written on the platform are left as they are. `python -m linkeddata import` runs every import, for
example every night."""

import hashlib
import importlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pyoxigraph as ox
import pyshacl
import requests
import yaml
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SH
from sqlalchemy import delete, func, insert, select

import database
from database.tables import PLATFORM, Note, Record, Source
from linkeddata import forms, rdf
from linkeddata.lift import lift
from linkeddata.model import ontology, profile, settings, shapes

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
    vocabulary = base + "sources/" + spec["name"] + "#"
    rows = lift(data, vocabulary, base, spec.get("kinds"))
    with SchemaMiner.from_graph(rows, delay=0) as miner:
        source = Client(miner.mine(dataset_name=spec["name"]), rows)
    statements = ox.Dataset()
    queries = []
    for kind, arguments in spec["rules"].items():
        rules = []
        for argument in arguments:
            # The kinds and fields are given as addresses, so that a rule stays when the data has none of them.
            if "object" in argument:
                steps = []
                for step in argument["object"].split("/"):
                    steps.append(f"<{vocabulary}{step}>")
                argument = {**argument, "object": "/".join(steps)}
            rules.append(Rule.between(client=source, focus=vocabulary + kind, **argument))
        queries.append(write_query(rules, title=f"{spec['name']}: {kind}", source=source, target=TARGET))
        for quad in Profile(spec["name"], rules).run(source):
            statements.add(quad)
    return statements, queries


def check(data: ox.Dataset) -> list[dict]:
    """The records in converted data, checked with pyshacl against the model and the class hierarchy of its
    vocabularies. The records of other sources that they link to are in the data with their class only,
    and are not reported."""
    graph = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    described = set()
    for subject, predicate in graph.subject_predicates():
        if predicate != RDF.type:
            described.add(subject)
    _, results, _ = pyshacl.validate(graph, shacl_graph=shapes(), ont_graph=ontology())
    notes = []
    for result in results.subjects(RDF.type, SH.ValidationResult):
        if results.value(result, SH.focusNode) not in described:
            continue
        messages = []
        for message in results.objects(result, SH.resultMessage):
            messages.append(str(message))
        notes.append({
            "iri": str(results.value(result, SH.focusNode)),
            "field": str(results.value(result, SH.resultPath) or ""),
            "value": str(results.value(result, SH.value) or ""),
            "reason": " ".join(messages),
            "component": str(results.value(result, SH.sourceConstraintComponent)),
        })
    return notes


def records_of(data: ox.Dataset, classes: list[str], source: str) -> list[dict]:
    """The rows of the records of each class in converted data, each with its JSON-LD document."""
    graph = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    rows = []
    for kind in classes:
        fields = {}
        for field in forms.form(kind):
            fields[field["iri"]] = field
        for subject in sorted(set(graph.subjects(RDF.type, URIRef(kind)))):
            own = Graph()
            for _, predicate, value in graph.triples((subject, None, None)):
                field = fields.get(str(predicate))
                # A text where a field takes only links, or a link where it takes only texts, is left out; the checks note it.
                if field and ((isinstance(value, Literal) and not field["texts"]) or (isinstance(value, URIRef) and not field["links"])):
                    continue
                own.add((subject, predicate, value))
            rows.append(rdf.row(rdf.document(own), kind, source))
    return rows


def known_types(source: str) -> list[ox.Quad]:
    """The classes of the records of the other sources, so that links to them are checked against their class."""
    with database.session() as db:
        found = db.execute(select(Record.iri, Record.type).where(Record.source != source)).all()
    quads = []
    for iri, kind in found:
        quads.append(ox.Quad(ox.NamedNode(iri), TYPE, ox.NamedNode(kind)))
    return quads


class Refused(Exception):
    """An import that would remove most of a source's records, which an upstream fault usually explains."""


def store(source: Source, rows: list[dict], notes: list[dict]) -> None:
    """The records of a source replace those it gave before, except the records written on the platform.
    An import that gives no records, or less than half of those it gave before, is refused."""
    with database.session() as db, db.begin():
        before = db.scalar(select(func.count()).select_from(Record).where(Record.source == source.name))
        if not rows or (before >= 10 and len(rows) < before / 2):
            raise Refused(f"the source gave {len(rows)} records where it gave {before} before; the records were kept")
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


ENTRY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def download(spec: dict, offline: bool) -> dict[str, bytes]:
    """The files of a source by name, fetched, or as the last import fetched them when *offline*. A source
    with entries also has, by its key, the file of each entry of its index (a JSON object)."""
    folder = database.STATE_DIR / "downloads" / spec["name"]
    contents = {}
    for name, url in files_of(spec).items():
        path = folder / name
        if not offline:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(fetch(url))
        contents[name] = path.read_bytes()
    if "entries" in spec:
        for key in json.loads(contents[spec["name"]]):
            # The keys come from upstream and name files here, so only plain names are taken.
            if not ENTRY.fullmatch(key) or key == spec["name"]:
                continue
            path = folder / key
            if not offline:
                try:
                    path.write_bytes(fetch(spec["entries"].format(key=key)))
                except requests.RequestException as problem:
                    print(f"{spec['name']}: {key} not fetched ({problem})")
            if path.exists():
                contents[key] = path.read_bytes()
    return contents


def import_source(spec: dict, offline: bool) -> None:
    config = settings()
    contents = download(spec, offline)
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    # A source of one file gives its parser the file; a source of several gives them by name.
    parsed = parser.parse(contents if "files" in spec or "entries" in spec else contents[spec["name"]])
    data, queries = convert(spec, parsed, config["base"])
    notes = check(ox.Dataset([*data, *known_types(spec["name"])]))
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


def note_problem(spec: dict, problem: Exception) -> None:
    """A source whose import failed keeps its records; why is shown on the sources page."""
    with database.session() as db, db.begin():
        source = db.get(Source, spec["name"])
        if source is None:
            source = Source(name=spec["name"], url=" ".join(files_of(spec).values()), fetched_at="", sha256="", queries="")
            db.add(source)
        source.problem = str(problem)


def import_all(offline: bool = False) -> list[str]:
    """Every source that is fetched is imported, with *offline* from its last download, and the records
    written on the platform are checked again. The problems of the sources that could not be imported
    are given back; their records are kept."""
    problems = []
    for spec in specs():
        try:
            import_source(spec, offline)
        except (Refused, requests.RequestException, OSError, ValueError) as problem:
            note_problem(spec, problem)
            problems.append(f"{spec['name']}: {problem}")
    check_written()
    return problems
