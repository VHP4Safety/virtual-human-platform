################################################################################
### Loading the required modules
import json
import os
import re
import secrets
import time

import nh3
import requests
import urllib.parse
from flask import Flask, abort, g, jsonify, render_template, request, Response, url_for
from flask_caching import Cache
from jinja2 import TemplateNotFound
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

# Import BioStudies extractor
from data.biostudies.search import BioStudiesExtractor
from data.zenodo.search import ZenodoExtractor
from data.mapping import normalize_all, scrub_draft
from database import records
from linkeddata import documents, outline, pages, storage, void
from linkeddata.model import hierarchy, settings
from routes.account import blueprint as account_blueprint
from routes import limiter, records_api
from routes.changes import blueprint as changes_blueprint
from routes.discovery import blueprint as discovery_blueprint
from routes.sources import blueprint as sources_blueprint
from routes.editor import blueprint as admin_blueprint
from routes.images import blueprint as images_blueprint
from routes.record_pages import blueprint as pages_blueprint
from routes.record_pages import listing_page, page_link, record_page

################################################################################
CACHE_TIMEOUT = 60 * 60 * 24 * 5  # 5 days
### Configuration for BioStudies Integration
# Change these variables to switch between collections
BIOSTUDIES_COLLECTION = "VHP4Safety"  # Replace with "EU-ToxRisk" to test
BIOSTUDIES_COLLECTION_NAME = "VHP4Safety"  # Display name for the page
ZENODO_COMMUNITY = "vhp4safety"  # zenodo community
ZENODO_RECORD_TYPE = "dataset"  # only show datasets

# Non-glossary "stage" labels. The five Process Flow Step stages are resolved
# from the glossary's records (see get_process_flow_steps); these legacy
# labels stay hardcoded because the data/models pages still reference them by
# literal key and their data sources have not migrated to the glossary URIs.
STAGE_EXPLANATIONS_LEGACY = {
    "Other": "Other or unknown category.",
    "ADME": "Absorption, distribution, metabolism, and excretion of a substance (toxic or not) in a living organism, following exposure to this substance.",
    "Hazard Assessment": "The process of assessing the intrinsic hazard a substance poses to human health and/or the environment",
    "Chemical Information": "Information about chemical properties and identity.",
    "General": "Not specific to a flow step.",
    "(External) exposure": "External exposure assessment.",
    "Generic": "Generic category.",
}

# Legacy glossary-URI -> stage-label mappings, superseded by the Process Flow
# Step URIs that get_process_flow_steps() gives from the glossary's records.
STAGE_MAPPING_LEGACY = {
    "https://vhp4safety.github.io/glossary#VHP0000056": "ADME",
    "https://vhp4safety.github.io/glossary#VHP0000102": "Hazard Assessment",
    "https://vhp4safety.github.io/glossary#VHP0000148": "Chemical Information",
    "https://vhp4safety.github.io/glossary#VHP0000149": "General",
}
METHODS_URL = "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/methods_index.json"
# TOOLS and SERVICES are synonymous
SERVICES_URL = "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/service_index.json"
CASESTUDIES_URL = (
    "https://raw.githubusercontent.com/VHP4Safety/ui-casestudy-config/"
    "refs/heads/main/ro-crate-metadata.json"
)
# Case-study content is only fetched from the config repository.
CASESTUDY_CONTENT_PREFIX = "https://raw.githubusercontent.com/VHP4Safety/ui-casestudy-config/"
# BioStudies accessions (S-VHPS21, E-MTAB-1234) and Zenodo record ids (1234567).
DATA_ID_PATTERN = r"S-[A-Z]+\d+|E-[A-Z]+-\d+|\d+"
MAX_PAGE_SIZE = 48
CACHE_RESET_INTERVAL = 5 * 60  # seconds

# SEO defaults. Every page renders a <title>/<meta description> (see base.html);
# routes override page_title / meta_description with page-specific values, and
# inject_seo_defaults() falls back to these for anything that does not.
DEFAULT_PAGE_TITLE = "VHP4Safety — Virtual Human Platform for safety assessment"


def clip(text, limit=160):
    """Trim a description to a search-snippet-friendly length (~160 chars)."""
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def page_args(default_size: int) -> tuple[int, int]:
    """Read ?page and ?page_size from the request, kept within sensible bounds."""
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = request.args.get("page_size", default_size, type=int)
    return page, min(max(page_size, 1), MAX_PAGE_SIZE)

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


cache_config = {
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": CACHE_TIMEOUT,  # 60 min chaching
}
app = Flask(__name__)
# The scheme and host are taken from the reverse proxy, for the ORCID login.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.from_mapping(cache_config)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("SECRET_KEY"):
    app.logger.warning("SECRET_KEY is not set: logins end on restart, and fail with several workers.")
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_DEBUG") != "1"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.register_blueprint(account_blueprint)
app.register_blueprint(admin_blueprint)
limiter.init_app(app)
records_api.register(app)
app.register_blueprint(pages_blueprint)
app.register_blueprint(sources_blueprint)
app.register_blueprint(changes_blueprint)
app.register_blueprint(images_blueprint)
app.register_blueprint(discovery_blueprint)
# Google Search Console verification token (rendered as a <meta> tag in
# base.html when set). Kept out of the repo -- set it in the service env.
app.config["GOOGLE_SITE_VERIFICATION"] = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
cache = Cache(app)
# The vocabularies' class hierarchy is read once, as the app starts, not by its first request.
hierarchy()


_last_cache_reset = 0.0


@app.before_request
def handle_cache_reset():
    """Clear the entire server-side cache when ?reset_cache is in the URL.

    Open to anyone, but the cache is cleared at most once every
    CACHE_RESET_INTERVAL seconds, as each reset refetches every upstream source.
    """
    global _last_cache_reset
    if "reset_cache" in request.args and time.time() - _last_cache_reset > CACHE_RESET_INTERVAL:
        _last_cache_reset = time.time()
        cache.clear()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", "object-src 'none'; base-uri 'self'")
    return response


@app.template_filter("sanitize_html")
def sanitize_html(value) -> Markup:
    """Keep the formatting tags of upstream HTML; scripts and event handlers are removed."""
    return Markup(nh3.clean(str(value or "")))


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_json_dict_cached(url: str, timeout: int = 5) -> dict:
    """Fetch xxxx_index.json from the cloud repo and return as a dictionary."""
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"Unexpected status code {resp.status_code} for {url}")
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected JSON type for {url}")
    return data


def get_json_dict(url: str, timeout: int = 5) -> dict:
    """Fetch xxxx_index.json from the cloud repo and return as a dictionary.
    Return an empty dict on any error to avoid breaking pages that depend on it.
    """
    try:
        return _get_json_dict_cached(url, timeout=timeout)
    except Exception:
        return {}


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_service_detail_cached(tool_id: str, timeout: int = 5) -> dict:
    """Fetch a tool/service detail JSON from the cloud repo."""
    detail_url = f"https://cloud.vhp4safety.nl/service/{tool_id}.json"
    return _get_json_dict_cached(detail_url, timeout=timeout)


def get_service_detail(tool_id: str, timeout: int = 5) -> dict:
    """Fetch service detail and return an empty dict on any error."""
    if not tool_id:
        return {}
    if not re.match(r"^[A-Za-z0-9._-]+$", tool_id):
        return {}
    try:
        return _get_service_detail_cached(tool_id, timeout=timeout)
    except Exception:
        return {}


# --- Case studies & regulatory questions -----------------------------------
# (case slug, question index) -> reg_q_Xy upstream field name. This is the
# only remaining hardcoded artifact: the keys must match upstream tool/method
# index field names (used to filter records) and the casestudy config files
# do not currently record them. If a field like `upstreamField` were added to
# each question in <case>_content.json's step1Contents.questions[], this map
# could be derived from the config too.
_REG_QUESTION_KEYS = {
    ("kidney", 0): "reg_q_1a",
    ("kidney", 1): "reg_q_1b",
    ("parkinson", 0): "reg_q_2a",
    ("parkinson", 1): "reg_q_2b",
    ("thyroid", 0): "reg_q_3a",
    ("thyroid", 1): "reg_q_3b",
}


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_casestudies_cached() -> dict:
    """Fetch + parse case studies. Raises on failure so the cache does not
    store an empty/poisoned result (a transient HTTP/SSL hiccup must not stick
    around for CACHE_TIMEOUT). Public wrapper get_casestudies() catches.
    """
    resp = requests.get(CASESTUDIES_URL, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    studies = {}
    for entry in data.get("@graph", []):
        types = entry.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if "File" not in types:
            continue
        if entry.get("encodingFormat") != "application/json":
            continue
        slug = entry.get("identifier")
        if not slug:
            continue
        studies[slug] = {
            "name": entry.get("name", ""),
            "description": entry.get("description", ""),
            "content_url": entry.get("contentUrl", ""),
        }
    if not studies:
        raise ValueError("no case studies found in RO-Crate @graph")
    return studies


def get_casestudies() -> dict:
    """Return case studies from VHP4Safety/ui-casestudy-config's RO-Crate.

    The upstream metadata is an RO-Crate (`ro-crate-metadata.json`) whose
    `@graph` lists every file in the repo. Case studies are the JSON `File`
    entities with an `identifier` (the slug) and a `contentUrl` to the
    per-case content JSON.

    Returns {slug: {"name", "description", "content_url"}}. Iteration yields
    slugs, so callers that just need the slug list can do `for c in
    get_casestudies()`. Returns an empty dict on any error so callers degrade
    safely; failures are NOT cached so the next request retries.
    """
    try:
        return _get_casestudies_cached()
    except Exception:
        return {}


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_casestudy_content_cached(url: str) -> dict:
    """Fetch the per-case content JSON. Raises on failure so the cache does
    not store an empty/poisoned result. Public wrapper get_casestudy_content()
    catches.
    """
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"empty case-study content at {url}")
    return data


def get_casestudy_content(slug: str) -> dict:
    """Fetch the per-case `<slug>_content.json` from the config repo.

    Returns an empty dict on any error so callers degrade safely; failures
    are NOT cached so the next request retries. The url-not-found case skips
    the fetch entirely (returning {} without going through the cache).
    """
    url = get_casestudies().get(slug, {}).get("content_url")
    if not url or not url.startswith(CASESTUDY_CONTENT_PREFIX):
        return {}
    try:
        return _get_casestudy_content_cached(url)
    except Exception:
        return {}


def get_reg_questions() -> dict:
    """Build {reg_q_Xy: {"label", "explanation"}} from per-case content JSONs.

    Keys come from _REG_QUESTION_KEYS (upstream field names). Labels and
    explanations come from each case's step1Contents.questions[] entries in
    the remote casestudy config (label and description fields respectively).
    """
    result = {}
    for slug in get_casestudies():
        content = get_casestudy_content(slug)
        questions = (content.get("step1Contents") or {}).get("questions") or []
        for i, q in enumerate(questions[:2]):
            key = _REG_QUESTION_KEYS.get((slug, i))
            if not key:
                continue
            value = q.get("value") or f"Q{i + 1}"
            steps = ((content.get("step2Contents") or {}).get(value) or {}).get("steps") or []
            result[key] = {
                "label": q.get("label") or f"{slug.title()} Q{i + 1}",
                "explanation": q.get("description", ""),
                "case": slug,
                # the case-study page keys questions by value ("Q2"), not label
                "url": f"/casestudies/{slug}/{value}",
                # process-flow steps (lowercased) whose button is enabled there;
                # data-tab pills for any other step link to the glossary term
                "enabled_steps": [
                    (s.get("value") or "").lower()
                    for s in steps
                    if s.get("state") != "disabled"
                ],
            }
    return result


def get_reg_question_explanations() -> dict:
    """{label: explanation} for templates that look up by hardcoded label."""
    return {v["label"]: v["explanation"] for v in get_reg_questions().values()}


# The glossary term whose kinds are the process flow steps.
PROCESS_FLOW_STEP = "https://vhp4safety.github.io/glossary#VHP0000152"


def get_process_flow_steps() -> dict:
    """Return {glossary_uri: {"label", "slug", "description"}} for the glossary's process flow steps, from
    their records, by address."""
    steps = {}
    for kind in pages.kinds(PROCESS_FLOW_STEP):
        steps[kind["iri"]] = {"label": kind["label"], "slug": kind["slug"], "description": kind["description"]}
    return steps


def get_stage_explanations() -> dict:
    """Stage label -> explanation: the glossary Process Flow Steps merged with
    the non-glossary legacy labels still used by the data/models pages.
    """
    glossary = {
        step["label"]: step["description"] for step in get_process_flow_steps().values()
    }
    return {**glossary, **STAGE_EXPLANATIONS_LEGACY}


def get_stage_mapping() -> dict:
    """Glossary URI -> stage label: the Process Flow Step URIs resolved from the
    glossary merged with the legacy URI mappings.
    """
    glossary = {uri: step["label"] for uri, step in get_process_flow_steps().items()}
    return {**glossary, **STAGE_MAPPING_LEGACY}


def linked_tools(catalogue: dict) -> dict:
    """The cloud catalogue's tools with their records' values; tools removed or
    moved on the platform are left out, and tools added on it are put in.
    """
    removed = records.removed("tools") | records.moved("tools")
    tools = {}
    for tool_id, tool in catalogue.items():
        if tool_id not in removed:
            tools[tool_id] = dict(tool)
    stage_mapping = get_stage_mapping()
    listed = records.of_kind("tools")
    statements = storage.graph([record.iri for record in listed])
    for record in listed:
        tool_id = record.iri.rsplit("/", 1)[-1]
        tool = tools.setdefault(tool_id, {"id": tool_id, "stage": "Unknown", "main_url": "no_url"})
        descriptions = documents.stored_values(statements, record.iri, "description")
        urls = documents.stored_values(statements, record.iri, "url")
        images = documents.stored_values(statements, record.iri, "image")
        about = documents.stored_values(statements, record.iri, "about")
        tool["service"] = record.name or tool_id
        tool["description"] = descriptions[0] if descriptions else ""
        tool["main_url"] = urls[0] if urls else "no_url"
        tool["png_file_name"] = page_link(images[0]) if images else None
        for iri in about:
            if iri in stage_mapping:
                tool["stage"] = iri
        # The regulatory questions a record links become the catalogue's reg_q_Xy flags.
        for (case, number), field in _REG_QUESTION_KEYS.items():
            tool[field] = str(records.address(f"casestudies/{case}/Q{number + 1}") in about).lower()
    return tools


def linked_methods() -> dict:
    """The platform's method records, shaped as the cloud catalogue's methods index for the methods pages."""
    stage_mapping = get_stage_mapping()
    cases = records.address("casestudies/")
    methods = {}
    listed = records.of_kind("methods")
    statements = storage.graph([record.iri for record in listed])
    for record in listed:
        method_id = record.iri.rsplit("/", 1)[-1]
        descriptions = documents.stored_values(statements, record.iri, "description")
        urls = documents.stored_values(statements, record.iri, "url")
        method = {
            "id": method_id,
            "method": record.name or method_id,
            "method_description_content": descriptions[0] if descriptions else "",
            "catalog_webpage_url": urls[0] if urls else "",
        }
        stages = []
        for value in documents.stored_values(statements, record.iri, "about"):
            if value.startswith(cases):
                case, question = value.removeprefix(cases).split("/")[:2]
                method["case_study"] = case
                if question[1:].isdigit():
                    method["regulatory_question"] = _REG_QUESTION_KEYS.get((case, int(question[1:]) - 1), "")
            elif value in stage_mapping or value in stage_mapping.values():
                stages.append(value)
        method["vhp4safety_workflow_stage_content"] = ", ".join(stages)
        methods[method_id] = method
    return methods


class _RepositoryFetchAllFailed(Exception):
    """Both extractors returned error-shaped dicts. Carries the original
    tuple so the public wrapper can return it without re-fetching."""


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_repository_data_cached(
    search_query: str,
    page: int = 1,
    page_size: int = 18,
    filters: list | None = None,
    load_metadata: bool = True,
) -> tuple[dict, dict]:
    """Fetch from BioStudies + Zenodo. The extractors swallow network failures
    and return {"error": "..."} dicts rather than raising, so we check the
    result here and raise if BOTH halves errored -- otherwise cache.memoize
    would store the dual-error tuple for CACHE_TIMEOUT and every subsequent
    request would see the same stale failure. Partial success is cacheable
    (the errored half stays until the timeout, but the working half remains
    usable).
    """
    bs_extractor = BioStudiesExtractor(collection=BIOSTUDIES_COLLECTION)
    if search_query:
        bs_results = bs_extractor.search_studies(
            search_query,
            page=page,
            page_size=page_size,
            filters=filters,
            load_metadata=load_metadata,
        )
    else:
        bs_results = bs_extractor.list_studies(
            page=page,
            page_size=page_size,
            include_urls=True,
            filters=filters,
            load_metadata=load_metadata,
        )

    zen_extractor = ZenodoExtractor(
        community=ZENODO_COMMUNITY, record_type=ZENODO_RECORD_TYPE
    )
    if not filters:
        # We currently do no filter Zenodo datasets.
        if search_query:
            zen_result = zen_extractor.search_records(
                search_query, page=page, size=page_size, load_metadata=load_metadata
            )
        else:
            # load metadata needed for is_rocrate filtering in template
            zen_result = zen_extractor.list_records(
                page=page,
                size=page_size,
                include_urls=True,
                load_metadata=load_metadata,
            )
    else:
        zen_result = {"hits": [], "total": 0, "error": None}

    # Both extractors errored -> bypass the cache by raising. The wrapper
    # catches and returns the same tuple to the caller (contract preserved),
    # but the next request will retry instead of getting the cached failure.
    if bs_results.get("error") and zen_result.get("error"):
        raise _RepositoryFetchAllFailed((bs_results, zen_result))

    return bs_results, zen_result


def get_repository_data(
    search_query: str,
    page: int = 1,
    page_size: int = 18,
    filters: list | None = None,
    load_metadata: bool = True,
) -> tuple[dict, dict]:
    """Return (bs_results, zen_result) from the two repositories.

    Each half is the extractor's raw response: a {"hits", "total"} dict on
    success or a {"error": "..."} dict on failure. A dual-failure result is
    NOT cached so the next request retries; partial success is cached as-is.
    """
    try:
        return _get_repository_data_cached(
            search_query,
            page=page,
            page_size=page_size,
            filters=filters,
            load_metadata=load_metadata,
        )
    except _RepositoryFetchAllFailed as exc:
        return exc.args[0]


def menu(kind: str) -> list[dict]:
    """A kind's records for the navigation menus and the search bar: each one's identifier, name and page, by
    name."""
    listed = []
    for record in records.of_kind(kind):
        if record.part_of is None:
            listed.append({"id": record.iri.rsplit("/", 1)[-1], "title": record.name or record.iri, "url": page_link(record.iri)})
    listed.sort(key=lambda item: item["title"].lower())
    return listed


@app.context_processor
def inject_menus():
    """The tools, methods and data of the navigation menus and the search bar, from their records."""
    return {"tools_menu": menu("tools"), "methods_menu": menu("methods"), "data_menu": menu("data")}


def data_hit_id(hit: dict) -> str:
    """Return the identifier to use in a /data/<id> URL for a repository hit.

    BioStudies hits resolve to their accession; Zenodo hits to their numeric
    recid. doi_url is intentionally never used -- it contains slashes the
    /data/<dataid> route's string converter cannot match.
    """
    return (
        hit.get("accession")
        or hit.get("accno")
        or hit.get("id")
        or hit.get("recid")
        or ""
    )


@app.context_processor
def inject_seo_defaults():
    """Provide SEO defaults so every page has a title/description/canonical.

    Routes override page_title / meta_description via render_template kwargs
    (explicit context wins over context processors). canonical_url defaults to
    a record's own address on its page, else the page's path at the platform's
    address, so that copies of the platform are not indexed as the platform.
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
    """The platform's catalogue: its record, its kinds of records with their counts, the workflow page's
    summary with the process flow steps, and its publisher's partners."""
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


def data_hit_id(hit: dict) -> str:
    """Return the identifier to use in a /data/<id> URL for a repository hit.

    BioStudies hits resolve to their accession; Zenodo hits to their numeric
    recid. doi_url is intentionally never used -- it contains slashes the
    /data/<dataid> route's string converter cannot match.
    """
    return (
        hit.get("accession")
        or hit.get("accno")
        or hit.get("id")
        or hit.get("recid")
        or ""
    )


################################################################################
### The sitemap.xml for search engines
@app.route("/sitemap.xml")
def sitemap():
    """The static pages, and each record's page with its last change."""
    BASE = "https://platform.vhp4safety.nl"

    # Static, parameter-less GET pages, derived from the URL map so new pages
    # are picked up automatically. Machine endpoints are excluded. Routes with
    # <params> are skipped and handled below.
    EXCLUDED_ENDPOINTS = {"sitemap", "robots", "static"}
    # The pages for editors (login, tokens, editing, changes) and the API are left out.
    EXCLUDED_BLUEPRINTS = {"account", "admin", "changes", "api", "api-docs"}
    paths = sorted(
        rule.rule.rstrip("/") or "/"
        for rule in app.url_map.iter_rules()
        if not rule.arguments
        and rule.endpoint not in EXCLUDED_ENDPOINTS
        and rule.endpoint.split(".")[0] not in EXCLUDED_BLUEPRINTS
        and "GET" in (rule.methods or set())
    )
    listed = records.with_pages()
    with_pages = {address.rstrip("/") for address, _ in listed}
    # A static page that is also a record's page, such as the home page, is listed once, with its last change.
    entries = [f"  <url>\n    <loc>{BASE}{p}</loc>\n  </url>" for p in paths if f"{BASE}{p}".rstrip("/") not in with_pages]
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
        "Sitemap: https://platform.vhp4safety.nl/sitemap.xml\n"
    )
    return Response(robotsContent, mimetype="text/plain")


################################################################################
### Pages under 'Data'
@app.route("/data")
def data():
    """The datasets, from their records (templates/records/listing.html)."""
    return listing_page("data")


################################################################################
### DataSet detail view


@app.template_filter("split_text_int")
def split_text_int(value: None | str) -> tuple[str, None | int]:
    """
    Splits trailing integer from a string.
    'S-VHPS21' -> ('S-VHPS', 21)
    'ABC'      -> ('ABC', None)
    'X-12A'    -> ('X-12A', None)   # only splits if digits are at the very end
    """
    # used to construct ftp file link *POTENTIALLY BRITTLE*
    if value is None:
        return ("", None)

    s = str(value)
    m = re.match(r"^(.*?)(\d+)$", s)
    if not m:
        return (s, None)

    return (m.group(1), int(m.group(2)))


@app.route("/data/<dataid>")
def data_detail(dataid):
    """A dataset's page, from its record."""
    record = records.get(records.address(f"data/{dataid}"))
    if record is None:
        abort(404)
    return record_page(record)


################################################################################
### Pages under 'Tools'


### Here begins the updated version for creating the tool list page.
@app.route("/tools")
def tools():
    """The tools, from their records (templates/records/listing.html)."""
    return listing_page("tools")


### New route to list methods (similar to the tools page)
@app.route("/methods")
@app.route("/methods/")
def methods():
    """The methods, from their records (templates/records/listing.html)."""
    return listing_page("methods")


@app.route("/methods/<methodid>")
def method_page(methodid):
    """Render a method page (templates/methods/method.html) from its record, with the profile's field names."""
    record = records.get(records.address(f"methods/{methodid}"))
    if record is None:
        abort(404)
    method = documents.view(record)
    method_name = record.name or methodid
    descriptions = documents.stored_values(storage.graph([record.iri]), record.iri, "description")
    return render_template(
        "methods/method.html",
        method=method,
        method_details=method,
        method_json=method,
        updated=record.updated_at,
        page_title=f"{method_name} — VHP4Safety",
        meta_description=clip(descriptions[0] if descriptions else "")
        or f"{method_name}, a method in the VHP4Safety Virtual Human Platform.",
    )


@app.route("/tools/<toolname>")
def tool_page(toolname):
    """Render a tool page (templates/tools/tool.html) from its record, with the profile's field names."""
    record = records.get(records.address(f"tools/{toolname}"))
    if record is None:
        abort(404)
    tool = documents.view(record)
    tool_name = record.name or toolname
    description = tool.get("description")
    if isinstance(description, dict):
        description = description.get("@value")
    return render_template(
        "tools/tool.html",
        tool_details=tool,
        process_flow_steps=get_process_flow_steps(),
        page_title=f"{tool_name} — VHP4Safety",
        meta_description=clip(description)
        or f"{tool_name}, a tool in the VHP4Safety Virtual Human Platform.",
    )


################################################################################
### Pages under 'Case Studies'


# General case studies page
@app.route("/casestudies")
def workflows():
    """The case studies, from their records: each one's name, aim and icon."""
    listed = [record for record in records.of_kind("casestudies") if record.part_of is None]
    statements = storage.graph([record.iri for record in listed])
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
    """A case study's page from its record: its content for readers without scripts, then the page drawn by
    static/js/case-study.js at the address asked for. Its question and step addresses are views of the same
    page, so they all have the case study's address as canonical."""
    record = records.get(records.address(f"casestudies/{case}"))
    if record is None:
        abort(404)
    found = outline.outline(record)
    descriptions = [field["values"][0] for field in found["fields"] if field["name"] == "description"]
    return render_template(
        "case_studies/casestudy.html",
        case_outline=found,
        case_document=url_for("api.read", path=f"casestudies/{case}"),
        page_address=records.address(request.path.strip("/")),
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=os.environ.get("FLASK_DEBUG") == "1")
