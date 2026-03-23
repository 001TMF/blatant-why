"""Screening funnel estimation based on historical pass rates.

BoltzGen internally generates num_designs candidates and ranks them down to
'budget' designs.  The funnel here starts AFTER BoltzGen's internal ranking,
so the input count is budget * num_scaffolds (not total raw designs).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .config import CampaignConfig

# Pass rates by (tool, protocol, target_difficulty).
# Each value maps filter stage name -> expected pass rate.
# BoltzGen designs are pre-ranked, so pass rates are higher than raw tools.
PASS_RATES: dict[tuple[str, str, str], dict[str, float]] = {
    # boltzgen nanobody-anything (VHH)
    ("boltzgen", "nanobody-anything", "well-studied"): {
        "iptm": 0.70, "ipsae": 0.60, "plddt": 0.90, "rmsd": 0.75,
        "liability": 0.75, "developability": 0.85,
    },
    ("boltzgen", "nanobody-anything", "moderate"): {
        "iptm": 0.55, "ipsae": 0.45, "plddt": 0.85, "rmsd": 0.65,
        "liability": 0.70, "developability": 0.80,
    },
    ("boltzgen", "nanobody-anything", "novel"): {
        "iptm": 0.35, "ipsae": 0.30, "plddt": 0.80, "rmsd": 0.50,
        "liability": 0.70, "developability": 0.80,
    },
    # boltzgen antibody-anything (scFv via Fab template)
    ("boltzgen", "antibody-anything", "well-studied"): {
        "iptm": 0.65, "ipsae": 0.55, "plddt": 0.88, "rmsd": 0.70,
        "liability": 0.70, "developability": 0.80,
    },
    ("boltzgen", "antibody-anything", "moderate"): {
        "iptm": 0.50, "ipsae": 0.40, "plddt": 0.82, "rmsd": 0.60,
        "liability": 0.65, "developability": 0.75,
    },
    ("boltzgen", "antibody-anything", "novel"): {
        "iptm": 0.30, "ipsae": 0.25, "plddt": 0.75, "rmsd": 0.45,
        "liability": 0.65, "developability": 0.75,
    },
    # boltzgen protein-anything (de novo miniprotein)
    ("boltzgen", "protein-anything", "well-studied"): {
        "iptm": 0.60, "ipsae": 0.50, "plddt": 0.85, "rmsd": 0.65,
        "liability": 0.80, "developability": 0.85,
    },
    ("boltzgen", "protein-anything", "moderate"): {
        "iptm": 0.45, "ipsae": 0.38, "plddt": 0.80, "rmsd": 0.55,
        "liability": 0.75, "developability": 0.80,
    },
    ("boltzgen", "protein-anything", "novel"): {
        "iptm": 0.28, "ipsae": 0.22, "plddt": 0.72, "rmsd": 0.42,
        "liability": 0.75, "developability": 0.78,
    },
}

# Ordered sequence of filter stages applied during screening.
FILTER_ORDER = [
    "iptm",
    "ipsae",
    "plddt",
    "rmsd",
    "liability",
    "developability",
]

# Human-readable names for filter stages.
STAGE_NAMES: dict[str, str] = {
    "iptm": "ipTM > threshold",
    "ipsae": "ipSAE > threshold",
    "plddt": "pLDDT > threshold",
    "rmsd": "RMSD < threshold",
    "liability": "Liability scan",
    "developability": "Developability",
}


@dataclass
class FunnelStage:
    """A single stage in the screening funnel."""
    name: str
    input_count: int
    pass_rate: float
    output_count: int


@dataclass
class FunnelEstimate:
    """Full funnel estimation from BoltzGen budget through screening."""
    stages: list[FunnelStage] = field(default_factory=list)
    survivors: int = 0
    lab_candidates: int = 0
    boltzgen_input: int = 0  # total raw designs before BoltzGen ranking
    boltzgen_budget: int = 0  # designs entering the screening funnel


def _lookup_rates(config: CampaignConfig) -> dict[str, float]:
    """Find the best-matching pass rate table for the config."""
    key = (config.design.tool, config.design.protocol, config.target_difficulty)
    if key in PASS_RATES:
        return PASS_RATES[key]

    # Fall back: try matching just tool + difficulty with any protocol.
    for (tool, _proto, diff), rates in PASS_RATES.items():
        if tool == config.design.tool and diff == config.target_difficulty:
            return rates

    # Final fallback: moderate boltzgen nanobody rates.
    return PASS_RATES[("boltzgen", "nanobody-anything", "moderate")]


def estimate_funnel(config: CampaignConfig) -> FunnelEstimate:
    """Estimate how many designs survive each screening stage.

    The funnel starts AFTER BoltzGen's internal ranking, so the input
    count is budget * num_scaffolds (not total raw designs).
    """
    num_scaffolds = max(len(config.design.scaffolds), 1)
    num_designs = config.boltzgen.num_designs
    budget = config.boltzgen.budget

    # BoltzGen generates num_designs per scaffold, ranks down to budget
    total_raw = num_scaffolds * num_designs
    total_budget = num_scaffolds * budget

    rates = _lookup_rates(config)

    stages: list[FunnelStage] = []
    current = total_budget  # funnel starts from budget, not total designs

    for stage_key in FILTER_ORDER:
        rate = rates.get(stage_key, 0.80)
        output = max(int(math.floor(current * rate)), 0)
        stages.append(FunnelStage(
            name=STAGE_NAMES.get(stage_key, stage_key),
            input_count=current,
            pass_rate=rate,
            output_count=output,
        ))
        current = output

    survivors = current
    lab_candidates = min(survivors, config.lab.max_candidates)

    return FunnelEstimate(
        stages=stages,
        survivors=survivors,
        lab_candidates=lab_candidates,
        boltzgen_input=total_raw,
        boltzgen_budget=total_budget,
    )


def format_funnel(estimate: FunnelEstimate) -> str:
    """Return a space-aligned funnel visualization."""
    # Column widths.
    name_w = max((len(s.name) for s in estimate.stages), default=20)
    name_w = max(name_w, len("Stage"))

    header = (
        f"  {'Stage':<{name_w}}  {'Input':>7}  {'Rate':>6}  {'Output':>7}"
    )
    sep = "  " + "-" * (name_w + 7 + 6 + 7 + 6)

    lines = [
        f"  BoltzGen: {estimate.boltzgen_input:,} designs -> {estimate.boltzgen_budget} ranked (budget)",
        "",
        header,
        sep,
    ]
    for stage in estimate.stages:
        lines.append(
            f"  {stage.name:<{name_w}}  {stage.input_count:>7}  "
            f"{stage.pass_rate:>5.0%}  {stage.output_count:>7}"
        )

    lines.append(sep)
    lines.append(
        f"  {'Survivors':<{name_w}}  {'':>7}  {'':>6}  {estimate.survivors:>7}"
    )
    lines.append(
        f"  {'Lab candidates':<{name_w}}  {'':>7}  {'':>6}  {estimate.lab_candidates:>7}"
    )

    return "\n".join(lines)
