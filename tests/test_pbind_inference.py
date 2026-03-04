"""Tests for p_bind inference module."""
from proteus_cli.scoring.pbind import interpret_pbind


def test_interpret_high_confidence():
    assert "High confidence" in interpret_pbind(0.9)


def test_interpret_likely():
    assert "Likely" in interpret_pbind(0.6)


def test_interpret_marginal():
    assert "Marginal" in interpret_pbind(0.4)


def test_interpret_unlikely():
    assert "Unlikely" in interpret_pbind(0.1)


def test_interpret_boundary_high():
    assert "High confidence" in interpret_pbind(0.81)


def test_interpret_boundary_low():
    assert "Unlikely" in interpret_pbind(0.3)


def test_interpret_zero():
    assert "Unlikely" in interpret_pbind(0.0)
