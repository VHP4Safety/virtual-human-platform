"""Imports of the sources into the database."""

import hashlib
import importlib
import io
import json
import re
import unicodedata
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
from rdfsolve.sparql_helper import EndpointError
from rdflib import RDF, RDFS, Graph, Literal, URIRef
from rdflib.namespace import SDO
from sqlalchemy import delete, func, insert, select

import database
from database import records
from database.tables import PLATFORM, Note, Record, Revision, Source, now
from linkeddata import checks, crates, documents
from linkeddata.profile import MODEL_DIR, fields, hierarchy, known, known_terms, settings, shape_fields, shapes, shapes_text

SOURCES_DIR = Path(__file__).parent / "sources"
ROOT = Path(__file__).parent.parent
# The registries with addresses that identify a person or an organisation, in sameAs.
REGISTRIES = ("https://orcid.org/", "https://ror.org/")
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
    """File on the web, read in parts with HTTP Range requests."""

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
    """Return the files of the zip at url with names that end in endings."""
    found = {}
    with zipfile.ZipFile(io.BufferedReader(Remote(url), buffer_size=1 << 16)) as packed:
        for name in packed.namelist():
            for ending in endings:
                if name.endswith(ending) and ending not in found:
                    found[ending] = packed.read(name)
    return found


def convert(rows: list[dict], base: str) -> ox.Dataset:
    """Return the statements of the parsed rows in the terms of the vocabularies and the profiles."""
    document = {"@context": {**documents.context(settings()), "@base": base}, "@graph": rows}
    # The cells of an RDF list (rdf:first, rdf:rest) are kept for the list fields.
    kept = known_terms() | {str(RDF.type), str(RDF.first), str(RDF.rest)}
    found = ox.Dataset()
    for quad in ox.parse(json.dumps(document).encode(), format=ox.RdfFormat.JSON_LD):
        if quad.predicate.value in kept:
            found.add(quad)
    return found


def records_of(data: ox.Dataset, classes: list[str], source: str) -> list[tuple[list[dict], Graph]]:
    """Return the records of classes in data, with their rows and statements."""
    graph = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    found = []
    for kind in classes:
        for subject in sorted(set(graph.subjects(RDF.type, URIRef(kind)))):
            if not isinstance(subject, URIRef):
                continue
            own = records.described(graph, str(subject))
            found.append((records.rows(own, str(subject), kind, source), own))
    return found


def words(name) -> set[str]:
    """Return the words of four or more letters of name, in lower case."""
    plain = "".join(letter for letter in unicodedata.normalize("NFKD", str(name or "")) if not unicodedata.combining(letter))
    return set(re.findall(r"\w{4,}", plain.casefold()))


def forwards() -> dict[str, str]:
    """Return the new address of each moved or merged address."""
    with database.session() as db:
        moved = dict(db.execute(select(Record.iri, Record.moved_to).where(Record.moved_to.is_not(None))).all())
    found = {}
    for iri, target in moved.items():
        seen = {iri}
        while target in moved and target not in seen:
            seen.add(target)
            target = moved[target]
        found[iri] = target
    return found


def one_per_identifier(found: list[tuple[list[dict], Graph]]) -> list[tuple[list[dict], Graph]]:
    """Return found with the records that have the same registry address as one record."""
    names = {listed[0]["iri"]: listed[0]["name"] for listed, _ in found}
    first, renamed = {}, forwards()
    for listed, statements in found:
        iri, of_class = listed[0]["iri"], listed[0]["type"]
        if iri in renamed:
            continue
        given = sorted(str(value) for value in statements.objects(URIRef(iri), SDO.sameAs) if str(value).startswith(REGISTRIES))
        if not given:
            continue
        if (of_class, given[0]) not in first:
            with database.engine().connect() as connection:
                stored = list(connection.scalars(records.nodes_with(of_class, str(SDO.sameAs), given[:1])))
            kept = sorted(record.iri for record in records.kept(stored) if record.part_of is None)
            names.update(records.names(kept))
            first[(of_class, given[0])] = (kept or [iri])[0]
        target = first[(of_class, given[0])]
        if target == iri:
            continue
        if words(names.get(iri)) & words(names.get(target)):
            renamed[iri] = target
        else:
            print(f"{iri} and {target} have the same address {given[0]} but other names; they are kept apart")

    def moved(node):
        return URIRef(renamed[str(node)]) if isinstance(node, URIRef) and str(node) in renamed else node

    joined = {}
    for listed, statements in found:
        iri = renamed.get(listed[0]["iri"], listed[0]["iri"])
        own = Graph()
        for subject, predicate, value in statements:
            own.add((moved(subject), predicate, moved(value)))
        if iri in joined:
            joined[iri] = (joined[iri][0], merge(joined[iri][1], own, shapes_text()).graph)
        else:
            joined[iri] = ([{**row, "iri": iri} if row["iri"] == listed[0]["iri"] else row for row in listed], own)
    return list(joined.values())


def one_record_each(order: list[str]) -> None:
    """Merge the stored records of one kind that have the same registry address."""
    rank = {PLATFORM: -1}
    for number, name in enumerate(order):
        rank[name] = number
    groups = {}
    for kind in settings()["kinds"].values():
        for of_class in records.within(kind):
            for iri, value in records.values(of_class, str(SDO.sameAs)):
                if str(value).startswith(REGISTRIES):
                    groups.setdefault((kind, str(value)), set()).add(iri)
    for (_, value), iris in sorted(groups.items()):
        listed = sorted((record for record in records.kept(sorted(iris)) if record.part_of is None),
                        key=lambda record: (rank.get(record.source, len(rank)), record.iri))
        for other in listed[1:]:
            if words(other.name) & words(listed[0].name):
                merge_into(other, listed[0], f"same address {value}")
            else:
                print(f"{other.iri} and {listed[0].iri} have the same address {value} but other names; they are kept apart")


def drafts_found() -> None:
    """Merge each draft term into the term of its vocabulary, if the vocabulary has it."""
    term = str(SDO.DefinedTerm)

    def plain(name) -> str:
        return re.sub(r"\s*\([^)]*\)$", "", str(name or "")).casefold()

    drafts = sorted({iri for iri, value in records.values(term, str(SDO.creativeWorkStatus)) if str(value) == "Draft"})
    if not drafts:
        return
    with database.session() as db:
        terms = list(db.scalars(select(Record).where(Record.type == term, Record.removed_at.is_(None), Record.moved_to.is_(None))))
    by_name = {}
    for found in terms:
        if found.iri not in drafts:
            by_name.setdefault(plain(found.name), []).append(found)
    for draft in records.kept(drafts):
        statements = records.graph([draft.iri])
        vocabulary = statements.value(URIRef(draft.iri), SDO.inDefinedTermSet)
        given = {str(value) for value in statements.objects(URIRef(draft.iri), SDO.sameAs)}
        candidates = [found for found in terms if found.iri in given] + by_name.get(plain(draft.name), [])
        for candidate in candidates:
            if records.graph([candidate.iri]).value(URIRef(candidate.iri), SDO.inDefinedTermSet) == vocabulary:
                merge_into(draft, candidate, f"the vocabulary has the term at {candidate.iri}", without={SDO.creativeWorkStatus})
                break


def merge_into(other: Record, kept: Record, reason: str, without: set = frozenset()) -> None:
    """Merge the record other into the record kept, without the fields without."""
    target = URIRef(kept.iri)

    def moved(node):
        return target if node == URIRef(other.iri) else node

    # The parts of the other record are numbered again under the kept record.
    statements = Graph()
    for subject, predicate, given in records.blank_parts(records.read([other.iri]), other.iri):
        if predicate not in without:
            statements.add((moved(subject), predicate, moved(given)))
    joined = merge(records.read([kept.iri]), records.described(statements, kept.iri), shapes_text()).graph
    if other.name and other.name != kept.name and str(SDO.alternateName) in {field["iri"] for field in fields(kept.type)}:
        joined.add((target, SDO.alternateName, Literal(other.name)))
    joined.add((target, SDO.sameAs, URIRef(other.iri)))
    relinked = {}
    for linked in records.kept(sorted(records.linking(other.iri) - {kept.iri})):
        if linked.part_of is None:
            relinked[linked.iri] = Graph()
            for subject, predicate, given in records.read([linked.iri]):
                relinked[linked.iri].add((subject, predicate, moved(given)))
    previous = documents.document_of(other.iri)
    with database.session() as db, db.begin():
        records.save(db, joined, kept.iri)
        records.delete(db, other.iri)
        for iri, found in relinked.items():
            records.save(db, found, iri)
            db.get(Record, iri).updated_at = now()
        db.get(Record, kept.iri).updated_at = now()
        row = db.get(Record, other.iri)
        row.removed_at, row.moved_to, row.source, row.updated_at = now(), kept.iri, PLATFORM, now()
        for earlier in db.scalars(select(Record).where(Record.moved_to == other.iri)):
            earlier.moved_to = kept.iri
        db.add(Revision(record_iri=other.iri, action="Merged", previous=previous, name=f"Import: {reason}", orcid=""))
    print(f"{other.iri}: merged into {kept.iri} ({reason})")


class Refused(Exception):
    """Import that is refused."""


def store(source: Source, found: list[tuple[list[dict], Graph]]) -> None:
    """Store the records in found in place of the earlier records of source."""
    with database.session() as db, db.begin():
        before = db.scalar(select(func.count()).select_from(Record).where(Record.source == source.name, Record.part_of.is_(None)))
        if not found or (before >= 10 and len(found) < before / 2):
            raise Refused(f"{len(found)} records given, {before} before; the records are kept")
        written = set(db.scalars(select(Record.iri).where(Record.source != source.name)))
        given = set(db.scalars(select(Record.iri).where(Record.source.not_in([source.name, PLATFORM]), Record.part_of.is_(None))))
        earlier = list(db.scalars(select(Record.iri).where(Record.source == source.name, Record.part_of.is_(None))))
        # A stored part that is imported again with the same values is given the same address.
        before = records.read(earlier)
        for iri in earlier:
            records.delete(db, iri)
        db.execute(delete(Record).where(Record.source == source.name))
        kept = {}
        for listed, statements in found:
            iri = listed[0]["iri"]
            if iri in given:
                merged = merge(records.read([iri]), statements, shapes_text())
                if merged.added:
                    records.save(db, merged.graph, iri)
            elif iri not in written:
                for row in listed:
                    kept[row["iri"]] = row
                records.save(db, statements, iri, before)
        if kept:
            db.execute(insert(Record), list(kept.values()))
        db.merge(source)


def files_of(spec: dict) -> dict[str, str]:
    """Return the files of the source spec, by name."""
    if "files" in spec:
        return dict(spec["files"])
    if "enriches" in spec:
        return {}
    if "url" in spec:
        return {spec["name"]: spec["url"]}
    return {spec["name"]: settings()["vocabularies"][spec["vocabulary"]]["url"]}


ENTRY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def linked_terms() -> list[str]:
    """Return the addresses of the terms linked from records and parts."""
    vocabularies = []
    for spec in specs():
        if "vocabulary" in spec:
            vocabularies.append(spec["name"])
    with database.session() as db:
        iris = list(db.scalars(select(Record.iri).where(Record.part_of.is_(None), Record.removed_at.is_(None), Record.source.not_in(vocabularies))))
        given = set(db.scalars(select(Record.iri).where(Record.source.in_(vocabularies))))
    found = records.graph(iris)
    terms = set()
    for iri in iris:
        terms_of(found, URIRef(iri), fields(str(found.value(URIRef(iri), RDF.type) or "")), terms)
    return sorted(terms - given)


def terms_of(found: Graph, node, given: list[dict], terms: set[str]) -> None:
    """Add to terms the addresses of the terms that node links to, by the fields given, and those of its parts."""
    by_path = {field["iri"]: field for field in given}
    for predicate, value in found.predicate_objects(node):
        field = by_path.get(str(predicate))
        if records.is_part(found, value):
            shape = field["parts"].get(str(found.value(value, RDF.type)), field["node"]) if field else ""
            terms_of(found, value, shape_fields(shape) if shape else fields(records.class_of(found, value)), terms)
        # A record or a part of the platform, such as a method as a measurement technique, is not a term.
        elif isinstance(value, URIRef) and not str(value).startswith(settings()["base"]) and termed(field, str(predicate)):
            terms.add(str(value))


def termed(field: dict | None, path: str) -> bool:
    """Return True if the values of a field, or of a property without a field, are terms: the field takes terms, or the
    property ranges over terms in the vocabularies. An additional type is a class of another vocabulary, such as a MeSH term."""
    if path == str(SDO.additionalType):
        return True
    if field is not None:
        return str(SDO.DefinedTerm) in field["classes"]
    above = {str(SDO.DefinedTerm), *map(str, hierarchy().transitive_objects(SDO.DefinedTerm, RDFS.subClassOf))}
    return bool(above & set(known().objects(path, str(SDO.rangeIncludes))))


def identified(spec: dict) -> list[tuple[str, str]]:
    """Return the records to enrich from the source spec, each with its key."""
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
    """Return the items of a Wikibase and the members of its class, as JSON."""
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
    """Return the files of the source spec, by name."""
    if hasattr(parser, "fetched"):
        return parser.fetched(spec)
    contents = {}
    for name, url in files_of(spec).items():
        # A pinned vocabulary is read from the model folder, unless an upstream address (url) is given for it.
        if "vocabulary" in spec and "url" not in spec:
            contents[name] = (MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()
        # A file of the repository is given by its path, such as linkeddata/launch/site/impact.html.
        elif not url.startswith(("https://", "http://")):
            contents[name] = (ROOT / url).read_bytes()
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
    # For a source of packages, the members of the zip of each entry are read, by "<key>/<file>". The zips are
    # listed by the parser and must be on the site of the source.
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
    # For a source of documents, the files named by the parser are read. Each file must be under one of the
    # addresses of the documents of the source.
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
    # One file is passed as it is. Several files are passed by name.
    parsed = parser.parse(contents if "files" in spec or "entries" in spec or "terms" in spec or "members" in spec or "documents" in spec or len(contents) > 1 else contents[spec["name"]])
    data = convert(parsed, config["base"])
    found = one_per_identifier(records_of(data, [of_class for kind in config["kinds"].values() for of_class in records.within(kind)], spec["name"]))
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
    if "members" in spec:
        keep(contents)
    print(f"{spec['name']}: {len(found)} records")


def keep(contents: dict[str, bytes]) -> None:
    """Store a copy of each RO-Crate metadata file in contents."""
    folder = crates.kept()
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in contents.items():
        key, _, member = name.partition("/")
        if member == "ro-crate-metadata.json":
            (folder / f"{key}.json").write_bytes(content)


def enrich(spec: dict) -> None:
    """Merge the values of the source spec into the records of other sources."""
    parser = importlib.import_module(spec["module"])
    contents = download(spec, parser)
    data = convert(parser.parse(contents), settings()["base"])
    given = Graph().parse(data=ox.serialize(data, format=ox.RdfFormat.N_QUADS), format="nt")
    notes = []
    with database.session() as db, db.begin():
        for iri in sorted(contents):
            record = db.get(Record, iri)
            current = records.read([iri])
            merged = merge(current, records.described(given, iri), shapes_text())
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
    """Return the sources, from sources/ and launch/."""
    found = []
    for path in sorted([*SOURCES_DIR.glob("*.yaml"), *LAUNCH_DIR.glob("*.yaml")], key=lambda path: path.name):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "url" in spec or "files" in spec or "vocabulary" in spec or "enriches" in spec:
            spec["module"] = ("linkeddata.launch." if path.parent == LAUNCH_DIR else "linkeddata.parsers.") + spec["parser"]
            spec["weekly"] = path.parent == SOURCES_DIR and ("url" in spec or "vocabulary" not in spec)
            found.append(spec)
    return found


def drifted(spec: dict) -> list[dict]:
    """Return the terms of the profile that changed upstream in the source spec."""
    parser = importlib.import_module(spec["module"])
    pinned = {}
    for row in parser.parse((MODEL_DIR / "vocabularies" / spec["vocabulary"]).read_bytes()):
        if row.get("@type") == "DefinedTerm":
            pinned[row["@id"]] = row.get("name") or ""
    used = set()
    for node in shapes().all_nodes():
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
    """Check the records of source against the model, and store the notes."""
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
    """Store the problem of the failed import of spec."""
    with database.session() as db, db.begin():
        source = db.get(Source, spec["name"])
        if source is None:
            source = Source(name=spec["name"], url=" ".join(files_of(spec).values()), fetched_at="", sha256="")
            db.add(source)
        source.problem = str(problem)


def import_all(once: bool = False) -> list[str]:
    """Import the sources, and return the problems of the failed sources."""
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
        except (Refused, requests.RequestException, EndpointError, OSError, ValueError, KeyError, TypeError) as problem:
            note_problem(spec, problem)
            problems.append(f"{spec['name']}: {problem}")
    one_record_each([spec["name"] for spec in every])
    drafts_found()
    # Records are checked after the enrichments. An enriching source has no records, and its notes are the
    # conflicting values.
    for spec in specs():
        if "enriches" not in spec:
            check(spec["name"], spec)
    check(PLATFORM)
    return problems
