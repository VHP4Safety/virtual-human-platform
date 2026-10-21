"""Profile and pinned vocabularies of the model release."""

import hashlib
import json
import os
from functools import cache
from operator import itemgetter
from pathlib import Path

import requests
import yaml
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SH, VOID
from rdfsolve.client.sql_tables import layout
from rdfsolve.iris import curie, local_name
from rdfsolve.schema_models.readers.json_schema import address, json_schema_shape, vocabulary_context
from rdfsolve.schema_models.readers.vocabulary import Vocabulary


# The model of the release is in model/<release>, and its tables are in database/<release>.
RELEASE = "v1"
MODEL_DIR = Path(__file__).parent / "model" / RELEASE
# The tables are written from the profile by `python -m linkeddata model`.
TABLES = Path(__file__).parent.parent / "database" / RELEASE / "tables.sql"
# The shapes of the official profiles are made from their pinned files by `python -m linkeddata model`.
OFFICIAL = MODEL_DIR / "bioschemas-profiles.shacl"
# The prefixes of the terms of the official profiles. A term of an earlier prefix is taken before a term of the same name.
OFFICIAL_PREFIXES = ("schema", "bioschemas", "bioschemas_draft")


FORM = Namespace("https://platform.vhp4safety.nl/model/v1/form#")
DASH = Namespace("http://datashapes.org/dash#")


@cache
def settings() -> dict:
    """Return the settings of the model."""
    graph = profile_graph()
    header = graph.value(None, RDF.type, OWL.Ontology)
    files = {}
    # The files of the official profiles (rdfs:isDefinedBy) are pinned in the same way as the vocabularies.
    for imported in [*graph.objects(header, OWL.imports), *graph.objects(None, RDFS.isDefinedBy)]:
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
    """Return the files of the pinned vocabularies with endings."""
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


def list_terms(of_class: str) -> dict[str, dict[str, str]]:
    """Return the JSON-LD term definitions of the list fields of the shapes of a class, by field name."""
    graph = profile_graph()
    shapes = set(graph.subjects(SH.targetClass, URIRef(of_class)))
    # The shape of a part of a class is given on the field that holds the part.
    for field in graph.subjects(SH["class"], URIRef(of_class)):
        shapes.update(graph.objects(field, SH.node))
    found = {}
    for shape in shapes:
        for field in graph.objects(shape, SH.property):
            path = graph.value(field, SH.path)
            if isinstance(path, URIRef) and graph.value(field, SH.node) == DASH.ListShape:
                found[local_name(str(path))] = {"@id": str(path), "@container": "@list"}
    return found


def official_text() -> str:
    """Return the Turtle of the shapes of the official profiles, made with rdfsolve from their pinned files."""
    graph = profile_graph()
    prefixes = settings()["prefixes"]
    known = Vocabulary([vocabulary(path) for path in vocabularies()])
    terms = vocabulary_context(known, [prefixes[name] for name in OFFICIAL_PREFIXES])
    found = Graph()
    for profile, source in sorted(graph.subject_objects(RDFS.isDefinedBy)):
        published = json.loads((MODEL_DIR / "vocabularies" / str(graph.value(source, FORM.file))).read_text(encoding="utf-8"))
        # A property without a term of the official prefixes keeps the address given in its profile file.
        declared = {}
        for node in published["@graph"]:
            prefix, _, name = str(node["@id"]).partition(":")
            if node.get("@type") == "rdf:Property" and prefix in published["@context"]:
                declared[node["rdfs:label"]] = published["@context"][prefix] + name
        # "type" is the name of @type in the JSON-LD context of schema.org.
        context = {**declared, **terms, "type": str(RDF.type), "@vocab": prefixes["schema"]}
        node = next(node for node in published["@graph"] if "$validation" in node)
        target = address(node["rdfs:subClassOf"]["@id"], context)
        # The list fields of the records of the class are RDF lists, as in the JSON-LD of the records.
        context.update(list_terms(target))
        shape = json_schema_shape(node["$validation"], shape=str(profile), target_class=target, context=context,
                                  levels={"required": "Violation", "recommended": "Warning"}, vocabulary=known)
        shape.to_rdf(found)
    for name in OFFICIAL_PREFIXES:
        found.bind(name, prefixes[name])
    return "# Made from the files of the official profiles by python -m linkeddata model. Do not edit.\n" + found.serialize(format="turtle")


def write_official() -> Path:
    """Write the shapes of the official profiles, and return the path of their file."""
    OFFICIAL.write_text(official_text(), encoding="utf-8")
    return OFFICIAL


def official_problems() -> list[str]:
    """Return a problem if the file of the shapes of the official profiles differs from the profiles."""
    if not OFFICIAL.exists() or OFFICIAL.read_text(encoding="utf-8") != official_text():
        return [f"{OFFICIAL} is out of date: run python -m linkeddata model, review and commit it."]
    return []


@cache
def official() -> Graph:
    """Return the shapes of the official profiles."""
    return Graph().parse(OFFICIAL, format="turtle")


@cache
def official_fields() -> dict:
    """Return the fields of the official shapes, by property shape."""
    graph = official()
    found = {}
    for shape, field in graph.subject_objects(SH.property):
        needs = graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity) == SH.Violation
        path = graph.value(field, SH.path)
        # A path to the members of a list is noted on the list field.
        if isinstance(path, BNode) and graph.value(path, RDF.first) is not None:
            path = graph.value(path, RDF.first)
        found[field] = (shape, path, needs)
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
    shape = shape_of(kind)
    return shape_fields(str(shape)) if shape is not None else []


@cache
def shape_fields(shape: str) -> list[dict]:
    """Return the fields of the node shape at shape, in the order of the form."""
    graph = profile_graph()
    kinds = set(settings()["kinds"].values())
    node_shapes = [URIRef(shape)] + list(graph.objects(URIRef(shape), SH.node))
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
            # The node shape of the values. The values of a list are described by the field of its members.
            described = graph.value(field, SH.node)
            if described == DASH.ListShape:
                member = next((own for own in graph.objects(field, SH.property) if not isinstance(graph.value(own, SH.path), URIRef)), None)
                described = graph.value(member, SH.node) if member is not None else None
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
                "node": str(described) if described is not None else "",
            })
    found.sort(key=itemgetter("position"))
    return found
