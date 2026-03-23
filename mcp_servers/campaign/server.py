"""Campaign State MCP Server — local campaign lifecycle management for Proteus agent."""
from __future__ import annotations

import fcntl
import json
import sys
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Generator

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Import campaign state machine from src/proteus_cli/campaign/
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from proteus_cli.campaign.config import CampaignConfig, TargetConfig, DesignConfig
from proteus_cli.campaign.cost import CostEstimate, estimate_cost
from proteus_cli.campaign.state import (
    CampaignState,
    RoundState,
    RunState,
    add_round,
    create_campaign,
    load_campaign,
    save_campaign,
    transition,
    update_run,
)

mcp = FastMCP("proteus-campaign")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_FILENAME = "campaign_log.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        state = load_campaign(str(log))
        yield state, log
        save_campaign(state, str(log))
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

    # Build a minimal CampaignConfig for the state machine.
    config = CampaignConfig(
        name=target_name.strip().lower().replace(" ", "-"),
        tier=tier,
        target=TargetConfig(name=target_name.strip(), pdb_id="", chain_id=""),
        design=DesignConfig(tool=tool.strip(), protocol=protocol),
    )

    try:
        state = create_campaign(config, base_dir=base_dir)
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
        state = load_campaign(str(log))
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
            transition(state, new_status, reason)
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
            new_round = add_round(state, parameters)
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
    if status:
        updates["status"] = status
    if designs_generated:
        updates["designs_generated"] = designs_generated
    if designs_passed:
        updates["designs_passed"] = designs_passed
    if top_iptm:
        updates["top_iptm"] = top_iptm
    if top_ipsae:
        updates["top_ipsae"] = top_ipsae

    try:
        with _locked_campaign(campaign_dir) as (state, log):
            run = update_run(state, round_id, run_id, **updates)
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

    try:
        # If existing scores file, merge (append).
        existing: list[dict] = []
        if scores_file.exists():
            existing = json.loads(scores_file.read_text())

        existing.extend(scores)

        # Write with file lock for safety.
        with open(scores_file, "w") as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                fd.write(json.dumps(existing, indent=2))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)

        return json.dumps(
            {"num_scores_recorded": len(scores), "run_id": run_id},
            indent=2,
        )
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
        state = load_campaign(str(log))
    except Exception as exc:
        return _error(f"Failed to load campaign: {exc}")

    # Aggregate metrics across all rounds and runs.
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

    # Load score files for richer summary.
    scores_dir = Path(campaign_dir).resolve() / "screening"
    all_scores: list[dict] = []
    if scores_dir.exists():
        for score_file in scores_dir.glob("*_scores.json"):
            try:
                file_scores = json.loads(score_file.read_text())
                if isinstance(file_scores, list):
                    all_scores.extend(file_scores)
            except (json.JSONDecodeError, OSError):
                continue

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
        state = load_campaign(str(log))
    except Exception as exc:
        return _error(f"Failed to load campaign: {exc}")

    # Reconstruct a CampaignConfig from the state for cost estimation.
    # The state stores target and tool info; use defaults for the rest.
    target_info = state.target if isinstance(state.target, dict) else {}
    config = CampaignConfig(
        name=state.campaign_id,
        target=TargetConfig(
            name=target_info.get("name", ""),
            pdb_id=target_info.get("pdb_id", ""),
            chain_id=target_info.get("chain_id", ""),
            uniprot_id=target_info.get("uniprot_id"),
        ),
        design=DesignConfig(
            tool=state.tool,
            protocol=state.protocol,
        ),
    )

    try:
        estimate = estimate_cost(config)
        return json.dumps(asdict(estimate), indent=2)
    except Exception as exc:
        return _error(f"Failed to estimate cost: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
