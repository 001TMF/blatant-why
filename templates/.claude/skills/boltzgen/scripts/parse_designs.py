#!/usr/bin/env python3
"""parse_designs.py — Flatten a BoltzGen output directory into a single CSV.

BoltzGen writes one or more per-seed metrics CSVs under
``<output>/final_ranked_designs/final_designs_metrics_*.csv``. For
multi-seed ensembles this script merges them and normalises column names,
adds a ``seed`` column derived from the file name, and writes a single
canonical CSV ranked by ``iptm`` descending.

Inputs (CLI flags):
    --output-dir PATH    BoltzGen output directory (required).
                         Expected to contain a ``final_ranked_designs/``
                         subdirectory with one or more metrics CSVs.
    --csv PATH           Path to write the merged CSV (default:
                         <output-dir>/designs.csv)
    --include-sequences  Keep the ``sequence`` column (default: on)
    --no-sequences       Drop the ``sequence`` column (smaller CSV)
    --min-iptm FLOAT     Optional hard filter on iptm before writing

Outputs:
    A single CSV with one row per design, columns:
        seed, design_id, iptm, ptm, plddt, design_iptm, ipsae_min,
        rmsd, sequence (optional)
    Console verification:
        ✓ parse_designs completed: <N> rows / <path>

Example invocation:
    python parse_designs.py --output-dir workspace/output --csv workspace/designs.csv
    python parse_designs.py --output-dir workspace/output --no-sequences --min-iptm 0.5
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable


CANONICAL_COLUMNS = [
    "seed",
    "design_id",
    "iptm",
    "ptm",
    "plddt",
    "design_iptm",
    "ipsae_min",
    "rmsd",
    "sequence",
]

# Map BoltzGen column-name variants seen across versions to the canonical set.
COLUMN_ALIASES = {
    "id": "design_id",
    "name": "design_id",
    "ipTM": "iptm",
    "ipsae": "ipsae_min",
    "ipsae_minimum": "ipsae_min",
    "ipSAE_min": "ipsae_min",
    "pLDDT": "plddt",
    "rmsd_ca": "rmsd",
    "ca_rmsd": "rmsd",
    "seq": "sequence",
}

SEED_RE = re.compile(r"final_designs_metrics(?:_seed)?_?(\d+)?", re.IGNORECASE)


def find_metrics_csvs(output_dir: Path) -> list[Path]:
    """Locate metrics CSVs under ``output_dir``.

    Looks first in ``final_ranked_designs/`` then falls back to a recursive
    search. Returns sorted absolute paths.
    """
    primary = output_dir / "final_ranked_designs"
    csvs: list[Path] = []
    if primary.exists():
        csvs.extend(sorted(primary.glob("final_designs_metrics*.csv")))
    if not csvs:
        csvs = sorted(output_dir.rglob("final_designs_metrics*.csv"))
    return csvs


def seed_from_filename(path: Path) -> int:
    """Extract a seed integer from a metrics CSV file name.

    Conventions seen:
      - final_designs_metrics_0.csv      -> 0
      - final_designs_metrics_seed_3.csv -> 3
      - final_designs_metrics.csv        -> 0 (single-seed run)
    """
    m = SEED_RE.search(path.stem)
    if m and m.group(1) is not None:
        return int(m.group(1))
    return 0


def normalise_row(row: dict[str, str]) -> dict[str, str]:
    """Rename known column aliases to canonical names."""
    out: dict[str, str] = {}
    for key, value in row.items():
        canonical = COLUMN_ALIASES.get(key, key)
        out[canonical] = value
    return out


def coerce_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_rows(csv_paths: Iterable[Path]) -> list[dict[str, str]]:
    """Read all CSVs and tag each row with its seed."""
    rows: list[dict[str, str]] = []
    for path in csv_paths:
        seed = seed_from_filename(path)
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                norm = normalise_row(row)
                norm["seed"] = str(seed)
                rows.append(norm)
    return rows


def filter_rows(
    rows: list[dict[str, str]],
    min_iptm: float | None,
) -> list[dict[str, str]]:
    if min_iptm is None:
        return rows
    kept = []
    for row in rows:
        iptm = coerce_float(row.get("iptm"))
        if iptm is None or iptm < min_iptm:
            continue
        kept.append(row)
    return kept


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Sort by iptm descending; designs missing iptm sink to the bottom."""

    def key(row: dict[str, str]) -> float:
        iptm = coerce_float(row.get("iptm"))
        return -1.0 if iptm is None else iptm

    return sorted(rows, key=key, reverse=True)


def write_csv(
    rows: list[dict[str, str]],
    csv_path: Path,
    include_sequences: bool,
) -> int:
    """Write rows to disk and return the row count."""
    columns = [c for c in CANONICAL_COLUMNS if include_sequences or c != "sequence"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})
    return len(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge BoltzGen output metrics into a single ranked CSV."
    )
    parser.add_argument("--output-dir", type=Path, required=True, dest="output_dir")
    parser.add_argument("--csv", type=Path, default=None, help="CSV path (default: <output-dir>/designs.csv)")
    seq_group = parser.add_mutually_exclusive_group()
    seq_group.add_argument(
        "--include-sequences",
        action="store_true",
        dest="include_sequences",
        default=True,
        help="Keep the sequence column (default)",
    )
    seq_group.add_argument(
        "--no-sequences",
        action="store_false",
        dest="include_sequences",
        help="Drop the sequence column",
    )
    parser.add_argument("--min-iptm", type=float, default=None, dest="min_iptm")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.output_dir.exists():
        sys.exit(f"output directory not found: {args.output_dir}")

    csv_paths = find_metrics_csvs(args.output_dir)
    if not csv_paths:
        sys.exit(
            f"no final_designs_metrics_*.csv found under {args.output_dir}. "
            f"Did the run finish? Check stderr and `run_config.json`."
        )

    rows = load_rows(csv_paths)
    rows = filter_rows(rows, args.min_iptm)
    rows = sort_rows(rows)

    csv_path = args.csv or (args.output_dir / "designs.csv")
    n = write_csv(rows, csv_path, args.include_sequences)
    print(f"✓ parse_designs completed: {n} rows / {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
