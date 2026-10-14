"""Rows as RDF, until rdfsolve reads JSON with a context itself: the fields of a source become
properties in the source's own vocabulary, and "@id" and "@type" give each row its address and kind."""

import json

import pyoxigraph as ox


def lift(rows: list[dict], vocabulary: str, base: str) -> ox.Dataset:
    document = {"@context": {"@vocab": vocabulary, "@base": base}, "@graph": rows}
    return ox.Dataset(ox.parse(json.dumps(document).encode(), format=ox.RdfFormat.JSON_LD))
