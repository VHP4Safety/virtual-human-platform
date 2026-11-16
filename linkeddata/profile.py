"""Profile and pinned vocabularies of the model release."""

import hashlib
import json
import os
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DC, DCTERMS, OWL, RDFS, SDO, SH
from rdfsolve.client.sql_tables import layout
from rdfsolve.iris import curie, local_name, namespace
from rdfsolve.schema_models.readers.json_schema import address, json_schema_shape, readable, vocabulary_context
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
# The levels of the JSON Schema of the official profiles, with the severity of a missing property.
LEVELS = {"required": "Violation", "recommended": "Warning"}
# The profiles that the platform publishes, in SHACL, in the layout of rocrate-validator: profiles/<name>/<version>/ has the
# description of the profile (profile.ttl, in the Profiles Vocabulary) and its shapes.
PROFILES = MODEL_DIR / "profiles"
# The settings of the release that are not shapes, and the JSON-LD context of the records with the prefixes and the JSON names.
SETTINGS = MODEL_DIR / "settings.yaml"
CONTEXT = MODEL_DIR / "context.jsonld"


FORM = Namespace("https://platform.vhp4safety.nl/model/v1/form#")
DASH = Namespace("http://datashapes.org/dash#")
PROF = Namespace("http://www.w3.org/ns/dx/prof/")


@cache
def settings() -> dict:
    """Return the settings of the model."""
    given = yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT.read_text(encoding="utf-8"))["@context"]
    # A name whose address ends in / or # is a prefix, any other name is the JSON name of a property, and a name with a
    # context of its own is a class with list fields.
    named = {name: iri for name, iri in context.items() if not name.startswith("@") and isinstance(iri, str)}
    prefixes = {name: iri for name, iri in named.items() if iri.endswith(("/", "#"))}
    terms = {name: iri for name, iri in named.items() if name not in prefixes}

    def expanded(name: str) -> str:
        prefix, _, local = name.partition(":")
        return prefixes[prefix] + local if local and prefix in prefixes else prefixes["schema"] + name

    lists = {}
    for entry in context.values():
        if isinstance(entry, dict) and "@context" in entry:
            lists[expanded(entry["@id"])] = [expanded(term["@id"]) for term in entry["@context"].values() if term.get("@container") == "@list"]
    files = {}
    # The files of the official profiles are pinned in the same way as the vocabularies.
    for pinned in [*given["vocabularies"], *given["profiles"].values()]:
        files[pinned["file"]] = {"url": pinned["url"], "sha256": pinned["sha256"]}
    for path in sorted((Path(__file__).parent / "sources").glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "pinned" in spec:
            files[spec["vocabulary"]] = {"url": spec["pinned"]["url"], "sha256": str(spec["pinned"]["sha256"])}
    kinds = {path: expanded(kind["class"]) for path, kind in given["kinds"].items()}
    labels = {expanded(kind["class"]): kind["label"] for kind in given["kinds"].values()}
    base = os.environ.get("PLATFORM_BASE", given["base"]).rstrip("/") + "/"
    profiles = {profile: pinned["file"] for profile, pinned in given["profiles"].items()}
    by_class = {}
    for key in ("read only", "hidden"):
        by_class[key] = {expanded(of_class): {expanded(path) for path in paths} for of_class, paths in given.get(key, {}).items()}
    released = given["base"].rstrip("/") + "/"
    # A copy at another address, such as a test site, is kept out of search indexes and training sets.
    return {"title": given["title"], "base": base, "release base": released, "copy": base != released, "vocabularies": files, "profiles": profiles, "kinds": kinds, "labels": labels,
            "prefixes": prefixes, "terms": dict(sorted(terms.items())), "lists": lists, "private": {expanded(path) for path in given.get("private", [])},
            "published as": {expanded(path): expanded(of_class) for path, of_class in given.get("published as", {}).items()},
            "read only": by_class["read only"], "hidden": by_class["hidden"], "read only in the editor": set(given.get("read only in the editor", []))}


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
    """Return the classes and properties of the platform profiles that no pinned vocabulary and no profile defines."""
    given = Graph()
    for paths in platform_profiles().values():
        for path in paths:
            given.parse(path, format="turtle")
    defined = set(given.subjects(RDF.type, None))
    for path in vocabularies():
        defined |= set(vocabulary(path).subjects())
    used = set(given.objects(None, SH.targetClass)) | {path for path in given.objects(None, SH.path) if isinstance(path, URIRef)} | set(given.objects(None, SH["class"]))
    # A crate term is defined by the official term of the same name.
    used = set(official_terms(Graph().parse(data="\n".join(f"<{term}> <{term}> <{term}> ." for term in used), format="nt"),
                              official_context()).subjects())
    return [f"{term} is used in a platform profile and defined in no pinned vocabulary." for term in sorted(used - defined)]


def write_tables() -> Path:
    """Write the SQL of the release tables, and return its path."""
    TABLES.parent.mkdir(parents=True, exist_ok=True)
    TABLES.write_text(layout(shapes_text()).ddl(), encoding="utf-8")
    return TABLES


def tables_problems() -> list[str]:
    """Return a problem if the SQL of the release differs from the profile."""
    if not TABLES.exists() or TABLES.read_text(encoding="utf-8") != layout(shapes_text()).ddl():
        return [f"{TABLES} is out of date: run python -m linkeddata model, review and commit it."]
    return []


@cache
def shapes_text() -> str:
    """Return the shapes of the profiles as one Turtle text, with a prefix for each namespace of their properties."""
    prefixes = dict(settings()["prefixes"])
    taken = set(prefixes.values()) | {str(space) for _, space in Graph().namespaces()}
    # A property declared by a profile file at the address of its editor, such as an address of discovery.biothings.io,
    # is named after the domain and the last part of its namespace, such as biothings_bioschemas.
    for path in official().objects(None, SH.path):
        space = namespace(str(path)) if isinstance(path, URIRef) else None
        if space and space not in taken:
            address = urlparse(space)
            prefixes[f"{address.hostname.split('.')[-2]}_{address.path.strip('/').rsplit('/', 1)[-1]}"] = space
            taken.add(space)
    declared = "".join(f"@prefix {name}: <{space}> .\n" for name, space in prefixes.items())
    return declared + OFFICIAL.read_text(encoding="utf-8")


def list_terms(of_class: str) -> dict[str, dict[str, str]]:
    """Return the JSON-LD term definitions of the list fields of a class, by field name."""
    return {local_name(path): {"@id": path, "@container": "@list"} for path in settings()["lists"].get(of_class, [])}


def profile_files() -> dict[str, Path]:
    """Return the pinned file of each official profile, by address."""
    return {profile: MODEL_DIR / "vocabularies" / name for profile, name in settings()["profiles"].items()}


def platform_profiles() -> dict[str, list[Path]]:
    """Return the shapes files of each profile of the platform, by address."""
    found = {}
    for described in sorted(PROFILES.glob("*/*/profile.ttl")):
        graph = Graph().parse(described, format="turtle")
        for profile in graph.subjects(RDF.type, PROF.Profile):
            found[str(profile)] = [described.parent / str(artifact).rsplit("/", 1)[-1] for artifact in graph.objects(None, PROF.hasArtifact)]
    return found


def official_terms(graph: Graph, terms: dict[str, str]) -> Graph:
    """Return graph with each term of the host and the name of an official term read as that term, such as http://schema.org/name."""

    def official(node):
        given = terms.get(local_name(str(node))) if isinstance(node, URIRef) else None
        if given and urlparse(given).netloc == urlparse(str(node)).netloc:
            return URIRef(given)
        return node

    found = Graph()
    for subject, predicate, value in graph:
        found.add((official(subject), official(predicate), official(value)))
    return found


@cache
def known() -> Vocabulary:
    """Return the pinned vocabularies."""
    return Vocabulary([vocabulary(path) for path in vocabularies()])


@cache
def official_context() -> dict[str, str]:
    """Return the official terms by name: schema.org first, then Bioschemas."""
    return vocabulary_context(known(), [settings()["prefixes"][name] for name in OFFICIAL_PREFIXES])


def official_text() -> str:
    """Return the Turtle of the shapes of the official profiles, made with rdfsolve from their files, and of the platform profiles."""
    prefixes = settings()["prefixes"]
    terms = official_context()
    found = Graph()
    for profile, path in sorted(profile_files().items()):
        published = json.loads(path.read_text(encoding="utf-8"))
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
                                  levels=LEVELS, vocabulary=known())
        shape.to_rdf(found)
    for profile, paths in sorted(platform_profiles().items()):
        given = Graph()
        for path in paths:
            given.parse(path, format="turtle")
        found += official_terms(given, terms)
    for name, namespace in prefixes.items():
        found.bind(name, namespace)
    header = ("# Made from the files of the official profiles and of the platform profiles by python -m linkeddata model. Do not edit.\n"
              "# The severities of the official profiles are set by the platform, as JSON Schema has none: a missing required property\n"
              "# is a Violation, and a missing recommended property or a value that does not fit is a Warning. The platform profiles\n"
              "# are in SHACL, with their own severities, and a term of the host and the name of an official term, such as\n"
              "# http://schema.org/name in a profile of crates, is read as that term.\n")
    return header + found.serialize(format="turtle")


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
def required() -> dict[URIRef, list[tuple[URIRef, set]]]:
    """Return the profiles of each class, with the properties that each profile requires."""
    graph = official()
    profiles = [*settings()["profiles"], *platform_profiles()]
    found = {}
    for shape, of_class in graph.subject_objects(SH.targetClass):
        profile = next((URIRef(given) for given in profiles if str(shape) in (given, ) or str(shape).startswith(given + "#")), None)
        if profile is None:
            continue
        needed = set()
        for field in graph.objects(shape, SH.property):
            path = field_path(graph, field)
            if path != DCTERMS.conformsTo and graph.value(field, SH.minCount) is not None and graph.value(field, SH.severity, default=SH.Violation) == SH.Violation:
                needed.add(path)
        found.setdefault(of_class, []).append((profile, needed))
    return found


@cache
def shapes() -> Graph:
    """Return the shapes of the profiles."""
    return official()


@cache
def known_terms() -> set[str]:
    """Return the terms that the pinned vocabularies define and the properties of the shapes of the profiles."""
    found = {str(path) for path in official().objects(None, SH.path) if isinstance(path, URIRef)}
    for path in vocabularies():
        found |= {str(term) for term in vocabulary(path).subjects() if isinstance(term, URIRef)}
    return found


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


def shape_of(of_class: str) -> URIRef:
    """Return the node shape of the form of the records of a class."""
    return FORM[local_name(of_class)]


# The node kinds of a field of parts. A part is stored with an address under its record (database.records.PART).
PARTS = (SH.BlankNode, SH.BlankNodeOrIRI)
# A property shape with one of these is a field. A property shape with only a count, such as the shape of a required
# property of an official profile, is the requirement of the field of the same property.
VALUES = (SH["or"], SH.datatype, SH["class"], SH.node, SH["in"], SH.nodeKind, SH.pattern, SH.order)
# The groups of the levels of the official profiles group the fields of a form, but are no sections of the pages.
LEVEL_GROUPS = tuple(f"#group-{level}" for level in (*LEVELS, "optional"))


def field_path(graph: Graph, field) -> URIRef:
    """Return the property of a field: of a field of a list, the first step of its path to the members."""
    path = graph.value(field, SH.path)
    return graph.value(path, RDF.first) if isinstance(path, BNode) else path


def platform_shape(shape) -> bool:
    """Return True if shape is a shape of a platform profile."""
    return any(str(shape).startswith(profile + "#") for profile in platform_profiles())


@cache
def linked_classes() -> set[URIRef]:
    """Return the classes whose values are links to records: the classes of the kinds, and the classes above and below them."""
    found = set()
    for kind in settings()["kinds"].values():
        found |= {URIRef(kind), *hierarchy().transitive_objects(URIRef(kind), RDFS.subClassOf), *hierarchy().transitive_subjects(RDFS.subClassOf, URIRef(kind))}
    return found


@cache
def node_shapes(of_class: str) -> tuple[str, ...]:
    """Return the node shapes that apply to the records of a class, those of the platform profiles first."""
    graph = official()
    above = {URIRef(of_class), *hierarchy().transitive_objects(URIRef(of_class), RDFS.subClassOf)}
    found = sorted({shape for shape, target in graph.subject_objects(SH.targetClass) if target in above}, key=lambda shape: (not platform_shape(shape), str(shape)))
    # A node shape that another uses as a whole, such as the shape of the pages for an about page, applies too.
    for shape in found:
        found.extend(used for used in graph.objects(shape, SH.node) if used not in found)
    return tuple(str(shape) for shape in found)


@cache
def fields(of_class: str) -> list[dict]:
    """Return the fields of the records of a class, in the order of the form."""
    above = {of_class, *map(str, hierarchy().transitive_objects(URIRef(of_class), RDFS.subClassOf))}
    read_only = set().union(*(settings()["read only"].get(given, set()) for given in above))
    hidden = set().union(*(settings()["hidden"].get(given, set()) for given in above))
    found = []
    for field in shape_fields(*node_shapes(of_class)):
        found.append({**field, "read_only": field["iri"] in read_only, "shown": field["iri"] not in hidden})
    return found


@cache
def shape_fields(*shapes: str) -> list[dict]:
    """Return the fields of node shapes, one for each property, in the order of the form. The first shape of a property gives its field."""
    graph = official()
    needed, chosen = {}, {}
    for rank, shape in enumerate(shapes):
        for field in graph.objects(URIRef(shape), SH.property):
            path = field_path(graph, field)
            if graph.value(field, SH.minCount) is not None:
                needed.setdefault(path, graph.value(field, SH.severity, default=SH.Violation))
            # The type of a record is the class of its kind, so it has no field.
            if path != RDF.type and any(graph.value(field, value) is not None for value in VALUES):
                chosen.setdefault(path, (rank, field))
    found = [described(graph, field, path, rank, needed.get(path)) for path, (rank, field) in chosen.items()]
    # The name comes first, as it names the record in the form and on its page.
    found.sort(key=lambda field: (field["iri"] != str(SDO.name), field["position"]))
    return found


def described(graph: Graph, field, path: URIRef, rank: int, needs) -> dict:
    """Return a field of a form from its property shape: its values are links, parts, listed values, addresses or texts."""
    choices = [field, *(graph.items(graph.value(field, SH["or"])) if graph.value(field, SH["or"]) is not None else [])]
    links, parts, addressed, values, datatypes = {}, {}, [], [], []
    for choice in choices:
        listed = graph.value(choice, SH["in"])
        values += [str(value) for value in graph.items(listed)] if listed is not None else []
        if graph.value(choice, SH.datatype) is not None:
            datatypes.append(str(graph.value(choice, SH.datatype)))
        of_class = graph.value(choice, SH["class"])
        if of_class is None:
            continue
        # A value with a shape of its own is a part. A value of a class without records, such as a DataDownload, is a
        # part with the fields of its shape (a definition of a profile); any other value is a link to a record.
        node = graph.value(choice, SH.node) or graph.value(field, SH.node)
        if node is None and of_class not in linked_classes() and graph.value(choice, SH.property) is not None:
            node = choice
        if node is None:
            links[str(of_class)] = str(graph.value(choice, RDFS.label) or settings()["labels"].get(str(of_class)) or readable(local_name(str(of_class))))
            continue
        parts[str(of_class)] = str(node)
        # A part with an address of its own is a record under its record, such as a step of a case-study question.
        if SH.IRI in (graph.value(choice, SH.nodeKind), graph.value(field, SH.nodeKind)):
            addressed.append(str(of_class))
    group = graph.value(field, SH.group)
    level = group is not None and str(group).endswith(LEVEL_GROUPS)
    kinds = {graph.value(choice, SH.nodeKind) for choice in choices} - {None}
    # An address of a property that ranges over the class of a kind is a link to a record of that kind, such as the
    # vocabulary of a term.
    if not links and SH.IRI in kinds:
        for given in known().objects(str(path), str(SDO.rangeIncludes)):
            if given in settings()["kinds"].values():
                links[given] = settings()["labels"].get(given) or readable(local_name(given))
    texts = bool(datatypes) or SH.Literal in kinds or (not links and not parts and not values and not kinds)
    address = not links and not parts and not datatypes and SH.IRI in kinds and SH.Literal not in kinds
    return {
        "name": jsonld_name(str(path)),
        "iri": str(path),
        "label": str(graph.value(field, SH.name) or readable(local_name(str(path)))),
        "description": str(graph.value(field, SH.description) or ""),
        "single": graph.value(field, SH.maxCount) == Literal(1),
        "list": isinstance(graph.value(field, SH.path), BNode),
        "values": values,
        "classes": [*links, *parts],
        "links": links,
        "parts": parts,
        "texts": texts,
        # A field of texts or links, such as keywords that are terms or texts.
        "open": texts and SH.IRI in kinds,
        "datatype": datatypes[0] if datatypes else "",
        "address": address,
        "iris": bool(links) or address or any(value.startswith(("http://", "https://")) for value in values),
        "pattern": str(graph.value(field, SH.pattern) or ""),
        "required": needs == SH.Violation,
        "recommended": needs == SH.Warning,
        "warning": graph.value(field, SH.severity) == SH.Warning,
        "message": str(graph.value(field, SH.message) or ""),
        "fixed": [str(value) for value in graph.objects(field, SH.hasValue)],
        "part": bool(parts),
        "addressed": addressed,
        "node": next(iter(parts.values())) if len(parts) == 1 else "",
        "long": graph.value(field, DASH.singleLine) == Literal(False),
        "position": (rank, int(graph.value(group, SH.order) or 0) if group is not None else 0, int(graph.value(field, SH.order) or 0)),
        "group": str(graph.value(group, RDFS.label) or "") if group is not None else "",
        "section": str(graph.value(group, RDFS.label) or "") if group is not None and not level else "",
        "read_only": False,
        "shown": True,
    }
