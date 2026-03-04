"""Shared utilities for Proteus CLI wrappers."""
from __future__ import annotations

import json
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


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
