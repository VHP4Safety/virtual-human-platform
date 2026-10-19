"""Where programs find the platform's data and services, at the addresses they look for:
- /.well-known/api-catalog: the APIs (RFC 9727), as a linkset (RFC 9264), with their OpenAPI descriptions;
- the API's answers link its description and its documentation (service-desc, service-doc, RFC 8631), and the
  home page links the catalogue (api-catalog);
- /.well-known/void: the published data (VoID), with its licence, vocabularies, size and dump (/api/dump);
- /llms.txt: where language models and agents find the records in Markdown, the API and the data (llmstxt.org).
The MCP server for agents (linkeddata/agents.py) is listed when PLATFORM_MCP gives its public address.
"""

import json
import os
from collections import Counter

from flask import Blueprint, Response, request
from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, FOAF, VOID

from database import records
from linkeddata import documents, markdown
from linkeddata.model import settings
from routes.record_pages import SERIALIZATIONS, data

blueprint = Blueprint("discovery", __name__)

CATALOG = "/.well-known/api-catalog"
OPENAPI = "api/docs/openapi.json"
DOCS = "api/docs/"


def services() -> list[dict]:
    """The platform's APIs as linkset entries: each one's address, description and documentation."""
    found = [{
        "anchor": records.address("api/"),
        "service-desc": [{"href": records.address(OPENAPI), "type": "application/vnd.oai.openapi+json"}],
        "service-doc": [{"href": records.address(DOCS), "type": "text/html"}],
    }]
    if os.environ.get("PLATFORM_MCP"):
        found.append({"anchor": os.environ["PLATFORM_MCP"], "service-doc": [{"href": records.address("llms.txt"), "type": "text/markdown"}]})
    return found


@blueprint.get(CATALOG)
def api_catalog():
    body = json.dumps({"linkset": services()}, indent=1)
    return Response(body, content_type='application/linkset+json; profile="https://www.rfc-editor.org/info/rfc9727"',
                    headers={"Access-Control-Allow-Origin": "*"})


def described() -> Graph:
    """The published data as a VoID dataset: what it is, its licence, its namespace and vocabularies, its size by
    class, its last change and its dump."""
    found = documents.published()
    dataset = URIRef(records.address(".well-known/void") + "#platform")
    void = Graph()
    void.bind("void", VOID)
    void.bind("dct", DCTERMS)
    void.add((dataset, RDF.type, VOID.Dataset))
    void.add((dataset, DCTERMS.title, Literal(settings()["title"])))
    void.add((dataset, DCTERMS.license, URIRef(settings()["license"])))
    void.add((dataset, FOAF.homepage, URIRef(settings()["base"])))
    void.add((dataset, VOID.uriSpace, Literal(settings()["base"])))
    void.add((dataset, VOID.dataDump, URIRef(records.address("api/dump"))))
    void.add((dataset, VOID.triples, Literal(len(found))))
    void.add((dataset, VOID.entities, Literal(len(set(found.subjects(RDF.type, None))))))
    if records.latest_change():
        void.add((dataset, DCTERMS.modified, Literal(records.latest_change(), datatype=XSD.dateTime)))
    for namespace in settings()["prefixes"].values():
        void.add((dataset, VOID.vocabulary, URIRef(namespace)))
    for namespace in settings()["terms"].values():
        void.add((dataset, VOID.vocabulary, URIRef(namespace.split("#")[0] + "#")))
    counted = Counter(found.objects(None, RDF.type))
    for of_class, count in sorted(counted.items()):
        partition = URIRef(f"{dataset}-" + documents.term(str(of_class)).replace(":", "-"))
        void.add((dataset, VOID.classPartition, partition))
        void.add((partition, VOID["class"], of_class))
        void.add((partition, VOID.entities, Literal(count)))
    return void


@blueprint.get("/.well-known/void")
def void_description():
    media = request.accept_mimetypes.best_match(["text/turtle", "application/ld+json", *SERIALIZATIONS]) or "text/turtle"
    answer = data(described(), media)
    answer.headers["Access-Control-Allow-Origin"] = "*"
    return answer


@blueprint.get("/llms.txt")
def llms_txt():
    lines = [f"# {settings()['title']}", f"> {settings()['description']}",
             "Every record's page is also in Markdown (add .md to its address, or ask for text/markdown) and in linked data "
             f"(.jsonld, .ttl, .nt). The records are under the licence <{settings()['license']}>.",
             "## Records"]
    listed = []
    for kind in settings()["kinds"]:
        listed.append(f"- [{kind.capitalize()}]({records.address(kind)}.md?page_size=200): the {kind}, in Markdown")
    lines.append("\n".join(listed))
    lines.append("## Data")
    lines.append("\n".join([
        f"- [API]({records.address(DOCS)}): search, filter and read records, in JSON, JSON-LD, Turtle or Markdown",
        f"- [OpenAPI description]({records.address(OPENAPI)}): the API for programs",
        f"- [All data]({records.address('api/dump')}): every published statement, as one N-Triples file",
        f"- [VoID description]({records.address('.well-known/void')}): what the data holds, by class",
        f"- [Shapes]({records.address('api/shapes.ttl')}): what each field of a record takes (SHACL)",
    ]))
    if os.environ.get("PLATFORM_MCP"):
        lines.append("## Agents")
        lines.append(f"- [MCP server]({os.environ['PLATFORM_MCP']}): tools to search, list and read records (streamable HTTP)")
    return Response("\n\n".join(lines) + "\n", content_type=markdown.MEDIA, headers={"Access-Control-Allow-Origin": "*"})


@blueprint.after_app_request
def service_links(response):
    links = []
    if request.path.startswith("/api/"):
        links.append(f'<{records.address(OPENAPI)}>; rel="service-desc"; type="application/vnd.oai.openapi+json"')
        links.append(f'<{records.address(DOCS)}>; rel="service-doc"; type="text/html"')
    if request.path == "/":
        links.append(f'<{CATALOG}>; rel="api-catalog"')
    if links:
        given = response.headers.get("Link")
        response.headers["Link"] = ", ".join(([given] if given else []) + links)
    return response
