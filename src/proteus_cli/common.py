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


TOOL_PATHS = {
    "proteus-fold": Path("/data/proteus/Protenix"),
    "proteus-prot": Path("/data/proteus/PXDesign"),
    "proteus-ab": Path("/data/proteus/proteus-design"),
}


def validate_tool_path(tool_name: str) -> Path:
    path = TOOL_PATHS.get(tool_name)
    if path is None:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_PATHS)}")
    if not path.exists():
        raise FileNotFoundError(f"Tool directory not found: {path}")
    return path


def get_tool_env(tool_name: str) -> dict[str, str]:
    """Return environment variables needed for a specific tool."""
    base = dict(os.environ)
    tool_dir = TOOL_PATHS[tool_name]

    if tool_name == "proteus-fold":
        base["PROTENIX_ROOT_DIR"] = str(tool_dir)
    elif tool_name == "proteus-prot":
        base["PROTENIX_DATA_ROOT_DIR"] = str(tool_dir / "release_data" / "ccd_cache")
        base["TOOL_WEIGHTS_ROOT"] = str(tool_dir / "tool_weights")
        base.setdefault("CUTLASS_PATH", str(Path.home() / "cutlass"))
    elif tool_name == "proteus-ab":
        base["PROTEUS_MODELS_DIR"] = str(Path.home() / ".cache" / "proteus-ab")
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
