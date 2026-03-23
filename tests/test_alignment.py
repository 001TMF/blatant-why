"""Tests for the screening alignment module."""
from proteus_cli.screening.alignment import (
    cdr_align,
    format_alignment,
    multiple_align,
    pairwise_align,
)


# ---------------------------------------------------------------------------
# pairwise_align tests
# ---------------------------------------------------------------------------


def test_pairwise_identical():
    """Identical sequences should have identity 1.0."""
    result = pairwise_align("ACDEFGHIK", "ACDEFGHIK")
    assert result["identity"] == 1.0
    assert result["score"] == 9.0
    assert result["num_identical"] == 9
    assert result["alignment_length"] == 9


def test_pairwise_different():
    """Completely different sequences should have identity 0.0."""
    result = pairwise_align("AAAA", "DDDD")
    assert result["identity"] == 0.0
    assert result["num_identical"] == 0


def test_pairwise_partial_match():
    """Partially matching sequences should have fractional identity."""
    result = pairwise_align("ACDE", "ACEE")
    assert 0.0 < result["identity"] < 1.0
    assert result["score"] > 0.0


def test_pairwise_empty_sequence():
    """Empty input should return zero identity without error."""
    result = pairwise_align("", "ACDE")
    assert result["identity"] == 0.0
    assert result["score"] == 0.0


def test_pairwise_unequal_length():
    """Unequal-length sequences should still align (global with gaps)."""
    result = pairwise_align("ACDEFGHIK", "ACDE")
    # Score may be 0 due to gap penalties, but alignment should still work
    assert result["score"] >= 0.0
    assert result["alignment_length"] == 9
    assert result["identity"] > 0.0


# ---------------------------------------------------------------------------
# cdr_align tests
# ---------------------------------------------------------------------------


def test_cdr_align_basic():
    """CDR identity matrix should be symmetric with 1.0 on diagonal."""
    designs = [
        {"name": "d1", "cdr3_sequence": "CARGGYW"},
        {"name": "d2", "cdr3_sequence": "CARGGYW"},
        {"name": "d3", "cdr3_sequence": "CARDDDW"},
    ]
    result = cdr_align(designs)
    assert result["n"] == 3
    assert len(result["matrix"]) == 3
    # Diagonal should be 1.0
    for i in range(3):
        assert result["matrix"][i][i] == 1.0
    # Identical sequences d1 and d2
    assert result["matrix"][0][1] == 1.0
    assert result["matrix"][1][0] == 1.0
    # d1 vs d3 should be < 1.0
    assert result["matrix"][0][2] < 1.0


def test_cdr_align_custom_key():
    """Should support custom CDR key."""
    designs = [
        {"name": "d1", "my_cdr": "CARGGYW"},
        {"name": "d2", "my_cdr": "CARDDDW"},
    ]
    result = cdr_align(designs, cdr_key="my_cdr")
    assert result["n"] == 2
    assert result["matrix"][0][1] < 1.0


# ---------------------------------------------------------------------------
# multiple_align tests
# ---------------------------------------------------------------------------


def test_multiple_align_basic():
    """Star alignment should produce consensus and MSA."""
    sequences = [
        {"name": "s1", "sequence": "ACDEFGHIK"},
        {"name": "s2", "sequence": "ACDEXGHIK"},
        {"name": "s3", "sequence": "ACDEFGHIK"},
    ]
    result = multiple_align(sequences)
    assert result["n"] == 3
    assert len(result["msa"]) == 3
    assert result["consensus"] != ""
    assert result["centroid_index"] in (0, 1, 2)


def test_multiple_align_single():
    """Single sequence should return itself as consensus."""
    sequences = [{"name": "only", "sequence": "ACDE"}]
    result = multiple_align(sequences)
    assert result["n"] == 1
    assert result["consensus"] == "ACDE"
    assert result["centroid_index"] == 0


def test_multiple_align_empty():
    """Empty input should return empty result."""
    result = multiple_align([])
    assert result["n"] == 0
    assert result["consensus"] == ""
    assert result["centroid_index"] == -1


# ---------------------------------------------------------------------------
# format_alignment tests
# ---------------------------------------------------------------------------


def test_format_pairwise():
    """Pairwise format should include score and identity lines."""
    result = pairwise_align("ACDE", "ACDE")
    text = format_alignment(result)
    assert "Pairwise Alignment" in text
    assert "Score" in text
    assert "Identity" in text
    assert "100.0%" in text


def test_format_cdr_matrix():
    """CDR matrix format should include the label header."""
    designs = [
        {"name": "d1", "cdr3_sequence": "CARGGYW"},
        {"name": "d2", "cdr3_sequence": "CARDDDW"},
    ]
    result = cdr_align(designs)
    text = format_alignment(result)
    assert "CDR Identity Matrix" in text
    assert "d1" in text
    assert "d2" in text


def test_format_multiple():
    """MSA format should include centroid marker and consensus."""
    sequences = [
        {"name": "s1", "sequence": "ACDE"},
        {"name": "s2", "sequence": "ACEE"},
        {"name": "s3", "sequence": "ACDE"},
    ]
    result = multiple_align(sequences)
    text = format_alignment(result)
    assert "Multiple Sequence Alignment" in text
    assert "Consensus" in text
    # Centroid should be marked with *
    assert "*" in text


# ---------------------------------------------------------------------------
# Imports from __init__
# ---------------------------------------------------------------------------


def test_exports_from_init():
    """All alignment functions should be importable from screening package."""
    from proteus_cli.screening import (
        pairwise_align,
        cdr_align,
        multiple_align,
        format_alignment,
    )
    assert callable(pairwise_align)
    assert callable(cdr_align)
    assert callable(multiple_align)
    assert callable(format_alignment)
