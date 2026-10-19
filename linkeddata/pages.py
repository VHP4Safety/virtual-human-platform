"""A page of the platform from its record, for its template (templates/records/page.html): its sections by
position, hidden ones left out, each with its text, figures, videos and items, and the fields it shows of the
record it presents (form:shows) or, for a grant, the records that name it; and the kinds
of a term the page explains, named the glossary's way ("Toxicokinetics (Process Flow Step)"). The platform's
catalogue, for the home page: its kinds of records with their counts, its pages, and its publisher's partners.
A kind's listing: a page of its records, found by name and filtered by its browsable fields, with counts."""

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SDO, VOID

from database import records
from database.tables import Record
from linkeddata import catalogue, documents, fields, outline, storage
from linkeddata.model import settings


def text(value):
    """A text for the template: an HTML text as {"@value": ...}, a plain one as it is."""
    if isinstance(value, Literal) and value.datatype == RDF.HTML:
        return {"@value": str(value)}
    return str(value) if value is not None else ""


def figures(found: Graph, node, path) -> list[dict]:
    listed = []
    for figure in found.objects(node, path):
        listed.append({"address": str(found.value(figure, SDO.contentUrl) or ""), "caption": str(found.value(figure, SDO.caption) or "")})
    return listed


def videos(found: Graph, node, path) -> list[dict]:
    listed = []
    for video in found.objects(node, path):
        listed.append({"name": str(found.value(video, SDO.name) or ""), "player": str(found.value(video, SDO.embedUrl) or "")})
    return listed


def outputs(grant) -> list[dict]:
    """The works that name a grant as their funding, such as publications and data, by name, each with its
    address, name and kind; the projects it funds are left out."""
    if grant is None:
        return []
    holders = set()
    for iri, path in catalogue.naming(str(grant)):
        if path == str(SDO.funding):
            holders.add(iri)
    organisations = catalogue.within(str(SDO.Organization))
    listed = []
    for record in records.kept(sorted(holders)):
        if record.type in organisations:
            continue
        listed.append({"address": record.iri, "name": record.name or record.iri, "kind": outline.kind_of(record.type)})
    listed.sort(key=outline.by_name)
    return listed


def shown(found: Graph, part) -> list[dict]:
    """The fields a section shows (form:shows) of the record it presents, in the order of that record's
    fields: its texts, its figures and players, its named parts as entries, and its links with their names."""
    presented = found.value(part, SDO.about)
    properties = list(found.objects(part, URIRef(settings()["prefixes"]["form"] + "shows")))
    if presented is None or not properties:
        return []
    held = documents.public(storage.with_names(storage.graph([str(presented)])))
    node = URIRef(str(presented))
    positions = {}
    for field in fields.of(str(held.value(node, RDF.type) or "")):
        positions[field["iri"]] = field["position"]

    def place(prop):
        return positions.get(str(prop), (len(positions), "", 0)), str(prop)

    blocks = []
    for prop in sorted(properties, key=place):
        entries = []
        links = []
        for value in outline.in_order(held, held.objects(node, prop)):
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
    """A node's sections by position, hidden ones left out."""
    parts = outline.in_order(found, found.objects(node, SDO.hasPart))
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
    """The kinds of a term, by address, each with its label without the term's name, an anchor and its
    definition."""
    found = records.kinds_of(term)
    statements = storage.graph([kind.iri for kind in found])
    listed = []
    for kind in found:
        label = kind.name.rsplit(" (", 1)[0]
        descriptions = documents.stored_values(statements, kind.iri, "description")
        listed.append({"iri": kind.iri, "label": label, "slug": label.lower().replace(" ", "-"),
                       "description": descriptions[0] if descriptions else ""})
    return listed


def page(record: Record) -> dict:
    found = documents.public(storage.graph([record.iri]))
    node = URIRef(record.iri)
    listed = sections(found, node)
    about = found.value(node, SDO.about)
    return {"name": str(found.value(node, SDO.name) or record.name or ""), "description": str(found.value(node, SDO.description) or ""),
            "sections": listed, "tabbed": any(section["heading"] for section in listed),
            "kinds": kinds(str(about)) if about is not None else []}


# Records on a page of a kind's listing.
LISTED = 12


def kind(of_class: str) -> dict:
    """A kind's name and description, from the platform's catalogue."""
    base = URIRef(settings()["base"])
    found = documents.public(storage.graph([str(base)]))
    for part in found.objects(base, VOID.classPartition):
        if str(found.value(part, VOID["class"])) == of_class:
            return {"name": str(found.value(part, SDO.name) or ""), "description": text(found.value(part, SDO.description))}
    return {"name": "", "description": ""}


def listing(path: str, arguments) -> dict:
    """A kind's page of records (*arguments*: search, page, and values of browsed fields by their names),
    with the values of the browsed fields that find records or are chosen, and their counts."""
    of_class = settings()["kinds"][path]
    given = {"search": arguments.get("search", "").strip()}
    browsed = []
    for field in fields.of(of_class):
        if catalogue.browsed(field):
            browsed.append(field)
            given[field["name"]] = arguments.getlist(field["name"])
    number = max(arguments.get("page", 1, type=int), 1)
    total, iris = catalogue.page(of_class, catalogue.filters(of_class, given), given["search"], (number - 1) * LISTED, LISTED)
    found = documents.public(storage.graph(iris))
    listed = []
    for iri in iris:
        listed.append({"address": iri, "name": str(found.value(URIRef(iri), SDO.name) or iri), "description": text(found.value(URIRef(iri), SDO.description))})
    counts = catalogue.counted(of_class, given)
    filters = []
    for field in browsed:
        shown = [value for value in counts[field["name"]] if value["count"] or value["value"] in given[field["name"]]]
        if shown:
            filters.append({"name": field["name"], "label": field["label"], "values": shown})
    query = [(name, value) for name in arguments for value in arguments.getlist(name) if name != "page"]
    return {**kind(of_class), "path": path, "search": given["search"], "chosen": given, "filters": filters, "listed": listed,
            "total": total, "page": number, "pages": (total + LISTED - 1) // LISTED, "query": query}


def by_role(partner: dict) -> tuple:
    """A partner's place: by its role, then by its name."""
    return partner["role"], outline.by_name(partner)


def partners(found: Graph, node) -> list[dict]:
    """A project's partners by role and name, then its co-funders by name; each with its name, logo and website."""
    held = []
    for role in found.objects(node, SDO.member):
        held.append((str(found.value(role, SDO.roleName) or ""), str(found.value(role, SDO.member) or "")))
    funders = sorted(str(funder) for funder in found.objects(node, SDO.funder))
    organisations = documents.public(storage.graph([iri for _, iri in held] + funders))
    listed = []
    for role, iri in held + [("", funder) for funder in funders]:
        organisation = URIRef(iri)
        listed.append({"role": role, "name": str(organisations.value(organisation, SDO.name) or iri), "address": iri,
                       "logo": str(organisations.value(organisation, SDO.logo) or ""), "url": str(organisations.value(organisation, SDO.url) or "")})
    partnered = sorted([one for one in listed if one["role"]], key=by_role)
    return partnered + sorted([one for one in listed if not one["role"]], key=outline.by_name)


def catalogue_of(record: Record) -> dict:
    """The platform's catalogue: its names, sentence and description, its kinds of records in order with their
    counts and addresses, the pages about it, and its publisher's addresses elsewhere and partners."""
    found = documents.public(storage.graph([record.iri]))
    node = URIRef(record.iri)
    paths = {}
    for name, of_class in settings()["kinds"].items():
        paths[of_class] = name
    kinds = []
    for part in outline.in_order(found, found.objects(node, VOID.classPartition)):
        of_class = str(found.value(part, VOID["class"]) or "")
        kinds.append({"name": str(found.value(part, SDO.name) or ""), "description": text(found.value(part, SDO.description)),
                      "address": "/" + paths.get(of_class, ""), "count": catalogue.page(of_class, {}, "", 0, 1)[0] if of_class in paths else 0})
    listed = sorted(str(page) for page in found.objects(node, SDO.subjectOf))
    names = records.names(listed)
    publisher = found.value(node, SDO.publisher)
    held = documents.public(storage.graph([str(publisher)])) if publisher is not None else Graph()
    return {"name": str(found.value(node, SDO.name) or ""), "heading": str(found.value(node, SDO.alternateName) or ""),
            "abstract": str(found.value(node, SDO.abstract) or ""), "description": text(found.value(node, SDO.description)), "kinds": kinds,
            "pages": [{"address": page, "name": names.get(page, page)} for page in listed],
            "elsewhere": sorted(str(address) for address in held.objects(publisher, SDO.sameAs)) if publisher is not None else [],
            "email": str(held.value(publisher, SDO.email) or "") if publisher is not None else "",
            "partners": partners(held, publisher) if publisher is not None else []}
