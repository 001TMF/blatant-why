#!/usr/bin/env python3
"""Estimate BY campaign cost across local, HPC RunPod, and Tamarind compute targets.

Purpose
-------
Given a target name, modality, tier, and scaffold count, this script prints a
side-by-side comparison of wall-clock hours and USD cost for each supported
compute provider, with simple confidence intervals.

Inputs (CLI args)
-----------------
- --target: target name (free-form string, used only for display)
- --modality: one of {vhh, scfv, bispecific_scfv, denovo}
- --tier: one of {preview, standard, production}
- --scaffolds: integer number of scaffolds (default 2)
- --provider: one of {local, hpc, tamarind, all} (default all)
- --gpu-class: HPC GPU class (default a100_40gb_spot); see GPU_RATES
- --target-length-aa: target protein length, for scaling (default 250)
- --glycosylated: flag — adds glycosylation overhead multiplier
- --lab-candidates: integer candidates submitted to lab (default 0)
- --lab-cost-per-variant: USD per lab variant (default 250)
- --out: optional path to write JSON estimate; defaults to stdout-only

Outputs
-------
- Stdout: human-readable table comparing providers.
- Optional JSON file with structured breakdown for downstream consumption.

Example invocation
------------------
    python scripts/estimate_campaign.py \\
        --target PD-L1 \\
        --modality vhh \\
        --tier standard \\
        --scaffolds 2 \\
        --provider all \\
        --out cost_estimate.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# Constants — calibration                                                     #
# --------------------------------------------------------------------------- #

# Designs per scaffold by tier
DESIGNS_PER_SCAFFOLD: dict[str, int] = {
    "preview": 500,
    "standard": 5000,
    "production": 20000,
}

# Engine selection by modality (display only; engines run via their own skills)
MODALITY_ENGINE: dict[str, str] = {
    "vhh": "BoltzGen (nanobody-anything)",
    "scfv": "BoltzGen (antibody-anything)",
    "bispecific_scfv": "BoltzGen (antibody-anything, bispecific)",
    "denovo": "PXDesign",
}

# Hours per design (single A100 40GB baseline)
HOURS_PER_DESIGN: dict[str, float] = {
    "vhh": 0.0010,            # ~3.6 sec/design
    "scfv": 0.0015,           # 1.5x VHH
    "bispecific_scfv": 0.0020,
    "denovo": 0.0012,
}

# Modality scaling factor (multiplies HOURS_PER_DESIGN)
MODALITY_SCALING: dict[str, float] = {
    "vhh": 1.0,
    "scfv": 1.5,
    "bispecific_scfv": 2.0,
    "denovo": 1.2,
}

# Long-target overhead threshold (aa)
LONG_TARGET_THRESHOLD_AA: int = 500
LONG_TARGET_SCALING: float = 1.3
GLYCOSYLATION_SCALING: float = 1.4

# Screening: ranked candidates per scaffold (post-engine ranking)
SCREENING_RANKED_PER_SCAFFOLD: int = 100
SCREENING_MINUTES_PER_DESIGN: float = 2.0  # Protenix refold validation per top candidate

# HPC RunPod GPU rates ($/hr); spot + on-demand
GPU_RATES: dict[str, dict[str, float]] = {
    "rtx_4090_spot":     {"hourly_usd": 0.34, "vram_gb": 24, "on_demand": 0.69},
    "a40_spot":          {"hourly_usd": 0.39, "vram_gb": 48, "on_demand": 0.79},
    "a100_40gb_spot":    {"hourly_usd": 0.79, "vram_gb": 40, "on_demand": 1.89},
    "a100_80gb_spot":    {"hourly_usd": 1.49, "vram_gb": 80, "on_demand": 2.69},
    "h100_pcie_spot":    {"hourly_usd": 2.49, "vram_gb": 80, "on_demand": 4.89},
}

TAMARIND_HOURLY_USD: float = 2.50
LOCAL_HOURLY_USD: float = 0.00  # User-facing report

# Confidence interval (fractional) per provider
CI_FRACTION: dict[str, float] = {
    "local": 0.25,
    "hpc": 0.20,
    "tamarind": 0.10,
}
HPC_QUEUE_BUFFER: float = 1.15  # Spot queues add ~15% wall clock


# --------------------------------------------------------------------------- #
# Dataclasses                                                                 #
# --------------------------------------------------------------------------- #

@dataclass
class ProviderEstimate:
    """Single-provider cost estimate."""
    provider: str
    gpu_hours: float
    cost_usd_mid: float
    cost_usd_low: float
    cost_usd_high: float
    wall_clock_hr: float
    notes: str = ""


@dataclass
class CampaignEstimate:
    """Full estimate across all requested providers."""
    target: str
    modality: str
    tier: str
    scaffolds: int
    total_designs: int
    total_ranked: int
    engine: str
    modality_factor: float
    estimates: list[ProviderEstimate] = field(default_factory=list)
    lab_cost_usd: float = 0.0
    recommendation: str = ""


# --------------------------------------------------------------------------- #
# Core math                                                                   #
# --------------------------------------------------------------------------- #

def compute_modality_factor(
    modality: str,
    target_length_aa: int,
    glycosylated: bool,
) -> float:
    """Compute total scaling factor applied to base hours/design.

    Combines the modality scaling, long-target overhead, and glycosylation overhead.
    """
    factor = MODALITY_SCALING.get(modality, 1.0)
    if target_length_aa > LONG_TARGET_THRESHOLD_AA:
        factor *= LONG_TARGET_SCALING
    if glycosylated:
        factor *= GLYCOSYLATION_SCALING
    return factor


def compute_gpu_hours(
    total_designs: int,
    total_ranked: int,
    modality: str,
    modality_factor: float,
) -> tuple[float, float]:
    """Return (design_hours, screening_hours) for given workload.

    Screening hours assume Protenix refold of top-ranked candidates.
    """
    per_design_hr = HOURS_PER_DESIGN.get(modality, 0.0012) * modality_factor
    design_hours = total_designs * per_design_hr
    screening_hours = total_ranked * (SCREENING_MINUTES_PER_DESIGN / 60.0)
    return design_hours, screening_hours


def estimate_local(
    design_hours: float,
    screening_hours: float,
) -> ProviderEstimate:
    """Local GPU is $0; report wall clock with ±25% CI."""
    total_hr = design_hours + screening_hours
    ci = CI_FRACTION["local"]
    return ProviderEstimate(
        provider="local",
        gpu_hours=round(total_hr, 2),
        cost_usd_mid=0.0,
        cost_usd_low=0.0,
        cost_usd_high=0.0,
        wall_clock_hr=round(total_hr, 2),
        notes=f"On-prem GPU; ±{int(ci*100)}% wall-clock variance",
    )


def estimate_hpc(
    design_hours: float,
    screening_hours: float,
    gpu_class: str,
) -> ProviderEstimate:
    """HPC RunPod cost = (design + screening) hours * $/hr * queue buffer."""
    if gpu_class not in GPU_RATES:
        raise ValueError(
            f"Unknown gpu_class '{gpu_class}'. Options: {sorted(GPU_RATES)}"
        )
    rate = GPU_RATES[gpu_class]["hourly_usd"]
    total_hr_raw = design_hours + screening_hours
    total_hr = total_hr_raw * HPC_QUEUE_BUFFER
    cost_mid = total_hr_raw * rate
    ci = CI_FRACTION["hpc"]
    return ProviderEstimate(
        provider=f"hpc ({gpu_class})",
        gpu_hours=round(total_hr_raw, 2),
        cost_usd_mid=round(cost_mid, 2),
        cost_usd_low=round(cost_mid * (1 - ci), 2),
        cost_usd_high=round(cost_mid * (1 + ci), 2),
        wall_clock_hr=round(total_hr, 2),
        notes=f"Spot pool, +{int((HPC_QUEUE_BUFFER-1)*100)}% queue buffer",
    )


def estimate_tamarind(
    design_hours: float,
    screening_hours: float,
) -> ProviderEstimate:
    """Tamarind cost = total hours * $2.50/hr (reference)."""
    total_hr = design_hours + screening_hours
    cost_mid = total_hr * TAMARIND_HOURLY_USD
    ci = CI_FRACTION["tamarind"]
    return ProviderEstimate(
        provider="tamarind",
        gpu_hours=round(total_hr, 2),
        cost_usd_mid=round(cost_mid, 2),
        cost_usd_low=round(cost_mid * (1 - ci), 2),
        cost_usd_high=round(cost_mid * (1 + ci), 2),
        wall_clock_hr=round(total_hr, 2),
        notes=f"Managed cloud; ±{int(ci*100)}% rate variance",
    )


def recommend_provider(
    estimates: list[ProviderEstimate],
    modality: str,
) -> str:
    """Recommendation string for the report footer."""
    if modality in {"scfv", "bispecific_scfv"}:
        return (
            "Recommendation: local if GPU >= 40 GB VRAM; otherwise HPC (A100 40GB+). "
            "Antibody campaigns need 40+ GB cards."
        )
    return (
        "Recommendation: local (default, $0). HPC if local card unavailable or "
        "wall clock too long. Tamarind only when local + HPC both unavailable."
    )


# --------------------------------------------------------------------------- #
# Estimate orchestration                                                      #
# --------------------------------------------------------------------------- #

def estimate_campaign(
    target: str,
    modality: str,
    tier: str,
    scaffolds: int,
    provider: str,
    gpu_class: str,
    target_length_aa: int,
    glycosylated: bool,
    lab_candidates: int,
    lab_cost_per_variant: float,
) -> CampaignEstimate:
    """Compute the full campaign estimate across requested providers."""
    if modality not in DESIGNS_PER_SCAFFOLD and modality not in HOURS_PER_DESIGN:
        # Catch unknown modality early
        raise ValueError(f"Unknown modality '{modality}'.")
    if tier not in DESIGNS_PER_SCAFFOLD:
        raise ValueError(
            f"Unknown tier '{tier}'. Options: {sorted(DESIGNS_PER_SCAFFOLD)}"
        )

    total_designs = scaffolds * DESIGNS_PER_SCAFFOLD[tier]
    total_ranked = scaffolds * SCREENING_RANKED_PER_SCAFFOLD
    modality_factor = compute_modality_factor(
        modality, target_length_aa, glycosylated
    )
    design_hours, screening_hours = compute_gpu_hours(
        total_designs, total_ranked, modality, modality_factor
    )

    estimates: list[ProviderEstimate] = []
    requested = (
        ["local", "hpc", "tamarind"] if provider == "all" else [provider]
    )
    for p in requested:
        if p == "local":
            estimates.append(estimate_local(design_hours, screening_hours))
        elif p == "hpc":
            estimates.append(
                estimate_hpc(design_hours, screening_hours, gpu_class)
            )
        elif p == "tamarind":
            estimates.append(estimate_tamarind(design_hours, screening_hours))
        else:
            raise ValueError(
                f"Unknown provider '{p}'. Options: local, hpc, tamarind, all."
            )

    lab_cost = lab_candidates * lab_cost_per_variant

    return CampaignEstimate(
        target=target,
        modality=modality,
        tier=tier,
        scaffolds=scaffolds,
        total_designs=total_designs,
        total_ranked=total_ranked,
        engine=MODALITY_ENGINE.get(modality, "unknown"),
        modality_factor=round(modality_factor, 2),
        estimates=estimates,
        lab_cost_usd=round(lab_cost, 2),
        recommendation=recommend_provider(estimates, modality),
    )


# --------------------------------------------------------------------------- #
# Rendering                                                                   #
# --------------------------------------------------------------------------- #

def render_table(estimate: CampaignEstimate) -> str:
    """Render the estimate as a human-readable table."""
    lines: list[str] = []
    lines.append(f"Campaign: {estimate.tier} tier | {estimate.modality} | "
                 f"{estimate.scaffolds} scaffold(s) | engine: {estimate.engine}")
    lines.append(f"Target: {estimate.target}")
    lines.append(
        f"Designs: {estimate.total_designs:,} total "
        f"-> {estimate.total_ranked} ranked (modality factor x{estimate.modality_factor})"
    )
    lines.append("")
    header = f"{'Provider':<22} {'Wall Clock':>12} {'Cost USD':>22} {'Notes'}"
    lines.append(header)
    lines.append("-" * (len(header) + 20))
    for p in estimate.estimates:
        cost_str = f"${p.cost_usd_mid:,.2f}"
        if p.cost_usd_high > p.cost_usd_low:
            cost_str = (
                f"${p.cost_usd_mid:,.2f} "
                f"(${p.cost_usd_low:,.2f}-${p.cost_usd_high:,.2f})"
            )
        lines.append(
            f"{p.provider:<22} {p.wall_clock_hr:>9.1f} hr "
            f"{cost_str:>22} {p.notes}"
        )
    if estimate.lab_cost_usd > 0:
        lines.append("")
        lines.append(f"Lab cost (if submitted): ${estimate.lab_cost_usd:,.2f}")
    lines.append("")
    lines.append(estimate.recommendation)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="estimate_campaign.py",
        description="Estimate BY campaign cost across local, HPC, and Tamarind providers.",
    )
    parser.add_argument("--target", required=True,
                        help="Target name (display only).")
    parser.add_argument("--modality", required=True,
                        choices=sorted(HOURS_PER_DESIGN.keys()),
                        help="Design modality.")
    parser.add_argument("--tier", required=True,
                        choices=sorted(DESIGNS_PER_SCAFFOLD.keys()),
                        help="Campaign tier.")
    parser.add_argument("--scaffolds", type=int, default=2,
                        help="Number of scaffolds (default 2).")
    parser.add_argument("--provider", default="all",
                        choices=["local", "hpc", "tamarind", "all"],
                        help="Which provider(s) to estimate (default all).")
    parser.add_argument("--gpu-class", default="a100_40gb_spot",
                        choices=sorted(GPU_RATES.keys()),
                        help="HPC RunPod GPU class (default a100_40gb_spot).")
    parser.add_argument("--target-length-aa", type=int, default=250,
                        help="Target protein length in aa (default 250).")
    parser.add_argument("--glycosylated", action="store_true",
                        help="Set if target is glycosylated (adds overhead).")
    parser.add_argument("--lab-candidates", type=int, default=0,
                        help="Number of lab candidates (default 0).")
    parser.add_argument("--lab-cost-per-variant", type=float, default=250.0,
                        help="USD per lab variant (default 250).")
    parser.add_argument("--out", default=None,
                        help="Optional path to write JSON estimate.")
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    estimate = estimate_campaign(
        target=args.target,
        modality=args.modality,
        tier=args.tier,
        scaffolds=args.scaffolds,
        provider=args.provider,
        gpu_class=args.gpu_class,
        target_length_aa=args.target_length_aa,
        glycosylated=args.glycosylated,
        lab_candidates=args.lab_candidates,
        lab_cost_per_variant=args.lab_cost_per_variant,
    )

    print(render_table(estimate))

    if args.out:
        try:
            with open(args.out, "w") as f:
                json.dump(asdict(estimate), f, indent=2)
            print(f"\n✓ Estimate written: {args.out}")
        except OSError as e:
            sys.exit(f"Failed to write {args.out}: {e}")
    else:
        print(f"\n✓ Estimate computed: {len(estimate.estimates)} provider(s)")


if __name__ == "__main__":
    main()
