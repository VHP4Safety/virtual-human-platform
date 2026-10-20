"""Imports of the sources.

- Fetch each source, and read it with its parser as rows in the terms of the model.
- Replace the earlier records of the source with the rows. Keep the records written on the platform.
- Import the sources of records first, then the sources of terms, then the sources that enrich records.
- Last, check the records of each source against the model.

Run the weekly imports with `python -m linkeddata import`, and all imports with `python -m linkeddata launch`."""

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
from rdfsolve.client.sql_tables import merge
from rdfsolve.mining.wikibase_strategy import WikibaseScopeStrategy
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SDO, SH
from sqlalchemy import delete, func, insert, select

import database
from database import records
from database.tables import PLATFORM, Note, Record, Revision, Source, now
from linkeddata import checks, documents
from linkeddata.profile import MODEL_DIR, fields, profile_graph, profile_text, settings

SOURCES_DIR = Path(__file__).parent / "sources"
LAUNCH_DIR = Path(__file__).parent / "launch"
ITEM = "http://wikiba.se/ontology#Item"


def fetch(url: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "VHP4Safety platform build"}
    if accept:
        headers["Accept"] = accept
    response = requests.get(url, timeout=60, headers=headers)
    response.raise_for_status()
    return response.content


class Remote(io.RawIOBase):
    """A file on the web, read in parts (HTTP Range), so that a few files of a large zip are read without a download
    of the zip."""

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
    """Return the files of a zip on the web whose names end as given, by their ending."""
    found = {}
    with zipfile.ZipFile(io.BufferedReader(Remote(url), buffer_size=1 << 16)) as packed:
        for name in packed.namelist():
            for ending in endings:
                if name.endswith(ending) and ending not in found:
                    found[ending] = packed.read(name)
    return found


def convert(rows: list[dict], base: str) -> ox.Dataset:
    """Convert parsed rows to statements of the model. Read the rows with the JSON-LD context of the platform, and
    keep only the types and the properties of the fields of the profile."""
    document = {"@context": {**documents.context(settings()), "@base": base}, "@graph": rows}
    kept = {str(path) for path in profile_graph().objects(None, SH.path)} | {str(RDF.type)}
    found = ox.Dataset()
    for quad in ox.parse(json.dumps(document).encode(), format=ox.RdfFormat.JSON_LD):
        if quad.predicate.value in kept:
            found.add(quad)
    return found


def records_of(data: ox.Dataset, classes: list[str], source: str) -> list[tuple[list[dict], Graph]]:
    """Return the records of each class in converted data, with the rows of the records and their parts for the
    records table, and their statements. Keep values as given, and leave misfits to the checks."""
    graph = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    found = []
    for kind in classes:
        for subject in sorted(set(graph.subjects(RDF.type, URIRef(kind)))):
            if not isinstance(subject, URIRef):
                continue
            own = records.described(graph, str(subject))
            found.append((records.rows(own, str(subject), kind, source), own))
    return found


class Refused(Exception):
    """An import that is refused, such as an import that would remove most of the records of a source, or a second
    launch."""


def store(source: Source, found: list[tuple[list[dict], Graph]]) -> None:
    """Store the records of a source in place of its earlier records. Keep the records written on the platform. For
    records of another source, keep their values and add the new values that the profile allows, as in an
    enrichment. Refuse an import of no records, or of less than half of the earlier records."""
    with database.session() as db, db.begin():
        before = db.scalar(select(func.count()).select_from(Record).where(Record.source == source.name, Record.part_of.is_(None)))
        if not found or (before >= 10 and len(found) < before / 2):
            raise Refused(f"{len(found)} records given, {before} before; the records are kept")
        written = set(db.scalars(select(Record.iri).where(Record.source != source.name)))
        given = set(db.scalars(select(Record.iri).where(Record.source.not_in([source.name, PLATFORM]), Record.part_of.is_(None))))
        for iri in db.scalars(select(Record.iri).where(Record.source == source.name, Record.part_of.is_(None))):
            records.delete(db, iri)
        db.execute(delete(Record).where(Record.source == source.name))
        kept = {}
        for listed, statements in found:
            iri = listed[0]["iri"]
            if iri in given:
                merged = merge(records.read([iri]), statements, profile_text())
                if merged.added:
                    records.save(db, merged.graph, iri)
            elif iri not in written:
                for row in listed:
                    kept[row["iri"]] = row
                records.save(db, statements, iri)
        if kept:
            db.execute(insert(Record), list(kept.values()))
        db.merge(source)


def files_of(spec: dict) -> dict[str, str]:
    """Return the files of a source by name: its url, its files, or else the pinned vocabulary in its definition."""
    if "files" in spec:
        return dict(spec["files"])
    if "enriches" in spec:
        return {}
    if "url" in spec:
        return {spec["name"]: spec["url"]}
    return {spec["name"]: settings()["vocabularies"][spec["vocabulary"]]["url"]}


ENTRY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def linked_terms() -> list[str]:
    """Return the linked terms of the records and parts.

    The terms are the addresses in the term fields (sh:class schema:DefinedTerm, alone or in sh:or), by the shape of
    the class of each node. Leave out the records and terms of the vocabularies of the model."""
    vocabularies = []
    for spec in specs():
        if "vocabulary" in spec:
            vocabularies.append(spec["name"])
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.part_of.is_(None), Record.removed_at.is_(None), Record.source.not_in(vocabularies))))
        given = set(db.scalars(select(Record.iri).where(Record.source.in_(vocabularies))))
    found = records.graph(iris)
    terms = set()
    for node, of_class in found.subject_objects(RDF.type):
        for field in fields(str(of_class)):
            if str(SDO.DefinedTerm) not in field["classes"]:
                continue
            for value in found.objects(node, URIRef(field["iri"])):
                if isinstance(value, URIRef) and str(value) not in given:
                    terms.add(str(value))
    return sorted(terms)


def identified(spec: dict) -> list[tuple[str, str]]:
    """Return the records to enrich from a source, each with its key.

    Leave out records written on the platform. The key is the end of the sameAs address after the identifier of the
    source, if it matches the keys of the source. For a source matched by name (by: name), the key is the name of
    each record without such an address."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(
            Record.type.in_(records.within(settings()["kinds"][spec["enriches"]])), Record.part_of.is_(None), Record.removed_at.is_(None), Record.source != PLATFORM)))
    found = records.read(iris)
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


def wikibase_items(wikibase: dict, items: list[str]) -> bytes:
    """Return the given items of a Wikibase and the members of its class, read with rdfsolve.

    Each item is a JSON row of its fields, named by rdfsolve after the labels of the properties. The row has the
    address of the item, texts without their language, and other values with their datatype."""
    strategy = WikibaseScopeStrategy(items, classes=[wikibase["members"]], membership=wikibase["membership"],
                                     prefix_classes={wikibase["entity"] + "Q": ITEM})
    with SchemaMiner(wikibase["endpoint"], strategy=strategy, counts=False) as miner:
        client = Client(miner.mine(dataset_name=wikibase["endpoint"]), wikibase["endpoint"])
    members = client.select(f"SELECT ?item WHERE {{ ?item <{wikibase['membership']}> <{wikibase['members']}> }}", exhaustive=True)
    every = set(items)
    for row in members.rows:
        every.add(row["item"].value)
    rows = {}
    for found in client.fetch(sorted(every), kind=ITEM).table().to_dict("records"):
        row = {"item": str(found["Identifier"])}
        for field, values in found.items():
            if not isinstance(values, list):
                continue
            row[field] = []
            for value in values:
                if isinstance(value, URIRef):
                    row[field].append({"@id": str(value)})
                elif isinstance(value, Literal) and value.datatype is not None:
                    row[field].append({"@value": str(value), "@type": str(value.datatype)})
                else:
                    row[field].append(str(value))
        rows[row["item"]] = row
    return json.dumps([rows[item] for item in sorted(rows)], indent=1, sort_keys=True).encode()


def download(spec: dict, parser) -> dict[str, bytes]:
    """Return the files of a source by name.

    For a source with entries, also return the file of each entry, by its key in the index. The keys are the keys of
    the JSON object, or the keys read by the parser."""
    contents = {}
    for name, url in files_of(spec).items():
        # A pinned vocabulary is read from the model folder, unless an upstream address (url) is given for it.
        if "vocabulary" in spec and "url" not in spec:
            contents[name] = (MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()
        else:
            contents[name] = fetch(url)
    if "entries" in spec:
        index = contents[spec["name"]]
        for key in parser.keys(index) if hasattr(parser, "keys") else json.loads(index):
            # Upstream keys are used in addresses, so only plain names are accepted.
            if not ENTRY.fullmatch(key) or key == spec["name"]:
                continue
            try:
                contents[key] = fetch(spec["entries"].format(key=key))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {key} not fetched ({problem})")
    # For a source of packages, some files of the zip of each entry are read (members), by "<key>/<file>". The zips
    # are listed by the parser and must be on the site of the source.
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
    # For a source of documents, the files named by the parser are read (documents: name → address), each under one
    # of the addresses of the source (its documents, by name), such as the files of a repository at a pinned commit.
    if "documents" in spec:
        for name, url in parser.documents(contents, spec["documents"]).items():
            if not url.startswith(tuple(spec["documents"].values())):
                continue
            try:
                contents[name] = fetch(url)
            except requests.RequestException as problem:
                print(f"{spec['name']}: {name} not fetched ({problem})")
    # For an enriching source, one response is read for each identified record, by the address of the record.
    if "enriches" in spec:
        for iri, key in identified(spec):
            try:
                contents[iri] = fetch(spec["answer"].format(key=quote(key, safe="/")), spec.get("accept"))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {iri} not fetched ({problem})")
    # For a source in a Wikibase, the items named by the parser (items) and the members of a class are read with rdfsolve.
    if "wikibase" in spec:
        contents["items"] = wikibase_items(spec["wikibase"], parser.items(contents))
    # For a source of terms, one response is read for each linked term, by its address.
    if "terms" in spec:
        for iri in linked_terms():
            try:
                contents[iri] = fetch(spec["terms"].format(iri=quote(iri, safe="")))
            except requests.RequestException as problem:
                print(f"{spec['name']}: {iri} not fetched ({problem})")
    return contents


def import_source(spec: dict) -> None:
    config = settings()
    parser = importlib.import_module(spec["module"])
    contents = download(spec, parser)
    # One file is passed as is; several files are passed by name.
    parsed = parser.parse(contents if "files" in spec or "entries" in spec or "terms" in spec or "members" in spec or "documents" in spec else contents[spec["name"]])
    data = convert(parsed, config["base"])
    found = records_of(data, [of_class for kind in config["kinds"].values() for of_class in records.within(kind)], spec["name"])
    checksum = hashlib.sha256()
    for name in sorted(contents):
        checksum.update(contents[name])
    source = Source(
        name=spec["name"],
        url=" ".join(files_of(spec).values()),
        fetched_at=now(),
        sha256=checksum.hexdigest(),
    )
    store(source, found)
    print(f"{spec['name']}: {len(found)} records")


def enrich(spec: dict) -> None:
    """Merge the values of a source into the records of other sources, as the profile allows. Keep the value of a
    single-valued field, and note a different value. Store the first enrichment of a record as its first revision,
    so that the origin of its values is shown."""
    parser = importlib.import_module(spec["module"])
    contents = download(spec, parser)
    data = convert(parser.parse(contents), settings()["base"])
    given = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    notes = []
    with database.session() as db, db.begin():
        for iri in sorted(contents):
            record = db.get(Record, iri)
            current = records.read([iri])
            merged = merge(current, records.described(given, iri), profile_text())
            for subject, predicate, kept, offered in merged.conflicts:
                notes.append(Note(source=spec["name"], iri=subject, field=predicate, value=offered, component="enrichment",
                                  reason=f"{spec['title']} gives {offered}; the record keeps {kept}."))
            if not merged.added:
                continue
            records.save(db, merged.graph, iri)
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
        db.merge(Source(name=spec["name"], url=spec["answer"], fetched_at=now(), sha256=checksum.hexdigest()))
    print(f"{spec['name']}: {len(contents)} records asked for, {len(notes)} conflicting values kept")


def specs() -> list[dict]:
    """Return the sources by name: fetched (url, files), read from a model vocabulary, or enriching records
    (enriches). Read a source in sources/ each week. Read a source in launch/, or a pinned vocabulary without url,
    once, at launch."""
    found = []
    for path in sorted([*SOURCES_DIR.glob("*.yaml"), *LAUNCH_DIR.glob("*.yaml")], key=lambda path: path.name):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "url" in spec or "files" in spec or "vocabulary" in spec or "enriches" in spec:
            spec["module"] = ("linkeddata.launch." if path.parent == LAUNCH_DIR else "linkeddata.parsers.") + spec["parser"]
            spec["weekly"] = path.parent == SOURCES_DIR and ("url" in spec or "vocabulary" not in spec)
            found.append(spec)
    return found


def drifted(spec: dict) -> list[dict]:
    """Return the terms of the profile that changed upstream.

    This applies to a source of a pinned vocabulary with an upstream address. A term changed if it is no longer in the
    upstream file, or if it has another label there."""
    parser = importlib.import_module(spec["module"])
    pinned = {}
    for row in parser.parse((MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()):
        if row.get("@type") == "DefinedTerm":
            pinned[row["@id"]] = row.get("name") or ""
    used = set()
    for node in profile_graph().all_nodes():
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


def check(source: str, spec: dict | None = None) -> None:
    """Check the records of a source, or of the platform, against the model as stored, with their linked records.
    Keep the misfits and note them for the data quality page. For a source of a pinned vocabulary with an upstream
    address, also note the terms of the profile that were dropped or renamed."""
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.source == source, Record.removed_at.is_(None), Record.part_of.is_(None))))
    notes = checks.notes(records.graph(iris))
    if spec is not None and "url" in spec and "vocabulary" in spec:
        notes += drifted(spec)
    with database.session() as db, db.begin():
        db.execute(delete(Note).where(Note.source == source))
        for note in notes:
            db.add(Note(source=source, **note))
    print(f"{source}: {len(iris)} records checked, {len(notes)} notes")


def note_problem(spec: dict, problem: Exception) -> None:
    """Store the problem of a failed import with its source, and keep the records of the source."""
    with database.session() as db, db.begin():
        source = db.get(Source, spec["name"])
        if source is None:
            source = Source(name=spec["name"], url=" ".join(files_of(spec).values()), fetched_at="", sha256="")
            db.add(source)
        source.problem = str(problem)


def import_all(once: bool = False) -> list[str]:
    """Import the weekly sources. At launch (once), import the sources that are read once first, and refuse a
    database with imported records. Then check each source. Return the problems of failed sources, and keep their
    records."""
    problems = []
    every = []
    if once:
        with database.session() as db:
            if db.scalar(select(Record.iri).where(Record.source != PLATFORM).limit(1)):
                raise Refused("The database holds imported records. Launch is run once, on a database without them.")
        # Records of both a launch source and a weekly source belong to the launch source, so they are kept by weekly imports.
        for spec in specs():
            if not spec["weekly"]:
                every.append(spec)
    for step in ("records", "terms", "enriches"):
        for spec in specs():
            if spec["weekly"] and ("terms" in spec) == (step == "terms") and ("enriches" in spec) == (step == "enriches"):
                every.append(spec)
    for spec in every:
        try:
            if "enriches" in spec:
                enrich(spec)
            else:
                import_source(spec)
        # A KeyError or TypeError of a parser means a changed format of an upstream file.
        except (Refused, requests.RequestException, OSError, ValueError, KeyError, TypeError) as problem:
            note_problem(spec, problem)
            problems.append(f"{spec['name']}: {problem}")
    # Records are checked after the enrichments. An enriching source has no records, and its notes are the
    # conflicting values.
    for spec in specs():
        if "enriches" not in spec:
            check(spec["name"], spec)
    check(PLATFORM)
    return problems
