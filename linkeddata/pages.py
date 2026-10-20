"""Content of the record pages, the listings and the home page, made from the stored records, and the Markdown of a
record (RFC 7763, GitHub variant)."""

from functools import lru_cache
from operator import itemgetter

from markdownify import markdownify
from markupsafe import Markup
from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.namespace import SDO, VOID
from werkzeug.datastructures import MultiDict

from database import records
from database.tables import Record
from linkeddata import documents, void
from linkeddata.parsers import QUESTIONS
from linkeddata.profile import fields, jsonld_name, profile_graph, settings, shape_of

# The name is used as the heading of a node, and the position for its order. Neither is listed with the fields.
HEADING = {str(SDO.name), str(SDO.position)}
# A text in HTML, or a text longer than this, is shown as paragraphs. Other values are shown as a list.
SHORT = 160
# Records on one page of a listing.
LISTED = 12
MEDIA = "text/markdown; charset=utf-8; variant=GFM"


def text(value):
    """Prepare a text for a template. Return an HTML text as {"@value": ...}."""
    if isinstance(value, Literal) and value.datatype == RDF.HTML:
        return {"@value": str(value)}
    return str(value) if value is not None else ""


def kind_of(of_class: str) -> str:
    """Return the label of a class in the profile, such as "Workflow page"."""
    return str(profile_graph().value(shape_of(of_class), RDFS.label) or "")


def in_order(found: Graph, nodes) -> list:
    """Sort nodes by position, then by name, then by values, with the nodes without a position last."""
    def place(node):
        try:
            number = float(found.value(node, SDO.position))
        except (TypeError, ValueError):
            number = float("inf")
        return number, str(found.value(node, SDO.name) or ""), sorted(str(value) for value in found.objects(node, None))
    return sorted(nodes, key=place)


def by_name(item: dict) -> str:
    """Return the sort key of an item: its name, in lower case."""
    return item["name"].casefold()


def node_outline(found: Graph, node, names: dict) -> dict:
    """Return the outline of a node from its statements, with an outline for each part."""
    of_class = str(found.value(node, RDF.type) or "")
    shown = {"address": None if isinstance(node, BNode) else str(node), "name": str(found.value(node, SDO.name) or ""),
             "kind": kind_of(of_class), "fields": [], "parts": []}
    for field in fields(of_class):
        values = list(found.objects(node, URIRef(field["iri"])))
        if field["iri"] in HEADING or not values or not field["shown"]:
            continue
        # A node without an address is shown as a part, also in a field of links, such as a named input.
        parts = [value for value in values if field["part"] or isinstance(value, BNode)]
        if parts:
            shown["parts"].append({"label": field["label"], "items": [node_outline(found, part, names) for part in in_order(found, parts)]})
        values = [value for value in values if value not in parts]
        if not values:
            continue
        values.sort(key=str)
        given = []
        long = False
        for value in values:
            if isinstance(value, Literal):
                given.append({"text": str(value), "html": value.datatype == RDF.HTML})
                if value.datatype == RDF.HTML or len(str(value)) > SHORT:
                    long = True
            else:
                given.append({"link": str(value), "name": names.get(str(value)) or str(value)})
        shown["fields"].append({"name": field["name"], "label": field["label"], "values": given, "long": long, "section": field["section"]})
    return shown


def named_on(record: Record) -> dict[str, list[dict]]:
    """Return the records with links to a record, grouped by the label of the field with the link."""
    paths = {}
    for iri, path in records.naming(record.iri):
        paths.setdefault(iri, []).append(path)
    found = {}
    for other in records.kept(list(paths)):
        if other.iri == record.iri:
            continue
        labels = {}
        for field in fields(other.type):
            labels[field["iri"]] = field["label"]
        for path in paths[other.iri]:
            found.setdefault(labels.get(path) or jsonld_name(path), []).append(
                {"address": other.iri, "name": other.name or other.iri, "kind": kind_of(other.type)})
    for listed in found.values():
        listed.sort(key=by_name)
    return found


def outline(record: Record) -> dict:
    """Return the outline of a record from its public statements, without private fields."""
    found = documents.public(records.graph([record.iri]))
    links = []
    for value in found.objects():
        if isinstance(value, URIRef):
            links.append(str(value))
    shown = node_outline(found, URIRef(record.iri), records.names(links))
    shown["named_on"] = named_on(record)
    return shown


def markdown_lines(found: dict, level: int) -> list[str]:
    """Write an outline as Markdown blocks. Below the sixth level, write a heading as a bold line."""
    title = found["name"] or found["kind"]
    lines = ["#" * level + " " + title if level <= 6 else f"**{title}**"]
    if level > 1 and found["kind"]:
        lines.append(f"_{found['kind']}_" + (f" · <{found['address']}>" if found["address"] else ""))
    listed = []
    for field in found["fields"]:
        values = []
        for value in field["values"]:
            if "link" not in value:
                values.append(markdownify(value["text"], heading_style="ATX", bullets="-").strip() if value["html"] else value["text"].strip())
            elif value["name"] == value["link"]:
                values.append(f"<{value['link']}>")
            else:
                values.append(f"[{value['name']}]({value['link']})")
        if field["long"]:
            lines.append(f"**{field['label']}**\n\n" + "\n\n".join(values))
        else:
            listed.append(f"- **{field['label']}:** " + "; ".join(values))
    if listed:
        lines.append("\n".join(listed))
    for group in found["parts"]:
        for item in group["items"]:
            lines.extend(markdown_lines(item, level + 1))
    return lines


def markdown(record: Record, formats: dict[str, str], licence: str) -> str:
    """Write a record in Markdown, with links to its data in other formats and to the licence."""
    found = outline(record)
    lines = markdown_lines(found, 1)
    lines.insert(1, f"<{found['address']}>")
    data = " · ".join(f"[{name}]({address})" for name, address in formats.items())
    lines.append(f"---\n\nData: {data}" + (f"  \nLicence: <{licence}>" if licence else ""))
    return "\n\n".join(lines) + "\n"


def figures(found: Graph, node, path) -> list[dict]:
    """List the images of a node with their address and caption."""
    listed = []
    for figure in found.objects(node, path):
        listed.append({"address": str(found.value(figure, SDO.contentUrl) or ""), "caption": str(found.value(figure, SDO.caption) or "")})
    return listed


def videos(found: Graph, node, path) -> list[dict]:
    """List the videos of a node with their name and player address."""
    listed = []
    for video in found.objects(node, path):
        listed.append({"name": str(found.value(video, SDO.name) or ""), "player": str(found.value(video, SDO.embedUrl) or "")})
    return listed


def outputs(grant) -> list[dict]:
    """List the works funded by a grant, such as publications and data, by name, without organisations and
    projects."""
    if grant is None:
        return []
    funded = set()
    for iri, path in records.naming(str(grant)):
        if path == str(SDO.funding):
            funded.add(iri)
    organisations = records.within(str(SDO.Organization))
    listed = []
    for record in records.kept(sorted(funded)):
        if record.type in organisations:
            continue
        listed.append({"address": record.iri, "name": record.name or record.iri, "kind": kind_of(record.type)})
    listed.sort(key=by_name)
    return listed


def shown(found: Graph, part) -> list[dict]:
    """Return the fields named by form:shows from the record that a section is about, in the field order of the
    profile."""
    presented = found.value(part, SDO.about)
    properties = list(found.objects(part, URIRef(settings()["prefixes"]["form"] + "shows")))
    if presented is None or not properties:
        return []
    held = documents.public(records.with_names(records.graph([str(presented)])))
    node = URIRef(str(presented))
    positions = {}
    for field in fields(str(held.value(node, RDF.type) or "")):
        positions[field["iri"]] = field["position"]

    def place(prop):
        return positions.get(str(prop), (len(positions), "", 0)), str(prop)

    blocks = []
    for prop in sorted(properties, key=place):
        entries = []
        links = []
        for value in in_order(held, held.objects(node, prop)):
            if isinstance(value, Literal):
                blocks.append({"text": text(value)})
            elif isinstance(value, URIRef):
                links.append({"address": str(value), "name": str(held.value(value, SDO.name) or value)})
            elif held.value(value, SDO.contentUrl) is not None:
                blocks.append({"figures": figures(held, node, prop)})
                break
            elif held.value(value, SDO.embedUrl) is not None:
                blocks.append({"videos": videos(held, node, prop)})
                break
            else:
                entries.append({"name": str(held.value(value, SDO.name) or ""), "description": str(held.value(value, SDO.description) or "")})
        if entries:
            blocks.append({"entries": entries})
        if links:
            blocks.append({"links": links})
    return blocks


def sections(found: Graph, node) -> list[dict]:
    """List the sections of a node by position, without hidden sections."""
    parts = in_order(found, found.objects(node, SDO.hasPart))
    listed = []
    for part in parts:
        if str(found.value(part, SDO.creativeWorkStatus) or "") == "hidden":
            continue
        presented = shown(found, part)
        listed.append({"heading": str(found.value(part, SDO.name) or ""), "text": text(found.value(part, SDO.text)),
                       "figures": figures(found, part, SDO.image), "videos": videos(found, part, SDO.video),
                       "sections": sections(found, part), "shown": presented,
                       "outputs": [] if presented else outputs(found.value(part, SDO.about))})
    return listed


def kinds(term: str) -> list[dict]:
    """List the kinds of a glossary term with a label, an anchor and a definition. Remove the name of the term from
    each label."""
    found = records.kinds_of(term)
    statements = records.graph([kind.iri for kind in found])
    listed = []
    for kind in found:
        label = kind.name.rsplit(" (", 1)[0]
        descriptions = documents.stored_values(statements, kind.iri, "description")
        listed.append({"iri": kind.iri, "label": label, "slug": label.lower().replace(" ", "-"),
                       "description": descriptions[0] if descriptions else ""})
    return listed


def page(record: Record) -> dict:
    """Return the content of a platform page from its record."""
    found = documents.public(records.graph([record.iri]))
    node = URIRef(record.iri)
    listed = sections(found, node)
    about = found.value(node, SDO.about)
    return {"name": str(found.value(node, SDO.name) or record.name or ""), "description": str(found.value(node, SDO.description) or ""),
            "sections": listed, "tabbed": any(section["heading"] for section in listed),
            "kinds": kinds(str(about)) if about is not None else []}


def kind(of_class: str) -> dict:
    """Return the name and the description of a kind of records from the catalogue record."""
    base = URIRef(settings()["base"])
    found = documents.public(records.graph([str(base)]))
    for part in found.objects(base, VOID.classPartition):
        if str(found.value(part, VOID["class"])) == of_class:
            return {"name": str(found.value(part, SDO.name) or ""), "description": text(found.value(part, SDO.description))}
    return {"name": "", "description": ""}


def kind_names() -> dict[str, str]:
    """Return the names of the kinds of records from the catalogue record, such as "Case Studies" for casestudies.
    Name a kind without a name by its path."""
    base = URIRef(settings()["base"])
    found = documents.public(records.graph([str(base)]))
    named = {}
    for part in found.objects(base, VOID.classPartition):
        named[str(found.value(part, VOID["class"]))] = str(found.value(part, SDO.name) or "")
    return {path: named.get(of_class) or path.capitalize() for path, of_class in settings()["kinds"].items()}


def listing(path: str, arguments, size: int = LISTED) -> dict:
    """Return one page of *size* records of a kind, found by name and filtered by the filter fields, with the values
    of these fields and their counts."""
    of_class = settings()["kinds"][path]
    given = {"search": arguments.get("search", "").strip()}
    browsed = []
    for field in fields(of_class):
        if records.browsed(field):
            browsed.append(field)
            given[field["name"]] = arguments.getlist(field["name"])
    number = max(arguments.get("page", 1, type=int), 1)
    total, iris = records.page(of_class, records.filters(of_class, given), given["search"], (number - 1) * size, size)
    found = documents.public(records.graph(iris))
    listed = []
    for iri in iris:
        listed.append({"address": iri, "name": str(found.value(URIRef(iri), SDO.name) or iri), "description": text(found.value(URIRef(iri), SDO.description))})
    counts = records.counted(of_class, given)
    filters = []
    for field in browsed:
        values = [value for value in counts[field["name"]] if value["count"] or value["value"] in given[field["name"]]]
        if values:
            filters.append({"name": field["name"], "label": field["label"], "values": values})
    query = [(name, value) for name in arguments for value in arguments.getlist(name) if name != "page"]
    return {**kind(of_class), "path": path, "search": given["search"], "chosen": given, "filters": filters, "listed": listed,
            "total": total, "page": number, "pages": (total + size - 1) // size, "query": query}



def items(iris: list[str]) -> list[dict]:
    """Return the items of a listing page, such as the training materials, with the linked tools and methods and
    the authors of each item."""
    found = documents.public(records.graph(iris))
    linked = set()
    for iri in iris:
        for predicate in (SDO.mentions, SDO.author):
            linked.update(str(value) for value in found.objects(URIRef(iri), predicate))
    names = records.names(sorted(linked))
    listed = []
    for iri in iris:
        node = URIRef(iri)
        named = {}
        for predicate in (SDO.mentions, SDO.author):
            named[predicate] = sorted(({"address": str(value), "name": names.get(str(value), str(value))} for value in found.objects(node, predicate)), key=by_name)
        listed.append({"address": iri, "name": str(found.value(node, SDO.name) or iri), "description": text(found.value(node, SDO.description)),
                       "kinds": sorted(str(value) for value in found.objects(node, SDO.learningResourceType)),
                       "url": str(found.value(node, SDO.url) or ""), "published": str(found.value(node, SDO.datePublished) or ""),
                       "videos": videos(found, node, SDO.video), "mentions": named[SDO.mentions], "authors": named[SDO.author]})
    return listed

def partners(found: Graph, node) -> list[dict]:
    """Return the partners of an organisation, sorted by role and name, and then the co-funders, sorted by name."""
    held = []
    for role in found.objects(node, SDO.member):
        held.append((str(found.value(role, SDO.roleName) or ""), str(found.value(role, SDO.member) or "")))
    funders = sorted(str(funder) for funder in found.objects(node, SDO.funder))
    organisations = documents.public(records.graph([iri for _, iri in held] + funders))
    listed = []
    for role, iri in held + [("", funder) for funder in funders]:
        organisation = URIRef(iri)
        listed.append({"role": role, "name": str(organisations.value(organisation, SDO.name) or iri), "address": iri,
                       "logo": str(organisations.value(organisation, SDO.logo) or ""), "url": str(organisations.value(organisation, SDO.url) or "")})
    partnered = sorted([one for one in listed if one["role"]], key=lambda one: (one["role"], by_name(one)))
    return partnered + sorted([one for one in listed if not one["role"]], key=by_name)


def catalogue_of(record: Record) -> dict:
    """Return the content of the home page from the catalogue record of the platform."""
    found = documents.public(records.graph([record.iri]))
    node = URIRef(record.iri)
    paths = {}
    for name, of_class in settings()["kinds"].items():
        paths[of_class] = name
    kinds = []
    for part in in_order(found, found.objects(node, VOID.classPartition)):
        of_class = str(found.value(part, VOID["class"]) or "")
        kinds.append({"name": str(found.value(part, SDO.name) or ""), "description": text(found.value(part, SDO.description)),
                      "address": "/" + paths.get(of_class, ""), "count": records.page(of_class, {}, "", 0, 1)[0] if of_class in paths else 0})
    listed = sorted(str(page) for page in found.objects(node, SDO.subjectOf))
    names = records.names(listed)
    publisher = found.value(node, SDO.publisher)
    held = documents.public(records.graph([str(publisher)])) if publisher is not None else Graph()
    return {"name": str(found.value(node, SDO.name) or ""), "heading": str(found.value(node, SDO.alternateName) or ""),
            "abstract": str(found.value(node, SDO.abstract) or ""), "description": text(found.value(node, SDO.description)), "kinds": kinds,
            "pages": [{"address": page, "name": names.get(page, page)} for page in listed],
            "elsewhere": sorted(str(address) for address in held.objects(publisher, SDO.sameAs)) if publisher is not None else [],
            "email": str(held.value(publisher, SDO.email) or "") if publisher is not None else "",
            "partners": partners(held, publisher) if publisher is not None else []}


# For the pages and listings of the tools, methods, data and models (templates/tools, templates/methods,
# templates/data), the records are converted to the form of the cloud catalogue that was read before.
SPDX = "https://spdx.org/licenses/"
RSD = "https://research-software-directory.org/software/"


def plain(value) -> str:
    """Return the text of a value without HTML tags."""
    if isinstance(value, Literal) and value.datatype == RDF.HTML:
        return Markup(str(value)).striptags()
    return str(value) if value is not None else ""


def local(address: str) -> str:
    """Return a platform address as a path on this server (/tools/aopwiki), so that the link is valid on each copy of
    the platform. Keep other addresses."""
    path = records.path(address)
    return address if path == address else "/" + path


def addresses(found: Graph, node, path) -> list[str]:
    """Return the values of a field as sorted texts."""
    return sorted(str(value) for value in found.objects(node, path))


def named(found: Graph, node, path) -> list[str]:
    """Return the texts of a field and the names of its linked records, in order, without links that have no name."""
    listed = []
    for value in in_order(found, found.objects(node, path)):
        if isinstance(value, Literal):
            listed.append(plain(value))
        elif found.value(value, SDO.name) is not None:
            listed.append(str(found.value(value, SDO.name)))
    return listed


def after(listed: list[str], prefix: str) -> str:
    """Return the end of the first address that starts with the prefix, such as the identifier of a bio.tools
    address."""
    for address in listed:
        if address.startswith(prefix):
            return address.removeprefix(prefix)
    return ""


def parts_of(found: Graph, node, path) -> list[dict]:
    """Return the web pages or the videos of a field, with their titles and addresses, in order."""
    listed = []
    for part in in_order(found, found.objects(node, path)):
        listed.append({"title": str(found.value(part, SDO.name) or ""), "url": local(str(found.value(part, SDO.url) or found.value(part, SDO.embedUrl) or ""))})
    return listed


def dois(found: Graph, node) -> list[str]:
    """Return the DOIs of the publications cited by a record, such as 10.1089/aivt.2021.0010. Keep a citation in
    text as it is written."""
    cited = list(found.objects(node, SDO.citation))
    held = documents.public(records.graph([str(value) for value in cited if isinstance(value, URIRef)]))
    listed = []
    for value in cited:
        if isinstance(value, Literal):
            listed.append(str(value))
        for address in [*held.objects(value, SDO.identifier), *held.objects(value, SDO.sameAs)]:
            doi = str(address).partition("doi.org/")[2]
            if doi and doi not in listed:
                listed.append(doi)
    return listed


def platform_publisher() -> URIRef:
    """Return the publisher of the platform, which hosts the tools marked as hosted by VHP."""
    return URIRef((void.platform()["publisher"] or {}).get("@id", ""))


def steps() -> dict[str, dict]:
    """Return the process flow steps of the glossary by address, each with a label, an anchor and a description."""
    return {step["iri"]: step for step in kinds(settings()["terms"]["processFlowStep"])}


def tool_details(record: Record) -> dict:
    """Return a tool in the form of a service of the cloud catalogue (service/<id>.json). Show a tool offered by the
    publisher of the platform as hosted by VHP, with its website as the instance address unless another address is
    given."""
    found = documents.public(records.with_names(records.graph([record.iri])))
    node = URIRef(record.iri)
    by = platform_publisher()
    hosted = by in found.objects(node, SDO.provider)
    url = local(str(found.value(node, SDO.url) or ""))
    licences = addresses(found, node, SDO.license)
    instance = {"url": local(str(found.value(node, SDO.installUrl) or "")) or (url if hosted else ""), "vhp-platform": "Development" if hosted else "",
                "version": str(found.value(node, SDO.softwareVersion) or ""), "license": after(licences, SPDX) or ", ".join(named(found, node, SDO.license)),
                "source": [local(address) for address in addresses(found, node, SDO.isBasedOn)],
                "docker": [local(address) for address in addresses(found, node, SDO.downloadUrl)]}
    elsewhere = addresses(found, node, SDO.sameAs)
    wikipedia = [address for address in elsewhere if "wikipedia.org/" in address]
    codes = {}
    for flag, path in QUESTIONS.items():
        codes[records.address(path)] = flag.removeprefix("reg_q_")
    asked = {}
    for question in addresses(found, node, URIRef(settings()["terms"]["regulatoryQuestion"])):
        if question in codes:
            asked[codes[question]] = "true"
    # The organisations other than the publisher are named, else the publisher.
    others = [str(found.value(value, SDO.name) or value) for value in found.objects(node, SDO.provider) if value != by]
    return {"id": record.iri.rsplit("/", 1)[-1], "service": str(found.value(node, SDO.name) or ""), "description": plain(found.value(node, SDO.description)),
            "url": url, "screenshot": local(str(found.value(node, SDO.image) or "")),
            "developed-by-VHP": "true" if by in found.objects(node, SDO.creator) else "",
            "instance": {key: value for key, value in instance.items() if value},
            "stage": addresses(found, node, URIRef(settings()["terms"]["processFlowStep"])), "regulatory-question": asked,
            "Other": {"wikipedia": wikipedia[0] if wikipedia else "", "rsd": after(elsewhere, RSD)},
            "ELIXIR": {"tess": str(found.value(node, SDO.keywords) or ""), "biotools": after(elsewhere, "https://bio.tools/")},
            "doi": (dois(found, node) or [""])[0], "intro": parts_of(found, node, SDO.softwareHelp), "workflow": parts_of(found, node, SDO.subjectOf),
            "peertube": parts_of(found, node, SDO.video),
            "provider": {"name": ", ".join(sorted(others) or named(found, node, SDO.provider)),
                         "contact": {"name": ", ".join(named(found, node, SDO.maintainer))}}}


def method_json(record: Record) -> dict:
    """Return a method in the form of a method of the cloud catalogue (methods/<id>.json), with the kind of assay as
    its type and as its ontology term. Of several kinds, use the last by address."""
    found = documents.public(records.with_names(records.graph([record.iri])))
    node = URIRef(record.iri)
    known = steps()
    labels = []
    for stage in addresses(found, node, URIRef(settings()["terms"]["processFlowStep"])):
        labels.append(known[stage]["label"] if stage in known else stage)
    types = addresses(found, node, SDO.additionalType)
    return {"method": str(found.value(node, SDO.name) or ""), "method_description_content": plain(found.value(node, SDO.description)),
            "vendor_content": ", ".join(named(found, node, SDO.provider)), "catalog_number_content": str(found.value(node, SDO.identifier) or ""),
            "catalog_webpage_url": local(str(found.value(node, SDO.url) or "")), "sop": local((addresses(found, node, SDO.subjectOf) or [""])[0]),
            "type_content": (types or [""])[-1], "ontology_term_content": (types or [""])[-1], "citation_content": (dois(found, node) or [""])[0],
            "timestamp": record.updated_at or "", "vhp4safety_workflow_stage_content": ", ".join(labels),
            "workflow_substage_content": ", ".join(named(found, node, SDO.about)), "data_producer_content": ", ".join(named(found, node, SDO.creator)),
            "relevant_vhp4safety_regulatory_question(s)_content": ", ".join(named(found, node, URIRef(settings()["terms"]["regulatoryQuestion"])))}


@lru_cache(maxsize=8)
def catalogue_filters(path: str, latest: str) -> dict:
    """Return the values of the filters of the tools, methods or data listing.

    The values are the process flow steps and the case-study questions of the records, with their explanations. Each
    question has its case study, address and open steps. Cache the values until a record is changed (*latest*,
    records.latest_change())."""
    every = records.counted(settings()["kinds"][path], {"search": ""})
    labels = {}
    explained = {}
    for step in steps().values():
        labels[step["iri"]] = step["label"]
        explained[step["label"]] = step["description"]
    stages = sorted(labels.get(value["value"], value["value"]) for value in every["processFlowStep"] if value["count"])
    if "Other" in stages:
        stages.remove("Other")
        stages.append("Other")
    questions = {}
    for value in every["regulatoryQuestion"]:
        if value["count"]:
            questions[value["name"]] = value["value"]
    held = records.graph(list(questions.values()))
    parts = records.graph([str(step) for step in held.objects(None, SDO.step)])
    texts = {}
    names = {}
    opened = {}
    for name, iri in questions.items():
        texts[name] = str(held.value(URIRef(iri), SDO.text) or "")
        names[iri] = name
        opened[iri] = []
        # The steps of a question that are not greyed out are opened by their process flow step.
        for step in held.objects(URIRef(iri), SDO.step):
            if str(parts.value(step, SDO.creativeWorkStatus) or "") != "disabled" and str(parts.value(step, SDO.additionalType)) in labels:
                opened[iri].append(labels[str(parts.value(step, SDO.additionalType))].lower())
    cases = {}
    for question in records.kept(list(questions.values())):
        if question.part_of:
            cases[question.iri] = question.part_of
    return {"stages": stages, "stage_explanations": explained, "reg_questions": questions, "reg_question_explanations": texts,
            "reg_question_cases": {name: cases.get(iri, "").rsplit("/", 1)[-1] for name, iri in questions.items()},
            "case_studies": sorted({case.rsplit("/", 1)[-1] for case in cases.values()}), "steps": {label: iri for iri, label in labels.items()},
            "cases": cases, "reg_q_labels": names, "reg_q_urls": {iri: "/" + records.path(iri) for iri in names}, "reg_q_steps": opened}


def filtered(path: str, arguments, size: int = LISTED) -> tuple[dict, dict]:
    """Return one page of a listing and the values of its filters.

    Read the filters by label of the cloud catalogue listings (stage, case_study and reg_q) as filters of the
    process flow steps, the case studies and the case-study questions. Use the case studies only if they are named
    in the records. Keep the filters of the other fields."""
    filters = catalogue_filters(path, records.latest_change())
    chosen = arguments.copy()
    chosen.setlist("processFlowStep", arguments.getlist("processFlowStep") + [filters["steps"].get(stage, stage) for stage in arguments.getlist("stage")])
    asked = [filters["reg_questions"][name] for name in arguments.getlist("reg_q") if name in filters["reg_questions"]]
    studies = sorted({case for case in filters["cases"].values() if case.rsplit("/", 1)[-1].title() in arguments.getlist("case_study")})
    given = [field["name"] for field in fields(settings()["kinds"][path])]
    if arguments.getlist("case_study") and "isPartOf" in given:
        chosen.setlist("isPartOf", arguments.getlist("isPartOf") + (studies or [""]))
    elif arguments.getlist("case_study"):
        within = [iri for iri, case in filters["cases"].items() if case in studies]
        asked = [iri for iri in asked if iri in within] if arguments.getlist("reg_q") else within
    # If no question fits the filters, a value of no record is requested, so that no record is found.
    if (arguments.getlist("reg_q") or (arguments.getlist("case_study") and "isPartOf" not in given)) and not asked:
        asked = [""]
    chosen.setlist("regulatoryQuestion", arguments.getlist("regulatoryQuestion") + asked)
    return listing(path, chosen, size), filters


def catalogue_listing(path: str, arguments) -> dict:
    """Return one page of the tools or the methods, in the form of the cloud catalogue listing."""
    found, filters = filtered(path, arguments)
    shown = documents.public(records.graph([item["address"] for item in found["listed"]]))
    by = platform_publisher()
    listed = []
    for item in found["listed"]:
        node = URIRef(item["address"])
        hosted = by in shown.objects(node, SDO.provider)
        url = local(str(shown.value(node, SDO.url) or ""))
        run = local(str(shown.value(node, SDO.installUrl) or "")) or (url if hosted else "")
        listed.append({"id": item["address"].rsplit("/", 1)[-1], "service": item["name"], "description": plain(shown.value(node, SDO.description)),
                       "png": local(str(shown.value(node, SDO.image) or "")), "inst_url": run or "no_url", "main_url": url or "no_url",
                       "vhp_deved": by in shown.objects(node, SDO.creator), "vhp_hosted": hosted,
                       "meta_data": "/" + records.path(item["address"]) + ".md"})
    return {**filters, path: listed, "selected_stages": arguments.getlist("stage"), "selected_case_studies": arguments.getlist("case_study"),
            "selected_questions": arguments.getlist("reg_q"), "page": found["page"], "page_size": LISTED, "total": found["total"],
            "has_prev": found["page"] > 1, "has_next": found["page"] < found["pages"], "search_query": found["search"]}


def dataset(found: Graph, node, known: dict) -> dict:
    """Return a dataset in the form of a BioStudies study or a Zenodo record, as used by the data pages of the cloud
    catalogue. Take the kind from the source record and the names of the process flow steps from *known* (steps()).
    The RO-Crate is the RO-Crate of the record."""
    source = str(found.value(node, SDO.isBasedOn) or "")
    type_of = "study" if "/biostudies/" in source else "dataset"
    doi_url = ([address for address in addresses(found, node, SDO.identifier) + addresses(found, node, SDO.sameAs) if "doi.org/" in address] or [""])[0]
    published = str(found.value(node, SDO.datePublished) or "")
    metadata = {"case_study": [case.rsplit("/", 1)[-1] for case in addresses(found, node, SDO.isPartOf)],
                "regulatory_question": addresses(found, node, URIRef(settings()["terms"]["regulatoryQuestion"])),
                "flow_step": [known[stage]["label"] if stage in known else stage
                              for stage in addresses(found, node, URIRef(settings()["terms"]["processFlowStep"]))],
                "rocrate_url": "/" + records.path(str(node)) + "/ro-crate-metadata.json", "raw_data": {}, "resource_type": {"type": type_of},
                "publication_date": published}
    return {"id": str(node).rsplit("/", 1)[-1], "accession": str(node).rsplit("/", 1)[-1], "type": type_of, "title": str(found.value(node, SDO.name) or ""),
            "release_date": published, "doi": doi_url.partition("doi.org/")[2], "doi_url": doi_url, "url": local(source), "metadata": metadata, "links": {},
            "parsed_metadata": {}}


def data_listing(arguments) -> dict:
    """Return one page of the datasets, in the form of the data listing of the cloud catalogue.

    Half of the page has BioStudies studies, and half has Zenodo records. Each half has the most recent records first."""
    every = arguments.copy()
    every.pop("page", None)
    # All records found are read at once, as the studies and the Zenodo records are paged separately.
    found, filters = filtered("data", every, records.page(settings()["kinds"]["data"], {}, "", 0, 1)[0] or 1)
    shown = documents.public(records.graph([item["address"] for item in found["listed"]]))
    known = steps()
    listed = []
    for item in found["listed"]:
        listed.append(dataset(shown, URIRef(item["address"]), known))
    listed.sort(key=itemgetter("release_date"), reverse=True)
    number = max(arguments.get("page", 1, type=int), 1)
    half = LISTED // 2
    first = (number - 1) * half
    studies = [one for one in listed if one["type"] == "study"]
    datasets = [one for one in listed if one["type"] == "dataset"]
    chosen = arguments.getlist("case_study") + arguments.getlist("reg_q") + arguments.getlist("stage")
    return {**filters, "studies": studies[first:first + half], "datasets": datasets[first:first + half], "total": len(listed), "page": number,
            "page_size": LISTED, "search_query": found["search"], "collection_name": (void.platform()["publisher"] or {}).get("name", ""), "errors": {},
            "has_next": first + half < max(len(studies), len(datasets)), "has_prev": number > 1, "filter_case_study": arguments.getlist("case_study"),
            "filter_regulatory_question": arguments.getlist("reg_q"), "filter_flow_step": arguments.getlist("stage"), "filters_applied": bool(chosen),
            "hits_returned": len(listed), "pages_fetched": 1, "page_size_met": True, "process_flow_steps": known, "kind": "data"}


def catalogue_details(record: Record) -> dict:
    """Return a dataset or a model in the form of the data pages of the cloud catalogue.

    The page has the authors with their ORCID iDs and affiliations, the grants, and the DOIs of the publications. The
    kind of a model is "model"."""
    found = documents.public(records.with_names(records.graph([record.iri])))
    node = URIRef(record.iri)
    shown = dataset(found, node, steps())
    if record.type != settings()["kinds"]["data"]:
        shown["type"] = kind_of(record.type).lower()
    people = documents.public(records.with_names(records.graph(addresses(found, node, SDO.creator))))
    authors = []
    for person in in_order(found, found.objects(node, SDO.creator)):
        orcid = after(addresses(people, person, SDO.sameAs), "https://orcid.org/")
        authors.append({"name": str(found.value(person, SDO.name) or person), "affiliation": ", ".join(named(people, person, SDO.affiliation)), "orcid": orcid})
    grants = documents.public(records.with_names(records.graph(addresses(found, node, SDO.funding))))
    funding = []
    for grant in in_order(grants, found.objects(node, SDO.funding)):
        funding.append({"funder": ", ".join(named(grants, grant, SDO.funder)) or str(grants.value(grant, SDO.name) or ""),
                        "code": str(grants.value(grant, SDO.identifier) or ""), "url": local(str(grants.value(grant, SDO.url) or ""))})
    description = found.value(node, SDO.description)
    shown["norm_metadata"] = {"type": shown["type"], "id": shown["id"], "ReleaseDate": shown["release_date"],
                              "version": str(found.value(node, SDO.version) or ""),
                              "license": after(addresses(found, node, SDO.license), SPDX) or ", ".join(named(found, node, SDO.license)),
                              "url": shown["url"], "doi": shown["doi"], "doi_url": shown["doi_url"], "title": shown["title"],
                              "description": str(description) if description is not None else "", "publications": [{"doi": doi} for doi in dois(found, node)],
                              "files": files(found, node), "authors": authors, "funding": funding}
    return shown


def files(found: Graph, node) -> list[dict]:
    """Return the files of a dataset (its downloads) or of a model (its digital artifacts), with their addresses and
    sizes, by name."""
    listed = []
    for part in [*found.objects(node, SDO.distribution), *found.objects(node, SDO.hasPart)]:
        address = found.value(part, SDO.contentUrl) or found.value(part, URIRef(documents.expand("pbpk:artifactLocation")))
        if address is None:
            continue
        listed.append({"name": str(found.value(part, SDO.name) or address), "url": str(address), "size": str(found.value(part, SDO.contentSize) or "")})
    return sorted(listed, key=by_name)


def uses(iris: list[str]) -> dict[str, dict]:
    """Return, by address, the case studies, the questions and the process flow steps of the case-study steps that
    use the records at these addresses. Count a record for a step if it is linked from a tool of the step (Tool,
    method or model). The process flow step is the step of the question above the step."""
    studies = [record.iri for record in records.of_kind("casestudies") if record.part_of is None]
    found = records.graph(studies)
    asked = URIRef(settings()["terms"]["regulatoryQuestion"])
    above = {}
    for upper, lower in found.subject_objects(SDO.step):
        above[lower] = upper
    known = steps()
    used = {}
    for iri in iris:
        used[iri] = {"case_study": set(), "regulatory_question": set(), "flow_step": set()}
    for step, tool in found.subject_objects(SDO.tool):
        item = str(found.value(tool, SDO.item) or "")
        if item not in used:
            continue
        held = [step]
        while held[-1] in above and found.value(None, asked, held[-1]) is None:
            held.append(above[held[-1]])
        for study in found.subjects(asked, held[-1]):
            used[item]["case_study"].add(str(study).rsplit("/", 1)[-1])
            used[item]["regulatory_question"].add(str(held[-1]))
            stage = str(found.value(held[-2] if len(held) > 1 else held[-1], SDO.additionalType) or "")
            if stage in known:
                used[item]["flow_step"].add(known[stage]["label"])
    return used


def model_listing(arguments) -> dict:
    """Return one page of the models, in the form of the data listing of the cloud catalogue, with the filters of
    the data listing. Find a model by a filter if a case-study step that uses the model fits the filter. Link the
    Zenodo button to the Zenodo record of the model."""
    filters = catalogue_filters("data", records.latest_change())
    # All the models found by name are read at once, as they are filtered here.
    found = listing("models", MultiDict({"search": arguments.get("search", "")}), records.page(settings()["kinds"]["models"], {}, "", 0, 1)[0] or 1)
    used = uses([item["address"] for item in found["listed"]])
    names = filters["reg_q_labels"]
    shown = documents.public(records.graph([item["address"] for item in found["listed"]]))
    known = steps()
    listed = []
    for item in found["listed"]:
        use = used[item["address"]]
        if arguments.getlist("case_study") and not {case.title() for case in use["case_study"]} & set(arguments.getlist("case_study")):
            continue
        if arguments.getlist("reg_q") and not {names.get(question, "") for question in use["regulatory_question"]} & set(arguments.getlist("reg_q")):
            continue
        if arguments.getlist("stage") and not use["flow_step"] & set(arguments.getlist("stage")):
            continue
        model = dataset(shown, URIRef(item["address"]), known)
        source = str(shown.value(URIRef(item["address"]), SDO.isBasedOn) or "")
        model["metadata"]["resource_type"] = {"type": kind_of(settings()["kinds"]["models"]).lower()}
        model.update(type=kind_of(settings()["kinds"]["models"]).lower(), doi="", doi_url=local(source) if "zenodo.org/" in source else "",
                     links={"archive": model["metadata"]["rocrate_url"]}, parsed_metadata={"is_rocrate": True})
        listed.append(model)
    listed.sort(key=itemgetter("release_date"), reverse=True)
    number = max(arguments.get("page", 1, type=int), 1)
    first = (number - 1) * LISTED
    chosen = arguments.getlist("case_study") + arguments.getlist("reg_q") + arguments.getlist("stage")
    return {**filters, "kind": "models", "studies": [], "datasets": listed[first:first + LISTED], "total": len(listed), "page": number, "page_size": LISTED,
            "search_query": found["search"], "collection_name": (void.platform()["publisher"] or {}).get("name", ""), "errors": {},
            "has_next": first + LISTED < len(listed), "has_prev": number > 1, "filter_case_study": arguments.getlist("case_study"),
            "filter_regulatory_question": arguments.getlist("reg_q"), "filter_flow_step": arguments.getlist("stage"), "filters_applied": bool(chosen),
            "hits_returned": len(listed), "pages_fetched": 1, "page_size_met": True, "process_flow_steps": known}
