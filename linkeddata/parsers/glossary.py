"""Parser of the VHP4Safety glossary, an OWL file, a workaround (see linkeddata/parsers).

The classes of the file are the terms, with labels and definitions. The rows are the glossary, as a vocabulary, and
its terms."""

from rdflib import RDF, RDFS, Graph
from rdflib.namespace import DC, OWL, SKOS

from linkeddata.parsers import link, present

NAMESPACE = "https://vhp4safety.github.io/glossary#"
VOCABULARY = "vocabularies/vhp4safety-glossary"


def parse(content: bytes) -> list[dict]:
    graph = Graph().parse(data=content, format="turtle")
    rows = [{"@id": VOCABULARY, "@type": "DefinedTermSet", "name": "VHP4Safety glossary", "void:uriSpace": NAMESPACE,
             "url": link(NAMESPACE.rstrip("#"))}]
    for term in sorted(graph.subjects(RDF.type, OWL.Class)):
        if not str(term).startswith(NAMESPACE):
            continue
        row = {"@id": str(term), "@type": "DefinedTerm", "termCode": str(term).removeprefix(NAMESPACE), "inDefinedTermSet": link(VOCABULARY)}
        label = graph.value(term, RDFS.label)
        if present(label):
            row["name"] = str(label)
        definition = graph.value(term, DC.description)
        if present(definition):
            row["description"] = str(definition)
        # A short label, such as Exposure for Exposure (Process Flow Step), is another name of the term.
        alternates = []
        for alternate in sorted(graph.objects(term, SKOS.altLabel)):
            if present(alternate):
                alternates.append(str(alternate))
        if alternates:
            row["alternateName"] = alternates
        rows.append(row)
    return rows
