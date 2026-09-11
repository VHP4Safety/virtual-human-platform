################################################################################
### Loading the required modules
import json
import os
import re

import requests
import urllib.parse
from flask import Flask, abort, jsonify, render_template, request, Response
from flask_caching import Cache
from jinja2 import TemplateNotFound
from werkzeug.routing import BaseConverter

# from wikidataintegrator import wdi_core
from wikibaseintegrator import wbi_helpers

# Import BioStudies extractor
from data.biostudies.search import BioStudiesExtractor
from data.zenodo.search import ZenodoExtractor
from data.mapping import normalize_all, scrub_draft

################################################################################
CACHE_TIMEOUT = 60 * 60 * 24 * 5  # 5 days
### Configuration for BioStudies Integration
# Change these variables to switch between collections
BIOSTUDIES_COLLECTION = "VHP4Safety"  # Replace with "EU-ToxRisk" to test
BIOSTUDIES_COLLECTION_NAME = "VHP4Safety"  # Display name for the page
ZENODO_COMMUNITY = "vhp4safety"  # zenodo community
ZENODO_RECORD_TYPE = "dataset"  # only show datasets
ZENODO_RECORD_TYPE_MODEL = "model"  # only show datasets

# Non-glossary "stage" labels. The five Process Flow Step stages are resolved
# from the VHP glossary at runtime (see get_process_flow_steps); these legacy
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
# Step URIs that get_process_flow_steps() resolves from the glossary.
STAGE_MAPPING_LEGACY = {
    "https://vhp4safety.github.io/glossary#VHP0000056": "ADME",
    "https://vhp4safety.github.io/glossary#VHP0000102": "Hazard Assessment",
    "https://vhp4safety.github.io/glossary#VHP0000148": "Chemical Information",
    "https://vhp4safety.github.io/glossary#VHP0000149": "General",
}
METHODS_URL = "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/methods_index.json"
# TOOLS and SERVICES are synonymous
SERVICES_URL = "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/service_index.json"
GLOSSARY_URL = (
    "https://raw.githubusercontent.com/VHP4Safety/glossary/refs/heads/main/glossary.owl"
)
CASESTUDIES_URL = (
    "https://raw.githubusercontent.com/VHP4Safety/ui-casestudy-config/"
    "refs/heads/main/ro-crate-metadata.json"
)

# SEO defaults. Every page renders a <title>/<meta description> (see base.html);
# routes override page_title / meta_description with page-specific values, and
# inject_seo_defaults() falls back to these for anything that does not.
DEFAULT_PAGE_TITLE = "VHP4Safety — Virtual Human Platform for safety assessment"
DEFAULT_META_DESCRIPTION = (
    "The Virtual Human Platform (VHP4Safety) brings together tools, methods, "
    "data and case studies for animal-free, human-based safety assessment of "
    "chemicals and pharmaceuticals."
)


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


cache_config = {
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": CACHE_TIMEOUT,  # 60 min chaching
}
app = Flask(__name__)
app.config.from_mapping(cache_config)
# Google Search Console verification token (rendered as a <meta> tag in
# base.html when set). Kept out of the repo -- set it in the service env.
app.config["GOOGLE_SITE_VERIFICATION"] = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
cache = Cache(app)


@app.before_request
def handle_cache_reset():
    """Clear the entire server-side cache when ?reset_cache is in the URL.

    Unprotected by design: a stranger forcing a refetch is low-impact (just
    repopulates the cache from the upstream indexes), and keeping it open
    removes a config knob (no CACHE_RESET_TOKEN env var needed).
    """
    if "reset_cache" in request.args:
        cache.clear()


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
    if not url:
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
            result[key] = {
                "label": q.get("label") or f"{slug.title()} Q{i + 1}",
                "explanation": q.get("description", ""),
                "case": slug,
            }
    return result


def get_reg_question_explanations() -> dict:
    """{label: explanation} for templates that look up by hardcoded label."""
    return {v["label"]: v["explanation"] for v in get_reg_questions().values()}


# Suffix the VHP glossary uses to mark an owl:Class as a Process Flow Step stage.
_PROCESS_FLOW_STEP_SUFFIX = " (Process Flow Step)"
# Matches a Turtle quoted literal, tolerating backslash escapes.
_TTL_QUOTED = r'"((?:[^"\\]|\\.)*)"'


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_process_flow_steps_cached() -> dict:
    """Fetch + parse Process Flow Steps from the glossary. Raises on failure
    so the cache does not store an empty/poisoned result (the raw.github CDN
    intermittently resets the connection; we must not keep that empty result
    around for CACHE_TIMEOUT). Public wrapper get_process_flow_steps() catches.
    """
    resp = requests.get(GLOSSARY_URL, timeout=5)
    resp.raise_for_status()
    # Normalise line endings so the block split works regardless of CRLF / LF
    ttl = resp.text.replace("\r\n", "\n")

    steps = {}
    # The glossary is Turtle with one blank-line-separated block per subject.
    for block in ttl.split("\n\n"):
        m_subj = re.match(r"\s*<([^>]+)>", block)
        m_label = re.search(r"rdfs:label\s+" + _TTL_QUOTED, block)
        if not (m_subj and m_label):
            continue
        label = m_label.group(1)
        if not label.endswith(_PROCESS_FLOW_STEP_SUFFIX):
            continue
        m_desc = re.search(r"dc:description\s+" + _TTL_QUOTED, block)
        clean_label = label[: -len(_PROCESS_FLOW_STEP_SUFFIX)].strip()
        steps[m_subj.group(1)] = {
            "label": clean_label,
            # URL/id-safe anchor slug, computed once here so the templates that
            # link to it (home.html) and define it (the accordion) can't drift.
            "slug": clean_label.lower().replace(" ", "-"),
            "description": (m_desc.group(1) if m_desc else "").strip(),
        }
    # sort by id
    sort_ids = [
        "https://vhp4safety.github.io/glossary#VHP0000153",
        "https://vhp4safety.github.io/glossary#VHP0000154",
        "https://vhp4safety.github.io/glossary#VHP0000155",
        "https://vhp4safety.github.io/glossary#VHP0000156",
        "https://vhp4safety.github.io/glossary#VHP0000158",
    ]
    steps = dict(
        sorted(
            steps.items(),
            key=lambda item: (
                sort_ids.index(item[0]) if item[0] in sort_ids else len(sort_ids)
            ),
        )
    )
    if not steps:
        raise ValueError("no Process Flow Step entries found in glossary")
    return steps


def get_process_flow_steps() -> dict:
    """Return {glossary_uri: {"label", "slug", "description"}} for every
    owl:Class whose rdfs:label ends with " (Process Flow Step)". Returns an
    empty dict on any error so callers degrade safely; failures are NOT cached
    so the next request retries.
    """
    try:
        return _get_process_flow_steps_cached()
    except Exception:
        return {}


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


# --- Partner logos ----------------------------------------------------------
PARTNERS_DIR = os.path.join(app.static_folder, "images", "partners")
PARTNERS_FILE = os.path.join(PARTNERS_DIR, "partners.txt")
_PARTNER_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp")


def get_partner_logos() -> list:
    """Return partner logos from static/images/partners/.

    Each item is a dict {"file": ..., "name": ..., "url": ...}. Order, names
    and links come from partners.txt, whose entries are
    "filename | Organization name | https://link" (name and link optional);
    blank lines and '#' comments are ignored. Only files explicitly listed in
    partners.txt are returned — images present in the directory but not
    registered (or commented out) are not displayed.
    """
    try:
        images = {
            f
            for f in os.listdir(PARTNERS_DIR)
            if f.lower().endswith(_PARTNER_IMAGE_EXTS)
        }
    except OSError:
        return []

    logos = []
    used = set()
    try:
        with open(PARTNERS_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                fname = parts[0]
                if fname in images and fname not in used:
                    used.add(fname)
                    logos.append(
                        {
                            "file": fname,
                            "name": (
                                parts[1]
                                if len(parts) > 1 and parts[1]
                                else os.path.splitext(fname)[0]
                            ),
                            "url": parts[2] if len(parts) > 2 else "",
                        }
                    )
    except OSError:
        pass

    return logos


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


@cache.memoize(timeout=CACHE_TIMEOUT)
def _get_repository_model_cached(
    search_query: str,
    page: int = 1,
    page_size: int = 18,
    filters: list | None = None,
    load_metadata: bool = True,
) -> tuple[dict, dict]:
    """Fetch from Zenodo. The extractors swallow network failures
    and return {"error": "..."} dicts rather than raising, so we check the
    result here and raise if BOTH halves errored -- otherwise cache.memoize
    would store the dual-error tuple for CACHE_TIMEOUT and every subsequent
    request would see the same stale failure. Partial success is cacheable
    (the errored half stays until the timeout, but the working half remains
    usable).
    """
    zen_extractor = ZenodoExtractor(
        community=ZENODO_COMMUNITY, record_type=ZENODO_RECORD_TYPE_MODEL
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
    if zen_result.get("error"):
        raise _RepositoryFetchAllFailed((bs_results, zen_result))

    return zen_result


def get_repository_model(
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
        return _get_repository_model_cached(
            search_query,
            page=page,
            page_size=page_size,
            filters=filters,
            load_metadata=load_metadata,
        )
    except _RepositoryFetchAllFailed as exc:
        return exc.args[0]


# Provide methods list to all templates for the Methods dropdown in the navbar
@app.context_processor
def inject_methods_menu():
    """Fetch methods_index.json and expose a simple list of {id, title} to templates.
    Return an empty list on any error to avoid breaking pages.
    """
    data = get_json_dict(METHODS_URL)
    if data:
        items = []
        for key, val in data.items() if isinstance(data, dict) else []:
            title = (
                val.get("method")
                or val.get("method_name_content")
                or val.get("method_name")
                or key
            )
            items.append({"id": key, "title": title})
        # sort by title
        items = sorted(items, key=lambda x: x["title"].lower())
        return {"methods_menu": items}
    else:
        return {"methods_menu": []}


@app.context_processor
def inject_tools_menu():
    """Fetch methods_index.json and expose a simple list of {id, title} to templates.
    Return an empty list on any error to avoid breaking pages.
    """
    data = get_json_dict(SERVICES_URL)
    if data:
        items = []
        for key, val in data.items() if isinstance(data, dict) else []:
            title = val.get("service") or key
            items.append({"id": key, "title": title})
        # sort by title
        items = sorted(items, key=lambda x: x["title"].lower())
        return {"tools_menu": items}
    else:
        return {"tools_menu": []}


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
def inject_data_menu():
    """Fetch methods_index.json and expose a simple list of {id, title} to templates.
    Return an empty list on any error to avoid breaking pages.
    """
    bs_results, zen_results = get_repository_data(search_query="")
    hits: list = bs_results.get("hits", [])
    hits.extend(zen_results.get("hits", []))
    if hits:
        items = []
        for hit in hits:
            title = hit.get("title")
            id = hit.get("accession", "") or hit.get("doi_url", "") or hit.get("id", "")
            url = hit.get("url", "") or hit.get("doi_url")
            items.append({"id": id, "title": title, "url": url})
        # sort by title
        items = sorted(items, key=lambda x: x["title"].lower())
        return {"data_menu": items}
    else:
        return {"data_menu": []}


@app.context_processor
def inject_seo_defaults():
    """Provide SEO defaults so every page has a title/description/canonical.

    Routes override page_title / meta_description via render_template kwargs
    (explicit context wins over context processors). canonical_url defaults to
    the current URL without its query string (request.base_url).
    """
    return {
        "page_title": DEFAULT_PAGE_TITLE,
        "meta_description": DEFAULT_META_DESCRIPTION,
        "canonical_url": request.base_url,
    }


################################################################################
### The landing page
@app.route("/")
def home():
    try:
        tools = get_json_dict(
            SERVICES_URL
        )  # Geting the service_list.json in the dictionary format.
        tools = list(tools.values())  # Converting the dictionary to a list object.
    except Exception as e:
        return f"Error processing service data: {e}", 500
    num_tools = len(tools)
    num_case_studies = len(get_casestudies())
    try:
        methods = get_json_dict(METHODS_URL)
        num_methods = len(methods) if isinstance(methods, dict) else 0
    except Exception:
        num_methods = 0
    bs_res, zen_res = get_repository_data(search_query="")
    num_datasets = bs_res.get("total", 0) + zen_res.get("total", 0)
    return render_template(
        "home.html",
        num_tools=num_tools,
        num_case_studies=num_case_studies,
        num_methods=num_methods,
        num_datasets=num_datasets,
        process_flow_steps=get_process_flow_steps(),
        partner_logos=get_partner_logos(),
        page_title=DEFAULT_PAGE_TITLE,
        meta_description=DEFAULT_META_DESCRIPTION,
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
@cache.memoize(timeout=CACHE_TIMEOUT)
def sitemap():
    BASE = "https://platform.vhp4safety.nl"

    # Static, parameter-less GET pages, derived from the URL map so new pages
    # are picked up automatically. Machine endpoints are excluded. Routes with
    # <params> are skipped and handled below.
    EXCLUDED_ENDPOINTS = {"sitemap", "robots", "static"}
    paths = sorted(
        rule.rule.rstrip("/") or "/"
        for rule in app.url_map.iter_rules()
        if not rule.arguments
        and rule.endpoint not in EXCLUDED_ENDPOINTS
        and "GET" in (rule.methods or set())
    )

    # Tool detail pages
    tools = get_json_dict(SERVICES_URL)
    if isinstance(tools, dict):
        paths += [f"/tools/{urllib.parse.quote(str(k))}" for k in tools]

    # Method detail pages
    methods = get_json_dict(METHODS_URL)
    if isinstance(methods, dict):
        paths += [f"/methods/{urllib.parse.quote(str(k))}" for k in methods]

    # Dataset detail pages (BioStudies + Zenodo). Fetched in pages of 25 (the
    # Zenodo API rejects larger page sizes) and looped until both sources are
    # exhausted. load_metadata=False keeps this cheap (no per-file HEAD requests).
    # A repo failure must never 500 the sitemap; tools/methods/case studies still
    # serve.
    DATA_PAGE_SIZE = 25
    try:
        page = 1
        while True:
            bs_results, zen_results = get_repository_data(
                search_query="",
                page=page,
                page_size=DATA_PAGE_SIZE,
                load_metadata=False,
            )
            bs_hits = (bs_results or {}).get("hits", [])
            zen_hits = (zen_results or {}).get("hits", [])
            for hit in bs_hits + zen_hits:
                hit_id = data_hit_id(hit)
                if hit_id:
                    paths.append(f"/data/{urllib.parse.quote(str(hit_id))}")
            total = max(
                (bs_results or {}).get("total") or 0,
                (zen_results or {}).get("total") or 0,
            )
            if (not bs_hits and not zen_hits) or page * DATA_PAGE_SIZE >= total:
                break
            page += 1
    except Exception:
        pass

    # Case study detail pages
    paths += [f"/casestudies/{urllib.parse.quote(c)}" for c in get_casestudies()]

    # Dedupe while preserving order
    seen = set()
    unique_paths = [p for p in paths if not (p in seen or seen.add(p))]

    url_entries = "\n".join(
        f"  <url>\n    <loc>{BASE}{p}</loc>\n  </url>" for p in unique_paths
    )
    sitemapContent = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{url_entries}\n"
        "</urlset>\n"
    )
    return Response(sitemapContent, mimetype="text/xml")


################################################################################
### robots.txt points crawlers at the sitemap so the detail pages get indexed
@app.route("/robots.txt")
def robots():
    robotsContent = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: https://platform.vhp4safety.nl/sitemap.xml\n"
    )
    return Response(robotsContent, mimetype="text/plain")


################################################################################
### Pages under 'Data'
@app.route("/data")
def data():
    # Get query parameters for pagination and search
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 12, type=int)
    search_query = request.args.get("search", "", type=str)

    # Get filter parameters (multi-select via repeated query params). Param
    # names match tools/methods: ?case_study=, ?reg_q=, ?stage=, ?search=.
    # Each filter type is a list; the extractor groups by field and applies
    # OR-within-field, AND-across-fields.
    filter_case_study = request.args.getlist("case_study")
    filter_regulatory_question = request.args.getlist("reg_q")
    filter_flow_step = request.args.getlist("stage")

    # Build filter list (one tuple per (field, value)); repeated field names
    # become OR within that field downstream in _apply_filters.
    # The reg-question dropdown sends the question label; records store the
    # canonical reg_q_Xy key, so convert label -> key (same map methods uses).
    reg_q_label_to_key = {v["label"]: k for k, v in get_reg_questions().items()}
    filters = []
    for v in filter_case_study:
        filters.append(("case_study", v))
    for v in filter_regulatory_question:
        filters.append(("regulatory_question", reg_q_label_to_key.get(v, v)))
    for v in filter_flow_step:
        filters.append(("flow_step", v))

    # Split page budget between the two repositories so the combined output
    # respects page_size (e.g. page_size=6 -> 3 from each source).
    per_source = max(page_size // 2, 1)
    bs_results, zen_results = get_repository_data(
        search_query, page, per_source, filters=filters
    )

    # Extract studies and metadata
    studies = bs_results.get("hits", [])
    bs_total = bs_results.get("total", 0)
    bs_error: str | None = bs_results.get("error", None)

    # Extract datasets and metadata from Zenodo
    datasets = zen_results.get("hits", [])
    zen_total = zen_results.get("total", 0)
    zen_error: str | None = zen_results.get("error", None)

    # enrich with normalized metadata mapping:

    # studies, datasets = normalize_all([studies],[datasets])

    # Hide '[DRAFT]'-tagged values so the template's `{% if %}` checks skip them.
    for s in studies:
        scrub_draft(s)
    for d in datasets:
        scrub_draft(d)

    # combine totals for pagination
    total = bs_total + zen_total

    # Get filtering metadata (if filters were applied)
    filters_applied = bs_results.get("filters_applied", False)
    hits_returned = bs_results.get("hits_returned", len(studies))
    pages_fetched = bs_results.get("pages_fetched", 1)
    page_size_met = bs_results.get("page_size_met", True)

    # Calculate pagination info per source so that if one source is empty or
    # filtered out, pagination still advances through the active source.
    has_next = (page * per_source < bs_total) or (page * per_source < zen_total)
    has_prev = page > 1

    # Pass data to template
    return render_template(
        "data/data.html",
        page_title="Data — VHP4Safety",
        meta_description=(
            "Browse datasets and studies in the VHP4Safety data collection, "
            "aggregated from BioStudies and Zenodo for animal-free safety assessment."
        ),
        studies=studies,
        datasets=datasets,
        total=total,
        page=page,
        page_size=page_size,
        search_query=search_query,
        collection_name=BIOSTUDIES_COLLECTION_NAME,
        collection=BIOSTUDIES_COLLECTION,
        errors={"zenodo": zen_error, "biostudies": bs_error},
        has_next=has_next,
        has_prev=has_prev,
        filter_case_study=filter_case_study,
        filter_regulatory_question=filter_regulatory_question,
        filter_flow_step=filter_flow_step,
        filters_applied=filters_applied,
        hits_returned=hits_returned,
        pages_fetched=pages_fetched,
        page_size_met=page_size_met,
        stage_explanations=get_stage_explanations(),
        reg_question_explanations=get_reg_question_explanations(),
        reg_question_cases={v["label"]: v.get("case", "") for v in get_reg_questions().values()},
        reg_questions={v["label"]: k for k, v in get_reg_questions().items()},
        reg_q_labels={k: v["label"] for k, v in get_reg_questions().items()},
        process_flow_steps=get_process_flow_steps(),
        case_studies=list(get_casestudies()),
    )


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
    bs_results, zen_results = get_repository_data(dataid)

    studies = bs_results.get("hits", [])
    bs_total = bs_results.get("total", 0)
    bs_error: str | None = bs_results.get("error", None)

    # Extract datasets and metadata from Zenodo
    datasets = zen_results.get("hits", [])
    zen_total = zen_results.get("total", 0)
    zen_error: str | None = zen_results.get("error", None)

    studies, datasets = normalize_all(studies, datasets)
    for s in studies:
        scrub_draft(s)
    for d in datasets:
        scrub_draft(d)

    if bs_error and not zen_error:
        if zen_total != 1:
            return abort(404)
    elif zen_error and not bs_error:
        if bs_total != 1:
            return abort(404)
    # reg-question records store the canonical reg_q_Xy key; map key -> label so
    # the badges show the human-readable question.
    reg_q_labels = {k: v["label"] for k, v in get_reg_questions().items()}
    record = studies[0] if studies else (datasets[0] if datasets else None)
    if record is None:
        return abort(404)
    rec_title = record.get("title") or "Dataset"
    rec_desc = record.get("description") or record.get("abstract") or ""
    return render_template(
        "data/data_details.html",
        data=record,
        reg_q_labels=reg_q_labels,
        page_title=f"{rec_title} — VHP4Safety data",
        meta_description=clip(rec_desc)
        or f"{rec_title}: a dataset in the VHP4Safety data collection.",
    )


################################################################################
### Pages under 'Models'
@app.route("/models_page")
def models():
    # Get query parameters for pagination and search
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 18, type=int)
    search_query = request.args.get("query", "", type=str)

    # Get filter parameters
    filter_case_study = request.args.get("filter_case_study", "", type=str)
    filter_regulatory_question = request.args.get(
        "filter_regulatory_question", "", type=str
    )
    filter_flow_step = request.args.get("filter_flow_step", "", type=str)

    # Build filter list (only include non-empty filters)
    filters = []
    if filter_case_study:
        filters.append(("case_study", filter_case_study))
    if filter_regulatory_question:
        filters.append(("regulatory_question", filter_regulatory_question))
    if filter_flow_step:
        filters.append(("flow_step", filter_flow_step))

    # Initialize extractor
    extractor = BioStudiesExtractor(collection=BIOSTUDIES_COLLECTION)

    # Fetch data based on search query or list all
    if search_query:
        results = extractor.search_studies(
            search_query, page=page, page_size=page_size, filters=filters
        )
    else:
        results = extractor.list_studies(
            page=page, page_size=page_size, include_urls=True, filters=filters
        )

    # Extract studies and metadata
    studies = results.get("hits", [])
    total = results.get("total", 0)
    error = results.get("error", None)

    # Get filtering metadata (if filters were applied)
    filters_applied = results.get("filters_applied", False)
    hits_returned = results.get("hits_returned", len(studies))
    pages_fetched = results.get("pages_fetched", 1)
    page_size_met = results.get("page_size_met", True)

    # Calculate pagination info
    has_next = (page * page_size) < total
    has_prev = page > 1

    # Pass model data to template
    return render_template(
        "models_page.html",
        page_title="Models — VHP4Safety",
        meta_description=(
            "Explore computational models in the VHP4Safety Virtual Human Platform "
            "for animal-free safety assessment of chemicals and pharmaceuticals."
        ),
        studies=studies,
        total=total,
        page=page,
        page_size=page_size,
        search_query=search_query,
        collection_name=BIOSTUDIES_COLLECTION_NAME,
        collection=BIOSTUDIES_COLLECTION,
        error=error,
        has_next=has_next,
        has_prev=has_prev,
        filter_case_study=filter_case_study,
        filter_regulatory_question=filter_regulatory_question,
        filter_flow_step=filter_flow_step,
        filters_applied=filters_applied,
        hits_returned=hits_returned,
        pages_fetched=pages_fetched,
        page_size_met=page_size_met,
        stage_explanations=get_stage_explanations(),
        reg_question_explanations=get_reg_question_explanations(),
        reg_question_cases={v["label"]: v.get("case", "") for v in get_reg_questions().values()},
        reg_questions={v["label"]: k for k, v in get_reg_questions().items()},
        case_studies=list(get_casestudies()),
    )


################################################################################
### Pages under 'Tools'


### Here begins the updated version for creating the tool list page.
@app.route("/tools")
def tools():
    try:
        tools = get_json_dict(
            SERVICES_URL
        )  # Geting the service_list.json in the dictionary format.
        tools = list(tools.values())  # Converting the dictionary to a list object.

        # Glossary URI -> stage label: Process Flow Steps resolved from the VHP
        # glossary, merged with the legacy URI mappings.
        stage_mapping = get_stage_mapping()

        # Map stage URLs to readable labels up front -- needed for filtering
        # and for building the stage dropdown.
        for tool in tools:
            full_stage_url = tool.get("stage", "")
            if full_stage_url in stage_mapping:
                tool["stage"] = stage_mapping[full_stage_url]
            elif tool["stage"] in ["NA", "Unknown"]:
                # Combining "NA" and "Unknown" stages in a single stage-type, "Other".
                tool["stage"] = "Other"

        # Collect all unique stages from the UNFILTERED tools first so the
        # Flow Step dropdown is stable -- otherwise applying a filter shrinks
        # the dropdown to just the values present in the filtered set, and
        # removing a filter pill (which doesn't trigger a server reload) can't
        # restore the missing options. Matches the methods() behaviour.
        stages = sorted(set(tool.get("stage") for tool in tools if tool.get("stage")))
        if "Other" in stages:
            stages.remove("Other")
            stages.append("Other")

        # Getting selected stages from the URL.
        selected_stages = request.args.getlist("stage")

        # Filtering tools by selected stages.
        if selected_stages:
            tools = [tool for tool in tools if tool.get("stage") in selected_stages]

        # Filter by case study. Tools have no `case_study` field; membership
        # is derived from the reg_q_Xy booleans via _REG_QUESTION_KEYS
        # (e.g. selecting "Kidney" matches tools where reg_q_1a OR reg_q_1b
        # is "true"). OR within type, AND across types.
        selected_case_studies = request.args.getlist("case_study")
        if selected_case_studies:
            slugs_lc = {c.lower() for c in selected_case_studies}
            case_fields = [
                field
                for (slug, _), field in _REG_QUESTION_KEYS.items()
                if slug in slugs_lc
            ]
            if case_fields:
                tools = [
                    tool
                    for tool in tools
                    if any(str(tool.get(f, "")).lower() == "true" for f in case_fields)
                ]

        # Filtering over the regulatory questions. OR within type: a tool
        # passes if any of the selected questions' reg_q_Xy field is "true".
        # Matches the convention used by every other within-type filter on
        # the platform (flow-step, case-study, methods reg-question).
        reg_questions = {v["label"]: k for k, v in get_reg_questions().items()}

        selected_questions = request.args.getlist("reg_q")

        if selected_questions:
            fields = [
                reg_questions.get(q) for q in selected_questions if reg_questions.get(q)
            ]
            tools = [
                tool
                for tool in tools
                if any(str(tool.get(f, "")).lower() == "true" for f in fields)
            ]

        # Getting the search query from URL to add a search bar based on tool names.
        search_query = request.args.get("search", "").strip().lower()

        # Filtering tools by search query.
        if search_query:
            tools = [
                tool
                for tool in tools
                if search_query in tool.get("service", "").lower()
            ]

        # Pagination
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 12, type=int)
        total = len(tools)
        start = (page - 1) * page_size
        end = start + page_size
        tools = tools[start:end]
        has_prev = page > 1
        has_next = end < total

        # Enrich only the tools on the current page. The per-tool detail fetch
        # below makes one HTTP request per tool, so doing it after pagination
        # keeps it to ~page_size requests instead of one for every tool.
        placeholder_logo = (
            "https://github.com/VHP4Safety/ui-design/blob/main/static/images/logo.png"
        )
        for tool in tools:
            html_name = tool.get("html_name")
            md_name = tool.get("md_file_name")
            png_name = tool.get("png_file_name")

            tool["url"] = f"https://cloud.vhp4safety.nl/service/{html_name}"
            tool["meta_data"] = (
                f"https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/{md_name}"
                if md_name
                else "md file not found"
            )

            # Check if the tool has the placeholder logo; also guard against None
            if not png_name or png_name == placeholder_logo:
                tool["png"] = None  # set to None if it's the common placeholder
            else:
                tool["png"] = (
                    f"https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/{png_name}"
                    if not png_name.startswith("http")
                    else png_name
                )

            inst_url = tool.get("inst_url", "no_url")
            if not inst_url:  # catches "" as well
                inst_url = "no_url"
            tool["inst_url"] = inst_url

            # Fetch per-tool detail JSON to check hosting status
            tool_id = tool.get("id", "")
            vhp_hosted = False
            vhp_deved = False
            if tool_id:
                detail = get_service_detail(tool_id)
                if detail.get("developed-by-VHP"):
                    vhp_deved = detail.get("developed-by-VHP") == "true"
                if inst_url != "no_url":
                    vhp_platform = (
                        detail.get("instance", {}).get("vhp-platform", "").lower()
                    )
                    vhp_hosted = vhp_platform not in ("external", "independent", "")
            tool["vhp_deved"] = vhp_deved
            tool["vhp_hosted"] = vhp_hosted

        return render_template(
            "tools/tools.html",
            page_title="Tools — VHP4Safety",
            meta_description=(
                "Browse the catalogue of tools in the VHP4Safety Virtual Human "
                "Platform for animal-free safety assessment of chemicals and "
                "pharmaceuticals."
            ),
            tools=tools,
            stages=stages,
            selected_stages=selected_stages,
            case_studies=list(get_casestudies()),
            selected_case_studies=selected_case_studies,
            reg_questions=reg_questions,
            selected_questions=selected_questions,
            stage_explanations=get_stage_explanations(),
            reg_question_explanations=get_reg_question_explanations(),
            reg_question_cases={v["label"]: v.get("case", "") for v in get_reg_questions().values()},
            page=page,
            page_size=page_size,
            total=total,
            has_prev=has_prev,
            has_next=has_next,
            search_query=search_query,
        )

    except Exception as e:
        return f"Error processing service data: {e}", 500


### New route to list methods (similar to the tools page)
@app.route("/methods")
@app.route("/methods/")
def methods():
    """Fetch methods_index.json from the cloud repo, normalize fields and render a methods list page."""
    methods = get_json_dict(METHODS_URL)  # cached for CACHE_TIMEOUT (5 days)

    if not methods:
        return "Error fetching methods list", 503

    try:
        methods = list(methods.values())  # convert dict to list

        # Normalize fields for the template and collect stages.
        # `vhp4safety_workflow_stage_content` is expected to hold glossary URIs
        # (same convention as service_index.json), e.g.
        # "https://vhp4safety.github.io/glossary#VHP0000156". We translate the
        # URI to the human label via get_stage_mapping(), so the dropdown,
        # filter, and tooltip (driven by get_stage_explanations()) all speak
        # the same vocabulary. Values that don't match a known URI fall
        # through as-is so legacy / typo values still render.
        stage_mapping = get_stage_mapping()
        stages_set = set()
        normalized = []
        for m in methods:
            norm = {}
            norm["id"] = m.get("id", "")
            # template expects 'service' and 'description'
            norm["service"] = (
                m.get("method")
                or m.get("method_name_content")
                or m.get("method_name")
                or ""
            )
            norm["description"] = (
                m.get("method_description_content") or m.get("method_description") or ""
            )
            # main_url used for method webpage (catalog page)
            norm["main_url"] = m.get("catalog_webpage_url") or "no_url"
            # interactive instance not present in methods index
            norm["inst_url"] = m.get("inst_url") or "no_url"
            # metadata md file not available in index; keep empty string
            norm["meta_data"] = m.get("meta_data") or ""
            # placeholder/no png
            norm["png"] = None
            # keep original raw data for potential details page
            norm["raw"] = m

            # Collect stages (split comma-separated values). Each part is a
            # glossary URI -> we resolve it to the human label. Placeholder
            # strings ("_No response_" / "No response") are skipped. The
            # resolved labels are stored on the record so the stage filter
            # below can match against them directly.
            stage_field = (m.get("vhp4safety_workflow_stage_content") or "").strip()
            resolved_stages = []
            if stage_field:
                for part in [s.strip() for s in stage_field.split(",")]:
                    if not part or part.lower().strip("_") == "no response":
                        continue
                    label = stage_mapping.get(part, part)  # URI -> label, else as-is
                    resolved_stages.append(label)
                    stages_set.add(label)
            norm["stages"] = resolved_stages

            normalized.append(norm)

        # Apply search and filters similar to /tools
        selected_case_studies = request.args.getlist("case_study")
        selected_stages = request.args.getlist("stage")
        selected_questions = request.args.getlist("reg_q")
        search_query = request.args.get("search", "").strip().lower()

        methods_filtered = normalized

        if selected_case_studies:
            # UI sends "Thyroid" (slug.title()); records store the lowercase
            # slug ("thyroid"). Case-insensitive match handles both ends.
            cs_lower = {c.lower() for c in selected_case_studies}
            methods_filtered = [
                m for m in methods_filtered
                if (m["raw"].get("case_study") or "").strip().lower() in cs_lower
            ]

        if selected_stages:
            # Match against the URI-resolved labels stored on `norm["stages"]`,
            # so the filter speaks the same vocabulary as the dropdown.
            sel = set(selected_stages)
            methods_filtered = [
                m for m in methods_filtered if sel & set(m.get("stages") or [])
            ]

        # Filter by regulatory questions. Methods records carry the canonical
        # reg_q_Xy key directly in the `regulatory_question` field (e.g.
        # "reg_q_1b"), matching the tools/data convention.
        reg_questions = {v["label"]: k for k, v in get_reg_questions().items()}
        if selected_questions:
            selected_keys = {
                reg_questions.get(q) for q in selected_questions if reg_questions.get(q)
            }
            methods_filtered = [
                m
                for m in methods_filtered
                if (m["raw"].get("regulatory_question") or "").strip() in selected_keys
            ]

        if search_query:
            methods_filtered = [
                m
                for m in methods_filtered
                if search_query in m.get("service", "").lower()
            ]

        stages = sorted(stages_set)
        if "Other" in stages:
            stages.remove("Other")
            stages.append("Other")

        # Pagination
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 12, type=int)
        total = len(methods_filtered)
        start = (page - 1) * page_size
        end = start + page_size
        methods_page = methods_filtered[start:end]
        has_prev = page > 1
        has_next = end < total

        # Pass everything the template expects
        return render_template(
            "methods/methods.html",
            page_title="Methods — VHP4Safety",
            meta_description=(
                "Browse the catalogue of experimental and computational methods in "
                "the VHP4Safety Virtual Human Platform for animal-free safety assessment."
            ),
            methods=methods_page,
            stages=stages,
            selected_stages=selected_stages,
            case_studies=list(get_casestudies()),
            selected_case_studies=selected_case_studies,
            reg_questions=reg_questions,
            selected_questions=selected_questions,
            stage_explanations=get_stage_explanations(),
            reg_question_explanations=get_reg_question_explanations(),
            reg_question_cases={v["label"]: v.get("case", "") for v in get_reg_questions().values()},
            page=page,
            page_size=page_size,
            total=total,
            has_prev=has_prev,
            has_next=has_next,
            search_query=search_query,
        )

    except Exception as e:
        return f"Error processing methods data: {e}", 500


@app.route("/methods/<methodid>")
def method_page(methodid):
    """Render a single method page using templates/methods/method.html
    Method details are taken from methods_index.json (keyed by method id).
    """
    try:
        methods = get_json_dict(METHODS_URL)
        # methods_index.json is a dict keyed by method id
        if methodid not in methods:
            abort(404)
        method_details = methods[methodid]
    except Exception as e:
        return f"Error processing methods data: {e}", 500

    # Try to load the full method JSON from the docs/methods folder (raw github)
    method_json = None
    # URL-encode the filename part to be safe
    encoded = urllib.parse.quote(methodid, safe="")
    raw_url = (
        "https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/docs/methods/"
        + f"{encoded}.json"
    )
    try:
        r = requests.get(raw_url, timeout=5)
        if r.status_code == 200:
            method_json = r.json()
        else:
            # fall back to using the index entry as minimal data
            method_json = method_details
    except Exception:
        # on any error, fall back to index entry
        method_json = method_details

    # Mirror the template's title/description resolution (methods/method.html)
    src = method_json if isinstance(method_json, dict) else method_details
    method_name = (
        src.get("method")
        or src.get("method_name_content")
        or src.get("service")
        or methodid
    )
    method_desc = (
        src.get("method_description_content")
        or src.get("method_description")
        or src.get("description")
        or ""
    )
    # Pass both to the template: some templates expect method_json, others method_details
    return render_template(
        "methods/method.html",
        method=method_details,
        method_details=method_details,
        method_json=method_json,
        page_title=f"{method_name} — VHP4Safety",
        meta_description=clip(method_desc)
        or f"{method_name}, a method in the VHP4Safety Virtual Human Platform.",
    )


@app.route("/tools/<toolname>")
def tool_page(toolname):
    # get the tools metadata:
    try:
        tools = get_json_dict(SERVICES_URL)
        tools = dict(tools)
        # Geting the service_list.json in the dictionary format.
        # Converting the dictionary to a list object.
    except Exception as e:
        return f"Error processing service data: {e}", 500

    # Map toolname to the correct JSON file in the new tool folder
    if toolname not in tools:
        abort(404)

    # get the tools metadata:
    url = "https://cloud.vhp4safety.nl/service/" + toolname + ".json"
    response = requests.get(url)

    if response.status_code != 200:
        return f"Error fetching service list: {response.status_code}", 503

    try:
        tool_details = response.json()
        tool_details = dict(tool_details)
        # Geting the service_list.json in the dictionary format.
        # Converting the dictionary to a list object.
    except Exception as e:
        return f"Error processing service data: {e}", 500

    tool_meta = tools[toolname]
    tool_name = tool_meta.get("service") or tool_meta.get("title") or toolname
    return render_template(
        "tools/tool.html",
        tool_json=tool_meta,
        tool_details=tool_details,
        process_flow_steps=get_process_flow_steps(),
        page_title=f"{tool_name} — VHP4Safety",
        meta_description=clip(tool_meta.get("description"))
        or f"{tool_name}, a tool in the VHP4Safety Virtual Human Platform.",
    )


@app.route("/model/<modelid>")
def model_page(modelid):
    zen_results = get_repository_model(modelid)

    # Extract datasets and metadata from Zenodo
    datasets = zen_results.get("hits", [])
    zen_total = zen_results.get("total", 0)
    zen_error: str | None = zen_results.get("error", None)

    studies, datasets = normalize_all([], datasets)
    for s in studies:
        scrub_draft(s)
    for d in datasets:
        scrub_draft(d)

    if zen_total != 1:
        return abort(404)
    # reg-question records store the canonical reg_q_Xy key; map key -> label so
    # the badges show the human-readable question.
    reg_q_labels = {k: v["label"] for k, v in get_reg_questions().items()}
    if studies:
        return render_template(
            "models/model.html", data=studies[0], reg_q_labels=reg_q_labels
        )
    elif datasets:
        return render_template(
            "models/model.html", data=datasets[0], reg_q_labels=reg_q_labels
        )
    return abort(404)


################################################################################
### Pages under 'Implementation'


# General Explore our work
@app.route("/explore_our_work")
def explore_our_work():
    return render_template(
        "implementation/explore_our_work.html",
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
        "implementation/training.html",
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
        "implementation/impact.html",
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
        "safety_assessment_workflow.html", process_flow_steps=get_process_flow_steps()
    )


################################################################################
### Pages under 'Case Studies'


# General case studies page
@app.route("/casestudies")
def workflows():
    return render_template(
        "case_studies/casestudies.html",
        page_title="Case studies — VHP4Safety",
        meta_description=(
            "Explore the VHP4Safety case studies (kidney, Parkinson's disease and "
            "thyroid) that connect tools, methods and data to real regulatory questions."
        ),
    )


# Individual case study page, dynamically filled based on URL
@app.route("/casestudies/<case>", defaults={"step": ""})
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
    if case not in get_casestudies():
        abort(404)
    # The <question>/<step> sub-routes are JS-driven states of the same page, so
    # canonicalise them all to the base case URL to avoid duplicate indexing.
    case_labels = {
        "kidney": "Kidney",
        "parkinson": "Parkinson's disease",
        "thyroid": "Thyroid",
    }
    case_name = case_labels.get(case, case.capitalize())
    # JS will handle steps via the URL
    return render_template(
        "case_studies/casestudy.html",
        case=case,
        page_title=f"{case_name} case study — VHP4Safety",
        meta_description=(
            f"The VHP4Safety {case_name} case study: a Virtual Human Platform "
            "workflow connecting tools, methods and data to a regulatory question."
        ),
        canonical_url=request.url_root.rstrip("/") + "/casestudies/" + case,
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


@app.route("/compound/<cwid>")
def show_compound(cwid):
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
        compound_dat = wbi_helpers.execute_sparql_query(
            sparqlquery, endpoint=compoundwikiEP
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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
        compound_dat = wbi_helpers.execute_sparql_query(
            sparqlquery, endpoint=compoundwikiEP
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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
        compound_dat = wbi_helpers.execute_sparql_query(
            sparqlquery, endpoint=compoundwikiEP
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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
        compound_dat = wbi_helpers.execute_sparql_query(
            sparqlquery, endpoint=compoundwikiEP
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if not bool(compound_dat):
        return jsonify({"error": "No data found"}), 404
    if len(compound_dat["results"]["bindings"]) == 0:
        return jsonify({"error": "No data found"}), 404
    compound_dat = compound_dat["results"]["bindings"][0]
    qid = compound_dat["qid"]["value"]
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
        compound_dat = requests.get(sparqlqueryURL)
        # return json.loads(compound_dat.content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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
        page_title="Terms of Service — VHP4Safety",
        meta_description="Terms of Service for the VHP4Safety Virtual Human Platform.",
    )


@app.route("/legal/privacypolicy")
def privacy_policy():
    return render_template(
        "legal/privacypolicy.html",
        page_title="Privacy Policy — VHP4Safety",
        meta_description="Privacy Policy for the VHP4Safety Virtual Human Platform.",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
