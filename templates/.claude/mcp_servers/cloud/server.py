#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx>=0.27",
#   "paramiko>=3.0.0",
# ]
# ///
"""Unified Cloud Compute MCP Server — consolidates Tamarind API + SSH remote
compute into a single interface for the BY campaign orchestrator.

Providers:
  - tamarind: Tamarind Bio cloud API (free tier, 200+ tools)
  - ssh: Remote GPU hosts via SSH/SFTP (paramiko)
  - local: Local GPU compute (CUDA_VISIBLE_DEVICES)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import paramiko
from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# MCP app
# ---------------------------------------------------------------------------

mcp = FastMCP("cloud")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


def _ok(data: dict) -> str:
    """Return a JSON-encoded success payload."""
    return json.dumps(data, indent=2)


def _gen_id(prefix: str = "cloud") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

_ENV_PATH = Path.home() / ".by" / "environment.json"
_CONFIG_PATH = Path.home() / ".by" / "config.json"


def _load_json(path: Path) -> dict:
    """Load a JSON file or return an empty dict if missing."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _load_environment() -> dict:
    return _load_json(_ENV_PATH)


def _load_config() -> dict:
    return _load_json(_CONFIG_PATH)


# ---------------------------------------------------------------------------
# Tamarind helpers
# ---------------------------------------------------------------------------

_TAMARIND_DEFAULT_URL = "https://app.tamarind.bio/api"
_TAMARIND_TIMEOUT = 60.0
_TAMARIND_MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB

# Tier concurrency limits (best-effort defaults)
_TIER_CONCURRENCY: dict[str, int] = {
    "free": 2,
    "basic": 5,
    "pro": 20,
    "enterprise": 50,
}


def _tam_base_url() -> str:
    return os.environ.get("TAMARIND_BASE_URL", _TAMARIND_DEFAULT_URL).rstrip("/")


def _tam_api_key() -> str | None:
    key = os.environ.get("TAMARIND_API_KEY")
    if not key:
        env = _load_environment()
        key = env.get("tamarind", {}).get("api_key")
    return key


def _tam_headers() -> dict[str, str]:
    key = _tam_api_key()
    if not key:
        return {}
    return {"x-api-key": key}


def _tam_check() -> str | None:
    """Return error JSON if Tamarind API key is missing, else None."""
    if not _tam_api_key():
        return _error(
            "TAMARIND_API_KEY is not set. "
            "Get a free key at https://app.tamarind.bio and set it: "
            "export TAMARIND_API_KEY=<your-key>"
        )
    return None


def _get_alternative_providers() -> list[dict]:
    """Return list of alternative providers with basic info for error responses."""
    alternatives: list[dict] = []
    # Check SSH hosts from config
    for host_cfg in _ssh_hosts():
        name = host_cfg.get("name", host_cfg["host"])
        alternatives.append({
            "name": name,
            "type": "ssh",
            "how": f"cloud_submit_job(provider='{name}', ...)",
        })
    # Check local GPU
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        alternatives.append({
            "name": "local",
            "type": "local",
            "how": "cloud_submit_job(provider='local', ...)",
        })
    return alternatives


def _structured_error(
    msg: str,
    error_code: str,
    retry_eligible: bool = False,
    **extra: Any,
) -> str:
    """Return a structured JSON error payload with alternatives and metadata."""
    payload: dict[str, Any] = {
        "error": msg,
        "error_code": error_code,
        "retry_eligible": retry_eligible,
        "alternatives": _get_alternative_providers(),
    }
    payload.update(extra)
    return json.dumps(payload, indent=2)


def _tam_handle_http(resp: httpx.Response) -> str | None:
    """Return structured error JSON for auth/rate-limit/server issues, or None."""
    if resp.status_code == 401:
        return _structured_error(
            "Invalid TAMARIND_API_KEY. Get one at https://app.tamarind.bio",
            error_code="auth_error",
            retry_eligible=False,
        )
    if resp.status_code == 429:
        return _structured_error(
            "Rate limited by Tamarind. Check your tier quota with "
            "cloud_list_providers(). Upgrade at tamarind.bio/pricing",
            error_code="rate_limited",
            retry_eligible=True,
            suggestion="Wait a few minutes or switch to an alternative provider.",
        )
    if resp.status_code >= 500:
        body = resp.text[:500]
        return _structured_error(
            f"Tamarind server error ({resp.status_code}): {body}",
            error_code="server_error",
            retry_eligible=True,
            suggestion="Tamarind may be temporarily down. Try again in a few minutes.",
        )
    if resp.status_code >= 400:
        body = resp.text[:500]
        return _structured_error(
            f"Tamarind API error ({resp.status_code}): {body}",
            error_code="api_error",
            retry_eligible=False,
        )
    return None


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------


def _ssh_hosts() -> list[dict]:
    """Load SSH host configurations from ~/.by/config.json."""
    cfg = _load_config()
    return cfg.get("ssh_hosts", [])


def _ssh_connect(host_cfg: dict) -> paramiko.SSHClient:
    """Open an SSH connection from a host config dict.

    Expected keys: host, user, port (optional, default 22),
    key_file (optional), password (optional).
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict[str, Any] = {
        "hostname": host_cfg["host"],
        "username": host_cfg.get("user", os.environ.get("USER", "root")),
        "port": host_cfg.get("port", 22),
        "timeout": 15,
    }

    key_file = host_cfg.get("key_file")
    if key_file:
        expanded = os.path.expanduser(key_file)
        connect_kwargs["key_filename"] = expanded
    elif host_cfg.get("password"):
        connect_kwargs["password"] = host_cfg["password"]
    # else: rely on ssh-agent / default keys

    client.connect(**connect_kwargs)
    return client


def _ssh_ping(host_cfg: dict) -> dict:
    """Try to connect to an SSH host and return status info."""
    try:
        client = _ssh_connect(host_cfg)
        # Check for GPU info
        _stdin, stdout, _stderr = client.exec_command(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no-gpu'",
            timeout=10,
        )
        gpu_info = stdout.read().decode().strip()
        client.close()
        return {
            "name": host_cfg.get("name", host_cfg["host"]),
            "host": host_cfg["host"],
            "status": "online",
            "gpu_info": gpu_info if gpu_info != "no-gpu" else None,
        }
    except Exception as exc:
        return {
            "name": host_cfg.get("name", host_cfg["host"]),
            "host": host_cfg["host"],
            "status": "offline",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# In-memory job / batch tracking
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_batches: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Tool 1: cloud_list_providers
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_list_providers() -> str:
    """List available compute providers with status, quota, and capability details.

    Reads ~/.by/environment.json for Tamarind config, pings each SSH
    host from ~/.by/config.json, and checks CUDA_VISIBLE_DEVICES for
    local GPU availability.

    Returns quota/credit information for cloud providers and capabilities
    (which tools each provider supports) for all providers.

    Returns:
        JSON list of {name, type, status, details, capabilities, recommended} objects.
    """
    providers: list[dict] = []
    cfg = _load_config()
    default_provider = cfg.get("default_provider")

    # --- Tamarind ---
    tam_entry: dict[str, Any] = {
        "name": "tamarind",
        "type": "cloud_api",
        "status": "unavailable",
        "details": {},
        "capabilities": ["boltzgen", "protenix", "pxdesign", "tap"],
        "recommended": False,
    }
    key = _tam_api_key()
    if key:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_tam_base_url()}/account",
                    headers=_tam_headers(),
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    acct = resp.json()
                    tier = acct.get("tier", acct.get("plan", "free"))
                    tam_entry["status"] = "online"
                    tam_entry["details"] = {
                        "tier": tier,
                        "max_concurrent": _TIER_CONCURRENCY.get(
                            str(tier).lower(),
                            _TIER_CONCURRENCY["free"],
                        ),
                        "api_url": _tam_base_url(),
                    }
                    # Extract quota/credit info from account response
                    # Adaptively inspect fields -- Tamarind may use different names
                    quota_used = acct.get("jobs_used", acct.get("usage", acct.get("quota_used")))
                    quota_limit = acct.get("jobs_limit", acct.get("limit", acct.get("quota_limit")))
                    quota_remaining = acct.get("quota_remaining", acct.get("jobs_remaining"))
                    # Compute remaining if we have used and limit but not remaining
                    if quota_remaining is None and quota_used is not None and quota_limit is not None:
                        try:
                            quota_remaining = int(quota_limit) - int(quota_used)
                        except (ValueError, TypeError):
                            quota_remaining = None
                    tam_entry["details"]["quota_used"] = quota_used
                    tam_entry["details"]["quota_limit"] = quota_limit
                    tam_entry["details"]["quota_remaining"] = quota_remaining
                elif resp.status_code == 401:
                    tam_entry["status"] = "auth_error"
                    tam_entry["details"] = {"error": "Invalid API key"}
                else:
                    # API key is set but /account may not exist -- still usable
                    tam_entry["status"] = "online"
                    tam_entry["details"] = {
                        "tier": "unknown",
                        "max_concurrent": _TIER_CONCURRENCY["free"],
                        "api_url": _tam_base_url(),
                        "note": f"/account returned {resp.status_code}",
                        "quota_used": None,
                        "quota_limit": None,
                        "quota_remaining": None,
                    }
        except Exception as exc:
            tam_entry["status"] = "error"
            tam_entry["details"] = {"error": str(exc)}
    else:
        tam_entry["details"] = {
            "error": "TAMARIND_API_KEY not set",
            "signup": "https://app.tamarind.bio",
        }
    providers.append(tam_entry)

    # --- SSH hosts ---
    for host_cfg in _ssh_hosts():
        info = await asyncio.to_thread(_ssh_ping, host_cfg)
        ssh_entry: dict[str, Any] = {
            "name": info["name"],
            "type": "ssh",
            "status": info["status"],
            "details": {
                k: v
                for k, v in info.items()
                if k not in ("name", "status")
            },
            "capabilities": ["boltzgen", "protenix", "pxdesign"],
            "recommended": False,
        }
        providers.append(ssh_entry)

    # --- Local GPU ---
    cuda_devices = os.environ.get("CUDA_VISIBLE_DEVICES")
    local_entry: dict[str, Any] = {
        "name": "local",
        "type": "local",
        "status": "unavailable",
        "details": {},
        "capabilities": [],
        "recommended": False,
    }
    # Detect local capabilities based on PROTEUS_*_DIR env vars
    local_caps: list[str] = []
    if os.environ.get("PROTEUS_FOLD_DIR"):
        local_caps.append("protenix")
    if os.environ.get("PROTEUS_PROT_DIR"):
        local_caps.append("pxdesign")
    if os.environ.get("PROTEUS_AB_DIR"):
        local_caps.append("boltzgen")
    local_entry["capabilities"] = local_caps

    if cuda_devices is not None:
        # Quick check for nvidia-smi
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                local_entry["status"] = "online"
                local_entry["details"] = {
                    "cuda_visible_devices": cuda_devices,
                    "gpu_info": result.stdout.strip(),
                }
            else:
                local_entry["status"] = "error"
                local_entry["details"] = {
                    "cuda_visible_devices": cuda_devices,
                    "error": "nvidia-smi failed",
                }
        except FileNotFoundError:
            local_entry["status"] = "error"
            local_entry["details"] = {"error": "nvidia-smi not found"}
        except Exception as exc:
            local_entry["status"] = "error"
            local_entry["details"] = {"error": str(exc)}
    else:
        local_entry["details"] = {"error": "CUDA_VISIBLE_DEVICES not set"}
    providers.append(local_entry)

    # --- Set recommended provider ---
    # If default_provider is configured, mark that one as recommended
    recommended_set = False
    if default_provider:
        for p in providers:
            if p["name"] == default_provider and p["status"] == "online":
                p["recommended"] = True
                recommended_set = True
                break
    # If no default set, recommend the first online provider (prefer Tamarind)
    if not recommended_set:
        for p in providers:
            if p["status"] == "online":
                p["recommended"] = True
                break

    return _ok({"providers": providers, "count": len(providers)})


# ---------------------------------------------------------------------------
# Tool 2: cloud_estimate_cost
# ---------------------------------------------------------------------------

# Estimated time per job in minutes by tool type
_TOOL_TIME_ESTIMATES: dict[str, tuple[int, int]] = {
    "boltzgen": (5, 15),
    "protenix": (2, 5),
    "pxdesign": (10, 30),
    "tap": (1, 3),
}


@mcp.tool()
async def cloud_estimate_cost(
    provider: str,
    tool: str,
    num_jobs: int = 1,
    num_designs_per_job: int = 10,
) -> str:
    """Estimate cost and quota impact BEFORE submitting compute jobs.

    Checks whether the requested jobs fit within the provider's quota and
    estimates execution time. Call this before cloud_submit_job or
    cloud_submit_batch to avoid surprise quota exhaustion.

    Args:
        provider: Provider name -- "tamarind", an SSH host name, or "local".
        tool: Tool/pipeline name (e.g. "boltzgen", "protenix", "pxdesign").
        num_jobs: Number of jobs to submit (default 1).
        num_designs_per_job: Designs per job, affects time estimate (default 10).

    Returns:
        JSON with estimated_time_minutes, jobs_within_quota, quota_after,
        provider, tool, and warnings.
    """
    provider = provider.strip().lower()
    tool = tool.strip().lower()
    warnings: list[str] = []

    # Time estimate
    time_range = _TOOL_TIME_ESTIMATES.get(tool, (5, 15))
    # Scale by designs per job (rough linear scaling)
    scale_factor = max(1.0, num_designs_per_job / 10.0)
    est_min = round(time_range[0] * num_jobs * scale_factor)
    est_max = round(time_range[1] * num_jobs * scale_factor)
    estimated_time = round((est_min + est_max) / 2)

    result: dict[str, Any] = {
        "provider": provider,
        "tool": tool,
        "num_jobs": num_jobs,
        "num_designs_per_job": num_designs_per_job,
        "estimated_time_minutes": estimated_time,
        "estimated_time_range": f"{est_min}-{est_max} min",
        "jobs_within_quota": True,
        "quota_after": None,
        "warnings": warnings,
    }

    if provider == "tamarind":
        # Fetch current quota from Tamarind /account
        key = _tam_api_key()
        if not key:
            result["jobs_within_quota"] = False
            warnings.append("TAMARIND_API_KEY not set. Cannot check quota.")
            result["warnings"] = warnings
            return _ok(result)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_tam_base_url()}/account",
                    headers=_tam_headers(),
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    acct = resp.json()
                    quota_used = acct.get("jobs_used", acct.get("usage", acct.get("quota_used")))
                    quota_limit = acct.get("jobs_limit", acct.get("limit", acct.get("quota_limit")))
                    quota_remaining = acct.get("quota_remaining", acct.get("jobs_remaining"))

                    if quota_remaining is None and quota_used is not None and quota_limit is not None:
                        try:
                            quota_remaining = int(quota_limit) - int(quota_used)
                        except (ValueError, TypeError):
                            quota_remaining = None

                    if quota_remaining is not None:
                        remaining_int = int(quota_remaining)
                        result["quota_after"] = remaining_int - num_jobs
                        result["jobs_within_quota"] = num_jobs <= remaining_int

                        if not result["jobs_within_quota"]:
                            warnings.append(
                                f"Batch of {num_jobs} jobs exceeds remaining quota "
                                f"({remaining_int} remaining). Reduce batch or switch provider."
                            )
                        elif remaining_int > 0 and num_jobs / remaining_int > 0.8:
                            warnings.append(
                                f"This batch uses {num_jobs}/{remaining_int} remaining "
                                f"quota (>{80}%). Consider reserving quota for future runs."
                            )
                    else:
                        warnings.append(
                            "Quota information not available from Tamarind API. "
                            "Proceeding without quota check."
                        )
                        result["quota_after"] = None
                else:
                    warnings.append(
                        f"Could not fetch account info (HTTP {resp.status_code}). "
                        "Quota check skipped."
                    )
        except Exception as exc:
            warnings.append(f"Failed to check Tamarind quota: {exc}")

    elif provider == "local":
        # Local GPU -- estimate GPU hours, no quota concept
        gpu_hours = round(estimated_time / 60, 2)
        result["estimated_gpu_hours"] = gpu_hours
        if not os.environ.get("CUDA_VISIBLE_DEVICES"):
            warnings.append("CUDA_VISIBLE_DEVICES not set. Local GPU may not be available.")
            result["jobs_within_quota"] = False

    else:
        # SSH host -- estimate GPU hours, no quota concept
        gpu_hours = round(estimated_time / 60, 2)
        result["estimated_gpu_hours"] = gpu_hours

    result["warnings"] = warnings
    return _ok(result)


# ---------------------------------------------------------------------------
# Tool 3: cloud_submit_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_submit_job(
    provider: str,
    tool: str,
    input_files: list[str] | None = None,
    parameters: dict | None = None,
) -> str:
    """Submit a single compute job to a cloud provider.

    Routes to Tamarind API or SSH backend based on the provider name.

    Args:
        provider: Provider name — "tamarind" or an SSH host name from config.
        tool: Tool/pipeline name (e.g. "boltzgen", "protenix", "tap").
        input_files: List of local file paths to upload as inputs.
        parameters: Tool-specific parameters dict (matches the tool schema).

    Returns:
        JSON with job_id, provider, status.
    """
    input_files = input_files or []
    parameters = parameters or {}
    provider = provider.strip().lower()

    if provider == "tamarind":
        return await _submit_tamarind(tool, input_files, parameters)

    # Check SSH hosts
    hosts = _ssh_hosts()
    host_cfg = next(
        (h for h in hosts if h.get("name", h["host"]).lower() == provider),
        None,
    )
    if host_cfg:
        return await _submit_ssh(host_cfg, tool, input_files, parameters)

    return _error(
        f"Unknown provider '{provider}'. "
        f"Use cloud_list_providers to see available options."
    )


async def _submit_tamarind(
    tool: str,
    input_files: list[str],
    parameters: dict,
) -> str:
    """Submit a job to Tamarind Bio."""
    err = _tam_check()
    if err:
        return err

    if not tool.strip():
        return _error("tool must not be empty.")

    # Upload input files first
    uploaded_refs: list[dict] = []
    for fpath in input_files:
        p = Path(fpath).resolve()
        if not p.exists():
            return _error(f"Input file not found: {p}")
        if p.stat().st_size > _TAMARIND_MAX_UPLOAD:
            return _error(
                f"File exceeds {_TAMARIND_MAX_UPLOAD // (1024 * 1024)} MB "
                f"limit: {p}"
            )

        upload_url = f"{_tam_base_url()}/files"
        try:
            file_content = p.read_bytes()
            files = {"file": (p.name, file_content, "application/octet-stream")}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    upload_url,
                    headers=_tam_headers(),
                    files=files,
                    timeout=_TAMARIND_TIMEOUT,
                )
                http_err = _tam_handle_http(resp)
                if http_err:
                    return http_err
                resp.raise_for_status()
                uploaded_refs.append(resp.json())
        except httpx.HTTPError as exc:
            return _error(f"Failed to upload {p.name} to Tamarind: {exc}")

    # Merge uploaded file references into parameters if the tool expects them
    if uploaded_refs:
        parameters["_uploaded_files"] = uploaded_refs

    job_name = _gen_id(f"by_{tool}")
    submit_url = f"{_tam_base_url()}/submit-job"
    body = {
        "jobName": job_name,
        "type": tool,
        "settings": parameters,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                submit_url,
                headers={**_tam_headers(), "Content-Type": "application/json"},
                json=body,
                timeout=_TAMARIND_TIMEOUT,
            )
            http_err = _tam_handle_http(resp)
            if http_err:
                return http_err
            resp.raise_for_status()
            data = resp.json()

            job_record = {
                "job_id": job_name,
                "provider": "tamarind",
                "tool": tool,
                "status": "submitted",
                "submitted_at": time.time(),
                "tamarind_response": data,
            }
            _jobs[job_name] = job_record

            return _ok({
                "job_id": job_name,
                "provider": "tamarind",
                "status": "submitted",
            })

    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        return _structured_error(
            "Cannot reach Tamarind API. Network may be down or API "
            "may be temporarily unavailable.",
            error_code="unreachable",
            retry_eligible=True,
            suggestion="Check your network connection. Try again in 30 seconds.",
        )
    except httpx.TimeoutException as exc:
        return _structured_error(
            f"Tamarind API request timed out after {_TAMARIND_TIMEOUT}s.",
            error_code="unreachable",
            retry_eligible=True,
            suggestion="Tamarind may be slow. Try again in a minute.",
        )
    except httpx.HTTPError as exc:
        return _structured_error(
            f"Failed to submit Tamarind job: {exc}",
            error_code="server_error",
            retry_eligible=True,
        )
    except Exception as exc:
        return _error(f"Unexpected error submitting Tamarind job: {exc}")


async def _submit_ssh(
    host_cfg: dict,
    tool: str,
    input_files: list[str],
    parameters: dict,
) -> str:
    """Submit a job to an SSH remote host."""
    host_name = host_cfg.get("name", host_cfg["host"])

    try:
        client = await asyncio.to_thread(_ssh_connect, host_cfg)
    except Exception as exc:
        return _error(f"SSH connection to {host_name} failed: {exc}")

    job_id = _gen_id(f"ssh_{tool}")
    remote_work_dir = host_cfg.get("work_dir", "/tmp/by_jobs")
    remote_job_dir = f"{remote_work_dir}/{job_id}"

    try:
        # Create remote work directory
        _stdin, _stdout, stderr = client.exec_command(
            f"mkdir -p {remote_job_dir}",
            timeout=10,
        )
        err_text = stderr.read().decode().strip()
        if err_text:
            return _error(f"Failed to create remote dir: {err_text}")

        # Upload input files via SFTP
        sftp = client.open_sftp()
        remote_files: list[str] = []
        for fpath in input_files:
            p = Path(fpath).resolve()
            if not p.exists():
                sftp.close()
                client.close()
                return _error(f"Input file not found: {p}")
            remote_path = f"{remote_job_dir}/{p.name}"
            sftp.put(str(p), remote_path)
            remote_files.append(remote_path)
        sftp.close()

        # Write parameters to a JSON file on remote
        params_json = json.dumps(parameters)
        _stdin, _stdout, _stderr = client.exec_command(
            f"cat > {remote_job_dir}/params.json << 'BY_EOF'\n"
            f"{params_json}\n"
            f"BY_EOF",
            timeout=10,
        )

        # Build and run the tool command
        tool_cmd = host_cfg.get("tool_commands", {}).get(tool)
        if not tool_cmd:
            # Default command pattern
            tool_cmd = (
                f"cd {remote_job_dir} && "
                f"python -m by.tools.{tool} "
                f"--params {remote_job_dir}/params.json "
                f"--output {remote_job_dir}/output"
            )
        else:
            tool_cmd = tool_cmd.replace("{JOB_DIR}", remote_job_dir)
            tool_cmd = tool_cmd.replace("{PARAMS}", f"{remote_job_dir}/params.json")

        # Run in background, capture PID
        bg_cmd = (
            f"nohup bash -c '{tool_cmd}' "
            f"> {remote_job_dir}/stdout.log 2> {remote_job_dir}/stderr.log & "
            f"echo $!"
        )
        _stdin, stdout, stderr = client.exec_command(bg_cmd, timeout=15)
        pid_str = stdout.read().decode().strip()
        err_text = stderr.read().decode().strip()

        if not pid_str.isdigit():
            client.close()
            return _error(
                f"Failed to start remote process. "
                f"stdout={pid_str!r}, stderr={err_text!r}"
            )

        pid = int(pid_str)
        client.close()

        job_record = {
            "job_id": job_id,
            "provider": host_name,
            "provider_type": "ssh",
            "tool": tool,
            "status": "running",
            "pid": pid,
            "host_cfg": host_cfg,
            "remote_job_dir": remote_job_dir,
            "submitted_at": time.time(),
        }
        _jobs[job_id] = job_record

        return _ok({
            "job_id": job_id,
            "provider": host_name,
            "status": "running",
            "pid": pid,
        })

    except Exception as exc:
        try:
            client.close()
        except Exception:
            pass
        return _error(f"SSH job submission failed on {host_name}: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: cloud_submit_batch
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_submit_batch(
    provider: str,
    jobs: list[dict],
    max_concurrent: int | None = None,
    force: bool = False,
) -> str:
    """Submit multiple jobs respecting concurrency limits.

    Submits up to max_concurrent jobs immediately and queues the rest.
    Each job dict must have 'tool' (str) and may have 'input_files' (list)
    and 'parameters' (dict).

    For Tamarind, performs a quota pre-check before submitting. If
    quota_remaining < len(jobs), returns an error with alternatives
    unless force=True.

    Args:
        provider: Provider name -- "tamarind" or an SSH host name.
        jobs: List of job spec dicts, each with 'tool', optional
            'input_files', and optional 'parameters'.
        max_concurrent: Maximum concurrent jobs. If None, auto-detects
            from provider tier (Tamarind) or defaults to 2 (SSH).
        force: If True, skip the quota pre-check (quota info may be stale).

    Returns:
        JSON with batch_id, job_ids, queued_count.
    """
    provider = provider.strip().lower()

    if not jobs:
        return _error("jobs list must not be empty.")

    # --- Quota pre-check for Tamarind ---
    if provider == "tamarind" and not force:
        key = _tam_api_key()
        if key:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{_tam_base_url()}/account",
                        headers=_tam_headers(),
                        timeout=10.0,
                    )
                    if resp.status_code == 200:
                        acct = resp.json()
                        quota_used = acct.get(
                            "jobs_used", acct.get("usage", acct.get("quota_used"))
                        )
                        quota_limit = acct.get(
                            "jobs_limit", acct.get("limit", acct.get("quota_limit"))
                        )
                        quota_remaining = acct.get(
                            "quota_remaining", acct.get("jobs_remaining")
                        )
                        if (
                            quota_remaining is None
                            and quota_used is not None
                            and quota_limit is not None
                        ):
                            try:
                                quota_remaining = int(quota_limit) - int(quota_used)
                            except (ValueError, TypeError):
                                quota_remaining = None

                        if quota_remaining is not None:
                            remaining_int = int(quota_remaining)
                            if remaining_int < len(jobs):
                                return _structured_error(
                                    f"Insufficient quota: {remaining_int} jobs remaining "
                                    f"but {len(jobs)} requested.",
                                    error_code="insufficient_quota",
                                    retry_eligible=False,
                                    quota_remaining=remaining_int,
                                    jobs_requested=len(jobs),
                                    suggestion=(
                                        f"Reduce batch to {remaining_int} jobs, "
                                        f"or use an alternative provider. "
                                        f"Pass force=True to override this check."
                                    ),
                                )
            except Exception:
                pass  # Quota check is best-effort; proceed on failure

    # Determine concurrency limit
    if max_concurrent is None:
        if provider == "tamarind":
            env = _load_environment()
            tier = env.get("tamarind", {}).get("tier", "free")
            max_concurrent = _TIER_CONCURRENCY.get(
                str(tier).lower(), _TIER_CONCURRENCY["free"]
            )
        else:
            max_concurrent = 2

    max_concurrent = max(1, max_concurrent)

    batch_id = _gen_id("batch")
    submitted_ids: list[str] = []
    queued_specs: list[dict] = []

    # Submit up to max_concurrent immediately
    immediate = jobs[:max_concurrent]
    remaining = jobs[max_concurrent:]

    for spec in immediate:
        tool = spec.get("tool", "")
        input_files = spec.get("input_files", [])
        parameters = spec.get("parameters", {})

        result_json = await cloud_submit_job(
            provider=provider,
            tool=tool,
            input_files=input_files,
            parameters=parameters,
        )
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            submitted_ids.append(f"error:{result_json[:100]}")
            continue

        if "error" in result:
            submitted_ids.append(f"error:{result['error'][:100]}")
        else:
            job_id = result.get("job_id", "unknown")
            submitted_ids.append(job_id)
            # Tag the job as belonging to this batch
            if job_id in _jobs:
                _jobs[job_id]["batch_id"] = batch_id

    # Queue remaining jobs
    for spec in remaining:
        queued_specs.append(spec)

    batch_record = {
        "batch_id": batch_id,
        "provider": provider,
        "submitted_ids": submitted_ids,
        "queued_specs": queued_specs,
        "max_concurrent": max_concurrent,
        "total_jobs": len(jobs),
        "created_at": time.time(),
    }
    _batches[batch_id] = batch_record

    return _ok({
        "batch_id": batch_id,
        "job_ids": submitted_ids,
        "submitted_count": len(submitted_ids),
        "queued_count": len(queued_specs),
        "total_jobs": len(jobs),
    })


# ---------------------------------------------------------------------------
# Tool 4: cloud_get_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_get_status(job_id: str, provider: str = "") -> str:
    """Get the status of a single compute job.

    Args:
        job_id: The job identifier returned by cloud_submit_job.
        provider: Provider name (optional — auto-detected from job record).

    Returns:
        JSON with status (queued/running/completed/failed), progress,
        and elapsed time.
    """
    if not job_id.strip():
        return _error("job_id must not be empty.")

    record = _jobs.get(job_id)

    # Auto-detect provider from record
    if record and not provider:
        provider = record.get("provider", "")
    provider = provider.strip().lower()

    elapsed = 0.0
    if record:
        elapsed = round(time.time() - record.get("submitted_at", time.time()), 1)

    # --- Tamarind ---
    if provider == "tamarind" or (record and record.get("provider") == "tamarind"):
        err = _tam_check()
        if err:
            return err

        # Tamarind uses job_name = job_id in our system
        url = f"{_tam_base_url()}/jobs"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, headers=_tam_headers(), timeout=_TAMARIND_TIMEOUT
                )
                http_err = _tam_handle_http(resp)
                if http_err:
                    return http_err
                resp.raise_for_status()
                data = resp.json()

                jobs_list = data if isinstance(data, list) else data.get("jobs", [data])
                matching = [j for j in jobs_list if j.get("JobName") == job_id]
                if not matching:
                    return _error(f"Job '{job_id}' not found on Tamarind.")

                job = matching[-1]
                tam_status = job.get("JobStatus", "Unknown")

                # Normalize Tamarind statuses
                status_map = {
                    "Submitted": "queued",
                    "In Queue": "queued",
                    "Running": "running",
                    "Complete": "completed",
                    "Failed": "failed",
                }
                normalized = status_map.get(tam_status, tam_status.lower())

                # Update local record
                if record:
                    record["status"] = normalized

                return _ok({
                    "job_id": job_id,
                    "provider": "tamarind",
                    "status": normalized,
                    "raw_status": tam_status,
                    "elapsed_seconds": elapsed,
                })

        except httpx.HTTPError as exc:
            return _error(f"Failed to get Tamarind job status: {exc}")
        except Exception as exc:
            return _error(f"Unexpected error getting Tamarind status: {exc}")

    # --- SSH ---
    if record and record.get("provider_type") == "ssh":
        host_cfg = record.get("host_cfg", {})
        pid = record.get("pid")

        if not pid:
            return _ok({
                "job_id": job_id,
                "provider": record.get("provider", "ssh"),
                "status": "unknown",
                "elapsed_seconds": elapsed,
                "error": "No PID recorded for this job.",
            })

        try:
            client = await asyncio.to_thread(_ssh_connect, host_cfg)
            _stdin, stdout, _stderr = client.exec_command(
                f"kill -0 {pid} 2>/dev/null && echo RUNNING || echo DONE",
                timeout=10,
            )
            result = stdout.read().decode().strip()
            client.close()

            if result == "RUNNING":
                status = "running"
            else:
                # Check exit code from the log
                remote_job_dir = record.get("remote_job_dir", "")
                try:
                    client2 = await asyncio.to_thread(_ssh_connect, host_cfg)
                    _stdin, stdout, _stderr = client2.exec_command(
                        f"cat {remote_job_dir}/stderr.log 2>/dev/null | tail -5",
                        timeout=10,
                    )
                    stderr_tail = stdout.read().decode().strip()
                    client2.close()

                    if "error" in stderr_tail.lower() or "traceback" in stderr_tail.lower():
                        status = "failed"
                    else:
                        status = "completed"
                except Exception:
                    status = "completed"

            record["status"] = status
            return _ok({
                "job_id": job_id,
                "provider": record.get("provider", "ssh"),
                "status": status,
                "pid": pid,
                "elapsed_seconds": elapsed,
            })

        except Exception as exc:
            return _error(f"SSH status check failed: {exc}")

    # Fallback: check local record
    if record:
        return _ok({
            "job_id": job_id,
            "provider": record.get("provider", "unknown"),
            "status": record.get("status", "unknown"),
            "elapsed_seconds": elapsed,
        })

    return _error(
        f"Job '{job_id}' not found. Use cloud_submit_job to create a job first."
    )


# ---------------------------------------------------------------------------
# Tool 5: cloud_get_batch_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_get_batch_status(batch_id: str) -> str:
    """Get the status of all jobs in a batch.

    Args:
        batch_id: The batch identifier returned by cloud_submit_batch.

    Returns:
        JSON with list of job statuses, overall progress (completed/total),
        and summary counts.
    """
    if not batch_id.strip():
        return _error("batch_id must not be empty.")

    batch = _batches.get(batch_id)
    if not batch:
        return _error(f"Batch '{batch_id}' not found.")

    provider = batch.get("provider", "")
    submitted_ids = batch.get("submitted_ids", [])

    job_statuses: list[dict] = []
    counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "error": 0}

    for jid in submitted_ids:
        if jid.startswith("error:"):
            job_statuses.append({
                "job_id": jid,
                "status": "error",
                "detail": jid[6:],
            })
            counts["error"] += 1
            continue

        status_json = await cloud_get_status(job_id=jid, provider=provider)
        try:
            status_data = json.loads(status_json)
        except json.JSONDecodeError:
            job_statuses.append({"job_id": jid, "status": "unknown"})
            continue

        if "error" in status_data:
            job_statuses.append({"job_id": jid, "status": "error", "detail": status_data["error"]})
            counts["error"] += 1
        else:
            st = status_data.get("status", "unknown")
            job_statuses.append({
                "job_id": jid,
                "status": st,
                "elapsed_seconds": status_data.get("elapsed_seconds"),
            })
            if st in counts:
                counts[st] += 1

    queued_remaining = len(batch.get("queued_specs", []))
    total = batch.get("total_jobs", len(submitted_ids) + queued_remaining)
    completed_total = counts["completed"] + counts["failed"]

    return _ok({
        "batch_id": batch_id,
        "provider": provider,
        "jobs": job_statuses,
        "queued_remaining": queued_remaining,
        "progress": f"{completed_total}/{total}",
        "counts": counts,
        "all_done": (completed_total + counts["error"]) >= total,
    })


# ---------------------------------------------------------------------------
# Tool 6: cloud_wait_batch
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_wait_batch(
    batch_id: str,
    poll_interval: int = 30,
    timeout: int = 3600,
) -> str:
    """Poll until all jobs in a batch complete or timeout.

    Uses exponential backoff starting at poll_interval, doubling each
    iteration up to a maximum of 120 seconds.

    Args:
        batch_id: The batch identifier returned by cloud_submit_batch.
        poll_interval: Initial polling interval in seconds (default 30).
        timeout: Maximum time to wait in seconds (default 3600).

    Returns:
        JSON with final batch status.
    """
    if not batch_id.strip():
        return _error("batch_id must not be empty.")

    batch = _batches.get(batch_id)
    if not batch:
        return _error(f"Batch '{batch_id}' not found.")

    interval = max(1, poll_interval)
    max_interval = 120
    deadline = time.monotonic() + timeout
    provider = batch.get("provider", "")

    while True:
        status_json = await cloud_get_batch_status(batch_id)
        try:
            status_data = json.loads(status_json)
        except json.JSONDecodeError:
            return status_json

        if "error" in status_data:
            return status_json

        # Check if all done
        if status_data.get("all_done", False):
            # Submit any queued jobs that can now run
            queued_specs = batch.get("queued_specs", [])
            if queued_specs:
                # Submit next batch of queued jobs
                max_c = batch.get("max_concurrent", 2)
                next_batch = queued_specs[:max_c]
                batch["queued_specs"] = queued_specs[max_c:]

                for spec in next_batch:
                    result_json = await cloud_submit_job(
                        provider=provider,
                        tool=spec.get("tool", ""),
                        input_files=spec.get("input_files", []),
                        parameters=spec.get("parameters", {}),
                    )
                    try:
                        result = json.loads(result_json)
                    except json.JSONDecodeError:
                        continue
                    if "error" not in result:
                        jid = result.get("job_id", "unknown")
                        batch["submitted_ids"].append(jid)
                        if jid in _jobs:
                            _jobs[jid]["batch_id"] = batch_id

                # Continue polling since we submitted more
                if next_batch:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return _error(
                            f"Timeout after {timeout}s waiting for batch "
                            f"'{batch_id}'."
                        )
                    await asyncio.sleep(min(interval, max_interval, remaining))
                    interval = min(interval * 2, max_interval)
                    continue

            return status_json

        # Check timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _error(
                f"Timeout after {timeout}s waiting for batch '{batch_id}'. "
                f"Progress: {status_data.get('progress', 'unknown')}"
            )

        # Sleep with exponential backoff
        sleep_time = min(interval, max_interval, remaining)
        await asyncio.sleep(sleep_time)
        interval = min(interval * 2, max_interval)


# ---------------------------------------------------------------------------
# Tool 7: cloud_get_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def cloud_get_results(
    job_id: str,
    output_dir: str,
    provider: str = "",
) -> str:
    """Download results from a completed job.

    For Tamarind: fetches results via the jobs API (Score field contains
    output data and metrics).
    For SSH: downloads output files from the remote job directory via SFTP.

    Args:
        job_id: The job identifier.
        output_dir: Local directory to save result files.
        provider: Provider name (optional — auto-detected from job record).

    Returns:
        JSON with list of downloaded file paths and any result data.
    """
    if not job_id.strip():
        return _error("job_id must not be empty.")

    out_path = Path(output_dir).resolve()
    try:
        out_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _error(f"Cannot create output directory: {exc}")

    record = _jobs.get(job_id)
    if record and not provider:
        provider = record.get("provider", "")
    provider = provider.strip().lower()

    # --- Tamarind results ---
    if provider == "tamarind" or (record and record.get("provider") == "tamarind"):
        err = _tam_check()
        if err:
            return err

        url = f"{_tam_base_url()}/jobs"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, headers=_tam_headers(), timeout=_TAMARIND_TIMEOUT
                )
                http_err = _tam_handle_http(resp)
                if http_err:
                    return http_err
                resp.raise_for_status()
                data = resp.json()

                jobs_list = data if isinstance(data, list) else data.get("jobs", [data])
                matching = [j for j in jobs_list if j.get("JobName") == job_id]

                if not matching:
                    return _error(f"Job '{job_id}' not found on Tamarind.")

                job = matching[-1]
                tam_status = job.get("JobStatus", "Unknown")

                if tam_status != "Complete":
                    return _error(
                        f"Job '{job_id}' is not complete "
                        f"(status: {tam_status}). Wait for completion first."
                    )

                # Parse and save Score (results)
                score = job.get("Score")
                if isinstance(score, str) and score.strip():
                    try:
                        score = json.loads(score)
                    except json.JSONDecodeError:
                        score = {"raw": score}
                elif not isinstance(score, dict):
                    score = {}

                results_file = out_path / f"{job_id}_results.json"
                results_file.write_text(json.dumps(score, indent=2))

                downloaded: list[str] = [str(results_file)]

                # Check for downloadable file URLs in results
                if isinstance(score, dict):
                    for key, val in score.items():
                        if isinstance(val, str) and val.startswith("http"):
                            try:
                                file_resp = await client.get(
                                    val,
                                    headers=_tam_headers(),
                                    timeout=120.0,
                                )
                                if file_resp.status_code == 200:
                                    fname = key.replace("/", "_")
                                    fpath = out_path / fname
                                    fpath.write_bytes(file_resp.content)
                                    downloaded.append(str(fpath))
                            except Exception:
                                pass

                return _ok({
                    "job_id": job_id,
                    "provider": "tamarind",
                    "output_dir": str(out_path),
                    "files": downloaded,
                    "results": score,
                })

        except httpx.HTTPError as exc:
            return _error(f"Failed to get Tamarind results: {exc}")
        except Exception as exc:
            return _error(f"Unexpected error getting Tamarind results: {exc}")

    # --- SSH results ---
    if record and record.get("provider_type") == "ssh":
        host_cfg = record.get("host_cfg", {})
        remote_job_dir = record.get("remote_job_dir", "")

        if not remote_job_dir:
            return _error("No remote job directory recorded for this job.")

        try:
            client = await asyncio.to_thread(_ssh_connect, host_cfg)
            sftp = client.open_sftp()

            # List files in the remote output directory
            remote_output = f"{remote_job_dir}/output"
            downloaded: list[str] = []

            try:
                remote_files = sftp.listdir(remote_output)
            except FileNotFoundError:
                # Fall back to entire job dir
                remote_files = sftp.listdir(remote_job_dir)
                remote_output = remote_job_dir

            for fname in remote_files:
                remote_path = f"{remote_output}/{fname}"
                local_path = out_path / fname
                try:
                    sftp.get(remote_path, str(local_path))
                    downloaded.append(str(local_path))
                except Exception:
                    # Skip directories and unreadable files
                    pass

            # Also grab stdout/stderr logs
            for log_name in ["stdout.log", "stderr.log"]:
                try:
                    remote_log = f"{remote_job_dir}/{log_name}"
                    local_log = out_path / f"{job_id}_{log_name}"
                    sftp.get(remote_log, str(local_log))
                    downloaded.append(str(local_log))
                except Exception:
                    pass

            sftp.close()
            client.close()

            return _ok({
                "job_id": job_id,
                "provider": record.get("provider", "ssh"),
                "output_dir": str(out_path),
                "files": downloaded,
            })

        except Exception as exc:
            return _error(f"SSH result download failed: {exc}")

    return _error(
        f"Job '{job_id}' not found or provider not determined. "
        f"Provide the provider name explicitly."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
