"""Tests for ipSAE scoring module."""
from proteus_cli.scoring.ipsae import interpret_ipsae


def test_interpret_excellent():
    assert "Excellent" in interpret_ipsae(0.9)


def test_interpret_good():
    assert "Good" in interpret_ipsae(0.6)


def test_interpret_moderate():
    assert "Moderate" in interpret_ipsae(0.4)


def test_interpret_poor():
    assert "Poor" in interpret_ipsae(0.1)


def test_interpret_boundary_high():
    assert "Excellent" in interpret_ipsae(0.81)


def test_interpret_boundary_low():
    assert "Poor" in interpret_ipsae(0.3)


def test_interpret_zero():
    assert "Poor" in interpret_ipsae(0.0)
