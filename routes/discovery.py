"""Discovery addresses of the data and the services of the platform, for programs:
- /.well-known/api-catalog: the APIs (RFC 9727), as a linkset (RFC 9264), with their OpenAPI descriptions.
- Link headers: link the responses of the API to its description and its documentation (service-desc, service-doc,
  RFC 8631), and the home page to the catalogue (api-catalog).
- /.well-known/void: the published data (VoID), as returned in Turtle at the address of the platform
  (linkeddata/void.py).
"""

import json

from flask import Blueprint, Response, request

from database import records
from linkeddata import void
from routes.record_pages import SERIALIZATIONS, data

blueprint = Blueprint("discovery", __name__)

CATALOG = "/.well-known/api-catalog"
OPENAPI = "api/docs/openapi.json"
DOCS = "api/docs/"


def services() -> list[dict]:
    """Return the APIs of the platform as linkset entries, each with its address, description and documentation."""
    found = [{
        "anchor": records.address("api/"),
        "service-desc": [{"href": records.address(OPENAPI), "type": "application/vnd.oai.openapi+json"}],
        "service-doc": [{"href": records.address(DOCS), "type": "text/html"}],
    }]
    return found


@blueprint.get(CATALOG)
def api_catalog():
    body = json.dumps({"linkset": services()}, indent=1)
    return Response(body, content_type='application/linkset+json; profile="https://www.rfc-editor.org/info/rfc9727"',
                    headers={"Access-Control-Allow-Origin": "*"})


@blueprint.get("/.well-known/void")
def void_description():
    media = request.accept_mimetypes.best_match(["text/turtle", "application/ld+json", *SERIALIZATIONS]) or "text/turtle"
    answer = data(void.described(), media)
    answer.headers["Access-Control-Allow-Origin"] = "*"
    return answer


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
