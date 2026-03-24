"""Cross-validation between dual structure predictors."""
from __future__ import annotations
from dataclasses import dataclass
from math import isclose


@dataclass
class CrossValidationResult:
    design_name: str
    predictor_1: str  # e.g., "boltzgen"
    predictor_2: str  # e.g., "protenix"
    iptm_1: float
    iptm_2: float
    ipsae_1: float
    ipsae_2: float
    iptm_delta: float
    ipsae_agreement: bool
    status: str  # "consensus", "divergent", "rejected"
    confidence: str  # "high", "medium", "low"


def classify_cross_validation(
    iptm_1: float, iptm_2: float,
    ipsae_1: float, ipsae_2: float,
    iptm_threshold: float = 0.3,
    ipsae_min: float = 0.3,
) -> tuple[str, str]:
    """Classify a design based on dual predictor agreement.

    Returns (status, confidence) tuple.
    """
    iptm_delta = abs(iptm_1 - iptm_2)
    within_iptm_threshold = iptm_delta < iptm_threshold or isclose(iptm_delta, iptm_threshold)
    both_ipsae_good = ipsae_1 >= ipsae_min and ipsae_2 >= ipsae_min
    both_ipsae_bad = ipsae_1 < 0.1 and ipsae_2 < 0.1

    if iptm_delta > 0.5 or both_ipsae_bad:
        return "rejected", "low"
    elif within_iptm_threshold and both_ipsae_good:
        return "consensus", "high"
    else:
        return "divergent", "medium"


def _has_predictor_scores(
    d: dict,
    predictor_1_key: str,
    predictor_2_key: str,
) -> bool:
    """Check whether a design has real scores from both predictors."""
    # A score is "missing" if the predictor-specific key is absent and
    # the value falls back to the 0 default.
    has_p1 = (
        f"{predictor_1_key}_iptm" in d
        or f"{predictor_1_key}_ipsae" in d
        or "iptm" in d
        or "ipsae_min" in d
    )
    has_p2 = (
        f"{predictor_2_key}_iptm" in d
        or f"{predictor_2_key}_ipsae" in d
    )
    return has_p1 and has_p2


def cross_validate_designs(
    designs: list[dict],
    predictor_1_key: str = "boltzgen",
    predictor_2_key: str = "protenix",
) -> list[CrossValidationResult]:
    """Cross-validate a list of designs with dual predictor scores."""
    results = []
    for d in designs:
        iptm_1 = d.get(f"{predictor_1_key}_iptm", d.get("iptm", 0))
        iptm_2 = d.get(f"{predictor_2_key}_iptm", 0)
        ipsae_1 = d.get(f"{predictor_1_key}_ipsae", d.get("ipsae_min", 0))
        ipsae_2 = d.get(f"{predictor_2_key}_ipsae", 0)

        # If either predictor's scores are entirely missing, classify as
        # data_incomplete instead of potentially mis-rejecting.
        if not _has_predictor_scores(d, predictor_1_key, predictor_2_key):
            status, confidence = "data_incomplete", "none"
        else:
            status, confidence = classify_cross_validation(iptm_1, iptm_2, ipsae_1, ipsae_2)

        results.append(CrossValidationResult(
            design_name=d.get("design_name", d.get("name", "unknown")),
            predictor_1=predictor_1_key,
            predictor_2=predictor_2_key,
            iptm_1=iptm_1, iptm_2=iptm_2,
            ipsae_1=ipsae_1, ipsae_2=ipsae_2,
            iptm_delta=round(abs(iptm_1 - iptm_2), 4),
            ipsae_agreement=ipsae_1 >= 0.3 and ipsae_2 >= 0.3,
            status=status, confidence=confidence,
        ))
    return results


def format_cross_validation(results: list[CrossValidationResult]) -> str:
    """Format cross-validation results as space-aligned text."""
    lines = ["  Cross-Validation Results", ""]
    lines.append(f"  {'Design':<20} {'Status':<12} {'Conf':<8} {'ipTM Δ':<10} {'ipSAE agree'}")
    lines.append("  " + "\u2500" * 65)
    for r in results:
        agree = "Yes" if r.ipsae_agreement else "No"
        lines.append(f"  {r.design_name:<20} {r.status:<12} {r.confidence:<8} {r.iptm_delta:<10.3f} {agree}")

    consensus = sum(1 for r in results if r.status == "consensus")
    divergent = sum(1 for r in results if r.status == "divergent")
    rejected = sum(1 for r in results if r.status == "rejected")
    lines.append("")
    lines.append(f"  Consensus: {consensus}  Divergent: {divergent}  Rejected: {rejected}")
    return "\n".join(lines)
