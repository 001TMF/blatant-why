"""End-to-end tests for the Proteus protein design agent pipeline.

These tests simulate full design workflows WITHOUT requiring network access
or GPU.  All tool invocations are mocked/monkeypatched so the tests run
entirely in-process with temporary directories.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from proteus_cli.common import ToolResult
from proteus_cli.main import cli
from proteus_cli.protein import build_pxdesign_config, parse_design_results
from proteus_cli.antibody import build_design_spec, parse_antibody_results
from proteus_cli.scoring.ipsae import interpret_ipsae
from proteus_cli.screening.liabilities import scan_liabilities, compute_net_charge
from proteus_cli.screening.developability import assess_developability


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_PDB_CONTENT = """\
HEADER    MOCK TARGET FOR TESTING
ATOM      1  N   ALA A   1       1.000   2.000   3.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       2.000   3.000   4.000  1.00  0.00           C
ATOM      3  C   ALA A   1       3.000   4.000   5.000  1.00  0.00           C
ATOM      4  O   ALA A   1       4.000   5.000   6.000  1.00  0.00           O
ATOM      5  N   GLY A   2       5.000   6.000   7.000  1.00  0.00           N
ATOM      6  CA  GLY A   2       6.000   7.000   8.000  1.00  0.00           C
ATOM      7  C   GLY A   2       7.000   8.000   9.000  1.00  0.00           C
ATOM      8  O   GLY A   2       8.000   9.000  10.000  1.00  0.00           O
END
"""

# A realistic antibody-like sequence with some known liability motifs
# for comprehensive screening tests.
DESIGN_SEQUENCE = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDNGWFAYWGQGTLVTVSS"

# A clean, short sequence for low-risk developability tests.
CLEAN_SEQUENCE = "EVQLVESGGGLVQAGGSLRLSCAASGRTFSEYAMAWFRQAPGKEREFVAAITK"


def _write_mock_pdb(tmp_path: Path) -> Path:
    """Write a mock PDB file and return its path."""
    pdb_path = tmp_path / "target.pdb"
    pdb_path.write_text(MOCK_PDB_CONTENT)
    return pdb_path


def _write_pxdesign_summary_csv(output_dir: Path) -> Path:
    """Write a mock PXDesign summary.csv with 5 fake designs."""
    csv_path = output_dir / "summary.csv"
    csv_path.write_text(
        "rank,name,sequence,af2_opt_success,af2_easy_success,ptx_success,ptx_basic_success,ptx_iptm,af2_binder_plddt,af2_complex_pred_design_rmsd\n"
        "1,design_001,AAAAA,True,True,True,True,0.92,88.0,1.5\n"
        "2,design_002,BBBBB,True,True,True,True,0.87,82.0,2.1\n"
        "3,design_003,CCCCC,True,True,True,True,0.95,91.0,1.2\n"
        "4,design_004,DDDDD,True,True,True,True,0.78,70.0,3.0\n"
        "5,design_005,EEEEE,True,True,True,True,0.83,79.0,2.5\n"
    )
    return csv_path


def _write_antibody_metrics_csv(output_dir: Path) -> Path:
    """Write a mock proteus-ab final_designs_metrics CSV with fake designs."""
    ranked_dir = output_dir / "final_ranked_designs"
    ranked_dir.mkdir(exist_ok=True)
    csv_path = ranked_dir / "final_designs_metrics_run1.csv"
    csv_path.write_text(
        "design_id,iptm,ptm,plddt,design_iptm,ipsae_min,rmsd,sequence\n"
        f"nb_design_1,0.82,0.80,90.5,0.78,0.65,1.5,{DESIGN_SEQUENCE}\n"
        f"nb_design_2,0.91,0.89,93.2,0.88,0.82,1.1,{CLEAN_SEQUENCE}\n"
        f"nb_design_3,0.75,0.72,85.3,0.70,0.55,2.3,{DESIGN_SEQUENCE}\n"
    )
    return csv_path


# ---------------------------------------------------------------------------
# Test: Full protein binder design pipeline
# ---------------------------------------------------------------------------


class TestE2EProteinDesignPipeline:
    """Full end-to-end flow for de novo protein binder design via PXDesign."""

    def test_e2e_protein_design_pipeline(self, tmp_path, monkeypatch):
        """Full pipeline: PDB -> config -> mock run -> parse -> score -> screen."""
        import proteus_cli.protein as protein_mod

        # --- Step 1: Build a mock PDB target ---
        pdb_path = _write_mock_pdb(tmp_path)
        assert pdb_path.exists()

        # --- Step 2: Build PXDesign config ---
        config_path = build_pxdesign_config(
            target_pdb=pdb_path,
            target_chains=["A"],
            hotspot_residues=["A1", "A2"],
            output_dir=tmp_path,
            binder_length=80,
        )
        assert config_path.exists()
        assert config_path.name == "pxdesign_config.yaml"

        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)
        assert cfg["target"]["file"] == str(pdb_path)
        assert "A" in cfg["target"]["chains"]
        assert cfg["target"]["chains"]["A"]["hotspots"] == [1, 2]
        assert cfg["binder_length"] == 80

        # --- Step 3: Mock run_protein_design to return success ---
        def mock_validate(name: str) -> Path:
            return tmp_path

        def mock_run(cmd, cwd=None, timeout=3600, env=None):
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

        from proteus_cli.protein import run_protein_design
        result = run_protein_design(config_path, output_dir=tmp_path)
        assert result.status == "success"
        assert result.tool == "pxdesign"

        # --- Step 4: Create a mock summary.csv ---
        _write_pxdesign_summary_csv(tmp_path)

        # --- Step 5: Parse results ---
        designs = parse_design_results(tmp_path)
        assert len(designs) == 5
        # Sorted by ptx_iptm descending
        assert designs[0]["name"] == "design_003"
        assert designs[0]["ptx_iptm"] == 0.95
        assert designs[-1]["name"] == "design_004"
        assert designs[-1]["ptx_iptm"] == 0.78

        # --- Step 6: Score with interpret_ipsae ---
        mock_ipsae_scores = [0.85, 0.65, 0.25]

        scored_designs = []
        for i, design in enumerate(designs[:3]):
            ipsae = mock_ipsae_scores[i]
            scored = dict(design)
            scored["ipsae"] = ipsae
            scored["ipsae_interpretation"] = interpret_ipsae(ipsae)
            scored_designs.append(scored)

        assert "excellent" in scored_designs[0]["ipsae_interpretation"]
        assert "good" in scored_designs[1]["ipsae_interpretation"]
        assert "weak" in scored_designs[2]["ipsae_interpretation"]

        # --- Step 7: Screen with liabilities + developability ---
        screened = []
        for sd in scored_designs:
            liabilities = scan_liabilities(DESIGN_SEQUENCE)
            dev_report = assess_developability(DESIGN_SEQUENCE, liabilities=liabilities)
            entry = dict(sd)
            entry["liability_count"] = len(liabilities)
            entry["overall_risk"] = dev_report.overall_risk
            entry["flags"] = dev_report.flags
            screened.append(entry)

        # --- Step 8: Verify the full pipeline produces ranked, screened results ---
        assert len(screened) == 3
        # Ranked by original ptx_iptm (descending)
        assert screened[0]["ptx_iptm"] > screened[1]["ptx_iptm"] > screened[2]["ptx_iptm"]
        # Each result has all expected keys
        expected_keys = {
            "name", "ptx_iptm",
            "ipsae", "ipsae_interpretation",
            "liability_count", "overall_risk", "flags",
        }
        for entry in screened:
            assert expected_keys.issubset(set(entry.keys()))
        # Screening results are present and sensible
        for entry in screened:
            assert isinstance(entry["liability_count"], int)
            assert entry["overall_risk"] in ("low", "medium", "high")
            assert isinstance(entry["flags"], list)


# ---------------------------------------------------------------------------
# Test: Full antibody design pipeline
# ---------------------------------------------------------------------------


class TestE2EAntibodyDesignPipeline:
    """Full end-to-end flow for antibody/nanobody design via proteus-ab."""

    def test_e2e_antibody_design_pipeline(self, tmp_path, monkeypatch):
        """Full pipeline: PDB -> spec -> mock run -> parse -> score -> screen."""
        import proteus_cli.antibody as antibody_mod

        # --- Step 1: Build a mock PDB target ---
        pdb_path = _write_mock_pdb(tmp_path)

        # --- Step 2: Build design spec ---
        spec_path = build_design_spec(
            target_pdb=pdb_path,
            target_chains=["A"],
            binding_residues={"A": [1, 2]},
            output_dir=tmp_path,
        )
        assert spec_path.exists()
        assert spec_path.name == "design_spec.yaml"

        with open(spec_path) as fh:
            spec = yaml.safe_load(fh)
        assert "entities" in spec
        target_entity = spec["entities"][0]
        assert target_entity["file"]["path"] == str(pdb_path)

        # --- Step 3: Mock run_antibody_design ---
        def mock_validate(name: str) -> Path:
            return tmp_path

        def mock_run(cmd, cwd=None, timeout=3600, env=None):
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

        from proteus_cli.antibody import run_antibody_design
        result = run_antibody_design(spec_path, output_dir=tmp_path)
        assert result.status == "success"
        assert result.tool == "boltzgen"

        # --- Step 4: Create mock antibody metrics CSV ---
        _write_antibody_metrics_csv(tmp_path)

        # --- Step 5: Parse antibody results ---
        designs = parse_antibody_results(tmp_path)
        assert len(designs) == 3
        # Sorted by iptm descending
        assert designs[0]["design_id"] == "nb_design_2"
        assert designs[0]["iptm"] == 0.91
        assert designs[1]["design_id"] == "nb_design_1"
        assert designs[1]["iptm"] == 0.82
        assert designs[2]["design_id"] == "nb_design_3"
        assert designs[2]["iptm"] == 0.75

        # --- Step 6: Score and screen each design ---
        ranked_screened = []
        for design in designs:
            seq = design["sequence"]
            # Simulate ipSAE from iptm (proxy in tests)
            mock_ipsae = design["iptm"] * 0.9

            liabilities = scan_liabilities(seq)
            dev_report = assess_developability(seq, liabilities=liabilities)

            ranked_screened.append({
                **design,
                "ipsae": round(mock_ipsae, 3),
                "ipsae_interpretation": interpret_ipsae(mock_ipsae),
                "liability_count": len(liabilities),
                "high_severity_count": len([l for l in liabilities if l.severity == "high"]),
                "overall_risk": dev_report.overall_risk,
                "flags": dev_report.flags,
                "net_charge": round(compute_net_charge(seq), 2),
            })

        # --- Step 7: Verify results ---
        assert len(ranked_screened) == 3
        # Maintained iptm ranking
        assert ranked_screened[0]["iptm"] > ranked_screened[1]["iptm"] > ranked_screened[2]["iptm"]
        # Each has full scoring + screening data
        for entry in ranked_screened:
            assert "ipsae" in entry
            assert "liability_count" in entry
            assert "overall_risk" in entry
            assert entry["overall_risk"] in ("low", "medium", "high")
            assert isinstance(entry["net_charge"], float)
            assert len(entry["ipsae_interpretation"]) > 0


# ---------------------------------------------------------------------------
# Test: Full screening battery
# ---------------------------------------------------------------------------


class TestE2EScreeningBattery:
    """Take a known sequence and run the full screening battery."""

    def test_e2e_screening_battery(self):
        """Complete screening: liabilities + charge + developability on known sequence."""
        sequence = DESIGN_SEQUENCE

        # --- Liability scan ---
        liabilities = scan_liabilities(sequence)
        assert isinstance(liabilities, list)
        # DESIGN_SEQUENCE contains known motifs:
        # - "NG" at position in "DNGW" -> deamidation (high)
        # - Methionine oxidation (M in SYAMS...)
        # - Check for types we expect
        types_found = {l.type for l in liabilities}
        # There should be at least deamidation hits (NG motif in DNGW)
        deamidation_hits = [l for l in liabilities if l.type == "deamidation"]
        assert len(deamidation_hits) >= 1

        # Verify each liability has all required fields
        for l in liabilities:
            assert l.type in ("deamidation", "isomerization", "oxidation", "free_cysteine", "glycosylation")
            assert l.severity in ("high", "medium", "low")
            assert isinstance(l.position, int)
            assert len(l.motif) > 0
            assert len(l.description) > 0

        # --- Net charge ---
        charge = compute_net_charge(sequence)
        assert isinstance(charge, float)
        # Antibody-like sequences are typically near-neutral to slightly positive
        assert -15.0 < charge < 15.0

        # --- Developability ---
        dev_report = assess_developability(sequence, liabilities=liabilities)
        assert dev_report.liability_count == len(liabilities)
        assert 0.0 <= dev_report.hydrophobic_fraction <= 1.0
        assert 0.0 <= dev_report.proline_fraction <= 1.0
        assert 0.0 <= dev_report.glycine_fraction <= 1.0
        assert dev_report.overall_risk in ("low", "medium", "high")
        assert isinstance(dev_report.flags, list)
        # Net charge should match
        assert abs(dev_report.net_charge - charge) < 0.01

        # --- Scoring interpretation ---
        # Test boundary cases of interpret functions across the battery
        for score_val, expected_fragment in [
            (0.9, "excellent"),
            (0.6, "good"),
            (0.4, "moderate"),
            (0.1, "poor"),
        ]:
            assert expected_fragment in interpret_ipsae(score_val)


    def test_e2e_screening_battery_clean_sequence(self):
        """Clean sequence should pass screening with low risk."""
        sequence = CLEAN_SEQUENCE

        liabilities = scan_liabilities(sequence)
        charge = compute_net_charge(sequence)
        dev_report = assess_developability(sequence, liabilities=liabilities)

        # A well-designed sequence should have few liabilities
        # and overall low-to-medium risk
        assert dev_report.overall_risk in ("low", "medium")
        assert isinstance(charge, float)
        assert dev_report.hydrophobic_fraction < 1.0

    def test_e2e_screening_battery_pathological_sequence(self):
        """A deliberately bad sequence should trigger multiple flags."""
        # Lots of NG (deamidation), DG (isomerization), many K (charge),
        # many I (hydrophobic), odd Cys, long CDR
        pathological = "NGNGNGDG" + "K" * 15 + "I" * 25 + "C"

        liabilities = scan_liabilities(pathological)
        dev_report = assess_developability(pathological, liabilities=liabilities)

        # Should have many liabilities
        assert len(liabilities) >= 5
        # High severity count should be >= 3 (3x NG + 1x DG = 4 high deam/iso + 1 free Cys)
        high_sev = [l for l in liabilities if l.severity == "high"]
        assert len(high_sev) >= 3
        # Should be flagged as high risk
        assert dev_report.overall_risk == "high"
        assert len(dev_report.flags) >= 3


# ---------------------------------------------------------------------------
# Test: CLI `proteus screen` command end-to-end
# ---------------------------------------------------------------------------


class TestE2ECLIScreenCommand:
    """End-to-end test using Click CliRunner for the ``screen`` command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_e2e_cli_screen_command(self, runner):
        """``proteus screen <sequence>`` produces full JSON screening output."""
        result = runner.invoke(cli, ["screen", DESIGN_SEQUENCE])
        assert result.exit_code == 0

        data = json.loads(result.output)

        # Top-level structure
        assert data["sequence_length"] == len(DESIGN_SEQUENCE)
        assert isinstance(data["net_charge"], (int, float))
        assert isinstance(data["liabilities"], list)
        assert "developability" in data

        # Liabilities are properly structured
        for l in data["liabilities"]:
            assert "type" in l
            assert "position" in l
            assert "motif" in l
            assert "severity" in l
            assert "description" in l
            assert l["severity"] in ("high", "medium", "low")

        # Developability section has all expected fields
        dev = data["developability"]
        assert "overall_risk" in dev
        assert "hydrophobic_fraction" in dev
        assert "proline_fraction" in dev
        assert "glycine_fraction" in dev
        assert "liability_count" in dev
        assert "flags" in dev
        assert dev["overall_risk"] in ("low", "medium", "high")
        assert dev["liability_count"] == len(data["liabilities"])

        # Verify the liability count matches
        assert dev["liability_count"] >= 1  # DESIGN_SEQUENCE has known motifs

    def test_e2e_cli_screen_pathological(self, runner):
        """Screening a pathological sequence via CLI reports high risk."""
        pathological = "NGNGNGDGKKKKKKKKKKKKKKKIIIIIIIIIIIIIIIIIIIIIIIIIIC"
        result = runner.invoke(cli, ["screen", pathological])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["developability"]["overall_risk"] == "high"
        assert len(data["developability"]["flags"]) >= 3

    def test_e2e_cli_screen_minimal(self, runner):
        """Screening a minimal clean sequence via CLI works."""
        result = runner.invoke(cli, ["screen", "AAAKKKEEE"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["sequence_length"] == 9
        assert data["developability"]["overall_risk"] == "low"


# ---------------------------------------------------------------------------
# Test: CLI `proteus check` command end-to-end
# ---------------------------------------------------------------------------


class TestE2ECLICheckCommand:
    """End-to-end test for ``proteus check <tool>`` with monkeypatched paths."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_e2e_cli_check_command_success(self, runner, tmp_path, monkeypatch):
        """``proteus check protenix`` succeeds when the tool directory exists."""
        import proteus_cli.common as common_mod

        # Create a fake tool directory
        fake_tool_dir = tmp_path / "Protenix"
        fake_tool_dir.mkdir()

        monkeypatch.setattr(
            common_mod,
            "TOOL_PATHS",
            {"protenix": fake_tool_dir, "pxdesign": tmp_path, "boltzgen": tmp_path},
        )

        result = runner.invoke(cli, ["check", "protenix"])
        assert result.exit_code == 0
        assert "OK" in result.output
        assert "protenix" in result.output
        assert str(fake_tool_dir) in result.output

    def test_e2e_cli_check_command_missing_dir(self, runner, tmp_path, monkeypatch):
        """``proteus check protenix`` fails when the tool directory is missing."""
        import proteus_cli.common as common_mod

        nonexistent = tmp_path / "nonexistent_tool_dir"
        monkeypatch.setattr(
            common_mod,
            "TOOL_PATHS",
            {"protenix": nonexistent, "pxdesign": tmp_path, "boltzgen": tmp_path},
        )

        result = runner.invoke(cli, ["check", "protenix"])
        assert result.exit_code != 0
        assert "ERROR" in result.output or "not found" in result.output

    def test_e2e_cli_check_command_unknown_tool(self, runner):
        """``proteus check unknown-tool`` fails with an error."""
        result = runner.invoke(cli, ["check", "unknown-tool"])
        assert result.exit_code != 0

    def test_e2e_cli_check_all_tools(self, runner, tmp_path, monkeypatch):
        """Verify all three tools can be checked when directories exist."""
        import proteus_cli.common as common_mod

        tool_dirs = {}
        for tool_name, dir_name in [
            ("protenix", "Protenix"),
            ("pxdesign", "PXDesign"),
            ("boltzgen", "boltzgen"),
        ]:
            d = tmp_path / dir_name
            d.mkdir()
            tool_dirs[tool_name] = d

        monkeypatch.setattr(common_mod, "TOOL_PATHS", tool_dirs)

        for tool_name in ("protenix", "pxdesign", "boltzgen"):
            result = runner.invoke(cli, ["check", tool_name])
            assert result.exit_code == 0, f"check {tool_name} failed: {result.output}"
            assert "OK" in result.output
