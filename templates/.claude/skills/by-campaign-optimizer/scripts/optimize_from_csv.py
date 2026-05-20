#!/usr/bin/env python3
"""Train a Random Forest on scored designs and propose next-round parameters.

Reads a CSV of scored designs (one row per design) and writes a JSON file
containing:

    - feature importances (sorted descending)
    - recommended parameter changes (min_ipsae, max_rmsd, etc.)
    - exploration regions (feature-space cells with high RF prediction variance)
    - a confidence level based on training-set size

Inputs:
    --scores PATH       CSV with scored designs (required)
    --target NAME       Column to optimize (default: ipsae)
    --output PATH       Where to write optimizer_output.json (required)
    --min-designs N     Floor below which we fall back to rule-based (default: 10)

Example:
    python optimize_from_csv.py \\
        --scores campaign/round_1/scores.csv \\
        --output campaign/round_1/optimizer_output.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit("Install with: pip install numpy pandas")

try:
    import sklearn
    from sklearn.ensemble import RandomForestRegressor
except ImportError:
    sys.exit("Install with: pip install scikit-learn")


RF_FEATURE_NAMES = [
    "ipsae",
    "iptm",
    "plddt",
    "rmsd",
    "liabilities",
    "cdr3_length",
]


def load_scores(path: Path) -> pd.DataFrame:
    """Load scored designs from CSV, coercing numeric columns."""
    if not path.exists():
        sys.exit(f"Scores CSV not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        sys.exit(f"Scores CSV is empty: {path}")
    # Coerce ipsae_min to ipsae if present
    if "ipsae" not in df.columns and "ipsae_min" in df.columns:
        df["ipsae"] = df["ipsae_min"]
    return df


def sha256_of_file(path: Path) -> str:
    """Hash file contents for reproducibility tracking."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def confidence_from_size(n: int) -> str:
    """Map training-set size to a coarse confidence label."""
    if n < 10:
        return "none"
    if n < 20:
        return "low"
    if n < 30:
        return "medium"
    return "high"


def build_feature_matrix(
    df: pd.DataFrame, target: str
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build X, y, and the feature names that were actually populated."""
    available = [f for f in RF_FEATURE_NAMES if f in df.columns]
    if target not in df.columns:
        sys.exit(f"Target column '{target}' not in CSV. Columns: {list(df.columns)}")
    sub = df[available + [target]].dropna()
    feature_names = [f for f in available if f != target]
    if not feature_names:
        sys.exit("No usable feature columns after dropping NaNs.")
    X = sub[feature_names].to_numpy(dtype=float)
    y = sub[target].to_numpy(dtype=float)
    return X, y, feature_names


def derive_recommendations(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    importances: dict[str, float],
) -> dict:
    """Derive concrete threshold recommendations from top-quartile designs."""
    rec: dict = {}
    threshold = float(np.percentile(y, 75))
    good_mask = y >= threshold
    if good_mask.sum() == 0:
        return rec
    good_means = X[good_mask].mean(axis=0)
    for i, feat in enumerate(feature_names):
        if importances.get(feat, 0.0) <= 0.10:
            continue
        mean_val = float(good_means[i])
        if feat in ("ipsae", "iptm", "plddt"):
            rec[f"min_{feat}"] = round(mean_val * 0.9, 3)
        elif feat == "rmsd":
            rec[f"max_{feat}"] = round(mean_val * 1.1, 2)
        elif feat == "cdr3_length":
            rec[f"target_{feat}"] = int(round(mean_val))
    rec["increase_num_designs"] = bool(len(y) < 50)
    rec["suggested_alpha"] = 0.001 if float(np.std(y)) < 0.1 else 0.01
    return rec


def find_exploration_regions(
    rf: RandomForestRegressor,
    X: np.ndarray,
    feature_names: list[str],
    top_k: int = 3,
) -> list[dict]:
    """Identify training rows where individual tree predictions disagree most.

    These are the regions of feature space where the RF is least confident,
    and therefore the most informative places to sample in the next round.
    """
    per_tree = np.array([tree.predict(X) for tree in rf.estimators_])
    pred_std = per_tree.std(axis=0)
    top_idx = np.argsort(pred_std)[-top_k:][::-1]
    regions = []
    for idx in top_idx:
        regions.append(
            {
                "row_index": int(idx),
                "prediction_std": round(float(pred_std[idx]), 4),
                "features": {
                    name: round(float(X[idx, i]), 4)
                    for i, name in enumerate(feature_names)
                },
            }
        )
    return regions


def fallback_result(reason: str, n_designs: int, data_hash: Optional[str]) -> dict:
    """Construct a rule-based fallback output."""
    return {
        "source": "rule_based",
        "confidence": confidence_from_size(n_designs),
        "n_designs": n_designs,
        "feature_importances": [],
        "recommended_parameters": {},
        "exploration_regions": [],
        "explanation": reason,
        "data_sha256": data_hash,
        "sklearn_version": sklearn.__version__,
    }


def optimize(
    scores_csv: Path, target: str, min_designs: int
) -> dict:
    """Run the full optimizer pipeline and return a result dict."""
    df = load_scores(scores_csv)
    data_hash = sha256_of_file(scores_csv)
    n = len(df)

    if n < min_designs:
        return fallback_result(
            reason=(
                f"Only {n} scored designs — need {min_designs}+ for ML. "
                "Using rule-based fallback."
            ),
            n_designs=n,
            data_hash=data_hash,
        )

    X, y, feature_names = build_feature_matrix(df, target)
    if len(X) < min_designs:
        return fallback_result(
            reason=f"Only {len(X)} rows have complete features after dropna.",
            n_designs=len(X),
            data_hash=data_hash,
        )

    rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=5,
        random_state=42,
    )
    rf.fit(X, y)

    importances = {
        name: float(imp) for name, imp in zip(feature_names, rf.feature_importances_)
    }
    sorted_importances = sorted(
        importances.items(), key=lambda kv: kv[1], reverse=True
    )

    recommendations = derive_recommendations(X, y, feature_names, importances)
    exploration_regions = find_exploration_regions(rf, X, feature_names)

    top_feat, top_imp = sorted_importances[0]
    explanation = (
        f"RF trained on {len(X)} designs (target={target}). "
        f"Top feature: {top_feat} (importance={top_imp:.3f}). "
        f"Top-quartile {target} >= {float(np.percentile(y, 75)):.3f}."
    )

    return {
        "source": "active_learning",
        "confidence": confidence_from_size(len(X)),
        "n_designs": len(X),
        "target": target,
        "feature_importances": [
            [name, round(imp, 4)] for name, imp in sorted_importances
        ],
        "recommended_parameters": recommendations,
        "exploration_regions": exploration_regions,
        "explanation": explanation,
        "data_sha256": data_hash,
        "sklearn_version": sklearn.__version__,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Train RF on scored designs and propose next-round parameters."
    )
    parser.add_argument(
        "--scores",
        type=Path,
        required=True,
        help="Path to scored designs CSV (one row per design).",
    )
    parser.add_argument(
        "--target",
        default="ipsae",
        help="Column to optimize (default: ipsae).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write optimizer_output.json.",
    )
    parser.add_argument(
        "--min-designs",
        type=int,
        default=10,
        help="Floor below which we fall back to rule-based (default: 10).",
    )
    args = parser.parse_args()

    result = optimize(args.scores, args.target, args.min_designs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))

    n = result.get("n_designs", 0)
    if result["source"] == "active_learning":
        top = result["feature_importances"][0][0]
        print(
            f"✓ Optimizer completed: {n} designs, source={result['source']}, "
            f"top feature: {top}, output: {args.output}"
        )
    else:
        print(
            f"✓ Optimizer completed: {n} designs, source={result['source']}, "
            f"output: {args.output}"
        )


if __name__ == "__main__":
    main()
