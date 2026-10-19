"""Parser of the VHP4Safety glossary (a workaround, see linkeddata/parsers): an OWL file whose classes are
its terms, with labels and definitions. Rows are the glossary, as a vocabulary, and its terms."""

from rdflib import RDF, RDFS, Graph
from rdflib.namespace import DC, OWL, SKOS

from linkeddata.parsers import link, present

NAMESPACE = "https://vhp4safety.github.io/glossary#"
VOCABULARY = "vocabularies/vhp4safety-glossary"


def parse(content: bytes) -> list[dict]:
    graph = Graph().parse(data=content, format="turtle")
    rows = [{"@id": VOCABULARY, "@type": "Vocabulary", "name": "VHP4Safety glossary", "namespace": NAMESPACE,
             "home": link(NAMESPACE.rstrip("#"))}]
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
        # A short label, such as Exposure for Exposure (Process Flow Step), is another name of the term.
        alternates = []
        for alternate in sorted(graph.objects(term, SKOS.altLabel)):
            if present(alternate):
                alternates.append(str(alternate))
        if alternates:
            row["alternate"] = alternates
        rows.append(row)
    return rows
