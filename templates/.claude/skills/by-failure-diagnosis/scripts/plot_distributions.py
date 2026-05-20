#!/usr/bin/env python3
"""Plot PASS vs FAIL distributions for the most discriminating features.

Reads a CSV of design scores (same format as diagnose_from_csv.py),
ranks numeric features by Mann-Whitney U p-value, and generates a single
multi-panel PDF with violin plots of PASS vs FAIL distributions for the
top-N features. Useful for visually validating diagnosis output before
acting on threshold recommendations.

Inputs
------
- CSV with a status column (PASS/FAIL) and one or more numeric features

Outputs
-------
- A PDF file containing one violin-plot panel per top feature, with
  median and quartile markers, rendered at 300 DPI

Example
-------
    python3 plot_distributions.py \\
        --input campaigns/tnf/run01/screening_results.csv \\
        --output campaigns/tnf/run01/diagnostics.pdf \\
        --top-n 5 \\
        --status-col status
"""
from __future__ import annotations

import argparse
import sys

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
    """Build the argparse parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate a multi-panel violin-plot PDF for PASS vs FAIL "
            "design score distributions, ranked by Mann-Whitney p-value."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input CSV.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output PDF file.",
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
        "--top-n",
        type=int,
        default=5,
        help="How many top features to plot.",
    )
    parser.add_argument(
        "--min-group-size",
        type=int,
        default=3,
        help="Minimum group size to consider a feature.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="PDF rendering DPI.",
    )
    return parser.parse_args()


def rank_features(
    df,
    status_col: str,
    pass_value: str,
    min_group_size: int,
) -> list[tuple[str, float, float]]:
    """Rank numeric features by Mann-Whitney p-value.

    Returns a list of (feature, p_value, effect_size) tuples sorted
    ascending by p-value.
    """
    import numpy as np
    from scipy.stats import mannwhitneyu

    passed_mask = df[status_col] == pass_value
    failed_mask = ~passed_mask

    numeric_cols = [
        c
        for c in df.columns
        if c != status_col and df[c].dtype.kind in "biufc"
    ]
    cols_ordered = [c for c in CANONICAL_FEATURES if c in numeric_cols]
    cols_ordered += [c for c in numeric_cols if c not in cols_ordered]

    ranked: list[tuple[str, float, float]] = []
    for feat in cols_ordered:
        p_vals = df.loc[passed_mask, feat].dropna().tolist()
        f_vals = df.loc[failed_mask, feat].dropna().tolist()
        if len(p_vals) < min_group_size or len(f_vals) < min_group_size:
            continue
        try:
            _stat, pval = mannwhitneyu(
                p_vals, f_vals, alternative="two-sided"
            )
        except (ValueError, TypeError):
            continue
        p_mean = float(np.mean(p_vals))
        f_mean = float(np.mean(f_vals))
        std_pool = float(np.std(p_vals + f_vals))
        effect = abs(p_mean - f_mean) / max(std_pool, 1e-6)
        ranked.append((feat, float(pval), float(effect)))
    ranked.sort(key=lambda t: t[1])
    return ranked


def render_pdf(
    df,
    ranked: list[tuple[str, float, float]],
    status_col: str,
    pass_value: str,
    output_path: str,
    dpi: int,
) -> None:
    """Render the top-N features as violin plots into a single PDF."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(ranked)
    if n == 0:
        # Emit an empty page with a message rather than failing silently.
        fig, ax = plt.subplots(figsize=(8.5, 11), dpi=dpi)
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "No features could be plotted.\n"
            "Check group sizes and data types.",
            ha="center",
            va="center",
            fontsize=14,
        )
        fig.savefig(output_path, dpi=dpi)
        plt.close(fig)
        return

    cols = 2 if n > 1 else 1
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(
        rows, cols, figsize=(8.5, 3.0 * rows + 1), dpi=dpi
    )
    if rows == 1 and cols == 1:
        axes = [axes]
    else:
        axes = list(axes.flatten())

    passed_mask = df[status_col] == pass_value

    for ax, (feat, pval, effect) in zip(axes, ranked):
        p_vals = df.loc[passed_mask, feat].dropna().tolist()
        f_vals = df.loc[~passed_mask, feat].dropna().tolist()
        parts = ax.violinplot(
            [p_vals, f_vals],
            positions=[1, 2],
            showmeans=False,
            showmedians=True,
            showextrema=True,
        )
        # Style: pass = green, fail = red.
        for body, color in zip(parts["bodies"], ("#2ca02c", "#d62728")):
            body.set_facecolor(color)
            body.set_alpha(0.6)
            body.set_edgecolor("black")
        ax.set_xticks([1, 2])
        ax.set_xticklabels(
            [f"PASS\n(n={len(p_vals)})", f"FAIL\n(n={len(f_vals)})"]
        )
        ax.set_ylabel(feat)
        ax.set_title(
            f"{feat}  (p={pval:.4f}, effect={effect:.2f})", fontsize=10
        )
        ax.grid(axis="y", alpha=0.3)

    # Hide unused axes.
    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle(
        "PASS vs FAIL distributions — top discriminating features",
        fontsize=13,
        y=1.0,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        sys.exit("Install with: pip install pandas scipy numpy matplotlib")
    try:
        import scipy  # noqa: F401
        import numpy  # noqa: F401
        import matplotlib  # noqa: F401
    except ImportError:
        sys.exit("Install with: pip install scipy numpy matplotlib")

    import pandas as pd

    df = pd.read_csv(args.input)
    if args.status_col not in df.columns:
        sys.exit(
            f"Missing status column '{args.status_col}'. "
            f"Available: {list(df.columns)}"
        )

    ranked = rank_features(
        df,
        status_col=args.status_col,
        pass_value=args.pass_value,
        min_group_size=args.min_group_size,
    )
    top = ranked[: args.top_n]

    render_pdf(
        df=df,
        ranked=top,
        status_col=args.status_col,
        pass_value=args.pass_value,
        output_path=args.output,
        dpi=args.dpi,
    )

    print(
        f"✓ Distributions plotted: {len(top)} features written "
        f"to {args.output} ({args.dpi} DPI)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
