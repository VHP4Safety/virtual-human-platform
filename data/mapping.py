from typing import Any, Dict, List, Optional, Tuple
import re

# ---------- small helpers ----------

# Prefer literal "<>" in real code (not HTML-escaped &lt; &gt;)
DOI_RE = re.compile(r'\b10\.\d{4,9}/[^\s"<>]+', re.IGNORECASE)


def is_valid_doi(doi: Optional[str]) -> bool:
    """Basic DOI sanity check. Rejects obvious redactions like '***'."""
    if not doi or not isinstance(doi, str):
        return False
    d = doi.strip()
    if "*" in d:  # handles 10.5281/zenodo.*** etc.
        return False
    if not d.lower().startswith("10."):
        return False
    if "/" not in d:
        return False
    return True


def g(d: Dict[str, Any], *path: str, default=None):
    """Safe nested-get. Never raises KeyError."""
    cur: Any = d
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur


def first(*vals, default=None):
    """Return first non-empty (not None, not '' , not []) value."""
    for v in vals:
        if v is None:
            continue
        if v == "":
            continue
        if isinstance(v, (list, dict)) and len(v) == 0:
            continue
        return v
    return default


def find_attr(attrs: Any, name: str) -> Optional[str]:
    """Find BioStudies attribute list entry with given name."""
    if not isinstance(attrs, list):
        return None
    for a in attrs:
        if isinstance(a, dict) and a.get("name") == name:
            return a.get("value")
    return None


def extract_doi_from_text(text: Any) -> Optional[str]:
    """Extract a DOI from a string (or return None)."""
    if not isinstance(text, str) or not text:
        return None
    m = DOI_RE.search(text)
    doi = m.group(0) if m else None
    return doi if is_valid_doi(doi) else None


def extract_all_dois(text: Any) -> List[str]:
    """Extract all valid DOIs from a string."""
    if not isinstance(text, str) or not text:
        return []
    dois = []
    for m in DOI_RE.finditer(text):
        d = m.group(0)
        if is_valid_doi(d):
            dois.append(d)
    return dois


def doi_url(doi: Optional[str]) -> Optional[str]:
    """Convert DOI to https://doi.org/..."""
    if not doi:
        return None
    d = doi.strip()
    if d.lower().startswith("http"):
        return d
    return f"https://doi.org/{d}"


# ---------- DOI + publications extraction ----------


def find_doi_anywhere(item: Dict[str, Any]) -> Optional[str]:
    """
    Best-effort *dataset DOI* extractor.
    NOTE: Intentionally does NOT search BioStudies raw_data publication subsections,
    because those are *linked publications*, not dataset DOI.
    """
    # direct keys first (dataset DOI)
    doi = first(item.get("doi"), g(item, "metadata", "doi"))
    doi = extract_doi_from_text(doi) or doi
    if is_valid_doi(doi):
        return doi

    # Zenodo: related identifiers (sometimes contains dataset DOI, but usually pubs)
    rel = g(item, "metadata", "related_identifiers", default=[]) or []
    if isinstance(rel, list):
        for r in rel:
            if not isinstance(r, dict):
                continue
            ident = r.get("identifier")
            scheme = (r.get("scheme") or "").lower()
            if scheme == "doi":
                found = extract_doi_from_text(ident) or ident
                if is_valid_doi(found):
                    return found
            found = extract_doi_from_text(ident)
            if found:
                return found

    # BioStudies: attributes (dataset DOI if present)
    attrs = g(item, "metadata", "attributes", default=[]) or []
    for key in ("DOI", "doi", "Dataset DOI"):
        v = find_attr(attrs, key)
        found = extract_doi_from_text(v)
        if found:
            return found

    # BioStudies: publications list (if present) - ambiguous; keep as last resort
    pubs = g(item, "metadata", "publications", default=[]) or []
    if isinstance(pubs, list):
        for p in pubs:
            if not isinstance(p, dict):
                continue
            for cand in (p.get("doi"), p.get("identifier"), p.get("url")):
                found = extract_doi_from_text(cand)
                if found:
                    return found

    # last resort: description text
    desc = first(g(item, "metadata", "description"), item.get("description"))
    found = extract_doi_from_text(desc)
    if found:
        return found

    return None


def _dedup_publications(pubs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate publications by DOI (preferred) or URL."""
    seen = set()
    out = []
    for p in pubs:
        doi = (p.get("doi") or "").lower().strip()
        url = (p.get("url") or "").lower().strip()
        key = doi or url
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def extract_publications_zenodo(z: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract linked publications from Zenodo record.
    Sources:
      - metadata.related_identifiers
      - metadata.references (list of strings)
      - DOIs embedded in metadata.description (optional, but useful)
    """
    pubs: List[Dict[str, Any]] = []

    dataset_doi = find_doi_anywhere(z)
    concept_doi = first(z.get("conceptdoi"), g(z, "metadata", "conceptdoi"))
    concept_doi = extract_doi_from_text(concept_doi) or concept_doi
    if not is_valid_doi(concept_doi):
        concept_doi = None

    rel = g(z, "metadata", "related_identifiers", default=[]) or []
    if isinstance(rel, list):
        for r in rel:
            if not isinstance(r, dict):
                continue
            ident = r.get("identifier")
            scheme = (r.get("scheme") or "").lower()
            relation = (r.get("relation") or "").lower()
            rtype = (r.get("resource_type") or "").lower()

            # Heuristic: treat as publication if resource_type contains "publication"
            # or relation indicates citation-like linkage.
            looks_like_pub = "publication" in rtype or relation in {
                "references",
                "iscitedby",
                "isreferencedby",
                "issupplementto",
                "isdocumentedby",
            }

            if not looks_like_pub:
                # still accept DOI-looking identifiers if they are clearly *not* Zenodo dataset DOIs
                pass

            doi = None
            url = None

            if scheme == "doi":
                doi = extract_doi_from_text(ident) or (
                    ident.strip() if isinstance(ident, str) else None
                )
                if not is_valid_doi(doi):
                    doi = None
                url = doi_url(doi) if doi else None
            elif scheme == "url":
                url = ident.strip() if isinstance(ident, str) else None
                doi = extract_doi_from_text(url)
            else:
                # Unknown scheme: try DOI extraction
                doi = extract_doi_from_text(ident)
                url = (
                    doi_url(doi)
                    if doi
                    else (ident.strip() if isinstance(ident, str) else None)
                )

            # Exclude dataset DOI / concept DOI if they appear
            if doi and (doi == dataset_doi or doi == concept_doi):
                continue

            if doi or url:
                pubs.append(
                    {
                        "doi": doi,
                        "doi_url": doi_url(doi) if doi else None,
                        "url": url,
                        "relation": relation or None,
                        "resource_type": r.get("resource_type"),
                        "source": "zenodo.related_identifiers",
                    }
                )

    refs = g(z, "metadata", "references", default=[]) or []
    if isinstance(refs, list):
        for ref in refs:
            doi = extract_doi_from_text(ref)
            if doi and doi not in {dataset_doi, concept_doi}:
                pubs.append(
                    {
                        "doi": doi,
                        "doi_url": doi_url(doi),
                        "url": doi_url(doi),
                        "relation": "references",
                        "resource_type": "publication",
                        "source": "zenodo.references",
                    }
                )

    # Optional: mine description for DOI links (often present as doi.org/10.xxxx/...)
    desc = g(z, "metadata", "description")
    for doi in extract_all_dois(desc):
        if doi not in {dataset_doi, concept_doi}:
            pubs.append(
                {
                    "doi": doi,
                    "doi_url": doi_url(doi),
                    "url": doi_url(doi),
                    "relation": "mentions",
                    "resource_type": "publication",
                    "source": "zenodo.description",
                }
            )

    return _dedup_publications(pubs)


def extract_publications_biostudies(b: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract linked publications from BioStudies record.
    Sources:
      - metadata.publications (if present)
      - metadata.raw_data.section.subsections entries of type 'Publication'
    """
    pubs: List[Dict[str, Any]] = []
    meta = b.get("metadata", {}) or {}

    # 1) metadata.publications (sometimes already structured)
    meta_pubs = meta.get("publications", []) or []
    if isinstance(meta_pubs, list):
        for p in meta_pubs:
            if isinstance(p, dict):
                doi = extract_doi_from_text(
                    first(p.get("doi"), p.get("identifier"), p.get("url"))
                )
                url = first(p.get("url"), doi_url(doi))
                if doi or url:
                    pubs.append(
                        {
                            "title": p.get("title"),
                            "doi": doi,
                            "doi_url": doi_url(doi) if doi else None,
                            "url": url,
                            "pmid": p.get("pmid") or p.get("PMID"),
                            "year": p.get("year") or p.get("Year"),
                            "authors": p.get("authors") or p.get("Authors"),
                            "source": "biostudies.metadata.publications",
                        }
                    )
            elif isinstance(p, str):
                doi = extract_doi_from_text(p)
                if doi:
                    pubs.append(
                        {
                            "doi": doi,
                            "doi_url": doi_url(doi),
                            "url": doi_url(doi),
                            "source": "biostudies.metadata.publications",
                        }
                    )

    # 2) raw_data.section.subsections: type == Publication
    subs = g(b, "metadata", "raw_data", "section", "subsections", default=[]) or []
    if isinstance(subs, list):
        for s in subs:
            if not isinstance(s, dict):
                continue
            stype = str(s.get("type", "")).strip().lower()
            if stype != "publication":
                continue

            # flatten attributes into dict
            attrs = s.get("attributes") or []
            flat: Dict[str, Any] = {}
            if isinstance(attrs, list):
                for a in attrs:
                    if isinstance(a, dict) and a.get("name"):
                        flat[a["name"]] = a.get("value")

            doi = extract_doi_from_text(flat.get("DOI") or flat.get("doi"))
            pmid = flat.get("PMID") or flat.get("pmid")
            title = flat.get("Title") or flat.get("title")
            year = flat.get("Year") or flat.get("year")
            authors = flat.get("Authors") or flat.get("Author") or flat.get("authors")

            url = doi_url(doi) if doi else None

            if doi or pmid or title:
                pubs.append(
                    {
                        "title": title,
                        "doi": doi,
                        "doi_url": doi_url(doi) if doi else None,
                        "url": url,
                        "pmid": pmid,
                        "year": year,
                        "authors": authors,
                        "journal": flat.get("Journal") or flat.get("journal"),
                        "volume": flat.get("Volume") or flat.get("volume"),
                        "issue": flat.get("Issue") or flat.get("issue"),
                        "type": flat.get("Type") or flat.get("type"),
                        "issn": flat.get("Issn") or flat.get("ISSN"),
                        "source": "biostudies.raw_data.section.subsections",
                    }
                )

    return _dedup_publications(pubs)


# ---------- Zenodo normalizer ----------


def normalize_zenodo(z: Dict[str, Any]) -> Dict[str, Any]:
    creators = g(z, "metadata", "creators", default=[]) or []
    grants = g(z, "metadata", "grants", default=[]) or []
    files = z.get("files", []) or []

    doi = find_doi_anywhere(z)
    if not is_valid_doi(doi):
        doi = None

    publications = extract_publications_zenodo(z)

    return {
        "title": first(g(z, "metadata", "title"), z.get("title")),
        "description": first(g(z, "metadata", "description")),
        "license": first(g(z, "metadata", "license", "id")),
        "authors": [
            {
                "name": c.get("name"),
                "orcid": c.get("orcid"),
                "affiliation": c.get("affiliation"),
            }
            for c in creators
            if isinstance(c, dict)
        ],
        "funding": [
            {
                "funder": g(gr, "funder", "name"),
                "funder_doi": g(gr, "funder", "doi"),
                "acronym": gr.get("acronym"),
                "title": gr.get("title"),
                "code": gr.get("code"),
                "url": gr.get("url"),
            }
            for gr in grants
            if isinstance(gr, dict)
        ],
        "ReleaseDate": first(g(z, "metadata", "publication_date"), z.get("created")),
        "id": first(z.get("id"), z.get("recid")),
        "type": first(g(z, "metadata", "resource_type", "type"), "dataset"),
        "version": first(g(z, "metadata", "version")),
        "files": [
            {
                "name": f.get("key"),
                "size": f.get("size"),
                "checksum": f.get("checksum"),
                "url": g(f, "links", "self"),
            }
            for f in files
            if isinstance(f, dict)
        ],
        "url": first(z.get("url"), g(z, "links", "self_html"), g(z, "links", "self")),
        # dataset DOI
        "doi": doi,
        "doi_url": doi_url(doi),
        "conceptdoi": first(z.get("conceptdoi"), g(z, "metadata", "conceptdoi")),
        "conceptdoi_url": doi_url(
            first(z.get("conceptdoi"), g(z, "metadata", "conceptdoi"))
        ),
        # NEW: linked publications
        "publications": publications,
    }


# ---------- BioStudies normalizer ----------


def normalize_biostudies(b: Dict[str, Any]) -> Dict[str, Any]:
    meta = b.get("metadata", {}) or {}
    attrs = meta.get("attributes", []) or []
    files = meta.get("files", []) or []

    author_details = meta.get("author_details", []) or []
    authors = meta.get("authors", []) or []

    if isinstance(author_details, list) and len(author_details) > 0:
        authors_norm = [
            {
                "name": a.get("name"),
                "orcid": a.get("orcid"),
                "affiliation": a.get("affiliation_name") or a.get("affiliation_ref"),
                "email": a.get("email"),
            }
            for a in author_details
            if isinstance(a, dict)
        ]
    else:
        authors_norm = [
            {"name": name, "orcid": None, "affiliation": None}
            for name in authors
            if isinstance(name, str)
        ]

    # funding best-effort (normalized)
    funding: List[Dict[str, Any]] = []
    subsections = (
        g(b, "metadata", "raw_data", "section", "subsections", default=[]) or []
    )
    if isinstance(subsections, list):
        for s in subsections:
            if not isinstance(s, dict):
                continue
            if str(s.get("type", "")).strip().lower() != "funding":
                continue

            flat = {}
            for a in s.get("attributes") or []:
                if isinstance(a, dict) and a.get("name"):
                    flat[a["name"]] = a.get("value")

            if not flat:
                continue

            funder = first(
                flat.get("Funder"),
                flat.get("Agency"),
                flat.get("Funding agency"),
                flat.get("Agency name"),
            )
            code = first(
                flat.get("Grant_id"),
                flat.get("Grant ID"),
                flat.get("Grant"),
                flat.get("Grant number"),
            )
            url = first(flat.get("URL"), flat.get("Url"), flat.get("Project URL"))

            funding.append(
                {
                    "funder": funder,
                    "code": code,
                    "url": url,
                    "acronym": flat.get("Acronym")
                    or flat.get("Programme")
                    or flat.get("Program"),
                    "raw": flat,
                    "source": "biostudies.raw_data.section.subsections",
                }
            )

    doi = find_doi_anywhere(b)
    if not is_valid_doi(doi):
        doi = None

    publications = extract_publications_biostudies(b)

    # ✅ files: PASS THROUGH URL only (no rebuilding)
    files_norm: List[Dict[str, Any]] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        files_norm.append(
            {
                "name": first(f.get("name"), f.get("path")),
                "size": f.get("size"),
                "path": f.get("path"),
                "url": f.get("url"),  # <-- do not rebuild
                # optional (keep if useful)
                "exists": g(f, "exists_check", "exists"),
                "content_length": g(f, "exists_check", "content_length"),
            }
        )

    # OPTIONAL strictness: attach warning if any url missing
    missing = [x.get("path") for x in files_norm if x.get("path") and not x.get("url")]
    if missing:
        meta.setdefault("warnings", []).append(
            f"{len(missing)} BioStudies file(s) missing url in metadata.files (pass-through mode)."
        )

    return {
        "title": first(meta.get("title"), b.get("title")),
        "description": first(meta.get("description")),
        "license": first(find_attr(attrs, "License")),
        "authors": authors_norm,
        "funding": funding,
        "ReleaseDate": first(
            b.get("release_date"),
            find_attr(attrs, "ReleaseDate"),
            find_attr(attrs, "Release Date"),
        ),
        "id": first(meta.get("accession"), b.get("accession"), b.get("id")),
        "type": first(b.get("type"), meta.get("type"), "study"),
        "version": first(meta.get("version")),
        "files": files_norm,
        "url": first(b.get("url")),
        "doi": doi,
        "doi_url": doi_url(doi),
        "publications": publications,
    }


# ---------- combine ----------


def normalize_all(
    bs_entries: List[Dict[str, Any]],
    zenodo_entries: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Adds 'norm_metadata' to each dict in both lists and returns a 2-tuple
    (bs_entries, zenodo_entries) with 'norm_metadata' populated.
    Robust: ignores non-dicts and missing lists.
    """

    for z in zenodo_entries or []:
        if isinstance(z, dict):
            z["norm_metadata"] = normalize_zenodo(z)

    for b in bs_entries or []:
        if isinstance(b, dict):
            b["norm_metadata"] = normalize_biostudies(b)

    return bs_entries, zenodo_entries


def scrub_draft(obj: Any) -> Any:
    """Strip in-progress '[DRAFT]' values from records so the templates'
    existing `{% if ... %}` checks skip them. String values containing
    '[DRAFT]' become None; list entries that are DRAFT strings are dropped.
    Mutates dicts/lists in place and returns the root object. Iterative +
    cycle-safe (tracks visited container ids), so deeply-nested or
    self-referencing structures won't blow the stack.
    Idempotent — safe to run against cached data.
    """
    def is_draft_str(x: Any) -> bool:
        return isinstance(x, str) and "[DRAFT]" in x

    seen: set[int] = set()
    stack: list = [obj]
    while stack:
        cur = stack.pop()
        cid = id(cur)
        if cid in seen:
            continue
        if isinstance(cur, dict):
            seen.add(cid)
            for k, v in cur.items():
                if is_draft_str(v):
                    cur[k] = None
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            seen.add(cid)
            cur[:] = [x for x in cur if not is_draft_str(x)]
            for x in cur:
                if isinstance(x, (dict, list)):
                    stack.append(x)
    return obj
