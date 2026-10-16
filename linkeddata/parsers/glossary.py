"""Parser of the VHP4Safety glossary (a workaround, see linkeddata/parsers): an OWL file whose classes are
the glossary's terms, each with its label and its definition. Its rows are the glossary, as a vocabulary,
and its terms at their own addresses."""

from rdflib import RDF, RDFS, Graph
from rdflib.namespace import DC, OWL

from linkeddata.parsers import link, present

NAMESPACE = "https://vhp4safety.github.io/glossary#"
VOCABULARY = "vocabularies/vhp4safety-glossary"


def parse(content: bytes) -> list[dict]:
    graph = Graph().parse(data=content, format="turtle")
    rows = [{"@id": VOCABULARY, "@type": "Vocabulary", "name": "VHP4Safety glossary", "namespace": link(NAMESPACE)}]
    for term in sorted(graph.subjects(RDF.type, OWL.Class)):
        if not str(term).startswith(NAMESPACE):
            continue
        row = {"@id": str(term), "@type": "Term", "code": str(term).removeprefix(NAMESPACE), "vocabulary": link(VOCABULARY)}
        label = graph.value(term, RDFS.label)
        if present(label):
            row["label"] = str(label)
        definition = graph.value(term, DC.description)
        if present(definition):
            row["definition"] = str(definition)
        rows.append(row)
    return rows
