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

from proteus_cli.campaign.active_learning import (
    has_enough_data,
    suggest_from_campaign,
)
from proteus_cli.campaign.config import CampaignConfig, TargetConfig, DesignConfig
from proteus_cli.campaign.cost import CostEstimate, estimate_cost
from proteus_cli.campaign.export import (
    export_campaign_summary,
    export_csv as export_csv_fn,
    export_fasta as export_fasta_fn,
)
from proteus_cli.campaign.decisions import log_decision, read_decisions
from proteus_cli.campaign.visualization import generate_chimerax_script, generate_pymol_script
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

    NOTE: The fcntl lock is advisory — it only prevents races between
    processes that also use ``_locked_campaign``.  Direct file writes that
    bypass this function will NOT be blocked by the lock.
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

    warning: str | None = None
    try:
        # If existing scores file, merge (append).
        existing: list[dict] = []
        if scores_file.exists():
            try:
                existing = json.loads(scores_file.read_text())
            except json.JSONDecodeError:
                # Corrupted file — preserve it and start fresh
                corrupted_path = scores_file.with_suffix(".corrupted")
                scores_file.rename(corrupted_path)
                warning = (
                    f"Existing scores file was corrupted JSON. "
                    f"Renamed to {corrupted_path.name} and started fresh."
                )

        existing.extend(scores)

        # Write with file lock for safety.
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
        path = export_fasta_fn(campaign_dir, output_path)
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
        path = export_csv_fn(campaign_dir, output_path)
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
        log_decision(
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
        decisions = read_decisions(campaign_dir)
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
            script = generate_chimerax_script(
                structure_path=structure_path,
                design_chains=d_chains,
                target_chains=t_chains,
                hotspot_residues=hotspots,
                output_path=out,
            )
        elif fmt == "pymol":
            script = generate_pymol_script(
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
        result = suggest_from_campaign(campaign_dir, min_designs=min_designs)
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
