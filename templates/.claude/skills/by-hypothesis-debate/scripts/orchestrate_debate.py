#!/usr/bin/env python3
"""Orchestrate a 3+1 hypothesis-debate for protein/antibody design strategy selection.

Reads a research bundle (output of `by-research`) and a campaign config
skeleton, spawns three hypothesis agents in parallel (Conservative,
Aggressive, Diverse), collects their `strategy_proposal.json` outputs,
spawns a single reflection agent to rank the proposals, and writes the
winning strategy into the campaign config.

Inputs
------
- research-dir : path to a directory containing
    research.md, recommended_hotspots.json, design_recommendation.json,
    validated_findings.json (output of `by-research`)
- campaign-config : path to campaign_config.yaml with target/PDB set
    but modality/scaffolds/tier TBD
- output-dir : where to write proposals/, ranking.json, debate_log.jsonl,
    and the updated campaign_config.yaml

Outputs
-------
- output-dir/proposals/<agent>.json (one per hypothesis agent)
- output-dir/ranking.json
- output-dir/debate_log.jsonl
- output-dir/decision_summary.md
- in-place update of campaign-config to include the winning strategy

Example
-------
    python3 orchestrate_debate.py \\
        --research-dir campaigns/IL23R/campaign_20260520_001/research \\
        --campaign-config campaigns/IL23R/campaign_20260520_001/campaign_config.yaml \\
        --output-dir campaigns/IL23R/campaign_20260520_001/debate \\
        --num-agents 3 \\
        --tie-break merge \\
        --reflection-temperature 0.2

Note
----
This script uses a Task() spawn API that exists in the BY Claude agent
runtime. When run standalone (no Task() in scope), it falls back to a
mock dispatcher that writes placeholder proposals so the pipeline can be
exercised end-to-end. Replace the `_spawn_agent_task` body with the real
runtime call in production.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("Install with: pip install pyyaml")

try:
    from validate_proposal import validate_proposal_dict
except ImportError:
    # Allow running from outside the scripts/ dir.
    sys.path.insert(0, str(Path(__file__).parent))
    from validate_proposal import validate_proposal_dict


HYPOTHESIS_AGENTS = ["conservative", "aggressive", "diverse"]
TIE_BREAK_MODES = ["merge", "aggressive_wins", "user_decides", "risk_adjusted"]
DEFAULT_WEIGHTS = {
    "balanced": {"W_RIGOR": 0.30, "W_FEASIBILITY": 0.25, "W_INNOVATION": 0.20, "W_RISK": 0.25},
    "hit_rate": {"W_RIGOR": 0.30, "W_FEASIBILITY": 0.30, "W_INNOVATION": 0.10, "W_RISK": 0.30},
    "diversity": {"W_RIGOR": 0.20, "W_FEASIBILITY": 0.20, "W_INNOVATION": 0.35, "W_RISK": 0.25},
    "novelty": {"W_RIGOR": 0.20, "W_FEASIBILITY": 0.15, "W_INNOVATION": 0.45, "W_RISK": 0.20},
}


@dataclass
class DebateConfig:
    research_dir: Path
    campaign_config: Path
    output_dir: Path
    num_agents: int = 3
    tie_break: str = "merge"
    reflection_temperature: float = 0.2
    rubric_preset: str = "balanced"
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.tie_break not in TIE_BREAK_MODES:
            raise ValueError(f"Unknown tie_break mode: {self.tie_break}. Use one of {TIE_BREAK_MODES}")
        if self.rubric_preset not in DEFAULT_WEIGHTS:
            raise ValueError(f"Unknown rubric preset: {self.rubric_preset}. Use one of {list(DEFAULT_WEIGHTS)}")
        if not 0.0 <= self.reflection_temperature <= 1.0:
            raise ValueError("reflection_temperature must be in [0.0, 1.0]")

    def weights(self) -> dict[str, float]:
        return DEFAULT_WEIGHTS[self.rubric_preset]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_event(config: DebateConfig, event: str, **fields: Any) -> None:
    """Append a structured event to the audit log and to debate_log.jsonl."""
    record = {"timestamp": _now_iso(), "event": event, **fields}
    config.audit_log.append(record)
    log_path = config.output_dir / "debate_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def load_research_bundle(research_dir: Path) -> dict[str, Any]:
    """Load required research artifacts. Raises FileNotFoundError if any missing."""
    required = [
        "research.md",
        "recommended_hotspots.json",
        "design_recommendation.json",
        "validated_findings.json",
    ]
    bundle: dict[str, Any] = {}
    for name in required:
        path = research_dir / name
        if not path.exists():
            raise FileNotFoundError(
                f"Required research artifact missing: {path}. "
                f"Run `by-research` to completion before debating."
            )
        if name.endswith(".json"):
            with path.open() as f:
                bundle[name] = json.load(f)
        else:
            with path.open() as f:
                bundle[name] = f.read()
    return bundle


def load_campaign_config(path: Path) -> dict[str, Any]:
    """Load campaign config YAML. Creates skeleton if missing."""
    if not path.exists():
        return {"target": None, "pdb_id": None, "compute": {"provider": "local"}}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def build_agent_directive(agent: str, research: dict[str, Any], campaign_config: dict[str, Any]) -> str:
    """Build the system prompt for a hypothesis agent.

    Reads the directive template from references/agent-profiles.md indirectly
    by encoding the same constraints inline (the references file is the
    canonical source for editing).
    """
    research_summary = json.dumps(research["validated_findings.json"], indent=2)[:2000]
    hotspots = json.dumps(research["recommended_hotspots.json"], indent=2)
    base = (
        f"You are the {agent.capitalize()} hypothesis agent in a strategy debate "
        f"for the BY protein design pipeline.\n\n"
        f"Target: {campaign_config.get('target', 'unknown')}\n"
        f"Validated findings (truncated):\n{research_summary}\n\n"
        f"Recommended hotspots:\n{hotspots}\n\n"
    )

    directives = {
        "conservative": (
            "Propose the lowest-risk, highest-precedent design strategy. "
            "Use scaffolds with PDB co-crystal evidence. Default to standard "
            "tier. Prefer VHH > scFv > de novo. Cite at least 3 HIGH-confidence "
            "research_source_ids. Do NOT propose untested scaffolds, novel "
            "modalities without precedent, or computational-only justifications."
        ),
        "aggressive": (
            "Propose the highest-novelty, first-in-class strategy. Your "
            "proposal MUST be novel in modality OR epitope OR scaffold. Default "
            "to production tier. Justify why this target needs the novel "
            "approach. Be willing to fail with information gain. Cite at least "
            "1 supporting source. Do NOT propose conventional defaults."
        ),
        "diverse": (
            "Propose a strategy hedging across at least 2 sub-runs varying "
            "modality OR epitope OR scaffold. Total designs across sub-runs "
            "must fit within standard tier. Enumerate the competing hypotheses "
            "your sub-runs cover. Plan for cross-run aggregation. Cite at least "
            "2 sources, one per sub-hypothesis."
        ),
    }
    output_schema_note = (
        "\n\nWrite your output as a strategy_proposal.json conforming to the "
        "schema in by-hypothesis-debate/SKILL.md. Required fields: agent, "
        "version='1.0', target, modality, protocol, scaffolds, tier, "
        "num_designs_per_scaffold, compute_provider, epitope, rationale, "
        "expected_hit_rate, expected_wall_time_hours, key_risks, mitigation, "
        "confidence, research_source_ids."
    )
    return base + directives[agent] + output_schema_note


def _spawn_agent_task(agent: str, directive: str, output_path: Path) -> dict[str, Any]:
    """Spawn a hypothesis agent via the BY Task() runtime.

    In the live BY agent runtime, this would call:
        Task(agent=f"by-{agent}-hypothesis", prompt=directive, output_path=output_path)

    When run standalone (e.g., for testing the orchestration loop without an
    LLM), the function returns a mock placeholder. Replace this body with
    the real Task() invocation in production.
    """
    try:
        # Real runtime path -- the Task symbol is injected by the BY agent host.
        Task  # type: ignore[name-defined]
    except NameError:
        # Standalone / test path: write a minimal mock proposal so the rest
        # of the pipeline can be exercised. This is NOT a substitute for the
        # real agent dispatch.
        mock = _build_mock_proposal(agent)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            json.dump(mock, f, indent=2)
        return {"status": "mocked", "task_id": f"mock_{agent}", "output_path": str(output_path)}

    # Real path (would be reachable in production):
    task_id = f"tsk_{agent}_{int(time.time())}"
    # Task(...)  -- left as a placeholder for the runtime call.
    return {"status": "spawned", "task_id": task_id, "output_path": str(output_path)}


def _build_mock_proposal(agent: str) -> dict[str, Any]:
    """Return a schema-valid placeholder proposal for standalone testing only."""
    base = {
        "agent": agent,
        "version": "1.0",
        "target": "MOCK_TARGET",
        "modality": "VHH",
        "protocol": "nanobody-anything",
        "scaffolds": ["caplacizumab"],
        "tier": "standard",
        "num_designs_per_scaffold": 5000,
        "compute_provider": "local",
        "epitope": {
            "pdb_id": "0XXX",
            "target_chain": "A",
            "residues": [1],
            "range_notation": "A1",
        },
        "rationale": f"Mock proposal from {agent} agent for standalone testing.",
        "expected_hit_rate": "10-30%",
        "expected_wall_time_hours": 4,
        "key_risks": ["mock_risk"],
        "mitigation": ["mock_mitigation"],
        "confidence": 0.5,
        "research_source_ids": ["src_001"],
    }
    if agent == "aggressive":
        base["modality"] = "de_novo_binder"
        base["protocol"] = "protein-anything"
        base["scaffolds"] = ["custom_helical_bundle"]
        base["tier"] = "production"
        base["confidence"] = 0.4
    if agent == "diverse":
        base["modality"] = "mixed"
        base["protocol"] = "split_run"
        base["sub_runs"] = [
            {"sub_run_id": "sub_001", "modality": "VHH", "num_designs": 3000},
            {"sub_run_id": "sub_002", "modality": "de_novo_binder", "num_designs": 2000},
        ]
        base["total_designs"] = 5000
    return base


def spawn_hypothesis_agents(config: DebateConfig, research: dict[str, Any], campaign_config: dict[str, Any]) -> list[Path]:
    """Spawn the configured number of hypothesis agents in parallel.

    Returns the list of proposal output paths once all agents return.
    """
    proposals_dir = config.output_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for agent in HYPOTHESIS_AGENTS[: config.num_agents]:
        directive = build_agent_directive(agent, research, campaign_config)
        output_path = proposals_dir / f"{agent}.json"
        result = _spawn_agent_task(agent, directive, output_path)
        _log_event(config, "spawned_agent", agent=agent, task_id=result["task_id"], status=result["status"])
        paths.append(output_path)

    # In real runtime, we would wait for all tasks here.
    # In mock mode, files are already written by _spawn_agent_task.

    for path in paths:
        if not path.exists():
            _log_event(config, "agent_no_output", path=str(path))
            raise RuntimeError(f"Agent did not produce output: {path}")
        _log_event(config, "proposal_returned", path=str(path))

    return paths


def validate_proposals(paths: list[Path], config: DebateConfig) -> list[dict[str, Any]]:
    """Validate each proposal against the schema. Drop and log invalid ones."""
    valid: list[dict[str, Any]] = []
    for path in paths:
        with path.open() as f:
            try:
                proposal = json.load(f)
            except json.JSONDecodeError as exc:
                _log_event(config, "proposal_invalid_json", path=str(path), error=str(exc))
                continue
        errors = validate_proposal_dict(proposal)
        if errors:
            _log_event(config, "proposal_schema_invalid", path=str(path), errors=errors)
            continue
        valid.append(proposal)
        _log_event(config, "proposal_validated", agent=proposal.get("agent"))
    return valid


def score_proposal_algorithmically(proposal: dict[str, Any], research: dict[str, Any]) -> dict[str, float]:
    """Fallback scoring when reflection agent is unavailable.

    Computes per-axis scores from proposal metadata. See
    references/fallback-decisions.md §3.
    """
    findings = research["validated_findings.json"].get("findings", [])
    high_ids = {sid for finding in findings if finding.get("confidence") == "HIGH" for sid in finding.get("supporting_sources", [])}
    medium_ids = {sid for finding in findings if finding.get("confidence") == "MEDIUM" for sid in finding.get("supporting_sources", [])}
    cited = set(proposal.get("research_source_ids", []))

    high_cit = len(cited & high_ids)
    med_cit = len(cited & medium_ids)
    scientific_rigor = min(1.0, 0.3 * (high_cit / 3) + 0.4 * (med_cit / 3) + 0.3)

    tier = proposal.get("tier", "standard")
    feasibility = {"preview": 1.0, "standard": 0.85, "production": 0.65}.get(tier, 0.7)

    modality = proposal.get("modality", "VHH")
    scaffolds = proposal.get("scaffolds", [])
    is_novel_modality = modality not in {"VHH", "scFv"}
    has_custom_scaffold = any("custom" in str(s).lower() for s in scaffolds)
    innovation = 0.3 + 0.3 * is_novel_modality + 0.3 * has_custom_scaffold

    risks = proposal.get("key_risks", []) or []
    mitigations = proposal.get("mitigation", []) or []
    unmitigated = max(0, len(risks) - len(mitigations))
    stated = proposal.get("confidence", 0.5)
    risk_adj = stated * max(0.0, 1.0 - 0.15 * unmitigated)

    return {
        "scientific_rigor": round(scientific_rigor, 4),
        "feasibility": round(feasibility, 4),
        "innovation": round(min(1.0, innovation), 4),
        "risk_adjusted_confidence": round(risk_adj, 4),
    }


def rank_proposals(proposals: list[dict[str, Any]], research: dict[str, Any], config: DebateConfig) -> dict[str, Any]:
    """Invoke the reflection agent to rank proposals.

    On reflection agent failure, falls back to algorithmic ranking per
    references/fallback-decisions.md §3.
    """
    # Real runtime would spawn the reflection agent here via Task().
    # For this orchestrator we use algorithmic ranking as the deterministic
    # baseline; the live runtime overrides via the by-reflection-agent task.
    weights = config.weights()
    candidates = []
    for prop in proposals:
        axes = score_proposal_algorithmically(prop, research)
        composite = (
            weights["W_RIGOR"] * axes["scientific_rigor"]
            + weights["W_FEASIBILITY"] * axes["feasibility"]
            + weights["W_INNOVATION"] * axes["innovation"]
            + weights["W_RISK"] * axes["risk_adjusted_confidence"]
        )
        candidates.append({
            "agent": prop["agent"],
            **axes,
            "composite_score": round(composite, 4),
        })
    candidates.sort(key=lambda c: c["composite_score"], reverse=True)
    for i, cand in enumerate(candidates):
        cand["rank"] = i + 1

    winner = candidates[0]["agent"]
    delta_top_two = (candidates[0]["composite_score"] - candidates[1]["composite_score"]) if len(candidates) >= 2 else 1.0
    tie_break_applied = delta_top_two < 0.05

    if tie_break_applied:
        winner = _apply_tie_break(candidates, config.tie_break)
        _log_event(config, "tie_break_applied", mode=config.tie_break, delta=delta_top_two, winner=winner)

    low_confidence = max(c["composite_score"] for c in candidates) < 0.5
    three_way_tie = len(candidates) >= 3 and (candidates[0]["composite_score"] - candidates[2]["composite_score"]) < 0.05

    ranking = {
        "version": "1.0",
        "target": proposals[0].get("target") if proposals else None,
        "ranked_at": _now_iso(),
        "rubric_preset": config.rubric_preset,
        "rubric_weights": weights,
        "candidates": candidates,
        "winner": winner,
        "tie_break_applied": tie_break_applied,
        "tie_break_mode": config.tie_break,
        "score_delta_top_two": round(delta_top_two, 4),
        "low_confidence": low_confidence,
        "three_way_tie": three_way_tie,
        "escalate_to_user": three_way_tie or (low_confidence and config.tie_break == "user_decides"),
        "rationale": f"Algorithmic ranking applied. Winner: {winner} with composite "
                     f"{candidates[0]['composite_score']:.4f}. Delta to runner-up: "
                     f"{delta_top_two:.4f}.",
        "dissenting_notes": "",
        "merged_recommendations": [],
    }
    return ranking


def _apply_tie_break(candidates: list[dict[str, Any]], mode: str) -> str:
    """Apply the configured tie-break mode and return the winner's agent name."""
    if mode == "merge":
        return candidates[0]["agent"]  # higher composite wins; merge happens separately
    if mode == "aggressive_wins":
        for cand in candidates[:2]:
            if cand["agent"] == "aggressive":
                return "aggressive"
        return candidates[0]["agent"]
    if mode == "risk_adjusted":
        return max(candidates[:2], key=lambda c: c["risk_adjusted_confidence"])["agent"]
    if mode == "user_decides":
        return candidates[0]["agent"]  # placeholder; orchestrator pauses
    return candidates[0]["agent"]


def write_outputs(
    config: DebateConfig,
    proposals: list[dict[str, Any]],
    ranking: dict[str, Any],
    campaign_config: dict[str, Any],
) -> None:
    """Write ranking.json, decision_summary.md, and update campaign_config.yaml."""
    ranking_path = config.output_dir / "ranking.json"
    with ranking_path.open("w") as f:
        json.dump(ranking, f, indent=2)
    _log_event(config, "ranking_written", path=str(ranking_path))

    summary_path = config.output_dir / "decision_summary.md"
    with summary_path.open("w") as f:
        f.write(_render_decision_summary(ranking, proposals))
    _log_event(config, "decision_summary_written", path=str(summary_path))

    winner_name = ranking["winner"]
    winner_proposal = next((p for p in proposals if p["agent"] == winner_name), None)
    if winner_proposal is None:
        raise RuntimeError(f"Winner {winner_name} not found in proposals")

    for field in ("modality", "protocol", "scaffolds", "tier", "epitope"):
        if field in winner_proposal:
            campaign_config[field] = winner_proposal[field]
    campaign_config["debate_winner"] = winner_name
    campaign_config["debate_ranking_path"] = str(ranking_path)
    if ranking.get("merged_recommendations"):
        campaign_config.setdefault("notes", []).extend(ranking["merged_recommendations"])

    with config.campaign_config.open("w") as f:
        yaml.safe_dump(campaign_config, f, sort_keys=False)
    _log_event(config, "campaign_config_updated", path=str(config.campaign_config), winner=winner_name)


def _render_decision_summary(ranking: dict[str, Any], proposals: list[dict[str, Any]]) -> str:
    lines = ["# Debate Decision Summary", ""]
    lines.append(f"**Target:** {ranking.get('target', 'unknown')}")
    lines.append(f"**Ranked at:** {ranking['ranked_at']}")
    lines.append(f"**Rubric preset:** {ranking['rubric_preset']}")
    lines.append(f"**Winner:** `{ranking['winner']}`")
    lines.append("")
    if ranking.get("escalate_to_user"):
        lines.append("> WARNING: This debate requires user input before execution.")
        lines.append("")
    if ranking.get("low_confidence"):
        lines.append("> WARNING: All proposals scored below 0.5. Treat winner as best-of-weak.")
        lines.append("")
    lines.append("## Ranking")
    lines.append("")
    lines.append("| Rank | Agent | Composite | Rigor | Feasibility | Innovation | Risk-Adj |")
    lines.append("|------|-------|-----------|-------|-------------|------------|----------|")
    for cand in ranking["candidates"]:
        lines.append(
            f"| {cand['rank']} | {cand['agent']} | {cand['composite_score']:.4f} | "
            f"{cand['scientific_rigor']:.2f} | {cand['feasibility']:.2f} | "
            f"{cand['innovation']:.2f} | {cand['risk_adjusted_confidence']:.2f} |"
        )
    lines.append("")
    lines.append(f"**Tie-break applied:** {ranking['tie_break_applied']} (mode: {ranking['tie_break_mode']})")
    lines.append(f"**Delta top-two:** {ranking['score_delta_top_two']:.4f}")
    lines.append("")
    lines.append("## Rationale")
    lines.append(ranking.get("rationale", ""))
    if ranking.get("dissenting_notes"):
        lines.append("")
        lines.append("## Dissenting Notes")
        lines.append(ranking["dissenting_notes"])
    if ranking.get("merged_recommendations"):
        lines.append("")
        lines.append("## Merged Recommendations (from runners-up)")
        for rec in ranking["merged_recommendations"]:
            lines.append(f"- {rec}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrate a hypothesis debate for BY design campaigns."
    )
    parser.add_argument("--research-dir", required=True, type=Path)
    parser.add_argument("--campaign-config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--num-agents", type=int, default=3, choices=[2, 3, 4])
    parser.add_argument("--tie-break", default="merge", choices=TIE_BREAK_MODES)
    parser.add_argument("--reflection-temperature", type=float, default=0.2)
    parser.add_argument("--rubric-preset", default="balanced", choices=list(DEFAULT_WEIGHTS))
    args = parser.parse_args()

    config = DebateConfig(
        research_dir=args.research_dir,
        campaign_config=args.campaign_config,
        output_dir=args.output_dir,
        num_agents=args.num_agents,
        tie_break=args.tie_break,
        reflection_temperature=args.reflection_temperature,
        rubric_preset=args.rubric_preset,
    )

    _log_event(config, "debate_started", research_dir=str(config.research_dir))
    print(f"✓ Loaded research from {config.research_dir}")

    research = load_research_bundle(config.research_dir)
    campaign_config = load_campaign_config(config.campaign_config)

    paths = spawn_hypothesis_agents(config, research, campaign_config)
    print(f"✓ Collected {len(paths)}/{config.num_agents} proposals")

    proposals = validate_proposals(paths, config)
    if len(proposals) < 2:
        print(f"✗ Fewer than 2 valid proposals ({len(proposals)}). Cannot rank.", file=sys.stderr)
        return 2
    print(f"✓ Validated {len(proposals)} proposals against schema")

    ranking = rank_proposals(proposals, research, config)
    print(f"✓ Ranking complete: winner={ranking['winner']}, composite={ranking['candidates'][0]['composite_score']:.4f}")

    write_outputs(config, proposals, ranking, campaign_config)
    print(f"✓ Updated {config.campaign_config}")

    _log_event(config, "debate_completed")
    print(f"✓ Debate written to {config.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
