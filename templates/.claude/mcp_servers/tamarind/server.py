#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx",
# ]
# ///
"""Tamarind Bio MCP Server — default compute provider for open-source users.

Endpoints verified by live API testing (2026-03-23).

WARNING: Free tier allows only 10 jobs/month. The agent should minimize
unnecessary submissions and prefer batching where possible.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})

mcp = FastMCP("by-tamarind")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://app.tamarind.bio/api"
TIMEOUT = 60.0
MAX_FILE_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# Tool cache (populated by tamarind_list_tools, expires after 1 hour)
_tool_cache: list[dict] | None = None
_tool_cache_ts: float = 0.0
_TOOL_CACHE_TTL = 3600.0  # seconds


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


def _require_api_key() -> str | None:
    """Return an error JSON string if the API key is missing, else None."""
    if not _api_key():
        return _error(
                "TAMARIND_API_KEY is not set. "
                "Get a free key at https://app.tamarind.bio and set it: "
                "export TAMARIND_API_KEY=<your-key>"
            )
    return None


def _invalidate_tool_cache() -> None:
    """Clear the tool cache (e.g. after an auth error invalidates it)."""
    global _tool_cache, _tool_cache_ts
    _tool_cache = None
    _tool_cache_ts = 0.0


def _handle_http_error(resp: httpx.Response) -> str | None:
    """Return an error string for auth/rate-limit/server issues, or None."""
    if resp.status_code == 401:
        _invalidate_tool_cache()
        return _error(
                "Invalid TAMARIND_API_KEY. "
                "Get one at https://app.tamarind.bio"
            )
    if resp.status_code == 429:
        return _error(
                "Rate limited. Free tier allows 10 jobs/month. "
                "Upgrade at tamarind.bio/pricing"
            )
    if resp.status_code >= 400:
        body = resp.text[:500]
        return _error(f"Tamarind API error ({resp.status_code}): {body}")
    return None


def _generate_job_name(prefix: str = "by") -> str:
    """Generate a unique job name with a prefix and short UUID."""
    short_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{short_id}"


def _parse_score(score_field: str | dict | None) -> dict | None:
    """Parse the Score field from a job object (may be a JSON string or dict)."""
    if score_field is None:
        return None
    if isinstance(score_field, dict):
        return score_field
    if isinstance(score_field, str) and score_field.strip():
        try:
            return json.loads(score_field)
        except json.JSONDecodeError:
            return {"raw": score_field}
    return None


def _parse_settings(settings_field: str | dict | None) -> dict | None:
    """Parse the Settings field from a job object."""
    if settings_field is None:
        return None
    if isinstance(settings_field, dict):
        return settings_field
    if isinstance(settings_field, str) and settings_field.strip():
        try:
            return json.loads(settings_field)
        except json.JSONDecodeError:
            return {"raw": settings_field}
    return None


# ---------------------------------------------------------------------------
# Tool 1: tamarind_list_tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_list_tools() -> str:
    """List all available tools on Tamarind Bio with their settings schemas.

    Returns 226+ tools including structure prediction (protenix, boltz,
    esmfold), binder design (boltzgen), developability (tap, tnp),
    humanization (ablang), and more.

    Results are cached for 1 hour.

    Returns:
        JSON list of tool objects with name, description, and settings schema.
    """
    global _tool_cache, _tool_cache_ts

    err = _require_api_key()
    if err:
        return err

    # Return cached result if still valid
    now = time.monotonic()
    if _tool_cache is not None and (now - _tool_cache_ts) < _TOOL_CACHE_TTL:
        return json.dumps(
            {"tools": _tool_cache, "count": len(_tool_cache), "cached": True},
            indent=2,
        )

    url = f"{_base_url()}/tools"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            # Cache the result
            tools = data if isinstance(data, list) else data.get("tools", data)
            _tool_cache = tools
            _tool_cache_ts = time.monotonic()

            return json.dumps(
                {"tools": tools, "count": len(tools), "cached": False},
                indent=2,
            )

    except httpx.HTTPError as exc:
        return _error(f"Failed to list Tamarind tools: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error listing Tamarind tools: {exc}")


# ---------------------------------------------------------------------------
# Tool 2: tamarind_upload_file
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_upload_file(file_path: str) -> str:
    """Upload a file to Tamarind Bio for use in jobs.

    Supports PDB, CIF, FASTA, and other structural biology file formats.

    Args:
        file_path: Absolute path to the local file to upload.

    Returns:
        JSON object with the uploaded file reference from Tamarind.
    """
    err = _require_api_key()
    if err:
        return err

    ALLOWED_EXTENSIONS = {'.pdb', '.cif', '.mmcif', '.fasta', '.fa', '.faa', '.yaml', '.yml', '.json', '.csv'}

    p = Path(file_path).resolve()
    if not p.exists():
        return _error(f"File not found: {p}")
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        return _error(f"File type '{p.suffix}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if p.stat().st_size > MAX_FILE_UPLOAD_SIZE:
        return _error(
                f"File exceeds {MAX_FILE_UPLOAD_SIZE // (1024 * 1024)} MB "
                f"limit: {p} ({p.stat().st_size / (1024 * 1024):.1f} MB)"
            )

    url = f"{_base_url()}/files"
    try:
        file_content = p.read_bytes()
        files = {"file": (p.name, file_content, "application/octet-stream")}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, headers=_auth_headers(), files=files, timeout=TIMEOUT
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to upload file to Tamarind: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error uploading file to Tamarind: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: tamarind_list_files
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_list_files() -> str:
    """List files uploaded to Tamarind Bio.

    Returns:
        JSON list of uploaded file objects.
    """
    err = _require_api_key()
    if err:
        return err

    url = f"{_base_url()}/files"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to list Tamarind files: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error listing Tamarind files: {exc}")


# ---------------------------------------------------------------------------
# Tool 4: tamarind_submit_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_submit_job(
    job_name: str,
    tool_type: str,
    settings_json: str,
) -> str:
    """Submit a compute job to Tamarind Bio.

    WARNING: Free tier allows only 10 jobs/month. Use sparingly.

    Args:
        job_name: Unique human-readable name for the job. Use a prefix like
            'by_' with a short UUID to ensure uniqueness.
        tool_type: The tool name from tamarind_list_tools (e.g., "boltzgen",
            "tap", "ablang", "protenix", "tnp", "esmfold").
        settings_json: JSON string matching the tool's settings schema.
            Get the schema from tamarind_list_tools.

    Returns:
        JSON object with submission confirmation.
    """
    err = _require_api_key()
    if err:
        return err

    if not job_name.strip():
        return _error("job_name must not be empty.")
    if not tool_type.strip():
        return _error("tool_type must not be empty.")

    # Parse and validate settings
    try:
        settings = json.loads(settings_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid JSON in settings_json: {exc}")

    url = f"{_base_url()}/submit-job"
    body = {
        "jobName": job_name,
        "type": tool_type,
        "settings": settings,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={**_auth_headers(), "Content-Type": "application/json"},
                json=body,
                timeout=TIMEOUT,
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(
                {
                    "submitted": True,
                    "job_name": job_name,
                    "tool_type": tool_type,
                    "response": data,
                },
                indent=2,
            )

    except httpx.HTTPError as exc:
        return _error(f"Failed to submit Tamarind job: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error submitting Tamarind job: {exc}")


# ---------------------------------------------------------------------------
# Tool 5: tamarind_submit_batch
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_submit_batch(
    batch_name: str,
    tool_type: str,
    settings_list_json: str,
) -> str:
    """Submit a batch of jobs to Tamarind Bio (same tool, multiple inputs).

    More efficient than submitting individual jobs. Each element in the
    settings list becomes one job in the batch.

    WARNING: Free tier allows only 10 jobs/month. Each batch item counts
    as one job.

    Args:
        batch_name: Unique name for the batch.
        tool_type: The tool name from tamarind_list_tools.
        settings_list_json: JSON array of settings objects, each matching
            the tool's settings schema.

    Returns:
        JSON object with batch submission confirmation.
    """
    err = _require_api_key()
    if err:
        return err

    if not batch_name.strip():
        return _error("batch_name must not be empty.")
    if not tool_type.strip():
        return _error("tool_type must not be empty.")

    # Parse and validate settings list
    try:
        settings_list = json.loads(settings_list_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid JSON in settings_list_json: {exc}")

    if not isinstance(settings_list, list):
        return _error("settings_list_json must be a JSON array of settings objects.")
    if len(settings_list) == 0:
        return _error("settings_list_json must not be empty.")

    url = f"{_base_url()}/submit-batch"
    body = {
        "batchName": batch_name,
        "type": tool_type,
        "settings": settings_list,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={**_auth_headers(), "Content-Type": "application/json"},
                json=body,
                timeout=TIMEOUT,
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(
                {
                    "submitted": True,
                    "batch_name": batch_name,
                    "tool_type": tool_type,
                    "job_count": len(settings_list),
                    "response": data,
                },
                indent=2,
            )

    except httpx.HTTPError as exc:
        return _error(f"Failed to submit Tamarind batch: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error submitting Tamarind batch: {exc}")


# ---------------------------------------------------------------------------
# Tool 6: tamarind_list_jobs
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_list_jobs() -> str:
    """List all jobs on Tamarind Bio with their status and results.

    Returns:
        JSON list of job objects. Each job contains JobName, JobStatus,
        Type, Settings, Created, Started, Completed, and Score fields.
        The Score field contains results/metrics as a JSON string (parsed
        automatically).
    """
    err = _require_api_key()
    if err:
        return err

    url = f"{_base_url()}/jobs"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            # Parse Score and Settings fields for each job
            jobs = data if isinstance(data, list) else data.get("jobs", [data])
            for job in jobs:
                if "Score" in job:
                    job["Score"] = _parse_score(job["Score"])
                if "Settings" in job:
                    job["Settings"] = _parse_settings(job["Settings"])

            return json.dumps(jobs, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to list Tamarind jobs: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error listing Tamarind jobs: {exc}")


# ---------------------------------------------------------------------------
# Tool 7: tamarind_get_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_get_job(job_name: str) -> str:
    """Get a specific Tamarind Bio job by name.

    Fetches all jobs via GET /api/jobs and filters by JobName.

    Args:
        job_name: The job name used when submitting.

    Returns:
        JSON object with the job's status, settings, and results (Score).
        JobStatus values: "Submitted", "In Queue", "Running", "Complete",
        "Failed".
    """
    err = _require_api_key()
    if err:
        return err

    if not job_name.strip():
        return _error("job_name must not be empty.")

    url = f"{_base_url()}/jobs"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            http_err = _handle_http_error(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            jobs = data if isinstance(data, list) else data.get("jobs", [data])

            # Filter by JobName
            matching = [
                j for j in jobs if j.get("JobName") == job_name
            ]

            if not matching:
                return _error(
                        f"No job found with name '{job_name}'. "
                        f"Use tamarind_list_jobs to see all jobs."
                    )

            # Return the most recent match (in case of duplicates)
            job = matching[-1]
            if "Score" in job:
                job["Score"] = _parse_score(job["Score"])
            if "Settings" in job:
                job["Settings"] = _parse_settings(job["Settings"])

            return json.dumps(job, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to get Tamarind job '{job_name}': {exc}")
    except Exception as exc:
        return _error(
                f"Unexpected error getting Tamarind job '{job_name}': {exc}"
            )


# ---------------------------------------------------------------------------
# Tool 8: tamarind_wait_for_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_wait_for_job(
    job_name: str,
    timeout_seconds: int = 3600,
    poll_interval_seconds: int = 30,
) -> str:
    """Poll a Tamarind Bio job until completion or timeout.

    Uses exponential backoff starting at poll_interval_seconds, doubling
    each iteration up to a maximum of 120 seconds.

    Args:
        job_name: The job name used when submitting.
        timeout_seconds: Maximum time to wait in seconds (default 3600).
        poll_interval_seconds: Initial polling interval in seconds (default 30).

    Returns:
        JSON object with the final job status and results.
    """
    err = _require_api_key()
    if err:
        return err

    if not job_name.strip():
        return _error("job_name must not be empty.")

    terminal_statuses = {"Complete", "Failed"}
    interval = max(1, poll_interval_seconds)
    max_interval = 120
    deadline = time.monotonic() + timeout_seconds

    while True:
        job_json = await tamarind_get_job(job_name)
        try:
            job_data = json.loads(job_json)
        except json.JSONDecodeError:
            return job_json  # Propagate raw error

        # If we got an error from the get call, return it
        if "error" in job_data:
            return job_json

        current_status = job_data.get("JobStatus", "")
        if current_status in terminal_statuses:
            return job_json

        # Check timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _error(
                    f"Timeout after {timeout_seconds}s waiting for job "
                    f"'{job_name}'. Last status: {current_status}"
                )

        # Sleep with exponential backoff
        sleep_time = min(interval, max_interval, remaining)
        await asyncio.sleep(sleep_time)
        interval = min(interval * 2, max_interval)


# ---------------------------------------------------------------------------
# Tool 9: tamarind_screen_developability
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_screen_developability(
    sequence: str,
    modality: str = "vhh",
) -> str:
    """Screen an antibody/nanobody sequence for developability.

    Smart wrapper that selects the right Tamarind tool based on modality:
    - VHH/nanobody: submits to 'tnp' (Therapeutic Nanobody Profiler)
    - scFv/antibody: submits to 'tap' (Therapeutic Antibody Profiler v2)

    WARNING: Counts as 1 of 10 free jobs/month.

    Args:
        sequence: Amino acid sequence (VH, VHH, or VL).
        modality: One of "vhh", "nanobody", "scfv", "antibody", "mab".
            Defaults to "vhh".

    Returns:
        JSON object with submitted job_name for polling with
        tamarind_get_job or tamarind_wait_for_job.
    """
    err = _require_api_key()
    if err:
        return err

    if not sequence.strip():
        return _error("sequence must not be empty.")

    modality_lower = modality.strip().lower()

    if modality_lower in ("vhh", "nanobody"):
        tool_type = "tnp"
        settings = {"sequence": sequence}
    elif modality_lower in ("scfv", "antibody", "mab"):
        tool_type = "tap"
        settings = {"sequence": sequence}
    else:
        return _error(
                f"Unknown modality '{modality}'. "
                f"Use 'vhh', 'nanobody', 'scfv', 'antibody', or 'mab'."
            )

    job_name = _generate_job_name(f"by_dev_{tool_type}")

    # Submit via the submit-job tool
    result = await tamarind_submit_job(
        job_name=job_name,
        tool_type=tool_type,
        settings_json=json.dumps(settings),
    )

    try:
        result_data = json.loads(result)
    except json.JSONDecodeError:
        return result

    if "error" in result_data:
        return result

    return json.dumps(
        {
            "job_name": job_name,
            "tool_type": tool_type,
            "modality": modality_lower,
            "message": (
                f"Developability screening submitted as '{job_name}'. "
                f"Poll with tamarind_get_job('{job_name}') or "
                f"tamarind_wait_for_job('{job_name}')."
            ),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 10: tamarind_screen_naturalness
# ---------------------------------------------------------------------------


@mcp.tool()
async def tamarind_screen_naturalness(
    heavy_sequence: str,
    light_sequence: str = "",
) -> str:
    """Screen antibody sequences for naturalness using AbLang2.

    Submits to Tamarind's 'ablang' tool which evaluates how natural
    (human-like) an antibody sequence is.

    WARNING: Counts as 1 of 10 free jobs/month.

    Args:
        heavy_sequence: Heavy chain amino acid sequence (VH or VHH).
        light_sequence: Light chain amino acid sequence (VL). Optional,
            omit for VHH/nanobodies.

    Returns:
        JSON object with submitted job_name for polling with
        tamarind_get_job or tamarind_wait_for_job.
    """
    err = _require_api_key()
    if err:
        return err

    if not heavy_sequence.strip():
        return _error("heavy_sequence must not be empty.")

    settings: dict = {"heavy_sequence": heavy_sequence}
    if light_sequence.strip():
        settings["light_sequence"] = light_sequence

    job_name = _generate_job_name("by_nat_ablang")

    result = await tamarind_submit_job(
        job_name=job_name,
        tool_type="ablang",
        settings_json=json.dumps(settings),
    )

    try:
        result_data = json.loads(result)
    except json.JSONDecodeError:
        return result

    if "error" in result_data:
        return result

    return json.dumps(
        {
            "job_name": job_name,
            "tool_type": "ablang",
            "message": (
                f"Naturalness screening submitted as '{job_name}'. "
                f"Poll with tamarind_get_job('{job_name}') or "
                f"tamarind_wait_for_job('{job_name}')."
            ),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
