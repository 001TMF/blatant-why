#!/usr/bin/env python3
"""Diagnose design-campaign failures from a CSV file.

Reads a CSV with one row per design, runs Mann-Whitney U tests comparing
PASS vs FAIL designs across every numeric feature column, applies the
Benjamini-Hochberg multiple-testing correction, and prints a formatted
table sorted by adjusted q-value alongside the top-3 actionable
recommendations.

Inputs
------
A CSV with at least:
- A status column (default name: status) with values "PASS" or "FAIL"
- One or more numeric feature columns (ipsae, iptm, plddt, rmsd,
  net_charge, hydrophobic_fraction, liabilities, cdr3_length, or any
  custom numeric columns)

Outputs
-------
- stdout: markdown-style table sorted by q-value
- stdout: top-3 recommendations

Example
-------
    python3 diagnose_from_csv.py \\
        --input campaigns/tnf/run01/screening_results.csv \\
        --status-col status \\
        --pass-value PASS \\
        --min-group-size 3
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterable

# Canonical feature columns expected in a BY screening output.
# Extra numeric columns in the CSV are also tested.
CANONICAL_FEATURES: tuple[str, ...] = (
    "ipsae",
    "ipsae_min",
    "iptm",
    "plddt",
    "rmsd",
    "net_charge",
    "hydrophobic_fraction",
    "liabilities",
    "cdr3_length",
)


def parse_args() -> argparse.Namespace:
    """Build the argparse parser and return parsed args."""
    parser = argparse.ArgumentParser(
        description=(
            "Mann-Whitney U diagnosis with BH correction on a design "
            "CSV. Identifies which features most strongly discriminate "
            "PASS from FAIL designs."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input CSV with one row per design.",
    )
    parser.add_argument(
        "--status-col",
        default="status",
        help="Name of the column holding PASS/FAIL labels.",
    )
    parser.add_argument(
        "--pass-value",
        default="PASS",
        help="Value in --status-col that means PASS.",
    )
    parser.add_argument(
        "--min-group-size",
        type=int,
        default=3,
        help="Minimum number of values per group to run the test.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance threshold after BH correction.",
    )
    parser.add_argument(
        "--top-n-recommendations",
        type=int,
        default=3,
        help="How many recommendations to emit.",
    )
    return parser.parse_args()


def bh_correct(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR correction.

    Returns adjusted q-values in the same order as the input p-values.
    Implements the monotonic (step-up) adjustment so that q_i is
    non-decreasing along ascending p_i.
    """
    n = len(pvals)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvals[i])
    ranked = [pvals[i] for i in order]
    raw_q = [p * n / (rank + 1) for rank, p in enumerate(ranked)]
    # Monotonic adjustment from the largest rank downward.
    for i in range(n - 2, -1, -1):
        raw_q[i] = min(raw_q[i], raw_q[i + 1])
    # Cap at 1.0 and restore original order.
    out = [0.0] * n
    for sorted_idx, original_idx in enumerate(order):
        out[original_idx] = min(raw_q[sorted_idx], 1.0)
    return out


def diagnose(
    df,
    status_col: str,
    pass_value: str,
    min_group_size: int,
) -> list[dict]:
    """Run Mann-Whitney U on every numeric column.

    Returns a list of result dicts, sorted ascending by p-value.
    """
    import numpy as np
    from scipy.stats import mannwhitneyu

    passed_mask = df[status_col] == pass_value
    failed_mask = ~passed_mask

    n_pass = int(passed_mask.sum())
    n_fail = int(failed_mask.sum())

    if n_pass < min_group_size or n_fail < min_group_size:
        print(
            f"⚠ Group too small: PASS={n_pass}, FAIL={n_fail} "
            f"(need ≥ {min_group_size} in each).",
            file=sys.stderr,
        )
        return []

    results: list[dict] = []
    numeric_cols = [
        c
        for c in df.columns
        if c != status_col and df[c].dtype.kind in "biufc"
    ]
    # Put canonical features first for stable ordering.
    cols_ordered = [c for c in CANONICAL_FEATURES if c in numeric_cols]
    cols_ordered += [c for c in numeric_cols if c not in cols_ordered]

    for feat in cols_ordered:
        p_vals = df.loc[passed_mask, feat].dropna().tolist()
        f_vals = df.loc[failed_mask, feat].dropna().tolist()
        if len(p_vals) < min_group_size or len(f_vals) < min_group_size:
            continue
        try:
            stat, pval = mannwhitneyu(
                p_vals, f_vals, alternative="two-sided"
            )
        except (ValueError, TypeError) as exc:
            # Constant data, identical samples, etc.
            print(
                f"  Skipping {feat}: {exc}", file=sys.stderr
            )
            continue
        p_mean = float(np.mean(p_vals))
        f_mean = float(np.mean(f_vals))
        std_pool = float(np.std(p_vals + f_vals))
        effect = abs(p_mean - f_mean) / max(std_pool, 1e-6)
        direction = "higher" if p_mean > f_mean else "lower"
        results.append(
            {
                "feature": feat,
                "statistic": float(stat),
                "p_value": float(pval),
                "effect_size": round(effect, 3),
                "passed_mean": round(p_mean, 4),
                "failed_mean": round(f_mean, 4),
                "direction": direction,
                "n_pass": len(p_vals),
                "n_fail": len(f_vals),
            }
        )

    # Sort by raw p-value, then apply BH.
    results.sort(key=lambda r: r["p_value"])
    pvals = [r["p_value"] for r in results]
    qvals = bh_correct(pvals)
    for r, q in zip(results, qvals):
        r["q_value"] = round(q, 4)
    return results


def format_table(results: list[dict], alpha: float) -> str:
    """Format results as a markdown-style table sorted by q-value."""
    if not results:
        return "(no features could be tested)"
    header = (
        "| Feature              | PASS mean  | FAIL mean  | "
        "Effect | p-value  | q-value  | Sig |"
    )
    sep = (
        "|----------------------|------------|------------|"
        "--------|----------|----------|-----|"
    )
    lines = [header, sep]
    for r in results:
        sig = "✓" if r["q_value"] < alpha else " "
        lines.append(
            f"| {r['feature']:<20} | {r['passed_mean']:>10.4f} | "
            f"{r['failed_mean']:>10.4f} | {r['effect_size']:>6.2f} | "
            f"{r['p_value']:>8.4f} | {r['q_value']:>8.4f} | {sig:^3} |"
        )
    return "\n".join(lines)


def recommend(
    results: list[dict], alpha: float, top_n: int
) -> list[str]:
    """Build human-readable recommendations from top-N significant features."""
    sig = [r for r in results if r["q_value"] < alpha]
    recs: list[str] = []
    for r in sig[:top_n]:
        feat = r["feature"]
        if feat in ("ipsae", "ipsae_min", "iptm") and r["direction"] == "higher":
            recs.append(
                f"Raise the {feat} threshold toward "
                f"{r['passed_mean']:.3f} (PASS mean)."
            )
        elif feat == "rmsd" and r["direction"] == "lower":
            recs.append(
                f"Tighten RMSD filter toward "
                f"{r['passed_mean']:.2f} Å (PASS mean)."
            )
        elif feat == "cdr3_length":
            recs.append(
                f"Constrain CDR3 length near "
                f"{r['passed_mean']:.0f} residues (PASS mean); "
                f"FAIL group mean is {r['failed_mean']:.0f}."
            )
        elif feat == "liabilities":
            recs.append(
                f"Move liability scan earlier in the screening "
                f"cascade — PASS mean {r['passed_mean']:.2f} vs FAIL "
                f"{r['failed_mean']:.2f}."
            )
        elif feat == "hydrophobic_fraction":
            recs.append(
                f"Add a hydrophobic_fraction ceiling near "
                f"{r['passed_mean']:.2f}; FAIL designs trend hydrophobic."
            )
        elif feat == "net_charge":
            recs.append(
                f"Enforce a net_charge window around "
                f"{r['passed_mean']:.2f} (PASS mean); FAIL skews to "
                f"{r['failed_mean']:.2f}."
            )
        else:
            recs.append(
                f"Investigate {feat}: PASS {r['passed_mean']:.3f} vs "
                f"FAIL {r['failed_mean']:.3f} "
                f"(effect={r['effect_size']:.2f}, q={r['q_value']:.4f})."
            )
    return recs


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        sys.exit("Install with: pip install pandas scipy numpy")
    try:
        import scipy  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        sys.exit("Install with: pip install scipy numpy")

    import pandas as pd

    df = pd.read_csv(args.input)
    if args.status_col not in df.columns:
        sys.exit(
            f"Missing status column '{args.status_col}'. "
            f"Available: {list(df.columns)}"
        )

    n_total = len(df)
    n_pass = int((df[args.status_col] == args.pass_value).sum())
    n_fail = n_total - n_pass
    pass_rate = n_pass / max(n_total, 1)
    print(
        f"Failure Diagnosis: {n_pass}/{n_total} PASS "
        f"({pass_rate:.1%}) — {n_fail} FAIL"
    )
    print(f"Input: {args.input}")
    print()

    results = diagnose(
        df,
        status_col=args.status_col,
        pass_value=args.pass_value,
        min_group_size=args.min_group_size,
    )

    print(format_table(results, alpha=args.alpha))
    print()

    recs = recommend(results, alpha=args.alpha, top_n=args.top_n_recommendations)
    if recs:
        print("Top recommendations:")
        for i, r in enumerate(recs, 1):
            print(f"  {i}. {r}")
    else:
        print(
            "No features reached q < {:.2f}. Consider: more designs, "
            "different features, or a strategy change.".format(args.alpha)
        )

    n_sig = sum(1 for r in results if r.get("q_value", 1.0) < args.alpha)
    print()
    print(
        f"✓ Diagnosis completed: {len(results)} features tested, "
        f"{n_sig} significant at q < {args.alpha}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
