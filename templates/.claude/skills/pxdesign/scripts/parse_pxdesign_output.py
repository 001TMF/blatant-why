#!/usr/bin/env python3
"""Parse a PXDesign output directory into a single tidy CSV of design rows.

Purpose
-------
PXDesign writes per-task ``summary.csv`` files under
``<output_dir>/design_outputs/<task_name>/summary.csv``. When the run includes
multiple hotspot batches (one task per batch), the rows are scattered across
sibling directories. This script:

1. Walks the output directory tree to discover every ``summary.csv``.
2. Loads each one with pandas.
3. Tags rows with ``task_name`` (the parent directory name) so per-hotspot
   batching is preserved.
4. Concatenates, re-ranks by ``ptx_iptm`` descending, and writes one tidy CSV.

Column contract (see ``references/filter-thresholds.md``):
- Always present: ``name``, ``sequence``, ``ptx_iptm``
- Filter columns: ``af2_easy_success``, ``af2_opt_success``,
  ``ptx_basic_success``, ``ptx_success`` (cast to bool when present)
- Extras kept verbatim if present: ``af2_binder_plddt``,
  ``af2_complex_pred_design_rmsd``, plus any other columns PXDesign emits.

The script never silently drops columns — anything PXDesign adds in a new
release propagates through.

Inputs (CLI)
------------
--output-dir    Path to the PXDesign output directory (the one passed to
                ``pxdesign pipeline -o``). Required.
--out           Output CSV path. Required.
--min-ptx-iptm  Optional float; drop rows below this ipTM before writing.
--require-pass  Optional flag; if set, only keep rows where
                ``ptx_basic_success`` is True.

Outputs
-------
- A CSV at ``--out`` with one row per design, sorted by ``ptx_iptm`` desc.
- On stdout: ``✓ Parsed N designs across M task batch(es) → <path>``

Example
-------
    python parse_pxdesign_output.py \\
        --output-dir /tmp/il6r/output \\
        --out /tmp/il6r/designs.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    sys.exit("Install with: pip install pandas")


# Filter columns we cast to bool when present
BOOL_COLUMNS = (
    "af2_easy_success",
    "af2_opt_success",
    "ptx_basic_success",
    "ptx_success",
)


def discover_summary_csvs(root: str) -> List[str]:
    """Return absolute paths to every ``summary.csv`` under ``root``.

    Walks the tree top-down. The expected layout is
    ``<root>/design_outputs/<task_name>/summary.csv`` but we accept any depth
    so that custom output trees and per-hotspot batches both work.
    """
    found: List[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if "summary.csv" in filenames:
            found.append(os.path.join(dirpath, "summary.csv"))
    return sorted(found)


def _to_bool(value: object) -> Optional[bool]:
    """Best-effort cast to bool. Accepts True/False, 1/0, 'True'/'False'."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "pass"}:
            return True
        if v in {"false", "0", "no", "fail"}:
            return False
        if v in {"", "nan", "na", "none"}:
            return None
    return None


def load_one(path: str) -> pd.DataFrame:
    """Load one PXDesign ``summary.csv`` and tag it with its task name."""
    df = pd.read_csv(path)
    task_name = os.path.basename(os.path.dirname(path))
    df["task_name"] = task_name
    df["source_csv"] = path
    for col in BOOL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(_to_bool)
    if "sequence" in df.columns:
        df["binder_length"] = df["sequence"].astype(str).str.len()
    return df


def combine_and_rank(frames: List[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate per-task frames, re-rank by ``ptx_iptm`` desc, add ``rank``."""
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)
    if "ptx_iptm" in combined.columns:
        combined = combined.sort_values(
            "ptx_iptm", ascending=False, na_position="last"
        ).reset_index(drop=True)
    combined.insert(0, "rank", range(1, len(combined) + 1))
    # Promote core identity columns to the front when present
    front = [
        "rank",
        "name",
        "task_name",
        "sequence",
        "binder_length",
        "ptx_iptm",
        "ptx_success",
        "ptx_basic_success",
        "af2_easy_success",
        "af2_opt_success",
    ]
    ordered = [c for c in front if c in combined.columns]
    rest = [c for c in combined.columns if c not in ordered]
    return combined[ordered + rest]


def apply_filters(
    df: pd.DataFrame,
    min_ptx_iptm: Optional[float],
    require_pass: bool,
) -> pd.DataFrame:
    """Optional row filtering after combine. Never mutates the input."""
    out = df
    if min_ptx_iptm is not None and "ptx_iptm" in out.columns:
        out = out[out["ptx_iptm"].fillna(-1) >= min_ptx_iptm]
    if require_pass and "ptx_basic_success" in out.columns:
        out = out[out["ptx_basic_success"] == True]  # noqa: E712 — explicit bool
    return out.reset_index(drop=True)


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Parse a PXDesign output directory into one tidy CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python parse_pxdesign_output.py "
            "--output-dir /tmp/il6r/output --out /tmp/il6r/designs.csv"
        ),
    )
    ap.add_argument(
        "--output-dir",
        required=True,
        help="PXDesign output dir (the one passed to `pxdesign pipeline -o`).",
    )
    ap.add_argument("--out", required=True, help="Output CSV path.")
    ap.add_argument(
        "--min-ptx-iptm",
        type=float,
        default=None,
        help="Optional: drop rows below this ipTM before writing.",
    )
    ap.add_argument(
        "--require-pass",
        action="store_true",
        help="Optional: keep only rows where ptx_basic_success is True.",
    )
    args = ap.parse_args()

    if not os.path.isdir(args.output_dir):
        sys.exit(f"ERROR: --output-dir not found: {args.output_dir}")

    csvs = discover_summary_csvs(args.output_dir)
    if not csvs:
        sys.exit(
            f"ERROR: no summary.csv found under {args.output_dir}. "
            f"Check stderr from the pxdesign run for an early crash."
        )

    frames: List[pd.DataFrame] = []
    for path in csvs:
        try:
            frames.append(load_one(path))
        except Exception as e:  # noqa: BLE001 — surface parse errors per file
            print(f"WARNING: failed to read {path}: {e}", file=sys.stderr)

    if not frames:
        sys.exit("ERROR: every summary.csv failed to parse. See warnings above.")

    combined = combine_and_rank(frames)
    filtered = apply_filters(
        combined,
        min_ptx_iptm=args.min_ptx_iptm,
        require_pass=args.require_pass,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    filtered.to_csv(args.out, index=False)

    n_designs = len(filtered)
    n_batches = len(csvs)
    print(
        f"✓ Parsed {n_designs} design{'s' if n_designs != 1 else ''} "
        f"across {n_batches} task batch{'es' if n_batches != 1 else ''} "
        f"→ {args.out}"
    )


if __name__ == "__main__":
    main()
