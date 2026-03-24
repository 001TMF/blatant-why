#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx",
# ]
# ///
"""Adaptyv Bio MCP Server — Lab submission tools with triple-layer safety gate.

This is the MOST SECURITY-SENSITIVE component of the BY agent.
It sends real sequences to a physical lab for synthesis and testing.

Safety architecture:
  Layer 1 — Two-step tool design (prepare + confirm, cannot combine)
  Layer 2 — Approval file check (written by TUI, not by Claude)
  Layer 3 — Module-level pending dict with 5-minute TTL
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("by-adaptyv")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADAPTYV_BASE_URL = os.environ.get(
    "ADAPTYV_BASE_URL", "https://api.adaptyvbio.com/v1"
)
TIMEOUT = 30.0
VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
MAX_SEQUENCES_PER_PLATE = 96
CONFIRMATION_TTL = 300.0  # 5 minutes
APPROVAL_TTL = 3600.0  # 1 hour

# Pricing tiers (per sequence, USD)
PRICING_TIERS = [
    (10, 215),   # 1-10 sequences: $215 each
    (50, 175),   # 11-50 sequences: $175 each
    (96, 119),   # 51-96 sequences: $119 each
]


# ---------------------------------------------------------------------------
# Pending submission storage (Layer 3)
# ---------------------------------------------------------------------------


@dataclass
class PendingSubmission:
    code: str
    payload: dict
    created_at: float
    ttl: float = 300.0

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


# Module-level storage -- NOT accessible to Claude agent
_pending: dict[str, PendingSubmission] = {}


def _generate_code() -> str:
    """Generate a cryptographically random confirmation code."""
    return f"BY-{secrets.token_hex(3).upper()}"


def _cleanup_expired():
    """Remove all expired pending submissions."""
    expired = [k for k, v in _pending.items() if v.expired]
    for k in expired:
        del _pending[k]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


def _log(msg: str) -> None:
    """Log to stderr for audit trail."""
    print(f"[adaptyv] {msg}", file=sys.stderr, flush=True)


def _get_api_token() -> str | None:
    """Read the API token from the environment."""
    return os.environ.get("ADAPTYV_API_TOKEN")


def _compute_cost(num_sequences: int) -> tuple[float, float]:
    """Compute cost per sequence and total cost.

    Returns:
        (cost_per_sequence, total_cost_usd)
    """
    if num_sequences <= 0:
        return (0.0, 0.0)
    cost_per = 215.0  # default to highest tier
    for tier_max, tier_price in PRICING_TIERS:
        if num_sequences <= tier_max:
            cost_per = float(tier_price)
            break
    else:
        # More than the last tier threshold — use lowest price
        cost_per = float(PRICING_TIERS[-1][1])
    return (cost_per, cost_per * num_sequences)


def _validate_sequences(sequences: list[dict]) -> str | None:
    """Validate a list of sequence dicts.

    Returns:
        None if valid, or an error message string.
    """
    if not sequences:
        return "No sequences provided."

    if len(sequences) > MAX_SEQUENCES_PER_PLATE:
        return (
            f"Maximum {MAX_SEQUENCES_PER_PLATE} sequences per submission "
            f"(one plate). Split into multiple batches."
        )

    for i, seq_entry in enumerate(sequences):
        if not isinstance(seq_entry, dict):
            return f"Sequence entry {i} is not an object."
        seq = seq_entry.get("sequence", "")
        name = seq_entry.get("name", f"entry_{i}")
        if not seq:
            return f"Sequence '{name}' is empty."
        invalid_chars = set(seq.upper()) - VALID_AMINO_ACIDS
        if invalid_chars:
            return (
                f"Invalid amino acid sequence in '{name}'. "
                f"Only standard amino acids (ACDEFGHIKLMNPQRSTVWY) allowed. "
                f"Found invalid characters: {sorted(invalid_chars)}"
            )

    return None


def _check_approval_file(campaign_dir: str) -> str | None:
    """Check the approval file in the campaign directory.

    Returns:
        None if approval is valid, or an error message string.
    """
    if not campaign_dir:
        return (
            "Lab submission requires a campaign directory with an approval file. "
            "The user must type /approve-lab in the BY TUI."
        )

    approval_path = Path(campaign_dir) / "lab" / "approval.json"

    if not approval_path.exists():
        return (
            "Lab submission requires user approval. "
            "The user must type /approve-lab in the BY TUI."
        )

    try:
        approval_data = json.loads(approval_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return f"Failed to read approval file: {exc}"

    if not approval_data.get("approved"):
        return (
            "Lab submission not approved. "
            "Use /approve-lab in the TUI first."
        )

    timestamp_str = approval_data.get("timestamp")
    if not timestamp_str:
        return "Approval file is missing a timestamp."

    try:
        # Support ISO format timestamps
        from datetime import datetime, timezone

        approval_time = datetime.fromisoformat(timestamp_str)
        # If naive, assume UTC
        if approval_time.tzinfo is None:
            approval_time = approval_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now - approval_time).total_seconds()
    except (ValueError, TypeError) as exc:
        return f"Invalid timestamp in approval file: {exc}"

    if age_seconds > APPROVAL_TTL:
        return (
            "Lab approval expired (1-hour window). "
            "The user must re-approve via /approve-lab."
        )

    if age_seconds < 0:
        return "Approval file has a timestamp in the future. Re-approve via /approve-lab."

    return None


# ---------------------------------------------------------------------------
# Tool 1: adaptyv_estimate_cost
# ---------------------------------------------------------------------------


@mcp.tool()
async def adaptyv_estimate_cost(
    num_sequences: int,
    assay_type: str = "binding_screen",
) -> str:
    """Estimate the cost of an Adaptyv Bio experiment.

    Pure computation -- no API call, no safety gate required.

    Args:
        num_sequences: Number of sequences to test (1-96).
        assay_type: Type of assay (default "binding_screen").

    Returns:
        JSON object with num_sequences, assay_type, cost_per_sequence,
        total_cost_usd, and turnaround_weeks.
    """
    if num_sequences <= 0:
        return _error("Number of sequences must be at least 1.")
    if num_sequences > MAX_SEQUENCES_PER_PLATE:
        return _error(
            f"Maximum {MAX_SEQUENCES_PER_PLATE} sequences per submission "
            f"(one plate). Split into multiple batches."
        )

    cost_per, total = _compute_cost(num_sequences)

    return json.dumps(
        {
            "num_sequences": num_sequences,
            "assay_type": assay_type,
            "cost_per_sequence": cost_per,
            "total_cost_usd": total,
            "turnaround_weeks": "2-4",
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 2: adaptyv_prepare_submission (Layer 1, step 1)
# ---------------------------------------------------------------------------


@mcp.tool()
async def adaptyv_prepare_submission(
    sequences_json: str,
    assay_type: str = "binding_screen",
    target_name: str = "",
    campaign_dir: str = "",
) -> str:
    """Prepare a lab submission to Adaptyv Bio for review.

    This does NOT submit anything. It validates the sequences, generates a
    confirmation code, and stores the payload for later confirmation.

    The agent must then call adaptyv_confirm_submission with the returned
    code to actually submit. The user must also have approved the submission
    via /approve-lab in the TUI.

    Args:
        sequences_json: JSON string of sequences, each with "name",
            "sequence", and "chain_type". Example:
            [{"name": "design_001", "sequence": "EVQLVE...", "chain_type": "VHH"}]
        assay_type: Type of assay (default "binding_screen").
        target_name: Name of the target protein (e.g. "TNF-alpha").
        campaign_dir: Path to the campaign directory containing lab/approval.json.

    Returns:
        JSON object with confirmation code, summary, and preview.
    """
    _log(f"prepare_submission called: assay={assay_type}, target={target_name}")

    # Parse sequences JSON
    try:
        sequences = json.loads(sequences_json)
    except json.JSONDecodeError as exc:
        _log(f"prepare_submission REJECTED: invalid JSON - {exc}")
        return _error(f"Invalid sequences JSON: {exc}")

    if not isinstance(sequences, list):
        _log("prepare_submission REJECTED: sequences is not a list")
        return _error("sequences_json must be a JSON array of sequence objects.")

    # Validate sequences
    validation_error = _validate_sequences(sequences)
    if validation_error is not None:
        _log(f"prepare_submission REJECTED: {validation_error}")
        return _error(validation_error)

    # Clean up expired entries before adding new one
    _cleanup_expired()

    # Generate confirmation code and store pending submission
    code = _generate_code()
    num_seqs = len(sequences)
    cost_per, total_cost = _compute_cost(num_seqs)

    payload = {
        "sequences": sequences,
        "assay_type": assay_type,
        "target_name": target_name,
        "campaign_dir": campaign_dir,
    }

    _pending[code] = PendingSubmission(
        code=code,
        payload=payload,
        created_at=time.time(),
        ttl=CONFIRMATION_TTL,
    )

    # Build preview strings
    previews = []
    for seq_entry in sequences:
        name = seq_entry.get("name", "unnamed")
        seq = seq_entry.get("sequence", "")
        preview_seq = seq[:6] + "..." if len(seq) > 6 else seq
        previews.append(f"{name}: {preview_seq} ({len(seq)} aa)")

    result = {
        "status": "awaiting_confirmation",
        "confirmation_code": code,
        "expires_in_seconds": CONFIRMATION_TTL,
        "summary": {
            "num_sequences": num_seqs,
            "assay_type": assay_type,
            "target": target_name,
            "estimated_cost_usd": total_cost,
            "estimated_turnaround": "2-4 weeks",
        },
        "sequences_preview": previews,
        "WARNING": (
            "PHYSICAL LAB SUBMISSION. This will send sequences to "
            "Adaptyv Bio for synthesis and testing. Confirm with the "
            "code above."
        ),
    }

    _log(
        f"prepare_submission OK: code={code}, "
        f"num_seqs={num_seqs}, cost=${total_cost}"
    )

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: adaptyv_confirm_submission (Layers 1+2+3)
# ---------------------------------------------------------------------------


@mcp.tool()
async def adaptyv_confirm_submission(
    confirmation_code: str,
    campaign_dir: str = "",
) -> str:
    """Confirm and submit a previously prepared lab submission.

    This performs ALL three safety checks before submitting:
      1. Confirmation code must exist and not be expired (Layer 1 + 3)
      2. Approval file must exist and be recent (Layer 2)
      3. API token must be set

    Args:
        confirmation_code: The code returned by adaptyv_prepare_submission.
        campaign_dir: Path to the campaign directory (overrides the one
            stored in the pending submission if provided).

    Returns:
        JSON object with experiment_id, status, submitted_at, and
        estimated_completion on success. Error object on failure.
    """
    _log(f"confirm_submission called: code={confirmation_code}")

    # Layer 3: Clean up expired entries
    _cleanup_expired()

    # Layer 1+3: Pop atomically — if two concurrent calls race, only one gets the entry
    pending = _pending.pop(confirmation_code, None)
    if pending is None:
        _log(f"confirm_submission REJECTED: invalid or already-used code {confirmation_code}")
        return _error(
            "Invalid or already-used confirmation code. "
            "Run adaptyv_prepare_submission first."
        )

    # Layer 3: Check if code expired (belt-and-suspenders; cleanup above
    # should have caught it, but check explicitly)
    if pending.expired:
        _log(f"confirm_submission REJECTED: expired code {confirmation_code}")
        return _error(
            "Confirmation code expired (5-minute window). "
            "Run adaptyv_prepare_submission again."
        )

    # Determine campaign_dir: use argument if provided, else from payload
    effective_campaign_dir = (
        campaign_dir if campaign_dir else pending.payload.get("campaign_dir", "")
    )

    # Layer 2: Check approval file
    approval_error = _check_approval_file(effective_campaign_dir)
    if approval_error is not None:
        _log(f"confirm_submission REJECTED: approval check failed - {approval_error}")
        return _error(approval_error)

    # Check API token
    token = _get_api_token()
    if not token:
        _log("confirm_submission REJECTED: no API token")
        return _error(
            "ADAPTYV_API_TOKEN not set. "
            "Get your token at https://www.adaptyvbio.com"
        )

    # All gates passed -- submit to Adaptyv Bio API
    payload = pending.payload
    api_payload = {
        "sequences": payload["sequences"],
        "assay_type": payload["assay_type"],
        "target_name": payload["target_name"],
    }

    _log(
        f"confirm_submission SUBMITTING: "
        f"{len(payload['sequences'])} sequences, "
        f"assay={payload['assay_type']}, "
        f"target={payload['target_name']}"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ADAPTYV_BASE_URL}/experiments",
                json=api_payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        _log(f"confirm_submission API ERROR: {exc.response.status_code} - {exc}")
        return _error(
            f"Adaptyv Bio API error ({exc.response.status_code}): "
            f"{exc.response.text}"
        )
    except httpx.HTTPError as exc:
        _log(f"confirm_submission NETWORK ERROR: {exc}")
        return _error(f"Failed to reach Adaptyv Bio API: {exc}")
    except Exception as exc:
        _log(f"confirm_submission UNEXPECTED ERROR: {exc}")
        return _error(f"Unexpected error during submission: {exc}")

    submitted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    result = {
        "experiment_id": data.get("experiment_id", data.get("id", "unknown")),
        "status": "submitted",
        "submitted_at": submitted_at,
        "estimated_completion": data.get("estimated_completion", "2-4 weeks"),
    }

    _log(
        f"confirm_submission SUCCESS: "
        f"experiment_id={result['experiment_id']}"
    )

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 4: adaptyv_get_experiment_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def adaptyv_get_experiment_status(experiment_id: str) -> str:
    """Check the status of an Adaptyv Bio experiment.

    Args:
        experiment_id: The experiment ID returned by a confirmed submission.

    Returns:
        JSON object with experiment_id, status, progress,
        estimated_completion, and notes.
    """
    if not experiment_id or not experiment_id.strip():
        return _error("experiment_id must not be empty.")

    token = _get_api_token()
    if not token:
        return _error(
            "ADAPTYV_API_TOKEN not set. "
            "Get your token at https://www.adaptyvbio.com"
        )

    experiment_id = experiment_id.strip()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ADAPTYV_BASE_URL}/experiments/{experiment_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return _error(
            f"Adaptyv Bio API error ({exc.response.status_code}): "
            f"{exc.response.text}"
        )
    except httpx.HTTPError as exc:
        return _error(f"Failed to reach Adaptyv Bio API: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error checking status: {exc}")

    return json.dumps(
        {
            "experiment_id": experiment_id,
            "status": data.get("status", "unknown"),
            "progress": data.get("progress"),
            "estimated_completion": data.get("estimated_completion"),
            "notes": data.get("notes", ""),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 5: adaptyv_get_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def adaptyv_get_results(experiment_id: str) -> str:
    """Retrieve results for a completed Adaptyv Bio experiment.

    Args:
        experiment_id: The experiment ID returned by a confirmed submission.

    Returns:
        JSON object with experiment_id and results array. Each result
        contains sequence_name, binding_signal, kd_nm, specificity,
        and notes.
    """
    if not experiment_id or not experiment_id.strip():
        return _error("experiment_id must not be empty.")

    token = _get_api_token()
    if not token:
        return _error(
            "ADAPTYV_API_TOKEN not set. "
            "Get your token at https://www.adaptyvbio.com"
        )

    experiment_id = experiment_id.strip()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ADAPTYV_BASE_URL}/experiments/{experiment_id}/results",
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return _error(
            f"Adaptyv Bio API error ({exc.response.status_code}): "
            f"{exc.response.text}"
        )
    except httpx.HTTPError as exc:
        return _error(f"Failed to reach Adaptyv Bio API: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error fetching results: {exc}")

    # Normalize results into expected format
    raw_results = data if isinstance(data, list) else data.get("results", [])
    results = []
    for entry in raw_results:
        results.append(
            {
                "sequence_name": entry.get("sequence_name", entry.get("name", "")),
                "binding_signal": entry.get("binding_signal"),
                "kd_nm": entry.get("kd_nm"),
                "specificity": entry.get("specificity"),
                "notes": entry.get("notes", ""),
            }
        )

    return json.dumps(
        {
            "experiment_id": experiment_id,
            "results": results,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
