"""Shared utilities for Proteus CLI wrappers."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    """Standardized result from any Proteus tool invocation."""
    tool: str
    status: str  # "success", "error", "running"
    output_dir: Path | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    designs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "tool": self.tool,
                "status": self.status,
                "output_dir": str(self.output_dir) if self.output_dir else None,
                "metrics": self.metrics,
                "designs": self.designs,
                "error": self.error,
            },
            indent=2,
        )


def _resolve_tool_path(*env_vars: str) -> Path | None:
    """Return a Path from the first set env var, or None if all are empty.

    Path("") resolves to "." which always passes .exists(), causing
    false-positive tool detection.  This helper avoids that.
    """
    for var in env_vars:
        value = os.getenv(var, "")
        if value:
            return Path(value)
    return None


# Default tool paths — override via environment variables
TOOL_PATHS: dict[str, Path | None] = {
    "protenix": _resolve_tool_path("PROTEUS_FOLD_DIR", "PROTENIX_DIR"),
    "pxdesign": _resolve_tool_path("PROTEUS_PROT_DIR", "PXDESIGN_DIR"),
    "boltzgen": _resolve_tool_path("PROTEUS_AB_DIR", "BOLTZGEN_DIR"),
}


def detect_local_tools() -> dict[str, bool]:
    """Check which local tools are available."""
    result = {}
    for name, path in TOOL_PATHS.items():
        if path is None or str(path) == "" or str(path) == ".":
            result[name] = False
            continue
        # Check for actual tool indicator (setup.py, pyproject.toml, or src/)
        result[name] = path.exists() and (
            (path / "setup.py").exists()
            or (path / "pyproject.toml").exists()
            or (path / "src").exists()
        )
    return result


def get_available_providers() -> list[str]:
    """Detect available compute providers.

    Checks for local tools, cloud API keys, and SSH configuration
    and returns a list of provider names that are ready to use.
    """
    providers = []
    local = detect_local_tools()
    if any(local.values()):
        providers.append("local")
    if os.getenv("TAMARIND_API_KEY"):
        providers.append("tamarind")
    if os.getenv("PROTEUS_SSH_HOST"):
        providers.append("ssh")
    return providers if providers else ["tamarind"]  # default fallback


def validate_tool_path(tool_name: str) -> Path:
    if tool_name not in TOOL_PATHS:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_PATHS)}")
    path = TOOL_PATHS[tool_name]
    if path is None or str(path) == "" or str(path) == ".":
        raise FileNotFoundError(
            f"Tool directory not configured for {tool_name}. "
            f"Set the appropriate environment variable (e.g. PROTEUS_FOLD_DIR)."
        )
    if not path.exists():
        raise FileNotFoundError(f"Tool directory not found: {path}")
    return path


def get_tool_env(tool_name: str) -> dict[str, str]:
    """Return environment variables needed for a specific tool."""
    base = dict(os.environ)
    tool_dir = TOOL_PATHS.get(tool_name)
    if tool_dir is None:
        raise FileNotFoundError(
            f"Tool directory not configured for {tool_name}. "
            f"Set the appropriate environment variable."
        )

    if tool_name == "protenix":
        base["PROTENIX_ROOT_DIR"] = str(tool_dir)
    elif tool_name == "pxdesign":
        base["PROTENIX_DATA_ROOT_DIR"] = str(tool_dir / "release_data" / "ccd_cache")
        base["TOOL_WEIGHTS_ROOT"] = str(tool_dir / "tool_weights")
        base.setdefault("CUTLASS_PATH", str(Path.home() / "cutlass"))
    elif tool_name == "boltzgen":
        base["PROTEUS_MODELS_DIR"] = str(Path.home() / ".cache" / "boltzgen")
        base["LAYERNORM_TYPE"] = "openfold"

    return base


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 3600,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        env=env,
    )
