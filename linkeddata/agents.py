"""The platform for agents, over the Model Context Protocol (MCP): tools to find, list and read records as
visitors read them (private fields are left out). Started by python -m linkeddata mcp; agents connect to
/mcp on MCP_HOST and MCP_PORT (127.0.0.1 and 5051 by default)."""

import json
import os
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from rdflib import URIRef
from rdflib.namespace import SDO

from database import records
from linkeddata import catalogue, documents, fields, markdown, outline, storage, void
from linkeddata.model import settings

server = MCPServer(settings()["title"], instructions=(
    f"The records of the {settings()['title']}: tools, methods, case studies, data, publications, organisations, people, pages, "
    "grants, terms and vocabularies. Find them with search or list_records, and read them with read."))
READING = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
PAGE = 50


def class_of(kind: str) -> str:
    if kind not in settings()["kinds"]:
        raise ToolError(f"Unknown kind {kind!r}; the kinds are {', '.join(settings()['kinds'])}.")
    return settings()["kinds"][kind]


def found_record(address: str):
    """The record at an address, or at a path on the platform (tools/aop-builder)."""
    record = records.get(records.address(address))
    if record is None or record.removed_at:
        raise ToolError(f"No record at {address}.")
    if record.moved_to:
        return found_record(record.moved_to)
    return record


@server.tool(annotations=READING)
def kinds() -> list[dict]:
    """The kinds of records, each with its count and its fields: name (for list_records filters), label,
    description, and the values a field takes when it has a list."""
    found = []
    for kind, of_class in settings()["kinds"].items():
        listed = []
        for field in fields.of(of_class):
            listed.append({"name": field["name"], "label": field["label"], "description": field["description"], "values": field["values"]})
        found.append({"kind": kind, "count": catalogue.page(of_class, {}, "", 0, 1)[0], "fields": listed})
    return found


@server.tool(annotations=READING)
def search(text: str, kind: str = "") -> list[dict]:
    """Records, their parts and vocabulary terms whose name or address has the text, of one kind when given;
    each with its address, name and class."""
    classes = [class_of(kind)] if kind else list(settings()["kinds"].values())
    found = []
    for record in records.search(text, classes, limit=50):
        found.append({"address": record.iri, "name": record.name or record.iri, "class": documents.term(record.type)})
    return found


@server.tool(annotations=READING)
def list_records(kind: str, filters: dict[str, list[str]] | None = None, text: str = "", page: int = 1) -> dict:
    """A kind's records, 50 a page, whose name has the text and that have, for each filtered field (by its
    name, as kinds gives it), one of the values; each with its address, name and description."""
    of_class = class_of(kind)
    names = {}
    for field in fields.of(of_class):
        names[field["name"]] = field["iri"]
    wanted = {}
    for name, values in (filters or {}).items():
        if name not in names:
            raise ToolError(f"No field {name!r} in {kind}; its fields are {', '.join(names)}.")
        wanted[names[name]] = values
    total, iris = catalogue.page(of_class, wanted, text, (page - 1) * PAGE, PAGE)
    found = documents.public(storage.graph(iris))
    listed = []
    for iri in iris:
        listed.append({"address": iri, "name": str(found.value(URIRef(iri), SDO.name) or iri),
                       "description": str(found.value(URIRef(iri), SDO.description) or "")})
    return {"total": total, "page": page, "records": listed}


@server.tool(annotations=READING)
def read(address: str, format: str = "markdown") -> str:
    """A record by its address (or its path on the platform, such as tools/aop-builder): its page in Markdown,
    with its parts and the records that name it, or its linked data in JSON-LD (format "json-ld")."""
    record = found_record(address)
    if format == "json-ld":
        return json.dumps(documents.document(documents.linked(record), record.iri), indent=1)
    formats = {"JSON-LD": record.iri + ".jsonld", "Turtle": record.iri + ".ttl", "N-Triples": record.iri + ".nt"}
    return markdown.record(outline.outline(record), formats, void.platform()["license"])


def run() -> None:
    """The server, over streamable HTTP, answering for the platform's host and this machine."""
    host = urlsplit(settings()["base"]).hostname
    security = TransportSecuritySettings(
        allowed_hosts=[host, f"{host}:*", "127.0.0.1:*", "localhost:*"],
        allowed_origins=[f"https://{host}", "http://127.0.0.1:*", "http://localhost:*"],
    )
    server.run(transport="streamable-http", host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MCP_PORT", "5051")),
               stateless_http=True, json_response=True, transport_security=security)
