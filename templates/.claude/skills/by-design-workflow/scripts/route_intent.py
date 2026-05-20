#!/usr/bin/env python3
"""Route a design intent to engine + protocol + compute target, or decide ACCEPT vs RERUN.

This script is the canonical implementation of the by-design-workflow routing
decision. It has two modes:

  1. ``--mode route`` (default) — reads an intent JSON (target, modality,
     budget, compute preference) plus the BY config, and writes
     ``routing_decision.json`` + ``handoff_package.json`` to the output dir.

  2. ``--mode accept-or-rerun`` — reads a screening summary plus the original
     ``routing_decision.json``, and writes ``accept_or_rerun.json`` with one of
     four verdicts: ACCEPT / RERUN / SWITCH_TOOL / ESCALATE.

The lookup tables at the top of this file are mirrored in
``references/tool-selection-matrix.md`` and ``references/quality-thresholds.md``.
If you change one, change the other in the same commit.

Inputs:
  - intent.json (route mode): {target, modality, hotspots?, tier?, compute_pref?, budget_usd?}
  - .by/config.json: {compute: {default_provider, fallback_allowed, local: {...}}}
  - screening_summary.json (accept-or-rerun mode): {pass_rate, ipsae_min_p50, iptm_p50, ...}

Outputs:
  - routing_decision.json
  - handoff_package.json
  - accept_or_rerun.json

Example:
  python3 route_intent.py \\
      --mode route \\
      --intent-json intent.json \\
      --config-json .by/config.json \\
      --out-dir campaigns/tnf_alpha/routing/

  python3 route_intent.py \\
      --mode accept-or-rerun \\
      --screening-summary screening_summary.json \\
      --routing-decision routing_decision.json \\
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
# Lookup tables (mirror references/tool-selection-matrix.md)
# -----------------------------------------------------------------------------

MODALITY_ALIASES: dict[str, str] = {
    "vhh": "VHH",
    "nanobody": "VHH",
    "sdab": "VHH",
    "single-domain": "VHH",
    "scfv": "scFv",
    "fab": "Fab",
    "igg": "IgG",
    "mab": "IgG",
    "antibody": "scFv",
    "de_novo": "de_novo",
    "de-novo": "de_novo",
    "de novo": "de_novo",
    "binder": "de_novo",
    "miniprotein": "de_novo",
    "ligand-binding": "de_novo",
    "structure": "structure_only",
    "fold": "structure_only",
    "predict": "structure_only",
}

ROUTING_TABLE: dict[str, dict[str, Any]] = {
    "VHH": {
        "engine": "boltzgen",
        "protocol": "nanobody-anything",
        "default_scaffolds": ["caplacizumab", "ozoralizumab"],
        "expected_pass_rate_range": "15-40%",
        "expected_pass_rate_median": 0.25,
    },
    "scFv": {
        "engine": "boltzgen",
        "protocol": "antibody-anything",
        "default_scaffolds": ["adalimumab", "tezepelumab"],
        "expected_pass_rate_range": "10-30%",
        "expected_pass_rate_median": 0.20,
    },
    "Fab": {
        "engine": "boltzgen",
        "protocol": "antibody-anything",
        "default_scaffolds": ["adalimumab", "dupilumab"],
        "expected_pass_rate_range": "10-30%",
        "expected_pass_rate_median": 0.20,
    },
    "IgG": {
        "engine": "boltzgen",
        "protocol": "antibody-anything",
        "default_scaffolds": ["adalimumab", "tezepelumab"],
        "expected_pass_rate_range": "10-25%",
        "expected_pass_rate_median": 0.18,
    },
    "de_novo": {
        "engine": "pxdesign",
        "protocol": "extended",
        "default_scaffolds": [],
        "expected_pass_rate_range": "17-82%",
        "expected_pass_rate_median": 0.40,
    },
    "de_novo_fallback": {
        "engine": "boltzgen",
        "protocol": "protein-anything",
        "default_scaffolds": [],
        "expected_pass_rate_range": "10-25%",
        "expected_pass_rate_median": 0.15,
    },
    "structure_only": {
        "engine": "protenix",
        "protocol": "base_default",
        "default_scaffolds": [],
        "expected_pass_rate_range": "n/a",
        "expected_pass_rate_median": None,
    },
}

TIER_SIZING: dict[str, dict[str, Any]] = {
    "Preview": {
        "designs_per_scaffold": 500,
        "budget_token": 10,
        "diversity_alpha": 0.001,
        "wall_hours_vhh": 0.5,
        "wall_hours_antibody": 0.75,
        "wall_hours_pxdesign": 0.5,
    },
    "Standard": {
        "designs_per_scaffold": 5000,
        "budget_token": 50,
        "diversity_alpha": 0.001,
        "wall_hours_vhh": 2.5,
        "wall_hours_antibody": 4.0,
        "wall_hours_pxdesign": 2.0,
    },
    "Production": {
        "designs_per_scaffold": 20000,
        "budget_token": 100,
        "diversity_alpha": 0.001,
        "wall_hours_vhh": 10.0,
        "wall_hours_antibody": 16.0,
        "wall_hours_pxdesign": 8.0,
    },
    "Exploratory": {
        "designs_per_scaffold": 50000,
        "budget_token": 200,
        "diversity_alpha": 0.01,
        "wall_hours_vhh": 25.0,
        "wall_hours_antibody": 40.0,
        "wall_hours_pxdesign": 24.0,
    },
}

# Default thresholds (mirror references/quality-thresholds.md)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "ipsae_min_pass": 0.3,
    "ipsae_min_good": 0.5,
    "iptm_pass": 0.5,
    "iptm_good": 0.7,
    "plddt_pass": 70.0,
    "ca_rmsd_pass": 3.5,
    "pass_rate_accept": 0.20,
    "pass_rate_escalate": 0.05,
    "pass_rate_rerun_lower": 0.10,
    "ipsae_asymmetry_max": 0.3,
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _utcnow() -> str:
    """Return current UTC time as ISO 8601 string with seconds precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON from a path, exiting with a clear message if missing or malformed."""
    if not path.exists():
        sys.exit(f"Input file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        sys.exit(f"Failed to parse JSON in {path}: {exc}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON pretty-printed to a path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def normalize_modality(raw: str) -> str:
    """Map a free-text modality string to the canonical key in ROUTING_TABLE.

    Args:
        raw: Free-text modality string from the user or upstream artifact.

    Returns:
        Canonical modality key (VHH / scFv / Fab / IgG / de_novo / structure_only).

    Raises:
        SystemExit: If the modality cannot be resolved (force the caller to ask).
    """
    key = (raw or "").strip().lower()
    if not key:
        sys.exit("Modality is empty — ASK THIS FIRST clarification question, do not guess.")
    if key in MODALITY_ALIASES:
        return MODALITY_ALIASES[key]
    sys.exit(
        f"Unknown modality '{raw}'. Valid: VHH/nanobody, scFv/Fab/IgG/antibody, "
        f"de_novo/binder, structure_only/fold. Ask the user to disambiguate."
    )


def resolve_tier(intent: dict[str, Any]) -> str:
    """Pick a tier from explicit user choice, budget, or default to Standard.

    Args:
        intent: The intent JSON payload.

    Returns:
        One of: Preview / Standard / Production / Exploratory.
    """
    explicit = intent.get("tier")
    if explicit and explicit in TIER_SIZING:
        return explicit
    budget = intent.get("budget_usd")
    if isinstance(budget, (int, float)):
        if budget <= 50:
            return "Preview"
        if budget <= 500:
            return "Standard"
        if budget <= 2000:
            return "Production"
        return "Exploratory"
    return "Standard"


def resolve_compute_target(
    intent: dict[str, Any], config: dict[str, Any]
) -> tuple[str, str]:
    """Resolve compute target from intent override or BY config.

    Args:
        intent: The intent JSON; may contain a ``compute_pref`` override.
        config: The ``.by/config.json`` payload.

    Returns:
        Tuple of (target, source) where target is local/hpc/tamarind and source
        explains where the choice came from for auditability.
    """
    explicit = intent.get("compute_pref")
    compute_cfg = config.get("compute", {})
    if explicit and explicit in {"local", "hpc", "tamarind", "auto"}:
        if explicit == "auto":
            priority = compute_cfg.get("providers_priority", ["local", "hpc", "tamarind"])
            return priority[0], "intent.compute_pref=auto"
        return explicit, "intent.compute_pref"
    default_provider = compute_cfg.get("default_provider", "local")
    return default_provider, ".by/config.json compute.default_provider"


def estimate_wall_hours(engine: str, modality: str, tier: str, num_scaffolds: int) -> float:
    """Estimate wall-clock hours for the campaign on a single local GPU.

    Args:
        engine: boltzgen / pxdesign / protenix.
        modality: VHH / scFv / Fab / IgG / de_novo / structure_only.
        tier: Preview / Standard / Production / Exploratory.
        num_scaffolds: Number of scaffolds to run (1 for de novo).

    Returns:
        Estimated wall-time hours.
    """
    tier_cfg = TIER_SIZING.get(tier, TIER_SIZING["Standard"])
    if engine == "boltzgen":
        if modality == "VHH":
            per = tier_cfg["wall_hours_vhh"]
        else:
            per = tier_cfg["wall_hours_antibody"]
    elif engine == "pxdesign":
        per = tier_cfg["wall_hours_pxdesign"]
    else:
        # Protenix: structure prediction is much faster, treat as ~0.5 h.
        return 0.5
    return float(per) * max(1, num_scaffolds)


def build_routing_decision(intent: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Construct a routing_decision.json payload from intent + config.

    Args:
        intent: The intent JSON payload.
        config: The ``.by/config.json`` payload.

    Returns:
        Routing decision dict ready to serialize.
    """
    modality = normalize_modality(intent.get("modality", ""))
    routing = ROUTING_TABLE[modality]
    tier = resolve_tier(intent)
    tier_cfg = TIER_SIZING[tier]

    scaffolds = intent.get("scaffolds") or routing["default_scaffolds"]
    num_scaffolds = max(1, len(scaffolds)) if scaffolds else 1
    designs_per_scaffold = tier_cfg["designs_per_scaffold"]
    if modality == "de_novo":
        # De novo runs without "scaffold" pools; designs are total, not per-scaffold.
        num_scaffolds = 1

    compute_target, compute_source = resolve_compute_target(intent, config)
    wall_hours = estimate_wall_hours(routing["engine"], modality, tier, num_scaffolds)

    pass_rate_median = routing["expected_pass_rate_median"]
    expected_passing = None
    if pass_rate_median is not None:
        expected_passing = int(pass_rate_median * designs_per_scaffold * num_scaffolds)

    rationale_parts: list[str] = [
        f"Modality {modality} (from intent).",
        f"Tier {tier} chosen from {'budget heuristic' if intent.get('budget_usd') else 'explicit setting' if intent.get('tier') else 'default Standard'}.",
        f"Pass-rate median {pass_rate_median} reflects canonical bucket for {modality}.",
        f"Compute target {compute_target} resolved via {compute_source}.",
    ]

    decision: dict[str, Any] = {
        "campaign_id": intent.get("campaign_id"),
        "target": intent.get("target"),
        "engine": routing["engine"],
        "protocol": routing["protocol"],
        "modality": modality,
        "tier": tier,
        "num_designs_per_scaffold": designs_per_scaffold,
        "scaffolds": scaffolds,
        "diversity_alpha": tier_cfg["diversity_alpha"],
        "budget_token": tier_cfg["budget_token"],
        "compute_target": compute_target,
        "compute_provider_source": compute_source,
        "estimated_wall_time_hours": round(wall_hours, 2),
        "estimated_pass_rate_range": routing["expected_pass_rate_range"],
        "expected_passing_designs": expected_passing,
        "rationale": " ".join(rationale_parts),
        "rerouting_triggers": [
            "local OOM (>1500 aa target)",
            "<10% pass rate at Preview stage",
            "PXDesign env failure (single retry → fallback)",
        ],
        "fallback_chain": ["local", "hpc", "tamarind"],
        "created_at": _utcnow(),
    }
    return decision


def build_handoff_package(
    decision: dict[str, Any], intent: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Construct a handoff_package.json payload from the routing decision.

    Args:
        decision: The already-built routing decision.
        intent: The intent JSON payload (for target details and hotspots).
        config: The ``.by/config.json`` payload (for local engine paths).

    Returns:
        Handoff package dict ready to serialize.
    """
    compute_cfg = config.get("compute", {})
    local_cfg = compute_cfg.get("local", {})
    engine_local = local_cfg.get(decision["engine"], {})

    package: dict[str, Any] = {
        "campaign_id": decision["campaign_id"],
        "target": intent.get("target"),
        "modality": decision["modality"],
        "engine": decision["engine"],
        "protocol": decision["protocol"],
        "hotspots": intent.get("hotspots"),
        "scaffolds": decision["scaffolds"],
        "tier": decision["tier"],
        "num_designs_per_scaffold": decision["num_designs_per_scaffold"],
        "compute_target": decision["compute_target"],
        "local_paths": {
            "binary": engine_local.get("binary"),
            "path": engine_local.get("path"),
            "conda_env": engine_local.get("conda_env"),
        }
        if decision["compute_target"] == "local"
        else None,
        "output_dir": intent.get("output_dir"),
        "diversity_alpha": decision["diversity_alpha"],
        "budget_token": decision["budget_token"],
        "msa_mode": intent.get("msa_mode", "mmseqs2"),
        "created_at": _utcnow(),
    }
    return package


def decide_accept_or_rerun(
    screening: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    """Apply the canonical accept-or-rerun rule set.

    Args:
        screening: The screening summary JSON (must include pass_rate, ipsae_min_p50,
            iptm_p50, plddt_p50, and optionally ipsae_asymmetry_p50).
        decision: The original routing_decision.json (for round bookkeeping).

    Returns:
        accept_or_rerun.json payload with verdict and reasoning.
    """
    thr = DEFAULT_THRESHOLDS
    pass_rate = float(screening.get("pass_rate", 0.0))
    ipsae_p50 = float(screening.get("ipsae_min_p50", 0.0))
    iptm_p50 = float(screening.get("iptm_p50", 0.0))
    plddt_p50 = float(screening.get("plddt_p50", 0.0))
    asymmetry_p50 = float(screening.get("ipsae_asymmetry_p50", 0.0))
    round_index = int(screening.get("round_index", 1))
    designs_total = int(screening.get("designs_total", 0))

    verdict = "ACCEPT"
    reasoning_parts: list[str] = []
    next_action = ""

    # Step 1: ESCALATE (hard reject)
    if (
        iptm_p50 < 0.4
        and plddt_p50 < 60
        and pass_rate < thr["pass_rate_escalate"]
    ):
        verdict = "ESCALATE"
        reasoning_parts.append(
            f"Catastrophic failure: iptm_p50={iptm_p50:.2f} (<0.4), "
            f"plddt_p50={plddt_p50:.1f} (<60), pass_rate={pass_rate:.1%} "
            f"(<{thr['pass_rate_escalate']:.0%}). Epitope likely untractable."
        )
        next_action = (
            "Recommend wet-lab epitope mapping before further computational investment."
        )
    # Step 2: SWITCH_TOOL (round 2+, pass rate stuck)
    elif (
        round_index >= 2
        and pass_rate < thr["pass_rate_rerun_lower"]
        and decision.get("engine") != "switched_already"
    ):
        verdict = "SWITCH_TOOL"
        current = decision["engine"]
        alt = "pxdesign" if current == "boltzgen" else "boltzgen"
        reasoning_parts.append(
            f"Round {round_index} pass rate {pass_rate:.1%} < "
            f"{thr['pass_rate_rerun_lower']:.0%} after RERUN. "
            f"Switch from {current} to {alt} with the same hotspots."
        )
        next_action = f"Re-route with engine={alt} as A/B test."
    # Step 3: RERUN (recoverable)
    elif (
        pass_rate < thr["pass_rate_accept"]
        or ipsae_p50 < thr["ipsae_min_good"]
        or asymmetry_p50 > thr["ipsae_asymmetry_max"]
    ):
        verdict = "RERUN"
        if asymmetry_p50 > thr["ipsae_asymmetry_max"]:
            reasoning_parts.append(
                f"ipSAE asymmetry {asymmetry_p50:.2f} > "
                f"{thr['ipsae_asymmetry_max']}; partial interface — tighten hotspots."
            )
            next_action = "Drop 1-2 edge hotspots and re-run same engine/tier."
        elif ipsae_p50 < thr["ipsae_min_good"]:
            reasoning_parts.append(
                f"ipSAE p50 {ipsae_p50:.2f} below Good threshold "
                f"{thr['ipsae_min_good']}; interface confidence marginal."
            )
            next_action = (
                "Narrow hotspot window to 3-5 spatially clustered residues; "
                "consider a different epitope region."
            )
        else:
            reasoning_parts.append(
                f"Pass rate {pass_rate:.1%} below accept threshold "
                f"{thr['pass_rate_accept']:.0%} but above escalate threshold."
            )
            next_action = (
                "Re-run with adjusted hotspots; if iptm is high but ipSAE is low, "
                "tighten hotspots; if diversity is collapsed, raise diversity_alpha."
            )
    else:
        # Step 4: ACCEPT
        verdict = "ACCEPT"
        reasoning_parts.append(
            f"Pass rate {pass_rate:.1%} ≥ accept threshold "
            f"{thr['pass_rate_accept']:.0%}; ipSAE p50 {ipsae_p50:.2f} ≥ "
            f"{thr['ipsae_min_good']}; asymmetry {asymmetry_p50:.2f} within limit."
        )
        next_action = (
            "Recommend lab submission of top 10 (Standard tier) or top 50 "
            "(Production tier) designs after by-screening final pass."
        )

    return {
        "campaign_id": decision.get("campaign_id"),
        "verdict": verdict,
        "round_index": round_index,
        "metrics_summary": {
            "designs_total": designs_total,
            "pass_rate": pass_rate,
            "ipsae_min_p50": ipsae_p50,
            "iptm_p50": iptm_p50,
            "plddt_p50": plddt_p50,
            "ipsae_asymmetry_p50": asymmetry_p50,
        },
        "verdict_reasoning": " ".join(reasoning_parts),
        "next_action": next_action,
        "escalation_path": (
            "If RERUN exceeds 2 rounds without ACCEPT, switch tool. "
            "If SWITCH_TOOL also fails, escalate to wet-lab epitope mapping."
        ),
        "created_at": _utcnow(),
    }


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Route a design intent to engine + preset, or compute ACCEPT/RERUN verdict."
    )
    parser.add_argument(
        "--mode",
        choices=["route", "accept-or-rerun"],
        default="route",
        help="Operation mode: 'route' (default) builds routing decision; "
        "'accept-or-rerun' produces post-screening verdict.",
    )
    parser.add_argument(
        "--intent-json",
        type=Path,
        help="Path to intent JSON (route mode). Required when --mode=route.",
    )
    parser.add_argument(
        "--config-json",
        type=Path,
        help="Path to .by/config.json (route mode). Required when --mode=route.",
    )
    parser.add_argument(
        "--screening-summary",
        type=Path,
        help="Path to screening summary JSON (accept-or-rerun mode).",
    )
    parser.add_argument(
        "--routing-decision",
        type=Path,
        help="Path to original routing_decision.json (accept-or-rerun mode).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory to write output JSON files (created if missing).",
    )
    return parser.parse_args()


def main() -> None:
    """Dispatch to route or accept-or-rerun mode and write output files."""
    args = _parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "route":
        if not args.intent_json or not args.config_json:
            sys.exit("--intent-json and --config-json are required in route mode.")
        intent = _load_json(args.intent_json)
        config = _load_json(args.config_json)

        decision = build_routing_decision(intent, config)
        handoff = build_handoff_package(decision, intent, config)

        decision_path = out_dir / "routing_decision.json"
        handoff_path = out_dir / "handoff_package.json"
        _write_json(decision_path, decision)
        _write_json(handoff_path, handoff)

        print(
            f"✓ Routing decision written: {decision_path} "
            f"(engine={decision['engine']}, protocol={decision['protocol']}, "
            f"tier={decision['tier']}, compute={decision['compute_target']})"
        )
        print(
            f"✓ Handoff package written: {handoff_path} "
            f"(scaffolds={len(decision['scaffolds'])}, "
            f"designs_per_scaffold={decision['num_designs_per_scaffold']})"
        )
        return

    # accept-or-rerun mode
    if not args.screening_summary or not args.routing_decision:
        sys.exit(
            "--screening-summary and --routing-decision are required in "
            "accept-or-rerun mode."
        )
    screening = _load_json(args.screening_summary)
    decision = _load_json(args.routing_decision)

    verdict = decide_accept_or_rerun(screening, decision)
    verdict_path = out_dir / "accept_or_rerun.json"
    _write_json(verdict_path, verdict)
    print(
        f"✓ Accept-or-rerun verdict written: {verdict_path} "
        f"(verdict={verdict['verdict']}, pass_rate="
        f"{verdict['metrics_summary']['pass_rate']:.1%})"
    )


if __name__ == "__main__":
    main()
