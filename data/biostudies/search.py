import requests
import json
import time
import re
from urllib.parse import quote


class BioStudiesExtractor:
    """Class to handle BioStudies API interactions"""

    _SPLIT_RE = re.compile(r"^(.*?)(\d+)$")

    def __init__(self, collection: str = ""):
        self.base_url = "https://www.ebi.ac.uk/biostudies/api/v1"
        self.ftp_base = "https://ftp.ebi.ac.uk/pub/databases/biostudies/"
        self.studies_url = self.base_url + "/studies"
        self.search_url = (
            f"{self.base_url}/{collection}/search"
            if collection
            else f"{self.base_url}/search"
        )

    # -----------------------------
    # ID validation / URL building
    # -----------------------------
    def validate_study_id(self, study_id):
        """
        Validate BioStudies ID format

        Args:
            study_id (str): BioStudies accession ID

        Returns:
            tuple: (is_valid, cleaned_id, error_message)
        """
        if not study_id or not isinstance(study_id, str):
            return False, None, "Study ID is required"

        verified_id = study_id.strip().upper()

        # Examples: S-ONTX26, E-MTAB-1234, S-BSST123, S-VHPS21, S-TOXR1735
        patterns = [
            r"^S-[A-Z0-9]+$",  # Studies starting with S-
            r"^E-[A-Z]+-\d+$",  # Expression studies like E-MTAB-1234
            r"^[A-Z]+-\d+$",  # General pattern like ABC-123
        ]

        if not any(re.match(pattern, verified_id) for pattern in patterns):
            return (
                False,
                verified_id,
                "Invalid BioStudies ID format. Expected format: S-ONTX26, E-MTAB-1234, etc.",
            )

        return True, verified_id, None

    def split_text_int(self, value: str):
        """
        Splits trailing integer from a string.
        'S-VHPS21' -> ('S-VHPS', 21)
        'ABC'      -> ('ABC', None)
        'X-12A'    -> ('X-12A', None)
        """
        if not value:
            return value, None
        m = self._SPLIT_RE.match(value)
        if not m:
            return value, None
        prefix, num = m.group(1), int(m.group(2))
        return prefix, num

    def build_biostudies_https_file_url(self, accno: str, filename: str) -> str | None:
        """
        Constructs:
        https://ftp.ebi.ac.uk/pub/databases/biostudies/{prefix}/{num3}/{accno}/Files/{filename}

        Returns None if accno has no trailing integer.

        Note:
        - We keep "/" safe in case filename contains subfolders (rare, but possible).
        """
        prefix, num = self.split_text_int(accno)
        if num is None or not filename:
            return None

        num3 = f"{num:03d}"

        # Encode only the filename segment (allow "/" for potential subpaths)
        safe_name = quote(filename, safe="/")

        return self.ftp_base + f"{prefix}/{num3}/{accno}/Files/{safe_name}"

    def url_exists_no_download(self, url: str, timeout=(3.05, 10)):
        """
        Returns a dict describing existence with minimal data transfer.
        - tries HEAD
        - falls back to GET Range bytes=0-0
        """
        result = {
            "url": url,
            "exists": False,
            "status_code": None,
            "content_length": None,
            "final_url": None,
            "error": None,
            "method": None,
        }

        if not url:
            result["error"] = "Empty URL"
            return result

        try:
            # 1) HEAD (preferred: no body)
            r = requests.head(url, allow_redirects=True, timeout=timeout)
            result["status_code"] = r.status_code
            result["final_url"] = str(r.url)
            result["method"] = "HEAD"

            if r.status_code == 200:
                result["exists"] = True
                result["content_length"] = r.headers.get("Content-Length")
                return result

            # 2) Fallback if HEAD not allowed or forbidden, etc.
            if r.status_code in (403, 405):
                rg = requests.get(
                    url,
                    stream=True,
                    allow_redirects=True,
                    headers={"Range": "bytes=0-0"},
                    timeout=timeout,
                )
                result["status_code"] = rg.status_code
                result["final_url"] = str(rg.url)
                result["method"] = "GET_RANGE"

                # 206 Partial Content is a strong "exists"
                if rg.status_code in (200, 206):
                    result["exists"] = True
                    result["content_length"] = rg.headers.get("Content-Length")

                return result

            # other codes (404, 410, 500...) treated as not found / not accessible
            return result

        except requests.RequestException as e:
            result["error"] = str(e)
            return result

    def _pick_rocrate_file(self, files: list[dict]) -> dict | None:
        """
        Return the first file dict whose name/path contains 'rocrate' (case-insensitive).
        Preference order:
        1) files where exists_check.exists is True (if exists_check present)
        2) otherwise first match
        """
        if not isinstance(files, list) or not files:
            return None

        def fname(f: dict) -> str:
            if not isinstance(f, dict):
                return ""
            return str(f.get("name") or f.get("path") or "").lower()

        # All matches by name/path
        matches = [f for f in files if "rocrate" in fname(f)]
        if not matches:
            return None

        # Prefer verified existing ones if available
        verified = [
            f
            for f in matches
            if isinstance(f, dict)
            and isinstance(f.get("exists_check"), dict)
            and f["exists_check"].get("exists") is True
        ]
        return verified[0] if verified else matches[0]

    # -----------------------------
    # API operations
    # -----------------------------
    def get_study_metadata(self, study_id):
        """
        Extract metadata for a given BioStudies ID

        Args:
            study_id (str): BioStudies accession ID (e.g., S-ONTX26)

        Returns:
            dict: Parsed metadata or error information
        """
        try:
            # Validate study ID format
            is_valid, verified_id, validation_error = self.validate_study_id(study_id)
            if not is_valid:
                return {"error": validation_error}

            url = self.studies_url + f"/{verified_id}"

            headers = {
                "Accept": "application/json",
                "User-Agent": "BioStudies-VHP4Safety-App/1.0",
            }

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if not data:
                        return {
                            "error": f"Empty response received for study {verified_id}"
                        }

                    # Parse metadata first, then build URL using the derived collection (no extra API calls)
                    md = self.parse_metadata(data)
                    collection = md.get("collection", "")
                    web_url = self.build_study_url(verified_id, collection).get(
                        "url", ""
                    )
                    return md | {"url": web_url}

                except json.JSONDecodeError as e:
                    return {
                        "error": f"Invalid JSON response from BioStudies API: {str(e)}"
                    }

            elif response.status_code == 404:
                return {
                    "error": f"Study '{verified_id}' not found in BioStudies database. Please check the ID and try again."
                }
            elif response.status_code == 403:
                return {
                    "error": "Access forbidden. The study may be restricted or private."
                }
            elif response.status_code == 500:
                return {"error": "BioStudies server error. Please try again later."}
            elif response.status_code == 503:
                return {
                    "error": "BioStudies service temporarily unavailable. Please try again later."
                }
            else:
                return {
                    "error": f"BioStudies API returned status {response.status_code}. Please try again later."
                }

        except requests.exceptions.Timeout:
            return {
                "error": "Request timed out. BioStudies server may be slow. Please try again."
            }
        except requests.exceptions.ConnectionError:
            return {
                "error": "Cannot connect to BioStudies server. Please check your internet connection."
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error occurred: {str(e)}"}

    def get_study_collection(self, study_id):
        """
        Extract collection for a given BioStudies ID
        """
        metadata = self.get_study_metadata(study_id)
        if "error" in metadata:
            return metadata
        collection = metadata.get("collection", "")
        return {"accession": study_id, "collection": collection}

    def build_study_url(self, study_id, collection: str = ""):
        """
        Build the URL to access the study in BioStudies web interface
        """
        is_valid, verified_id, validation_error = self.validate_study_id(study_id)
        if not is_valid:
            return {"error": validation_error}

        if collection:
            url = f"https://www.ebi.ac.uk/biostudies/{collection}/studies/{verified_id}"
        else:
            url = f"https://www.ebi.ac.uk/biostudies/studies/{verified_id}"

        return {"accession": verified_id, "url": url}

    # -----------------------------
    # Search / list
    # -----------------------------
    def search_studies(
        self,
        query,
        page=1,
        page_size=10,
        load_metadata: bool = True,
        filters: tuple[tuple] | None = None,
    ) -> dict:
        """
        Search for studies in BioStudies database
        """
        try:
            if not query or not isinstance(query, str):
                return {"error": "Search query must be a non-empty string."}

            filters_applied = bool(filters)
            if filters_applied:
                load_metadata = True

            params = {"query": query, "page": page, "pageSize": page_size}

            headers = {
                "Accept": "application/json",
                "User-Agent": "BioStudies-VHP4Safety-App/1.0",
            }

            response = requests.get(
                self.search_url, headers=headers, params=params, timeout=30
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    hits = data.get("hits", [])
                    total_hits = data.get("totalHits", 0)

                    if not data or total_hits == 0:
                        return {"error": "No results found."}

                    if load_metadata:
                        hits = self._hit_metadata(hits)
                    hits = self._hit_url(hits)

                    if filters_applied:
                        hits = self._apply_filters(hits, filters)

                        page_size_met = len(hits) >= page_size
                        pages_fetched = 1

                        if not page_size_met:
                            hits, page_size_met, pages_fetched = (
                                self._backfill_filtered_results(
                                    hits, page, page_size, filters, query
                                )
                            )

                        return {
                            "totalHits": total_hits,
                            "hits": hits,
                            "hits_returned": len(hits),
                            "page": page,
                            "pageSize": page_size,
                            "pages_fetched": pages_fetched,
                            "filters_applied": True,
                            "page_size_met": page_size_met,
                        }

                    return data | {"hits": hits, "total": total_hits}

                except json.JSONDecodeError as e:
                    return {
                        "error": f"Invalid JSON response from BioStudies API: {str(e)}"
                    }

            elif response.status_code == 400:
                return {"error": "Bad request. Please check your search parameters."}
            elif response.status_code == 403:
                return {"error": "Access forbidden. The collection may be restricted."}
            elif response.status_code == 500:
                return {"error": "BioStudies server error. Please try again later."}
            elif response.status_code == 503:
                return {
                    "error": "BioStudies service temporarily unavailable. Please try again later."
                }
            else:
                return {
                    "error": f"BioStudies API returned status {response.status_code}. Please try again later."
                }

        except requests.exceptions.Timeout:
            return {
                "error": "Request timed out. BioStudies server may be slow. Please try again."
            }
        except requests.exceptions.ConnectionError:
            return {
                "error": "Cannot connect to BioStudies server. Please check your internet connection."
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error occurred: {str(e)}"}

    def list_studies(
        self,
        page=1,
        page_size=50,
        include_urls: bool = False,
        load_metadata: bool = False,
        filters: tuple[tuple] | None = None,
    ) -> dict:
        """
        List studies in the configured BioStudies collection for a specific page.
        """
        filters_applied = bool(filters)
        if filters_applied:
            load_metadata = True
            include_urls = True

        headers = {
            "Accept": "application/json",
            "User-Agent": "BioStudies-VHP4Safety-App/1.0",
        }
        params = {"page": page, "pageSize": page_size}

        try:
            response = requests.get(
                self.search_url, headers=headers, params=params, timeout=30
            )
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Network error during listing: {e}",
                "total": 0,
                "hits": [],
            }

        if response.status_code != 200:
            return {
                "error": f"BioStudies API returned status {response.status_code} while listing.",
                "total": 0,
                "hits": [],
            }

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON response from BioStudies API: {str(e)}",
                "total": 0,
                "hits": [],
            }

        total_hits = data.get("totalHits") or data.get("total") or 0
        hits = data.get("hits", [])

        if include_urls:
            hits = self._hit_url(hits)
        if load_metadata:
            hits = self._hit_metadata(hits)

        if filters_applied:
            hits = self._apply_filters(hits, filters)

            page_size_met = len(hits) >= page_size
            pages_fetched = 1

            if not page_size_met:
                hits, page_size_met, pages_fetched = self._backfill_filtered_results(
                    hits, page, page_size, filters, query=None
                )

            return {
                "totalHits": total_hits,
                "total": total_hits,
                "hits": hits,
                "hits_returned": len(hits),
                "page": page,
                "pageSize": page_size,
                "pages_fetched": pages_fetched,
                "filters_applied": True,
                "page_size_met": page_size_met,
            }

        return {"total": total_hits, "hits": hits}

    def _hit_url(self, hits: list) -> list:
        for hit in hits:
            acc = hit.get("accession") or hit.get("accno")
            if acc:
                hit["url"] = self.build_study_url(acc).get("url", "")
        return hits

    def _hit_metadata(self, hits: list) -> list:
        for hit in hits:
            acc = hit.get("accession") or hit.get("accno")
            if acc:
                hit["metadata"] = self.get_study_metadata(acc)
        return hits

    def _apply_filters(self, hits: list, filters: list[tuple]) -> list:
        """
        Filter hits based on metadata field values.

        Semantics: OR within the same field name (e.g. ("case_study","Kidney")
        and ("case_study","Parkinson") together match records in either case),
        AND across different field names. Case-insensitive. Matches the
        convention used by tools/methods filters.
        """
        if not filters:
            return hits

        # Group accepted values by field name, lowercased for case-insensitive
        # comparison.
        accepted_by_field: dict[str, list[str]] = {}
        for field, value in filters:
            accepted_by_field.setdefault(field, []).append(str(value).strip().lower())

        def _field_values(metadata: dict, field: str) -> list[str]:
            # A field may be a list (case_study/regulatory_question/flow_step)
            # or a plain string; normalise to a lowercased list for matching.
            raw = metadata.get(field, "")
            values = raw if isinstance(raw, (list, tuple)) else [raw]
            return [str(v).strip().lower() for v in values if v]

        filtered = []
        for hit in hits:
            metadata = hit.get("metadata", {})
            if not metadata:
                continue
            # AND across fields; within a field the record matches if any of its
            # values is among the accepted ones (OR).
            if all(
                any(v in accepted for v in _field_values(metadata, field))
                for field, accepted in accepted_by_field.items()
            ):
                filtered.append(hit)
        return filtered

    def _backfill_filtered_results(
        self,
        initial_hits: list,
        page: int,
        page_size: int,
        filters: list[tuple],
        query: str = None,
    ) -> tuple:
        """
        Backfill filtered results by fetching additional pages until page_size is met or timeout
        """
        filtered = initial_hits[:]
        current_page = page
        start_time = time.time()
        pages_fetched = 1

        while len(filtered) < page_size:
            if time.time() - start_time > 30:
                break

            current_page += 1

            try:
                params = {"page": current_page, "pageSize": page_size}
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "BioStudies-VHP4Safety-App/1.0",
                }

                if query:
                    params["query"] = query

                response = requests.get(
                    self.search_url, headers=headers, params=params, timeout=30
                )
                if response.status_code != 200:
                    break

                data = response.json()
                next_hits = data.get("hits", [])
                if not next_hits:
                    break

                next_hits = self._hit_metadata(next_hits)
                next_filtered = self._apply_filters(next_hits, filters)
                filtered.extend(next_filtered)
                pages_fetched += 1

            except Exception:
                break

        page_size_met = len(filtered) >= page_size
        return filtered[:page_size], page_size_met, pages_fetched

    # -----------------------------
    # Metadata parsing (FIXED)
    # -----------------------------
    def parse_metadata(
        self, raw_data: dict, *, validate_files: bool = True, file_timeout=(3.05, 10)
    ):
        """
        Parse and structure the metadata from BioStudies API response.

        FIX:
        - Files are extracted ONLY here (enriched), not in _extract_comprehensive_metadata().
          This prevents duplicates and ensures consistent structure.
        """
        try:
            metadata = {
                "accession": raw_data.get("accno", "N/A"),
                "title": raw_data.get("title", "N/A"),
                "description": raw_data.get("description", "N/A"),
                "release_date": raw_data.get(
                    "rdate", raw_data.get("ReleaseDate", "N/A")
                ),
                "modification_date": raw_data.get("mdate", "N/A"),
                "type": raw_data.get("type", "N/A"),
                # VHP4Safety filterable fields (a record may carry several of
                # each, so these are lists)
                "case_study": [],
                "regulatory_question": [],
                "flow_step": [],
                "collection": "",
                "attributes": [],
                "authors": [],
                "files": [],
                "links": [],
                "protocols": [],
                "publications": [],
                "organizations": [],
                "biological_context": {},
                "technical_details": {},
                "experimental_design": {},
                "raw_data": raw_data,
            }

            # ---- helpers
            def _norm_attr_name(attr: dict) -> str:
                return (attr.get("name") or "").strip().lower()

            def _attr_value(attr: dict) -> str:
                v = attr.get("value", "")
                return "" if v is None else str(v)

            def _capture_vhp_fields(attr_name: str, attr_value: str):
                # case study / regulatory question / process flow step can each
                # appear multiple times in a submission; collect all (deduped,
                # order-preserving).
                field = {
                    "case study": "case_study",
                    "regulatory question": "regulatory_question",
                    "process flow step": "flow_step",
                }.get(attr_name)
                if attr_name == "attachto":
                    metadata["collection"] = attr_value
                elif field and attr_value and attr_value not in metadata[field]:
                    metadata[field].append(attr_value)

            BIO_KEYS = {
                "organism",
                "species",
                "organism part",
                "organ",
                "cell type",
                "tissue",
                "disease",
                "disease state",
                "sample type",
            }
            TECH_KEYS = {
                "platform",
                "instrument",
                "assay",
                "assay type",
                "library strategy",
                "library source",
                "data type",
                "sequencing mode",
                "sequencing date",
                "index adapters",
                "pipeline",
            }
            AUTHOR_KEYS = {"author", "authors", "contact", "submitter"}

            def _categorize(attr_name: str, attr_value: str):
                if attr_name in BIO_KEYS:
                    metadata["biological_context"][attr_name] = attr_value
                elif attr_name in TECH_KEYS:
                    metadata["technical_details"][attr_name] = attr_value
                elif attr_name in AUTHOR_KEYS:
                    if attr_value and attr_value not in metadata["authors"]:
                        metadata["authors"].append(attr_value)

            def _file_attrs_map(fobj: dict) -> dict:
                out = {}
                for a in (fobj or {}).get("attributes", []) or []:
                    n = (a.get("name") or "").strip()
                    if n:
                        out[n] = a.get("value")
                return out

            def _iter_section_files(sec: dict):
                if not isinstance(sec, dict):
                    return
                if isinstance(sec.get("files"), list):
                    for f in sec["files"]:
                        yield f
                if isinstance(sec.get("subsections"), list):
                    for s in sec["subsections"]:
                        yield from _iter_section_files(s)

            seen_files = set()

            def _add_files(files_list):
                if not isinstance(files_list, list):
                    return

                accno = metadata.get("accession") or raw_data.get("accno") or "N/A"

                for f in files_list:
                    if not isinstance(f, dict):
                        continue

                    file_path = (
                        f.get("path") or f.get("name") or f.get("filename") or ""
                    ).strip()
                    if not file_path:
                        continue

                    dedupe_key = f"{accno}::{file_path}"
                    if dedupe_key in seen_files:
                        continue
                    seen_files.add(dedupe_key)

                    fam = _file_attrs_map(f)
                    url = self.build_biostudies_https_file_url(accno, file_path)

                    entry = {
                        "name": file_path,
                        "path": file_path,
                        "size": f.get("size"),
                        "type": f.get("type"),
                        "description": fam.get("Description")
                        or fam.get("description")
                        or "",
                        "file_kind": fam.get("Type") or fam.get("type") or "",
                        "attributes": f.get("attributes", []),
                        "url": url,
                        "exists_check": None,
                        "raw": f,
                    }

                    if validate_files and url:
                        entry["exists_check"] = self.url_exists_no_download(
                            url, timeout=file_timeout
                        )

                    metadata["files"].append(entry)

            # ---- top-level attributes
            if isinstance(raw_data.get("attributes"), list):
                for attr in raw_data["attributes"]:
                    if not isinstance(attr, dict):
                        continue
                    name_raw = attr.get("name", "")
                    attr_name = _norm_attr_name(attr)
                    value = _attr_value(attr)

                    metadata["attributes"].append({"name": name_raw, "value": value})
                    _capture_vhp_fields(attr_name, value)
                    _categorize(attr_name, value)

            # ---- org lookup
            organization_lookup = {}
            if isinstance(raw_data.get("section"), dict):
                self._build_organization_lookup(
                    raw_data["section"], organization_lookup
                )

            # ---- section attributes
            section = (
                raw_data.get("section")
                if isinstance(raw_data.get("section"), dict)
                else None
            )
            if section and isinstance(section.get("attributes"), list):
                for attr in section["attributes"]:
                    if not isinstance(attr, dict):
                        continue
                    name_raw = attr.get("name", "")
                    attr_name = _norm_attr_name(attr)
                    value = _attr_value(attr)

                    if attr_name == "title" and (
                        metadata["title"] == "N/A" or not metadata["title"]
                    ):
                        metadata["title"] = value
                    elif attr_name == "description" and (
                        metadata["description"] == "N/A" or not metadata["description"]
                    ):
                        metadata["description"] = value

                    _capture_vhp_fields(attr_name, value)
                    _categorize(attr_name, value)
                    metadata["attributes"].append({"name": name_raw, "value": value})

            # ---- comprehensive extraction (NO FILES inside this anymore!)
            if section:
                self._extract_comprehensive_metadata(
                    section, metadata, organization_lookup
                )

            # ---- files (enriched, deduped)
            if section:
                _add_files(list(_iter_section_files(section)))
            if isinstance(raw_data.get("files"), list):
                _add_files(raw_data["files"])

            # ---- links + publications
            def _add_links(links_list):
                if not isinstance(links_list, list):
                    return
                for link in links_list:
                    if not isinstance(link, dict):
                        continue
                    link_data = {
                        "url": link.get("url", ""),
                        "type": link.get("type", ""),
                        "description": link.get("description", ""),
                        "attributes": link.get("attributes", []),
                    }
                    metadata["links"].append(link_data)

                    link_type = (link.get("type", "") or "").lower()
                    if (
                        ("doi" in link_type)
                        or ("pubmed" in link_type)
                        or ("publication" in link_type)
                    ):
                        metadata["publications"].append(link_data)

            _add_links(raw_data.get("links"))
            if section:
                _add_links(section.get("links"))

            # pick ro-crate link from available files -> requires filename to contain "rocrate"
            rocrate = self._pick_rocrate_file(metadata.get("files", []))
            metadata["rocrate_file"] = (
                rocrate  # full dict (name/path/url/size/exists_check...)
            )
            metadata["rocrate_url"] = (
                rocrate.get("url") if isinstance(rocrate, dict) else None
            )

            return metadata

        except Exception as e:
            return {
                "error": f"Failed to parse metadata: {str(e)}",
                "raw_data": raw_data,
            }

    # -----------------------------
    # Organisation lookup / deep extraction
    # -----------------------------
    def _build_organization_lookup(self, section, org_lookup):
        """Build a lookup table for organization references"""
        if isinstance(section, dict):
            if section.get("type", "").lower() in ["organization", "organisation"]:
                org_id = section.get("accno", "")
                if org_id and "attributes" in section:
                    org_data = {}
                    for attr in section["attributes"]:
                        attr_name = (attr.get("name", "") or "").lower()
                        attr_value = attr.get("value", "")
                        if attr_name in [
                            "name",
                            "organization",
                            "email",
                            "address",
                            "department",
                            "affiliation",
                        ]:
                            org_data[attr_name] = attr_value
                    if org_data:
                        org_lookup[org_id] = org_data

            if "subsections" in section:
                for subsection in section["subsections"]:
                    self._build_organization_lookup(subsection, org_lookup)

        elif isinstance(section, list):
            for item in section:
                self._build_organization_lookup(item, org_lookup)

    def _extract_comprehensive_metadata(
        self, section, metadata, organization_lookup=None
    ):
        """
        Comprehensively extract metadata from sections/subsections.

        IMPORTANT FIX:
        - DO NOT append files here (to avoid duplicates). Files are handled in parse_metadata().
        """
        if organization_lookup is None:
            organization_lookup = {}

        if isinstance(section, dict):
            # ---- protocols
            if (
                section.get("type", "").lower() == "protocols"
                or "protocol" in section.get("type", "").lower()
            ):
                if "subsections" in section:
                    for protocol in section["subsections"]:
                        protocol_data = {
                            "type": protocol.get("type", ""),
                            "description": protocol.get("description", ""),
                            "attributes": [],
                        }

                        if "attributes" in protocol:
                            for attr in protocol["attributes"]:
                                protocol_data["attributes"].append(
                                    {
                                        "name": attr.get("name", ""),
                                        "value": attr.get("value", ""),
                                    }
                                )

                        metadata["protocols"].append(protocol_data)

            # ---- author and organization information
            if section.get("type", "").lower() in ["author", "contact", "person"]:
                if "attributes" in section:
                    author_info = {}
                    author_affiliation_ref = None

                    for attr in section["attributes"]:
                        attr_name = (attr.get("name", "") or "").lower()
                        attr_value = attr.get("value", "")

                        if attr_name in [
                            "name",
                            "first name",
                            "last name",
                            "email",
                            "e-mail",
                            "orcid",
                        ]:
                            author_info[attr_name] = attr_value
                        elif attr_name == "affiliation" and attr.get("reference"):
                            author_affiliation_ref = attr_value

                    if author_info:
                        author_name = author_info.get("name", "")
                        if not author_name:
                            first = author_info.get("first name", "")
                            last = author_info.get("last name", "")
                            author_name = f"{first} {last}".strip()

                        email = author_info.get("email") or author_info.get(
                            "e-mail", ""
                        )
                        orcid = author_info.get("orcid") or None

                        author_entry = {
                            "name": author_name,
                            "email": email,
                            "orcid": orcid,
                            "affiliation_ref": author_affiliation_ref,
                            "affiliation_name": "",
                        }

                        if (
                            author_affiliation_ref
                            and author_affiliation_ref in organization_lookup
                        ):
                            resolved_org = organization_lookup[author_affiliation_ref]
                            author_entry["affiliation_name"] = resolved_org.get(
                                "name", ""
                            )

                        if author_name:
                            existing_author = next(
                                (
                                    a
                                    for a in metadata.get("author_details", [])
                                    if a.get("name") == author_name
                                ),
                                None,
                            )
                            if not existing_author:
                                metadata.setdefault("author_details", []).append(
                                    author_entry
                                )

                            if author_name not in metadata["authors"]:
                                metadata["authors"].append(author_name)

            # ---- experimental design info
            if "attributes" in section:
                for attr in section["attributes"]:
                    attr_name = (attr.get("name", "") or "").lower()
                    attr_value = attr.get("value", "")

                    if attr_name in [
                        "experimental factor",
                        "variable",
                        "treatment",
                        "condition",
                        "time point",
                    ]:
                        metadata["experimental_design"].setdefault(
                            "factors", []
                        ).append({"name": attr_name, "value": attr_value})

            # ---- recurse
            if "subsections" in section:
                for subsection in section["subsections"]:
                    self._extract_comprehensive_metadata(
                        subsection, metadata, organization_lookup
                    )

        elif isinstance(section, list):
            for item in section:
                self._extract_comprehensive_metadata(
                    item, metadata, organization_lookup
                )
