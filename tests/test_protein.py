"""Tests for proteus_cli.protein module."""
from __future__ import annotations

import os
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
        """Config file is written as valid, loadable YAML with correct structure."""
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

        assert cfg["target"]["file"] == str(pdb)
        assert "A" in cfg["target"]["chains"]
        assert cfg["binder_length"] == 100

    def test_build_config_with_hotspots(self, tmp_path):
        """Hotspot residues appear in the per-chain config."""
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

        assert cfg["target"]["chains"]["A"]["hotspots"] == [45, 50, 52]

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

        assert "A" in cfg["target"]["chains"]
        assert "B" in cfg["target"]["chains"]

    def test_build_config_with_crop_and_msa(self, tmp_path):
        """Crop ranges and MSA dirs appear in per-chain config."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        config_path = build_pxdesign_config(
            target_pdb=pdb,
            target_chains=["A"],
            crop_ranges={"A": ["1-116"]},
            msa_dirs={"A": "./msa/chain_A"},
            output_dir=tmp_path,
        )

        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        assert cfg["target"]["chains"]["A"]["crop"] == ["1-116"]
        assert cfg["target"]["chains"]["A"]["msa"] == "./msa/chain_A"


class TestRunProteinDesign:
    """Tests for run_protein_design."""

    def test_run_protein_validates_tool(self, tmp_path, monkeypatch):
        """validate_tool_path is called with 'proteus-prot'."""
        import proteus_cli.protein as protein_mod

        calls: list[str] = []

        def mock_validate(name: str) -> Path:
            calls.append(name)
            return tmp_path

        def mock_run(cmd, cwd=None, timeout=3600, env=None):
            """Return a fake successful CompletedProcess."""

            class FakeProc:
                returncode = 0
                stdout = ""
                stderr = ""

            return FakeProc()

        def mock_get_tool_env(name: str) -> dict[str, str]:
            return dict(os.environ)

        monkeypatch.setattr(protein_mod, "validate_tool_path", mock_validate)
        monkeypatch.setattr(protein_mod, "run_command", mock_run)
        monkeypatch.setattr(protein_mod, "get_tool_env", mock_get_tool_env)

        config = tmp_path / "pxdesign_config.yaml"
        config.touch()

        result = run_protein_design(config)

        assert calls == ["pxdesign"]
        assert result.status == "success"
        assert result.tool == "pxdesign"


class TestParseDesignResults:
    """Tests for parse_design_results."""

    def test_parse_results_empty_dir(self, tmp_path):
        """Returns empty list when summary.csv is missing."""
        results = parse_design_results(tmp_path)
        assert results == []

    def test_parse_results_from_csv(self, tmp_path):
        """Parses a mock summary.csv correctly and sorts by ptx_iptm descending."""
        csv_path = tmp_path / "summary.csv"
        csv_path.write_text(
            "rank,name,sequence,af2_opt_success,af2_easy_success,ptx_success,ptx_basic_success,ptx_iptm,af2_binder_plddt,af2_complex_pred_design_rmsd\n"
            "1,design_1,AAAAAA,True,True,True,True,0.75,85.0,2.1\n"
            "2,design_2,BBBBBB,True,True,True,True,0.92,90.0,1.2\n"
            "3,design_3,CCCCCC,True,True,True,True,0.88,87.0,1.8\n"
        )

        results = parse_design_results(tmp_path)

        assert len(results) == 3
        # Sorted by ptx_iptm descending
        assert results[0]["name"] == "design_2"
        assert results[0]["ptx_iptm"] == 0.92
        assert results[1]["name"] == "design_3"
        assert results[1]["ptx_iptm"] == 0.88
        assert results[2]["name"] == "design_1"
        assert results[2]["ptx_iptm"] == 0.75
        # Verify key fields are present
        for r in results:
            assert "name" in r
            assert "sequence" in r
            assert "ptx_iptm" in r
