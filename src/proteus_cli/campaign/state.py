"""Campaign state machine with JSON persistence."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CampaignConfig

# Valid campaign statuses and allowed transitions.
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["configured"],
    "configured": ["debating", "planned", "designing"],
    "debating": ["planned", "designing", "failed"],
    "planned": ["designing", "failed"],  # plan approved, ready to execute
    "designing": ["screening", "failed"],
    "failed": ["draft", "closed"],
    "screening": ["ranked", "failed"],
    "ranked": ["lab_pending", "designing", "closed"],
    "lab_pending": ["lab_submitted", "failed"],
    "lab_submitted": ["lab_complete", "failed"],
    "lab_complete": ["iterated", "closed", "failed"],
    "iterated": ["designing", "closed"],
}


@dataclass
class RunState:
    """State of a single design run within a round."""
    run_id: str = ""
    scaffold: str = ""
    status: str = "pending"
    designs_requested: int = 0
    designs_generated: int = 0
    designs_passed: int = 0
    top_iptm: float = 0.0
    top_ipsae: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    output_dir: str | None = None


@dataclass
class RoundState:
    """State of a design-screen-rank round."""
    round_id: int = 0
    state: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    runs: list[RunState] = field(default_factory=list)
    screening: dict[str, Any] | None = None
    ranking: dict[str, Any] | None = None


@dataclass
class CampaignState:
    """Top-level campaign state persisted as campaign_log.json."""
    campaign_id: str = ""
    target: dict[str, Any] = field(default_factory=dict)
    tool: str = ""
    protocol: str = ""
    status: str = "draft"
    plan_approved: bool = False
    lab_approved: bool = False
    rounds: list[RoundState] = field(default_factory=list)
    costs: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    iteration: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_cmd_output(cmd: str) -> str:
    """Run a shell command and return its stdout, or 'not found' on failure."""
    try:
        return subprocess.run(
            cmd.split(), capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        return "not found"


def _capture_environment() -> dict:
    """Capture environment snapshot for reproducibility."""
    env = {
        "python_version": platform.python_version(),
        "node_version": _get_cmd_output("node --version"),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Tool versions
    for tool, cmd in [
        ("boltzgen", "boltzgen --version"),
        ("protenix", "protenix --version"),
        ("pxdesign", "pxdesign --version"),
    ]:
        env[f"{tool}_version"] = _get_cmd_output(cmd)
    # API keys (just whether set, not values)
        env[f"{key}_set"] = bool(os.getenv(key))
    return env


def create_campaign(
    config: CampaignConfig,
    base_dir: str = "campaigns",
) -> CampaignState:
    """Initialize a new campaign: create directories and write initial state."""
    campaign_id = f"{config.name}-{uuid.uuid4().hex[:8]}"
    campaign_dir = Path(base_dir) / campaign_id

    # Create directory structure.
    for sub in ("designs", "predictions", "screening", "lab"):
        (campaign_dir / sub).mkdir(parents=True, exist_ok=True)

    now = _now()
    state = CampaignState(
        campaign_id=campaign_id,
        target={
            "name": config.target.name,
            "pdb_id": config.target.pdb_id,
            "chain_id": config.target.chain_id,
            "uniprot_id": config.target.uniprot_id,
        },
        tool=config.design.tool,
        protocol=config.design.protocol,
        status="draft",
        lab_approved=False,
        rounds=[],
        costs={},
        created_at=now,
        updated_at=now,
        iteration=0,
        history=[{
            "timestamp": now,
            "from_status": None,
            "to_status": "draft",
            "reason": "Campaign created",
        }],
        environment=_capture_environment(),
    )

    save_campaign(state, str(campaign_dir / "campaign_log.json"))
    return state


def load_campaign(path: str) -> CampaignState:
    """Read campaign_log.json and return a CampaignState."""
    raw = json.loads(Path(path).read_text())

    rounds = []
    for r in raw.get("rounds", []):
        runs = [RunState(**run) for run in r.pop("runs", [])]
        rounds.append(RoundState(**r, runs=runs))

    raw.pop("rounds", None)
    return CampaignState(**raw, rounds=rounds)


def save_campaign(state: CampaignState, path: str) -> None:
    """Write a CampaignState to campaign_log.json."""
    data = asdict(state)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2))


def transition(
    state: CampaignState,
    new_status: str,
    reason: str,
) -> CampaignState:
    """Advance the campaign to a new status, enforcing valid transitions."""
    allowed = VALID_TRANSITIONS.get(state.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {state.status!r} -> {new_status!r}. "
            f"Allowed: {allowed}"
        )

    now = _now()
    state.history.append({
        "timestamp": now,
        "from_status": state.status,
        "to_status": new_status,
        "reason": reason,
    })
    state.status = new_status
    state.updated_at = now
    return state


def add_round(
    state: CampaignState,
    parameters: dict[str, Any],
) -> RoundState:
    """Append a new round to the campaign and return it."""
    round_id = len(state.rounds) + 1
    now = _now()
    new_round = RoundState(
        round_id=round_id,
        state="pending",
        started_at=now,
        parameters=parameters,
    )
    state.rounds.append(new_round)
    state.updated_at = now
    return new_round


def update_run(
    state: CampaignState,
    round_id: int,
    run_id: str,
    **updates: Any,
) -> RunState:
    """Update fields on a specific run within a round."""
    target_round: RoundState | None = None
    for r in state.rounds:
        if r.round_id == round_id:
            target_round = r
            break
    if target_round is None:
        raise ValueError(f"Round {round_id} not found in campaign {state.campaign_id}")

    target_run: RunState | None = None
    for run in target_round.runs:
        if run.run_id == run_id:
            target_run = run
            break
    if target_run is None:
        raise ValueError(
            f"Run {run_id!r} not found in round {round_id} "
            f"of campaign {state.campaign_id}"
        )

    for key, value in updates.items():
        if not hasattr(target_run, key):
            raise ValueError(f"RunState has no field {key!r}")
        setattr(target_run, key, value)

    state.updated_at = _now()
    return target_run
