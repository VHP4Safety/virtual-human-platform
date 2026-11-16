"""Content of the record pages, the listings and the home page."""

import re
from functools import lru_cache
from operator import itemgetter
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify
from markupsafe import Markup
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SDO, VOID
from rdfsolve.iris import local_name
from werkzeug.datastructures import MultiDict

from database import records
from database.tables import Record
from linkeddata import documents, void
from linkeddata.parsers import QUESTIONS
from linkeddata.profile import fields, jsonld_name, readable, settings, shape_fields

# The name is used as the heading of a node, and the position for its order. Neither is listed with the fields.
HEADING = {str(SDO.name), str(SDO.position)}
# A text in HTML, or a text longer than this, is shown as paragraphs. Other values are shown as a list.
SHORT = 160
# A text with a tag of markup is a text in HTML, also when it is stored as a plain text.
MARKUP = re.compile(r"<[a-zA-Z][a-zA-Z0-9]*(\s[^<>]*)?/?>")
# Records on one page of a listing.
LISTED = 12
# The glossary names each process flow step "<step> (Process Flow Step)". A tool of no step has the stage Other.
# The text of the stage column of the sources for a tool or a method of no process flow step in particular.
OTHER = "Other"
MEDIA = "text/markdown; charset=utf-8; variant=GFM"


def html(value) -> bool:
    """Return True if value is a text in HTML."""
    return isinstance(value, Literal) and (value.datatype == RDF.HTML or bool(MARKUP.search(str(value))))


def text(value):
    """Return a text value for a template, with an HTML text as a dict with @value."""
    if html(value):
        return {"@value": str(value)}
    return str(value) if value is not None else ""


def kind_of(of_class: str) -> str:
    """Return the name of the kind of of_class, or the name of of_class, such as Research project or Computer language."""
    return settings()["labels"].get(of_class) or (readable(local_name(of_class)) if of_class else "")


def in_order(found: Graph, nodes) -> list:
    """Return nodes sorted by position, then by name."""
    def place(node):
        try:
            number = float(found.value(node, SDO.position))
        except (TypeError, ValueError):
            number = float("inf")
        return number, str(found.value(node, SDO.name) or ""), sorted(str(value) for value in found.objects(node, None))
    return sorted(nodes, key=place)


def members(found: Graph, node, path) -> list:
    """Return the values of a field of node in their order."""
    values = list(found.objects(node, path))
    heads = [value for value in values if (value, RDF.first, None) in found]
    if heads:
        return [member for head in heads for member in Collection(found, head)]
    return in_order(found, values)


def by_name(item: dict) -> str:
    """Return the name of item in lower case, for sorting."""
    return item["name"].casefold()


def node_outline(found: Graph, node, names: dict, shape: str = "") -> dict:
    """Return the outline of node, by the fields of shape or else of its class, with an outline for each part."""
    of_class = records.class_of(found, node)
    shown = {"address": None if records.is_part(found, node) else str(node), "name": str(found.value(node, SDO.name) or ""),
             "kind": kind_of(of_class), "fields": [], "parts": []}
    given = shape_fields(shape) if shape else fields(of_class)
    # A value of a property without a field, such as a value kept from an import, is shown after the fields.
    known = {field["iri"] for field in given} | {str(RDF.type)}
    for path in sorted({str(predicate) for predicate in found.predicates(node, None)} - known):
        given = [*given, {"name": jsonld_name(path), "iri": path, "label": readable(local_name(path)), "shown": True, "addressed": [],
                          "parts": {}, "node": "", "section": ""}]
    for field in given:
        values = members(found, node, URIRef(field["iri"]))
        if field["iri"] in HEADING or not values or not field["shown"]:
            continue
        listed = any((value, RDF.first, None) in found for value in found.objects(node, URIRef(field["iri"])))
        # A node without an address is shown as a part, also in a field of links, such as a named input. A list holds parts
        # or links, so the members that are parts are found one by one. A value with an address is a part only in a field of
        # parts with addresses, such as the steps of a case-study question, and a link or a text in any other field.
        parts = [value for value in values if (field["addressed"] and not listed and isinstance(value, URIRef)) or records.is_part(found, value)]
        if parts:
            items = [node_outline(found, part, names, field["parts"].get(str(found.value(part, RDF.type)), field["node"])) for part in parts]
            shown["parts"].append({"label": field["label"], "items": items})
        values = [value for value in values if value not in parts]
        if not values:
            continue
        if not listed:
            values.sort(key=str)
        given = []
        long = False
        for value in values:
            if isinstance(value, Literal):
                given.append({"text": str(value), "html": html(value)})
                if html(value) or len(str(value)) > SHORT:
                    long = True
            else:
                given.append({"link": str(value), "name": names.get(str(value)) or str(value)})
        shown["fields"].append({"name": field["name"], "label": field["label"], "values": given, "long": long, "section": field["section"]})
    return shown


def named_on(record: Record) -> dict[str, list[dict]]:
    """Return the records that link to record, by field label."""
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
            found.setdefault(labels.get(path) or readable(local_name(path)), []).append(
                {"address": other.iri, "name": other.name or other.iri, "kind": kind_of(other.type)})
    for listed in found.values():
        listed.sort(key=by_name)
    return found


def outline(record: Record) -> dict:
    """Return the outline of record without private fields."""
    found = documents.without_private(records.graph([record.iri]))
    links = []
    for value in found.objects():
        if isinstance(value, URIRef):
            links.append(str(value))
    shown = node_outline(found, URIRef(record.iri), records.names(links))
    shown["named_on"] = named_on(record)
    return shown


def markdown_lines(found: dict, level: int) -> list[str]:
    """Return an outline as Markdown lines."""
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
    """Return record in Markdown, with links to its other formats."""
    found = outline(record)
    lines = markdown_lines(found, 1)
    lines.insert(1, f"<{found['address']}>")
    data = " · ".join(f"[{name}]({address})" for name, address in formats.items())
    lines.append(f"---\n\nData: {data}" + (f"  \nLicence: <{licence}>" if licence else ""))
    return "\n\n".join(lines) + "\n"


def figures(found: Graph, node, path) -> list[dict]:
    """Return the images of a field of node, with address and caption."""
    listed = []
    for figure in found.objects(node, path):
        listed.append({"address": str(found.value(figure, SDO.contentUrl) or ""), "caption": str(found.value(figure, SDO.caption) or "")})
    return listed


def videos(found: Graph, node, path) -> list[dict]:
    """Return the videos of a field of node, with name and player address."""
    listed = []
    for video in found.objects(node, path):
        listed.append({"name": str(found.value(video, SDO.name) or ""), "player": str(found.value(video, SDO.embedUrl) or "")})
    return listed


def outputs(grant) -> list[dict]:
    """Return the works funded by grant, without organisations and projects."""
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
    """Return the fields of the record that part is about, as listed by form:shows."""
    presented = found.value(part, SDO.about)
    properties = list(found.objects(part, URIRef(settings()["prefixes"]["form"] + "shows")))
    if presented is None or not properties:
        return []
    held = documents.public(records.with_names(records.graph([str(presented)])))
    node = URIRef(str(presented))
    positions = {}
    for field in fields(records.class_of(held, node)):
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
    """Return the sections of node in order, without hidden sections."""
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
    """Return the kinds of the glossary term term, with label, anchor and definition."""
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
    """Return the content of the platform page record."""
    found = documents.public(records.graph([record.iri]))
    node = URIRef(record.iri)
    listed = sections(found, node)
    about = found.value(node, SDO.about)
    return {"name": str(found.value(node, SDO.name) or record.name or ""), "description": str(found.value(node, SDO.description) or ""),
            "sections": listed, "tabbed": any(section["heading"] for section in listed),
            "kinds": kinds(str(about)) if about is not None else []}


def kind(of_class: str) -> dict:
    """Return the name and description of the kind of_class."""
    base = URIRef(settings()["base"])
    found = documents.public(records.graph([str(base)]))
    for part in found.objects(base, VOID.classPartition):
        if str(found.value(part, VOID["class"])) == of_class:
            return {"name": str(found.value(part, SDO.name) or ""), "description": text(found.value(part, SDO.description))}
    return {"name": "", "description": ""}


def kind_names() -> dict[str, str]:
    """Return the names of the kinds of records, by path."""
    base = URIRef(settings()["base"])
    found = documents.public(records.graph([str(base)]))
    named = {}
    for part in found.objects(base, VOID.classPartition):
        named[str(found.value(part, VOID["class"]))] = str(found.value(part, SDO.name) or "")
    return {path: named.get(of_class) or path.capitalize() for path, of_class in settings()["kinds"].items()}


def listing(path: str, arguments, size: int = LISTED) -> dict:
    """Return one page of records of the kind at path, with the filter counts."""
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
    """Return the listing items of iris, with linked tools, methods and authors."""
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
    """Return the partners and co-funders of an organisation, each by name."""
    members = sorted(str(member) for member in found.objects(node, SDO.member))
    funders = sorted(str(funder) for funder in found.objects(node, SDO.funder))
    organisations = documents.public(records.graph(members + funders))
    listed = []
    for iri in members + funders:
        organisation = URIRef(iri)
        listed.append({"name": str(organisations.value(organisation, SDO.name) or iri), "address": iri,
                       "logo": str(organisations.value(organisation, SDO.logo) or ""), "url": str(organisations.value(organisation, SDO.url) or "")})
    return sorted(listed, key=by_name)


# The partner logo files of the home page, in their order.
PARTNERS = Path(__file__).parent.parent / "static" / "images" / "partners" / "partners.txt"


def partner_order() -> dict[str, int]:
    """Return the place of each partner logo file in partners.txt."""
    order = {}
    for line in PARTNERS.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.strip().startswith("#"):
            order[line.split("|")[0].strip()] = len(order)
    return order


def home_text(value) -> dict:
    """Return the description of the platform in the parts of the home page."""
    soup = BeautifulSoup(value["@value"] if isinstance(value, dict) else f"<p>{value}</p>", "html.parser")
    lead = soup.find("p")
    found = {"lead": lead.decode_contents() if lead else "", "text": "", "parts": []}
    if lead:
        lead.extract()
    for block in soup.contents:
        if getattr(block, "name", None) in ("h2", "h3", "h4", "h5", "h6"):
            found["parts"].append({"title": block.get_text(" ", strip=True), "html": ""})
        elif found["parts"]:
            found["parts"][-1]["html"] += str(block)
        else:
            found["text"] += str(block)
    return found


def catalogue_of(record: Record) -> dict:
    """Return the content of the home page from the platform record."""
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
    order = partner_order()
    placed = {}
    for partner in partners(held, publisher) if publisher is not None else []:
        logo = partner["logo"].rsplit("/", 1)[-1]
        if logo in order:
            placed[order[logo]] = partner
    return {"name": str(found.value(node, SDO.name) or ""), "heading": str(found.value(node, SDO.alternateName) or ""),
            "abstract": str(found.value(node, SDO.abstract) or ""), "description": text(found.value(node, SDO.description)), "kinds": kinds,
            "about": home_text(text(found.value(node, SDO.description))),
            "pages": [{"address": page, "name": names.get(page, page)} for page in listed],
            "elsewhere": sorted(str(address) for address in held.objects(publisher, SDO.sameAs)) if publisher is not None else [],
            # The email of the publisher is the contact address of the platform, shown although the email field of
            # organisations is private.
            "email": str(records.graph([str(publisher)]).value(publisher, SDO.email) or "") if publisher is not None else "",
            "partners": [placed[place] for place in sorted(placed)]}


# The pages and listings of the tools, methods, data and models use the form of the cloud catalogue.
SPDX = "https://spdx.org/licenses/"
RSD = "https://research-software-directory.org/software/"


def plain(value) -> str:
    """Return value without HTML tags."""
    if html(value):
        return Markup(str(value)).striptags()
    return str(value) if value is not None else ""


def local(address: str) -> str:
    """Return a platform address as a path on this server, and other addresses unchanged."""
    path = records.path(address)
    return address if path == address else "/" + path


def addresses(found: Graph, node, path) -> list[str]:
    """Return the values of a field of node as sorted texts."""
    return sorted(str(value) for value in found.objects(node, path))


def named(found: Graph, node, path) -> list[str]:
    """Return the texts and the names of the linked records of a field of node."""
    return names_of(found, found.objects(node, path))


def names_of(found: Graph, values) -> list[str]:
    """Return the texts and the names of the linked records among values, in order."""
    listed = []
    for value in in_order(found, values):
        if isinstance(value, Literal):
            listed.append(plain(value))
        elif found.value(value, SDO.name) is not None:
            listed.append(str(found.value(value, SDO.name)))
    return listed


def after(listed: list[str], prefix: str) -> str:
    """Return the end of the first address in listed that starts with prefix."""
    for address in listed:
        if address.startswith(prefix):
            return address.removeprefix(prefix)
    return ""


def parts_of(found: Graph, node, path) -> list[dict]:
    """Return the pages or videos of a field of node, with titles and addresses."""
    listed = []
    for part in in_order(found, found.objects(node, path)):
        listed.append({"title": str(found.value(part, SDO.name) or ""), "url": local(str(found.value(part, SDO.url) or found.value(part, SDO.embedUrl) or ""))})
    return listed


def dois(found: Graph, node) -> list[str]:
    """Return the DOIs of the publications cited by node."""
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
    """Return the publisher of the platform."""
    return URIRef((void.platform()["publisher"] or {}).get("@id", ""))


def steps() -> dict[str, dict]:
    """Return the process flow steps by address, in their order: the values that the case-study profile allows as the step
    of the process flow of a step of a question, with the label and the definition of their glossary terms."""
    question = next(shape for field in fields(settings()["kinds"]["casestudies"]) for of_class, shape in field["parts"].items() if of_class == str(SDO.HowTo))
    allowed = next(field["values"] for field in shape_fields(question) if field["iri"] == str(SDO.additionalType))
    found = records.graph(allowed)
    listed = {}
    for iri in allowed:
        label = str(found.value(URIRef(iri), SDO.name) or iri).rsplit(" (", 1)[0]
        descriptions = documents.stored_values(found, iri, "description")
        listed[iri] = {"iri": iri, "label": label, "slug": label.lower().replace(" ", "-"), "description": descriptions[0] if descriptions else ""}
    return listed


def stages(found: Graph, node) -> list[str]:
    """Return the process flow steps of node: its keywords that are steps."""
    known = steps()
    return [value for value in addresses(found, node, SDO.keywords) if value in known]


def questions() -> set[str]:
    """Return the regulatory questions: the workflows that the case studies list as their parts."""
    studies = [record.iri for record in records.of_kind("casestudies") if record.part_of is None]
    parts = {str(part) for part in records.graph(studies).objects(None, SDO.hasPart)}
    return {record.iri for record in records.kept(sorted(parts)) if record.type == str(SDO.HowTo)}


def tool_details(record: Record) -> dict:
    """Return record as a service of the cloud catalogue."""
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
    for question in addresses(found, node, SDO.isPartOf):
        if question in codes:
            asked[codes[question]] = "true"
    # The organisations other than the publisher are named, else the publisher.
    others = [str(found.value(value, SDO.name) or value) for value in found.objects(node, SDO.provider) if value != by]
    return {"id": record.iri.rsplit("/", 1)[-1], "service": str(found.value(node, SDO.name) or ""), "description": plain(found.value(node, SDO.description)),
            "url": url, "screenshot": local(str(found.value(node, SDO.image) or "")),
            "developed-by-VHP": "true" if by in found.objects(node, SDO.author) else "",
            "instance": {key: value for key, value in instance.items() if value},
            "stage": stages(found, node), "regulatory-question": asked,
            "Other": {"wikipedia": wikipedia[0] if wikipedia else "", "rsd": after(elsewhere, RSD)},
            "ELIXIR": {"tess": next((str(value) for value in found.objects(node, SDO.keywords) if isinstance(value, Literal) and str(value) != OTHER), ""),
                       "biotools": after(elsewhere, "https://bio.tools/")},
            "doi": (dois(found, node) or [""])[0], "intro": parts_of(found, node, SDO.softwareHelp), "workflow": parts_of(found, node, SDO.subjectOf),
            "peertube": parts_of(found, node, SDO.video),
            "provider": {"name": ", ".join(sorted(others) or named(found, node, SDO.provider)),
                         "contact": {"name": ", ".join(named(found, node, SDO.maintainer))}}}


def method_json(record: Record) -> dict:
    """Return record as a method of the cloud catalogue."""
    found = documents.public(records.with_names(records.graph([record.iri])))
    node = URIRef(record.iri)
    known = steps()
    labels = []
    for stage in stages(found, node):
        labels.append(known[stage]["label"])
    # The keywords other than the steps are the substages, such as key events.
    substages = names_of(found, [value for value in found.objects(node, SDO.keywords) if str(value) not in known])
    types = addresses(found, node, SDO.additionalType)
    return {"method": str(found.value(node, SDO.name) or ""), "method_description_content": plain(found.value(node, SDO.description)),
            "vendor_content": ", ".join(named(found, node, SDO.provider)), "catalog_number_content": str(found.value(node, SDO.identifier) or ""),
            "catalog_webpage_url": local(str(found.value(node, SDO.url) or "")), "sop": local((addresses(found, node, SDO.subjectOf) or [""])[0]),
            "type_content": (types or [""])[-1], "ontology_term_content": (types or [""])[-1], "citation_content": (dois(found, node) or [""])[0],
            "timestamp": record.updated_at or "", "vhp4safety_workflow_stage_content": ", ".join(labels),
            "workflow_substage_content": ", ".join(substages),
            "data_producer_content": ", ".join(named(found, node, SDO.author)),
            "relevant_vhp4safety_regulatory_question(s)_content": ", ".join(named(found, node, SDO.isPartOf))}


@lru_cache(maxsize=8)
def catalogue_filters(path: str, latest: str) -> dict:
    """Return the filter values of the listing at path, cached until latest changes."""
    every = records.counted(settings()["kinds"][path], {"search": ""})
    labels = {}
    explained = {}
    for step in steps().values():
        labels[step["iri"]] = step["label"]
        explained[step["label"]] = step["description"]
    stated = sorted(labels[value["value"]] for value in every["keywords"] if value["count"] and value["value"] in labels)
    asked = questions()
    named_questions = {}
    for value in every["isPartOf"]:
        if value["count"] and value["value"] in asked:
            named_questions[value["name"]] = value["value"]
    held = records.graph(list(named_questions.values()))
    parts = records.graph([str(step) for step in held.objects(None, SDO.step)])
    texts = {}
    names = {}
    opened = {}
    for name, iri in named_questions.items():
        texts[name] = str(held.value(URIRef(iri), SDO.text) or "")
        names[iri] = name
        opened[iri] = []
        # The steps of a question that are not greyed out are opened by their process flow step.
        for step in held.objects(URIRef(iri), SDO.step):
            if str(parts.value(step, SDO.creativeWorkStatus) or "") != "Incomplete" and str(parts.value(step, SDO.additionalType)) in labels:
                opened[iri].append(labels[str(parts.value(step, SDO.additionalType))].lower())
    cases = {}
    for question in records.kept(list(named_questions.values())):
        if question.part_of:
            cases[question.iri] = question.part_of
    return {"stages": stated, "stage_explanations": explained, "reg_questions": named_questions, "reg_question_explanations": texts,
            "reg_question_cases": {name: cases.get(iri, "").rsplit("/", 1)[-1] for name, iri in named_questions.items()},
            "case_studies": sorted({case.rsplit("/", 1)[-1] for case in cases.values()}), "steps": {label: iri for iri, label in labels.items()},
            "cases": cases, "reg_q_labels": names, "reg_q_urls": {iri: "/" + records.path(iri) for iri in names}, "reg_q_steps": opened}


def filtered(path: str, arguments, size: int = LISTED) -> tuple[dict, dict]:
    """Return one page of a listing and the values of its filters."""
    filters = catalogue_filters(path, records.latest_change())
    chosen = arguments.copy()
    chosen.setlist("keywords", arguments.getlist("keywords") + [filters["steps"].get(stage, stage) for stage in arguments.getlist("stage")])
    asked = [filters["reg_questions"][name] for name in arguments.getlist("reg_q") if name in filters["reg_questions"]]
    studies = sorted({case for case in filters["cases"].values() if case.rsplit("/", 1)[-1].title() in arguments.getlist("case_study")})
    # A record of a case study is part of one of its questions, or of the case study itself, as a dataset can be.
    if arguments.getlist("case_study"):
        within = [iri for iri, case in filters["cases"].items() if case in studies]
        asked = [iri for iri in asked if iri in within] if arguments.getlist("reg_q") else within + studies
    # If no question fits the filters, a value of no record is requested, so that no record is found.
    if (arguments.getlist("reg_q") or arguments.getlist("case_study")) and not asked:
        asked = [""]
    chosen.setlist("isPartOf", arguments.getlist("isPartOf") + asked)
    return listing(path, chosen, size), filters


def catalogue_listing(path: str, arguments) -> dict:
    """Return one page of tools or methods as a listing of the cloud catalogue."""
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
                       "vhp_deved": by in shown.objects(node, SDO.author), "vhp_hosted": hosted,
                       "meta_data": "/" + records.path(item["address"]) + ".md"})
    return {**filters, path: listed, "selected_stages": arguments.getlist("stage"), "selected_case_studies": arguments.getlist("case_study"),
            "selected_questions": arguments.getlist("reg_q"), "page": found["page"], "page_size": LISTED, "total": found["total"],
            "has_prev": found["page"] > 1, "has_next": found["page"] < found["pages"], "search_query": found["search"]}


def dataset(found: Graph, node, known: dict) -> dict:
    """Return a dataset as a data page of the cloud catalogue."""
    source = str(found.value(node, SDO.isBasedOn) or "")
    type_of = "study" if "/biostudies/" in source else "dataset"
    doi_url = ([address for address in addresses(found, node, SDO.identifier) + addresses(found, node, SDO.sameAs) if "doi.org/" in address] or [""])[0]
    published = str(found.value(node, SDO.datePublished) or "")
    crate_files = [file for file in files(found, node) if "rocrate" in file["name"].lower().replace("-", "")]
    links, parsed = {}, {}
    if source.startswith("https://zenodo.org/records/"):
        links["archive"] = "https://zenodo.org/api/records/" + source.rstrip("/").rsplit("/", 1)[-1] + "/files-archive"
        parsed["is_rocrate"] = any(file["name"].lower() == "ro-crate-metadata.json" for file in crate_files)
    asked = questions()
    metadata = {"case_study": [case.rsplit("/", 1)[-1] for case in addresses(found, node, SDO.isPartOf) if case not in asked],
                "regulatory_question": [question for question in addresses(found, node, SDO.isPartOf) if question in asked],
                "flow_step": [known[stage]["label"] for stage in stages(found, node)],
                "rocrate_url": crate_files[0]["url"] if crate_files else None, "raw_data": {}, "resource_type": {"type": type_of},
                "publication_date": published}
    return {"id": str(node).rsplit("/", 1)[-1], "accession": str(node).rsplit("/", 1)[-1], "type": type_of, "title": str(found.value(node, SDO.name) or ""),
            "release_date": published, "doi": doi_url.partition("doi.org/")[2], "doi_url": doi_url, "url": local(source), "metadata": metadata, "links": links,
            "parsed_metadata": parsed}


def data_listing(arguments) -> dict:
    """Return one page of datasets as the data listing of the cloud catalogue."""
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
            "hits_returned": len(listed), "pages_fetched": 1, "page_size_met": True, "process_flow_steps": known}


def catalogue_details(record: Record) -> dict:
    """Return a dataset or a model as a data page of the cloud catalogue."""
    found = documents.public(records.with_names(records.graph([record.iri])))
    node = URIRef(record.iri)
    shown = dataset(found, node, steps())
    if record.type != settings()["kinds"]["data"]:
        shown["type"] = kind_of(record.type).lower()
    creators = members(found, node, SDO.creator)
    people = documents.public(records.with_names(records.graph([str(person) for person in creators if isinstance(person, URIRef)])))
    authors = []
    for person in creators:
        orcid = after(addresses(people, person, SDO.sameAs), "https://orcid.org/")
        authors.append({"name": str(found.value(person, SDO.name) or person), "affiliation": ", ".join(named(people, person, SDO.affiliation)), "orcid": orcid})
    grants = documents.public(records.with_names(records.graph(addresses(found, node, SDO.funding))))
    funding = []
    for grant in in_order(grants, found.objects(node, SDO.funding)):
        # The project page of a grant is linked, but not the page of the grant record.
        url = str(grants.value(grant, SDO.url) or "")
        funding.append({"funder": ", ".join(named(grants, grant, SDO.funder)) or str(grants.value(grant, SDO.name) or ""),
                        "acronym": str(grants.value(grant, SDO.alternateName) or ""),
                        "code": str(grants.value(grant, SDO.identifier) or ""), "url": local(url) if url != str(grant) else ""})
    description = found.value(node, SDO.description)
    shown["norm_metadata"] = {"type": shown["type"], "id": shown["id"], "ReleaseDate": shown["release_date"],
                              "version": str(found.value(node, SDO.version) or ""),
                              "license": after(addresses(found, node, SDO.license), SPDX) or ", ".join(named(found, node, SDO.license)),
                              "url": shown["url"], "doi": shown["doi"], "doi_url": shown["doi_url"], "title": shown["title"],
                              "description": str(description) if description is not None else "", "publications": [{"doi": doi} for doi in dois(found, node)],
                              "files": files(found, node), "authors": authors, "funding": funding}
    shown["description"] = plain(description)
    shown["metadata"]["raw_data"] = {"section": design_of(found, node)} if shown["type"] == "study" else {}
    return shown


# Bioschemas draft terms. The experimental design of a study is a LabProtocol part of the dataset.
DRAFT = "https://bioschemas.org/draft_terms/"
SAMPLE_VALUES = URIRef("https://bioschemas.org/terms/additionalProperty")


def attributes_of(found: Graph, node, path) -> list[dict]:
    """Return the values of a field of node as BioStudies attributes, with URL, TermId, Ontology and Unit qualifiers."""
    listed = []
    for item in in_order(found, found.objects(node, path)):
        qualifiers = []
        # A term without a page of its own is linked at its address.
        page = found.value(item, SDO.url) or next((term for term in found.objects(item, SDO.valueReference) if not records.is_part(found, term)), None)
        if page is not None:
            qualifiers.append({"name": "URL", "value": local(str(page))})
        for reference in found.objects(item, SDO.valueReference):
            if records.is_part(found, reference):
                qualifiers.append({"name": str(found.value(reference, SDO.propertyID) or ""), "value": str(found.value(reference, SDO.value) or "")})
            else:
                term = re.split(r"[/#]", str(reference))[-1]
                qualifiers += [{"name": "TermId", "value": term}, {"name": "Ontology", "value": term.split("_")[0]}]
        if found.value(item, SDO.unitText) is not None:
            qualifiers.append({"name": "Unit", "value": str(found.value(item, SDO.unitText))})
        listed.append({"name": str(found.value(item, SDO.propertyID) or ""), "value": str(found.value(item, SDO.value) or ""), "valqual": qualifiers})
    return listed


def section_of(found: Graph, node, kind: str = "") -> dict:
    """Return a part of the experimental design as a BioStudies section, with the sections below it as one table."""
    attributes = attributes_of(found, node, URIRef(DRAFT + "additionalProperty")) + attributes_of(found, node, SAMPLE_VALUES)
    if (node, RDF.type, SDO.ChemicalSubstance) in found:
        attributes = [{"name": "Chemical", "value": str(found.value(node, SDO.name) or ""), "valqual": []}]
        attributes += attributes_of(found, node, SDO.identifier)
    below = members(found, node, SDO.hasPart) + in_order(found, found.objects(node, SDO.subjectOf))
    return {"type": kind or str(found.value(node, SDO.additionalType) or ""), "attributes": attributes,
            "subsections": [[section_of(found, part) for part in below]] if below else []}


def design_of(found: Graph, node) -> dict | None:
    """Return the experimental design of a dataset as BioStudies sections, or None."""
    for design in found.objects(node, SDO.hasPart):
        if (design, RDF.type, URIRef(DRAFT + "LabProtocol")) in found:
            sections = [section_of(found, sample, "Biological model information") for sample in in_order(found, found.objects(design, URIRef(DRAFT + "bioSample")))]
            sections += [section_of(found, chemical, "Chemical information") for chemical in members(found, design, URIRef(DRAFT + "reagent"))]
            sections += [section_of(found, part) for part in members(found, design, SDO.hasPart)]
            return {"attributes": attributes_of(found, design, URIRef(DRAFT + "additionalProperty")), "subsections": sections}
    return None


def files(found: Graph, node) -> list[dict]:
    """Return the files of a dataset or a model, with address, size and checksum."""
    listed = []
    for part in in_order(found, [*found.objects(node, SDO.distribution), *found.objects(node, SDO.hasPart)]):
        address = found.value(part, SDO.contentUrl) or found.value(part, URIRef(documents.expand("pbpk:artifactLocation")))
        if address is None:
            continue
        checksum = found.value(part, URIRef(documents.expand("spdx:checksum")))
        algorithm = str(found.value(checksum, URIRef(documents.expand("spdx:algorithm"))) or "").rsplit("_", 1)[-1] if checksum is not None else ""
        value = str(found.value(checksum, URIRef(documents.expand("spdx:checksumValue"))) or "") if checksum is not None else ""
        listed.append({"name": str(found.value(part, SDO.name) or address), "url": str(address), "size": str(found.value(part, SDO.contentSize) or ""),
                       "checksum": f"{algorithm}:{value}" if value else ""})
    return listed


def uses(iris: list[str]) -> dict[str, dict]:
    """Return the case studies, questions and steps that use each record in iris."""
    studies = [record.iri for record in records.of_kind("casestudies") if record.part_of is None]
    found = records.graph(studies)
    # A case study lists its questions as its parts.
    asked = SDO.hasPart
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


def case_studies() -> list[dict]:
    """Return the address, name, aim and icon of each case study."""
    listed = [record for record in records.of_kind("casestudies") if record.part_of is None]
    statements = records.graph([record.iri for record in listed])
    found = []
    for record in listed:
        aims = documents.stored_values(statements, record.iri, "description")
        icons = documents.stored_values(statements, record.iri, "image")
        found.append({"address": record.iri, "name": record.name, "aim": aims[0] if aims else "", "icon": icons[0] if icons else ""})
    return found


@lru_cache(maxsize=16)
def case_outline(iri: str, latest: str) -> dict:
    """Return the outline of the case study at iri, cached until latest changes."""
    return outline(records.get(iri))


def menu(kind: str) -> list[dict]:
    """Return the identifier, name and page of each record of a kind, sorted by name."""
    listed = []
    for record in records.of_kind(kind):
        if record.part_of is None:
            listed.append({"id": record.iri.rsplit("/", 1)[-1], "title": record.name or record.iri, "url": local(record.iri)})
    listed.sort(key=lambda item: item["title"].lower())
    return listed


def based_on(path: str, address: str) -> list[str]:
    """Return the addresses of the records of the kind at path that are made from the source record at address."""
    return sorted(iri for iri, value in records.values(settings()["kinds"][path], documents.expand("isBasedOn")) if value == address)


def model_listing(search: str, page: int, size: int, filters: list[tuple[str, str]]) -> dict:
    """Return one page of models found by name and by case-study use, as search results of the models page."""
    labels = catalogue_filters("data", records.latest_change())["reg_q_labels"]
    # All the models found by name are read at once, as they are filtered here.
    found = listing("models", MultiDict({"search": search}), records.page(settings()["kinds"]["models"], {}, "", 0, 1)[0] or 1)
    used = uses([item["address"] for item in found["listed"]])
    shown = documents.public(records.graph([item["address"] for item in found["listed"]]))
    known = steps()
    listed = []
    for item in found["listed"]:
        use = used[item["address"]]
        chosen = {"case_study": {case.title() for case in use["case_study"]}, "flow_step": use["flow_step"],
                  "regulatory_question": {labels.get(question, "") for question in use["regulatory_question"]}}
        if any(value not in chosen[field] for field, value in filters):
            continue
        model = dataset(shown, URIRef(item["address"]), known)
        path = "/" + records.path(item["address"])
        model.update(type=kind_of(settings()["kinds"]["models"]).lower(), url=path, meta_data=path + ".md",
                     links={"archive": path + "/ro-crate-metadata.json"})
        listed.append(model)
    listed.sort(key=itemgetter("release_date"), reverse=True)
    first = (page - 1) * size
    return {"hits": listed[first:first + size], "total": len(listed), "filters_applied": bool(filters), "hits_returned": len(listed)}
