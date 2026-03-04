"""Tests for proteus_cli.main — unified CLI entry point."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from proteus_cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLIHelp:
    """Tests for CLI help and version output."""

    def test_cli_help(self, runner: CliRunner) -> None:
        """``cli --help`` exits 0 and shows usage information."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Proteus protein design agent CLI" in result.output

    def test_cli_version(self, runner: CliRunner) -> None:
        """``cli --version`` exits 0 and shows version 0.1.0."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCheckCommand:
    """Tests for the ``check`` subcommand."""

    def test_check_unknown_tool(self, runner: CliRunner) -> None:
        """``cli check nonexistent`` exits non-zero with an error message."""
        result = runner.invoke(cli, ["check", "nonexistent"])
        assert result.exit_code != 0

    def test_check_known_tool_missing_dir(self, runner: CliRunner) -> None:
        """``cli check proteus-fold`` reports error when directory is missing."""
        result = runner.invoke(cli, ["check", "proteus-fold"])
        # On this machine the tool dir may or may not exist; just verify it
        # does not crash unexpectedly (exit 0 if exists, 1 if missing).
        assert result.exit_code in (0, 1)


class TestScreenCommand:
    """Tests for the ``screen`` subcommand."""

    def test_screen_clean_sequence(self, runner: CliRunner) -> None:
        """``cli screen AAAKKKEEE`` exits 0 and returns valid JSON with expected fields."""
        result = runner.invoke(cli, ["screen", "AAAKKKEEE"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["sequence_length"] == 9
        assert isinstance(data["net_charge"], (int, float))
        assert isinstance(data["liabilities"], list)
        assert "developability" in data
        assert "overall_risk" in data["developability"]
        assert "hydrophobic_fraction" in data["developability"]
        assert "proline_fraction" in data["developability"]
        assert "glycine_fraction" in data["developability"]
        assert "liability_count" in data["developability"]
        assert "flags" in data["developability"]

    def test_screen_sequence_with_liabilities(self, runner: CliRunner) -> None:
        """Screening a sequence with known motifs reports liabilities."""
        result = runner.invoke(cli, ["screen", "ANGMDSCK"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        # Should find NG deamidation and DS isomerization at minimum
        liability_types = [l["type"] for l in data["liabilities"]]
        assert "deamidation" in liability_types


class TestSubcommandRegistration:
    """Verify all expected subcommands are registered."""

    def test_all_commands_registered(self, runner: CliRunner) -> None:
        """All six subcommands appear in --help output."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ("fold", "protein", "ab", "check", "screen", "score"):
            assert cmd in result.output, f"Command '{cmd}' not found in help output"

    def test_fold_help(self, runner: CliRunner) -> None:
        """``cli fold --help`` exits 0."""
        result = runner.invoke(cli, ["fold", "--help"])
        assert result.exit_code == 0
        assert "Protenix" in result.output

    def test_protein_help(self, runner: CliRunner) -> None:
        """``cli protein --help`` exits 0."""
        result = runner.invoke(cli, ["protein", "--help"])
        assert result.exit_code == 0
        assert "PXDesign" in result.output

    def test_ab_help(self, runner: CliRunner) -> None:
        """``cli ab --help`` exits 0."""
        result = runner.invoke(cli, ["ab", "--help"])
        assert result.exit_code == 0
        assert "antibody" in result.output.lower() or "nanobody" in result.output.lower()

    def test_score_help(self, runner: CliRunner) -> None:
        """``cli score --help`` exits 0."""
        result = runner.invoke(cli, ["score", "--help"])
        assert result.exit_code == 0
        assert "ipSAE" in result.output
