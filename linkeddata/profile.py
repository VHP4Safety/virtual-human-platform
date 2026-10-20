"""Profile and pinned vocabularies of the model release."""

import hashlib
import os
from functools import cache
from operator import itemgetter
from pathlib import Path

import requests
import yaml
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SDO, SH, VOID
from rdfsolve.client.sql_tables import layout
from rdfsolve.iris import curie


# The model of the release is in model/<release>, and its tables are in database/<release>.
RELEASE = "v1"
MODEL_DIR = Path(__file__).parent / "model" / RELEASE
# The tables are written from the profile by `python -m linkeddata model`.
TABLES = Path(__file__).parent.parent / "database" / RELEASE / "tables.sql"


FORM = Namespace("https://platform.vhp4safety.nl/model/v1/form#")
DASH = Namespace("http://datashapes.org/dash#")


@cache
def settings() -> dict:
    """Return the settings of the model."""
    graph = profile_graph()
    header = graph.value(None, RDF.type, OWL.Ontology)
    files = {}
    # The official shapes (sh:shapesGraph) are pinned in the same way as the vocabularies.
    for imported in [*graph.objects(header, OWL.imports), *graph.objects(header, SH.shapesGraph)]:
        files[str(graph.value(imported, FORM.file))] = {"url": str(imported), "sha256": str(graph.value(imported, FORM.sha256))}
    for path in sorted((Path(__file__).parent / "sources").glob("*.yaml")):
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


def jsonld_name(iri: str) -> str:
    """Return the JSON-LD name of the property or class at iri."""
    for name, named in settings().get("terms", {}).items():
        if iri == named:
            return name
    found = curie(iri, settings()["prefixes"])
    if found is None:
        return iri
    written, prefix, namespace = found
    return iri.removeprefix(namespace) if prefix == "schema" else written


def vocabularies(endings: tuple = (".ttl", ".jsonld")) -> list[Path]:
    """Return the files of the pinned vocabularies, or of the official shapes with endings."""
    files = []
    for name in settings()["vocabularies"]:
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            download_vocabularies()
        if path.suffix in endings:
            files.append(path)
    return files


def download_vocabularies() -> list[str]:
    """Download the missing vocabulary files, and return the files with a wrong SHA-256."""
    problems = []
    for name, pinned in settings()["vocabularies"].items():
        path = MODEL_DIR / "vocabularies" / name
        if not path.exists():
            response = requests.get(pinned["url"], timeout=60, headers={"User-Agent": "VHP4Safety platform build"})
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        found = hashlib.sha256(path.read_bytes()).hexdigest()
        if found != pinned["sha256"]:
            problems.append(f"{path} has SHA-256 {found}, where it is pinned as {pinned['sha256']}.")
    return problems


def terms_problems() -> list[str]:
    """Return the classes and properties of the profile that no pinned vocabulary defines."""
    defined = set(profile_graph().subjects())
    for path in vocabularies():
        defined |= set(vocabulary(path).subjects())
    used = set(profile_graph().objects(None, SH.targetClass)) | set(profile_graph().objects(None, SH.path)) | set(profile_graph().objects(None, SH["class"]))
    return [f"{term} is used in the profile and defined in no pinned vocabulary." for term in sorted(used - defined) if isinstance(term, URIRef)]


def write_tables() -> Path:
    """Write the SQL of the release tables, and return its path."""
    TABLES.parent.mkdir(parents=True, exist_ok=True)
    TABLES.write_text(layout(profile_text()).ddl(), encoding="utf-8")
    return TABLES


def tables_problems() -> list[str]:
    """Return a problem if the SQL of the release differs from the profile."""
    if not TABLES.exists() or TABLES.read_text(encoding="utf-8") != layout(profile_text()).ddl():
        return [f"{TABLES} is out of date: run python -m linkeddata model, review and commit it."]
    return []


@cache
def profile_text() -> str:
    """Return the profile as one Turtle text."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted((MODEL_DIR / "profile").glob("*.ttl")))


@cache
def profile_graph() -> Graph:
    """Return the profile as a graph."""
    graph = Graph().parse(data=profile_text(), format="turtle")
    if os.environ.get("PLATFORM_BASE"):
        graph.set((graph.value(None, RDF.type, OWL.Ontology), VOID.uriSpace, Literal(os.environ["PLATFORM_BASE"].rstrip("/") + "/")))
    return graph


@cache
def official() -> Graph:
    """Return the official shapes, with targets from the profile."""
    found = Graph()
    for path in vocabularies((".shacl",)):
        found.parse(path, format="turtle")
    for target in (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf):
        found.remove((None, target, None))
    for shape, conformed in profile_graph().subject_objects(DCTERMS.conformsTo):
        for of_class in profile_graph().objects(shape, SH.targetClass):
            found.add((conformed, SH.targetClass, of_class))
    properties = set()
    for path in vocabularies():
        properties.update(str(term) for term in vocabulary(path).subjects(RDF.type, RDF.Property))
    for field, path in list(found.subject_objects(SH.path)):
        if isinstance(path, URIRef) and corrected(path, properties) != path:
            found.set((field, SH.path, corrected(path, properties)))
    return found


# Change against upstream: in the official shapes, some properties have addresses at discovery.biothings.io, such as
# https://discovery.biothings.io/view/bioschemasdrafts/keywords, which are not used in markup.
BIOTHINGS = {"https://discovery.biothings.io/view/bioschemas/": "https://bioschemas.org/terms/",
             "https://discovery.biothings.io/view/bioschemasdrafts/": "https://bioschemas.org/draft_terms/"}


def corrected(path: URIRef, properties: set[str]) -> URIRef:
    """Return the schema.org or Bioschemas property for the discovery.biothings.io address path."""
    for prefix, namespace in BIOTHINGS.items():
        if str(path).startswith(prefix):
            name = str(path).removeprefix(prefix)
            return URIRef(str(SDO) + name) if str(SDO) + name in properties else URIRef(namespace + name)
    return path


@cache
def official_fields() -> dict:
    """Return the fields of the official shapes, by property shape."""
    graph = official()
    found = {}
    for shape, field in graph.subject_objects(SH.property):
        path = graph.value(field, SH.path)
        if graph.value(path, SH.alternativePath) is not None:
            paths = list(Collection(graph, graph.value(path, SH.alternativePath)))
            path = next((given for given in paths if str(given).startswith(str(SDO))), paths[-1])
        found[field] = (shape, path, graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) == SH.Violation)
    return found


@cache
def required() -> dict[URIRef, tuple[URIRef, set]]:
    """Return the official shape and its required properties for each class."""
    found = {}
    for shape, conformed in profile_graph().subject_objects(DCTERMS.conformsTo):
        needed = set()
        for official_shape, path, needs in official_fields().values():
            if official_shape == conformed and needs and path != DCTERMS.conformsTo:
                needed.add(path)
        for of_class in profile_graph().objects(shape, SH.targetClass):
            found[of_class] = (conformed, needed)
    return found


@cache
def shapes() -> Graph:
    """Return the shapes of the profile and the official shapes."""
    return profile_graph() + official()


@cache
def vocabulary(path: Path) -> Graph:
    return Graph().parse(path, format="json-ld" if path.suffix == ".jsonld" else "turtle")


@cache
def hierarchy() -> Graph:
    """Return the class hierarchy of the pinned vocabularies."""
    graph = Graph()
    for path in vocabularies():
        for statement in vocabulary(path).triples((None, RDFS.subClassOf, None)):
            graph.add(statement)
    return graph


def terms(iris: list[str]) -> dict[str, dict]:
    """Return the vocabulary terms at iris, with label, description and vocabulary title."""
    found = {}
    if not iris:
        return found
    for path in vocabularies():
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


def shape_of(kind: str) -> URIRef | None:
    """Return the node shape of the class kind."""
    return profile_graph().value(None, SH.targetClass, URIRef(kind))


# The node kinds of a field of parts. A part is stored with an address under its record (database.records.PART).
PARTS = (SH.BlankNode, SH.BlankNodeOrIRI)


@cache
def fields(kind: str) -> list[dict]:
    """Return the fields of the class kind, in the order of the form."""
    graph = profile_graph()
    kinds = set(settings()["kinds"].values())
    shape = shape_of(kind)
    node_shapes = [shape] + list(graph.objects(shape, SH.node)) if shape is not None else []
    found = []
    for node in node_shapes:
        for field in graph.objects(node, SH.property):
            path = str(graph.value(field, SH.path))
            group = graph.value(field, SH.group)
            name = graph.value(field, SH.name)
            fixed = []
            for value in graph.objects(field, SH.hasValue):
                fixed.append(str(value))
            values = []
            iris = graph.value(field, SH.nodeKind) == SH.IRI
            for listed in graph.objects(field, SH["in"]):
                for value in graph.items(listed):
                    values.append(str(value))
                    iris = iris or isinstance(value, URIRef)
            classes = []
            for of_class in graph.objects(field, SH["class"]):
                classes.append(str(of_class))
            for alternatives in graph.objects(field, SH["or"]):
                for alternative in graph.items(alternatives):
                    for of_class in graph.objects(alternative, SH["class"]):
                        classes.append(str(of_class))
            found.append({
                "name": jsonld_name(path),
                "iri": path,
                "label": str(name) if name is not None else jsonld_name(path),
                "description": str(graph.value(field, SH.description) or ""),
                "single": graph.value(field, SH.maxCount) == Literal(1),
                "values": values,
                "classes": classes,
                "datatype": str(graph.value(field, SH.datatype) or ""),
                "address": graph.value(field, SH.nodeKind) == SH.IRI,
                "iris": iris or (bool(classes) and graph.value(field, SH.nodeKind) not in PARTS),
                "pattern": str(graph.value(field, SH.pattern) or ""),
                "required": graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) != SH.Warning,
                "warning": graph.value(field, SH.severity) == SH.Warning,
                "shown": graph.value(field, FORM.shown) != Literal(False),
                "recommended": graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) == SH.Warning,
                "message": str(graph.value(field, SH.message) or ""),
                "fixed": fixed,
                "part": graph.value(field, SH.nodeKind) in PARTS or (
                    graph.value(field, SH.node) is not None and str(graph.value(field, SH["class"])) not in kinds),
                "addressed": graph.value(field, SH.nodeKind) == SH.IRI,
                "read_only": graph.value(field, DASH.readOnly) == Literal(True),
                "position": (int(graph.value(group, SH.order) or 0) if group is not None else 0, str(group or ""), int(graph.value(field, SH.order) or 0)),
                "section": str(graph.value(group, RDFS.label) or "") if group is not None else "",
            })
    found.sort(key=itemgetter("position"))
    return found
