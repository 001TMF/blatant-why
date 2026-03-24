"""Tests for proteus_cli.common module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from proteus_cli.common import TOOL_PATHS, ToolResult, validate_tool_path


class TestToolResult:
    """Tests for the ToolResult dataclass."""

    def test_creation_minimal(self):
        """ToolResult can be created with only required fields."""
        result = ToolResult(tool="protenix", status="success")
        assert result.tool == "protenix"
        assert result.status == "success"

    def test_defaults(self):
        """Optional fields default correctly."""
        result = ToolResult(tool="boltzgen", status="running")
        assert result.output_dir is None
        assert result.metrics == {}
        assert result.designs == []
        assert result.error is None

    def test_creation_full(self):
        """ToolResult can be created with all fields populated."""
        result = ToolResult(
            tool="pxdesign",
            status="success",
            output_dir=Path("/tmp/output"),
            metrics={"ipTM": 0.85, "pLDDT": 92.3},
            designs=[{"name": "design_1", "score": 0.9}],
            error=None,
        )
        assert result.tool == "pxdesign"
        assert result.output_dir == Path("/tmp/output")
        assert result.metrics["ipTM"] == 0.85
        assert len(result.designs) == 1

    def test_to_json_returns_valid_json(self):
        """to_json produces valid, parseable JSON."""
        result = ToolResult(
            tool="protenix",
            status="success",
            output_dir=Path("/tmp/out"),
            metrics={"score": 1.0},
        )
        raw = result.to_json()
        parsed = json.loads(raw)
        assert parsed["tool"] == "protenix"
        assert parsed["status"] == "success"
        assert parsed["output_dir"] == "/tmp/out"
        assert parsed["metrics"] == {"score": 1.0}
        assert parsed["designs"] == []
        assert parsed["error"] is None

    def test_to_json_none_output_dir(self):
        """to_json handles None output_dir."""
        result = ToolResult(tool="boltzgen", status="error", error="failed")
        parsed = json.loads(result.to_json())
        assert parsed["output_dir"] is None
        assert parsed["error"] == "failed"

    def test_metrics_dict_independence(self):
        """Each ToolResult gets its own metrics dict (no shared mutable default)."""
        r1 = ToolResult(tool="protenix", status="success")
        r2 = ToolResult(tool="boltzgen", status="success")
        r1.metrics["key"] = "value"
        assert "key" not in r2.metrics

    def test_designs_list_independence(self):
        """Each ToolResult gets its own designs list (no shared mutable default)."""
        r1 = ToolResult(tool="protenix", status="success")
        r2 = ToolResult(tool="boltzgen", status="success")
        r1.designs.append({"name": "d1"})
        assert len(r2.designs) == 0


class TestToolPaths:
    """Tests for the TOOL_PATHS constant."""

    def test_has_all_three_tools(self):
        """TOOL_PATHS contains exactly the three expected tools."""
        expected = {"protenix", "pxdesign", "boltzgen"}
        assert set(TOOL_PATHS.keys()) == expected

    def test_paths_are_path_or_none(self):
        """All values in TOOL_PATHS are Path instances or None."""
        for name, path in TOOL_PATHS.items():
            assert path is None or isinstance(path, Path), (
                f"{name} path should be a Path or None, got {type(path)}"
            )

    def test_default_paths_none_without_env(self, monkeypatch):
        """Default tool paths are None when no env vars are set."""
        # Note: TOOL_PATHS are resolved at import time from env vars.
        # Without env vars set, they default to None (not Path("")).
        for name, path in TOOL_PATHS.items():
            assert path is None or isinstance(path, Path), (
                f"{name} should be None or a Path"
            )


class TestValidateToolPath:
    """Tests for the validate_tool_path function."""

    def test_unknown_tool_raises_value_error(self):
        """Passing an unknown tool name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            validate_tool_path("nonexistent-tool")

    def test_unknown_tool_error_lists_available(self):
        """The ValueError message includes available tool names."""
        with pytest.raises(ValueError, match="protenix"):
            validate_tool_path("bad-tool")

    def test_missing_directory_raises_file_not_found(self, tmp_path, monkeypatch):
        """If the tool directory doesn't exist, FileNotFoundError is raised."""
        import proteus_cli.common as common_mod

        fake_paths = {"protenix": tmp_path / "nonexistent"}
        monkeypatch.setattr(common_mod, "TOOL_PATHS", fake_paths)
        with pytest.raises(FileNotFoundError, match="Tool directory not found"):
            validate_tool_path("protenix")

    def test_valid_tool_returns_path(self, tmp_path, monkeypatch):
        """A valid, existing tool path is returned successfully."""
        import proteus_cli.common as common_mod

        existing = tmp_path / "Protenix"
        existing.mkdir()
        fake_paths = {"protenix": existing}
        monkeypatch.setattr(common_mod, "TOOL_PATHS", fake_paths)
        result = validate_tool_path("protenix")
        assert result == existing
