"""Tests for proteus_cli.protein module."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from proteus_cli.protein import (
    PRESETS,
    build_pxdesign_config,
    parse_design_results,
    run_protein_design,
)


class TestPresets:
    """Tests for the PRESETS constant."""

    def test_presets_has_expected_keys(self):
        """PRESETS contains both 'preview' and 'extended'."""
        assert "preview" in PRESETS
        assert "extended" in PRESETS
        assert PRESETS["preview"] == "preview"
        assert PRESETS["extended"] == "extended"


class TestBuildPxdesignConfig:
    """Tests for build_pxdesign_config."""

    def test_build_config_creates_yaml(self, tmp_path):
        """Config file is written as valid, loadable YAML."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        config_path = build_pxdesign_config(
            target_pdb=pdb,
            target_chains=["A"],
            output_dir=tmp_path,
        )

        assert config_path.exists()
        assert config_path.name == "pxdesign_config.yaml"

        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        assert cfg["target"]["pdb_path"] == str(pdb)
        assert cfg["target"]["chains"] == ["A"]
        assert cfg["design"]["preset"] == "extended"
        assert cfg["design"]["num_designs"] == 10
        assert cfg["output"]["directory"] == str(tmp_path)

    def test_build_config_with_hotspots(self, tmp_path):
        """Hotspot residues appear in the written config."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()
        hotspots = ["A45", "A50", "A52"]

        config_path = build_pxdesign_config(
            target_pdb=pdb,
            target_chains=["A"],
            hotspot_residues=hotspots,
            output_dir=tmp_path,
        )

        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        assert cfg["target"]["hotspot_residues"] == hotspots

    def test_build_config_without_hotspots(self, tmp_path):
        """Config is valid without hotspot_residues."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        config_path = build_pxdesign_config(
            target_pdb=pdb,
            target_chains=["A", "B"],
            output_dir=tmp_path,
        )

        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        assert "hotspot_residues" not in cfg["target"]
        assert cfg["target"]["chains"] == ["A", "B"]


class TestRunProteinDesign:
    """Tests for run_protein_design."""

    def test_run_protein_validates_tool(self, tmp_path, monkeypatch):
        """validate_tool_path is called with 'proteus-prot'."""
        import proteus_cli.protein as protein_mod

        calls: list[str] = []

        def mock_validate(name: str) -> Path:
            calls.append(name)
            return tmp_path

        def mock_run(cmd, cwd=None, timeout=3600):
            """Return a fake successful CompletedProcess."""

            class FakeProc:
                returncode = 0
                stdout = ""
                stderr = ""

            return FakeProc()

        monkeypatch.setattr(protein_mod, "validate_tool_path", mock_validate)
        monkeypatch.setattr(protein_mod, "run_command", mock_run)

        config = tmp_path / "pxdesign_config.yaml"
        config.touch()

        result = run_protein_design(config)

        assert calls == ["proteus-prot"]
        assert result.status == "success"
        assert result.tool == "proteus-prot"


class TestParseDesignResults:
    """Tests for parse_design_results."""

    def test_parse_results_empty_dir(self, tmp_path):
        """Returns empty list when summary.csv is missing."""
        results = parse_design_results(tmp_path)
        assert results == []

    def test_parse_results_from_csv(self, tmp_path):
        """Parses a mock summary.csv correctly and sorts by score descending."""
        csv_path = tmp_path / "summary.csv"
        csv_path.write_text(
            "design_name,score,sc_score,mpnn_score\n"
            "design_1,0.75,0.60,0.80\n"
            "design_2,0.92,0.85,0.70\n"
            "design_3,0.88,0.72,0.91\n"
        )

        results = parse_design_results(tmp_path)

        assert len(results) == 3
        # Sorted by score descending
        assert results[0]["design_name"] == "design_2"
        assert results[0]["score"] == 0.92
        assert results[1]["design_name"] == "design_3"
        assert results[1]["score"] == 0.88
        assert results[2]["design_name"] == "design_1"
        assert results[2]["score"] == 0.75
        # Verify all fields are present
        for r in results:
            assert "design_name" in r
            assert "score" in r
            assert "sc_score" in r
            assert "mpnn_score" in r
