import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Levitate Bio MCP Server — antibody design and analysis pipelines."""
from __future__ import annotations

import asyncio
import json
import math
import os
import time
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_servers._shared.base import _error, _validate_pdb_path

mcp = FastMCP("levitate")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.levitate.bio/v1"
TIMEOUT = 60.0

VALID_GPU_TYPES = {"t4", "l4", "a100"}

# GPU cost rates (USD per hour)
GPU_RATES: dict[str, float] = {
    "t4": 3.50,
    "l4": 5.60,
    "a100": 29.34,
}

# Estimated hours per pipeline per 10 designs on l4 baseline
_PIPELINE_HOURS_PER_10: dict[str, dict[str, float]] = {
    "rfantibody": {"t4": 0.8, "l4": 0.5, "a100": 0.2},
    "developability": {"t4": 0.15, "l4": 0.1, "a100": 0.05},
    "immunogenicity": {"t4": 0.2, "l4": 0.12, "a100": 0.06},
    "biophysics": {"t4": 0.15, "l4": 0.1, "a100": 0.05},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_url() -> str:
    return os.environ.get("LEVITATE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _client_id() -> str | None:
    return os.environ.get("LEVITATE_CLIENT_ID")


def _client_secret() -> str | None:
    return os.environ.get("LEVITATE_CLIENT_SECRET")


def _auth_headers() -> dict[str, str]:
    cid = _client_id()
    secret = _client_secret()
    if not cid or not secret:
        return {}
    return {
        "X-Client-Id": cid,
        "X-Client-Secret": secret,
    }


def _check_credentials() -> str | None:
    """Return an error JSON string if credentials are missing, else None."""
    cid = _client_id()
    secret = _client_secret()
    if not cid or not secret:
        return _error(
                "LEVITATE_CLIENT_ID and LEVITATE_CLIENT_SECRET must be set. "
                "Get credentials at https://levitate.bio/register"
            )
    return None


def _handle_status_error(resp: httpx.Response) -> str | None:
    """Return an error string for common HTTP errors, or None."""
    if resp.status_code == 401:
        return _error(
                "Invalid Levitate credentials. "
                "Check LEVITATE_CLIENT_ID and LEVITATE_CLIENT_SECRET. "
                "Get credentials at https://levitate.bio/register"
            )
    if resp.status_code == 429:
        return _error("Rate limited by Levitate Bio. Please try again later.")
    return None


# ---------------------------------------------------------------------------
# Tool 1: levitate_list_pipelines
# ---------------------------------------------------------------------------


@mcp.tool()
async def levitate_list_pipelines() -> str:
    """List available pipelines on Levitate Bio.

    Returns:
        JSON list of pipeline objects with pipeline_id, name,
        description, and supported parameters.
    """
    cred_err = _check_credentials()
    if cred_err:
        return cred_err

    url = f"{_base_url()}/pipelines"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=TIMEOUT
            )
            status_err = _handle_status_error(resp)
            if status_err:
                return status_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to list Levitate pipelines: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error listing Levitate pipelines: {exc}")


# ---------------------------------------------------------------------------
# Tool 2: levitate_run_rfantibody
# ---------------------------------------------------------------------------


@mcp.tool()
async def levitate_run_rfantibody(
    target_pdb: str,
    target_chain: str,
    epitope_residues: str,
    num_designs: int = 10,
    gpu_type: str = "l4",
) -> str:
    """Run RFAntibody de novo antibody design on Levitate Bio.

    Args:
        target_pdb: Path to the target antigen PDB file.
        target_chain: Chain ID of the target antigen in the PDB.
        epitope_residues: Comma-separated residue numbers defining the
            epitope (e.g. "75,76,77,79,81").
        num_designs: Number of antibody designs to generate (default 10).
        gpu_type: GPU tier — "t4", "l4", or "a100" (default "l4").

    Returns:
        JSON object with run_id, status, gpu_type, estimated_cost_usd,
        and estimated_time_minutes.
    """
    cred_err = _check_credentials()
    if cred_err:
        return cred_err

    # Validate gpu_type
    gpu_type = gpu_type.lower().strip()
    if gpu_type not in VALID_GPU_TYPES:
        return _error(
                f"Invalid gpu_type: '{gpu_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_GPU_TYPES))}"
            )

    # Validate target_chain
    if not target_chain.strip():
        return _error("target_chain must not be empty.")

    # Validate epitope_residues
    if not epitope_residues.strip():
        return _error("epitope_residues must not be empty.")
    try:
        residue_list = [
            int(r.strip()) for r in epitope_residues.split(",") if r.strip()
        ]
    except ValueError:
        return _error(
                "epitope_residues must be comma-separated integers "
                f"(e.g. '75,76,77'). Got: '{epitope_residues}'"
            )

    if not residue_list:
        return _error("epitope_residues must not be empty.")

    # Validate and read PDB file
    p = Path(target_pdb).resolve()
    if not p.exists():
        return _error(f"Target PDB file not found: {p}")
    if p.stat().st_size > 10 * 1024 * 1024:
        return _error(f"Target PDB file exceeds 10 MB limit: {p}")

    pdb_bytes = p.read_bytes()

    url = f"{_base_url()}/runs/rfantibody"

    try:
        async with httpx.AsyncClient() as client:
            files = {"target_pdb": (p.name, pdb_bytes, "chemical/x-pdb")}
            form_data = {
                "target_chain": target_chain.strip(),
                "epitope_residues": ",".join(str(r) for r in residue_list),
                "num_designs": str(num_designs),
                "gpu_type": gpu_type,
            }

            resp = await client.post(
                url,
                headers=_auth_headers(),
                data=form_data,
                files=files,
                timeout=TIMEOUT,
            )
            status_err = _handle_status_error(resp)
            if status_err:
                return status_err

            # Handle GPU OOM specifically
            if resp.status_code == 507 or (
                resp.status_code >= 400
                and "out of memory" in resp.text.lower()
            ):
                higher = {"t4": "l4", "l4": "a100", "a100": None}
                suggestion = higher.get(gpu_type)
                msg = (
                    f"GPU out of memory on {gpu_type}. "
                    f"Try a higher tier: gpu_type='{suggestion}'"
                    if suggestion
                    else f"GPU out of memory on {gpu_type} (already highest tier). "
                    f"Reduce num_designs or simplify the input."
                )
                return _error(msg)

            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to submit RFAntibody run: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error submitting RFAntibody run: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: levitate_run_analysis
# ---------------------------------------------------------------------------


@mcp.tool()
async def levitate_run_analysis(
    design_pdb: str,
    analysis_type: str = "developability",
) -> str:
    """Run analysis on an antibody design via Levitate Bio.

    Args:
        design_pdb: Path to the antibody design PDB file.
        analysis_type: Type of analysis — "developability",
            "immunogenicity", or "biophysics" (default "developability").

    Returns:
        JSON object with analysis_id, status, and estimated_time_minutes.
    """
    cred_err = _check_credentials()
    if cred_err:
        return cred_err

    valid_types = {"developability", "immunogenicity", "biophysics"}
    analysis_type = analysis_type.lower().strip()
    if analysis_type not in valid_types:
        return _error(
                f"Invalid analysis_type: '{analysis_type}'. "
                f"Must be one of: {', '.join(sorted(valid_types))}"
            )

    # Validate and read PDB file
    p = Path(design_pdb).resolve()
    if not p.exists():
        return _error(f"Design PDB file not found: {p}")
    if p.stat().st_size > 10 * 1024 * 1024:
        return _error(f"Design PDB file exceeds 10 MB limit: {p}")

    pdb_bytes = p.read_bytes()

    url = f"{_base_url()}/runs/analysis"

    try:
        async with httpx.AsyncClient() as client:
            files = {"design_pdb": (p.name, pdb_bytes, "chemical/x-pdb")}
            form_data = {"analysis_type": analysis_type}

            resp = await client.post(
                url,
                headers=_auth_headers(),
                data=form_data,
                files=files,
                timeout=TIMEOUT,
            )
            status_err = _handle_status_error(resp)
            if status_err:
                return status_err
            resp.raise_for_status()
            data = resp.json()

            return json.dumps(data, indent=2)

    except httpx.HTTPError as exc:
        return _error(f"Failed to submit Levitate analysis: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error submitting Levitate analysis: {exc}")


# ---------------------------------------------------------------------------
# Tool 4: levitate_get_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def levitate_get_results(run_id: str, output_dir: str) -> str:
    """Download results of a Levitate Bio run.

    Args:
        run_id: The run or analysis identifier.
        output_dir: Local directory to save result files.

    Returns:
        JSON object with run_id, status, output_dir, and designs
        (list of {name, sequence, metrics}).
    """
    cred_err = _check_credentials()
    if cred_err:
        return cred_err

    if not run_id.strip():
        return _error("run_id must not be empty.")

    out_path = Path(output_dir)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _error(f"Cannot create output directory: {exc}")

    url = f"{_base_url()}/runs/{run_id}/results"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers=_auth_headers(), timeout=120.0
            )
            status_err = _handle_status_error(resp)
            if status_err:
                return status_err
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status", "unknown")

            # Download result files if present
            designs: list[dict] = []
            for design in data.get("designs", []):
                file_url = design.get("url", "")
                file_name = design.get("name", "unknown.pdb")
                sequence = design.get("sequence", "")
                metrics = design.get("metrics", {})

                if file_url:
                    file_resp = await client.get(
                        file_url, headers=_auth_headers(), timeout=120.0
                    )
                    file_resp.raise_for_status()
                    file_path = out_path / file_name
                    file_path.write_bytes(file_resp.content)

                designs.append(
                    {
                        "name": file_name,
                        "sequence": sequence,
                        "metrics": metrics,
                    }
                )

            # Also download any additional files (analysis reports, etc.)
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

            return json.dumps(
                {
                    "run_id": run_id,
                    "status": status,
                    "output_dir": str(out_path),
                    "designs": designs,
                },
                indent=2,
            )

    except httpx.HTTPError as exc:
        return _error(f"Failed to get Levitate results for {run_id}: {exc}")
    except Exception as exc:
        return _error(
                f"Unexpected error getting Levitate results "
                f"for {run_id}: {exc}"
            )


# ---------------------------------------------------------------------------
# Tool 5: levitate_estimate_cost
# ---------------------------------------------------------------------------


@mcp.tool()
async def levitate_estimate_cost(
    gpu_type: str,
    num_designs: int,
    pipeline: str = "rfantibody",
) -> str:
    """Estimate the cost of a Levitate Bio run (no API call needed).

    Args:
        gpu_type: GPU tier — "t4", "l4", or "a100".
        num_designs: Number of designs to generate.
        pipeline: Pipeline name — "rfantibody", "developability",
            "immunogenicity", or "biophysics" (default "rfantibody").

    Returns:
        JSON object with gpu_type, estimated_hours, cost_per_hour,
        and total_cost_usd.
    """
    gpu_type = gpu_type.lower().strip()
    if gpu_type not in VALID_GPU_TYPES:
        return _error(
                f"Invalid gpu_type: '{gpu_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_GPU_TYPES))}"
            )

    pipeline = pipeline.lower().strip()
    if pipeline not in _PIPELINE_HOURS_PER_10:
        return _error(
                f"Unknown pipeline: '{pipeline}'. "
                f"Must be one of: {', '.join(sorted(_PIPELINE_HOURS_PER_10))}"
            )

    if num_designs < 1:
        return _error("num_designs must be at least 1.")

    # Scale linearly from the per-10 baseline
    hours_per_10 = _PIPELINE_HOURS_PER_10[pipeline][gpu_type]
    estimated_hours = round(hours_per_10 * (num_designs / 10.0), 3)
    cost_per_hour = GPU_RATES[gpu_type]
    total_cost = round(estimated_hours * cost_per_hour, 2)

    return json.dumps(
        {
            "gpu_type": gpu_type,
            "pipeline": pipeline,
            "num_designs": num_designs,
            "estimated_hours": estimated_hours,
            "cost_per_hour": cost_per_hour,
            "total_cost_usd": total_cost,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
