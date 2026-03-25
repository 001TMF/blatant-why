#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///
"""Local compute MCP Server — run BY tools on local or SSH-remote GPUs.

Self-contained: all tool detection and SSH logic is inlined. No proteus_cli dependency.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP


# ===========================================================================
# Inlined tool detection and SSH logic (replaces proteus_cli.common + ssh_runner)
# ===========================================================================


# ---------------------------------------------------------------------------
# Tool paths  (replaces proteus_cli.common.TOOL_PATHS)
# ---------------------------------------------------------------------------

def _get_tool_paths() -> dict[str, Path]:
    """Resolve tool installation paths from environment variables or defaults."""
    default_base = Path(os.environ.get("BY_TOOLS_DIR", str(Path.home() / ".local" / "share" / "by-tools")))
    return {
        "protenix": Path(os.environ.get("PROTEUS_FOLD_DIR", os.environ.get("PROTENIX_DIR", str(default_base / "Protenix")))),
        "pxdesign": Path(os.environ.get("PROTEUS_PROT_DIR", os.environ.get("PXDESIGN_DIR", str(default_base / "PXDesign")))),
        "boltzgen": Path(os.environ.get("PROTEUS_AB_DIR", os.environ.get("BOLTZGEN_DIR", str(default_base / "proteus-design")))),
    }


TOOL_PATHS = _get_tool_paths()


def _detect_local_tools() -> dict[str, dict]:
    """Check which BY tools are installed locally."""
    tools: dict[str, dict] = {}
    for name, path in TOOL_PATHS.items():
        tools[name] = {
            "installed": path.exists(),
            "path": str(path),
        }
        # Check for CLI binary
        cli_names = {
            "protenix": "protenix",
            "pxdesign": "pxdesign",
            "boltzgen": "boltzgen",
        }
        cli = cli_names.get(name, name)
        tools[name]["cli_available"] = shutil.which(cli) is not None
    return tools


def _get_available_providers() -> list[str]:
    """Detect available compute providers from environment."""
    providers = []
    if os.environ.get("TAMARIND_API_KEY"):
        providers.append("tamarind")
    if os.environ.get("PROTEUS_SSH_HOST"):
        providers.append("ssh")
    # Check for local GPU
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            providers.append("local_gpu")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Check for local tool installations
    for name, path in TOOL_PATHS.items():
        if path.exists():
            providers.append(f"local_{name}")
    return providers


# ---------------------------------------------------------------------------
# SSH config  (replaces proteus_cli.ssh_runner.SSHConfig)
# ---------------------------------------------------------------------------

@dataclass
class SSHConfig:
    """SSH connection configuration."""
    host: str = ""
    user: str = ""
    port: int = 22
    key_path: str = ""
    tools_path: str = ""

    @classmethod
    def from_env(cls) -> SSHConfig:
        """Build config from environment variables."""
        return cls(
            host=os.environ.get("PROTEUS_SSH_HOST", ""),
            user=os.environ.get("PROTEUS_SSH_USER", os.environ.get("USER", "")),
            port=int(os.environ.get("PROTEUS_SSH_PORT", "22")),
            key_path=os.environ.get("PROTEUS_SSH_KEY", ""),
            tools_path=os.environ.get("BY_SSH_TOOLS_PATH", os.environ.get("PROTEUS_SSH_TOOLS_PATH", str(Path.home() / ".local" / "share" / "by-tools"))),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    def _ssh_base_cmd(self) -> list[str]:
        """Build base SSH command with options."""
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
        if self.key_path:
            cmd.extend(["-i", self.key_path])
        if self.port != 22:
            cmd.extend(["-p", str(self.port)])
        target = f"{self.user}@{self.host}" if self.user else self.host
        cmd.append(target)
        return cmd


def _ssh_run_command(config: SSHConfig, command: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command on a remote SSH server."""
    cmd = config._ssh_base_cmd() + [command]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ssh_check_gpu(config: SSHConfig) -> dict:
    """Check GPU availability on remote SSH server."""
    try:
        result = _ssh_run_command(
            config,
            "nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader",
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "gpus": [], "error": "SSH nvidia-smi timed out"}

    if result.returncode != 0:
        return {"available": False, "gpus": [], "error": result.stderr.strip()[:200]}

    gpus = []
    for line in result.stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            gpus.append({
                "name": parts[0],
                "memory_total": parts[1],
                "memory_free": parts[2],
                "driver_version": parts[3],
            })
        elif len(parts) >= 2:
            gpus.append({"name": parts[0], "memory_total": parts[1]})

    return {"available": bool(gpus), "gpus": gpus}


def _ssh_check_tools(config: SSHConfig) -> dict[str, bool]:
    """Check which BY tools are available on remote server."""
    tools_dir = config.tools_path
    result: dict[str, bool] = {}
    tool_dirs = {
        "protenix": "Protenix",
        "pxdesign": "PXDesign",
        "boltzgen": "proteus-design",
    }
    for tool, dirname in tool_dirs.items():
        try:
            check = _ssh_run_command(config, f"test -d {tools_dir}/{dirname} && echo yes || echo no", timeout=10)
            result[tool] = check.stdout.strip() == "yes"
        except (subprocess.TimeoutExpired, Exception):
            result[tool] = False
    return result


def _ssh_run_design_job(
    config: SSHConfig,
    tool: str,
    config_path: str,
    output_dir: str,
    extra_args: str = "",
) -> dict:
    """Run a design job on remote GPU server via SSH.

    Uploads the config file, runs the tool, and downloads results.
    """
    import uuid as _uuid

    job_id = f"{tool}-{_uuid.uuid4().hex[:8]}"
    remote_work = f"/tmp/by-jobs/{job_id}"
    local_config = Path(config_path)
    local_output = Path(output_dir)
    local_output.mkdir(parents=True, exist_ok=True)

    # Build SCP base
    scp_opts = ["-o", "StrictHostKeyChecking=no"]
    if config.key_path:
        scp_opts.extend(["-i", config.key_path])
    if config.port != 22:
        scp_opts.extend(["-P", str(config.port)])
    target = f"{config.user}@{config.host}" if config.user else config.host

    try:
        # Create remote work dir
        _ssh_run_command(config, f"mkdir -p {remote_work}", timeout=10)

        # Upload config
        scp_cmd = ["scp"] + scp_opts + [str(local_config), f"{target}:{remote_work}/"]
        subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30, check=True)

        # Build run command
        remote_config = f"{remote_work}/{local_config.name}"
        remote_output = f"{remote_work}/output"

        tool_cmds = {
            "protenix": (
                f"cd {config.tools_path}/Protenix && "
                f"PROTENIX_ROOT_DIR={config.tools_path}/Protenix "
                f"protenix pred -i {remote_config} -o {remote_output} "
                f"-n base_default --use_default_params true --dtype bf16 {extra_args}"
            ),
            "pxdesign": (
                f"cd {config.tools_path}/PXDesign && "
                f"pxdesign pipeline --preset extended "
                f"-i {remote_config} -o {remote_output} "
                f"--N_sample 500 --dtype bf16 {extra_args}"
            ),
            "boltzgen": (
                f"cd {config.tools_path}/proteus-design && "
                f"boltzgen run {remote_config} "
                f"--output {remote_output} {extra_args}"
            ),
        }

        run_cmd = tool_cmds.get(tool, "")
        if not run_cmd:
            return {"success": False, "error": f"Unknown tool: {tool}", "job_id": job_id}

        # Run the tool
        result = _ssh_run_command(config, run_cmd, timeout=7200)

        if result.returncode != 0:
            return {
                "success": False,
                "job_id": job_id,
                "error": result.stderr[-500:] if result.stderr else "Unknown error",
                "stdout_tail": result.stdout[-500:] if result.stdout else "",
            }

        # Download results
        scp_dl = ["scp", "-r"] + scp_opts + [f"{target}:{remote_output}/", str(local_output)]
        subprocess.run(scp_dl, capture_output=True, text=True, timeout=300, check=True)

        # Cleanup remote
        _ssh_run_command(config, f"rm -rf {remote_work}", timeout=10)

        return {
            "success": True,
            "job_id": job_id,
            "output_dir": str(local_output),
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "job_id": job_id, "error": "SSH job timed out"}
    except subprocess.CalledProcessError as exc:
        return {"success": False, "job_id": job_id, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "job_id": job_id, "error": str(exc)}


# ===========================================================================
# MCP Server
# ===========================================================================


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})

mcp = FastMCP("by-local-compute")


# ---------------------------------------------------------------------------
# Tool 1: local_detect_tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def local_detect_tools() -> str:
    """Check which BY tools are installed locally.

    Inspects the configured tool paths (override with PROTEUS_FOLD_DIR,
    PROTEUS_PROT_DIR, PROTEUS_AB_DIR environment variables).

    Returns:
        JSON object mapping tool name to availability status, plus
        the resolved paths and available compute providers.
    """
    tools = _detect_local_tools()
    providers = _get_available_providers()
    return json.dumps(
        {
            "tools": tools,
            "paths": {name: str(path) for name, path in TOOL_PATHS.items()},
            "available_providers": providers,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 2: local_detect_gpu
# ---------------------------------------------------------------------------


@mcp.tool()
async def local_detect_gpu() -> str:
    """Check local GPU availability via nvidia-smi.

    Returns:
        JSON object with 'available' (bool) and 'gpus' (list of GPU info
        dicts with 'name' and 'memory' keys).
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return json.dumps({"available": False, "gpus": [], "error": "nvidia-smi not found"})
    except subprocess.TimeoutExpired:
        return json.dumps({"available": False, "gpus": [], "error": "nvidia-smi timed out"})

    if result.returncode != 0:
        return json.dumps(
            {"available": False, "gpus": [], "error": result.stderr.strip()[:200]}
        )

    gpus = []
    for line in result.stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            gpus.append({
                "name": parts[0],
                "memory_total": parts[1],
                "memory_free": parts[2],
                "driver_version": parts[3],
            })
        elif len(parts) >= 2:
            gpus.append({"name": parts[0], "memory_total": parts[1]})

    return json.dumps({"available": bool(gpus), "gpus": gpus}, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: local_run_boltzgen
# ---------------------------------------------------------------------------


@mcp.tool()
async def local_run_boltzgen(
    spec_yaml: str,
    output_dir: str,
    num_designs: int = 100,
    budget: int = 10,
    extra_args: str = "",
) -> str:
    """Run BoltzGen locally for antibody/nanobody design.

    Args:
        spec_yaml: Path to the entities YAML spec file.
        output_dir: Directory to write output designs.
        num_designs: Number of designs to generate (default 100).
        budget: Number of top designs to keep after ranking (default 10).
        extra_args: Additional CLI arguments (optional).

    Returns:
        JSON object with success status, output directory, and any errors.
    """
    tool_path = TOOL_PATHS["boltzgen"]
    if not tool_path.exists():
        return _error(
                f"BoltzGen not found at {tool_path}. "
                f"Set PROTEUS_AB_DIR or BOLTZGEN_DIR to override."
            )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    spec = Path(spec_yaml).resolve()
    if not spec.exists():
        return _error(f"Spec file not found: {spec}")

    cmd = [
        "boltzgen", "run", str(spec),
        "--output", str(output_dir),
        "--num_designs", str(num_designs),
        "--budget", str(budget),
    ]
    if extra_args:
        cmd.extend(extra_args.split())

    env = dict(os.environ)
    env["PROTEUS_MODELS_DIR"] = os.getenv(
        "PROTEUS_MODELS_DIR", str(Path.home() / ".cache" / "boltzgen")
    )
    env["LAYERNORM_TYPE"] = "openfold"

    try:
        result = subprocess.run(
            cmd, cwd=str(tool_path), capture_output=True, text=True,
            timeout=7200, env=env,
        )
    except subprocess.TimeoutExpired:
        return _error("BoltzGen run timed out after 2 hours")

    if result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": result.stderr[-500:] if result.stderr else "Unknown error",
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
        })

    return json.dumps({
        "success": True,
        "output_dir": str(output_dir),
        "stdout_tail": result.stdout[-500:] if result.stdout else "",
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 4: local_run_pxdesign
# ---------------------------------------------------------------------------


@mcp.tool()
async def local_run_pxdesign(
    config_yaml: str,
    output_dir: str,
    preset: str = "extended",
    n_sample: int = 500,
    extra_args: str = "",
) -> str:
    """Run PXDesign locally for de novo protein binder design.

    Args:
        config_yaml: Path to the PXDesign YAML config file.
        output_dir: Directory to write output designs.
        preset: PXDesign preset (default "extended").
        n_sample: Number of samples to generate (default 500).
        extra_args: Additional CLI arguments (optional).

    Returns:
        JSON object with success status, output directory, and any errors.
    """
    tool_path = TOOL_PATHS["pxdesign"]
    if not tool_path.exists():
        return _error(
                f"PXDesign not found at {tool_path}. "
                f"Set PROTEUS_PROT_DIR or PXDESIGN_DIR to override."
            )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    config = Path(config_yaml).resolve()
    if not config.exists():
        return _error(f"Config file not found: {config}")

    cmd = [
        "pxdesign", "pipeline",
        "--preset", preset,
        "-i", str(config),
        "-o", str(output_dir),
        "--N_sample", str(n_sample),
        "--dtype", "bf16",
    ]
    if extra_args:
        cmd.extend(extra_args.split())

    env = dict(os.environ)
    env["PROTENIX_DATA_ROOT_DIR"] = str(tool_path / "release_data" / "ccd_cache")
    env["TOOL_WEIGHTS_ROOT"] = str(tool_path / "tool_weights")
    env.setdefault("CUTLASS_PATH", str(Path.home() / "cutlass"))

    try:
        result = subprocess.run(
            cmd, cwd=str(tool_path), capture_output=True, text=True,
            timeout=7200, env=env,
        )
    except subprocess.TimeoutExpired:
        return _error("PXDesign run timed out after 2 hours")

    if result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": result.stderr[-500:] if result.stderr else "Unknown error",
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
        })

    return json.dumps({
        "success": True,
        "output_dir": str(output_dir),
        "stdout_tail": result.stdout[-500:] if result.stdout else "",
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 5: local_run_protenix
# ---------------------------------------------------------------------------


@mcp.tool()
async def local_run_protenix(
    input_json: str,
    output_dir: str,
    model: str = "base_default",
    extra_args: str = "",
) -> str:
    """Run Protenix locally for structure prediction.

    Args:
        input_json: Path to the Protenix input JSON file.
        output_dir: Directory to write prediction output.
        model: Model name to use (default "base_default").
        extra_args: Additional CLI arguments (optional).

    Returns:
        JSON object with success status, output directory, and any errors.
    """
    tool_path = TOOL_PATHS["protenix"]
    if not tool_path.exists():
        return _error(
                f"Protenix not found at {tool_path}. "
                f"Set PROTEUS_FOLD_DIR or PROTENIX_DIR to override."
            )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    inp = Path(input_json).resolve()
    if not inp.exists():
        return _error(f"Input JSON not found: {inp}")

    cmd = [
        "protenix", "pred",
        "-i", str(inp),
        "-o", str(output_dir),
        "-n", model,
        "--use_default_params", "true",
        "--dtype", "bf16",
    ]
    if extra_args:
        cmd.extend(extra_args.split())

    env = dict(os.environ)
    env["PROTENIX_ROOT_DIR"] = str(tool_path)

    try:
        result = subprocess.run(
            cmd, cwd=str(tool_path), capture_output=True, text=True,
            timeout=7200, env=env,
        )
    except subprocess.TimeoutExpired:
        return _error("Protenix run timed out after 2 hours")

    if result.returncode != 0:
        return json.dumps({
            "success": False,
            "error": result.stderr[-500:] if result.stderr else "Unknown error",
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
        })

    return json.dumps({
        "success": True,
        "output_dir": str(output_dir),
        "stdout_tail": result.stdout[-500:] if result.stdout else "",
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 6: ssh_detect_tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def ssh_detect_tools_remote(
    host: str = "",
    user: str = "",
    port: int = 0,
    key_path: str = "",
    tools_path: str = "",
) -> str:
    """Check which BY tools are installed on a remote SSH server.

    Args:
        host: SSH hostname (default from PROTEUS_SSH_HOST env var).
        user: SSH username (default from PROTEUS_SSH_USER env var).
        port: SSH port (default from PROTEUS_SSH_PORT or 22).
        key_path: Path to SSH key (default from PROTEUS_SSH_KEY env var).
        tools_path: Remote tools directory (default from PROTEUS_SSH_TOOLS_PATH).

    Returns:
        JSON object mapping tool name to availability on the remote server.
    """
    config = SSHConfig.from_env()
    if host:
        config.host = host
    if user:
        config.user = user
    if port:
        config.port = port
    if key_path:
        config.key_path = key_path
    if tools_path:
        config.tools_path = tools_path

    if not config.is_configured:
        return _error(
                "SSH not configured. Set PROTEUS_SSH_HOST or pass host parameter."
            )

    try:
        tools = _ssh_check_tools(config)
    except Exception as exc:
        return _error(f"SSH connection failed: {exc}")

    return json.dumps({"host": config.host, "tools": tools}, indent=2)


# ---------------------------------------------------------------------------
# Tool 7: ssh_detect_gpu
# ---------------------------------------------------------------------------


@mcp.tool()
async def ssh_detect_gpu_remote(
    host: str = "",
    user: str = "",
    port: int = 0,
    key_path: str = "",
) -> str:
    """Check GPU availability on a remote SSH server.

    Args:
        host: SSH hostname (default from PROTEUS_SSH_HOST env var).
        user: SSH username (default from PROTEUS_SSH_USER env var).
        port: SSH port (default from PROTEUS_SSH_PORT or 22).
        key_path: Path to SSH key (default from PROTEUS_SSH_KEY env var).

    Returns:
        JSON object with 'available' (bool) and 'gpus' (list of GPU info).
    """
    config = SSHConfig.from_env()
    if host:
        config.host = host
    if user:
        config.user = user
    if port:
        config.port = port
    if key_path:
        config.key_path = key_path

    if not config.is_configured:
        return _error(
                "SSH not configured. Set PROTEUS_SSH_HOST or pass host parameter."
            )

    try:
        gpu_info = _ssh_check_gpu(config)
    except Exception as exc:
        return _error(f"SSH connection failed: {exc}")

    return json.dumps({"host": config.host, **gpu_info}, indent=2)


# ---------------------------------------------------------------------------
# Tool 8: ssh_run_job
# ---------------------------------------------------------------------------


@mcp.tool()
async def ssh_run_job(
    tool: str,
    config_path: str,
    output_dir: str,
    extra_args: str = "",
    host: str = "",
    user: str = "",
    port: int = 0,
    key_path: str = "",
    tools_path: str = "",
) -> str:
    """Run a BY design job on a remote GPU server via SSH.

    Uploads the config file, executes the tool remotely, and downloads
    the results.

    Args:
        tool: Tool to run ("protenix", "pxdesign", or "boltzgen").
        config_path: Local path to the config/spec file.
        output_dir: Local directory to download results to.
        extra_args: Additional CLI arguments for the tool (optional).
        host: SSH hostname (default from PROTEUS_SSH_HOST env var).
        user: SSH username (default from PROTEUS_SSH_USER env var).
        port: SSH port (default from PROTEUS_SSH_PORT or 22).
        key_path: Path to SSH key (default from PROTEUS_SSH_KEY env var).
        tools_path: Remote tools directory (default from PROTEUS_SSH_TOOLS_PATH).

    Returns:
        JSON object with success status, job_id, output_dir, and any errors.
    """
    valid_tools = {"protenix", "pxdesign", "boltzgen"}
    if tool not in valid_tools:
        return _error(f"Unknown tool: {tool}. Must be one of: {sorted(valid_tools)}")

    config = SSHConfig.from_env()
    if host:
        config.host = host
    if user:
        config.user = user
    if port:
        config.port = port
    if key_path:
        config.key_path = key_path
    if tools_path:
        config.tools_path = tools_path

    if not config.is_configured:
        return _error(
                "SSH not configured. Set PROTEUS_SSH_HOST or pass host parameter."
            )

    if not Path(config_path).exists():
        return _error(f"Config file not found: {config_path}")

    try:
        result = _ssh_run_design_job(
            config, tool, config_path, output_dir, extra_args=extra_args,
        )
    except Exception as exc:
        return _error(f"SSH job execution failed: {exc}")

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
