"""Parser of the glossary's OWL file (a workaround, see linkeddata/parsers): the five safety
assessment steps, picked by their glossary codes so that a change of their names does not matter."""

from rdflib import Graph, URIRef
from rdflib.namespace import DC, RDFS

GLOSSARY = "https://vhp4safety.github.io/glossary#"
STEPS = ["VHP0000153", "VHP0000154", "VHP0000155", "VHP0000156", "VHP0000158"]


def parse(content: bytes) -> list[dict]:
    graph = Graph().parse(data=content, format="turtle")
    rows = []
    for code in STEPS:
        term = URIRef(GLOSSARY + code)
        label = graph.value(term, RDFS.label)
        if label is None:
            continue
        # The glossary adds "(Process Flow Step)" to the labels of the steps.
        row = {"@id": GLOSSARY + code, "@type": "Term", "code": code, "label": str(label).split(" (")[0]}
        description = graph.value(term, DC.description)
        if description is not None:
            row["description"] = str(description)
        rows.append(row)
    return rows
