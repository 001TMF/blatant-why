#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx",
#   "biopython>=1.80",
# ]
# ///
"""PDB MCP Server — RCSB Protein Data Bank query tools for BY agent."""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pdb")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA_URL = "https://data.rcsb.org/rest/v1/core/entry"
RCSB_POLYMER_URL = "https://data.rcsb.org/rest/v1/core/polymer_entity"
RCSB_DOWNLOAD_URL = "https://files.rcsb.org/download"

TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


async def _get_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    """GET a URL and return parsed JSON, or None on failure."""
    resp = await client.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tool 1: pdb_search
# ---------------------------------------------------------------------------


@mcp.tool()
async def pdb_search(query: str, max_results: int = 10) -> str:
    """Search the RCSB Protein Data Bank by text query.

    Args:
        query: Free-text search string (e.g. "PD-L1", "insulin receptor").
        max_results: Maximum number of results to return (default 10, max 100).

    Returns:
        JSON list of matching entries with pdb_id, title, method,
        resolution, and release_date.
    """
    if not query.strip():
        return _error("Query string must not be empty.")

    max_results = min(max(1, max_results), 100)

    search_payload = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": max_results},
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RCSB_SEARCH_URL,
                json=search_payload,
                timeout=TIMEOUT,
            )
            if resp.status_code == 204:
                return json.dumps([])
            resp.raise_for_status()
            data = resp.json()

            pdb_ids = [
                hit["identifier"] for hit in data.get("result_set", [])
            ]
            if not pdb_ids:
                return json.dumps([])

            results = []
            for pdb_id in pdb_ids:
                entry_url = f"{RCSB_DATA_URL}/{pdb_id}"
                try:
                    entry = await _get_json(client, entry_url)
                    if entry is None:
                        continue
                    exptl = entry.get("exptl", [{}])
                    method = exptl[0].get("method", "unknown") if exptl else "unknown"
                    rcsb_summary = entry.get("rcsb_entry_info", {}) or {}
                    resolution = rcsb_summary.get("resolution_combined")
                    if isinstance(resolution, list) and resolution:
                        resolution = resolution[0]
                    audit = entry.get("rcsb_accession_info", {}) or {}
                    release_date = audit.get("initial_release_date", "")
                    struct = entry.get("struct", {}) or {}
                    title = struct.get("title", "")

                    results.append(
                        {
                            "pdb_id": pdb_id,
                            "title": title,
                            "method": method,
                            "resolution": resolution,
                            "release_date": release_date,
                        }
                    )
                except httpx.HTTPError:
                    results.append({"pdb_id": pdb_id, "title": "", "method": "", "resolution": None, "release_date": ""})

            return json.dumps(results, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"RCSB search request failed: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error during PDB search: {exc}")


# ---------------------------------------------------------------------------
# Tool 2: pdb_fetch_structure
# ---------------------------------------------------------------------------


@mcp.tool()
async def pdb_fetch_structure(pdb_id: str) -> str:
    """Get metadata for a PDB entry.

    Args:
        pdb_id: 4-character PDB identifier (e.g. "7S4S").

    Returns:
        JSON object with pdb_id, title, method, resolution, release_date,
        polymer_entity_count, and organism.
    """
    pdb_id = pdb_id.strip().upper()
    if len(pdb_id) != 4:
        return _error(f"Invalid PDB ID: '{pdb_id}'. Must be 4 characters.")

    try:
        async with httpx.AsyncClient() as client:
            entry_url = f"{RCSB_DATA_URL}/{pdb_id}"
            entry = await _get_json(client, entry_url)
            if entry is None:
                return _error(f"No data returned for PDB ID: {pdb_id}")

            struct = entry.get("struct", {}) or {}
            title = struct.get("title", "")

            exptl = entry.get("exptl", [{}])
            method = exptl[0].get("method", "unknown") if exptl else "unknown"

            rcsb_summary = entry.get("rcsb_entry_info", {}) or {}
            resolution = rcsb_summary.get("resolution_combined")
            if isinstance(resolution, list) and resolution:
                resolution = resolution[0]

            polymer_entity_count = rcsb_summary.get("polymer_entity_count", 0)

            audit = entry.get("rcsb_accession_info", {}) or {}
            release_date = audit.get("initial_release_date", "")

            # Try to get organism from the first polymer entity
            organism = ""
            try:
                entity_url = f"{RCSB_POLYMER_URL}/{pdb_id}/1"
                entity_data = await _get_json(client, entity_url)
                if entity_data:
                    src = entity_data.get("rcsb_entity_source_organism", [])
                    if src:
                        organism = src[0].get("scientific_name", "")
            except httpx.HTTPError:
                pass

            return json.dumps(
                {
                    "pdb_id": pdb_id,
                    "title": title,
                    "method": method,
                    "resolution": resolution,
                    "release_date": release_date,
                    "polymer_entity_count": polymer_entity_count,
                    "organism": organism,
                },
                indent=2,
            )

    except httpx.HTTPError as exc:
        return _error(f"Failed to fetch PDB entry {pdb_id}: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error fetching {pdb_id}: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: pdb_get_chains
# ---------------------------------------------------------------------------


@mcp.tool()
async def pdb_get_chains(pdb_id: str) -> str:
    """List chains (polymer entities) in a PDB structure.

    Args:
        pdb_id: 4-character PDB identifier (e.g. "7S4S").

    Returns:
        JSON list of chain objects with chain_id, entity_id, molecule_name,
        sequence, and length.
    """
    pdb_id = pdb_id.strip().upper()
    if len(pdb_id) != 4:
        return _error(f"Invalid PDB ID: '{pdb_id}'. Must be 4 characters.")

    try:
        async with httpx.AsyncClient() as client:
            # First get entry to find number of polymer entities
            entry_url = f"{RCSB_DATA_URL}/{pdb_id}"
            entry = await _get_json(client, entry_url)
            if entry is None:
                return _error(f"No data returned for PDB ID: {pdb_id}")

            rcsb_summary = entry.get("rcsb_entry_info", {}) or {}
            entity_count = rcsb_summary.get("polymer_entity_count", 0)

            chains: list[dict] = []

            for entity_id in range(1, entity_count + 1):
                try:
                    entity_url = f"{RCSB_POLYMER_URL}/{pdb_id}/{entity_id}"
                    entity_data = await _get_json(client, entity_url)
                    if entity_data is None:
                        continue

                    # Get chain IDs (auth_asym_ids) mapped to this entity
                    entity_poly = entity_data.get("entity_poly", {}) or {}
                    chain_ids_str = entity_poly.get(
                        "pdbx_strand_id", ""
                    )
                    chain_id_list = [
                        c.strip() for c in chain_ids_str.split(",") if c.strip()
                    ]

                    sequence = entity_poly.get(
                        "pdbx_seq_one_letter_code_can", ""
                    )

                    rcsb_poly = entity_data.get("rcsb_polymer_entity", {}) or {}
                    molecule_name = rcsb_poly.get(
                        "pdbx_description", ""
                    )

                    for chain_id in chain_id_list:
                        chains.append(
                            {
                                "chain_id": chain_id,
                                "entity_id": entity_id,
                                "molecule_name": molecule_name,
                                "sequence": sequence,
                                "length": len(sequence),
                            }
                        )
                except httpx.HTTPError:
                    continue

            return json.dumps(chains, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to fetch chains for {pdb_id}: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error fetching chains for {pdb_id}: {exc}")


# ---------------------------------------------------------------------------
# Tool 4: pdb_interface_residues
# ---------------------------------------------------------------------------


@mcp.tool()
async def pdb_interface_residues(
    pdb_id: str,
    chain1: str,
    chain2: str,
    distance_cutoff: float = 5.0,
) -> str:
    """Find interface residues between two chains in a PDB structure.

    Downloads the mmCIF structure and identifies residue pairs whose
    heavy atoms are within the distance cutoff.

    Args:
        pdb_id: 4-character PDB identifier.
        chain1: Author chain ID of the first chain.
        chain2: Author chain ID of the second chain.
        distance_cutoff: Distance threshold in Angstroms (default 5.0).

    Returns:
        JSON object with chain1_residues, chain2_residues (lists of
        {resname, resseq}), and contact_count.
    """
    pdb_id = pdb_id.strip().upper()
    if len(pdb_id) != 4:
        return _error(f"Invalid PDB ID: '{pdb_id}'. Must be 4 characters.")

    try:
        from Bio.PDB import MMCIFParser
    except ImportError:
        return _error(
            "BioPython is required for interface residue analysis. "
            "Install with: pip install biopython"
        )

    # Download structure
    cif_url = f"{RCSB_DOWNLOAD_URL}/{pdb_id}.cif"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(cif_url, timeout=60.0)
            resp.raise_for_status()
            cif_text = resp.text
    except httpx.HTTPError as exc:
        return _error(f"Failed to download structure {pdb_id}.cif: {exc}")

    # Parse with BioPython
    try:
        parser = MMCIFParser(QUIET=True)
        structure = parser.get_structure(pdb_id, StringIO(cif_text))
    except Exception as exc:
        return _error(f"Failed to parse mmCIF for {pdb_id}: {exc}")

    model = structure[0]

    # Validate chains exist
    available_chains = [ch.id for ch in model.get_chains()]
    if chain1 not in available_chains:
        return _error(
            f"Chain '{chain1}' not found in {pdb_id}. "
            f"Available chains: {available_chains}"
        )
    if chain2 not in available_chains:
        return _error(
            f"Chain '{chain2}' not found in {pdb_id}. "
            f"Available chains: {available_chains}"
        )

    chain_obj1 = model[chain1]
    chain_obj2 = model[chain2]

    # Collect heavy atoms per chain
    def _get_heavy_atoms(chain):
        atoms = []
        for residue in chain.get_residues():
            # Skip water and hetero residues that aren't standard amino acids
            hetfield = residue.id[0]
            if hetfield == "W":
                continue
            for atom in residue.get_atoms():
                if atom.element != "H":
                    atoms.append(atom)
        return atoms

    atoms1 = _get_heavy_atoms(chain_obj1)
    atoms2 = _get_heavy_atoms(chain_obj2)

    if not atoms1:
        return _error(f"No heavy atoms found in chain {chain1}")
    if not atoms2:
        return _error(f"No heavy atoms found in chain {chain2}")

    # Build a mapping from (chain_id, auth_seq_id) -> label_seq_id.
    # BioPython's MMCIFParser stores the _atom_site fields, but
    # label_seq_id is most reliably obtained by counting residues
    # sequentially within each chain (1-indexed, no gaps).
    label_seq_map: dict[tuple[str, int, str], int] = {}  # (chain, auth_seq_id, icode) -> label
    for ch in (chain_obj1, chain_obj2):
        label_counter = 0
        for residue in ch.get_residues():
            hetfield = residue.id[0]
            if hetfield == "W":
                continue
            label_counter += 1
            key = (ch.id, residue.id[1], residue.id[2].strip())
            label_seq_map[key] = label_counter

    # Find contacts
    cutoff_sq = distance_cutoff ** 2
    # Store tuples of (resname, auth_seq_id, icode)
    c1_interface_residues: set[tuple[str, int, str]] = set()
    c2_interface_residues: set[tuple[str, int, str]] = set()
    contact_count = 0

    for a1 in atoms1:
        r1 = a1.get_parent()
        for a2 in atoms2:
            diff = a1.get_vector() - a2.get_vector()
            dist_sq = diff[0] ** 2 + diff[1] ** 2 + diff[2] ** 2
            if dist_sq <= cutoff_sq:
                r2 = a2.get_parent()
                c1_interface_residues.add(
                    (r1.get_resname(), r1.id[1], r1.id[2].strip())
                )
                c2_interface_residues.add(
                    (r2.get_resname(), r2.id[1], r2.id[2].strip())
                )
                contact_count += 1

    def _build_residue_list(
        interface_set: set[tuple[str, int, str]], chain_id: str
    ) -> list[dict]:
        res_list = []
        for resname, auth_seq, icode in interface_set:
            label_seq = label_seq_map.get((chain_id, auth_seq, icode))
            res_list.append({
                "resname": resname,
                "label_seq_id": label_seq,  # preferred — 1-indexed sequential
                "auth_seq_id": auth_seq,     # kept for backward compat
                "resseq": auth_seq,          # deprecated alias for auth_seq_id
            })
        res_list.sort(key=lambda x: (x["label_seq_id"] or 0, x["auth_seq_id"]))
        return res_list

    chain1_res = _build_residue_list(c1_interface_residues, chain1)
    chain2_res = _build_residue_list(c2_interface_residues, chain2)

    return json.dumps(
        {
            "pdb_id": pdb_id,
            "chain1": chain1,
            "chain2": chain2,
            "distance_cutoff": distance_cutoff,
            "chain1_residues": chain1_res,
            "chain2_residues": chain2_res,
            "contact_count": contact_count,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 5: pdb_download
# ---------------------------------------------------------------------------


@mcp.tool()
async def pdb_download(
    pdb_id: str,
    format: str = "cif",
    output_dir: str = "/tmp",
) -> str:
    """Download a PDB structure file.

    Args:
        pdb_id: 4-character PDB identifier.
        format: File format — "cif" (mmCIF) or "pdb".
        output_dir: Directory to save the file (default /tmp).

    Returns:
        JSON object with path and size_bytes.
    """
    pdb_id = pdb_id.strip().upper()
    if len(pdb_id) != 4:
        return _error(f"Invalid PDB ID: '{pdb_id}'. Must be 4 characters.")

    format = format.lower().strip()
    if format not in ("cif", "pdb"):
        return _error(f"Unsupported format: '{format}'. Use 'cif' or 'pdb'.")

    ext = format
    download_url = f"{RCSB_DOWNLOAD_URL}/{pdb_id}.{ext}"

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{pdb_id}.{ext}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(download_url, timeout=60.0, follow_redirects=True)
            resp.raise_for_status()
            file_path.write_bytes(resp.content)

        size_bytes = file_path.stat().st_size
        return json.dumps(
            {"path": str(file_path), "size_bytes": size_bytes},
            indent=2,
        )

    except httpx.HTTPError as exc:
        return _error(f"Failed to download {pdb_id}.{ext}: {exc}")
    except OSError as exc:
        return _error(f"Failed to write file {file_path}: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error downloading {pdb_id}: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
