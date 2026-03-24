"""Tests for Pareto front extraction and formatting."""

from proteus_cli.screening.pareto import format_pareto, is_dominated, pareto_front


OBJECTIVES = [
    ("ipsae_min", "maximize"),
    ("iptm", "maximize"),
    ("liabilities", "minimize"),
]


class TestIsDominated:
    """Tests for pairwise Pareto dominance."""

    def test_returns_true_when_other_is_better_or_equal_on_all_objectives(self):
        """A design is dominated when another is no worse on all metrics and better on one."""
        design = {"ipsae_min": 0.70, "iptm": 0.80, "liabilities": 3}
        other = {"ipsae_min": 0.75, "iptm": 0.80, "liabilities": 2}

        assert is_dominated(design, other, OBJECTIVES) is True

    def test_returns_false_when_tradeoff_exists(self):
        """A better score on one objective prevents dominance if another objective is worse."""
        design = {"ipsae_min": 0.70, "iptm": 0.90, "liabilities": 1}
        other = {"ipsae_min": 0.80, "iptm": 0.85, "liabilities": 1}

        assert is_dominated(design, other, OBJECTIVES) is False

    def test_returns_false_when_designs_are_identical(self):
        """Equal designs are not dominated because there is no strict improvement."""
        design = {"ipsae_min": 0.80, "iptm": 0.90, "liabilities": 2}
        other = {"ipsae_min": 0.80, "iptm": 0.90, "liabilities": 2}

        assert is_dominated(design, other, OBJECTIVES) is False


class TestParetoFront:
    """Tests for Pareto front extraction."""

    def test_single_design_is_returned_with_rank_and_tradeoff(self):
        """A single design should always be Pareto-optimal."""
        designs = [
            {
                "design_name": "solo",
                "ipsae_min": 0.82,
                "iptm": 0.91,
                "liabilities": 1,
            }
        ]

        front = pareto_front(designs, OBJECTIVES)

        assert len(front) == 1
        assert front[0]["design_name"] == "solo"
        assert front[0]["pareto_rank"] == 0
        assert front[0]["tradeoff"] == "Best ipsae_min; Best iptm; Best liabilities"

    def test_returns_only_best_design_when_all_others_are_dominated(self):
        """One globally superior design should be the entire front."""
        designs = [
            {
                "design_name": "best",
                "ipsae_min": 0.90,
                "iptm": 0.95,
                "liabilities": 1,
            },
            {
                "design_name": "dominated_1",
                "ipsae_min": 0.85,
                "iptm": 0.90,
                "liabilities": 2,
            },
            {
                "design_name": "dominated_2",
                "ipsae_min": 0.70,
                "iptm": 0.80,
                "liabilities": 3,
            },
        ]

        front = pareto_front(designs, OBJECTIVES)

        assert [d["design_name"] for d in front] == ["best"]
        assert front[0]["tradeoff"] == "Best ipsae_min; Best iptm; Best liabilities"

    def test_keeps_all_designs_when_none_are_dominated(self):
        """Mutual trade-offs should keep every design on the Pareto front."""
        designs = [
            {
                "design_name": "high_ipsae",
                "ipsae_min": 0.95,
                "iptm": 0.80,
                "liabilities": 3,
            },
            {
                "design_name": "high_iptm",
                "ipsae_min": 0.80,
                "iptm": 0.96,
                "liabilities": 2,
            },
            {
                "design_name": "low_liability",
                "ipsae_min": 0.82,
                "iptm": 0.84,
                "liabilities": 1,
            },
        ]

        front = pareto_front(designs, OBJECTIVES)

        assert [d["design_name"] for d in front] == [
            "high_ipsae",
            "high_iptm",
            "low_liability",
        ]
        assert all(d["pareto_rank"] == 0 for d in front)

    def test_adds_tradeoff_annotations_for_metric_leaders(self):
        """Each Pareto-optimal design should be annotated with its distinguishing strength."""
        designs = [
            {
                "design_name": "best_ipsae",
                "ipsae_min": 0.96,
                "iptm": 0.82,
                "liabilities": 2,
            },
            {
                "design_name": "best_iptm",
                "ipsae_min": 0.84,
                "iptm": 0.97,
                "liabilities": 2,
            },
            {
                "design_name": "best_liability",
                "ipsae_min": 0.84,
                "iptm": 0.83,
                "liabilities": 1,
            },
        ]

        front = pareto_front(designs, OBJECTIVES)
        by_name = {design["design_name"]: design for design in front}

        assert by_name["best_ipsae"]["tradeoff"] == "Best ipsae_min"
        assert by_name["best_iptm"]["tradeoff"] == "Best iptm"
        assert by_name["best_liability"]["tradeoff"] == "Best liabilities"


class TestFormatPareto:
    """Tests for Pareto table formatting."""

    def test_returns_message_for_empty_front(self):
        """An empty front should produce a simple fallback message."""
        assert format_pareto([]) == "  No Pareto-optimal designs found."

    def test_formats_table_with_headers_values_and_summary(self):
        """Formatted output should include headers, values, trade-offs, and summary."""
        front = [
            {
                "design_name": "candidate_alpha",
                "ipsae_min": 0.91234,
                "iptm": 0.87654,
                "liabilities": 2,
                "tradeoff": "Best ipsae_min",
            },
            {
                "name": "candidate_beta",
                "ipsae_min": 0.845,
                "iptm": 0.9321,
                "liabilities": 1,
                "tradeoff": "Best iptm; Best liabilities",
            },
        ]

        formatted = format_pareto(front, OBJECTIVES)

        assert "Pareto-Optimal Candidates" in formatted
        assert "Design" in formatted
        assert "ipsae_min" in formatted
        assert "Trade-off" in formatted
        assert "candidate_alpha" in formatted
        assert "candidate_beta" in formatted
        assert "0.912" in formatted
        assert "0.877" in formatted
        assert "0.932" in formatted
        assert "Best ipsae_min" in formatted
        assert "Best iptm; Best liabilities" in formatted
        assert "2 Pareto-optimal designs from 2 on front 0" in formatted
