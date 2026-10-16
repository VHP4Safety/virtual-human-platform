"""The imports: each source is fetched and cleaned by its parser, converted to the model with rdfsolve,
and stored as records in place of those the source gave before. Records written on the platform are left
as they are. The sources of terms (terms) come last, as they ask for the terms that the records of the
other sources are about. Once every source is stored, the records of each are checked against the model,
with the records they link to as the database holds them. `python -m linkeddata import` runs every import, for
example every night."""

import hashlib
import importlib
import json
import re
from pathlib import Path
from urllib.parse import quote

import pyoxigraph as ox
import requests
import yaml
from rdfsolve import SchemaMiner
from rdfsolve.api import Client
from rdfsolve.conversion import Profile, Rule, write_query
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import SDO, SH
from sqlalchemy import delete, func, insert, select

import database
from database.tables import PLATFORM, Note, Record, Source, now
from linkeddata import checks, storage
from linkeddata.model import MODEL_DIR, RELEASE, profile, settings

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


def records_of(data: ox.Dataset, classes: list[str], source: str) -> list[tuple[list[dict], Graph]]:
    """The records of each class in converted data: the rows of each and of its parts in the records table,
    and its own statements with its parts'. Values are kept as the source gives them; the checks note those
    that do not fit the model."""
    graph = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    found = []
    for kind in classes:
        for subject in sorted(set(graph.subjects(RDF.type, URIRef(kind)))):
            if not isinstance(subject, URIRef):
                continue
            own = storage.described(graph, str(subject))
            found.append((storage.rows(own, str(subject), kind, source), own))
    return found


class Refused(Exception):
    """An import that would remove most of a source's records, which an upstream fault usually explains."""


def store(source: Source, found: list[tuple[list[dict], Graph]]) -> None:
    """The records of a source replace those it gave before, except the records written on the platform and
    those that another source gives, such as a person whom two sources name. An import that gives no
    records, or less than half of those it gave before, is refused."""
    with database.session() as db, db.begin():
        before = db.scalar(select(func.count()).select_from(Record).where(Record.source == source.name, Record.part_of.is_(None)))
        if not found or (before >= 10 and len(found) < before / 2):
            raise Refused(f"the source gave {len(found)} records where it gave {before} before; the records were kept")
        written = set(db.scalars(select(Record.iri).where(Record.source != source.name)))
        for iri in db.scalars(select(Record.iri).where(Record.source == source.name, Record.part_of.is_(None))):
            storage.delete(db, iri)
        db.execute(delete(Record).where(Record.source == source.name))
        kept = {}
        for listed, statements in found:
            if listed[0]["iri"] not in written:
                for row in listed:
                    kept[row["iri"]] = row
                storage.save(db, statements, listed[0]["iri"])
        if kept:
            db.execute(insert(Record), list(kept.values()))
        db.merge(source)


def files_of(spec: dict) -> dict[str, str]:
    """The files of a source by name: the one at its url, those listed under its files, or the pinned
    vocabulary of the model that it names."""
    if "files" in spec:
        return dict(spec["files"])
    if "vocabulary" in spec:
        return {spec["name"]: settings()["vocabularies"][spec["vocabulary"]]["url"]}
    return {spec["name"]: spec["url"]}


ENTRY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def linked_terms() -> list[str]:
    """The addresses that the records give in the fields of terms (sh:class schema:DefinedTerm, or one of
    sh:or), at any depth of their parts, but for the terms that the vocabularies of the model give."""
    graph = profile()
    paths = set()
    for field in graph.objects(None, SH.property):
        classes = set(graph.objects(field, SH["class"]))
        for alternatives in graph.objects(field, SH["or"]):
            for alternative in graph.items(alternatives):
                classes.update(graph.objects(alternative, SH["class"]))
        if SDO.DefinedTerm in classes:
            paths.add(graph.value(field, SH.path))
    vocabularies = []
    for spec in specs():
        if "vocabulary" in spec:
            vocabularies.append(spec["name"])
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.part_of.is_(None), Record.removed_at.is_(None))))
        given = set(db.scalars(select(Record.iri).where(Record.source.in_(vocabularies))))
    found = storage.graph(iris)
    terms = set()
    for path in paths:
        for value in found.objects(None, path):
            if isinstance(value, URIRef) and str(value) not in given:
                terms.add(str(value))
    return sorted(terms)


def download(spec: dict, parser) -> dict[str, bytes]:
    """The files of a source by name. A source with entries also has, by its key, the file of each entry
    of its index: the keys of the index (a JSON object), or those its parser reads from it (keys)."""
    contents = {}
    for name, url in files_of(spec).items():
        # A pinned vocabulary is read from the model's folder, where its SHA-256 is checked.
        contents[name] = (MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes() if "vocabulary" in spec else fetch(url)
    if "entries" in spec:
        index = contents[spec["name"]]
        for key in parser.keys(index) if hasattr(parser, "keys") else json.loads(index):
            # The keys come from upstream and are put in addresses, so only plain names are taken.
            if not ENTRY.fullmatch(key) or key == spec["name"]:
                continue
            try:
                contents[key] = fetch(spec["entries"].format(key=key))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {key} not fetched ({problem})")
    # A source of terms also has the answer for each term that the records are about, by its address.
    if "terms" in spec:
        for iri in linked_terms():
            try:
                contents[iri] = fetch(spec["terms"].format(iri=quote(iri, safe="")))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {iri} not fetched ({problem})")
    return contents


def import_source(spec: dict) -> None:
    config = settings()
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    contents = download(spec, parser)
    # A source of one file gives its parser the file; a source of several gives them by name.
    parsed = parser.parse(contents if "files" in spec or "entries" in spec or "terms" in spec else contents[spec["name"]])
    data, queries = convert(spec, parsed, config["base"])
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
    store(source, found)
    print(f"{spec['name']}: {len(found)} records")


def spec_of(name: str) -> dict:
    """A source as its file in sources/ describes it. A source whose rows are also those of other sources
    names them (uses), and has their rules too."""
    spec = yaml.safe_load((SOURCES_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    rules = {}
    for other in spec.get("uses", []):
        rules.update(spec_of(other)["rules"])
    spec["rules"] = {**rules, **spec.get("rules", {})}
    return spec


def specs() -> list[dict]:
    """The sources that are fetched (they have a url or files) or read (a vocabulary of the model)."""
    found = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = spec_of(path.stem)
        if "url" in spec or "files" in spec or "vocabulary" in spec:
            found.append(spec)
    return found


def check(source: str) -> None:
    """The records of a source, or those written on the platform, are checked against the model as the
    database holds them, with the records they link to; what does not fit is noted for the data quality
    page. The values are kept as they are."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.source == source, Record.removed_at.is_(None), Record.part_of.is_(None))))
    notes = checks.notes(storage.graph(iris))
    with database.session() as db, db.begin():
        db.execute(delete(Note).where(Note.source == source))
        for note in notes:
            db.add(Note(source=source, **note))
    print(f"{source}: {len(iris)} records checked, {len(notes)} notes")


def note_problem(spec: dict, problem: Exception) -> None:
    """A source whose import failed keeps its records; why is shown on the sources page."""
    with database.session() as db, db.begin():
        source = db.get(Source, spec["name"])
        if source is None:
            source = Source(name=spec["name"], url=" ".join(files_of(spec).values()), fetched_at="", sha256="", queries="")
            db.add(source)
        source.problem = str(problem)


def import_all() -> list[str]:
    """Every source is imported, and then the records of every source, and those written on the platform,
    are checked. The problems of the sources that could not be imported are given back; their records are
    kept."""
    problems = []
    every = []
    for terms in (False, True):
        for spec in specs():
            if ("terms" in spec) == terms:
                every.append(spec)
    for spec in every:
        try:
            import_source(spec)
        except (Refused, requests.RequestException, OSError, ValueError) as problem:
            note_problem(spec, problem)
            problems.append(f"{spec['name']}: {problem}")
    for spec in every:
        check(spec["name"])
    check(PLATFORM)
    return problems
