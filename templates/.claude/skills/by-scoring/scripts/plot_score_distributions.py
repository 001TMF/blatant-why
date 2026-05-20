#!/usr/bin/env python3
"""Plot score distributions for a screened design panel.

Reads a scored CSV (from composite_score.py or screening output) and
produces a multi-panel PDF showing:
    - ipSAE_min distribution with verdict-band threshold lines
    - ipTM distribution with hard-filter threshold line
    - Composite score distribution with verdict-band lines
    - (optional) pLDDT mean distribution with hard-filter line

Inputs:
    Input CSV must contain columns: ipsae_min, iptm, composite_score.
    Optional columns plotted if present: plddt_mean, verdict.

Outputs:
    PDF at the specified path, 300 DPI, four panels (or three if pLDDT missing).

Example invocation:
    python plot_score_distributions.py --input ranked.csv --output distributions.pdf
    python plot_score_distributions.py --input ranked.csv --output distributions.pdf \\
        --modality nanobody --bins 40

Dependencies:
    pandas >= 1.5
    matplotlib >= 3.5
    numpy >= 1.20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit(
        "Install with: pip install 'pandas>=1.5' 'matplotlib>=3.5' 'numpy>=1.20'"
    )


# Per-modality ipSAE_min verdict thresholds for the threshold lines.
# Matches references/thresholds-by-modality.md.
MODALITY_IPSAE_LINES: dict[str, dict[str, float]] = {
    "antibody":  {"lab_ready": 0.75, "follow_up": 0.60, "borderline": 0.45},
    "nanobody":  {"lab_ready": 0.70, "follow_up": 0.55, "borderline": 0.40},
    "vhh":       {"lab_ready": 0.70, "follow_up": 0.55, "borderline": 0.40},
    "denovo":    {"lab_ready": 0.85, "follow_up": 0.70, "borderline": 0.55},
    "bispecific":{"lab_ready": 0.70, "follow_up": 0.55, "borderline": 0.40},
    "peptide":   {"lab_ready": 0.75, "follow_up": 0.60, "borderline": 0.45},
    "default":   {"lab_ready": 0.80, "follow_up": 0.50, "borderline": 0.20},
}

COMPOSITE_LINES = {"lab_ready": 0.75, "follow_up": 0.60, "borderline": 0.45}
IPTM_HARD_FILTER = 0.50
PLDDT_HARD_FILTER = 70.0


def _add_threshold_lines(
    ax: plt.Axes,
    lines: dict[str, float],
    label_map: dict[str, str] | None = None,
) -> None:
    """Draw vertical threshold lines with labels on a histogram axis."""
    colors = {"lab_ready": "#2a9d4a", "follow_up": "#f4a236", "borderline": "#d04a4a"}
    labels = label_map or {
        "lab_ready": "LAB-READY",
        "follow_up": "FOLLOW-UP",
        "borderline": "BORDERLINE",
    }
    for key, value in lines.items():
        ax.axvline(
            value,
            color=colors.get(key, "black"),
            linestyle="--",
            linewidth=1.2,
            label=f"{labels.get(key, key)}: {value:.2f}",
        )


def _plot_histogram(
    ax: plt.Axes,
    series: pd.Series,
    title: str,
    xlabel: str,
    bins: int,
    xlim: tuple[float, float],
    threshold_lines: dict[str, float] | None = None,
) -> None:
    """Plot a single histogram panel."""
    values = series.dropna().astype(float).values
    if len(values) == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title)
        return

    ax.hist(values, bins=bins, range=xlim, color="#4a7ab4", edgecolor="white", alpha=0.85)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    ax.set_xlim(xlim)

    if threshold_lines:
        _add_threshold_lines(ax, threshold_lines)
        ax.legend(fontsize=7, loc="upper left", framealpha=0.85)

    # Annotation: median + n
    median = float(np.median(values))
    n = len(values)
    ax.text(
        0.98,
        0.95,
        f"n={n}\nmedian={median:.3f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.85),
    )


def make_plot(
    df: pd.DataFrame,
    output: Path,
    modality: str,
    bins: int,
    title_suffix: str | None = None,
) -> None:
    """Render the multi-panel PDF."""
    has_plddt = "plddt_mean" in df.columns and df["plddt_mean"].notna().any()
    n_panels = 4 if has_plddt else 3
    fig, axes = plt.subplots(
        nrows=1,
        ncols=n_panels,
        figsize=(5 * n_panels, 4.5),
        constrained_layout=True,
    )
    if n_panels == 1:
        axes = [axes]

    suffix = f" — {title_suffix}" if title_suffix else ""
    fig.suptitle(
        f"BY Score Distributions ({modality}, n={len(df)}){suffix}",
        fontsize=13,
        fontweight="bold",
    )

    ipsae_lines = MODALITY_IPSAE_LINES.get(modality.lower(), MODALITY_IPSAE_LINES["default"])

    _plot_histogram(
        axes[0],
        df["ipsae_min"],
        title="ipSAE_min",
        xlabel="ipSAE_min",
        bins=bins,
        xlim=(0.0, 1.0),
        threshold_lines=ipsae_lines,
    )

    _plot_histogram(
        axes[1],
        df["iptm"],
        title="ipTM",
        xlabel="ipTM",
        bins=bins,
        xlim=(0.0, 1.0),
        threshold_lines={"hard_filter": IPTM_HARD_FILTER},
    )
    # Override default label colors for the single hard-filter line
    if axes[1].get_legend():
        axes[1].legend(["hard filter: 0.50"], fontsize=7, loc="upper left", framealpha=0.85)

    _plot_histogram(
        axes[2],
        df["composite_score"],
        title="Composite Score",
        xlabel="composite",
        bins=bins,
        xlim=(0.0, 1.0),
        threshold_lines=COMPOSITE_LINES,
    )

    if has_plddt:
        _plot_histogram(
            axes[3],
            df["plddt_mean"],
            title="pLDDT mean (design chain)",
            xlabel="pLDDT",
            bins=bins,
            xlim=(0.0, 100.0),
            threshold_lines={"hard_filter": PLDDT_HARD_FILTER},
        )
        if axes[3].get_legend():
            axes[3].legend(["hard filter: 70"], fontsize=7, loc="upper left", framealpha=0.85)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format="pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot score distributions for a scored design panel.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", type=Path, required=True, help="Scored CSV (from composite_score.py).")
    parser.add_argument("--output", type=Path, required=True, help="Output PDF path.")
    parser.add_argument(
        "--modality",
        choices=sorted(MODALITY_IPSAE_LINES.keys()),
        default="default",
        help="Modality for per-modality threshold lines.",
    )
    parser.add_argument("--bins", type=int, default=30, help="Number of histogram bins.")
    parser.add_argument("--title-suffix", type=str, default=None, help="Optional extra title text.")

    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Input CSV not found: {args.input}")

    df = pd.read_csv(args.input)
    required = {"ipsae_min", "iptm", "composite_score"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(
            f"Input CSV missing required columns: {sorted(missing)}. "
            "Run composite_score.py first to add composite_score."
        )

    make_plot(
        df=df,
        output=args.output,
        modality=args.modality,
        bins=args.bins,
        title_suffix=args.title_suffix,
    )

    n_total = len(df)
    n_lab_ready = int((df.get("verdict") == "LAB-READY").sum()) if "verdict" in df.columns else 0
    print(
        f"✓ Distribution plot written: {args.output} "
        f"({n_total} designs, {n_lab_ready} LAB-READY)"
    )


if __name__ == "__main__":
    main()
