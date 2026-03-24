"""Tests for proteus_cli.fold module."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from proteus_cli.fold import (
    MODELS,
    build_protenix_json,
    parse_fold_output,
    run_fold,
)


# ---------------------------------------------------------------------------
# build_protenix_json
# ---------------------------------------------------------------------------


class TestBuildProtenixJson:
    """Tests for build_protenix_json."""

    def test_build_protenix_json_basic(self, tmp_path: Path) -> None:
        """Builds correct JSON structure from a list of sequence strings."""
        seqs = ["MGSSHHH", "EVQLVES"]
        json_path = build_protenix_json(seqs, tmp_path, name="test_pred")

        assert json_path.exists()
        payload = json.loads(json_path.read_text())

        # Top-level is a list with one entry.
        assert isinstance(payload, list)
        assert len(payload) == 1

        entry = payload[0]
        assert entry["name"] == "test_pred"
        assert entry["modelSeeds"] == [42]
        assert entry["sampleCount"] == 1
        assert len(entry["sequences"]) == 2

        # Each sequence is wrapped as proteinChain.
        for i, seq_str in enumerate(seqs):
            chain = entry["sequences"][i]
            assert "proteinChain" in chain
            assert chain["proteinChain"]["sequence"] == seq_str
            assert chain["proteinChain"]["count"] == 1

    def test_build_protenix_json_custom_seeds(self, tmp_path: Path) -> None:
        """Custom seeds and sample_count are respected."""
        json_path = build_protenix_json(
            ["AAA"],
            tmp_path,
            seeds=[1, 2, 3],
            sample_count=5,
        )
        payload = json.loads(json_path.read_text())
        assert payload[0]["modelSeeds"] == [1, 2, 3]
        assert payload[0]["sampleCount"] == 5

    def test_build_protenix_json_dict_input(self, tmp_path: Path) -> None:
        """Handles dict sequence input with explicit type."""
        seqs = [
            {"sequence": "MGSS", "type": "proteinChain"},
            {"sequence": "CCD_MG", "type": "ligand"},
        ]
        json_path = build_protenix_json(seqs, tmp_path)
        payload = json.loads(json_path.read_text())

        entries = payload[0]["sequences"]
        assert "proteinChain" in entries[0]
        assert entries[0]["proteinChain"]["sequence"] == "MGSS"
        assert "ligand" in entries[1]
        assert entries[1]["ligand"]["sequence"] == "CCD_MG"

    def test_build_protenix_json_dict_default_type(self, tmp_path: Path) -> None:
        """Dict input without explicit type defaults to proteinChain."""
        seqs = [{"sequence": "ACDE"}]
        json_path = build_protenix_json(seqs, tmp_path)
        payload = json.loads(json_path.read_text())
        assert "proteinChain" in payload[0]["sequences"][0]

    def test_build_protenix_json_creates_output_dir(self, tmp_path: Path) -> None:
        """Creates the output directory if it does not exist."""
        out = tmp_path / "nested" / "dir"
        json_path = build_protenix_json(["AAA"], out)
        assert json_path.exists()
        assert out.is_dir()


# ---------------------------------------------------------------------------
# MODELS dict
# ---------------------------------------------------------------------------


class TestModelsDict:
    """Tests for the MODELS constant."""

    def test_models_dict_has_expected_keys(self) -> None:
        """MODELS contains base_default, base_20250630, and mini."""
        assert "base_default" in MODELS
        assert "base_20250630" in MODELS
        assert "mini" in MODELS

    def test_model_names_follow_protenix_convention(self) -> None:
        """All model values start with 'protenix_'."""
        for key, name in MODELS.items():
            assert name.startswith("protenix_"), f"{key} has unexpected name: {name}"


# ---------------------------------------------------------------------------
# run_fold
# ---------------------------------------------------------------------------


class TestRunFold:
    """Tests for run_fold."""

    def test_run_fold_validates_tool_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """validate_tool_path is called for 'proteus-fold'."""
        called_with: list[str] = []

        def fake_validate(tool_name: str) -> Path:
            called_with.append(tool_name)
            return Path("/fake/protenix")

        def fake_run_command(cmd, cwd=None, timeout=3600, env=None):
            from types import SimpleNamespace

            return SimpleNamespace(returncode=1, stdout="", stderr="no gpu")

        import proteus_cli.fold as fold_mod

        def fake_get_tool_env(name: str) -> dict[str, str]:
            return dict(os.environ)

        monkeypatch.setattr(fold_mod, "validate_tool_path", fake_validate)
        monkeypatch.setattr(fold_mod, "run_command", fake_run_command)
        monkeypatch.setattr(fold_mod, "get_tool_env", fake_get_tool_env)

        # Need a real input file for the path-exists check.
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump([], f)
            f.flush()
            run_fold(f.name)

        assert called_with == ["protenix"]

    def test_run_fold_unknown_model_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown model key returns an error ToolResult without calling the tool."""
        import proteus_cli.fold as fold_mod

        monkeypatch.setattr(
            fold_mod, "validate_tool_path", lambda _: Path("/fake")
        )
        result = run_fold("/dev/null", model="nonexistent")
        assert result.status == "error"
        assert "nonexistent" in (result.error or "")

    def test_run_fold_missing_input_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing input JSON returns an error ToolResult."""
        import proteus_cli.fold as fold_mod

        monkeypatch.setattr(
            fold_mod, "validate_tool_path", lambda _: Path("/fake")
        )
        result = run_fold("/no/such/file.json")
        assert result.status == "error"
        assert "not found" in (result.error or "")


# ---------------------------------------------------------------------------
# parse_fold_output
# ---------------------------------------------------------------------------


class TestParseFoldOutput:
    """Tests for parse_fold_output."""

    def test_parse_fold_output_empty(self, tmp_path: Path) -> None:
        """Handles a missing or empty output directory gracefully."""
        # Non-existent directory.
        assert parse_fold_output(tmp_path / "nope") == {}
        # Existing but empty directory.
        assert parse_fold_output(tmp_path) == {}

    def test_parse_fold_output_reads_confidence(self, tmp_path: Path) -> None:
        """Parses summary_confidence JSON files and extracts metrics."""
        scores = {
            "iptm": 0.85,
            "ptm": 0.78,
            "plddt": 91.2,
            "ranking_score": 0.83,
        }
        fname = "pred_summary_confidence_sample_0.json"
        (tmp_path / fname).write_text(json.dumps(scores))

        result = parse_fold_output(tmp_path)
        assert result["iptm"] == 0.85
        assert result["ptm"] == 0.78
        assert result["plddt"] == 91.2
        assert result["ranking_score"] == 0.83

    def test_parse_fold_output_picks_best(self, tmp_path: Path) -> None:
        """When multiple samples exist, picks the one with highest ranking_score."""
        worse = {"iptm": 0.5, "ptm": 0.4, "plddt": 60.0, "ranking_score": 0.3}
        better = {"iptm": 0.9, "ptm": 0.88, "plddt": 95.0, "ranking_score": 0.9}

        (tmp_path / "pred_summary_confidence_sample_0.json").write_text(
            json.dumps(worse)
        )
        (tmp_path / "pred_summary_confidence_sample_1.json").write_text(
            json.dumps(better)
        )

        result = parse_fold_output(tmp_path)
        assert result["ranking_score"] == 0.9
        assert result["iptm"] == 0.9

    def test_parse_fold_output_handles_list_values(self, tmp_path: Path) -> None:
        """Values serialised as single-element lists are unwrapped."""
        scores = {
            "iptm": [0.77],
            "ptm": [0.65],
            "plddt": [88.0],
            "ranking_score": [0.72],
        }
        (tmp_path / "x_summary_confidence_sample_0.json").write_text(
            json.dumps(scores)
        )
        result = parse_fold_output(tmp_path)
        assert result["iptm"] == 0.77

    def test_parse_fold_output_ignores_malformed_json(self, tmp_path: Path) -> None:
        """Gracefully skips files that are not valid JSON."""
        (tmp_path / "bad_summary_confidence_sample_0.json").write_text("NOT JSON!")
        assert parse_fold_output(tmp_path) == {}
