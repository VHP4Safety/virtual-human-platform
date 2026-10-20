"""The data model: the vocabularies, classes and application profile of one model version."""

import hashlib
from functools import cache
from pathlib import Path

import requests
import yaml
from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SH, VOID
from rdfsolve.client.sql_tables import layout


# The served release: its model is in model/<release>, its tables in database/<release>.
RELEASE = "v1"
MODEL_DIR = Path(__file__).parent / "model" / RELEASE
PROFILE_DIR = MODEL_DIR / "profile"
# The release's tables, written from its profile by `python -m linkeddata model`.
TABLES = Path(__file__).parent.parent / "database" / RELEASE / "tables.sql"


FORM = Namespace("https://platform.vhp4safety.nl/model/v1/form#")
SOURCES_DIR = Path(__file__).parent / "sources"


@cache
def settings() -> dict:
    """The model's settings, as its profile states them: its title and the address space of its records (the
    ontology's label and void:uriSpace), the files it is built from (owl:imports, each with form:file and
    form:sha256) and those its sources read (pinned in sources/<name>.yaml), its kinds of records (node shapes
    with form:path, in sh:order), the prefixes of its JSON-LD (sh:declare) and the JSON-LD names of other
    vocabularies' properties (form:term)."""
    graph = profile()
    header = graph.value(None, RDF.type, OWL.Ontology)
    files = {}
    # The official shapes the records are checked with (sh:shapesGraph) are pinned as the vocabularies are.
    for imported in [*graph.objects(header, OWL.imports), *graph.objects(header, SH.shapesGraph)]:
        files[str(graph.value(imported, FORM.file))] = {"url": str(imported), "sha256": str(graph.value(imported, FORM.sha256))}
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "pinned" in spec:
            files[spec["vocabulary"]] = {"url": spec["pinned"]["url"], "sha256": str(spec["pinned"]["sha256"])}
    kinds = []
    for shape, path in graph.subject_objects(FORM.path):
        kinds.append((int(graph.value(shape, SH.order) or 0), str(path), str(graph.value(shape, SH.targetClass))))
    prefixes = {}
    for declared in graph.objects(header, SH.declare):
        prefixes[str(graph.value(declared, SH.prefix))] = str(graph.value(declared, SH.namespace))
    terms = {}
    for iri, name in graph.subject_objects(FORM["term"]):
        terms[str(name)] = str(iri)
    return {"title": str(graph.value(header, RDFS.label)), "base": str(graph.value(header, VOID.uriSpace)), "vocabularies": files,
            "kinds": {path: of_class for _, path, of_class in sorted(kinds)}, "prefixes": prefixes, "terms": dict(sorted(terms.items()))}


def vocabularies(config: dict, endings: tuple = (".ttl", ".jsonld")) -> list[Path]:
    """The RDF vocabulary files of the model folder, or with endings (".shacl",) the official shapes; a missing
    file is downloaded from its pinned address. A pinned file of another format, such as a JSON licence list, is
    read by its source only."""
    files = []
    for name in config["vocabularies"]:
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            download_vocabularies()
        if path.suffix in endings:
            files.append(path)
    return files


def pinned_problems() -> list[str]:
    """The vocabulary files that are missing or do not match the SHA-256 the profile or their source pins."""
    problems = []
    for name, pinned in settings()["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            problems.append(f"{path} is missing: run python -m linkeddata model.")
            continue
        found = hashlib.sha256(path.read_bytes()).hexdigest()
        if found != pinned.get("sha256"):
            problems.append(f"{path} has SHA-256 {found}, where it is pinned as {pinned.get('sha256')}.")
    return problems


def download_vocabularies() -> list[str]:
    """Missing vocabulary files are downloaded from their pinned addresses; mismatches are given back."""
    for name, pinned in settings()["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            response = requests.get(pinned["url"], timeout=60, headers={"User-Agent": "VHP4Safety platform build"})
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
    return pinned_problems()


def terms_problems() -> list[str]:
    """The classes and properties used in the profile and defined in no pinned vocabulary."""
    defined = set(profile().subjects())
    for path in vocabularies(settings()):
        defined |= set(vocabulary(path).subjects())
    used = set(profile().objects(None, SH.targetClass)) | set(profile().objects(None, SH.path)) | set(profile().objects(None, SH["class"]))
    return [f"{term} is used in the profile and defined in no pinned vocabulary." for term in sorted(used - defined) if isinstance(term, URIRef)]


def tables_sql() -> str:
    return layout(profile_text()).ddl()


def write_tables() -> Path:
    TABLES.parent.mkdir(parents=True, exist_ok=True)
    TABLES.write_text(tables_sql(), encoding="utf-8")
    return TABLES


def tables_problems() -> list[str]:
    """Whether the release's SQL is what the profile gives."""
    if not TABLES.exists() or TABLES.read_text(encoding="utf-8") != tables_sql():
        return [f"{TABLES} is out of date: run python -m linkeddata model, review and commit it."]
    return []


def profile_files() -> list[Path]:
    """The application profile's modules: its header, and the shapes of each kind of record with its parts."""
    return sorted(PROFILE_DIR.glob("*.ttl"))


@cache
def profile_text() -> str:
    """The application profile's modules as one Turtle text."""
    return "\n".join(path.read_text(encoding="utf-8") for path in profile_files())


@cache
def profile() -> Graph:
    """The application profile: required, fixed and single values, and the form's guidance."""
    return Graph().parse(data=profile_text(), format="turtle")


@cache
def official() -> Graph:
    """The official shapes (sh:shapesGraph). An official shape named by a node shape (dct:conformsTo) is given the
    class of that node shape as a target too, as other addresses are targeted for the Bioschemas types, such as
    LabProtocol, in the Bioschemas file."""
    found = Graph()
    for path in vocabularies(settings(), (".shacl",)):
        found.parse(path, format="turtle")
    for shape, conformed in profile().subject_objects(DCTERMS.conformsTo):
        for of_class in profile().objects(shape, SH.targetClass):
            found.add((conformed, SH.targetClass, of_class))
    return found


@cache
def official_fields() -> dict:
    """The fields of the official shapes, by property shape: the shape, the property (of alternative paths, the
    last) and whether a value is required (a minimum count at Violation severity)."""
    graph = official()
    found = {}
    for shape, field in graph.subject_objects(SH.property):
        path = graph.value(field, SH.path)
        if graph.value(path, SH.alternativePath) is not None:
            path = list(Collection(graph, graph.value(path, SH.alternativePath)))[-1]
        found[field] = (shape, path, graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) == SH.Violation)
    return found


@cache
def required() -> dict[URIRef, tuple[URIRef, set]]:
    """By class, the official shape named by the node shape of the class (dct:conformsTo), and the properties
    required by that shape; dct:conformsTo is left out."""
    found = {}
    for shape, conformed in profile().subject_objects(DCTERMS.conformsTo):
        needed = set()
        for official_shape, path, needs in official_fields().values():
            if official_shape == conformed and needs and path != DCTERMS.conformsTo:
                needed.add(path)
        for of_class in profile().objects(shape, SH.targetClass):
            found[of_class] = (conformed, needed)
    return found


@cache
def shapes() -> Graph:
    """The shapes the records are checked with: those of the profile and the official ones."""
    return profile() + official()


@cache
def vocabulary(path: Path) -> Graph:
    return Graph().parse(path, format="json-ld" if path.suffix == ".jsonld" else "turtle")


@cache
def hierarchy() -> Graph:
    """The vocabularies' class hierarchy (rdfs:subClassOf), so a link to a subclass's record fits."""
    graph = Graph()
    for path in vocabularies(settings()):
        for statement in vocabulary(path).triples((None, RDFS.subClassOf, None)):
            graph.add(statement)
    return graph


def terms(iris: list[str]) -> dict[str, dict]:
    """The vocabulary terms at these addresses, such as the glossary's steps, with label, description and
    vocabulary title."""
    found = {}
    if not iris:
        return found
    for path in vocabularies(settings()):
        graph = vocabulary(path)
        title = path.stem
        for node in graph.subjects(RDF.type, OWL.Ontology):
            title = str(graph.value(node, DCTERMS.title) or title)
        for iri in iris:
            label = graph.value(URIRef(iri), RDFS.label)
            if label is None or iri in found:
                continue
            description = graph.value(URIRef(iri), DC.description) or graph.value(URIRef(iri), RDFS.comment)
            found[iri] = {"name": str(label), "description": str(description or ""), "title": title}
    return found

