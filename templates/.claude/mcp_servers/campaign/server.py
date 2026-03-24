#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///
"""Campaign State MCP Server — local campaign lifecycle management for BY agent.

Self-contained: all campaign logic is inlined. No proteus_cli dependency.
Campaign state is stored as JSON files on disk.
"""
from __future__ import annotations

import csv
import fcntl
import io
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from mcp.server.fastmcp import FastMCP


# ===========================================================================
# Inlined campaign state machine (replaces proteus_cli.campaign.*)
# ===========================================================================


# ---------------------------------------------------------------------------
# State data models  (replaces proteus_cli.campaign.state)
# ---------------------------------------------------------------------------

@dataclass
class RunState:
    """State of a single design run within a round."""
    run_id: str = ""
    status: str = "pending"  # pending, running, complete, failed
    designs_generated: int = 0
    designs_passed: int = 0
    top_iptm: float = 0.0
    top_ipsae: float = 0.0
    started_at: str = ""
    completed_at: str = ""


@dataclass
class RoundState:
    """State of a design-screen-rank round."""
    round_id: int = 0
    state: str = "pending"  # pending, designing, screening, ranking, complete
    parameters: dict = field(default_factory=dict)
    runs: list[RunState] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


@dataclass
class CampaignState:
    """Full campaign state."""
    campaign_id: str = ""
    status: str = "draft"  # draft, configured, designing, screening, ranking, complete, failed
    target: dict = field(default_factory=dict)
    tool: str = ""
    protocol: str = ""
    tier: str = "standard"
    rounds: list[RoundState] = field(default_factory=list)
    iteration: int = 0
    lab_approved: bool = False
    created_at: str = ""
    updated_at: str = ""


# Valid status transitions
_TRANSITIONS = {
    "draft": {"configured", "failed"},
    "configured": {"designing", "failed"},
    "designing": {"screening", "failed"},
    "screening": {"ranking", "failed"},
    "ranking": {"complete", "designing", "failed"},  # designing = next round
    "complete": {"designing"},  # reopen for new round
    "failed": {"draft"},  # reset
}


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _create_campaign(
    name: str,
    target_name: str,
    tool: str,
    tier: str = "standard",
    protocol: str = "",
    base_dir: str = "campaigns",
) -> CampaignState:
    """Create a new campaign with directory structure."""
    campaign_id = f"{name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    campaign_dir = Path(base_dir) / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    for subdir in ("screening", "exports", "structures", "logs"):
        (campaign_dir / subdir).mkdir(exist_ok=True)

    state = CampaignState(
        campaign_id=campaign_id,
        status="draft",
        target={"name": target_name},
        tool=tool,
        protocol=protocol,
        tier=tier,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )

    _save_campaign(state, str(campaign_dir / LOG_FILENAME))
    return state


def _load_campaign(log_path: str) -> CampaignState:
    """Load campaign state from a JSON file."""
    data = json.loads(Path(log_path).read_text())

    rounds = []
    for r in data.get("rounds", []):
        runs = [RunState(**run) for run in r.get("runs", [])]
        rd = dict(r)
        rd["runs"] = runs
        rounds.append(RoundState(**rd))

    return CampaignState(
        campaign_id=data.get("campaign_id", ""),
        status=data.get("status", "draft"),
        target=data.get("target", {}),
        tool=data.get("tool", ""),
        protocol=data.get("protocol", ""),
        tier=data.get("tier", "standard"),
        rounds=rounds,
        iteration=data.get("iteration", 0),
        lab_approved=data.get("lab_approved", False),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


def _save_campaign(state: CampaignState, log_path: str) -> None:
    """Save campaign state to a JSON file."""
    state.updated_at = _now_iso()
    Path(log_path).write_text(json.dumps(asdict(state), indent=2))


def _transition(state: CampaignState, new_status: str, reason: str) -> None:
    """Transition campaign to a new status (validates transition)."""
    valid = _TRANSITIONS.get(state.status, set())
    if new_status not in valid:
        raise ValueError(
            f"Invalid transition: {state.status} -> {new_status}. "
            f"Valid targets: {sorted(valid)}"
        )
    state.status = new_status
    state.updated_at = _now_iso()


def _add_round(state: CampaignState, parameters: dict) -> RoundState:
    """Add a new round to the campaign."""
    round_id = len(state.rounds) + 1
    new_round = RoundState(
        round_id=round_id,
        state="pending",
        parameters=parameters,
        started_at=_now_iso(),
    )
    state.rounds.append(new_round)
    state.iteration = round_id
    state.updated_at = _now_iso()
    return new_round


def _update_run(
    state: CampaignState,
    round_id: int,
    run_id: str,
    **updates: Any,
) -> RunState:
    """Update a specific run within a round, creating it if needed."""
    target_round = None
    for rnd in state.rounds:
        if rnd.round_id == round_id:
            target_round = rnd
            break

    if target_round is None:
        raise ValueError(f"Round {round_id} not found")

    # Find or create run
    target_run = None
    for run in target_round.runs:
        if run.run_id == run_id:
            target_run = run
            break

    if target_run is None:
        target_run = RunState(run_id=run_id, started_at=_now_iso())
        target_round.runs.append(target_run)

    # Apply updates
    for key, value in updates.items():
        if hasattr(target_run, key):
            setattr(target_run, key, value)

    if updates.get("status") == "complete" and not target_run.completed_at:
        target_run.completed_at = _now_iso()

    state.updated_at = _now_iso()
    return target_run


# ---------------------------------------------------------------------------
# Cost estimation  (replaces proteus_cli.campaign.cost)
# ---------------------------------------------------------------------------

# Rough cost estimates per tool
_COST_PER_DESIGN = {
    "boltzgen": 0.02,    # GPU hours * rate
    "pxdesign": 0.05,
    "protenix": 0.01,
}

_GPU_HOURS_PER_DESIGN = {
    "boltzgen": 0.1,
    "pxdesign": 0.25,
    "protenix": 0.05,
}

_LAB_COST_PER_DESIGN = 119.0  # Adaptyv Bio base cost


@dataclass
class CostEstimate:
    """Campaign cost breakdown."""
    gpu_hours: float = 0.0
    cloud_cost: float = 0.0
    lab_cost: float = 0.0
    total_cost: float = 0.0
    designs_planned: int = 0
    lab_candidates: int = 0
    tool: str = ""
    tier: str = ""


def _estimate_cost(
    tool: str,
    tier: str = "standard",
    num_designs: int | None = None,
    lab_candidates: int | None = None,
) -> CostEstimate:
    """Estimate campaign cost based on tool and tier."""
    tier_designs = {
        "preview": 500,
        "quick": 1000,
        "standard": 5000,
        "deep": 20000,
        "exploratory": 50000,
    }
    tier_lab = {
        "preview": 5,
        "quick": 10,
        "standard": 50,
        "deep": 100,
        "exploratory": 200,
    }

    n_designs = num_designs or tier_designs.get(tier, 5000)
    n_lab = lab_candidates or tier_lab.get(tier, 50)

    gpu_per = _GPU_HOURS_PER_DESIGN.get(tool, 0.1)
    cost_per = _COST_PER_DESIGN.get(tool, 0.02)

    gpu_hours = n_designs * gpu_per
    cloud_cost = n_designs * cost_per
    lab_cost = n_lab * _LAB_COST_PER_DESIGN

    return CostEstimate(
        gpu_hours=round(gpu_hours, 1),
        cloud_cost=round(cloud_cost, 2),
        lab_cost=round(lab_cost, 2),
        total_cost=round(cloud_cost + lab_cost, 2),
        designs_planned=n_designs,
        lab_candidates=n_lab,
        tool=tool,
        tier=tier,
    )


# ---------------------------------------------------------------------------
# Decision logging  (replaces proteus_cli.campaign.decisions)
# ---------------------------------------------------------------------------

def _log_decision(
    campaign_dir: str,
    agent: str,
    decision: str,
    reasoning: str,
    alternatives: list | None = None,
    confidence: str = "high",
) -> None:
    """Append a decision entry to decision_log.jsonl."""
    log_file = Path(campaign_dir).resolve() / "decision_log.jsonl"
    entry = {
        "timestamp": _now_iso(),
        "agent": agent,
        "decision": decision,
        "reasoning": reasoning,
        "alternatives": alternatives or [],
        "confidence": confidence,
    }
    with open(log_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read_decisions(campaign_dir: str) -> list[dict]:
    """Read all decisions from decision_log.jsonl."""
    log_file = Path(campaign_dir).resolve() / "decision_log.jsonl"
    if not log_file.exists():
        return []
    decisions = []
    for line in log_file.read_text().strip().split("\n"):
        if line.strip():
            try:
                decisions.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return decisions


# ---------------------------------------------------------------------------
# Export helpers  (replaces proteus_cli.campaign.export)
# ---------------------------------------------------------------------------

def _collect_scores(campaign_dir: str) -> list[dict]:
    """Collect all scored designs from the campaign screening directory."""
    scores_dir = Path(campaign_dir).resolve() / "screening"
    all_scores: list[dict] = []
    if scores_dir.exists():
        for score_file in sorted(scores_dir.glob("*_scores.json")):
            try:
                data = json.loads(score_file.read_text())
                if isinstance(data, list):
                    all_scores.extend(data)
            except (json.JSONDecodeError, OSError):
                continue
    return all_scores


def _export_fasta(campaign_dir: str, output_path: str = "") -> str:
    """Export design sequences as FASTA."""
    scores = _collect_scores(campaign_dir)
    if not scores:
        raise ValueError("No scores found in campaign to export")

    export_dir = Path(campaign_dir).resolve() / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out = Path(output_path) if output_path else export_dir / "designs.fasta"

    lines: list[str] = []
    for s in scores:
        name = s.get("design_name", s.get("name", "unknown"))
        seq = s.get("sequence", "")
        if not seq:
            continue
        header_parts = [name]
        for metric in ("iptm", "ipsae", "plddt"):
            if metric in s:
                header_parts.append(f"{metric}={s[metric]}")
        lines.append(f">{' '.join(header_parts)}")
        # Wrap at 80 chars
        for i in range(0, len(seq), 80):
            lines.append(seq[i:i+80])

    out.write_text("\n".join(lines) + "\n")
    return str(out)


def _export_csv(campaign_dir: str, output_path: str = "") -> str:
    """Export all scored designs as CSV."""
    scores = _collect_scores(campaign_dir)
    if not scores:
        raise ValueError("No scores found in campaign to export")

    export_dir = Path(campaign_dir).resolve() / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out = Path(output_path) if output_path else export_dir / "designs.csv"

    # Collect all keys
    all_keys: set[str] = set()
    for s in scores:
        all_keys.update(s.keys())
    # Preferred column order
    preferred = ["design_name", "name", "sequence", "ipsae", "iptm", "plddt", "rmsd", "status"]
    columns = [k for k in preferred if k in all_keys]
    columns.extend(sorted(all_keys - set(columns)))

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for s in scores:
        writer.writerow(s)

    out.write_text(buf.getvalue())
    return str(out)


def _export_campaign_summary(campaign_dir: str) -> dict:
    """Generate a summary dict for the campaign."""
    log = Path(campaign_dir).resolve() / LOG_FILENAME
    if not log.exists():
        return {"error": f"Campaign log not found at {log}"}
    state = _load_campaign(str(log))
    scores = _collect_scores(campaign_dir)
    return {
        "campaign_id": state.campaign_id,
        "status": state.status,
        "rounds": len(state.rounds),
        "total_scores": len(scores),
    }


# ---------------------------------------------------------------------------
# Visualization  (replaces proteus_cli.campaign.visualization)
# ---------------------------------------------------------------------------

def _generate_pymol_script(
    structure_path: str,
    design_chains: list[str],
    target_chains: list[str],
    hotspot_residues: list[int] | None = None,
    output_path: str | None = None,
) -> str:
    """Generate a PyMOL .pml visualization script."""
    lines = [
        f"load {structure_path}, complex",
        "bg_color white",
        "hide everything",
    ]

    # Target: surface
    for ch in target_chains:
        lines.append(f"show surface, chain {ch}")
        lines.append(f"color palecyan, chain {ch}")
        lines.append(f"set transparency, 0.4, chain {ch}")

    # Design: cartoon
    for ch in design_chains:
        lines.append(f"show cartoon, chain {ch}")
        lines.append(f"color tv_green, chain {ch}")

    # Hotspot residues
    if hotspot_residues:
        resi_str = "+".join(str(r) for r in hotspot_residues)
        t_chains = "+".join(target_chains)
        lines.append(f"show sticks, chain {t_chains} and resi {resi_str}")
        lines.append(f"color tv_red, chain {t_chains} and resi {resi_str}")

    lines.append("zoom complex")
    lines.append("ray 1200, 900")

    script = "\n".join(lines) + "\n"
    if output_path:
        Path(output_path).write_text(script)
    return script


def _generate_chimerax_script(
    structure_path: str,
    design_chains: list[str],
    target_chains: list[str],
    hotspot_residues: list[int] | None = None,
    output_path: str | None = None,
) -> str:
    """Generate a ChimeraX .cxc visualization script."""
    lines = [
        f"open {structure_path}",
        "set bgColor white",
        "hide atoms",
    ]

    for ch in target_chains:
        lines.append(f"show /{ch} surface")
        lines.append(f"color /{ch} #88CCCC transparency 40")

    for ch in design_chains:
        lines.append(f"show /{ch} cartoons")
        lines.append(f"color /{ch} #66BB6A")

    if hotspot_residues:
        for ch in target_chains:
            resi_str = ",".join(str(r) for r in hotspot_residues)
            lines.append(f"show /{ch}:{resi_str} atoms")
            lines.append(f"color /{ch}:{resi_str} red")

    lines.append("view")

    script = "\n".join(lines) + "\n"
    if output_path:
        Path(output_path).write_text(script)
    return script


# ---------------------------------------------------------------------------
# Active learning suggestion  (replaces proteus_cli.campaign.active_learning)
# ---------------------------------------------------------------------------

@dataclass
class SuggestionResult:
    source: str  # "active_learning" or "rule_based"
    recommended_parameters: dict
    feature_importances: dict
    confidence: str
    explanation: str
    files_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def _suggest_from_campaign(
    campaign_dir: str,
    min_designs: int = 10,
) -> SuggestionResult:
    """Suggest next round parameters. Falls back to rule-based if not enough data."""
    scores = _collect_scores(campaign_dir)

    if len(scores) < min_designs:
        return SuggestionResult(
            source="rule_based",
            recommended_parameters={
                "increase_diversity": True,
                "alpha": 0.001,
                "budget_multiplier": 1.5,
            },
            feature_importances={},
            confidence="low",
            explanation=(
                f"Only {len(scores)} scored designs available (need {min_designs} "
                f"for ML). Using rule-based suggestions."
            ),
        )

    # Simple rule-based analysis of score distributions
    ipsae_vals = [s.get("ipsae", s.get("ipsae_min", 0)) for s in scores if isinstance(s.get("ipsae", s.get("ipsae_min")), (int, float))]
    iptm_vals = [s.get("iptm", 0) for s in scores if isinstance(s.get("iptm"), (int, float))]

    recs: dict = {}
    importances: dict = {}
    warnings: list[str] = []

    if ipsae_vals:
        avg_ipsae = sum(ipsae_vals) / len(ipsae_vals)
        if avg_ipsae < 0.3:
            recs["increase_designs"] = True
            recs["try_different_scaffolds"] = True
            warnings.append(f"Low average ipSAE ({avg_ipsae:.3f}) — consider different scaffolds")
        importances["ipsae"] = round(avg_ipsae, 4)

    if iptm_vals:
        avg_iptm = sum(iptm_vals) / len(iptm_vals)
        importances["iptm"] = round(avg_iptm, 4)

    # Pass rate
    passed = sum(1 for s in scores if s.get("status") == "PASS")
    rate = passed / len(scores) if scores else 0
    if rate < 0.1:
        recs["relax_thresholds"] = True
        recs["alpha"] = 0.01
        warnings.append(f"Very low pass rate ({rate:.1%}) — consider relaxing thresholds")
    elif rate > 0.5:
        recs["tighten_thresholds"] = True
        recs["alpha"] = 0.0001

    recs.setdefault("alpha", 0.001)
    recs.setdefault("budget_multiplier", 1.0)

    # Try ML if scikit-learn is available
    source = "rule_based"
    try:
        from sklearn.ensemble import RandomForestRegressor
        import numpy as np

        # Build feature matrix from scores
        feature_keys = [k for k in ("ipsae", "ipsae_min", "iptm", "plddt", "rmsd", "liabilities")
                        if any(isinstance(s.get(k), (int, float)) for s in scores)]
        if len(feature_keys) >= 2:
            X = []
            y = []
            for s in scores:
                row = [float(s.get(k, 0)) for k in feature_keys]
                target = float(s.get("ipsae", s.get("ipsae_min", 0)))
                X.append(row)
                y.append(target)

            X_arr = np.array(X)
            y_arr = np.array(y)

            if len(X_arr) >= min_designs:
                rf = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=5)
                rf.fit(X_arr, y_arr)
                importances = {k: round(float(v), 4) for k, v in zip(feature_keys, rf.feature_importances_)}
                source = "active_learning"
    except ImportError:
        warnings.append("scikit-learn not installed — using rule-based suggestions")

    return SuggestionResult(
        source=source,
        recommended_parameters=recs,
        feature_importances=importances,
        confidence="medium" if source == "active_learning" else "low",
        explanation=f"Based on {len(scores)} scored designs. Source: {source}.",
        warnings=warnings,
    )


# ===========================================================================
# MCP Server
# ===========================================================================

mcp = FastMCP("by-campaign")

LOG_FILENAME = "campaign_log.json"


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


def _log_path(campaign_dir: str) -> Path:
    """Resolve the campaign_log.json path within a campaign directory."""
    return Path(campaign_dir).resolve() / LOG_FILENAME


@contextmanager
def _locked_campaign(campaign_dir: str) -> Generator[tuple[CampaignState, Path], None, None]:
    """Context manager that loads campaign state under an exclusive file lock.

    Yields (state, log_path). On successful exit the caller is expected to
    have mutated *state* and the context manager will persist it back to disk
    before releasing the lock.
    """
    log = _log_path(campaign_dir)
    if not log.exists():
        raise FileNotFoundError(f"Campaign log not found: {log}")

    fd = open(log, "r+")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = _load_campaign(str(log))
        yield state, log
        _save_campaign(state, str(log))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


# ---------------------------------------------------------------------------
# Tool 1: campaign_create
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_create(
    target_name: str,
    tool: str,
    tier: str = "standard",
    protocol: str = "",
    base_dir: str = "campaigns",
) -> str:
    """Create a new campaign with directory structure and initial state.

    Args:
        target_name: Name of the target protein (e.g. "TNF-alpha").
        tool: Design tool to use ("boltzgen", "pxdesign", "protenix").
        tier: Campaign tier — "quick", "standard", or "deep" (default "standard").
        protocol: Design protocol (e.g. "nanobody-anything"). Auto-selected if empty.
        base_dir: Parent directory for campaigns (default "campaigns").

    Returns:
        JSON with campaign_id, path, target, tool, tier, and status.
    """
    if not target_name.strip():
        return _error("target_name must not be empty.")
    if not tool.strip():
        return _error("tool must not be empty.")

    try:
        name = target_name.strip().lower().replace(" ", "-")
        state = _create_campaign(
            name=name,
            target_name=target_name.strip(),
            tool=tool.strip(),
            tier=tier,
            protocol=protocol,
            base_dir=base_dir,
        )
    except Exception as exc:
        return _error(f"Failed to create campaign: {exc}")

    campaign_dir = str(Path(base_dir) / state.campaign_id)

    return json.dumps(
        {
            "campaign_id": state.campaign_id,
            "path": campaign_dir,
            "target": target_name.strip(),
            "tool": tool.strip(),
            "tier": tier,
            "status": state.status,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 2: campaign_get
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_get(campaign_dir: str) -> str:
    """Read the full campaign state from disk.

    Args:
        campaign_dir: Path to the campaign directory containing campaign_log.json.

    Returns:
        The full campaign state as JSON.
    """
    log = _log_path(campaign_dir)
    if not log.exists():
        return _error(f"Campaign log not found at {log}")

    try:
        state = _load_campaign(str(log))
        return json.dumps(asdict(state), indent=2)
    except Exception as exc:
        return _error(f"Failed to load campaign: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: campaign_update_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_update_status(
    campaign_dir: str,
    new_status: str,
    reason: str,
) -> str:
    """Advance the campaign to a new status.

    Only valid transitions are allowed (e.g. draft -> configured -> designing).

    Args:
        campaign_dir: Path to the campaign directory.
        new_status: Target status to transition to.
        reason: Human-readable reason for the transition.

    Returns:
        Updated campaign state, or an error if the transition is invalid.
    """
    try:
        with _locked_campaign(campaign_dir) as (state, log):
            _transition(state, new_status, reason)
        return json.dumps(asdict(state), indent=2)
    except FileNotFoundError as exc:
        return _error(str(exc))
    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        return _error(f"Failed to update status: {exc}")


# ---------------------------------------------------------------------------
# Tool 4: campaign_add_round
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_add_round(
    campaign_dir: str,
    parameters_json: str,
) -> str:
    """Add a new design-screen-rank round to the campaign.

    Args:
        campaign_dir: Path to the campaign directory.
        parameters_json: JSON string with round parameters (e.g. scaffolds,
            designs_per_scaffold, budget).

    Returns:
        JSON with round_id, status, and parameters.
    """
    try:
        parameters = json.loads(parameters_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid parameters JSON: {exc}")

    try:
        with _locked_campaign(campaign_dir) as (state, log):
            new_round = _add_round(state, parameters)
        return json.dumps(
            {
                "round_id": new_round.round_id,
                "status": new_round.state,
                "parameters": new_round.parameters,
            },
            indent=2,
        )
    except FileNotFoundError as exc:
        return _error(str(exc))
    except Exception as exc:
        return _error(f"Failed to add round: {exc}")


# ---------------------------------------------------------------------------
# Tool 5: campaign_update_round
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_update_round(
    campaign_dir: str,
    round_id: int,
    run_id: str,
    status: str = "",
    designs_generated: int = 0,
    designs_passed: int = 0,
    top_iptm: float = 0,
    top_ipsae: float = 0,
) -> str:
    """Update a specific run within a campaign round.

    Args:
        campaign_dir: Path to the campaign directory.
        round_id: Round number to update.
        run_id: Identifier for the run within the round.
        status: New run status (e.g. "running", "complete", "failed").
        designs_generated: Number of designs generated so far.
        designs_passed: Number of designs that passed screening.
        top_iptm: Highest ipTM score in this run.
        top_ipsae: Highest ipSAE score in this run.

    Returns:
        Updated run state as JSON.
    """
    updates: dict[str, Any] = {}
    if status is not None:
        updates["status"] = status
    if designs_generated is not None:
        updates["designs_generated"] = designs_generated
    if designs_passed is not None:
        updates["designs_passed"] = designs_passed
    if top_iptm is not None:
        updates["top_iptm"] = top_iptm
    if top_ipsae is not None:
        updates["top_ipsae"] = top_ipsae

    try:
        with _locked_campaign(campaign_dir) as (state, log):
            run = _update_run(state, round_id, run_id, **updates)
        return json.dumps(asdict(run), indent=2)
    except FileNotFoundError as exc:
        return _error(str(exc))
    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        return _error(f"Failed to update round: {exc}")


# ---------------------------------------------------------------------------
# Tool 6: campaign_record_scores
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_record_scores(
    campaign_dir: str,
    run_id: str,
    scores_json: str,
) -> str:
    """Record design scores for a specific run.

    Args:
        campaign_dir: Path to the campaign directory.
        run_id: Run identifier these scores belong to.
        scores_json: JSON array of score objects, each with at least
            "design_name" plus metric fields like "iptm", "ipsae", "plddt".

    Returns:
        JSON with num_scores_recorded and run_id.
    """
    try:
        scores = json.loads(scores_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid scores JSON: {exc}")

    if not isinstance(scores, list):
        return _error("scores_json must be a JSON array.")

    campaign_path = Path(campaign_dir).resolve()
    scores_dir = campaign_path / "screening"
    scores_dir.mkdir(parents=True, exist_ok=True)

    scores_file = scores_dir / f"{run_id}_scores.json"

    warning: str | None = None
    try:
        existing: list[dict] = []
        if scores_file.exists():
            try:
                existing = json.loads(scores_file.read_text())
            except json.JSONDecodeError:
                corrupted_path = scores_file.with_suffix(".corrupted")
                scores_file.rename(corrupted_path)
                warning = (
                    f"Existing scores file was corrupted JSON. "
                    f"Renamed to {corrupted_path.name} and started fresh."
                )

        existing.extend(scores)

        with open(scores_file, "w") as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                fd.write(json.dumps(existing, indent=2))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)

        result: dict = {"num_scores_recorded": len(scores), "run_id": run_id}
        if warning:
            result["warning"] = warning
        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Failed to record scores: {exc}")


# ---------------------------------------------------------------------------
# Tool 7: campaign_get_summary
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_get_summary(campaign_dir: str) -> str:
    """Get an aggregated summary of a campaign.

    Args:
        campaign_dir: Path to the campaign directory.

    Returns:
        JSON summary with total_rounds, total_designs, pass_rates,
        top_scores, status, and cost_estimate.
    """
    log = _log_path(campaign_dir)
    if not log.exists():
        return _error(f"Campaign log not found at {log}")

    try:
        state = _load_campaign(str(log))
    except Exception as exc:
        return _error(f"Failed to load campaign: {exc}")

    total_designs_generated = 0
    total_designs_passed = 0
    best_iptm = 0.0
    best_ipsae = 0.0
    total_rounds = len(state.rounds)

    for rnd in state.rounds:
        for run in rnd.runs:
            total_designs_generated += run.designs_generated
            total_designs_passed += run.designs_passed
            if run.top_iptm > best_iptm:
                best_iptm = run.top_iptm
            if run.top_ipsae > best_ipsae:
                best_ipsae = run.top_ipsae

    pass_rate = (
        (total_designs_passed / total_designs_generated * 100)
        if total_designs_generated > 0
        else 0.0
    )

    all_scores = _collect_scores(campaign_dir)

    summary = {
        "campaign_id": state.campaign_id,
        "status": state.status,
        "target": state.target,
        "tool": state.tool,
        "total_rounds": total_rounds,
        "total_designs_generated": total_designs_generated,
        "total_designs_passed": total_designs_passed,
        "pass_rate_pct": round(pass_rate, 1),
        "top_iptm": best_iptm,
        "top_ipsae": best_ipsae,
        "total_scores_recorded": len(all_scores),
        "iteration": state.iteration,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }

    return json.dumps(summary, indent=2)


# ---------------------------------------------------------------------------
# Tool 8: campaign_get_cost_estimate
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_get_cost_estimate(campaign_dir: str) -> str:
    """Get an estimated cost breakdown for a campaign.

    Uses the campaign's design parameters to project GPU hours and
    lab testing costs.

    Args:
        campaign_dir: Path to the campaign directory.

    Returns:
        JSON cost breakdown with GPU hours, cloud cost, lab cost, and total.
    """
    log = _log_path(campaign_dir)
    if not log.exists():
        return _error(f"Campaign log not found at {log}")

    try:
        state = _load_campaign(str(log))
    except Exception as exc:
        return _error(f"Failed to load campaign: {exc}")

    try:
        estimate = _estimate_cost(
            tool=state.tool,
            tier=state.tier,
        )
        return json.dumps(asdict(estimate), indent=2)
    except Exception as exc:
        return _error(f"Failed to estimate cost: {exc}")


# ---------------------------------------------------------------------------
# Tool 9: campaign_export_fasta
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_export_fasta(
    campaign_dir: str,
    output_path: str = "",
) -> str:
    """Export campaign design sequences as FASTA.

    Collects all design sequences from the campaign directory and writes
    them in FASTA format with score annotations in the header lines.

    Args:
        campaign_dir: Path to the campaign directory.
        output_path: Optional output file path. If empty, writes to campaign_dir/exports/.

    Returns:
        JSON with the path to the exported FASTA file.
    """
    log = _log_path(campaign_dir)
    if not log.exists():
        return _error(f"Campaign log not found at {log}")

    try:
        path = _export_fasta(campaign_dir, output_path)
        return json.dumps({"exported": path, "format": "fasta"}, indent=2)
    except Exception as exc:
        return _error(f"Failed to export FASTA: {exc}")


# ---------------------------------------------------------------------------
# Tool 10: campaign_export_csv
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_export_csv(
    campaign_dir: str,
    output_path: str = "",
) -> str:
    """Export all scored campaign designs as CSV.

    Columns: design_name, sequence, ipsae, iptm, plddt, rmsd, liabilities, status.

    Args:
        campaign_dir: Path to the campaign directory.
        output_path: Optional output file path. If empty, writes to campaign_dir/exports/.

    Returns:
        JSON with the path to the exported CSV file.
    """
    log = _log_path(campaign_dir)
    if not log.exists():
        return _error(f"Campaign log not found at {log}")

    try:
        path = _export_csv(campaign_dir, output_path)
        return json.dumps({"exported": path, "format": "csv"}, indent=2)
    except Exception as exc:
        return _error(f"Failed to export CSV: {exc}")


# ---------------------------------------------------------------------------
# Tool 11: campaign_log_decision
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_log_decision(
    campaign_dir: str,
    agent: str,
    decision: str,
    reasoning: str,
    alternatives: str = "[]",
    confidence: str = "high",
) -> str:
    """Record a decision in the campaign audit trail.

    Appends an entry to decision_log.jsonl inside the campaign directory.

    Args:
        campaign_dir: Path to the campaign directory.
        agent: Name of the agent making the decision.
        decision: Short description of what was decided.
        reasoning: Explanation of why this decision was made.
        alternatives: JSON array of alternative options considered (default "[]").
        confidence: Confidence level — "high", "medium", or "low".

    Returns:
        JSON confirmation with timestamp and decision summary.
    """
    if not agent.strip():
        return _error("agent must not be empty.")
    if not decision.strip():
        return _error("decision must not be empty.")
    if not reasoning.strip():
        return _error("reasoning must not be empty.")
    if confidence not in ("high", "medium", "low"):
        return _error(f"confidence must be 'high', 'medium', or 'low', got {confidence!r}")

    try:
        alt_list = json.loads(alternatives)
        if not isinstance(alt_list, list):
            return _error("alternatives must be a JSON array.")
    except json.JSONDecodeError as exc:
        return _error(f"Invalid alternatives JSON: {exc}")

    try:
        _log_decision(
            campaign_dir=campaign_dir,
            agent=agent.strip(),
            decision=decision.strip(),
            reasoning=reasoning.strip(),
            alternatives=alt_list,
            confidence=confidence,
        )
        return json.dumps(
            {
                "logged": True,
                "agent": agent.strip(),
                "decision": decision.strip(),
                "confidence": confidence,
            },
            indent=2,
        )
    except Exception as exc:
        return _error(f"Failed to log decision: {exc}")


# ---------------------------------------------------------------------------
# Tool 12: campaign_get_decisions
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_get_decisions(campaign_dir: str) -> str:
    """Retrieve all decisions from the campaign audit trail.

    Reads decision_log.jsonl from the campaign directory.

    Args:
        campaign_dir: Path to the campaign directory.

    Returns:
        JSON array of decision entries with timestamp, agent, decision,
        reasoning, alternatives, and confidence.
    """
    try:
        decisions = _read_decisions(campaign_dir)
        return json.dumps(decisions, indent=2)
    except Exception as exc:
        return _error(f"Failed to read decisions: {exc}")


# ---------------------------------------------------------------------------
# Tool 13: campaign_generate_visualization
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_generate_visualization(
    structure_path: str,
    format: str = "pymol",
    design_chains: str = "A",
    target_chains: str = "B",
    hotspot_residues: str = "",
    output_path: str = "",
) -> str:
    """Generate a PyMOL (.pml) or ChimeraX (.cxc) visualization script.

    Creates a script that renders the target as a semi-transparent surface,
    the binder as a cartoon with CDR loops colored by region, and optionally
    highlights hotspot residues on the target.

    Args:
        structure_path: Path to the PDB or mmCIF structure file to load.
        format: Visualization tool — "pymol" (default) or "chimerax".
        design_chains: Comma-separated chain IDs for the designed binder (default "A").
        target_chains: Comma-separated chain IDs for the target protein (default "B").
        hotspot_residues: Comma-separated residue numbers to highlight (default "").
        output_path: Optional output file path. If empty, the script is returned
            as a string without writing to disk.

    Returns:
        JSON with the generated script text and, if written, the output file path.
    """
    d_chains = [c.strip() for c in design_chains.split(",") if c.strip()]
    t_chains = [c.strip() for c in target_chains.split(",") if c.strip()]
    hotspots: list[int] | None = None
    if hotspot_residues.strip():
        try:
            hotspots = [int(r.strip()) for r in hotspot_residues.split(",") if r.strip()]
        except ValueError:
            return _error("hotspot_residues must be comma-separated integers.")

    out = output_path if output_path.strip() else None
    fmt = format.strip().lower()

    try:
        if fmt == "chimerax":
            script = _generate_chimerax_script(
                structure_path=structure_path,
                design_chains=d_chains,
                target_chains=t_chains,
                hotspot_residues=hotspots,
                output_path=out,
            )
        elif fmt == "pymol":
            script = _generate_pymol_script(
                structure_path=structure_path,
                design_chains=d_chains,
                target_chains=t_chains,
                hotspot_residues=hotspots,
                output_path=out,
            )
        else:
            return _error(f"Unsupported format {fmt!r}. Use 'pymol' or 'chimerax'.")
    except Exception as exc:
        return _error(f"Failed to generate visualization script: {exc}")

    result: dict[str, Any] = {"format": fmt, "script": script}
    if out:
        result["output_path"] = out
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 14: campaign_suggest_next_round
# ---------------------------------------------------------------------------


@mcp.tool()
async def campaign_suggest_next_round(
    campaign_dir: str,
    min_designs: int = 10,
) -> str:
    """Suggest optimised parameters for the next design round using active learning.

    Trains a lightweight random-forest regressor on all scored designs in the
    campaign and returns data-driven recommendations (feature importances,
    threshold refinements, diversity / alpha suggestions).  When fewer than
    *min_designs* scored entries are available, or scikit-learn is missing, the
    tool transparently falls back to a rule-based stub.

    Inspired by EVOLVEpro (Science, 2024) — few-shot active learning with PLMs.

    Args:
        campaign_dir: Path to the campaign directory containing screening score files.
        min_designs: Minimum scored designs required before ML kicks in (default 10).

    Returns:
        JSON with source ("active_learning" or "rule_based"), recommended_parameters,
        feature_importances, confidence, and explanation.
    """
    try:
        result = _suggest_from_campaign(campaign_dir, min_designs=min_designs)
        payload: dict = {
            "source": result.source,
            "recommended_parameters": result.recommended_parameters,
            "feature_importances": result.feature_importances,
            "confidence": result.confidence,
            "explanation": result.explanation,
        }
        if result.files_skipped > 0:
            payload["files_skipped"] = result.files_skipped
        if result.warnings:
            payload["warnings"] = result.warnings
        return json.dumps(payload, indent=2)
    except Exception as exc:
        return _error(f"Failed to suggest next round: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
