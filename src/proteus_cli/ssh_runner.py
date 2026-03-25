"""SSH remote execution for Proteus tools on GPU servers."""
from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SSHConfig:
    """SSH connection configuration."""
    host: str = ""
    user: str = ""
    port: int = 22
    key_path: str = ""
    tools_path: str = "/opt/proteus"  # remote tool installation path
    workspace: str = "/tmp/proteus"    # remote workspace for job files

    @classmethod
    def from_env(cls) -> SSHConfig:
        """Build SSHConfig from environment variables."""
        return cls(
            host=os.getenv("PROTEUS_SSH_HOST", ""),
            user=os.getenv("PROTEUS_SSH_USER", os.getenv("USER", "")),
            port=int(os.getenv("PROTEUS_SSH_PORT", "22")),
            key_path=os.getenv("PROTEUS_SSH_KEY", ""),
            tools_path=os.getenv("PROTEUS_SSH_TOOLS_PATH", "/opt/proteus"),
            workspace=os.getenv("PROTEUS_SSH_WORKSPACE", "/tmp/proteus"),
        )

    @property
    def is_configured(self) -> bool:
        """Return True if the minimum SSH config (host) is set."""
        return bool(self.host)


def _ssh_base_cmd(config: SSHConfig) -> list[str]:
    """Build base SSH command with options."""
    cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes"]
    if config.port != 22:
        cmd.extend(["-p", str(config.port)])
    if config.key_path:
        cmd.extend(["-i", config.key_path])
    cmd.append(f"{config.user}@{config.host}")
    return cmd


def _scp_cmd(
    config: SSHConfig, local_path: str, remote_path: str, upload: bool = True,
) -> list[str]:
    """Build SCP command for file transfer."""
    cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes"]
    if config.port != 22:
        cmd.extend(["-P", str(config.port)])
    if config.key_path:
        cmd.extend(["-i", config.key_path])
    remote = f"{config.user}@{config.host}:{remote_path}"
    if upload:
        cmd.extend([local_path, remote])
    else:
        cmd.extend([remote, local_path])
    return cmd


def ssh_run_command(
    config: SSHConfig, remote_cmd: str, timeout: int = 3600,
) -> subprocess.CompletedProcess:
    """Execute a command on the remote server via SSH."""
    cmd = _ssh_base_cmd(config) + [remote_cmd]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ssh_upload_file(config: SSHConfig, local_path: str, remote_path: str) -> bool:
    """Upload a file to the remote server.

    Creates the remote parent directory if it does not exist.
    """
    remote_dir = str(Path(remote_path).parent)
    ssh_run_command(config, f"mkdir -p {remote_dir}")
    cmd = _scp_cmd(config, local_path, remote_path, upload=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0


def ssh_download_file(config: SSHConfig, remote_path: str, local_path: str) -> bool:
    """Download a file from the remote server."""
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = _scp_cmd(config, local_path, remote_path, upload=False)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0


def ssh_download_dir(config: SSHConfig, remote_dir: str, local_dir: str) -> bool:
    """Download a directory recursively from the remote server."""
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    cmd = _scp_cmd(config, local_dir, remote_dir, upload=False)
    cmd.insert(1, "-r")  # recursive flag
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return result.returncode == 0


def ssh_check_tools(config: SSHConfig) -> dict[str, bool]:
    """Check which Proteus tools are available on the remote server."""
    tools: dict[str, bool] = {}
    for name, subdir in [
        ("protenix", "Protenix"),
        ("pxdesign", "PXDesign"),
        ("boltzgen", "boltzgen"),
    ]:
        result = ssh_run_command(
            config,
            f"test -d {config.tools_path}/{subdir} && echo yes || echo no",
        )
        tools[name] = result.stdout.strip() == "yes"
    return tools


def ssh_check_gpu(config: SSHConfig) -> dict:
    """Check GPU availability on the remote server.

    Returns a dict with 'available' (bool) and 'gpus' (list of dicts
    with 'name' and 'memory' keys).
    """
    result = ssh_run_command(
        config,
        "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader "
        "2>/dev/null || echo 'no gpu'",
    )
    if "no gpu" in result.stdout:
        return {"available": False, "gpus": []}
    gpus = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split(", ")
        if len(parts) == 2:
            gpus.append({"name": parts[0].strip(), "memory": parts[1].strip()})
    return {"available": bool(gpus), "gpus": gpus}


def ssh_run_design_job(
    config: SSHConfig,
    tool: str,
    config_file: str,
    output_dir: str,
    extra_args: str = "",
) -> dict:
    """Run a design job on the remote server.

    Workflow:
    1. Upload config file to a unique remote workspace.
    2. Execute the tool command remotely.
    3. Download results to the local output directory.

    Returns a dict with 'success', 'job_id', 'output_dir', and
    'remote_workspace' on success, or 'error' on failure.
    """
    job_id = str(uuid.uuid4())[:8]
    remote_workspace = f"{config.workspace}/job_{job_id}"
    remote_config = f"{remote_workspace}/config.yaml"
    remote_output = f"{remote_workspace}/output"

    # Setup remote workspace
    ssh_run_command(config, f"mkdir -p {remote_workspace}")

    # Upload config
    if not ssh_upload_file(config, config_file, remote_config):
        return {"success": False, "error": "Failed to upload config file"}

    # Build tool command
    tool_cmds = {
        "protenix": (
            f"cd {config.tools_path}/Protenix && "
            f"protenix pred -i {remote_config} -o {remote_output} "
            f"--use_default_params true --dtype bf16"
        ),
        "pxdesign": (
            f"cd {config.tools_path}/PXDesign && "
            f"pxdesign pipeline -i {remote_config} -o {remote_output} "
            f"{extra_args}"
        ),
        "boltzgen": (
            f"cd {config.tools_path}/boltzgen && "
            f"boltzgen run {remote_config} --output {remote_output} "
            f"{extra_args}"
        ),
    }

    cmd = tool_cmds.get(tool)
    if not cmd:
        return {"success": False, "error": f"Unknown tool: {tool}"}

    # Execute remotely (2 hour timeout for long design runs)
    result = ssh_run_command(config, cmd, timeout=7200)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr[-500:] if result.stderr else "Unknown error",
            "job_id": job_id,
        }

    # Download results
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    if not ssh_download_dir(config, remote_output, output_dir):
        return {
            "success": False,
            "error": "Failed to download results",
            "job_id": job_id,
        }

    return {
        "success": True,
        "job_id": job_id,
        "output_dir": output_dir,
        "remote_workspace": remote_workspace,
    }
