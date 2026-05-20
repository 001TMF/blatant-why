#!/usr/bin/env python3
"""Normalize raw MCP scoring output into a tidy per-design CSV.

The BY screening MCP server returns JSON in several shapes depending on which
tool was called: `score_ipsae` returns directional scores, `screen_composite`
returns nested scoring + liabilities + developability, `interpret_scores`
returns prose. This script flattens whichever shape is present into a single
row per design with consistent column names that `screen_batch.py` consumes.

Accepted input shapes:
  1. List of design records:
       [{"name": "...", "iptm": ..., "ipsae_min": ..., ...}, ...]
  2. Single record with a "designs" key:
       {"designs": [{...}, ...]}
  3. Map of name -> record:
       {"d_001": {"iptm": ...}, "d_002": {...}}
  4. Per-design ipSAE result list:
       [{"name": "d_001", "design_ipsae_min": 0.65, ...}]

Output (CSV) columns (always emitted; null when source lacks the field):
  name, sequence, modality, iptm, plddt, rmsd_ca, ipsae_min,
  design_to_target_ipsae, target_to_design_ipsae,
  liability_count, net_charge, hydrophobic_fraction,
  cdr_regions (JSON string), notes

Example:
  python parse_scores.py --input raw_mcp_output.json --output scores_tidy.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


OUTPUT_FIELDS = [
    "name",
    "sequence",
    "modality",
    "iptm",
    "plddt",
    "rmsd_ca",
    "ipsae_min",
    "design_to_target_ipsae",
    "target_to_design_ipsae",
    "liability_count",
    "net_charge",
    "hydrophobic_fraction",
    "cdr_regions",
    "notes",
]


def _coerce_design_list(data: Any) -> list[dict[str, Any]]:
    """Normalize the input JSON into a list of design dicts."""
    if isinstance(data, dict):
        if "designs" in data and isinstance(data["designs"], list):
            return list(data["designs"])
        # name -> record map
        out: list[dict[str, Any]] = []
        for name, record in data.items():
            if isinstance(record, dict):
                merged = {"name": name, **record}
                out.append(merged)
        if out:
            return out
        # Single record case
        return [data]
    if isinstance(data, list):
        return list(data)
    raise ValueError("Input JSON must be a list or dict")


def _pick(d: dict[str, Any], *keys: str) -> Any:
    """Return the first present non-None value from `keys`."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    """Project a single source record to the canonical output columns."""
    name = _pick(record, "name", "design_id", "id") or "unknown"
    sequence = _pick(record, "sequence", "design_sequence", "seq") or ""
    modality = _pick(record, "modality", "design_modality") or ""

    iptm = _pick(record, "iptm", "interface_ptm", "ipTM")
    plddt = _pick(record, "plddt", "mean_plddt", "pLDDT")
    rmsd_ca = _pick(record, "rmsd_ca", "ca_rmsd", "rmsd")
    ipsae_min = _pick(record, "ipsae_min", "design_ipsae_min", "best_ipsae_min")
    dt = _pick(record, "design_to_target_ipsae", "dt_ipsae")
    td = _pick(record, "target_to_design_ipsae", "td_ipsae")

    # Nested shapes ("scores", "developability", "liabilities")
    scores = record.get("scores") if isinstance(record.get("scores"), dict) else {}
    if iptm is None:
        iptm = _pick(scores, "iptm", "interface_ptm")
    if plddt is None:
        plddt = _pick(scores, "plddt", "mean_plddt")
    if rmsd_ca is None:
        rmsd_ca = _pick(scores, "rmsd_ca", "ca_rmsd", "rmsd")
    if ipsae_min is None:
        ipsae_min = _pick(scores, "ipsae_min", "design_ipsae_min")

    devo = record.get("developability") if isinstance(record.get("developability"), dict) else {}
    liabilities = record.get("liabilities")
    liability_count = (
        len(liabilities) if isinstance(liabilities, list) else _pick(devo, "liability_count")
    )
    net_charge = _pick(devo, "net_charge", "charge")
    hydro = _pick(devo, "hydrophobic_fraction")
    cdr_regions = _pick(record, "cdr_regions") or _pick(devo, "cdr_regions")
    if cdr_regions is not None and not isinstance(cdr_regions, str):
        cdr_regions = json.dumps(cdr_regions)

    notes = _pick(record, "notes", "interpretation", "summary") or ""

    return {
        "name": name,
        "sequence": sequence,
        "modality": modality,
        "iptm": iptm,
        "plddt": plddt,
        "rmsd_ca": rmsd_ca,
        "ipsae_min": ipsae_min,
        "design_to_target_ipsae": dt,
        "target_to_design_ipsae": td,
        "liability_count": liability_count,
        "net_charge": net_charge,
        "hydrophobic_fraction": hydro,
        "cdr_regions": cdr_regions or "",
        "notes": notes,
    }


def parse_input(path: Path) -> list[dict[str, Any]]:
    """Load and flatten the input file."""
    with path.open() as f:
        data = json.load(f)
    records = _coerce_design_list(data)
    return [flatten_record(r) for r in records if isinstance(r, dict)]


def write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    """Write the tidy CSV with a stable column order."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in OUTPUT_FIELDS})


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", required=True, type=Path, help="Raw MCP JSON output")
    parser.add_argument("--output", required=True, type=Path, help="Tidy CSV path")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Input file not found: {args.input}")

    try:
        rows = parse_input(args.input)
    except (json.JSONDecodeError, ValueError) as exc:
        sys.exit(f"Could not parse input JSON: {exc}")

    write_csv(rows, args.output)
    print(f"✓ parsed scores: {len(rows)} designs -> {args.output}")


if __name__ == "__main__":
    main()
