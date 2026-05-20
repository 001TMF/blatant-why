#!/usr/bin/env python3
"""Ingest a lab readout file (CSV / TSV / Excel / Adaptyv JSON) and emit
a normalized JSON record set conforming to BY's canonical schema.

Inputs:
    --input <path>          Source file (.csv, .tsv, .xlsx, .json)
    --output <path>         Output path for normalized JSON
    --assay <type>          One of: affinity_elisa, affinity_bli,
                            affinity_octet, expression_qc, polyspecificity_panel
    --aggregate <policy>    median | mean | keep-all (default: median)
    --alias <a>=<b>         Column-rename mapping; repeatable (e.g.
                            --alias design_id=variant_name --alias kd_nm=KD_nM)
    --outcome-col <name>    Column holding ground-truth outcome (default: lab_outcome)
    --outcome-pass-value <v>   Value indicating PASS (default: PASS)
    --kd-threshold-nm <f>   PASS if kd_nm <= this (default: 100)
    --binding-threshold <f> PASS if binding_signal >= this (default: 0.3)
    --lod-kd-nm <f>         Limit-of-detection for Kd; values above are CENSORED
    --batch-col <name>      Column holding batch id (optional)
    --format <type>         adaptyv-json | auto (default: auto)
    --keep-extra-col <c>    Retain a non-canonical column; repeatable

Outputs:
    JSON file at --output, containing:
        {
            "metadata": {
                "assay": ...,
                "source_file": ...,
                "aggregation_policy": ...,
                "row_count_input": N_in,
                "row_count_output": N_out,
                "warnings": [...]
            },
            "records": [
                {"design_id": ..., "lab_outcome": "PASS", "kd_nm": ..., ...},
                ...
            ]
        }

Example:
    python3 ingest_lab_results.py \\
        --input experiments/batch_001_adaptyv.csv \\
        --output campaigns/tnfa/c001/lab_results.normalized.json \\
        --assay affinity_bli \\
        --aggregate median \\
        --alias design_id=sequence_name \\
        --kd-threshold-nm 100
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    sys.exit("Install with: pip install pandas")


CANONICAL_COLUMNS: dict[str, str] = {
    "design_id": "str",
    "lab_outcome": "str",
    "assay": "str",
    "kd_nm": "float",
    "ka_per_M_per_s": "float",
    "kd_per_s": "float",
    "binding_signal": "float",
    "expression_mg_per_L": "float",
    "polyspecificity_score": "float",
    "aggregation_pct": "float",
    "replicate_id": "str",
    "batch_id": "str",
}

ASSAY_TYPES = {
    "affinity_elisa",
    "affinity_bli",
    "affinity_octet",
    "expression_qc",
    "polyspecificity_panel",
}


def parse_aliases(alias_args: list[str]) -> dict[str, str]:
    """Parse --alias canonical=source pairs into a dict."""
    mapping: dict[str, str] = {}
    for raw in alias_args:
        if "=" not in raw:
            raise SystemExit(f"--alias must be in form canonical=source; got: {raw}")
        canonical, source = raw.split("=", 1)
        mapping[canonical.strip()] = source.strip()
    return mapping


def load_source(input_path: Path, fmt: str) -> pd.DataFrame:
    """Load source file into a DataFrame; supports CSV, TSV, Excel, Adaptyv JSON."""
    suffix = input_path.suffix.lower()
    if fmt == "adaptyv-json" or (fmt == "auto" and suffix == ".json"):
        with input_path.open() as fh:
            data = json.load(fh)
        rows = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise SystemExit(f"Adaptyv JSON did not contain a results array: {input_path}")
        return pd.DataFrame(rows)
    if suffix in {".csv"}:
        return pd.read_csv(input_path)
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(input_path, sep="\t")
    if suffix in {".xlsx", ".xls"}:
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            sys.exit("Install with: pip install openpyxl")
        return pd.read_excel(input_path)
    raise SystemExit(f"Unsupported input format: {suffix}")


def apply_aliases(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    """Rename source columns to canonical names via alias map."""
    # aliases is canonical -> source; pandas rename needs source -> canonical
    rename_map = {source: canonical for canonical, source in aliases.items()}
    # Only rename columns that actually exist
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    return df.rename(columns=rename_map)


def coerce_dtypes(df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """Coerce canonical columns to declared dtypes, accumulating warnings."""
    for col, dtype in CANONICAL_COLUMNS.items():
        if col not in df.columns:
            continue
        if dtype == "float":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif dtype == "str":
            df[col] = df[col].astype("string")
    return df


def derive_outcome(
    df: pd.DataFrame,
    outcome_col: str,
    pass_value: str,
    kd_threshold_nm: float,
    binding_threshold: float,
    lod_kd_nm: float | None,
    warnings: list[str],
) -> pd.DataFrame:
    """Derive a canonical `lab_outcome` column (PASS / FAIL / CENSORED).

    Priority order:
      1. Existing categorical outcome_col matching pass_value
      2. kd_nm <= kd_threshold_nm
      3. binding_signal >= binding_threshold
    """
    # Mark censored Kd first (right-censored above LOD)
    if lod_kd_nm is not None and "kd_nm" in df.columns:
        censored_mask = df["kd_nm"].notna() & (df["kd_nm"] > lod_kd_nm)
        df.loc[censored_mask, "_censored"] = True
    else:
        df["_censored"] = False

    # If user-specified outcome column exists, use it directly
    if outcome_col in df.columns:
        normalized = (
            df[outcome_col]
            .astype("string")
            .str.strip()
            .str.upper()
        )
        target = str(pass_value).strip().upper()
        df["lab_outcome"] = normalized.where(
            normalized.isin([target, "PASS", "FAIL"]),
            other="FAIL",
        )
        # Re-map vendor categorical to canonical PASS/FAIL
        df["lab_outcome"] = df["lab_outcome"].where(
            df["lab_outcome"] == target, "FAIL"
        )
        df.loc[df["lab_outcome"] == target, "lab_outcome"] = "PASS"
    elif "kd_nm" in df.columns and df["kd_nm"].notna().any():
        df["lab_outcome"] = "FAIL"
        df.loc[df["kd_nm"] <= kd_threshold_nm, "lab_outcome"] = "PASS"
        warnings.append(
            f"Derived lab_outcome from kd_nm with threshold {kd_threshold_nm} nM"
        )
    elif "binding_signal" in df.columns and df["binding_signal"].notna().any():
        df["lab_outcome"] = "FAIL"
        df.loc[df["binding_signal"] >= binding_threshold, "lab_outcome"] = "PASS"
        warnings.append(
            f"Derived lab_outcome from binding_signal with threshold {binding_threshold}"
        )
    else:
        raise SystemExit(
            f"No outcome column '{outcome_col}', no kd_nm, no binding_signal — "
            "cannot derive lab_outcome. Pass --outcome-col or include kd_nm / binding_signal."
        )

    # Apply censored override last
    df.loc[df["_censored"], "lab_outcome"] = "CENSORED"
    df = df.drop(columns=["_censored"])
    return df


def aggregate_replicates(
    df: pd.DataFrame, policy: str, warnings: list[str]
) -> pd.DataFrame:
    """Aggregate by design_id according to policy.

    median / mean: collapse numeric columns; for lab_outcome take majority (tie -> FAIL).
    keep-all: leave the table as-is.
    """
    if policy == "keep-all":
        return df

    if "design_id" not in df.columns:
        warnings.append("No design_id column; skipping replicate aggregation")
        return df

    numeric_cols = [
        c
        for c, dtype in CANONICAL_COLUMNS.items()
        if dtype == "float" and c in df.columns
    ]
    string_cols = [
        c
        for c, dtype in CANONICAL_COLUMNS.items()
        if dtype == "str" and c in df.columns and c not in {"design_id", "replicate_id"}
    ]

    groups = df.groupby("design_id", dropna=False)

    rows = []
    for design_id, group in groups:
        rec: dict[str, Any] = {"design_id": design_id}
        # Numeric aggregation
        for col in numeric_cols:
            values = group[col].dropna()
            if len(values) == 0:
                rec[col] = None
                continue
            if policy == "median":
                rec[col] = float(values.median())
            elif policy == "mean":
                # Geometric mean for kd_nm (log-normal); arithmetic otherwise
                if col == "kd_nm":
                    rec[col] = float(math.exp(values.apply(math.log).mean()))
                else:
                    rec[col] = float(values.mean())
            else:
                raise SystemExit(f"Unknown aggregation policy: {policy}")
        # String columns: take first non-null
        for col in string_cols:
            non_null = group[col].dropna()
            rec[col] = str(non_null.iloc[0]) if len(non_null) > 0 else None
        # Outcome: majority vote, tie breaks to FAIL
        if "lab_outcome" in group.columns:
            counts = group["lab_outcome"].value_counts()
            if len(counts) == 0:
                rec["lab_outcome"] = "FAIL"
            else:
                top = counts.idxmax()
                top_count = counts.iloc[0]
                # Tie check
                if len(counts) > 1 and counts.iloc[1] == top_count:
                    rec["lab_outcome"] = "FAIL"
                else:
                    rec["lab_outcome"] = top
        rows.append(rec)

    aggregated = pd.DataFrame(rows)
    if len(df) != len(aggregated):
        warnings.append(
            f"Aggregated {len(df)} input rows -> {len(aggregated)} unique design_ids ({policy})"
        )
    return aggregated


def validate(df: pd.DataFrame, assay: str, warnings: list[str]) -> None:
    """Final validation; raises SystemExit on hard errors, appends to warnings on soft."""
    if "design_id" not in df.columns:
        raise SystemExit(
            "Missing required column: design_id (after alias substitution). "
            "Pass --alias design_id=<source-column>."
        )
    if df["design_id"].isna().any():
        warnings.append(
            f"{int(df['design_id'].isna().sum())} rows have null design_id"
        )
    if df["design_id"].duplicated().any():
        dup_count = int(df["design_id"].duplicated().sum())
        warnings.append(
            f"{dup_count} duplicate design_ids remain after aggregation — "
            "consider --aggregate median or --aggregate mean"
        )
    if "lab_outcome" not in df.columns:
        raise SystemExit("Failed to derive lab_outcome column")

    # Assay-specific sanity checks
    if assay.startswith("affinity_") and "kd_nm" not in df.columns and "binding_signal" not in df.columns:
        warnings.append(
            f"Affinity assay '{assay}' but neither kd_nm nor binding_signal present"
        )
    if assay == "expression_qc" and "expression_mg_per_L" not in df.columns:
        warnings.append(
            "expression_qc assay but no expression_mg_per_L column"
        )


def to_records(df: pd.DataFrame, source_file: str) -> list[dict[str, Any]]:
    """Convert DataFrame to a list of plain-dict records, preserving provenance."""
    records: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        rec: dict[str, Any] = {}
        for col in df.columns:
            value = row[col]
            if pd.isna(value):
                rec[col] = None
            elif isinstance(value, (int, float)):
                rec[col] = float(value) if isinstance(value, float) else int(value)
            else:
                rec[col] = str(value)
        rec["source_file"] = source_file
        rec["source_row"] = int(idx)
        records.append(rec)
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize a lab readout file to BY's canonical schema.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Source lab readout file")
    parser.add_argument("--output", required=True, help="Output normalized JSON path")
    parser.add_argument(
        "--assay", required=True, choices=sorted(ASSAY_TYPES), help="Assay type"
    )
    parser.add_argument(
        "--aggregate",
        default="median",
        choices=["median", "mean", "keep-all"],
        help="Replicate aggregation policy",
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        help="Column-rename mapping (canonical=source); repeatable",
    )
    parser.add_argument(
        "--outcome-col",
        default="lab_outcome",
        help="Column holding ground-truth outcome",
    )
    parser.add_argument(
        "--outcome-pass-value",
        default="PASS",
        help="Value indicating PASS in outcome column",
    )
    parser.add_argument(
        "--kd-threshold-nm",
        type=float,
        default=100.0,
        help="PASS if kd_nm <= this (when deriving from kd_nm)",
    )
    parser.add_argument(
        "--binding-threshold",
        type=float,
        default=0.3,
        help="PASS if binding_signal >= this (when deriving from signal)",
    )
    parser.add_argument(
        "--lod-kd-nm",
        type=float,
        default=None,
        help="Limit-of-detection for Kd; values above are CENSORED",
    )
    parser.add_argument(
        "--batch-col",
        default=None,
        help="Source column holding batch_id",
    )
    parser.add_argument(
        "--format",
        default="auto",
        choices=["auto", "adaptyv-json"],
        help="Input format hint",
    )
    parser.add_argument(
        "--keep-extra-col",
        action="append",
        default=[],
        help="Retain a non-canonical column in output; repeatable",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    aliases = parse_aliases(args.alias)
    warnings: list[str] = []

    df = load_source(input_path, args.format)
    df = apply_aliases(df, aliases)

    if args.batch_col and args.batch_col in df.columns:
        df = df.rename(columns={args.batch_col: "batch_id"})

    df = coerce_dtypes(df, warnings)
    df = derive_outcome(
        df,
        outcome_col=args.outcome_col,
        pass_value=args.outcome_pass_value,
        kd_threshold_nm=args.kd_threshold_nm,
        binding_threshold=args.binding_threshold,
        lod_kd_nm=args.lod_kd_nm,
        warnings=warnings,
    )

    # Filter columns to canonical + assay tag + extras
    keep_cols = [c for c in CANONICAL_COLUMNS if c in df.columns]
    keep_cols += [c for c in args.keep_extra_col if c in df.columns]
    df = df[keep_cols].copy()
    df["assay"] = args.assay

    n_input = len(df)
    df = aggregate_replicates(df, args.aggregate, warnings)
    validate(df, args.assay, warnings)

    records = to_records(df, str(input_path))

    payload = {
        "metadata": {
            "assay": args.assay,
            "source_file": str(input_path),
            "aggregation_policy": args.aggregate,
            "row_count_input": n_input,
            "row_count_output": len(records),
            "warnings": warnings,
            "outcome_derivation": {
                "outcome_col": args.outcome_col,
                "pass_value": args.outcome_pass_value,
                "kd_threshold_nm": args.kd_threshold_nm,
                "binding_threshold": args.binding_threshold,
                "lod_kd_nm": args.lod_kd_nm,
            },
        },
        "records": records,
    }

    with output_path.open("w") as fh:
        json.dump(payload, fh, indent=2, default=str)

    print(f"✓ Ingest completed: {len(records)} rows -> {output_path}")
    if warnings:
        print(f"  ({len(warnings)} warnings — see metadata.warnings in output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
