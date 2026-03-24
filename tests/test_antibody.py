"""Tests for proteus_cli.antibody module."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from proteus_cli.antibody import (
    PROTOCOLS,
    _residues_to_ranges,
    build_design_spec,
    parse_antibody_results,
    run_antibody_design,
)


class TestProtocols:
    """Tests for the PROTOCOLS constant."""

    def test_protocols_has_expected_keys(self):
        """PROTOCOLS contains both 'nanobody-anything' and 'antibody-anything'."""
        assert "nanobody-anything" in PROTOCOLS
        assert "antibody-anything" in PROTOCOLS
        assert PROTOCOLS["nanobody-anything"] == "nanobody-anything"
        assert PROTOCOLS["antibody-anything"] == "antibody-anything"


class TestResidueToRanges:
    """Tests for the _residues_to_ranges helper."""

    def test_contiguous_range(self):
        assert _residues_to_ranges([7, 8, 9, 10, 11, 12]) == "7..12"

    def test_multiple_ranges(self):
        assert _residues_to_ranges([7, 8, 9, 10, 11, 12, 27, 28, 29, 30, 31, 32, 33, 34]) == "7..12,27..34"

    def test_single_residue(self):
        assert _residues_to_ranges([42]) == "42"

    def test_empty(self):
        assert _residues_to_ranges([]) == ""


class TestBuildDesignSpec:
    """Tests for build_design_spec."""

    def test_build_spec_creates_yaml(self, tmp_path):
        """Spec file is written as valid, loadable YAML with entities structure."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        spec_path = build_design_spec(
            target_pdb=pdb,
            target_chains=["A"],
            binding_residues={"A": [45, 50, 52]},
            output_dir=tmp_path,
        )

        assert spec_path.exists()
        assert spec_path.name == "design_spec.yaml"

        with open(spec_path) as fh:
            cfg = yaml.safe_load(fh)

        assert "entities" in cfg
        assert len(cfg["entities"]) >= 1
        target_entity = cfg["entities"][0]
        assert target_entity["file"]["path"] == str(pdb)
        assert target_entity["file"]["include"][0]["chain"]["id"] == "A"

    def test_build_spec_binding_types(self, tmp_path):
        """Binding residues are converted to range notation in binding_types."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        spec_path = build_design_spec(
            target_pdb=pdb,
            target_chains=["A"],
            binding_residues={"A": [7, 8, 9, 10, 11, 12, 27, 28, 29, 30]},
            output_dir=tmp_path,
        )

        with open(spec_path) as fh:
            cfg = yaml.safe_load(fh)

        target_entity = cfg["entities"][0]
        binding_types = target_entity["file"]["binding_types"]
        assert len(binding_types) == 1
        assert binding_types[0]["chain"]["id"] == "A"
        assert "7..12" in binding_types[0]["chain"]["binding"]
        assert "27..30" in binding_types[0]["chain"]["binding"]

    def test_build_spec_with_scaffolds(self, tmp_path):
        """Scaffold paths produce a second entity."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        spec_path = build_design_spec(
            target_pdb=pdb,
            target_chains=["A"],
            scaffold_paths=["/data/scaffolds/adalimumab.yaml"],
            output_dir=tmp_path,
        )

        with open(spec_path) as fh:
            cfg = yaml.safe_load(fh)

        assert len(cfg["entities"]) == 2
        assert cfg["entities"][1]["file"]["path"] == "/data/scaffolds/adalimumab.yaml"


class TestRunAntibodyDesign:
    """Tests for run_antibody_design."""

    def test_run_antibody_validates_tool(self, tmp_path, monkeypatch):
        """validate_tool_path is called with 'proteus-ab'."""
        import proteus_cli.antibody as antibody_mod

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

        monkeypatch.setattr(antibody_mod, "validate_tool_path", mock_validate)
        monkeypatch.setattr(antibody_mod, "run_command", mock_run)
        monkeypatch.setattr(antibody_mod, "get_tool_env", mock_get_tool_env)

        spec = tmp_path / "design_spec.yaml"
        spec.touch()

        result = run_antibody_design(spec)

        assert calls == ["boltzgen"]
        assert result.status == "success"
        assert result.tool == "boltzgen"


class TestParseAntibodyResults:
    """Tests for parse_antibody_results."""

    def test_parse_results_empty_dir(self, tmp_path):
        """Returns empty list when no CSV found."""
        results = parse_antibody_results(tmp_path)
        assert results == []

    def test_parse_results_from_csv(self, tmp_path):
        """Parses a mock final_designs_metrics CSV correctly and sorts by iptm descending."""
        ranked_dir = tmp_path / "final_ranked_designs"
        ranked_dir.mkdir()
        csv_path = ranked_dir / "final_designs_metrics_run1.csv"
        csv_path.write_text(
            "design_id,iptm,ptm,plddt,design_iptm,ipsae_min,rmsd,sequence\n"
            "nb_design_1,0.72,0.70,85.3,0.68,0.55,2.1,EVQLVESGGGLVQPGG\n"
            "nb_design_2,0.91,0.89,92.1,0.88,0.82,1.2,QVQLVESGGGLVQAGG\n"
            "nb_design_3,0.85,0.82,88.7,0.80,0.70,1.8,DVQLVESGGGLVQPGG\n"
        )

        results = parse_antibody_results(tmp_path)

        assert len(results) == 3
        # Sorted by iptm descending
        assert results[0]["design_id"] == "nb_design_2"
        assert results[0]["iptm"] == 0.91
        assert results[1]["design_id"] == "nb_design_3"
        assert results[1]["iptm"] == 0.85
        assert results[2]["design_id"] == "nb_design_1"
        assert results[2]["iptm"] == 0.72
        # Verify key fields present
        for r in results:
            assert "design_id" in r
            assert "iptm" in r
            assert "plddt" in r
            assert "ipsae_min" in r
            assert "sequence" in r
