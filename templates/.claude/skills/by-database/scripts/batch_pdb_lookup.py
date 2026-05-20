#!/usr/bin/env python3
"""Batch PDB lookup — enrich a list of PDB IDs into a CSV.

Purpose
-------
Given a list of PDB IDs (CLI args, file, or stdin), query the RCSB Data API for
each entry and write a single enriched CSV with the following columns:

    pdb_id, title, method, resolution, organism, polymer_entity_count,
    chain_count, chain_ids, ligand_count, ligand_ids, release_date

Inputs
------
- A list of 4-character PDB IDs supplied via `--ids`, `--input` (file with one
  ID per line), or stdin.
- Optional `--out` path for the CSV (default: stdout).

Outputs
-------
- CSV written to `--out` (or stdout if omitted).
- On success: `✓ batch_pdb_lookup completed: <N> rows -> <path>`.

Example
-------
    python batch_pdb_lookup.py --ids 7S4S 6XWG 5JDS --out enriched.csv
    cat ids.txt | python batch_pdb_lookup.py --out enriched.csv
    python batch_pdb_lookup.py --input ids.txt --out enriched.csv

Why use this script over an MCP loop
------------------------------------
- One HTTP session with connection pooling.
- Exponential backoff on transient 429 / 5xx errors.
- Deduplicates input IDs.
- Single CSV file out instead of N JSON blobs.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Iterable

try:
    import httpx
except ImportError:
    sys.exit("Install with: pip install httpx")


RCSB_DATA_URL = "https://data.rcsb.org/rest/v1/core/entry"
RCSB_POLYMER_URL = "https://data.rcsb.org/rest/v1/core/polymer_entity"
RCSB_NONPOLY_URL = "https://data.rcsb.org/rest/v1/core/nonpolymer_entity"
TIMEOUT = 30.0
MAX_RETRIES = 4
BACKOFF_BASE = 1.5

FIELDS = [
    "pdb_id",
    "title",
    "method",
    "resolution",
    "organism",
    "polymer_entity_count",
    "chain_count",
    "chain_ids",
    "ligand_count",
    "ligand_ids",
    "release_date",
]


def _get_json_with_retry(client: httpx.Client, url: str) -> dict | list | None:
    """GET a URL with exponential backoff on 429 / 5xx; return JSON or None."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, timeout=TIMEOUT)
            if resp.status_code == 404:
                return None
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(BACKOFF_BASE ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(BACKOFF_BASE ** attempt)
    return None


def _normalize_id(raw: str) -> str | None:
    """Normalize a candidate PDB ID; return None if not 4 alphanumeric chars."""
    candidate = raw.strip().upper()
    if len(candidate) != 4 or not candidate.isalnum():
        return None
    return candidate


def _fetch_one(client: httpx.Client, pdb_id: str) -> dict:
    """Fetch entry + polymer + nonpolymer info for a single PDB ID."""
    row: dict = {field: "" for field in FIELDS}
    row["pdb_id"] = pdb_id

    entry = _get_json_with_retry(client, f"{RCSB_DATA_URL}/{pdb_id}")
    if entry is None:
        row["title"] = "NOT_FOUND"
        return row

    struct = entry.get("struct", {}) or {}
    row["title"] = struct.get("title", "")

    exptl = entry.get("exptl", [{}])
    row["method"] = exptl[0].get("method", "") if exptl else ""

    summary = entry.get("rcsb_entry_info", {}) or {}
    resolution = summary.get("resolution_combined")
    if isinstance(resolution, list) and resolution:
        resolution = resolution[0]
    row["resolution"] = resolution if resolution is not None else ""

    polymer_entity_count = summary.get("polymer_entity_count", 0)
    row["polymer_entity_count"] = polymer_entity_count

    nonpoly_ids = summary.get("nonpolymer_entity_ids", []) or []
    row["ligand_count"] = len(nonpoly_ids)

    audit = entry.get("rcsb_accession_info", {}) or {}
    row["release_date"] = audit.get("initial_release_date", "")

    # Collect chains and organism from polymer entities.
    chain_ids: list[str] = []
    organism = ""
    for entity_id in range(1, polymer_entity_count + 1):
        entity_data = _get_json_with_retry(
            client, f"{RCSB_POLYMER_URL}/{pdb_id}/{entity_id}"
        )
        if entity_data is None:
            continue
        entity_poly = entity_data.get("entity_poly", {}) or {}
        chains_str = entity_poly.get("pdbx_strand_id", "")
        for c in chains_str.split(","):
            c = c.strip()
            if c and c not in chain_ids:
                chain_ids.append(c)
        if not organism:
            src = entity_data.get("rcsb_entity_source_organism", []) or []
            if src:
                organism = src[0].get("scientific_name", "")
    row["chain_count"] = len(chain_ids)
    row["chain_ids"] = ";".join(chain_ids)
    row["organism"] = organism

    # Collect ligand identifiers from nonpolymer entities.
    ligand_ids: list[str] = []
    for nonpoly_id in nonpoly_ids:
        nonpoly = _get_json_with_retry(
            client, f"{RCSB_NONPOLY_URL}/{pdb_id}/{nonpoly_id}"
        )
        if nonpoly is None:
            continue
        comp = nonpoly.get("pdbx_entity_nonpoly", {}) or {}
        name = comp.get("comp_id") or comp.get("name") or ""
        if name and name not in ligand_ids:
            ligand_ids.append(name)
    row["ligand_ids"] = ";".join(ligand_ids)
    return row


def enrich_pdb_ids(pdb_ids: Iterable[str]) -> list[dict]:
    """Enrich a sequence of PDB IDs into row dicts. Public for library use."""
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in pdb_ids:
        norm = _normalize_id(raw)
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(norm)
    if not deduped:
        return []

    rows: list[dict] = []
    with httpx.Client() as client:
        for pdb_id in deduped:
            rows.append(_fetch_one(client, pdb_id))
    return rows


def _read_input(args: argparse.Namespace) -> list[str]:
    """Collect PDB IDs from --ids, --input, or stdin (in that order)."""
    if args.ids:
        return list(args.ids)
    if args.input:
        text = Path(args.input).read_text()
        return [line.strip() for line in text.splitlines() if line.strip()]
    if not sys.stdin.isatty():
        return [line.strip() for line in sys.stdin if line.strip()]
    return []


def _write_csv(rows: list[dict], out_path: str | None) -> str:
    """Write rows to CSV; return the destination string for the success message."""
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        f = open(out_path, "w", newline="")
        destination = out_path
    else:
        f = sys.stdout
        destination = "stdout"
    try:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    finally:
        if out_path:
            f.close()
    return destination


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enrich a list of PDB IDs into a CSV via the RCSB Data API.",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        help="One or more PDB IDs (space-separated).",
    )
    parser.add_argument(
        "--input",
        help="Path to a text file with one PDB ID per line.",
    )
    parser.add_argument(
        "--out",
        help="Output CSV path. If omitted, writes to stdout.",
    )
    args = parser.parse_args()

    ids = _read_input(args)
    if not ids:
        parser.error("Provide PDB IDs via --ids, --input, or stdin.")

    rows = enrich_pdb_ids(ids)
    if not rows:
        sys.exit("No valid 4-character PDB IDs found in input.")

    destination = _write_csv(rows, args.out)
    print(
        f"✓ batch_pdb_lookup completed: {len(rows)} rows -> {destination}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
