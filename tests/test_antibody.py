"""Tests for proteus_cli.antibody module."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from proteus_cli.antibody import (
    PROTOCOLS,
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


class TestBuildDesignSpec:
    """Tests for build_design_spec."""

    def test_build_spec_creates_yaml(self, tmp_path):
        """Spec file is written as valid, loadable YAML with correct structure."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        spec_path = build_design_spec(
            target_pdb=pdb,
            target_chains=["A"],
            epitope_residues=[45, 50, 52],
            output_dir=tmp_path,
        )

        assert spec_path.exists()
        assert spec_path.name == "design_spec.yaml"

        with open(spec_path) as fh:
            cfg = yaml.safe_load(fh)

        assert cfg["target"]["pdb_path"] == str(pdb)
        assert cfg["target"]["chains"] == ["A"]
        assert cfg["target"]["epitope_residues"] == [45, 50, 52]
        assert cfg["protocol"] == "nanobody-anything"
        assert cfg["design"]["num_designs"] == 10
        assert cfg["output"]["directory"] == str(tmp_path)

    def test_build_spec_default_protocol(self, tmp_path):
        """Default protocol is nanobody-anything."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        spec_path = build_design_spec(
            target_pdb=pdb,
            target_chains=["A"],
            epitope_residues=[45],
            output_dir=tmp_path,
        )

        with open(spec_path) as fh:
            cfg = yaml.safe_load(fh)

        assert cfg["protocol"] == "nanobody-anything"

    def test_build_spec_custom_params(self, tmp_path):
        """Custom budget, diversity_alpha, and msa_mode appear in spec."""
        pdb = tmp_path / "target.pdb"
        pdb.touch()

        spec_path = build_design_spec(
            target_pdb=pdb,
            target_chains=["A", "B"],
            epitope_residues=[10, 20, 30],
            protocol="antibody-anything",
            num_designs=50,
            output_dir=tmp_path,
            prefilter=False,
            msa_mode="colabfold",
            budget=200,
            diversity_alpha=0.8,
        )

        with open(spec_path) as fh:
            cfg = yaml.safe_load(fh)

        assert cfg["protocol"] == "antibody-anything"
        assert cfg["design"]["budget"] == 200
        assert cfg["design"]["diversity_alpha"] == 0.8
        assert cfg["design"]["msa_mode"] == "colabfold"
        assert cfg["design"]["prefilter"] is False
        assert cfg["design"]["num_designs"] == 50
        assert cfg["target"]["chains"] == ["A", "B"]


class TestRunAntibodyDesign:
    """Tests for run_antibody_design."""

    def test_run_antibody_validates_tool(self, tmp_path, monkeypatch):
        """validate_tool_path is called with 'proteus-ab'."""
        import proteus_cli.antibody as antibody_mod

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

        monkeypatch.setattr(antibody_mod, "validate_tool_path", mock_validate)
        monkeypatch.setattr(antibody_mod, "run_command", mock_run)

        spec = tmp_path / "design_spec.yaml"
        spec.touch()

        result = run_antibody_design(spec)

        assert calls == ["proteus-ab"]
        assert result.status == "success"
        assert result.tool == "proteus-ab"


class TestParseAntibodyResults:
    """Tests for parse_antibody_results."""

    def test_parse_results_empty_dir(self, tmp_path):
        """Returns empty list when no CSV found."""
        results = parse_antibody_results(tmp_path)
        assert results == []

    def test_parse_results_from_csv(self, tmp_path):
        """Parses a mock final_designs_metrics_run1.csv correctly and sorts by ipTM descending."""
        csv_path = tmp_path / "final_designs_metrics_run1.csv"
        csv_path.write_text(
            "design_name,ipTM,pLDDT,ca_rmsd,sequence\n"
            "nb_design_1,0.72,85.3,2.1,EVQLVESGGGLVQPGG\n"
            "nb_design_2,0.91,92.1,1.2,QVQLVESGGGLVQAGG\n"
            "nb_design_3,0.85,88.7,1.8,DVQLVESGGGLVQPGG\n"
        )

        results = parse_antibody_results(tmp_path)

        assert len(results) == 3
        # Sorted by ipTM descending
        assert results[0]["design_name"] == "nb_design_2"
        assert results[0]["ipTM"] == 0.91
        assert results[1]["design_name"] == "nb_design_3"
        assert results[1]["ipTM"] == 0.85
        assert results[2]["design_name"] == "nb_design_1"
        assert results[2]["ipTM"] == 0.72
        # Verify all fields are present
        for r in results:
            assert "design_name" in r
            assert "ipTM" in r
            assert "pLDDT" in r
            assert "ca_rmsd" in r
            assert "sequence" in r
        # Verify specific field values for the top design
        assert results[0]["pLDDT"] == 92.1
        assert results[0]["ca_rmsd"] == 1.2
        assert results[0]["sequence"] == "QVQLVESGGGLVQAGG"
