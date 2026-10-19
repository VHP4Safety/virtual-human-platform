"""Imports of the sources. Each source is fetched, cleaned by its parser, converted to the model with
rdfsolve, and stored in place of its earlier records; records written on the platform are kept. Sources of
terms (terms) run next, for the terms the records are about, and sources that enrich records (enriches)
last. Then each source's records are checked against the model. `python -m linkeddata import` runs every
import, such as nightly."""

import hashlib
import importlib
import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import quote, urlsplit

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
from database.tables import PLATFORM, Note, Record, Revision, Source, now
from linkeddata import catalogue, checks, documents, patches, storage
from linkeddata.model import MODEL_DIR, RELEASE, profile, settings

SOURCES_DIR = Path(__file__).parent / "sources"
TARGET = f"VHP4Safety model {RELEASE}"


def fetch(url: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "VHP4Safety platform build"}
    if accept:
        headers["Accept"] = accept
    response = requests.get(url, timeout=60, headers=headers)
    response.raise_for_status()
    return response.content


class Remote(io.RawIOBase):
    """A file on the web read in parts (HTTP Range), so that a few files of a large zip are read without
    downloading it."""

    def __init__(self, url: str):
        self.url = url
        self.at = 0
        self.size = int(requests.head(url, allow_redirects=True, timeout=60, headers={"User-Agent": "VHP4Safety platform build"}).headers["Content-Length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.at

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.at = offset
        elif whence == 1:
            self.at += offset
        else:
            self.at = self.size + offset
        return self.at

    def readinto(self, buffer) -> int:
        end = min(self.at + len(buffer), self.size) - 1
        if end < self.at:
            return 0
        response = requests.get(self.url, timeout=60, headers={"Range": f"bytes={self.at}-{end}", "User-Agent": "VHP4Safety platform build"})
        response.raise_for_status()
        buffer[:len(response.content)] = response.content
        self.at += len(response.content)
        return len(response.content)


def members(url: str, endings: list[str]) -> dict[str, bytes]:
    """The files of a zip on the web whose names end as given, by their ending."""
    found = {}
    with zipfile.ZipFile(io.BufferedReader(Remote(url), buffer_size=1 << 16)) as packed:
        for name in packed.namelist():
            for ending in endings:
                if name.endswith(ending) and ending not in found:
                    found[ending] = packed.read(name)
    return found


def lift(rows: list[dict], vocabulary: str, base: str) -> ox.Dataset:
    """Parsed rows as RDF, until rdfsolve reads JSON with a context: fields become properties of the
    source's vocabulary, "@id" is a row's address and "@type" its kind."""
    document = {"@context": {"@vocab": vocabulary, "@base": base}, "@graph": rows}
    return ox.Dataset(ox.parse(json.dumps(document).encode(), format=ox.RdfFormat.JSON_LD))


def convert(spec: dict, data: list[dict], base: str) -> tuple[ox.Dataset, list[str]]:
    """One source's rows in the model, and the CONSTRUCT queries that made them."""
    vocabulary = base + "sources/" + spec["name"] + "#"
    rows = lift(data, vocabulary, base)
    with SchemaMiner.from_graph(rows, delay=0) as miner:
        source = Client(miner.mine(dataset_name=spec["name"]), rows)
    statements = ox.Dataset()
    queries = []
    for kind, arguments in spec["rules"].items():
        rules = []
        for argument in arguments:
            # Addresses are given, so a rule is kept when the data lacks the kind or field.
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
    """The records of each class in converted data: their rows and their parts' for the records table, and
    their statements. Values are kept as given; misfits are noted by the checks."""
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
    """An import that would remove most of a source's records, usually after an upstream fault."""


def store(source: Source, found: list[tuple[list[dict], Graph]]) -> None:
    """A source's records replace its earlier ones; records written on the platform are kept, and records
    given by another source keep their values and take the new ones the profile allows (as an enrichment
    does). An import of no records, or of less than half the earlier ones, is refused."""
    with database.session() as db, db.begin():
        before = db.scalar(select(func.count()).select_from(Record).where(Record.source == source.name, Record.part_of.is_(None)))
        if not found or (before >= 10 and len(found) < before / 2):
            raise Refused(f"{len(found)} records given, {before} before; the records are kept")
        written = set(db.scalars(select(Record.iri).where(Record.source != source.name)))
        given = set(db.scalars(select(Record.iri).where(Record.source.not_in([source.name, PLATFORM]), Record.part_of.is_(None))))
        for iri in db.scalars(select(Record.iri).where(Record.source == source.name, Record.part_of.is_(None))):
            storage.delete(db, iri)
        db.execute(delete(Record).where(Record.source == source.name))
        kept = {}
        for listed, statements in found:
            iri = listed[0]["iri"]
            if iri in given:
                merged = patches.merge(storage.read([iri]), statements, storage.profile())
                if merged.added:
                    storage.save(db, merged.graph, iri)
            elif iri not in written:
                for row in listed:
                    kept[row["iri"]] = row
                storage.save(db, statements, iri)
        if kept:
            db.execute(insert(Record), list(kept.values()))
        db.merge(source)


def files_of(spec: dict) -> dict[str, str]:
    """A source's files by name: its url, its files, or else the pinned vocabulary it names."""
    if "files" in spec:
        return dict(spec["files"])
    if "enriches" in spec:
        return {}
    if "url" in spec:
        return {spec["name"]: spec["url"]}
    return {spec["name"]: settings()["vocabularies"][spec["vocabulary"]]["url"]}


ENTRY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def linked_terms() -> list[str]:
    """The addresses in term fields (sh:class schema:DefinedTerm, alone or in sh:or) at any depth, except
    terms of the model's vocabularies."""
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


def identified(spec: dict) -> list[tuple[str, str]]:
    """The records of the kind a source enriches, except those written on the platform, each with its key:
    the end of its sameAs address after the source's identifier, when it matches the source's keys; or, for a
    source that finds records by name (by: name), the name of each record without such an address."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(
            Record.type.in_(catalogue.within(settings()["kinds"][spec["enriches"]])), Record.part_of.is_(None), Record.removed_at.is_(None), Record.source != PLATFORM)))
    found = storage.read(iris)
    keys = []
    for iri in iris:
        addresses = []
        for value in sorted(found.objects(URIRef(iri), SDO.sameAs)):
            if str(value).startswith(spec["identifier"]):
                addresses.append(str(value).removeprefix(spec["identifier"]))
        if spec.get("by") == "name":
            name = found.value(URIRef(iri), SDO.name)
            if not addresses and name is not None:
                keys.append((iri, str(name).strip()))
            continue
        for key in addresses:
            if re.fullmatch(spec["keys"], key):
                keys.append((iri, key))
                break
    return keys


def download(spec: dict, parser) -> dict[str, bytes]:
    """A source's files by name; with entries, also each entry's file by its key in the index (the JSON
    object's keys, or those its parser reads)."""
    contents = {}
    for name, url in files_of(spec).items():
        # A pinned vocabulary is read from the model folder, unless the source follows it upstream (url).
        if "vocabulary" in spec and "url" not in spec:
            contents[name] = (MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()
        else:
            contents[name] = fetch(url)
    if "entries" in spec:
        index = contents[spec["name"]]
        for key in parser.keys(index) if hasattr(parser, "keys") else json.loads(index):
            # Upstream keys go into addresses, so only plain names are taken.
            if not ENTRY.fullmatch(key) or key == spec["name"]:
                continue
            try:
                contents[key] = fetch(spec["entries"].format(key=key))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {key} not fetched ({problem})")
    # A source of packages reads some files of each entry's zip (members), by "<key>/<file>"; the parser gives
    # the zips, which must be on the source's own site.
    if "members" in spec:
        site = "https://" + urlsplit(spec["url"]).netloc + "/"
        for key, url in parser.packages(contents[spec["name"]]).items():
            if not ENTRY.fullmatch(key) or not url.startswith(site):
                continue
            try:
                for ending, content in members(url, spec["members"]).items():
                    contents[f"{key}/{ending}"] = content
            except (requests.RequestException, zipfile.BadZipFile) as problem:
                print(f"{spec['name']}: {key} not read ({problem})")
    # An enriching source has one answer per identified record, by the record's address.
    if "enriches" in spec:
        for iri, key in identified(spec):
            try:
                contents[iri] = fetch(spec["answer"].format(key=quote(key, safe="/")), spec.get("accept"))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {iri} not fetched ({problem})")
    # A source of terms has one answer per linked term, by its address.
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
    # One file is given as is; several are given by name.
    parsed = parser.parse(contents if "files" in spec or "entries" in spec or "terms" in spec or "members" in spec else contents[spec["name"]])
    data, queries = convert(spec, parsed, config["base"])
    found = records_of(data, [of_class for kind in config["kinds"].values() for of_class in catalogue.within(kind)], spec["name"])
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


def enrich(spec: dict) -> None:
    """A source's values are merged into other sources' records as the profile allows: a single-valued
    field keeps its value, and a different one is noted. A record's first enrichment is its first revision,
    which shows where its values came from."""
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    contents = download(spec, parser)
    data, queries = convert(spec, parser.parse(contents), settings()["base"])
    given = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    notes = []
    with database.session() as db, db.begin():
        for iri in sorted(contents):
            record = db.get(Record, iri)
            current = storage.read([iri])
            merged = patches.merge(current, storage.described(given, iri), storage.profile())
            for subject, predicate, kept, offered in merged.conflicts:
                notes.append(Note(source=spec["name"], iri=subject, field=predicate, value=offered, component="enrichment",
                                  reason=f"{spec['title']} gives {offered}; the record keeps {kept}."))
            if not merged.added:
                continue
            storage.save(db, merged.graph, iri)
            if merged.graph.value(URIRef(iri), SDO.name) is not None:
                record.name = str(merged.graph.value(URIRef(iri), SDO.name))
            record.updated_at = now()
            if db.scalar(select(func.count()).select_from(Revision).where(Revision.record_iri == iri)) == 0:
                db.add(Revision(record_iri=iri, action="Enriched", name=spec["title"], orcid="",
                                previous=json.dumps(documents.document(current, iri), indent=2),
                                document=json.dumps(documents.document(merged.graph, iri), indent=2)))
        db.execute(delete(Note).where(Note.source == spec["name"]))
        db.add_all(notes)
        checksum = hashlib.sha256()
        for name in sorted(contents):
            checksum.update(contents[name])
        db.merge(Source(name=spec["name"], url=spec["answer"], fetched_at=now(), sha256=checksum.hexdigest(), queries="\n\n".join(queries)))
    print(f"{spec['name']}: {len(contents)} records asked for, {len(notes)} conflicting values kept")


def spec_of(name: str) -> dict:
    """A source as its file in sources/ describes it, with the rules of the sources it uses (uses)."""
    spec = yaml.safe_load((SOURCES_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    rules = {}
    for other in spec.get("uses", []):
        rules.update(spec_of(other)["rules"])
    spec["rules"] = {**rules, **spec.get("rules", {})}
    return spec


def specs() -> list[dict]:
    """The sources that are fetched (url, files), read (a model vocabulary) or enrich records (enriches)."""
    found = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = spec_of(path.stem)
        if "url" in spec or "files" in spec or "vocabulary" in spec or "enriches" in spec:
            found.append(spec)
    return found


def drifted(spec: dict) -> list[dict]:
    """For a source that follows a pinned vocabulary upstream: the profile's terms that it no longer gives,
    or gives under another label."""
    parser = importlib.import_module("linkeddata.parsers." + spec["parser"])
    pinned = {}
    for row in parser.parse((MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()):
        if row.get("@type") == "Term":
            pinned[row["@id"]] = row.get("label") or ""
    used = set()
    for node in profile().all_nodes():
        if str(node) in pinned:
            used.add(str(node))
    with database.session() as db:
        given = dict(db.execute(select(Record.iri, Record.name).where(Record.source == spec["name"])).all())
    found = []
    for iri in sorted(used):
        if iri not in given:
            reason = f"{pinned[iri]}: used by the profile, no longer in {spec['title']}."
        elif (given[iri] or "") != pinned[iri]:
            reason = f"{pinned[iri]}: used by the profile, named {given[iri]} in {spec['title']}."
        else:
            continue
        found.append({"iri": iri, "field": "", "value": iri, "reason": reason, "component": "model"})
    return found


def check(source: str) -> None:
    """A source's records, or the platform's, are checked against the model as stored, with their linked
    records; misfits are kept and noted for the data quality page. A source that follows a pinned vocabulary
    upstream also notes the profile's terms it dropped or renamed."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.source == source, Record.removed_at.is_(None), Record.part_of.is_(None))))
    notes = checks.notes(storage.graph(iris))
    if source != PLATFORM:
        spec = spec_of(source)
        if "url" in spec and "vocabulary" in spec:
            notes += drifted(spec)
    with database.session() as db, db.begin():
        db.execute(delete(Note).where(Note.source == source))
        for note in notes:
            db.add(Note(source=source, **note))
    print(f"{source}: {len(iris)} records checked, {len(notes)} notes")


def note_problem(spec: dict, problem: Exception) -> None:
    """A failed import is noted on the sources page; the source's records are kept."""
    with database.session() as db, db.begin():
        source = db.get(Source, spec["name"])
        if source is None:
            source = Source(name=spec["name"], url=" ".join(files_of(spec).values()), fetched_at="", sha256="", queries="")
            db.add(source)
        source.problem = str(problem)


def import_all() -> list[str]:
    """Every source is imported, then every source's records and the platform's are checked. The problems
    of failed sources are given back; their records are kept."""
    problems = []
    every = []
    for step in ("records", "terms", "enriches"):
        for spec in specs():
            if ("terms" in spec) == (step == "terms") and ("enriches" in spec) == (step == "enriches"):
                every.append(spec)
    for spec in every:
        try:
            if "enriches" in spec:
                enrich(spec)
            else:
                import_source(spec)
        except (Refused, requests.RequestException, OSError, ValueError) as problem:
            note_problem(spec, problem)
            problems.append(f"{spec['name']}: {problem}")
    # Records are checked after the enrichments; an enriching source has no records, and its notes are the
    # conflicting values.
    for spec in every:
        if "enriches" not in spec:
            check(spec["name"])
    check(PLATFORM)
    return problems
