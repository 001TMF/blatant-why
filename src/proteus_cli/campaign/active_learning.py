"""Active learning campaign optimizer using lightweight random forest.

Replaces rule-based iteration with data-driven parameter suggestions
after sufficient data is available (minimum 10 scored designs).

Reference: EVOLVEpro (Science, 2024) -- few-shot active learning with PLMs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class OptimizationResult:
    """Result from the active learning optimizer or rule-based fallback."""

    source: str  # "active_learning" or "rule_based"
    recommended_parameters: dict
    feature_importances: list[tuple[str, float]] = field(default_factory=list)
    confidence: str = "medium"
    explanation: str = ""
    files_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


# -- Feature extraction -------------------------------------------------------

_FEATURE_NAMES = [
    "ipsae",
    "iptm",
    "plddt",
    "rmsd",
    "liabilities",
    "cdr3_length",
    "net_charge",
    "hydrophobic_fraction",
]


def _extract_features(design: dict) -> dict:
    """Extract ML features from a design score dict."""
    return {
        "ipsae": design.get("ipsae_min", design.get("ipsae", 0)),
        "iptm": design.get("iptm", 0),
        "plddt": design.get("plddt", 0),
        "rmsd": design.get("rmsd", 0),
        "liabilities": design.get("liabilities", 0),
        "cdr3_length": design.get("cdr3_length", 0),
        "net_charge": design.get("net_charge", 0),
        "hydrophobic_fraction": design.get("hydrophobic_fraction", 0),
    }


# -- Data sufficiency check ----------------------------------------------------


def has_enough_data(campaign_dir: str, min_designs: int = 10) -> bool:
    """Check if there's enough scored data for ML-based optimization."""
    scores_dir = Path(campaign_dir)
    score_files = list(scores_dir.rglob("*_scores.json"))
    total = 0
    for f in score_files:
        try:
            data = json.loads(f.read_text())
            total += len(data) if isinstance(data, list) else 1
        except (json.JSONDecodeError, OSError):
            continue
    return total >= min_designs


# -- Public entry point --------------------------------------------------------


def suggest_from_campaign(campaign_dir: str, min_designs: int = 10) -> OptimizationResult:
    """Analyze campaign data and suggest next-round parameters.

    Collects all ``*_scores.json`` files under *campaign_dir*, trains a random
    forest regressor on the scored designs, and returns data-driven
    recommendations.  Falls back to a rule-based stub when fewer than *min_designs*
    scored designs are available or when scikit-learn is not installed.
    """
    # Collect all scored designs
    scores_path = Path(campaign_dir)
    all_designs: list[dict] = []
    files_skipped = 0
    skip_warnings: list[str] = []
    for f in scores_path.rglob("*_scores.json"):
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list):
                all_designs.extend(data)
        except json.JSONDecodeError as exc:
            files_skipped += 1
            skip_warnings.append(f"Skipped {f.name}: invalid JSON ({exc})")
            continue
        except OSError as exc:
            files_skipped += 1
            skip_warnings.append(f"Skipped {f.name}: read error ({exc})")
            continue

    if len(all_designs) < min_designs:
        return OptimizationResult(
            source="rule_based",
            recommended_parameters={},
            confidence="low",
            explanation=(
                f"Only {len(all_designs)} scored designs -- need {min_designs}+ for ML. "
                "Using rule-based iteration."
            ),
            files_skipped=files_skipped,
            warnings=skip_warnings,
        )

    try:
        result = _ml_suggest(all_designs)
        result.files_skipped = files_skipped
        result.warnings = skip_warnings
        return result
    except ImportError:
        return OptimizationResult(
            source="rule_based",
            recommended_parameters={},
            confidence="low",
            explanation=(
                "scikit-learn not installed. "
                "pip install scikit-learn for ML-based optimization."
            ),
            files_skipped=files_skipped,
            warnings=skip_warnings,
        )


# -- Internal ML logic ---------------------------------------------------------

# Features used by the random forest (subset of _FEATURE_NAMES that appear in
# most score dicts -- net_charge and hydrophobic_fraction are kept for
# extraction but excluded from the RF because they are rarely populated).
_RF_FEATURE_NAMES = [
    "ipsae",
    "iptm",
    "plddt",
    "rmsd",
    "liabilities",
    "cdr3_length",
]


def _ml_suggest(designs: list[dict]) -> OptimizationResult:
    """Train a RandomForest on scored designs and suggest parameters."""
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor

    # Build feature matrix
    X: list[list[float]] = []
    y: list[float] = []
    for d in designs:
        feats = _extract_features(d)
        row = [feats.get(f, 0) for f in _RF_FEATURE_NAMES]
        if all(v is not None for v in row):
            X.append(row)
            # Target: ipSAE (what we want to maximise)
            y.append(feats.get("ipsae", 0))

    if len(X) < 10:
        return OptimizationResult(
            source="rule_based",
            recommended_parameters={},
            confidence="low",
            explanation="Not enough valid features for ML.",
        )

    X_arr = np.array(X, dtype=float)
    y_arr = np.array(y, dtype=float)

    # Train random forest
    rf = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
    rf.fit(X_arr, y_arr)

    # Feature importances (sorted descending)
    importances = sorted(
        zip(_RF_FEATURE_NAMES, rf.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )

    # Derive recommendations from the top-quartile designs
    recommendations: dict = {}
    threshold = float(np.percentile(y_arr, 75))
    good_mask = y_arr >= threshold

    if good_mask.sum() > 0:
        good_means = X_arr[good_mask].mean(axis=0)
        for i, (feat, imp) in enumerate(
            zip(_RF_FEATURE_NAMES, rf.feature_importances_)
        ):
            if imp > 0.1:  # only features with significant importance
                if feat in ("ipsae", "iptm", "plddt"):
                    recommendations[f"min_{feat}"] = round(
                        float(good_means[i] * 0.9), 3
                    )
                elif feat == "rmsd":
                    recommendations[f"max_{feat}"] = round(
                        float(good_means[i] * 1.1), 2
                    )
                elif feat == "cdr3_length":
                    recommendations[f"target_{feat}"] = round(
                        float(good_means[i]), 0
                    )

    recommendations["increase_num_designs"] = len(designs) < 50
    recommendations["suggested_alpha"] = 0.001 if float(np.std(y_arr)) < 0.1 else 0.01

    top_feature = importances[0][0]
    explanation = (
        f"RF trained on {len(X)} designs. "
        f"Top feature: {top_feature} (importance: {importances[0][1]:.3f}). "
        f"Top quartile ipSAE >= {threshold:.3f}."
    )

    return OptimizationResult(
        source="active_learning",
        recommended_parameters=recommendations,
        feature_importances=[
            (f, round(float(i), 4)) for f, i in importances
        ],
        confidence="high" if len(X) > 30 else "medium",
        explanation=explanation,
    )
