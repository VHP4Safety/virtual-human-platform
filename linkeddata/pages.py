"""A page of the platform from its record, for its template (templates/records/page.html): its sections by
position, hidden ones left out, each with its text, figures, videos and items; the description, videos,
research lines and grants of an about page's subject; the records that name a section's grant; and the kinds
of a term the page explains, named the glossary's way ("Toxicokinetics (Process Flow Step)"). The platform's
catalogue, for the home page: its kinds of records with their counts, its pages, and its publisher's partners."""

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SDO, VOID

from database import records
from database.tables import Record
from linkeddata import catalogue, documents, outline, storage
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
    listed.sort(key=lambda found: found["name"].casefold())
    return listed


def sections(found: Graph, node) -> list[dict]:
    """A node's sections by position, hidden ones left out."""
    parts = sorted(found.objects(node, SDO.hasPart), key=lambda part: outline.placed(found, part))
    listed = []
    for part in parts:
        if str(found.value(part, SDO.creativeWorkStatus) or "") == "hidden":
            continue
        listed.append({"heading": str(found.value(part, SDO.name) or ""), "text": text(found.value(part, SDO.text)),
                       "figures": figures(found, part, SDO.image), "videos": videos(found, part, SDO.video),
                       "sections": sections(found, part), "outputs": outputs(found.value(part, SDO.about))})
    return listed


def grant(iri: str) -> dict:
    found = documents.public(storage.graph([iri]))
    node = URIRef(iri)
    amount = found.value(node, SDO.amount)
    funder = found.value(node, SDO.funder)
    return {"address": iri, "name": str(found.value(node, SDO.name) or iri), "identifier": str(found.value(node, SDO.identifier) or ""),
            "funder": records.names([str(funder)]).get(str(funder), str(funder)) if funder is not None else "",
            "amount": {"value": float(found.value(amount, SDO.value)), "currency": str(found.value(amount, SDO.currency) or "")} if amount is not None else None,
            "description": text(found.value(node, SDO.description))}


def subject(iri: str) -> dict:
    """What an about page shows of its subject: its names, description, videos, research lines and grants."""
    found = documents.public(storage.graph([iri]))
    node = URIRef(iri)
    lines = []
    for line in found.objects(node, SDO.subOrganization):
        lines.append({"name": str(found.value(line, SDO.name) or ""), "description": str(found.value(line, SDO.description) or "")})
    lines.sort(key=lambda line: line["name"])
    grants = []
    for funding in sorted(found.objects(node, SDO.funding)):
        grants.append(grant(str(funding)))
    return {"name": str(found.value(node, SDO.name) or ""), "alternateName": str(found.value(node, SDO.alternateName) or ""),
            "description": text(found.value(node, SDO.description)), "videos": videos(found, node, SDO.subjectOf),
            "figures": figures(found, node, SDO.image), "lines": lines, "grants": grants}


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
    shown = sections(found, node)
    main = found.value(node, SDO.mainEntity)
    about = found.value(node, SDO.about)
    return {"name": str(found.value(node, SDO.name) or record.name or ""), "description": str(found.value(node, SDO.description) or ""),
            "sections": shown, "tabbed": any(section["heading"] for section in shown),
            "subject": subject(str(main)) if main is not None else None, "kinds": kinds(str(about)) if about is not None else []}


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
    partnered = sorted([one for one in listed if one["role"]], key=lambda one: (one["role"], one["name"].casefold()))
    return partnered + sorted([one for one in listed if not one["role"]], key=lambda one: one["name"].casefold())


def catalogue_of(record: Record) -> dict:
    """The platform's catalogue: its names, sentence and description, its kinds of records in order with their
    counts and addresses, the pages about it, and its publisher's addresses elsewhere and partners."""
    found = documents.public(storage.graph([record.iri]))
    node = URIRef(record.iri)
    paths = {}
    for name, of_class in settings()["kinds"].items():
        paths[of_class] = name
    kinds = []
    for part in sorted(found.objects(node, VOID.classPartition), key=lambda part: outline.placed(found, part)):
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
