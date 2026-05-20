#!/usr/bin/env python3
"""Estimate design space, wall time, and expected passing designs for a campaign.

This script is the canonical budgeting tool invoked by by-design-workflow before
launching compute. It maps (modality, tier, number of scaffolds, optional pass-rate
override) to a structured forecast that ``by-campaign-manager`` consumes for the
cost gate.

Lookup tables are mirrored in ``references/preset-comparison.md``. If you change a
bucket here, change it in the reference doc in the same commit.

Inputs:
  - --modality   : VHH / scFv / Fab / IgG / de_novo / structure_only
  - --tier       : Preview / Standard / Production / Exploratory
  - --num-scaffolds : Number of scaffolds in the campaign (default 1)
  - --target-class  : well_studied / moderate / novel / difficult (refines pass rate)
  - --pass-rate     : Optional explicit override (0.0 - 1.0)
  - --compute-target: local / hpc / tamarind (for cost estimate)
  - --out-dir       : Where to write pass_rate_forecast.json

Output:
  - pass_rate_forecast.json with total_designs, wall_hours, expected_passing,
    estimated_cost_usd, and rationale.

Example:
  python3 estimate_design_space.py \\
      --modality VHH \\
      --tier Standard \\
      --num-scaffolds 2 \\
      --target-class well_studied \\
      --compute-target local \\
      --out-dir campaigns/tnf_alpha/routing/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# -----------------------------------------------------------------------------
# Lookup tables (mirror references/preset-comparison.md)
# -----------------------------------------------------------------------------

VALID_MODALITIES = {"VHH", "scFv", "Fab", "IgG", "de_novo", "structure_only"}
VALID_TIERS = {"Preview", "Standard", "Production", "Exploratory"}
VALID_TARGET_CLASSES = {"well_studied", "moderate", "novel", "difficult"}
VALID_COMPUTE_TARGETS = {"local", "hpc", "tamarind"}

DESIGNS_PER_SCAFFOLD: dict[str, int] = {
    "Preview": 500,
    "Standard": 5000,
    "Production": 20000,
    "Exploratory": 50000,
}

# Wall-time per scaffold in hours on a 1x80GB local GPU.
WALL_HOURS_BY_MODALITY_AND_TIER: dict[str, dict[str, float]] = {
    "VHH": {"Preview": 0.5, "Standard": 2.5, "Production": 10.0, "Exploratory": 25.0},
    "scFv": {"Preview": 0.75, "Standard": 4.0, "Production": 16.0, "Exploratory": 40.0},
    "Fab": {"Preview": 0.75, "Standard": 4.0, "Production": 16.0, "Exploratory": 40.0},
    "IgG": {"Preview": 0.75, "Standard": 4.0, "Production": 16.0, "Exploratory": 40.0},
    "de_novo": {"Preview": 0.5, "Standard": 2.0, "Production": 8.0, "Exploratory": 24.0},
    "structure_only": {"Preview": 0.1, "Standard": 0.5, "Production": 1.0, "Exploratory": 2.0},
}

# Pass-rate matrix [modality][target_class] -> median pass rate.
PASS_RATE_MATRIX: dict[str, dict[str, float]] = {
    "VHH": {
        "well_studied": 0.35,
        "moderate": 0.25,
        "novel": 0.15,
        "difficult": 0.10,
    },
    "scFv": {
        "well_studied": 0.25,
        "moderate": 0.20,
        "novel": 0.12,
        "difficult": 0.08,
    },
    "Fab": {
        "well_studied": 0.25,
        "moderate": 0.20,
        "novel": 0.12,
        "difficult": 0.08,
    },
    "IgG": {
        "well_studied": 0.22,
        "moderate": 0.18,
        "novel": 0.10,
        "difficult": 0.06,
    },
    "de_novo": {
        "well_studied": 0.55,
        "moderate": 0.35,
        "novel": 0.20,
        "difficult": 0.10,
    },
    "structure_only": {
        "well_studied": 1.0,  # Not a pass-rate metric; placeholder.
        "moderate": 1.0,
        "novel": 1.0,
        "difficult": 1.0,
    },
}

# Compute cost USD per GPU-hour by target.
COMPUTE_HOURLY_USD: dict[str, float] = {
    "local": 0.0,
    "hpc": 3.50,        # RunPod H100 SXM bucket midpoint
    "tamarind": 5.00,   # Tamarind cold-start credits midpoint
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _utcnow() -> str:
    """Return UTC timestamp as ISO 8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Pretty-print JSON to disk, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def estimate_total_designs(modality: str, tier: str, num_scaffolds: int) -> int:
    """Return total designs in the campaign.

    Args:
        modality: Canonical modality key.
        tier: Canonical tier name.
        num_scaffolds: Number of scaffolds in this campaign.

    Returns:
        Total designs across all scaffolds (or single de novo run).
    """
    per_scaffold = DESIGNS_PER_SCAFFOLD[tier]
    if modality == "de_novo":
        # De novo has no scaffold concept — designs are total.
        return per_scaffold
    return per_scaffold * max(1, num_scaffolds)


def estimate_wall_hours(modality: str, tier: str, num_scaffolds: int) -> float:
    """Return wall-clock hours on a 1×80GB local GPU.

    Args:
        modality: Canonical modality key.
        tier: Canonical tier name.
        num_scaffolds: Number of scaffolds.

    Returns:
        Total wall-time hours.
    """
    per = WALL_HOURS_BY_MODALITY_AND_TIER[modality][tier]
    if modality in {"de_novo", "structure_only"}:
        return per
    return per * max(1, num_scaffolds)


def resolve_pass_rate(
    modality: str, target_class: str, explicit_override: float | None
) -> float:
    """Pick a pass rate from explicit override or the canonical bucket.

    Args:
        modality: Canonical modality key.
        target_class: well_studied / moderate / novel / difficult.
        explicit_override: Optional 0.0-1.0 override (e.g., empirical prior).

    Returns:
        Pass rate as a float in [0.0, 1.0].
    """
    if explicit_override is not None:
        if not 0.0 <= explicit_override <= 1.0:
            sys.exit(f"--pass-rate must be between 0.0 and 1.0, got {explicit_override}")
        return explicit_override
    return PASS_RATE_MATRIX[modality][target_class]


def estimate_cost_usd(wall_hours: float, compute_target: str) -> float:
    """Estimate dollar cost for the campaign on the chosen compute target.

    Args:
        wall_hours: Total wall-time hours.
        compute_target: local / hpc / tamarind.

    Returns:
        Estimated cost in USD (0.0 for local).
    """
    rate = COMPUTE_HOURLY_USD.get(compute_target, 0.0)
    return round(rate * wall_hours, 2)


def build_forecast(
    modality: str,
    tier: str,
    num_scaffolds: int,
    target_class: str,
    pass_rate_override: float | None,
    compute_target: str,
) -> dict[str, Any]:
    """Construct the forecast payload.

    Args:
        modality: Canonical modality key.
        tier: Canonical tier name.
        num_scaffolds: Number of scaffolds.
        target_class: well_studied / moderate / novel / difficult.
        pass_rate_override: Optional explicit pass-rate override.
        compute_target: local / hpc / tamarind.

    Returns:
        Forecast dict ready to serialize.
    """
    total_designs = estimate_total_designs(modality, tier, num_scaffolds)
    wall_hours = estimate_wall_hours(modality, tier, num_scaffolds)
    pass_rate = resolve_pass_rate(modality, target_class, pass_rate_override)
    expected_passing = int(round(total_designs * pass_rate))
    cost_usd = estimate_cost_usd(wall_hours, compute_target)

    rationale = (
        f"Modality {modality}, tier {tier}, {num_scaffolds} scaffold(s). "
        f"Pass rate {pass_rate:.0%} sourced from "
        f"{'explicit override' if pass_rate_override is not None else f'target_class={target_class} bucket'}. "
        f"Wall time {wall_hours:.1f} h on 1×80GB local GPU; "
        f"cost ${cost_usd:.2f} on {compute_target}."
    )

    return {
        "modality": modality,
        "tier": tier,
        "num_scaffolds": num_scaffolds,
        "target_class": target_class,
        "total_designs": total_designs,
        "estimated_pass_rate": pass_rate,
        "expected_passing_designs": expected_passing,
        "estimated_wall_hours": round(wall_hours, 2),
        "compute_target": compute_target,
        "estimated_cost_usd": cost_usd,
        "rationale": rationale,
        "created_at": _utcnow(),
    }


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Estimate total designs, wall-time hours, expected passing designs, "
            "and cost for a campaign before launching compute."
        )
    )
    parser.add_argument(
        "--modality",
        required=True,
        choices=sorted(VALID_MODALITIES),
        help="Canonical modality key.",
    )
    parser.add_argument(
        "--tier",
        required=True,
        choices=sorted(VALID_TIERS),
        help="Campaign tier.",
    )
    parser.add_argument(
        "--num-scaffolds",
        type=int,
        default=1,
        help="Number of scaffolds in the campaign (ignored for de_novo/structure_only).",
    )
    parser.add_argument(
        "--target-class",
        default="moderate",
        choices=sorted(VALID_TARGET_CLASSES),
        help="Target difficulty bucket; refines the pass-rate prior.",
    )
    parser.add_argument(
        "--pass-rate",
        type=float,
        default=None,
        help="Explicit pass-rate override (0.0-1.0). Bypasses the target_class bucket.",
    )
    parser.add_argument(
        "--compute-target",
        default="local",
        choices=sorted(VALID_COMPUTE_TARGETS),
        help="Compute target for the cost estimate.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory to write pass_rate_forecast.json (created if missing).",
    )
    return parser.parse_args()


def main() -> None:
    """Build the forecast and write it to disk."""
    args = _parse_args()
    forecast = build_forecast(
        modality=args.modality,
        tier=args.tier,
        num_scaffolds=args.num_scaffolds,
        target_class=args.target_class,
        pass_rate_override=args.pass_rate,
        compute_target=args.compute_target,
    )
    out_path: Path = args.out_dir / "pass_rate_forecast.json"
    _write_json(out_path, forecast)
    print(
        f"✓ Forecast written: {out_path} "
        f"(total_designs={forecast['total_designs']}, "
        f"expected_passing={forecast['expected_passing_designs']}, "
        f"wall_hours={forecast['estimated_wall_hours']}, "
        f"cost=${forecast['estimated_cost_usd']:.2f})"
    )


if __name__ == "__main__":
    main()
