"""The imports: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
checked against the model, and stored as records in place of those the source gave before. Records
written on the platform are left as they are. `python -m linkeddata import` runs every import, for
example every night."""

import hashlib
import importlib
import json
import re
from pathlib import Path

import pyoxigraph as ox
import requests
import yaml
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query
from rdflib import RDF, Graph, URIRef
from sqlalchemy import delete, func, insert, select

import database
from database.tables import PLATFORM, Note, Record, Source, now
from linkeddata import rdf, tables
from linkeddata.model import RELEASE, settings

SOURCES_DIR = Path(__file__).parent / "sources"
TARGET = f"VHP4Safety model {RELEASE}"


def fetch(url: str) -> bytes:
    response = requests.get(url, timeout=60, headers={"User-Agent": "VHP4Safety platform build"})
    response.raise_for_status()
    return response.content


def lift(rows: list[dict], vocabulary: str, base: str) -> ox.Dataset:
    """Parsed rows as RDF, until rdfsolve reads JSON with a context itself: their fields become properties
    in the source's own vocabulary, "@id" gives a row its address, and "@type" its kind."""
    document = {"@context": {"@vocab": vocabulary, "@base": base}, "@graph": rows}
    return ox.Dataset(ox.parse(json.dumps(document).encode(), format=ox.RdfFormat.JSON_LD))


def convert(spec: dict, data: list[dict], base: str) -> tuple[ox.Dataset, list[str]]:
    """The statements of one source's parsed rows in the model, and the CONSTRUCT queries that made them."""
    vocabulary = base + "sources/" + spec["name"] + "#"
    rows = lift(data, vocabulary, base)
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


def records_of(data: ox.Dataset, classes: list[str], source: str) -> list[tuple[dict, Graph]]:
    """The records of each class in converted data: the row of each in the records table, and its own
    statements. Values are kept as the source gives them; the checks note those that do not fit the model."""
    graph = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    found = []
    for kind in classes:
        for subject in sorted(set(graph.subjects(RDF.type, URIRef(kind)))):
            own = Graph()
            for statement in graph.triples((subject, None, None)):
                own.add(statement)
            found.append((rdf.row(own, str(subject), kind, source), own))
    return found


class Refused(Exception):
    """An import that would remove most of a source's records, which an upstream fault usually explains."""


def store(source: Source, found: list[tuple[dict, Graph]], notes: list[dict]) -> None:
    """The records of a source replace those it gave before, except the records written on the platform.
    An import that gives no records, or less than half of those it gave before, is refused."""
    with database.session() as db, db.begin():
        before = db.scalar(select(func.count()).select_from(Record).where(Record.source == source.name))
        if not found or (before >= 10 and len(found) < before / 2):
            raise Refused(f"the source gave {len(found)} records where it gave {before} before; the records were kept")
        written = set(db.scalars(select(Record.iri).where(Record.source == PLATFORM)))
        for iri in db.scalars(select(Record.iri).where(Record.source == source.name)):
            tables.delete(db, iri)
        db.execute(delete(Record).where(Record.source == source.name))
        kept = {}
        for row, statements in found:
            if row["iri"] not in written:
                kept[row["iri"]] = row
                tables.save(db, statements, row["iri"])
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


def download(spec: dict) -> dict[str, bytes]:
    """The files of a source by name. A source with entries also has, by its key, the file of each entry
    of its index (a JSON object)."""
    contents = {}
    for name, url in files_of(spec).items():
        contents[name] = fetch(url)
    if "entries" in spec:
        for key in json.loads(contents[spec["name"]]):
            # The keys come from upstream and are put in addresses, so only plain names are taken.
            if not ENTRY.fullmatch(key) or key == spec["name"]:
                continue
            try:
                contents[key] = fetch(spec["entries"].format(key=key))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {key} not fetched ({problem})")
    return contents


def import_source(spec: dict) -> None:
    config = settings()
    contents = download(spec)
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    # A source of one file gives its parser the file; a source of several gives them by name.
    parsed = parser.parse(contents if "files" in spec or "entries" in spec else contents[spec["name"]])
    data, queries = convert(spec, parsed, config["base"])
    notes = rdf.notes(Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt"))
    found = records_of(data, list(config["kinds"].values()), spec["name"])
    checksum = hashlib.sha256()
    for name in sorted(contents):
        checksum.update(contents[name])
    source = Source(
        name=spec["name"],
        url=" ".join(files_of(spec).values()),
        fetched_at=now(),
        sha256=checksum.hexdigest(),
        queries="\n\n".join(queries),
    )
    store(source, found, notes)
    print(f"{spec['name']}: {len(found)} records, {len(notes)} notes")


def specs() -> list[dict]:
    """The sources that are fetched (they have a url or files), as their files in sources/ describe them."""
    found = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "url" in spec or "files" in spec:
            found.append(spec)
    return found


def check_written() -> None:
    """The records written on the platform are checked again against the model, which may have changed
    since they were written; what no longer fits is noted for the data quality page."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.source == PLATFORM, Record.removed_at.is_(None))))
    notes = rdf.notes(rdf.graph(iris))
    with database.session() as db, db.begin():
        db.execute(delete(Note).where(Note.source == PLATFORM))
        for note in notes:
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


def import_all() -> list[str]:
    """Every source that is fetched is imported, and the records written on the platform are checked
    again. The problems of the sources that could not be imported are given back; their records are kept."""
    problems = []
    for spec in specs():
        try:
            import_source(spec)
        except (Refused, requests.RequestException, OSError, ValueError) as problem:
            note_problem(spec, problem)
            problems.append(f"{spec['name']}: {problem}")
    check_written()
    return problems
