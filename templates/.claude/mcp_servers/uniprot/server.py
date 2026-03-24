#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx",
# ]
# ///
"""BY UniProt MCP Server — tools for querying the UniProt REST API."""
from __future__ import annotations

import json

import httpx
from mcp.server.fastmcp import FastMCP

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
_TIMEOUT = 30.0

mcp = FastMCP("by-uniprot")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get(url: str, params: dict | None = None) -> dict:
    """Perform an async GET against the UniProt REST API and return JSON."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _safe_get(d: dict, *keys: str, default: str = "") -> str:
    """Walk nested dicts/lists safely, returning *default* on any miss."""
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        elif isinstance(cur, list) and cur:
            cur = cur[0]
            if isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return default
        else:
            return default
        if cur is None:
            return default
    return cur if isinstance(cur, str) else default


def _extract_function(entry: dict) -> str:
    """Extract the function description from a full UniProt entry."""
    comments = entry.get("comments", [])
    for c in comments:
        if c.get("commentType") == "FUNCTION":
            texts = c.get("texts", [])
            if texts:
                return texts[0].get("value", "")
    return ""


def _extract_subcellular_location(entry: dict) -> str:
    """Extract subcellular location string from a full UniProt entry."""
    comments = entry.get("comments", [])
    for c in comments:
        if c.get("commentType") == "SUBCELLULAR LOCATION":
            locations = c.get("subcellularLocations", [])
            parts: list[str] = []
            for loc in locations:
                location_val = loc.get("location", {})
                val = location_val.get("value", "") if isinstance(location_val, dict) else ""
                if val:
                    parts.append(val)
            if parts:
                return "; ".join(parts)
    return ""


def _extract_gene_name(entry: dict) -> str:
    """Extract the primary gene name from a UniProt entry."""
    genes = entry.get("genes", [])
    if genes:
        gene_name = genes[0].get("geneName", {})
        if isinstance(gene_name, dict):
            return gene_name.get("value", "")
    return ""


def _extract_organism(entry: dict) -> str:
    """Extract organism scientific name from a UniProt entry."""
    organism = entry.get("organism", {})
    return organism.get("scientificName", "")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def uniprot_search(query: str, max_results: int = 10) -> str:
    """Search UniProt by text, gene name, or organism.

    Args:
        query: Free-text search query (e.g. gene name, protein name, organism).
        max_results: Maximum number of results to return (default 10).

    Returns:
        JSON array of matching proteins with accession, name, organism,
        gene_name, length, and reviewed status.
    """
    try:
        data = await _get(
            f"{UNIPROT_BASE}/search",
            params={"query": query, "format": "json", "size": max_results},
        )
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"UniProt API error: {exc.response.status_code}"})
    except httpx.RequestError as exc:
        return json.dumps({"error": f"Request failed: {exc}"})

    results: list[dict] = []
    for entry in data.get("results", []):
        protein_desc = entry.get("proteinDescription", {})
        rec_name = protein_desc.get("recommendedName", {})
        full_name = rec_name.get("fullName", {})
        name = full_name.get("value", "") if isinstance(full_name, dict) else ""
        if not name:
            sub_names = protein_desc.get("submissionNames", [])
            if sub_names:
                name = sub_names[0].get("fullName", {}).get("value", "")

        entry_type = entry.get("entryType", "")
        reviewed = "Swiss-Prot" in entry_type

        results.append({
            "accession": entry.get("primaryAccession", ""),
            "name": name,
            "organism": _extract_organism(entry),
            "gene_name": _extract_gene_name(entry),
            "length": entry.get("sequence", {}).get("length", 0),
            "reviewed": reviewed,
        })

    return json.dumps(results, indent=2)


@mcp.tool()
async def uniprot_fetch_protein(accession: str) -> str:
    """Fetch full protein record from UniProt by accession.

    Args:
        accession: UniProt accession code (e.g. P04637, Q9Y6K9).

    Returns:
        JSON object with accession, name, organism, gene_name, sequence,
        length, function_description, and subcellular_location.
    """
    try:
        entry = await _get(f"{UNIPROT_BASE}/{accession}", params={"format": "json"})
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"UniProt API error: {exc.response.status_code}"})
    except httpx.RequestError as exc:
        return json.dumps({"error": f"Request failed: {exc}"})

    protein_desc = entry.get("proteinDescription", {})
    rec_name = protein_desc.get("recommendedName", {})
    full_name = rec_name.get("fullName", {})
    name = full_name.get("value", "") if isinstance(full_name, dict) else ""
    if not name:
        sub_names = protein_desc.get("submissionNames", [])
        if sub_names:
            name = sub_names[0].get("fullName", {}).get("value", "")

    seq_data = entry.get("sequence", {})

    result = {
        "accession": entry.get("primaryAccession", ""),
        "name": name,
        "organism": _extract_organism(entry),
        "gene_name": _extract_gene_name(entry),
        "sequence": seq_data.get("value", ""),
        "length": seq_data.get("length", 0),
        "function_description": _extract_function(entry),
        "subcellular_location": _extract_subcellular_location(entry),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
async def uniprot_get_domains(accession: str) -> str:
    """Get domain and region annotations for a UniProt protein.

    Parses features of type Domain, Region, and Binding site.

    Args:
        accession: UniProt accession code (e.g. P04637).

    Returns:
        JSON array of domain annotations with type, description, start, and end.
    """
    try:
        entry = await _get(f"{UNIPROT_BASE}/{accession}", params={"format": "json"})
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"UniProt API error: {exc.response.status_code}"})
    except httpx.RequestError as exc:
        return json.dumps({"error": f"Request failed: {exc}"})

    target_types = {"Domain", "Region", "Binding site"}
    domains: list[dict] = []

    for feat in entry.get("features", []):
        feat_type = feat.get("type", "")
        if feat_type not in target_types:
            continue

        location = feat.get("location", {})
        start_pos = location.get("start", {})
        end_pos = location.get("end", {})

        domains.append({
            "type": feat_type,
            "description": feat.get("description", ""),
            "start": start_pos.get("value", 0) if isinstance(start_pos, dict) else 0,
            "end": end_pos.get("value", 0) if isinstance(end_pos, dict) else 0,
        })

    return json.dumps(domains, indent=2)


@mcp.tool()
async def uniprot_get_variants(accession: str) -> str:
    """Get known variants and mutagenesis annotations for a UniProt protein.

    Parses features of type Natural variant and Mutagenesis.

    Args:
        accession: UniProt accession code (e.g. P04637).

    Returns:
        JSON array of variant annotations with type, position, original,
        variation, and description.
    """
    try:
        entry = await _get(f"{UNIPROT_BASE}/{accession}", params={"format": "json"})
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"UniProt API error: {exc.response.status_code}"})
    except httpx.RequestError as exc:
        return json.dumps({"error": f"Request failed: {exc}"})

    target_types = {"Natural variant", "Mutagenesis"}
    variants: list[dict] = []

    for feat in entry.get("features", []):
        feat_type = feat.get("type", "")
        if feat_type not in target_types:
            continue

        location = feat.get("location", {})
        start_pos = location.get("start", {})
        end_pos = location.get("end", {})

        # Position: for point variants start == end
        position = start_pos.get("value", 0) if isinstance(start_pos, dict) else 0

        # Extract alternativeSequence data
        alt_seq = feat.get("alternativeSequence", {})
        original = alt_seq.get("originalSequence", "")
        alternatives = alt_seq.get("alternativeSequences", [])
        variation = alternatives[0] if alternatives else ""

        variants.append({
            "type": feat_type,
            "position": position,
            "original": original,
            "variation": variation,
            "description": feat.get("description", ""),
        })

    return json.dumps(variants, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
