#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx",
# ]
# ///
"""SAbDab (Structural Antibody Database) MCP Server.

Exposes tools for querying SAbDab at https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab/
Provides antibody structure search, summary retrieval, and CDR sequence extraction.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sabdab")

BASE_URL = "https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab"

# TSV columns returned by the SAbDab summary endpoint
SUMMARY_COLUMNS = [
    "pdb", "Hchain", "Lchain", "model", "antigen_chain", "antigen_type",
    "antigen_het_name", "antigen_name", "short_header", "date", "compound",
    "organism", "heavy_species", "light_species", "antigen_species", "authors",
    "resolution", "method", "r_free", "r_factor", "scfv", "engineered",
    "heavy_subclass", "light_subclass", "light_ctype", "affinity", "delta_g",
    "affinity_method", "temperature", "pmid",
]

# CDR names in order
CDR_NAMES = ["H1", "H2", "H3", "L1", "L2", "L3"]


async def _fetch_text(client: httpx.AsyncClient, url: str, **kwargs: Any) -> str:
    """Fetch a URL and return its text content, raising on HTTP errors."""
    resp = await client.get(url, follow_redirects=True, timeout=30.0, **kwargs)
    resp.raise_for_status()
    return resp.text


def _parse_tsv(tsv_text: str) -> list[dict[str, str]]:
    """Parse SAbDab TSV text into a list of row dicts."""
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    return [dict(row) for row in reader]


def _row_to_result(row: dict[str, str]) -> dict[str, Any]:
    """Convert a raw TSV row to the standardised result dict."""
    resolution = row.get("resolution", "")
    try:
        resolution_val: float | None = float(resolution)
    except (ValueError, TypeError):
        resolution_val = None

    return {
        "pdb_id": row.get("pdb", "").strip(),
        "heavy_chain": row.get("Hchain", "").strip(),
        "light_chain": row.get("Lchain", "").strip(),
        "antigen_name": row.get("antigen_name", "").strip(),
        "antigen_chain": row.get("antigen_chain", "").strip(),
        "resolution": resolution_val,
        "species": row.get("heavy_species", "").strip(),
        "method": row.get("method", "").strip(),
    }


async def _fetch_summary_tsv(client: httpx.AsyncClient, pdb_id: str) -> str:
    """Fetch the TSV summary for a single PDB entry from SAbDab."""
    url = f"{BASE_URL}/summary/{pdb_id.lower()}/"
    return await _fetch_text(client, url)


async def _search_pdb_and_get_tsv(
    client: httpx.AsyncClient,
    pdb_id: str,
) -> str:
    """Search SAbDab for a specific PDB and retrieve the session-specific TSV.

    The search/?pdb={id} endpoint returns HTML containing a link to a
    session-specific TSV summary file. This function extracts that link
    and fetches the TSV content.
    """
    search_url = f"{BASE_URL}/search/"
    params = {"pdb": pdb_id.lower()}
    html = await _fetch_text(client, search_url, params=params)

    # Extract the session-specific summary download link.
    # The HTML contains a #downloads section with:
    #   <a href="/webapps/sabdab-sabpred/sabdab/summary/{session_id}/">summary file</a>
    # We want the session-specific one (long ID), not the per-PDB ones (4 chars).
    all_summary_links = re.findall(
        r'/webapps/sabdab-sabpred/sabdab/summary/([^/]+)/', html
    )
    session_link = None
    for link_id in all_summary_links:
        # Session IDs are longer than PDB codes (4 chars) and are not "all"
        if len(link_id) > 4 and link_id != "all":
            session_link = f"/webapps/sabdab-sabpred/sabdab/summary/{link_id}/"
            break

    if session_link is None:
        raise ValueError(
            "Could not find session-specific summary TSV link in search results. "
            "The PDB may not be in SAbDab."
        )

    summary_url = f"https://opig.stats.ox.ac.uk{session_link}"
    return await _fetch_text(client, summary_url)


# ---------------------------------------------------------------------------
# SAbDab summary caching
# ---------------------------------------------------------------------------

_SABDAB_CACHE_TTL = int(os.environ.get("SABDAB_CACHE_TTL", str(24 * 3600)))  # 24h default
_SABDAB_CACHE_DIR = Path(os.environ.get(
    "SABDAB_CACHE_DIR",
    os.path.join(os.environ.get("TMPDIR", "/tmp"), "by_sabdab_cache"),
))
_SABDAB_CACHE_FILE = _SABDAB_CACHE_DIR / "sabdab_summary_all.tsv"


def _cache_is_fresh() -> bool:
    """Return True if the cached SAbDab summary exists and is within TTL."""
    try:
        if _SABDAB_CACHE_FILE.exists():
            age = time.time() - _SABDAB_CACHE_FILE.stat().st_mtime
            return age < _SABDAB_CACHE_TTL
    except OSError:
        pass
    return False


async def _fetch_all_summary_tsv(client: httpx.AsyncClient) -> str:
    """Fetch the full SAbDab database summary as TSV (~8MB) with file caching.

    Caches the downloaded summary in a temp directory and reuses it for
    subsequent queries within the TTL (default 24 hours). This avoids
    re-downloading ~8MB on every query.
    """
    # Return cached version if fresh
    if _cache_is_fresh():
        try:
            return _SABDAB_CACHE_FILE.read_text()
        except OSError:
            pass  # Fall through to download

    # Download fresh copy
    url = f"{BASE_URL}/summary/all/"
    resp = await client.get(url, follow_redirects=True, timeout=60.0)
    resp.raise_for_status()
    tsv_text = resp.text

    # Write to cache (best-effort, non-blocking)
    try:
        _SABDAB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = _SABDAB_CACHE_FILE.with_suffix(".tmp")
        tmp_path.write_text(tsv_text)
        tmp_path.rename(_SABDAB_CACHE_FILE)
    except OSError:
        pass  # Caching failure is non-fatal

    return tsv_text


def _extract_cdrs_from_html(html: str) -> dict[str, dict[str, str | int]]:
    """Extract CDR sequences from the SAbDab structure viewer HTML.

    The viewer page has a section like:
        <tr><td><b><a href="...">CDRH1</a></b></td><td>GFNIKDY</td></tr>
        <tr><td><b><a href="...">CDRH2</a></b></td><td>DPENGN</td></tr>
        ...

    Returns a dict mapping CDR name (H1, H2, ...) to {sequence, length}.
    """
    cdrs: dict[str, dict[str, str | int]] = {}

    # Match CDR rows from the structure viewer HTML
    pattern = re.compile(
        r'CDR(H[123]|L[123])</a></b></td>\s*<td[^>]*>([A-Z]+)</td>',
        re.IGNORECASE,
    )

    for match in pattern.finditer(html):
        cdr_name = match.group(1).upper()  # H1, H2, H3, L1, L2, L3
        sequence = match.group(2).upper()
        cdrs[cdr_name] = {
            "sequence": sequence,
            "length": len(sequence),
        }

    return cdrs


@mcp.tool()
async def sabdab_search_antibodies(
    query: str = "",
    antigen: str = "",
    species: str = "",
    max_results: int = 20,
) -> str:
    """Search SAbDab for antibody structures.

    Args:
        query: PDB code or general search term. If a 4-character PDB code is
            provided, performs a direct PDB lookup. Otherwise treated as a
            keyword search against antigen names.
        antigen: Filter by antigen type (e.g. 'protein', 'peptide', 'hapten').
        species: Filter by antibody species (e.g. 'HOMO SAPIENS', 'MUS MUSCULUS').
        max_results: Maximum number of results to return (default 20).

    Returns:
        JSON list of antibody structure records with fields: pdb_id, heavy_chain,
        light_chain, antigen_name, antigen_chain, resolution, species, method.
    """
    async with httpx.AsyncClient() as client:
        try:
            is_pdb_query = (
                bool(query) and len(query.strip()) == 4 and query.strip().isalnum()
            )

            # Strategy: For PDB code queries, use the direct summary endpoint.
            # For everything else, download the full database TSV and filter
            # client-side (SAbDab's search form does not support server-side
            # keyword filtering via URL params).
            if is_pdb_query:
                pdb_code = query.strip().lower()
                try:
                    tsv_text = await _fetch_summary_tsv(client, pdb_code)
                except httpx.HTTPStatusError:
                    # Fall back to search endpoint
                    try:
                        tsv_text = await _search_pdb_and_get_tsv(client, pdb_code)
                    except (ValueError, httpx.HTTPStatusError):
                        return json.dumps({
                            "error": f"PDB {pdb_code} not found in SAbDab."
                        })
                rows = _parse_tsv(tsv_text)

            elif query or antigen or species:
                tsv_text = await _fetch_all_summary_tsv(client)
                rows = _parse_tsv(tsv_text)

                # Apply client-side filters
                if query:
                    q_lower = query.lower()
                    rows = [
                        r for r in rows
                        if q_lower in r.get("antigen_name", "").lower()
                        or q_lower in r.get("compound", "").lower()
                        or q_lower in r.get("short_header", "").lower()
                        or q_lower in r.get("organism", "").lower()
                    ]
                if antigen:
                    ant_lower = antigen.lower()
                    rows = [
                        r for r in rows
                        if ant_lower in r.get("antigen_type", "").lower()
                    ]
                if species:
                    sp_lower = species.lower()
                    rows = [
                        r for r in rows
                        if sp_lower in r.get("heavy_species", "").lower()
                        or sp_lower in r.get("light_species", "").lower()
                    ]
            else:
                return json.dumps({"error": "No search criteria provided."})

            results = [_row_to_result(r) for r in rows[:max_results]]
            return json.dumps(results, indent=2)

        except Exception as exc:
            return json.dumps({"error": f"SAbDab search failed: {exc}"})


@mcp.tool()
async def sabdab_get_structure(pdb_id: str) -> str:
    """Get antibody structure summary from SAbDab.

    Args:
        pdb_id: 4-character PDB identifier (e.g. '1ahw').

    Returns:
        JSON object with fields: pdb_id, heavy_chain, light_chain, antigen_name,
        antigen_chain, resolution, species, method, antigen_type, antigen_species,
        r_free, r_factor, scfv, engineered, heavy_subclass, light_subclass,
        light_ctype, date, cdr_lengths (if available from structure viewer).
    """
    pdb_id = pdb_id.strip().lower()
    if not pdb_id or len(pdb_id) != 4:
        return json.dumps({"error": "Invalid PDB ID. Must be a 4-character code."})

    async with httpx.AsyncClient() as client:
        try:
            # Fetch the TSV summary
            tsv_text = await _fetch_summary_tsv(client, pdb_id)
            rows = _parse_tsv(tsv_text)

            if not rows:
                return json.dumps({"error": f"No SAbDab entry found for PDB {pdb_id}."})

            # Use the first row as the primary entry (a PDB may have multiple
            # chain pairings; we return all of them).
            entries = []
            for row in rows:
                resolution = row.get("resolution", "")
                try:
                    resolution_val: float | None = float(resolution)
                except (ValueError, TypeError):
                    resolution_val = None

                r_free = row.get("r_free", "")
                try:
                    r_free_val: float | None = float(r_free)
                except (ValueError, TypeError):
                    r_free_val = None

                r_factor = row.get("r_factor", "")
                try:
                    r_factor_val: float | None = float(r_factor)
                except (ValueError, TypeError):
                    r_factor_val = None

                entry = {
                    "pdb_id": row.get("pdb", "").strip(),
                    "heavy_chain": row.get("Hchain", "").strip(),
                    "light_chain": row.get("Lchain", "").strip(),
                    "antigen_name": row.get("antigen_name", "").strip(),
                    "antigen_chain": row.get("antigen_chain", "").strip(),
                    "antigen_type": row.get("antigen_type", "").strip(),
                    "resolution": resolution_val,
                    "species": row.get("heavy_species", "").strip(),
                    "light_species": row.get("light_species", "").strip(),
                    "antigen_species": row.get("antigen_species", "").strip(),
                    "method": row.get("method", "").strip(),
                    "r_free": r_free_val,
                    "r_factor": r_factor_val,
                    "scfv": row.get("scfv", "").strip(),
                    "engineered": row.get("engineered", "").strip(),
                    "heavy_subclass": row.get("heavy_subclass", "").strip(),
                    "light_subclass": row.get("light_subclass", "").strip(),
                    "light_ctype": row.get("light_ctype", "").strip(),
                    "date": row.get("date", "").strip(),
                }
                entries.append(entry)

            # Try to get CDR lengths from the structure viewer page
            try:
                viewer_url = f"{BASE_URL}/structureviewer/?pdb={pdb_id}"
                viewer_html = await _fetch_text(client, viewer_url)
                cdrs = _extract_cdrs_from_html(viewer_html)
                if cdrs:
                    cdr_lengths = {
                        name: cdrs[name]["length"]
                        for name in CDR_NAMES
                        if name in cdrs
                    }
                    for entry in entries:
                        entry["cdr_lengths"] = cdr_lengths
            except Exception:
                # CDR extraction is best-effort; don't fail the whole request
                pass

            if len(entries) == 1:
                return json.dumps(entries[0], indent=2)
            return json.dumps({"pdb_id": pdb_id, "chain_pairings": entries}, indent=2)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return json.dumps({"error": f"PDB {pdb_id} not found in SAbDab."})
            return json.dumps({"error": f"SAbDab request failed: {exc}"})
        except Exception as exc:
            return json.dumps({"error": f"Failed to get structure summary: {exc}"})


@mcp.tool()
async def sabdab_cdr_sequences(pdb_id: str) -> str:
    """Get CDR (Complementarity-Determining Region) sequences for an antibody structure.

    Extracts CDR sequences using the Chothia numbering scheme from the SAbDab
    structure viewer.

    Args:
        pdb_id: 4-character PDB identifier (e.g. '1ahw').

    Returns:
        JSON object with fields: pdb_id, and for each CDR (H1, H2, H3, L1, L2, L3)
        a sub-object with {sequence, length}. CDRs not present in the structure
        will be omitted.
    """
    pdb_id = pdb_id.strip().lower()
    if not pdb_id or len(pdb_id) != 4:
        return json.dumps({"error": "Invalid PDB ID. Must be a 4-character code."})

    async with httpx.AsyncClient() as client:
        try:
            viewer_url = f"{BASE_URL}/structureviewer/?pdb={pdb_id}"
            html = await _fetch_text(client, viewer_url)

            cdrs = _extract_cdrs_from_html(html)

            if not cdrs:
                return json.dumps({
                    "error": f"No CDR sequences found for PDB {pdb_id}. "
                    "The structure may not be annotated in SAbDab or the viewer page "
                    "format may have changed."
                })

            result: dict[str, Any] = {"pdb_id": pdb_id}
            for name in CDR_NAMES:
                if name in cdrs:
                    result[name] = cdrs[name]
                else:
                    result[name] = None

            return json.dumps(result, indent=2)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return json.dumps({"error": f"PDB {pdb_id} not found in SAbDab."})
            return json.dumps({"error": f"SAbDab request failed: {exc}"})
        except Exception as exc:
            return json.dumps({"error": f"Failed to get CDR sequences: {exc}"})


@mcp.tool()
async def sabdab_search_by_antigen(antigen_name: str, max_results: int = 20) -> str:
    """Find antibodies targeting a specific antigen in SAbDab.

    Searches the full SAbDab database for antibody structures bound to the
    specified antigen. The search is case-insensitive and matches partial
    antigen names.

    Args:
        antigen_name: Name of the target antigen (e.g. 'HER2', 'PD-L1',
            'tissue factor', 'insulin'). Case-insensitive partial match.
        max_results: Maximum number of results to return (default 20).

    Returns:
        JSON list of antibody structure records with fields: pdb_id, heavy_chain,
        light_chain, antigen_name, antigen_chain, resolution, species, method.
    """
    if not antigen_name or not antigen_name.strip():
        return json.dumps({"error": "antigen_name is required."})

    async with httpx.AsyncClient() as client:
        try:
            # Download the full SAbDab summary and filter client-side.
            # SAbDab's web search does not support server-side keyword filtering
            # via URL parameters, so client-side filtering is the reliable approach.
            tsv_text = await _fetch_all_summary_tsv(client)
            rows = _parse_tsv(tsv_text)

            # Filter for matching antigen name (case-insensitive partial match)
            query_lower = antigen_name.strip().lower()
            filtered = [
                r for r in rows
                if query_lower in r.get("antigen_name", "").lower()
            ]

            if not filtered:
                return json.dumps({
                    "query": antigen_name,
                    "total_results": 0,
                    "results": [],
                    "message": f"No antibodies found targeting '{antigen_name}'.",
                })

            results = [_row_to_result(r) for r in filtered[:max_results]]
            return json.dumps({
                "query": antigen_name,
                "total_results": len(filtered),
                "showing": len(results),
                "results": results,
            }, indent=2)

        except Exception as exc:
            return json.dumps({"error": f"Antigen search failed: {exc}"})


if __name__ == "__main__":
    mcp.run()
