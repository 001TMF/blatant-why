"""Statistical failure diagnosis for design campaigns."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeatureAnalysis:
    feature_name: str
    test_type: str  # "mann_whitney" or "chi_squared"
    statistic: float
    p_value: float
    effect_size: float
    passed_mean: float | None = None
    failed_mean: float | None = None
    interpretation: str = ""


@dataclass
class FailureDiagnosis:
    total_designs: int
    passed: int
    failed: int
    pass_rate: float
    discriminating_features: list[FeatureAnalysis] = field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)


def diagnose_failures(
    designs: list[dict],
    pass_key: str = "status",
    pass_value: str = "PASS",
) -> FailureDiagnosis:
    """Compare passed vs failed designs to find discriminating features."""
    # Check scipy availability before doing any work
    try:
        import scipy.stats  # noqa: F401
    except ImportError:
        return FailureDiagnosis(
            total_designs=len(designs),
            passed=0,
            failed=0,
            pass_rate=0.0,
            summary=(
                "scipy is not installed — statistical diagnosis requires it. "
                "Install with: pip install scipy"
            ),
        )

    passed = [d for d in designs if d.get(pass_key) == pass_value]
    failed = [d for d in designs if d.get(pass_key) != pass_value]

    if not passed or not failed:
        return FailureDiagnosis(
            total_designs=len(designs),
            passed=len(passed),
            failed=len(failed),
            pass_rate=len(passed) / max(len(designs), 1),
            summary="Cannot diagnose: need both passed and failed designs.",
        )

    # Continuous features to test
    continuous = [
        "ipsae",
        "ipsae_min",
        "iptm",
        "plddt",
        "rmsd",
        "net_charge",
        "hydrophobic_fraction",
        "liabilities",
        "cdr3_length",
    ]

    analyses: list[FeatureAnalysis] = []
    for feat in continuous:
        p_vals = [d.get(feat) for d in passed if d.get(feat) is not None]
        f_vals = [d.get(feat) for d in failed if d.get(feat) is not None]
        if len(p_vals) < 3 or len(f_vals) < 3:
            continue

        try:
            from scipy.stats import mannwhitneyu
            import numpy as np

            stat, pval = mannwhitneyu(p_vals, f_vals, alternative="two-sided")
            p_mean = float(np.mean(p_vals))
            f_mean = float(np.mean(f_vals))
            effect = abs(p_mean - f_mean) / max(
                float(np.std(p_vals + f_vals)), 1e-6
            )

            direction = "higher" if p_mean > f_mean else "lower"
            interp = (
                f"{feat} is significantly {direction} in passed designs "
                f"(mean {p_mean:.3f} vs {f_mean:.3f})"
            )

            analyses.append(
                FeatureAnalysis(
                    feature_name=feat,
                    test_type="mann_whitney",
                    statistic=float(stat),
                    p_value=float(pval),
                    effect_size=round(effect, 3),
                    passed_mean=round(p_mean, 4),
                    failed_mean=round(f_mean, 4),
                    interpretation=interp,
                )
            )
        except (ValueError, TypeError, ArithmeticError) as exc:
            # Skip features where the statistical test fails (e.g.
            # constant values, type mismatches, division issues)
            continue

    # Sort by p-value
    analyses.sort(key=lambda a: a.p_value)
    significant = [a for a in analyses if a.p_value < 0.05]

    # Generate recommendations
    recommendations: list[str] = []
    for a in significant[:3]:
        if (
            a.feature_name in ("ipsae", "ipsae_min", "iptm")
            and a.passed_mean is not None
            and a.failed_mean is not None
        ):
            if a.passed_mean > a.failed_mean:
                recommendations.append(
                    f"Increase {a.feature_name} threshold "
                    f"(passed mean: {a.passed_mean:.3f})"
                )
        elif (
            a.feature_name == "rmsd"
            and a.passed_mean is not None
            and a.failed_mean is not None
        ):
            if a.passed_mean < a.failed_mean:
                recommendations.append(
                    f"Tighten RMSD filter "
                    f"(passed mean: {a.passed_mean:.2f}\u00c5)"
                )
        elif (
            a.feature_name == "cdr3_length"
            and a.passed_mean is not None
            and a.failed_mean is not None
        ):
            recommendations.append(
                f"Constrain CDR3 length "
                f"(passed mean: {a.passed_mean:.0f} vs "
                f"failed: {a.failed_mean:.0f})"
            )
        elif a.feature_name == "liabilities":
            recommendations.append(
                f"Reduce liability count "
                f"(passed mean: {a.passed_mean:.1f} vs "
                f"failed: {a.failed_mean:.1f})"
            )

    summary = f"{len(significant)} discriminating features found (p<0.05). "
    if significant:
        summary += (
            f"Top: {significant[0].feature_name} "
            f"(p={significant[0].p_value:.4f})"
        )

    return FailureDiagnosis(
        total_designs=len(designs),
        passed=len(passed),
        failed=len(failed),
        pass_rate=len(passed) / len(designs),
        discriminating_features=analyses,
        summary=summary,
        recommendations=recommendations,
    )


def format_diagnosis(diag: FailureDiagnosis) -> str:
    """Format a FailureDiagnosis as a human-readable text report."""
    lines = [
        f"  Failure Diagnosis ({diag.passed}/{diag.total_designs} passed, "
        f"{diag.pass_rate:.0%} rate)",
        "",
    ]
    sig = [a for a in diag.discriminating_features if a.p_value < 0.05]
    if sig:
        lines.append("  Discriminating Features (p < 0.05):")
        lines.append(
            f"  {'Feature':<20} {'Passed':<10} {'Failed':<10} "
            f"{'p-value':<10} {'Effect'}"
        )
        lines.append("  " + "\u2500" * 60)
        for a in sig[:5]:
            p = f"{a.passed_mean:.3f}" if a.passed_mean is not None else "\u2014"
            f = f"{a.failed_mean:.3f}" if a.failed_mean is not None else "\u2014"
            lines.append(
                f"  {a.feature_name:<20} {p:<10} {f:<10} "
                f"{a.p_value:<10.4f} {a.effect_size:.2f}"
            )
    if diag.recommendations:
        lines.append("")
        lines.append("  Recommendations:")
        for r in diag.recommendations:
            lines.append(f"    - {r}")
    return "\n".join(lines)
