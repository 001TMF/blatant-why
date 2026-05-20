#!/usr/bin/env python3
"""Compute BY composite score for a CSV of scored designs.

Composite formula:
    composite = w_ipsae * ipSAE_min
              + w_iptm  * ipTM
              + w_liab  * (1 - min(high_liability_count / liability_cap, 1.0))

Defaults: w_ipsae=0.50, w_iptm=0.30, w_liab=0.20, liability_cap=5.

Inputs:
    Input CSV must contain columns:
      - design_id
      - ipsae_min        (float in [0.0, 1.0])
      - iptm             (float in [0.0, 1.0])
      - liability_count  (int; high-severity count by default)
    Optional columns (passed through to output):
      - plddt_mean, ca_rmsd, scaffold, etc.
    Optional columns used for hard filtering:
      - plddt_mean       (filter: > 70 by default)
      - ca_rmsd          (filter: < 3.5 A by default)

Outputs:
    Enriched CSV with new columns:
      - composite_score  (float; '--' if any hard filter failed)
      - rank             (int; '--' if filter failed)
      - verdict          (LAB-READY / FOLLOW-UP / BORDERLINE / NOT-VIABLE / FILTER-FAIL)

Example invocation:
    python composite_score.py --input scored.csv --output ranked.csv
    python composite_score.py --input scored.csv --output ranked.csv \\
        --weight-ipsae 0.60 --weight-iptm 0.40 --weight-liability 0.00
    python composite_score.py --input scored.csv --output ranked.csv \\
        --modality nanobody

Dependencies:
    pandas >= 1.5
    numpy >= 1.20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit("Install with: pip install 'pandas>=1.5' 'numpy>=1.20'")


# Per-modality hard-filter overrides. See references/thresholds-by-modality.md.
MODALITY_FILTERS: dict[str, dict[str, float]] = {
    "antibody":  {"iptm_min": 0.50, "plddt_min": 70.0, "ca_rmsd_max": 3.5},
    "nanobody":  {"iptm_min": 0.50, "plddt_min": 70.0, "ca_rmsd_max": 3.0},
    "vhh":       {"iptm_min": 0.50, "plddt_min": 70.0, "ca_rmsd_max": 3.0},
    "denovo":    {"iptm_min": 0.50, "plddt_min": 75.0, "ca_rmsd_max": 2.5},
    "bispecific":{"iptm_min": 0.50, "plddt_min": 70.0, "ca_rmsd_max": 4.0},
    "peptide":   {"iptm_min": 0.50, "plddt_min": 65.0, "ca_rmsd_max": 2.5},
    "default":   {"iptm_min": 0.50, "plddt_min": 70.0, "ca_rmsd_max": 3.5},
}


def normalize_liabilities(count: float, cap: float) -> float:
    """Normalize liability count to [0, 1]."""
    if count < 0:
        return 0.0
    return float(min(count / cap, 1.0))


def composite(
    ipsae_min: float,
    iptm: float,
    liability_count: float,
    w_ipsae: float,
    w_iptm: float,
    w_liab: float,
    liability_cap: float,
) -> float:
    """Compute composite score for a single design."""
    norm_liab = normalize_liabilities(liability_count, liability_cap)
    return (
        w_ipsae * float(ipsae_min)
        + w_iptm * float(iptm)
        + w_liab * (1.0 - norm_liab)
    )


def verdict_from_composite(score: float) -> str:
    """Map composite score to verdict band."""
    if score >= 0.75:
        return "LAB-READY"
    if score >= 0.60:
        return "FOLLOW-UP"
    if score >= 0.45:
        return "BORDERLINE"
    return "NOT-VIABLE"


def apply_hard_filters(
    row: pd.Series,
    filters: dict[str, float],
) -> tuple[bool, list[str]]:
    """Return (passed, list of failure reasons)."""
    reasons: list[str] = []

    iptm = row.get("iptm", np.nan)
    if pd.isna(iptm) or float(iptm) <= filters["iptm_min"]:
        reasons.append(f"ipTM<={filters['iptm_min']}")

    if "plddt_mean" in row.index:
        plddt = row.get("plddt_mean", np.nan)
        if not pd.isna(plddt) and float(plddt) <= filters["plddt_min"]:
            reasons.append(f"pLDDT<={filters['plddt_min']}")

    if "ca_rmsd" in row.index:
        rmsd = row.get("ca_rmsd", np.nan)
        if not pd.isna(rmsd) and float(rmsd) >= filters["ca_rmsd_max"]:
            reasons.append(f"CA-RMSD>={filters['ca_rmsd_max']}A")

    return (len(reasons) == 0, reasons)


def score_dataframe(
    df: pd.DataFrame,
    w_ipsae: float,
    w_iptm: float,
    w_liab: float,
    liability_cap: float,
    modality: str,
) -> pd.DataFrame:
    """Add composite_score, rank, verdict columns to df."""
    filters = MODALITY_FILTERS.get(modality.lower(), MODALITY_FILTERS["default"])

    composites: list[Any] = []
    verdicts: list[str] = []
    filter_reasons: list[str] = []

    for _, row in df.iterrows():
        passed, reasons = apply_hard_filters(row, filters)
        if not passed:
            composites.append(np.nan)
            verdicts.append("FILTER-FAIL")
            filter_reasons.append(",".join(reasons))
            continue

        score = composite(
            ipsae_min=row["ipsae_min"],
            iptm=row["iptm"],
            liability_count=row.get("liability_count", 0),
            w_ipsae=w_ipsae,
            w_iptm=w_iptm,
            w_liab=w_liab,
            liability_cap=liability_cap,
        )
        composites.append(round(score, 4))
        verdicts.append(verdict_from_composite(score))
        filter_reasons.append("")

    df = df.copy()
    df["composite_score"] = composites
    df["verdict"] = verdicts
    df["filter_failures"] = filter_reasons

    # Rank only passing designs.
    passing = df["composite_score"].notna()
    df["rank"] = pd.Series(dtype="Int64")
    df.loc[passing, "rank"] = (
        df.loc[passing, "composite_score"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    return df.sort_values(
        by=["rank", "composite_score"],
        ascending=[True, False],
        na_position="last",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute BY composite score for scored designs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", type=Path, required=True, help="Input CSV with scored designs.")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV with composite column.")
    parser.add_argument("--weight-ipsae", type=float, default=0.50, help="Weight on ipSAE_min.")
    parser.add_argument("--weight-iptm", type=float, default=0.30, help="Weight on ipTM.")
    parser.add_argument("--weight-liability", type=float, default=0.20, help="Weight on developability.")
    parser.add_argument(
        "--liability-cap",
        type=float,
        default=5.0,
        help="Max liability count for normalization (count >= cap -> developability term = 0).",
    )
    parser.add_argument(
        "--modality",
        choices=sorted(MODALITY_FILTERS.keys()),
        default="default",
        help="Modality for per-modality hard-filter thresholds.",
    )

    args = parser.parse_args()

    weight_sum = args.weight_ipsae + args.weight_iptm + args.weight_liability
    if abs(weight_sum - 1.0) > 1e-6:
        sys.exit(
            f"Weights must sum to 1.0; got "
            f"{args.weight_ipsae} + {args.weight_iptm} + {args.weight_liability} = {weight_sum}"
        )

    if not args.input.exists():
        sys.exit(f"Input CSV not found: {args.input}")

    df = pd.read_csv(args.input)
    required = {"design_id", "ipsae_min", "iptm"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"Input CSV missing required columns: {sorted(missing)}")

    if "liability_count" not in df.columns:
        print("⚠ 'liability_count' column missing; treating all designs as 0 high-severity liabilities", file=sys.stderr)
        df["liability_count"] = 0

    scored = score_dataframe(
        df,
        w_ipsae=args.weight_ipsae,
        w_iptm=args.weight_iptm,
        w_liab=args.weight_liability,
        liability_cap=args.liability_cap,
        modality=args.modality,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False)

    n_total = len(scored)
    n_lab_ready = int((scored["verdict"] == "LAB-READY").sum())
    n_follow_up = int((scored["verdict"] == "FOLLOW-UP").sum())
    n_borderline = int((scored["verdict"] == "BORDERLINE").sum())
    n_not_viable = int((scored["verdict"] == "NOT-VIABLE").sum())
    n_filter_fail = int((scored["verdict"] == "FILTER-FAIL").sum())

    print(
        f"✓ Composite scoring completed: {n_total} rows -> {args.output}"
    )
    print(
        f"  LAB-READY={n_lab_ready}  FOLLOW-UP={n_follow_up}  "
        f"BORDERLINE={n_borderline}  NOT-VIABLE={n_not_viable}  "
        f"FILTER-FAIL={n_filter_fail}"
    )


if __name__ == "__main__":
    main()
