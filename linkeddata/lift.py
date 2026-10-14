"""JSON as RDF, until rdfsolve reads JSON with a context itself: the fields of a source become
properties in the source's own vocabulary, "@id" gives an object its address, and "@type" its kind.
Objects found under the keys listed in *kinds* are given that kind when they have none."""

import json

import pyoxigraph as ox


def typed(value, kinds: dict, key: str = ""):
    """The JSON value, with "@type" added to the objects under the keys in *kinds*."""
    if isinstance(value, list):
        items = []
        for item in value:
            items.append(typed(item, kinds, key))
        return items
    if isinstance(value, dict):
        node = {}
        for name, item in value.items():
            node[name] = typed(item, kinds, name)
        if key in kinds and "@type" not in node:
            node["@type"] = kinds[key]
        return node
    return value


def lift(data, vocabulary: str, base: str, kinds: dict | None = None) -> ox.Dataset:
    document = {"@context": {"@vocab": vocabulary, "@base": base}, "@graph": typed(data, kinds or {})}
    return ox.Dataset(ox.parse(json.dumps(document).encode(), format=ox.RdfFormat.JSON_LD))
