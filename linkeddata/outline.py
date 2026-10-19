"""A record for reading, as its page, its Markdown and agents show it: its name, its fields by their labels in
the profile's order, its parts (such as case study questions, sections, inputs and outputs), each an outline of
its own in their order, and the records that name it. Private fields are left out."""

from rdflib import RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.namespace import SDO

from database import records
from database.tables import Record
from linkeddata import catalogue, documents, fields, storage
from linkeddata.model import profile

# A node's name heads it, and its position orders it among its kind; neither is listed with its fields.
HEADING = {str(SDO.name), str(SDO.position)}
# A field with a text longer than this, or in HTML, is read as paragraphs; others as a list.
SHORT = 160


def kind_of(of_class: str) -> str:
    """The label of a class, as the profile gives it, such as "Workflow page"."""
    return str(profile().value(fields.shape_of(of_class), RDFS.label) or "")


def value_of(value, names: dict) -> dict:
    """A field's value: a text, marked when it is HTML, or a link with its name."""
    if isinstance(value, Literal):
        return {"text": str(value), "html": value.datatype == RDF.HTML}
    return {"link": str(value), "name": names.get(str(value)) or str(value)}


def placed(found: Graph, node) -> tuple:
    """A part's place: by its position, then by its name, then by its values, so parts in the same place
    keep one order."""
    position = found.value(node, SDO.position)
    try:
        number = float(position)
    except (TypeError, ValueError):
        number = float("inf")
    return number, str(found.value(node, SDO.name) or ""), sorted(str(value) for value in found.objects(node, None))


def in_order(found: Graph, nodes) -> list:
    """Nodes in the order of their places (placed)."""
    def place(node):
        return placed(found, node)
    return sorted(nodes, key=place)


def by_name(item: dict) -> str:
    """An item's place in a list by its name, whatever its case."""
    return item["name"].casefold()


def node_outline(found: Graph, node, names: dict) -> dict:
    of_class = str(found.value(node, RDF.type) or "")
    shown = {"address": None if isinstance(node, BNode) else str(node), "name": str(found.value(node, SDO.name) or ""),
             "kind": kind_of(of_class), "fields": [], "parts": []}
    for field in fields.of(of_class):
        values = list(found.objects(node, URIRef(field["iri"])))
        if field["iri"] in HEADING or not values or not field["shown"]:
            continue
        if field["part"]:
            values = in_order(found, values)
            shown["parts"].append({"label": field["label"], "items": [node_outline(found, part, names) for part in values]})
        else:
            values.sort(key=str)
            given = [value_of(value, names) for value in values]
            long = False
            for value in given:
                if "text" in value and (value["html"] or len(value["text"]) > SHORT):
                    long = True
            shown["fields"].append({"name": field["name"], "label": field["label"], "values": given, "long": long, "section": field["section"]})
    return shown


def named_on(record: Record) -> dict[str, list[dict]]:
    """The records that name this one, by the label of the field that names it on them; each with its address,
    name and kind."""
    fields_of = {}
    for holder, path in catalogue.naming(record.iri):
        fields_of.setdefault(holder, []).append(path)
    found = {}
    for holder in records.kept(list(fields_of)):
        if holder.iri == record.iri:
            continue
        labels = {}
        for field in fields.of(holder.type):
            labels[field["iri"]] = field["label"]
        for path in fields_of[holder.iri]:
            found.setdefault(labels.get(path) or documents.term(path), []).append(
                {"address": holder.iri, "name": holder.name or holder.iri, "kind": kind_of(holder.type)})
    for listed in found.values():
        listed.sort(key=by_name)
    return found


def outline(record: Record) -> dict:
    """A record's outline, from its public statements and its parts', with the records that name it."""
    found = documents.public(storage.graph([record.iri]))
    links = []
    for value in found.objects():
        if isinstance(value, URIRef):
            links.append(str(value))
    shown = node_outline(found, URIRef(record.iri), records.names(links))
    shown["named_on"] = named_on(record)
    return shown
