from __future__ import annotations

import json
import re
import time
from typing import Any

import requests


class ZenodoExtractor:
    """Extractor for interacting with the Zenodo Records API.

    Defaults to community 'vhp4safety' and record type 'dataset' to match
    the user's request. Optional access_token may be provided for higher
    rate limits or accessing private records.
    """

    def __init__(
        self,
        access_token: str | None = None,
        community: str = "vhp4safety",
        record_type: str = "dataset",
        base_url: str = "https://zenodo.org/api/records",
    ) -> None:
        self.base_url = base_url
        self.community = community
        self.record_type = record_type
        self.session = requests.Session()
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Zenodo-VHP4Safety-App/1.0",
        }
        if access_token:
            # Use Authorization header when token is provided
            self.headers["Authorization"] = f"Bearer {access_token}"

    def validate_record_id(self, record_id: Any) -> tuple[bool, Any, str | None]:
        """Validate a Zenodo record identifier.

        Accepts numeric recid (int or numeric string) or DOI (10.xxxx/...).

        Returns:
            (is_valid, normalized_id, error_message)
        """
        if record_id is None:
            return False, None, "Record ID is required"

        # numeric recid
        try:
            if isinstance(record_id, int):
                return True, record_id, None
            if isinstance(record_id, str) and record_id.isdigit():
                return True, int(record_id), None
        except Exception:
            pass

        # DOI pattern
        if isinstance(record_id, str):
            # strip DOI url wrapper
            candidate = record_id.strip()
            # DOI url like https://doi.org/10.5281/zenodo.1234
            if candidate.startswith("http") and "doi.org" in candidate:
                candidate = candidate.split("doi.org/", 1)[-1]

            doi_regex = r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$"
            if re.match(doi_regex, candidate, flags=re.IGNORECASE):
                return True, candidate, None

        return (
            False,
            record_id,
            "Invalid Zenodo record identifier (expect recid or DOI)",
        )

    def build_record_url(self, record_id: Any) -> dict[str, Any]:
        """Build a public URL for a record identifier (recid or DOI)."""
        is_valid, normalized, error = self.validate_record_id(record_id)
        if not is_valid:
            return {"error": error}

        if isinstance(normalized, int):
            url = f"https://zenodo.org/records/{normalized}"
        else:
            # DOI string
            url = f"https://doi.org/{normalized}"

        return {"id": normalized, "url": url}

    def get_record_metadata(self, record_id: Any) -> dict[str, Any]:
        """Retrieve and normalize metadata for a single record.

        If record_id is a DOI string, perform a search for that DOI and
        return the first match's parsed metadata.
        """
        try:
            is_valid, normalized, validation_error = self.validate_record_id(record_id)
            if not is_valid:
                return {"error": validation_error}

            # If numeric recid, retrieve directly
            if isinstance(normalized, int):
                url = f"{self.base_url}/{normalized}"
                resp = self.session.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        parsed = self.parse_metadata(data)
                        parsed_url = self.build_record_url(normalized).get("url", "")
                        return parsed | {"url": parsed_url}
                    except json.JSONDecodeError as e:
                        return {"error": f"Invalid JSON response from Zenodo API: {e}"}
                elif resp.status_code == 404:
                    return {"error": f"Record '{normalized}' not found."}
                else:
                    return {"error": f"Zenodo API returned status {resp.status_code}."}

            # DOI case: search for DOI
            doi = normalized
            query = f'doi:"{doi}"'
            search = self.search_records(
                query=query, page=1, size=1, load_metadata=True
            )
            if "error" in search:
                return search
            hits = search.get("hits", [])
            if not hits:
                return {"error": f"Record with DOI '{doi}' not found."}
            # return parsed metadata from first hit
            first = hits[0]
            # parsed metadata may be under 'parsed_metadata' or 'metadata'
            parsed = first.get("parsed_metadata") or first.get("metadata")
            parsed_url = self.build_record_url(
                first.get("recid") or first.get("id") or doi
            ).get(
                "url",
                "",
            )
            return parsed | {"url": parsed_url}

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Zenodo server may be slow."}
        except requests.exceptions.ConnectionError:
            return {
                "error": "Cannot connect to Zenodo server. Check your internet connection."
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}

    def search_records(
        self,
        query: str = "",
        page: int = 1,
        size: int = 25,
        load_metadata: bool = True,
        filters: tuple[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Search Zenodo records.

        Defaults to the configured community and record_type.
        """
        try:
            if not isinstance(query, str):
                return {"error": "Query must be a string."}

            # If filters are provided, ensure metadata is loaded
            filters_applied = bool(filters)
            if filters_applied:
                load_metadata = True

            params = {
                "q": query,
                "page": page,
                "size": size,
                "communities": self.community,
                "type": self.record_type,
            }

            resp = self.session.get(
                self.base_url, headers=self.headers, params=params, timeout=30
            )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except json.JSONDecodeError as e:
                    return {"error": f"Invalid JSON response from Zenodo API: {e}"}

                hits = (
                    data.get("hits", {}).get("hits", [])
                    if isinstance(data.get("hits"), dict)
                    else data.get("hits", [])
                )
                total = (
                    data.get("hits", {}).get("total")
                    if isinstance(data.get("hits"), dict)
                    else data.get("total", 0)
                )

                if not data or (isinstance(total, int) and total == 0):
                    return {"error": "No results found.", "hits": []}

                if load_metadata:
                    hits = self._hit_metadata(hits)

                hits = self._hit_url(hits)

                if filters_applied:
                    hits = self._apply_filters(hits, filters)

                    page_size_met = len(hits) >= size
                    pages_fetched = 1
                    if not page_size_met:
                        hits, page_size_met, pages_fetched = (
                            self._backfill_filtered_results(
                                hits, page, size, filters, query
                            )
                        )

                    return {
                        "totalHits": total,
                        "hits": hits,
                        "hits_returned": len(hits),
                        "page": page,
                        "pageSize": size,
                        "pages_fetched": pages_fetched,
                        "filters_applied": True,
                        "page_size_met": page_size_met,
                    }

                return {"total": total, "hits": hits}

            elif resp.status_code == 400:
                return {"error": "Bad request. Check your search parameters."}
            elif resp.status_code == 403:
                return {
                    "error": "Access forbidden. Community or collection may be restricted."
                }
            elif resp.status_code in (500, 503):
                return {"error": "Zenodo server error. Please try again later."}
            else:
                return {"error": f"Zenodo API returned status {resp.status_code}."}

        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Zenodo server may be slow."}
        except requests.exceptions.ConnectionError:
            return {
                "error": "Cannot connect to Zenodo server. Check your internet connection."
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}

    def list_records(
        self,
        page: int = 1,
        size: int = 25,
        include_urls: bool = False,
        load_metadata: bool = False,
        filters: tuple[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """list records for the configured community/type (wrapper for search_records)."""
        # If filters provided, require metadata and URLs
        if filters:
            load_metadata = True
            include_urls = True

        result = self.search_records(
            query="", page=page, size=size, load_metadata=load_metadata, filters=filters
        )

        if include_urls and "hits" in result:
            result["hits"] = self._hit_url(result["hits"])

        return result

    def _hit_url(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for hit in hits:
            # try recid present in different keys
            recid = (
                hit.get("recid")
                or hit.get("id")
                or (hit.get("metadata", {}).get("doi") if hit.get("metadata") else None)
            )
            if recid:
                try:
                    recid_int = int(recid)
                    hit["url"] = self.build_record_url(recid_int).get("url", "")
                except Exception:
                    # fallback to DOI url
                    doi = (
                        hit.get("metadata", {}).get("doi")
                        if hit.get("metadata")
                        else None
                    )
                    if doi:
                        hit["url"] = self.build_record_url(doi).get("url", "")
        return hits

    def _hit_metadata(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach parsed metadata to each hit as 'parsed_metadata'."""
        for hit in hits:
            try:
                # some hits already include top-level fields, but parse consistently
                parsed = self.parse_metadata(hit)
                # preserve both raw and parsed
                hit["parsed_metadata"] = parsed
            except Exception:
                hit["parsed_metadata"] = {}
        return hits

    def _apply_filters(
        self, hits: list[dict[str, Any]], filters: tuple[tuple[str, str]] | None
    ) -> list[dict[str, Any]]:
        """Apply filters to hits using parsed metadata when available.

        Semantics: OR within the same field name (e.g. multiple case_study
        values match any of them), AND across different field names. Matches
        the convention used by tools/methods filters. Field matching is
        case-insensitive. For list fields (keywords, creators, communities)
        a record matches a field if ANY of its list elements contains ANY
        of the accepted values.
        """
        if not filters:
            return hits

        # Group accepted values by field name, lowercased for case-insensitive
        # comparison.
        accepted_by_field: dict[str, list[str]] = {}
        for field, value in filters:
            accepted_by_field.setdefault(field, []).append(value.lower())

        filtered: list[dict[str, Any]] = []
        for hit in hits:
            metadata = hit.get("parsed_metadata") or hit.get("metadata") or {}
            if not metadata:
                continue

            matches_all_fields = True
            for field, accepted in accepted_by_field.items():
                field_value = metadata.get(field, "")

                if isinstance(field_value, list):
                    found = False
                    for item in field_value:
                        if isinstance(item, dict):
                            text = " ".join(
                                str(v) for v in item.values() if isinstance(v, str)
                            ).lower()
                        else:
                            text = str(item).lower()
                        if any(v in text for v in accepted):
                            found = True
                            break
                    if not found:
                        matches_all_fields = False
                        break
                else:
                    if not isinstance(field_value, str):
                        field_value = str(field_value)
                    fv = field_value.lower()
                    if not any(v == fv or v in fv for v in accepted):
                        matches_all_fields = False
                        break

            if matches_all_fields:
                filtered.append(hit)

        return filtered

    def _backfill_filtered_results(
        self,
        initial_hits: list[dict[str, Any]],
        page: int,
        page_size: int,
        filters: tuple[tuple[str, str]] | None,
        query: None | str = None,
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """Fetch subsequent pages until page_size filtered results are collected or timeout.

        Returns (filtered_hits_trimmed, page_size_met, pages_fetched).
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
                params = {
                    "q": query or "",
                    "page": current_page,
                    "size": page_size,
                    "communities": self.community,
                    "type": self.record_type,
                }
                resp = self.session.get(
                    self.base_url, headers=self.headers, params=params, timeout=30
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                next_hits = (
                    data.get("hits", {}).get("hits", [])
                    if isinstance(data.get("hits"), dict)
                    else data.get("hits", [])
                )
                if not next_hits:
                    break

                next_hits = self._hit_metadata(next_hits)
                next_hits = self._hit_url(next_hits)
                next_filtered = self._apply_filters(next_hits, filters)
                filtered.extend(next_filtered)
                pages_fetched += 1

            except Exception:
                break

        page_size_met = len(filtered) >= page_size
        return filtered[:page_size], page_size_met, pages_fetched

    def parse_metadata(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        """Normalize Zenodo record structure into a simpler metadata dict.

        Accepts either a full record returned from /api/records/:id or a hit
        element from a search response.
        """
        try:
            # Zenodo typically nests useful fields under 'metadata'
            raw = raw_record.get("metadata", raw_record)

            metadata: dict[str, Any] = {
                "id": raw_record.get("id")
                or raw_record.get("recid")
                or raw.get("recid"),
                "recid": raw_record.get("recid") or raw_record.get("id"),
                "doi": raw.get("doi"),
                "doi_url": raw_record.get("doi_url") or raw.get("doi_url"),
                "title": raw.get("title", "N/A"),
                "description": raw.get("description", "N/A"),
                "publication_date": raw.get(
                    "publication_date", raw.get("publication_date", "N/A")
                ),
                "access_right": raw.get("access_right"),
                "creators": raw.get("creators", []),
                "keywords": raw.get("keywords", []),
                "resource_type": raw.get("resource_type", {}),
                "license": raw.get("license", {}),
                "grants": raw.get("grants", []),
                "communities": raw.get("communities", []),
                "related_identifiers": raw.get(
                    "related_identifiers", raw.get("related_identifiers", [])
                ),
                "files": [],
                "links": raw_record.get("links", {}),
                "stats": raw_record.get("stats", {}),
                "raw": raw_record,
            }

            # Extract files if available at top-level or under raw
            files = raw_record.get("files") or raw.get("files") or []
            is_rocrate = False
            for f in files:
                if f.get("key", "").lower() == "rocrate-metadata.json":
                    is_rocrate = True
                metadata["files"].append(
                    {
                        "id": f.get("id"),
                        "key": f.get("key") or f.get("name"),
                        "size": f.get("size"),
                        "checksum": f.get("checksum"),
                        "links": f.get("links", {}),
                    }
                )
            metadata["is_rocrate"] = is_rocrate

            return metadata

        except Exception as e:
            return {"error": f"Failed to parse metadata: {e}", "raw": raw_record}
