"""Cost estimation for campaign GPU and lab spend."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import CampaignConfig

# GPU hourly rates by provider (USD).
HOURLY_RATES: dict[str, float] = {
    "tamarind": 2.50,
    "local": 0.0,
}

# BoltzGen design time: roughly 0.001 hours per design (3.6 sec/design on cloud GPU).
BOLTZGEN_HOURS_PER_DESIGN = 0.001

# Post-BoltzGen screening time per ranked design in minutes.
# This covers Protenix refolding validation and scoring pipeline.
SCREENING_MINUTES_PER_DESIGN = 2.0


@dataclass
class CostEstimate:
    """Itemized cost breakdown for a campaign."""
    design_gpu_hours: float = 0.0
    screening_gpu_hours: float = 0.0
    total_gpu_hours: float = 0.0
    cloud_cost_usd: float = 0.0
    lab_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    breakdown: dict[str, Any] = field(default_factory=dict)


def estimate_cost(config: CampaignConfig) -> CostEstimate:
    """Compute an estimated cost breakdown for the given campaign config.

    BoltzGen cost model:
    - Design time: num_designs * 0.001 hours per scaffold (cloud GPU)
    - No separate prediction step (BoltzGen does generation + inverse folding
      + refolding internally)
    - Screening: runs on the 'budget' designs that survive BoltzGen ranking
    """
    num_scaffolds = max(len(config.design.scaffolds), 1)
    num_designs = config.boltzgen.num_designs
    budget = config.boltzgen.budget
    total_designs = num_scaffolds * num_designs

    # Design generation time (BoltzGen on Tamarind)
    design_gpu_hours = total_designs * BOLTZGEN_HOURS_PER_DESIGN

    # Screening time: runs on budget designs (post-BoltzGen ranking)
    total_budget = num_scaffolds * budget
    screening_minutes = total_budget * SCREENING_MINUTES_PER_DESIGN
    screening_gpu_hours = screening_minutes / 60.0

    total_gpu_hours = design_gpu_hours + screening_gpu_hours

    # Cloud cost
    rate = HOURLY_RATES.get(config.compute.provider, HOURLY_RATES["tamarind"])
    cloud_cost_usd = total_gpu_hours * rate

    # Lab cost
    lab_cost_usd = config.lab.max_candidates * config.lab.cost_per_variant_usd

    total_cost_usd = cloud_cost_usd + lab_cost_usd

    breakdown = {
        "num_scaffolds": num_scaffolds,
        "num_designs_per_scaffold": num_designs,
        "total_designs": total_designs,
        "budget_per_scaffold": budget,
        "total_budget": total_budget,
        "modality": config.design.modality,
        "tier": config.boltzgen.tier,
        "alpha": config.boltzgen.alpha,
        "hourly_rate_usd": rate,
        "provider": config.compute.provider,
    }

    return CostEstimate(
        design_gpu_hours=round(design_gpu_hours, 2),
        screening_gpu_hours=round(screening_gpu_hours, 2),
        total_gpu_hours=round(total_gpu_hours, 2),
        cloud_cost_usd=round(cloud_cost_usd, 2),
        lab_cost_usd=round(lab_cost_usd, 2),
        total_cost_usd=round(total_cost_usd, 2),
        breakdown=breakdown,
    )


def format_cost_table(estimate: CostEstimate) -> str:
    """Return a human-readable, space-aligned cost table."""
    rate = _rate(estimate)
    tier = estimate.breakdown.get("tier", "standard")
    modality = estimate.breakdown.get("modality", "vhh")
    num_scaffolds = estimate.breakdown.get("num_scaffolds", 1)
    num_designs = estimate.breakdown.get("num_designs_per_scaffold", 0)
    total_designs = estimate.breakdown.get("total_designs", 0)
    total_budget = estimate.breakdown.get("total_budget", 0)

    rows = [
        ("BoltzGen design", f"{estimate.design_gpu_hours:.1f} hr",
         f"${estimate.design_gpu_hours * rate:,.2f}"),
        ("Screening + scoring", f"{estimate.screening_gpu_hours:.1f} hr",
         f"${estimate.screening_gpu_hours * rate:,.2f}"),
        ("GPU subtotal", f"{estimate.total_gpu_hours:.1f} hr",
         f"${estimate.cloud_cost_usd:,.2f}"),
        (f"Lab testing ({estimate.breakdown.get('num_candidates', '-')})",
         "-",
         f"${estimate.lab_cost_usd:,.2f}"),
        ("TOTAL", "-", f"${estimate.total_cost_usd:,.2f}"),
    ]

    # Compute column widths.
    col0_w = max(len(r[0]) for r in rows)
    col1_w = max(len(r[1]) for r in rows)
    col2_w = max(len(r[2]) for r in rows)

    lines = []
    lines.append(f"  Campaign: {tier} tier | {modality} | {num_scaffolds} scaffold(s)")
    lines.append(f"  Designs: {total_designs:,} total ({num_designs:,}/scaffold) -> {total_budget} ranked")
    lines.append("")
    lines.append(f"  {'Component':<{col0_w}}  {'Hours':>{col1_w}}  {'Cost':>{col2_w}}")
    lines.append(f"  {'-' * (col0_w + col1_w + col2_w + 4)}")
    for label, hours, cost in rows:
        lines.append(f"  {label:<{col0_w}}  {hours:>{col1_w}}  {cost:>{col2_w}}")

    return "\n".join(lines)


def _rate(estimate: CostEstimate) -> float:
    """Extract the hourly rate from the breakdown."""
    return estimate.breakdown.get("hourly_rate_usd", 2.50)
