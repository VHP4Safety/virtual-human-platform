"""The content of the record pages, the listings and the home page is made here from the stored records. A record
is also given in Markdown (RFC 7763, GitHub variant) for readers of plain text."""

from markdownify import markdownify
from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.namespace import SDO, VOID

from database import records
from database.tables import Record
from linkeddata import documents
from linkeddata.profile import fields, jsonld_name, profile_graph, settings, shape_of

# The name is the heading of a node, and the position sets its order. They are not listed with the fields.
HEADING = {str(SDO.name), str(SDO.position)}
# A text in HTML, or a text longer than this, is shown as paragraphs. Other values are shown as a list.
SHORT = 160
# Records on one page of a listing.
LISTED = 12
MEDIA = "text/markdown; charset=utf-8; variant=GFM"


def text(value):
    """A text is prepared for a template. An HTML text is given as {"@value": ...}."""
    if isinstance(value, Literal) and value.datatype == RDF.HTML:
        return {"@value": str(value)}
    return str(value) if value is not None else ""


def kind_of(of_class: str) -> str:
    """The label of a class is read from the profile, such as "Workflow page"."""
    return str(profile_graph().value(shape_of(of_class), RDFS.label) or "")


def in_order(found: Graph, nodes) -> list:
    """Nodes are sorted by position, then by name, then by values. Nodes without a position come last."""
    def place(node):
        try:
            number = float(found.value(node, SDO.position))
        except (TypeError, ValueError):
            number = float("inf")
        return number, str(found.value(node, SDO.name) or ""), sorted(str(value) for value in found.objects(node, None))
    return sorted(nodes, key=place)


def by_name(item: dict) -> str:
    """Items are sorted by name, without regard to case."""
    return item["name"].casefold()


def node_outline(found: Graph, node, names: dict) -> dict:
    """The outline of a node is made from its statements. Each part is given as an outline too."""
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
    """The records that link to a record are found here. They are grouped by the label of the field with the link."""
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
    """The outline of a record is made from its public statements. Private fields are left out."""
    found = documents.public(records.graph([record.iri]))
    links = []
    for value in found.objects():
        if isinstance(value, URIRef):
            links.append(str(value))
    shown = node_outline(found, URIRef(record.iri), records.names(links))
    shown["named_on"] = named_on(record)
    return shown


def markdown_lines(found: dict, level: int) -> list[str]:
    """An outline is written as Markdown blocks. Below the sixth level, a heading is written as a bold line."""
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
    """A record is written in Markdown, with links to its data in other formats and to the licence."""
    found = outline(record)
    lines = markdown_lines(found, 1)
    lines.insert(1, f"<{found['address']}>")
    data = " · ".join(f"[{name}]({address})" for name, address in formats.items())
    lines.append(f"---\n\nData: {data}" + (f"  \nLicence: <{licence}>" if licence else ""))
    return "\n\n".join(lines) + "\n"


def figures(found: Graph, node, path) -> list[dict]:
    """The images of a node are listed with their address and caption."""
    listed = []
    for figure in found.objects(node, path):
        listed.append({"address": str(found.value(figure, SDO.contentUrl) or ""), "caption": str(found.value(figure, SDO.caption) or "")})
    return listed


def videos(found: Graph, node, path) -> list[dict]:
    """The videos of a node are listed with their name and player address."""
    listed = []
    for video in found.objects(node, path):
        listed.append({"name": str(found.value(video, SDO.name) or ""), "player": str(found.value(video, SDO.embedUrl) or "")})
    return listed


def outputs(grant) -> list[dict]:
    """The works funded by a grant, such as publications and data, are listed by name. Organisations and projects
    are left out."""
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
    """The fields named by form:shows are read from the record that a section is about. They are given in the field
    order of the profile."""
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
    """The sections of a node are listed by position. Hidden sections are left out."""
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
    """The kinds of a glossary term are listed with a label, an anchor and a definition. The name of the term is
    removed from each label."""
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
    """The content of a platform page is made from its record."""
    found = documents.public(records.graph([record.iri]))
    node = URIRef(record.iri)
    listed = sections(found, node)
    about = found.value(node, SDO.about)
    return {"name": str(found.value(node, SDO.name) or record.name or ""), "description": str(found.value(node, SDO.description) or ""),
            "sections": listed, "tabbed": any(section["heading"] for section in listed),
            "kinds": kinds(str(about)) if about is not None else []}


def kind(of_class: str) -> dict:
    """The name and the description of a kind of records are read from the catalogue record."""
    base = URIRef(settings()["base"])
    found = documents.public(records.graph([str(base)]))
    for part in found.objects(base, VOID.classPartition):
        if str(found.value(part, VOID["class"])) == of_class:
            return {"name": str(found.value(part, SDO.name) or ""), "description": text(found.value(part, SDO.description))}
    return {"name": "", "description": ""}


def kind_names() -> dict[str, str]:
    """The names of the kinds of records, as the catalogue record gives them, such as "Case Studies" for casestudies.
    A kind without a name is named by its path."""
    base = URIRef(settings()["base"])
    found = documents.public(records.graph([str(base)]))
    named = {}
    for part in found.objects(base, VOID.classPartition):
        named[str(found.value(part, VOID["class"]))] = str(found.value(part, SDO.name) or "")
    return {path: named.get(of_class) or path.capitalize() for path, of_class in settings()["kinds"].items()}


def listing(path: str, arguments) -> dict:
    """One page of the records of a kind is made here. The records are found by name and filtered by the browsed
    fields. The values of these fields are given with their counts."""
    of_class = settings()["kinds"][path]
    given = {"search": arguments.get("search", "").strip()}
    browsed = []
    for field in fields(of_class):
        if records.browsed(field):
            browsed.append(field)
            given[field["name"]] = arguments.getlist(field["name"])
    number = max(arguments.get("page", 1, type=int), 1)
    total, iris = records.page(of_class, records.filters(of_class, given), given["search"], (number - 1) * LISTED, LISTED)
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
            "total": total, "page": number, "pages": (total + LISTED - 1) // LISTED, "query": query}


def partners(found: Graph, node) -> list[dict]:
    """The partners of an organisation are sorted by role and name. The co-funders follow, sorted by name."""
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
    """The content of the home page is made from the catalogue record of the platform."""
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
