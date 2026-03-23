"""Tamarind Bio MCP Server — default compute provider for open-source users."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_servers._shared.base import _error, _validate_pdb_path

mcp = FastMCP("tamarind")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://app.tamarind.bio/api"
TIMEOUT = 60.0
MAX_PDB_UPLOAD_SIZE = 4 * 1024 * 1024  # 4 MB

# Model cache (populated by tamarind_list_models, expires after 1 hour)
_model_cache: dict[str, object] = {}
_model_cache_ts: float = 0.0
_MODEL_CACHE_TTL = 3600.0  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_url() -> str:
    return os.environ.get("TAMARIND_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str | None:
    return os.environ.get("TAMARIND_API_KEY")


def _auth_headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        return {}
    return {"x-api-key": key}


def _handle_auth_error(status_code: int) -> str | None:
    """Return an error string for auth/rate-limit issues, or None."""
    if status_code == 401:
        return json.dumps(
            _error(
                "Invalid TAMARIND_API_KEY. "
                "Get one at https://app.tamarind.bio"
            )
        )
    if status_code == 429:
        return json.dumps(
            _error(
                "Rate limited. Free tier allows 10 jobs/month. "
                "Upgrade at tamarind.bio/pricing"
            )
        )
    return None


# ---------------------------------------------------------------------------
# Tool 1: tamarind_list_models
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_list_models() -> str:
    """List available models on Tamarind Bio with their capabilities.

    Returns:
        JSON list of model objects with model_id, name, description,
        and supported input types.
    """
    global _model_cache, _model_cache_ts

    key = _api_key()
    if not key:
        return json.dumps(
            _error(
                "TAMARIND_API_KEY is not set. "
                "Get a free key at https://app.tamarind.bio and set it: "
                "export TAMARIND_API_KEY=<your-key>"
            )
        )

    # Return cached result if still valid
    now = time.monotonic()
    if _model_cache and (now - _model_cache_ts) < _MODEL_CACHE_TTL:
        return json.dumps(_model_cache, indent=2)

    url = f"{_base_url()}/models"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            auth_err = _handle_auth_error(resp.status_code)
            if auth_err:
                return auth_err
            resp.raise_for_status()
            data = resp.json()

            # Cache the result
            _model_cache = data
            _model_cache_ts = time.monotonic()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return json.dumps(_error(f"Failed to list Tamarind models: {exc}"))
    except Exception as exc:
        return json.dumps(
            _error(f"Unexpected error listing Tamarind models: {exc}")
        )


# ---------------------------------------------------------------------------
# Tool 2: tamarind_submit_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_submit_job(
    model_id: str,
    job_name: str,
    pdb_path: str = "",
    sequence: str = "",
    parameters: str = "",
) -> str:
    """Submit a compute job to Tamarind Bio.

    Args:
        model_id: Identifier of the model to run (from tamarind_list_models).
        job_name: Human-readable name for the job.
        pdb_path: Path to a local PDB file to upload (optional).
        sequence: Amino acid sequence input (optional).
        parameters: JSON string with model-specific settings (optional).

    Returns:
        JSON object with job_id, model_id, status, submitted_at,
        and estimated_cost_usd.
    """
    key = _api_key()
    if not key:
        return json.dumps(
            _error(
                "TAMARIND_API_KEY is not set. "
                "Get a free key at https://app.tamarind.bio and set it: "
                "export TAMARIND_API_KEY=<your-key>"
            )
        )

    if not model_id.strip():
        return json.dumps(_error("model_id must not be empty."))
    if not job_name.strip():
        return json.dumps(_error("job_name must not be empty."))

    # Parse optional parameters
    params_dict: dict = {}
    if parameters:
        try:
            params_dict = json.loads(parameters)
        except json.JSONDecodeError as exc:
            return json.dumps(
                _error(f"Invalid JSON in parameters: {exc}")
            )

    url = f"{_base_url()}/jobs"

    try:
        async with httpx.AsyncClient() as client:
            # Build request depending on whether we have a PDB file
            if pdb_path:
                # Validate PDB path exists and check size
                p = Path(pdb_path).resolve()
                if not p.exists():
                    return json.dumps(
                        _error(f"PDB file not found: {p}")
                    )
                if p.stat().st_size > MAX_PDB_UPLOAD_SIZE:
                    return json.dumps(
                        _error(
                            f"PDB file exceeds 4 MB limit: {p} "
                            f"({p.stat().st_size / (1024 * 1024):.1f} MB)"
                        )
                    )

                pdb_bytes = p.read_bytes()
                files = {"file": (p.name, pdb_bytes, "chemical/x-pdb")}
                form_data = {
                    "model_id": model_id,
                    "job_name": job_name,
                }
                if sequence:
                    form_data["sequence"] = sequence
                if params_dict:
                    form_data["parameters"] = json.dumps(params_dict)

                resp = await client.post(
                    url,
                    headers=_auth_headers(),
                    data=form_data,
                    files=files,
                    timeout=TIMEOUT,
                )
            else:
                # JSON body request
                body: dict = {
                    "model_id": model_id,
                    "job_name": job_name,
                }
                if sequence:
                    body["sequence"] = sequence
                if params_dict:
                    body["parameters"] = params_dict

                resp = await client.post(
                    url,
                    headers=_auth_headers(),
                    json=body,
                    timeout=TIMEOUT,
                )

            auth_err = _handle_auth_error(resp.status_code)
            if auth_err:
                return auth_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return json.dumps(_error(f"Failed to submit Tamarind job: {exc}"))
    except Exception as exc:
        return json.dumps(
            _error(f"Unexpected error submitting Tamarind job: {exc}")
        )


# ---------------------------------------------------------------------------
# Tool 3: tamarind_get_job_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_get_job_status(job_id: str) -> str:
    """Get the status of a Tamarind Bio compute job.

    Args:
        job_id: The job identifier returned by tamarind_submit_job.

    Returns:
        JSON object with job_id, status, progress_pct, started_at,
        estimated_completion, and error_message.
    """
    key = _api_key()
    if not key:
        return json.dumps(
            _error(
                "TAMARIND_API_KEY is not set. "
                "Get a free key at https://app.tamarind.bio and set it: "
                "export TAMARIND_API_KEY=<your-key>"
            )
        )

    if not job_id.strip():
        return json.dumps(_error("job_id must not be empty."))

    url = f"{_base_url()}/jobs/{job_id}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            auth_err = _handle_auth_error(resp.status_code)
            if auth_err:
                return auth_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return json.dumps(
            _error(f"Failed to get Tamarind job status for {job_id}: {exc}")
        )
    except Exception as exc:
        return json.dumps(
            _error(
                f"Unexpected error getting Tamarind job status "
                f"for {job_id}: {exc}"
            )
        )


# ---------------------------------------------------------------------------
# Tool 4: tamarind_get_job_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_get_job_results(job_id: str, output_dir: str) -> str:
    """Download results of a completed Tamarind Bio job.

    Args:
        job_id: The job identifier.
        output_dir: Local directory to save result files.

    Returns:
        JSON object with job_id, output_dir, files (list of {name, size_bytes}),
        and metrics.
    """
    key = _api_key()
    if not key:
        return json.dumps(
            _error(
                "TAMARIND_API_KEY is not set. "
                "Get a free key at https://app.tamarind.bio and set it: "
                "export TAMARIND_API_KEY=<your-key>"
            )
        )

    if not job_id.strip():
        return json.dumps(_error("job_id must not be empty."))

    out_path = Path(output_dir)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return json.dumps(_error(f"Cannot create output directory: {exc}"))

    url = f"{_base_url()}/jobs/{job_id}/results"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=120.0
            )
            auth_err = _handle_auth_error(resp.status_code)
            if auth_err:
                return auth_err
            resp.raise_for_status()
            data = resp.json()

            # Download each result file
            saved_files: list[dict] = []
            for file_info in data.get("files", []):
                file_url = file_info.get("url", "")
                file_name = file_info.get("name", "unknown")
                if not file_url:
                    continue

                file_resp = await client.get(
                    file_url, headers=_auth_headers(), timeout=120.0
                )
                file_resp.raise_for_status()

                file_path = out_path / file_name
                file_path.write_bytes(file_resp.content)
                saved_files.append(
                    {
                        "name": file_name,
                        "size_bytes": file_path.stat().st_size,
                    }
                )

            return json.dumps(
                {
                    "job_id": job_id,
                    "output_dir": str(out_path),
                    "files": saved_files,
                    "metrics": data.get("metrics", {}),
                },
                indent=2,
            )

    except httpx.HTTPError as exc:
        return json.dumps(
            _error(f"Failed to get Tamarind results for {job_id}: {exc}")
        )
    except Exception as exc:
        return json.dumps(
            _error(
                f"Unexpected error getting Tamarind results "
                f"for {job_id}: {exc}"
            )
        )


# ---------------------------------------------------------------------------
# Tool 5: tamarind_wait_for_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_wait_for_job(
    job_id: str,
    timeout_seconds: int = 3600,
    poll_interval_seconds: int = 30,
) -> str:
    """Poll a Tamarind Bio job until completion or timeout.

    Uses exponential backoff starting at poll_interval_seconds, doubling
    each iteration up to a maximum of 120 seconds.

    Args:
        job_id: The job identifier.
        timeout_seconds: Maximum time to wait in seconds (default 3600).
        poll_interval_seconds: Initial polling interval in seconds (default 30).

    Returns:
        JSON object with the final job status (same shape as
        tamarind_get_job_status).
    """
    key = _api_key()
    if not key:
        return json.dumps(
            _error(
                "TAMARIND_API_KEY is not set. "
                "Get a free key at https://app.tamarind.bio and set it: "
                "export TAMARIND_API_KEY=<your-key>"
            )
        )

    if not job_id.strip():
        return json.dumps(_error("job_id must not be empty."))

    terminal_statuses = {"completed", "failed", "cancelled", "error"}
    interval = max(1, poll_interval_seconds)
    max_interval = 120
    deadline = time.monotonic() + timeout_seconds

    while True:
        status_json = await tamarind_get_job_status(job_id)
        try:
            status_data = json.loads(status_json)
        except json.JSONDecodeError:
            return status_json  # Propagate raw error

        # If we got an error from the status call, return it
        if "error" in status_data:
            return status_json

        current_status = status_data.get("status", "").lower()
        if current_status in terminal_statuses:
            return status_json

        # Check timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return json.dumps(
                _error(
                    f"Timeout after {timeout_seconds}s waiting for job "
                    f"{job_id}. Last status: {current_status}"
                )
            )

        # Sleep with exponential backoff
        sleep_time = min(interval, max_interval, remaining)
        await asyncio.sleep(sleep_time)
        interval = min(interval * 2, max_interval)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
