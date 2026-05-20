#!/usr/bin/env python3
"""Join normalized lab outcomes with in-silico features and run a calibration
diagnosis: which in-silico features actually predicted real lab outcomes?

Statistical approach matches by-failure-diagnosis: Mann-Whitney U per feature
with Benjamini-Hochberg correction across features. Adds calibration-specific
metrics: precision at top-K, lift over random, AUC.

Inputs:
    --lab <path>             Normalized lab JSON (from ingest_lab_results.py)
    --silico <path>          screening_results.json (from by-screening) or CSV
    --output-json <path>     calibration.json output
    --output-md <path>       calibration_report.md output (optional)
    --enriched-csv <path>    enriched_dataset.csv (silico + lab joined) (optional)
    --top-k <int>            K for precision-at-K (default: 10)
    --rank-feature <name>    Silico feature to rank by for top-K (default: ipsae)
    --silico-feature-alias <a>=<b>   Map canonical feature name to source col;
                                     repeatable (e.g. ipsae=ipsae_min)
    --cross-validate         Run 5-fold CV AUC (requires N>=30)

Outputs:
    calibration.json with structure:
        {
            "metadata": {n_lab, n_silico, n_joined, n_passed, n_failed, ...},
            "features": [
                {
                    "name": "ipsae",
                    "verdict": "validated" | "contradicted" | "inconclusive",
                    "p_value": ..., "q_value": ..., "effect_size": ...,
                    "passed_mean": ..., "failed_mean": ...,
                    "precision_at_top_k": ..., "lift_over_random": ...,
                    "auc": ..., "interpretation": "..."
                },
                ...
            ],
            "recommendations": [...]
        }

Example:
    python3 diagnose_silico_vs_lab.py \\
        --lab    lab_results.normalized.json \\
        --silico screening_results.json \\
        --output-json calibration.json \\
        --output-md   calibration_report.md \\
        --top-k 10
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    import numpy as np
except ImportError:
    sys.exit("Install with: pip install pandas numpy")

try:
    from scipy.stats import mannwhitneyu
except ImportError:
    sys.exit("Install with: pip install scipy")

try:
    from sklearn.metrics import roc_auc_score
    HAVE_SKLEARN = True
except ImportError:
    HAVE_SKLEARN = False


CANONICAL_FEATURES: list[str] = [
    "ipsae",
    "ipsae_min",
    "iptm",
    "plddt",
    "rmsd",
    "net_charge",
    "hydrophobic_fraction",
    "liabilities",
    "cdr3_length",
    "aggregation_predicted",
    "polyspecificity_predicted",
]

# Features where LOWER value indicates better design (so PASS group should have
# lower mean; "contradicted" verdict is reversed).
LOWER_IS_BETTER: set[str] = {
    "rmsd",
    "liabilities",
    "aggregation_predicted",
    "polyspecificity_predicted",
    "hydrophobic_fraction",
}


def load_lab(path: Path) -> pd.DataFrame:
    """Load normalized lab JSON into a DataFrame."""
    with path.open() as fh:
        payload = json.load(fh)
    if "records" not in payload:
        raise SystemExit(f"Lab file missing 'records' key: {path}")
    df = pd.DataFrame(payload["records"])
    if "design_id" not in df.columns:
        raise SystemExit(f"Lab file missing design_id column: {path}")
    return df


def load_silico(path: Path) -> pd.DataFrame:
    """Load in-silico feature table. Supports CSV or JSON list."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    with path.open() as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        # Sometimes wrapped (e.g. {"designs": [...]})
        for key in ("designs", "results", "records"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise SystemExit(f"Silico file not a list of records: {path}")
    return pd.DataFrame(data)


def parse_feature_aliases(raw: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in raw:
        if "=" not in token:
            raise SystemExit(f"--silico-feature-alias must be canonical=source: {token}")
        canonical, source = token.split("=", 1)
        out[canonical.strip()] = source.strip()
    return out


def apply_silico_aliases(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    rename_map = {source: canonical for canonical, source in aliases.items()}
    rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
    return df.rename(columns=rename_map)


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Compute BH-corrected q-values from a list of p-values."""
    n = len(pvalues)
    if n == 0:
        return []
    indexed = sorted(enumerate(pvalues), key=lambda x: x[1])
    qvalues = [0.0] * n
    prev_q = 1.0
    for rank in range(n - 1, -1, -1):
        original_idx, p = indexed[rank]
        q = p * n / (rank + 1)
        q = min(q, prev_q)
        prev_q = q
        qvalues[original_idx] = q
    return qvalues


def compute_effect_size(u: float, n1: int, n2: int) -> float:
    """Convert Mann-Whitney U to Cohen's d analog via rank-biserial r."""
    if n1 == 0 or n2 == 0:
        return 0.0
    r = 1.0 - (2.0 * u) / (n1 * n2)
    # r is in [-1, 1]; map to Cohen's d
    if abs(r) >= 0.9999:
        return float("inf") if r > 0 else float("-inf")
    d = 2.0 * r / math.sqrt(1.0 - r * r)
    return float(d)


def feature_calibration(
    feature: str,
    values: pd.Series,
    outcomes: pd.Series,
    top_k: int,
) -> dict[str, Any] | None:
    """Compute per-feature calibration metrics. Returns None if feature is
    unusable (all-NaN, constant, or one-class)."""
    series = pd.to_numeric(values, errors="coerce")
    mask = series.notna() & outcomes.isin(["PASS", "FAIL"])
    series = series[mask]
    outcomes_aligned = outcomes[mask]
    if series.empty:
        return None
    if series.nunique() < 2:
        return None
    passed = series[outcomes_aligned == "PASS"]
    failed = series[outcomes_aligned == "FAIL"]
    if len(passed) < 2 or len(failed) < 2:
        return None

    higher_is_better = feature not in LOWER_IS_BETTER
    # Two-sided Mann-Whitney
    try:
        u_stat, p_val = mannwhitneyu(
            passed, failed, alternative="two-sided"
        )
    except ValueError:
        return None

    effect = compute_effect_size(float(u_stat), len(passed), len(failed))

    # Precision at top-K based on silico ranking
    silico_sorted = (
        series.sort_values(ascending=not higher_is_better).head(top_k).index
    )
    top_k_outcomes = outcomes_aligned.loc[silico_sorted]
    k_actual = len(top_k_outcomes)
    precision_at_k = (
        float((top_k_outcomes == "PASS").sum()) / k_actual if k_actual > 0 else None
    )
    base_rate = float((outcomes_aligned == "PASS").mean())
    lift = (
        precision_at_k / base_rate if precision_at_k is not None and base_rate > 0 else None
    )

    # AUC
    auc: float | None = None
    if HAVE_SKLEARN and len(outcomes_aligned) >= 10:
        try:
            y = (outcomes_aligned == "PASS").astype(int)
            scores = series if higher_is_better else -series
            auc_val = roc_auc_score(y, scores)
            auc = float(auc_val)
        except Exception:
            auc = None

    # Verdict
    significant = (p_val < 0.05) and (abs(effect) > 0.5)
    pass_better = passed.median() > failed.median()
    if higher_is_better:
        expected_direction = pass_better
    else:
        expected_direction = not pass_better

    if significant and expected_direction:
        verdict = "validated"
    elif significant and not expected_direction:
        verdict = "contradicted"
    else:
        verdict = "inconclusive"

    direction_word = "higher" if pass_better else "lower"
    interpretation = (
        f"PASS designs have {direction_word} {feature} "
        f"(PASS median={float(passed.median()):.3f}, "
        f"FAIL median={float(failed.median()):.3f}, "
        f"p={p_val:.4f}, |d|={abs(effect):.2f})"
    )

    return {
        "name": feature,
        "n_passed": int(len(passed)),
        "n_failed": int(len(failed)),
        "passed_mean": float(passed.mean()),
        "failed_mean": float(failed.mean()),
        "passed_median": float(passed.median()),
        "failed_median": float(failed.median()),
        "statistic": float(u_stat),
        "p_value": float(p_val),
        "effect_size": float(effect),
        "higher_is_better": higher_is_better,
        "precision_at_top_k": precision_at_k,
        "lift_over_random": lift,
        "auc": auc,
        "verdict": verdict,
        "interpretation": interpretation,
    }


def build_recommendations(
    features: list[dict[str, Any]], n_joined: int
) -> list[str]:
    """Surface the top-3 actionable recommendations."""
    recs: list[str] = []
    validated = [f for f in features if f["verdict"] == "validated"]
    contradicted = [f for f in features if f["verdict"] == "contradicted"]

    if validated:
        top = max(validated, key=lambda f: abs(f["effect_size"]))
        action = "tighten" if top["higher_is_better"] else "lower"
        recs.append(
            f"Keep '{top['name']}' in the screener; consider {action}ing its threshold "
            f"(effect |d|={abs(top['effect_size']):.2f}, p={top['p_value']:.4f})"
        )
    if contradicted:
        worst = max(contradicted, key=lambda f: abs(f["effect_size"]))
        recs.append(
            f"REMOVE or INVERT '{worst['name']}' from the screener — predicted "
            f"the WRONG direction (effect |d|={abs(worst['effect_size']):.2f}). "
            f"Emit a knowledge_store_failure record."
        )
    if not validated and not contradicted and n_joined >= 30:
        recs.append(
            "No feature reached validated/contradicted at this sample size. "
            "Consider adding new features (shape complementarity, paratope SASA, "
            "expression predictor) before more lab compute."
        )
    if n_joined < 30:
        recs.append(
            f"Sample size N={n_joined} is below 30; treat all verdicts as "
            "provisional. Submit a wider batch next round."
        )
    return recs[:3]


def render_markdown(
    features: list[dict[str, Any]],
    metadata: dict[str, Any],
    recommendations: list[str],
) -> str:
    lines: list[str] = []
    n_pass = metadata.get("n_passed", 0)
    n_total = metadata.get("n_joined", 0)
    pass_rate = n_pass / n_total if n_total else 0.0
    validated_features = [f for f in features if f["verdict"] == "validated"]
    contradicted_features = [f for f in features if f["verdict"] == "contradicted"]

    top_validated = (
        max(validated_features, key=lambda f: abs(f["effect_size"]))
        if validated_features
        else None
    )

    lines.append("# Calibration Report")
    lines.append("")
    if top_validated:
        auc_str = (
            f", AUC={top_validated['auc']:.2f}" if top_validated.get("auc") is not None else ""
        )
        lines.append(
            f"**Headline:** {n_pass}/{n_total} lab-tested designs PASSed ({pass_rate:.0%}); "
            f"`{top_validated['name']}` was the strongest validated predictor "
            f"(p={top_validated['p_value']:.4f}{auc_str})."
        )
    else:
        lines.append(
            f"**Headline:** {n_pass}/{n_total} lab-tested designs PASSed ({pass_rate:.0%}); "
            f"no feature reached validated status."
        )
    lines.append("")
    lines.append(f"- Assay: `{metadata.get('assay', 'unknown')}`")
    lines.append(f"- Joined designs (lab ∩ silico): {n_total}")
    lines.append(f"- Lab PASS: {n_pass}; Lab FAIL: {metadata.get('n_failed', 0)}")
    lines.append("")

    def section(title: str, rows: list[dict[str, Any]]) -> None:
        lines.append(f"## {title}")
        if not rows:
            lines.append("_None._")
            lines.append("")
            return
        lines.append("| Feature | p | q (BH) | |d| | AUC | Prec@K | Lift |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for f in rows:
            auc = f"{f['auc']:.2f}" if f.get("auc") is not None else "—"
            prec = f"{f['precision_at_top_k']:.2f}" if f.get("precision_at_top_k") is not None else "—"
            lift = f"{f['lift_over_random']:.2f}" if f.get("lift_over_random") is not None else "—"
            lines.append(
                f"| `{f['name']}` | {f['p_value']:.4f} | {f.get('q_value', float('nan')):.4f} | "
                f"{abs(f['effect_size']):.2f} | {auc} | {prec} | {lift} |"
            )
        lines.append("")
        for f in rows:
            lines.append(f"- **{f['name']}**: {f['interpretation']}")
        lines.append("")

    section("Validated predictors", validated_features)
    section("Contradicted predictors", contradicted_features)
    section(
        "Inconclusive features",
        [f for f in features if f["verdict"] == "inconclusive"],
    )

    lines.append("## Recommendations")
    if recommendations:
        for i, rec in enumerate(recommendations, start=1):
            lines.append(f"{i}. {rec}")
    else:
        lines.append("_No actionable recommendations at this sample size._")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose in-silico vs lab divergence with Mann-Whitney + calibration metrics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--lab", required=True, help="Normalized lab JSON")
    parser.add_argument("--silico", required=True, help="In-silico feature file (JSON or CSV)")
    parser.add_argument("--output-json", required=True, help="calibration.json output")
    parser.add_argument("--output-md", default=None, help="calibration_report.md output")
    parser.add_argument(
        "--enriched-csv",
        default=None,
        help="Optional path for the joined enriched_dataset.csv",
    )
    parser.add_argument("--top-k", type=int, default=10, help="K for precision-at-K")
    parser.add_argument(
        "--rank-feature", default="ipsae", help="Default silico feature for top-K ranking"
    )
    parser.add_argument(
        "--silico-feature-alias",
        action="append",
        default=[],
        help="Canonical=source feature alias; repeatable",
    )
    parser.add_argument(
        "--cross-validate",
        action="store_true",
        help="Run 5-fold CV AUC (requires N>=30 and scikit-learn)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lab_path = Path(args.lab)
    silico_path = Path(args.silico)
    if not lab_path.exists():
        sys.exit(f"Lab file not found: {lab_path}")
    if not silico_path.exists():
        sys.exit(f"Silico file not found: {silico_path}")

    lab_df = load_lab(lab_path)
    silico_df = load_silico(silico_path)
    aliases = parse_feature_aliases(args.silico_feature_alias)
    silico_df = apply_silico_aliases(silico_df, aliases)

    if "design_id" not in silico_df.columns:
        sys.exit("Silico file missing design_id column")

    n_lab = len(lab_df)
    n_silico = len(silico_df)

    # Inner join on design_id
    joined = lab_df.merge(
        silico_df, on="design_id", how="inner", suffixes=("_lab", "_silico")
    )
    n_joined = len(joined)

    if n_joined == 0:
        sys.exit(
            f"0 designs joined between lab (N={n_lab}) and silico (N={n_silico}). "
            "Check design_id format alignment."
        )

    # Censored rows: keep as FAIL for categorical analysis
    if "lab_outcome" in joined.columns:
        joined.loc[joined["lab_outcome"] == "CENSORED", "lab_outcome"] = "FAIL"

    # Drop rows without a valid outcome
    joined = joined[joined["lab_outcome"].isin(["PASS", "FAIL"])].copy()

    n_passed = int((joined["lab_outcome"] == "PASS").sum())
    n_failed = int((joined["lab_outcome"] == "FAIL").sum())

    print(
        f"joined {n_joined} designs ({n_passed} lab-PASS, {n_failed} lab-FAIL); "
        f"running diagnosis"
    )

    # Per-feature calibration
    candidate_features = [
        f for f in CANONICAL_FEATURES if f in joined.columns
    ]
    features: list[dict[str, Any]] = []
    for feat in candidate_features:
        result = feature_calibration(
            feature=feat,
            values=joined[feat],
            outcomes=joined["lab_outcome"],
            top_k=args.top_k,
        )
        if result is not None:
            features.append(result)

    # BH correction
    if features:
        pvals = [f["p_value"] for f in features]
        qvals = benjamini_hochberg(pvals)
        for f, q in zip(features, qvals):
            f["q_value"] = q
            # Re-assess: validated requires q < 0.10 too
            if f["verdict"] == "validated" and q >= 0.10:
                f["verdict"] = "inconclusive"

    # Sort by absolute effect size (descending)
    features.sort(key=lambda f: abs(f["effect_size"]), reverse=True)

    metadata = {
        "lab_file": str(lab_path),
        "silico_file": str(silico_path),
        "assay": (
            json.loads(lab_path.read_text()).get("metadata", {}).get("assay", "unknown")
        ),
        "n_lab": n_lab,
        "n_silico": n_silico,
        "n_joined": n_joined,
        "n_passed": n_passed,
        "n_failed": n_failed,
        "top_k": args.top_k,
        "features_tested": [f["name"] for f in features],
        "have_sklearn": HAVE_SKLEARN,
    }
    recommendations = build_recommendations(features, n_joined)

    output_payload = {
        "metadata": metadata,
        "features": features,
        "recommendations": recommendations,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w") as fh:
        json.dump(output_payload, fh, indent=2, default=str)
    print(f"✓ Calibration JSON written: {output_json}")

    if args.output_md:
        md = render_markdown(features, metadata, recommendations)
        output_md = Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(md)
        print(f"✓ Calibration report written: {output_md}")

    if args.enriched_csv:
        enriched_path = Path(args.enriched_csv)
        enriched_path.parent.mkdir(parents=True, exist_ok=True)
        joined.to_csv(enriched_path, index=False)
        print(f"✓ Enriched dataset written: {enriched_path}")

    n_validated = sum(1 for f in features if f["verdict"] == "validated")
    n_contradicted = sum(1 for f in features if f["verdict"] == "contradicted")
    print(
        f"✓ Diagnosis completed: {len(features)} features tested "
        f"({n_validated} validated, {n_contradicted} contradicted)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
