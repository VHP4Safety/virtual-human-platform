"""A page of the platform from its record, for its template (templates/records/page.html): its sections by
position, hidden ones left out, each with its text, figures, videos and items; the description, videos,
research lines and grants of an about page's subject; the records that name a section's grant; and the kinds
of a term the page explains, named the glossary's way ("Toxicokinetics (Process Flow Step)")."""

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SDO

from database import records
from database.tables import Record
from linkeddata import catalogue, documents, outline, storage


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

