"""Lab results analysis and next-round recommendation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import CampaignConfig
from .state import CampaignState


@dataclass
class IterationAnalysis:
    """Summary of lab results and recommended next action."""
    hit_rate: float = 0.0
    scaffold_analysis: list[dict[str, Any]] = field(default_factory=list)
    threshold_refinement: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""


def analyze_lab_results(
    lab_results: list[dict[str, Any]],
    campaign_state: CampaignState,
) -> IterationAnalysis:
    """Analyze lab assay results and produce an iteration recommendation.

    Each entry in lab_results should contain at minimum:
        - "design_id": str
        - "scaffold": str
        - "hit": bool (True if the design was a binder in the assay)
    Optional fields: "kd_nm", "iptm", "ipsae", "plddt"
    """
    if not lab_results:
        return IterationAnalysis(
            hit_rate=0.0,
            recommendation="no_data",
        )

    total = len(lab_results)
    hits = sum(1 for r in lab_results if r.get("hit", False))
    hit_rate = hits / total if total > 0 else 0.0

    # Per-scaffold hit rates.
    scaffold_counts: dict[str, dict[str, int]] = {}
    for r in lab_results:
        scaffold = r.get("scaffold", "unknown")
        entry = scaffold_counts.setdefault(scaffold, {"total": 0, "hits": 0})
        entry["total"] += 1
        if r.get("hit", False):
            entry["hits"] += 1

    scaffold_analysis = []
    for scaffold, counts in sorted(scaffold_counts.items()):
        sc_total = counts["total"]
        sc_hits = counts["hits"]
        sc_rate = sc_hits / sc_total if sc_total > 0 else 0.0
        scaffold_analysis.append({
            "scaffold": scaffold,
            "total": sc_total,
            "hits": sc_hits,
            "hit_rate": round(sc_rate, 4),
        })

    # Threshold refinement: compare predicted scores of hits vs misses.
    threshold_refinement: dict[str, Any] = {}
    for metric in ("iptm", "ipsae", "plddt"):
        hit_vals = [r[metric] for r in lab_results if r.get("hit") and metric in r]
        miss_vals = [r[metric] for r in lab_results if not r.get("hit") and metric in r]
        if hit_vals and miss_vals:
            threshold_refinement[metric] = {
                "hit_mean": round(sum(hit_vals) / len(hit_vals), 4),
                "miss_mean": round(sum(miss_vals) / len(miss_vals), 4),
                "suggested_threshold": round(
                    (sum(hit_vals) / len(hit_vals) + sum(miss_vals) / len(miss_vals)) / 2.0,
                    4,
                ),
            }

    # Determine recommendation.
    current_iteration = campaign_state.iteration
    if hit_rate > 0.30:
        recommendation = "scale_up"
    elif hit_rate >= 0.10:
        recommendation = "adjust"
    elif hit_rate > 0.0:
        recommendation = "major_change"
    else:
        # Zero hits.
        if current_iteration >= 2:
            recommendation = "abort"
        else:
            recommendation = "major_change"

    return IterationAnalysis(
        hit_rate=round(hit_rate, 4),
        scaffold_analysis=scaffold_analysis,
        threshold_refinement=threshold_refinement,
        recommendation=recommendation,
    )


def recommend_next_round(
    analysis: IterationAnalysis,
    config: CampaignConfig,
) -> dict[str, Any]:
    """Produce updated parameters for the next design round.

    Returns a dict suitable for passing to ``add_round(state, parameters)``.
    """
    params: dict[str, Any] = {
        "recommendation": analysis.recommendation,
        "previous_hit_rate": analysis.hit_rate,
    }

    if analysis.recommendation == "scale_up":
        # Keep top scaffolds, increase designs per scaffold.
        top_scaffolds = [
            s["scaffold"]
            for s in sorted(
                analysis.scaffold_analysis, key=lambda x: x["hit_rate"], reverse=True,
            )
            if s["hit_rate"] > 0.0
        ]
        # Drop bottom half of scaffolds.
        keep = max(len(top_scaffolds) // 2, 1)
        params["scaffolds"] = top_scaffolds[:keep]
        params["designs_per_scaffold"] = int(config.design.designs_per_scaffold * 1.5)
        params["budget"] = config.design.budget

    elif analysis.recommendation == "adjust":
        # Vary one axis: increase budget or try different seed selection.
        params["scaffolds"] = [
            s["scaffold"] for s in analysis.scaffold_analysis
        ]
        params["designs_per_scaffold"] = config.design.designs_per_scaffold
        params["budget"] = min(config.design.budget + 16, 128)
        # Suggest tighter screening if thresholds are available.
        if analysis.threshold_refinement:
            params["refined_thresholds"] = {
                metric: info["suggested_threshold"]
                for metric, info in analysis.threshold_refinement.items()
            }

    elif analysis.recommendation == "major_change":
        # Suggest epitope or tool change — flag for human review.
        params["action"] = "review_required"
        params["suggestions"] = [
            "Consider alternative epitope region",
            "Consider switching design tool or protocol",
            "Review target structure quality",
        ]
        params["scaffolds"] = [
            s["scaffold"] for s in analysis.scaffold_analysis
        ]
        params["designs_per_scaffold"] = config.design.designs_per_scaffold

    elif analysis.recommendation == "abort":
        params["action"] = "abort_recommended"
        params["reason"] = (
            "Zero hits after multiple rounds. "
            "Target may not be tractable with current approach."
        )

    return params
