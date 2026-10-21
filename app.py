################################################################################
### Loading the required modules
import json
import os
import re
import secrets
from datetime import timedelta
from functools import lru_cache

import nh3
import requests
import urllib.parse
from flask import Flask, abort, g, jsonify, redirect, render_template, request, Response, url_for
from jinja2 import TemplateNotFound
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

# Import BioStudies extractor
from admin.writes import slug
from database import records
from linkeddata import documents, pages, void
from linkeddata.profile import hierarchy, settings
from routes.account import blueprint as account_blueprint
from routes import limiter, records_api
from routes.changes import blueprint as changes_blueprint
from routes.discovery import blueprint as discovery_blueprint
from routes.editor import blueprint as admin_blueprint
from routes.images import blueprint as images_blueprint
from routes.record_pages import blueprint as pages_blueprint
from routes.record_pages import listing_page, page_link, record_page

################################################################################

# SEO defaults. Every page renders a <title>/<meta description> (see base.html);
# routes override page_title / meta_description with page-specific values, and
# inject_seo_defaults() falls back to these for anything that does not.
DEFAULT_PAGE_TITLE = "VHP4Safety — Virtual Human Platform for safety assessment"


def clip(text, limit=160):
    """Trim a description to a search-snippet-friendly length (~160 chars)."""
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

################################################################################
class RegexConverter(BaseConverter):
    """Converter for regular expression routes.

    References
    ----------
    Scholia views.py
    https://stackoverflow.com/questions/5870188

    """

    def __init__(self, url_map, *items):
        """Set up regular expression matcher."""
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app = Flask(__name__)
# The scheme and host are taken from the reverse proxy, for the ORCID login.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("SECRET_KEY"):
    app.logger.warning("SECRET_KEY is not set: logins end on restart, and fail with several workers.")
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_DEBUG") != "1"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
# With the __Host- prefix, the cookie is sent only to this host. The prefix is accepted only on a secure cookie.
if app.config["SESSION_COOKIE_SECURE"]:
    app.config["SESSION_COOKIE_NAME"] = "__Host-session"
app.register_blueprint(account_blueprint)
app.register_blueprint(admin_blueprint)
limiter.init_app(app)
records_api.register(app)
app.register_blueprint(pages_blueprint)
app.register_blueprint(changes_blueprint)
app.register_blueprint(images_blueprint)
app.register_blueprint(discovery_blueprint)
# Google Search Console verification token (rendered as a <meta> tag in
# base.html when set). Kept out of the repo -- set it in the service env.
app.config["GOOGLE_SITE_VERIFICATION"] = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
# The class hierarchy of the vocabularies is read once, at start, not at the first request.
hierarchy()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", "object-src 'none'; base-uri 'self'")
    return response


def local_link(tag: str, attribute: str, value: str) -> str:
    """Return the address of a link or an image in a text as a path on this server."""
    return page_link(value) if attribute in ("href", "src") else value


@app.template_filter("sanitize_html")
def sanitize_html(value) -> Markup:
    """Return upstream HTML with its formatting tags, without scripts and event handlers."""
    return Markup(nh3.clean(str(value or ""), attribute_filter=local_link))


def get_process_flow_steps() -> dict:
    """Return the process flow steps of the glossary by address, with label, slug and description."""
    return pages.steps()


def page_record(path: str) -> dict:
    """Return the content of the page record at path, or abort with 404."""
    record = records.get(records.address(path))
    if record is None:
        abort(404)
    return pages.page(record)


def menu(kind: str) -> list[dict]:
    """Return the records of a kind for the menus and the search bar, by name."""
    listed = []
    for record in records.of_kind(kind):
        if record.part_of is None:
            listed.append({"id": record.iri.rsplit("/", 1)[-1], "title": record.name or record.iri, "url": page_link(record.iri)})
    listed.sort(key=lambda item: item["title"].lower())
    return listed


@app.context_processor
def inject_menus():
    """Return the tools, methods and data for the menus and the search bar."""
    return {"tools_menu": menu("tools"), "methods_menu": menu("methods"), "data_menu": menu("data")}


@app.context_processor
def inject_seo_defaults():
    """Provide SEO defaults so every page has a title/description/canonical.

    Routes override page_title / meta_description via render_template kwargs
    (explicit context wins over context processors). canonical_url defaults to
    the address of the record of the page, else the page path under the
    platform address.
    """
    return {
        "page_title": DEFAULT_PAGE_TITLE,
        "meta_description": void.platform()["abstract"],
        "canonical_url": g.record.iri if "record" in g else records.address(request.path.strip("/")),
    }


################################################################################
### The landing page
@app.route("/")
def home():
    record = records.get(settings()["base"])
    if record is None:
        abort(404)
    platform = pages.catalogue_of(record)
    workflow = records.get(records.address("safety_assessment_workflow"))
    return render_template(
        "home.html",
        platform=platform,
        workflow=pages.page(workflow) if workflow is not None else None,
        process_flow_steps=get_process_flow_steps(),
        page_title=DEFAULT_PAGE_TITLE,
        meta_description=platform["abstract"],
    )


################################################################################
### The sitemap.xml for search engines
@app.route("/sitemap.xml")
def sitemap():

    # Static, parameter-less GET pages, derived from the URL map so new pages
    # are picked up automatically. Machine endpoints are excluded. Routes with
    # <params> are skipped and handled below.
    EXCLUDED_ENDPOINTS = {"sitemap", "robots", "static", "pages.models_page"}
    # The pages for editors (login, tokens, editing, changes) and the API are left out.
    EXCLUDED_BLUEPRINTS = {"account", "admin", "changes", "records", "api-docs", "discovery"}
    paths = sorted({
        rule.rule.rstrip("/") or "/"
        for rule in app.url_map.iter_rules()
        if not rule.arguments
        and rule.endpoint not in EXCLUDED_ENDPOINTS
        and rule.endpoint.split(".")[0] not in EXCLUDED_BLUEPRINTS
        and "GET" in (rule.methods or set())
    })
    listed = records.with_pages()
    with_pages = {address.rstrip("/") for address, _ in listed}
    # A static page that is also the page of a record, such as the home page, is listed once.
    entries = [f"  <url>\n    <loc>{records.address(p)}</loc>\n  </url>" for p in paths if records.address(p).rstrip("/") not in with_pages]
    for address, changed in listed:
        entries.append(f"  <url>\n    <loc>{address}</loc>\n    <lastmod>{changed}</lastmod>\n  </url>")
    sitemapContent = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    return Response(sitemapContent, mimetype="text/xml")


################################################################################
### robots.txt points crawlers at the sitemap so the detail pages get indexed
@app.route("/robots.txt")
def robots():
    robotsContent = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "\n"
        f"Sitemap: {records.address('sitemap.xml')}\n"
    )
    return Response(robotsContent, mimetype="text/plain")


################################################################################
### Pages under 'Data'
@app.route("/data")
def data():
    return listing_page("data")


################################################################################
### DataSet detail view


@app.route("/data/<dataid>")
def data_detail(dataid):
    record = records.get(records.address(f"data/{dataid}"))
    if record is None:
        abort(404)
    return record_page(record)


################################################################################
### Pages under 'Tools'


### Here begins the updated version for creating the tool list page.
@app.route("/tools")
def tools():
    return listing_page("tools")


### New route to list methods (similar to the tools page)
@app.route("/methods")
@app.route("/methods/")
def methods():
    """Render the methods listing from the records."""
    return listing_page("methods")


@app.route("/methods/<methodid>")
def method_page(methodid):
    """Render the page of a method from its record."""
    record = records.get(records.address(f"methods/{methodid}"))
    if record is None:
            abort(404)
    return record_page(record)


@app.route("/tools/<toolname>")
def tool_page(toolname):
    record = records.get(records.address(f"tools/{toolname}"))
    if record is None:
        abort(404)
    return record_page(record)


################################################################################
### Pages under 'Implementation'


# General Explore our work
@app.route("/explore_our_work")
def explore_our_work():
    return render_template(
        "records/page.html",
        page=page_record("explore_our_work"),
        page_title="Our work — VHP4Safety",
        meta_description=(
            "How the VHP4Safety consortium builds the Virtual Human Platform to "
            "advance animal-free safety assessment of chemicals and pharmaceuticals."
        ),
    )


# General Training
@app.route("/training")
def training():
    return render_template(
        "records/page.html",
        page=page_record("training"),
        listed=pages.items(records.page(settings()["kinds"]["training"], {}, "", 0, None)[1]),
        page_title="Training — VHP4Safety",
        meta_description=(
            "Training materials and courses on the VHP4Safety Virtual Human Platform "
            "and animal-free, human-based safety assessment."
        ),
    )


# General Impact
@app.route("/impact")
def impact():
    return render_template(
        "records/page.html",
        page=page_record("impact"),
        page_title="Impact — VHP4Safety",
        meta_description=(
            "The scientific and societal impact of VHP4Safety in the transition to "
            "animal-free safety assessment of chemicals and pharmaceuticals."
        ),
    )


################################################################################
### Pages under 'Process Flow'


# General Safety Assessment Workflow page
@app.route("/safety_assessment_workflow")
def SafetyAssessmentWorkflow():
    return render_template(
        "safety_assessment_workflow.html", process_flow_steps=get_process_flow_steps(),
        page=page_record("safety_assessment_workflow"), page_title="Safety Assessment Workflow — VHP4Safety",
    )


################################################################################
### Pages under 'Case Studies'


# General case studies page
@app.route("/casestudies")
def workflows():
    listed = [record for record in records.of_kind("casestudies") if record.part_of is None]
    statements = records.graph([record.iri for record in listed])
    case_studies = []
    for record in listed:
        aims = documents.stored_values(statements, record.iri, "description")
        icons = documents.stored_values(statements, record.iri, "image")
        case_studies.append({"address": record.iri, "name": record.name, "aim": aims[0] if aims else "", "icon": icons[0] if icons else ""})
    return render_template(
        "case_studies/casestudies.html",
        case_studies=case_studies,
        page_title="Case studies — VHP4Safety",
        meta_description=(
            "Explore the VHP4Safety case studies (kidney, Parkinson's disease and "
            "thyroid) that connect tools, methods and data to real regulatory questions."
        ),
    )


@lru_cache(maxsize=16)
def case_outline(iri: str, latest: str) -> dict:
    """Return the outline of a case study for readers without scripts."""
    return pages.outline(records.get(iri))


# Individual case study page, dynamically filled based on URL
@app.route("/casestudies/<case>")
@app.route("/casestudies/<case>/<question>")
@app.route("/casestudies/<case>/<question>/<step>")
@app.route("/casestudies/<case>/<question>/<step>/<step2>")
@app.route("/casestudies/<case>/<question>/<step>/<step2>/<step3>")
@app.route("/casestudies/<case>/<question>/<step>/<step2>/<step3>/<step4>")
@app.route("/casestudies/<case>/<question>/<step>/<step2>/<step3>/<step4>/<step5>")
# additional routes are parsed client side via js to allow smooth animation
def casestudy(case: str = "", question: str = "", step: str = "",
              step1: str = "", step2: str = "", step3: str = "",
              step4: str = "", step5: str = ""):
    record = records.get(records.address(f"casestudies/{case}"))
    if record is None:
        abort(404)
    address = records.address(request.path.strip("/"))
    # An address such as /casestudies/kidney/Q1/Exposure/Current_Dose_levels is matched to a page part by part.
    if address != record.iri and records.get(address) is None:
        wanted = [slug(part) for part in address.removeprefix(record.iri + "/").split("/")]
        for part in records.parts_of(record.iri):
            if [slug(given) for given in part.removeprefix(record.iri + "/").split("/")] == wanted:
                return redirect(page_link(part), code=301)
    found = case_outline(record.iri, records.latest_change())
    descriptions = [field["values"][0] for field in found["fields"] if field["name"] == "description"]
    return render_template(
        "case_studies/casestudy.html",
        case_outline=found,
        case_document=url_for("records.read", path=f"casestudies/{case}"),
        # At the address of a question or a step, the page record is that part. The case study is given too.
        case_json=None if address == record.iri else documents.page_document(record.iri, records.latest_change()),
        page_address=address,
        config_base=records.address(""),
        page_title=f"{record.name or case} — VHP4Safety",
        meta_description=clip(descriptions[0]["text"] if descriptions else "")
        or f"The VHP4Safety {record.name or case}: a Virtual Human Platform workflow connecting tools, methods and data to a regulatory question.",
        canonical_url=record.iri,
    )


@app.route("/workflow/<workflow>")
def show(workflow):
    try:
        return render_template(
            f"case_studies/parkinson/workflows/{workflow}_workflow.html"
        )
    except TemplateNotFound:
        abort(404)


################################################################################
### Pages related to chemical compounds


def is_valid_qid(qid):
    return re.fullmatch(r"Q\d+", qid) is not None


def run_sparql(endpoint: str, query: str) -> dict:
    """Run a SPARQL query with a time limit and return the JSON results."""
    response = requests.post(
        endpoint,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json", "User-Agent": "VHP4Safety platform"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


@app.route("/compound/<cwid>")
def show_compound(cwid):
    if not is_valid_qid(cwid):
        abort(404)
    try:
        return render_template("compound.html", cwid=cwid)
    except TemplateNotFound:
        abort(404)


@app.route("/get_compound_properties/<cwid>")
def show_compounds_properties_as_json(cwid):
    if not is_valid_qid(cwid):
        return jsonify({"error": "Invalid compound identifier"}), 400
    compoundwikiEP = "https://compoundcloud.wikibase.cloud/query/sparql"
    sparqlquery = (
        "PREFIX wd: <https://compoundcloud.wikibase.cloud/entity/>\n"
        "PREFIX wdt: <https://compoundcloud.wikibase.cloud/prop/direct/>\n\n"
        "SELECT ?cmp ?cmpLabel ?type ?formula ?mass ?inchi ?inchiKey ?SMILES WHERE {\n"
        "  VALUES ?cmp { wd:" + cwid + " }\n"
        "  ?cmp wdt:P1 ?type \n"
        "  OPTIONAL { ?cmp wdt:P9 ?inchi }\n"
        "  OPTIONAL { ?cmp wdt:P10 ?inchiKey }\n"
        "  OPTIONAL { ?cmp wdt:P2 ?mass }\n"
        "  OPTIONAL { ?cmp wdt:P3 ?formula }\n"
        "  OPTIONAL { ?cmp wdt:P7 ?chiralSMILES }\n"
        "  OPTIONAL { ?cmp wdt:P12 ?nonchiralSMILES }\n"
        '  BIND (COALESCE(IF(BOUND(?chiralSMILES), ?chiralSMILES, 1/0), IF(BOUND(?nonchiralSMILES), ?nonchiralSMILES, 1/0), "") AS ?SMILES)\n'
        '  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }\n'
        "}"
    )
    try:
        compound_dat = run_sparql(compoundwikiEP, sparqlquery)
    except Exception:
        app.logger.exception("Compound query failed")
        return jsonify({"error": "Upstream query failed"}), 500
    if not bool(compound_dat):
        return jsonify({"error": "No data found"}), 404
    compound_dat = compound_dat["results"]["bindings"][0]
    # return jsonify(compound_dat);
    compound_list = [
        {
            "wcid": compound_dat["cmp"]["value"],
            "label": compound_dat["cmpLabel"]["value"],
        }
    ]
    if "inchi" in compound_dat:
        compound_list[0]["inchi"] = compound_dat["inchi"]["value"]
    if "inchikey" in compound_dat:
        compound_list[0]["inchikey"] = compound_dat["inchikey"]["value"]
    if "SMILES" in compound_dat:
        compound_list[0]["SMILES"] = compound_dat["SMILES"]["value"]
    if "formula" in compound_dat:
        compound_list[0]["formula"] = compound_dat["formula"]["value"]
    if "mass" in compound_dat:
        compound_list[0]["mass"] = compound_dat["mass"]["value"]
    return jsonify(compound_list), 200


@app.route("/get_compound_identifiers/<cwid>")
def show_compounds_identifiers_as_json(cwid):
    if not is_valid_qid(cwid):
        return jsonify({"error": "Invalid compound identifier"}), 400
    compoundwikiEP = "https://compoundcloud.wikibase.cloud/query/sparql"
    sparqlquery = (
        "PREFIX wd: <https://compoundcloud.wikibase.cloud/entity/>\n"
        "PREFIX wdt: <https://compoundcloud.wikibase.cloud/prop/direct/>\n\n"
        "SELECT DISTINCT ?propertyLabel ?value ?formatterURL\n"
        "WHERE {\n"
        "  VALUES ?property { wd:P13 wd:P22 wd:P23 wd:P26 wd:P27 wd:P28 wd:P36 wd:P41 wd:P43 wd:P44 wd:P45 }\n"
        "  ?property wikibase:directClaim ?valueProp .\n"
        "  OPTIONAL { wd:" + cwid + " ?valueProp ?value }\n"
        "  OPTIONAL { ?property wdt:P6 ?formatterURL }\n"
        '  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }\n'
        "}"
    )
    try:
        compound_dat = run_sparql(compoundwikiEP, sparqlquery)
    except Exception:
        app.logger.exception("Compound query failed")
        return jsonify({"error": "Upstream query failed"}), 500
    if len(compound_dat["results"]["bindings"]) == 0:
        return jsonify({"error": "No data found"}), 404
    compound_dat = compound_dat["results"]["bindings"]
    # return jsonify(compound_dat)

    compound_list = []
    for expProp in compound_dat:
        if "value" in expProp:
            compound_list.append(
                {
                    "propertyLabel": expProp["propertyLabel"]["value"],
                    "value": expProp["value"]["value"],
                    "formatterURL": expProp["formatterURL"]["value"],
                }
            )
        else:
            compound_list.append(
                {
                    "propertyLabel": expProp["propertyLabel"]["value"],
                    "value": "",
                    "formatterURL": "",
                }
            )
    return jsonify(compound_list), 200


@app.route("/get_compound_toxicology/<cwid>")
def show_compounds_toxicology_as_json(cwid):
    if not is_valid_qid(cwid):
        return jsonify({"error": "Invalid compound identifier"}), 400
    compoundwikiEP = "https://compoundcloud.wikibase.cloud/query/sparql"
    sparqlquery = (
        "PREFIX wd: <https://compoundcloud.wikibase.cloud/entity/>\n"
        "PREFIX wdt: <https://compoundcloud.wikibase.cloud/prop/direct/>\n\n"
        "SELECT DISTINCT ?propertyLabel ?value ?formatterURL\n"
        "WHERE {\n"
        "  VALUES ?property { wd:P17 wd:P19 wd:P4 }\n"
        "  ?property wikibase:directClaim ?valueProp .\n"
        "  OPTIONAL { wd:" + cwid + " ?valueProp ?value }\n"
        "  OPTIONAL { ?property wdt:P6 ?formatterURL }\n"
        '  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }\n'
        "}"
    )
    try:
        compound_dat = run_sparql(compoundwikiEP, sparqlquery)
    except Exception:
        app.logger.exception("Compound query failed")
        return jsonify({"error": "Upstream query failed"}), 500
    if len(compound_dat["results"]["bindings"]) == 0:
        return jsonify({"error": "No data found"}), 404
    compound_dat = compound_dat["results"]["bindings"]
    # return jsonify(compound_dat)

    compound_list = []
    for expProp in compound_dat:
        print(expProp)
        if "value" in expProp:
            compound_list.append(
                {
                    "propertyLabel": expProp["propertyLabel"]["value"],
                    "value": expProp["value"]["value"],
                }
            )
        else:
            compound_list.append(
                {"propertyLabel": expProp["propertyLabel"]["value"], "value": ""}
            )
    return jsonify(compound_list), 200


@app.route("/get_compound_expdata/<cwid>")
def show_compounds_expdata_as_json(cwid):
    if not is_valid_qid(cwid):
        return jsonify({"error": "Invalid compound identifier"}), 400
    compoundwikiEP = "https://compoundcloud.wikibase.cloud/query/sparql"
    sparqlquery = (
        "PREFIX wd: <https://compoundcloud.wikibase.cloud/entity/>\n"
        "PREFIX wdt: <https://compoundcloud.wikibase.cloud/prop/direct/>\n"
        "PREFIX wid: <http://www.wikidata.org/entity/>\n"
        "PREFIX widt: <http://www.wikidata.org/prop/direct/>\n"
        "PREFIX prov: <http://www.w3.org/ns/prov#>\n\n"
        "SELECT ?qid WHERE {\n"
        "  wd:P5 wikibase:directClaim ?identifierProp .\n"
        "  wd:" + cwid + " ?identifierProp ?wikidata .\n"
        '  BIND (iri(CONCAT("http://www.wikidata.org/entity/", ?wikidata)) AS ?qid)\n'
        "}"
    )
    try:
        compound_dat = run_sparql(compoundwikiEP, sparqlquery)
    except Exception:
        app.logger.exception("Compound query failed")
        return jsonify({"error": "Upstream query failed"}), 500
    if not bool(compound_dat):
        return jsonify({"error": "No data found"}), 404
    if len(compound_dat["results"]["bindings"]) == 0:
        return jsonify({"error": "No data found"}), 404
    compound_dat = compound_dat["results"]["bindings"][0]
    qid = compound_dat["qid"]["value"]
    if not re.fullmatch(r"http://www\.wikidata\.org/entity/Q\d+", qid):
        return jsonify({"error": "No data found"}), 404
    # the next query may be affected by https://github.com/ad-freiburg/qlever-control/issues/187
    sparqlquery = (
        "PREFIX wd: <http://www.wikidata.org/entity/>\n"
        "PREFIX wdt: <http://www.wikidata.org/prop/direct/>\n"
        "PREFIX prov: <http://www.w3.org/ns/prov#>\n"
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        "PREFIX pr: <http://www.wikidata.org/prop/reference/>\n"
        "PREFIX wikibase: <http://wikiba.se/ontology#>\n\n"
        "SELECT DISTINCT ?propEntityLabel ?value ?unitsLabel ?source ?doi ?statement\n"
        "WHERE {\n"
        "    <" + qid + "> ?propp ?statement .\n"
        "    ?statement a wikibase:BestRank ;\n"
        "      ?proppsv [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?units ] .\n"
        "    #OPTIONAL { ?statement prov:wasDerivedFrom/pr:P248 ?sourceTmp . OPTIONAL { ?sourceTmp wdt:P356 ?doiTmp . } }\n"
        "    ?property wikibase:claim ?propp ; wikibase:statementValue ?proppsv ; wdt:P1629 ?propEntity ; wdt:P31 wd:Q21077852 .\n"
        "    ?propEntity @en@rdfs:label ?propEntityLabel .\n"
        "    ?units @en@rdfs:label ?unitsLabel .\n"
        '    BIND (COALESCE(IF(BOUND(?sourceTmp), ?sourceTmp, 1/0), "") AS ?source)\n'
        '    BIND (COALESCE(IF(BOUND(?doiTmp), ?doiTmp, 1/0), "") AS ?doi)\n'
        "}"
    )
    # return sparqlquery
    try:
        sparqlqueryURL = (
            "https://qlever.dev/api/wikidata?format=json&query="
            + urllib.parse.quote_plus(sparqlquery)
        )
        # return sparqlqueryURL
        compound_dat = requests.get(sparqlqueryURL, timeout=10)
        # return json.loads(compound_dat.content)
    except Exception:
        app.logger.exception("Compound query failed")
        return jsonify({"error": "Upstream query failed"}), 500
    if not bool(compound_dat):
        return jsonify({"error": "No data found"}), 404
    compound_dat = json.loads(compound_dat.content)["results"]["bindings"]
    # return jsonify(compound_dat)
    compound_list = []
    for expProp in compound_dat:
        # return jsonify(expProp)
        compound_list.append(
            {
                "propEntityLabel": expProp["propEntityLabel"]["value"],
                "value": expProp["value"]["value"],
                "unitsLabel": expProp["unitsLabel"]["value"],
                "source": expProp["source"]["value"],
                "doi": expProp["doi"]["value"],
                "seeAlso": expProp["statement"]["value"],
            }
        )
    return jsonify(compound_list), 200


################################################################################
### Pages under 'Legal'
@app.route("/legal/terms_of_service")
def terms_of_service():
    return render_template(
        "legal/terms_of_service.html",
        page=page_record("legal/terms_of_service"),
        page_title="Terms of Service — VHP4Safety",
        meta_description="Terms of Service for the VHP4Safety Virtual Human Platform.",
    )


@app.route("/legal/privacypolicy")
def privacy_policy():
    return render_template(
        "legal/privacypolicy.html",
        page=page_record("legal/privacypolicy"),
        page_title="Privacy Policy — VHP4Safety",
        meta_description="Privacy Policy for the VHP4Safety Virtual Human Platform.",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=os.environ.get("FLASK_DEBUG") == "1")
