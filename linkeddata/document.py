"""Compact JSON-LD documents of records, with the model's prefixes."""

from pyld import jsonld


def context(config: dict) -> dict:
    """The JSON-LD context: schema.org terms without a prefix, other vocabularies with theirs."""
    terms = {"@vocab": config["prefixes"]["schema"]}
    for prefix, namespace in config["prefixes"].items():
        if prefix != "schema":
            terms[prefix] = namespace
    return terms


def compact(statements: str, config: dict) -> dict:
    """A compact JSON-LD document of statements in N-Triples."""
    return jsonld.compact(jsonld.from_rdf(statements, {"format": "application/n-quads"}), context(config))
