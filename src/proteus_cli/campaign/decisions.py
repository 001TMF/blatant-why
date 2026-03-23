"""Decision logging for campaign audit trail."""
from __future__ import annotations

import fcntl
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path


def log_decision(
    campaign_dir: str,
    agent: str,
    decision: str,
    reasoning: str,
    alternatives: list[str] | None = None,
    confidence: str = "high",
) -> None:
    """Append a decision to the campaign decision log.

    Args:
        campaign_dir: Path to the campaign directory.
        agent: Name of the agent making the decision.
        decision: Short description of what was decided.
        reasoning: Explanation of why this decision was made.
        alternatives: Other options that were considered.
        confidence: Confidence level — "high", "medium", or "low".
    """
    log_path = Path(campaign_dir) / "decision_log.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "decision": decision,
        "reasoning": reasoning,
        "alternatives": alternatives or [],
        "confidence": confidence,
    }
    with open(log_path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_decisions(campaign_dir: str) -> list[dict]:
    """Read all decisions from the log.

    Args:
        campaign_dir: Path to the campaign directory.

    Returns:
        List of decision entries, each a dict with timestamp, agent,
        decision, reasoning, alternatives, and confidence.
    """
    log_path = Path(campaign_dir) / "decision_log.jsonl"
    if not log_path.exists():
        return []
    decisions = []
    for line_num, line in enumerate(log_path.read_text().splitlines(), 1):
        if line.strip():
            try:
                decisions.append(json.loads(line))
            except json.JSONDecodeError:
                warnings.warn(
                    f"Corrupted decision log entry at line {line_num} in "
                    f"{log_path}, skipping."
                )
    return decisions
