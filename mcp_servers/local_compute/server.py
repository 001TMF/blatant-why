"""Local compute MCP Server — run Proteus tools on local or SSH-remote GPUs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Add project root so shared imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp_servers._shared.base import _error
from src.proteus_cli.common import TOOL_PATHS, detect_local_tools, get_available_providers
from src.proteus_cli.ssh_runner import (
    SSHConfig,
    ssh_check_gpu,
    ssh_check_tools,
    ssh_run_design_job,
)

mcp = FastMCP("proteus-local")


# ---------------------------------------------------------------------------
# Tool 1: local_detect_tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def local_detect_tools() -> str:
    """Check which Proteus tools are installed locally.

    Inspects the configured tool paths (override with PROTEUS_FOLD_DIR,
    PROTEUS_PROT_DIR, PROTEUS_AB_DIR environment variables).

    Returns:
        JSON object mapping tool name to availability status, plus
        the resolved paths and available compute providers.
    """
    tools = detect_local_tools()
    providers = get_available_providers()
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
        "proteus-ab", "run", str(spec),
        "--output", str(output_dir),
        "--num_designs", str(num_designs),
        "--budget", str(budget),
    ]
    if extra_args:
        cmd.extend(extra_args.split())

    env = dict(os.environ)
    env["PROTEUS_MODELS_DIR"] = os.getenv(
        "PROTEUS_MODELS_DIR", str(Path.home() / ".cache" / "proteus-ab")
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
    """Check which Proteus tools are installed on a remote SSH server.

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
        tools = ssh_check_tools(config)
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
        gpu_info = ssh_check_gpu(config)
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
    """Run a Proteus design job on a remote GPU server via SSH.

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
        result = ssh_run_design_job(
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
