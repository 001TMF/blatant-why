"""Tests for ipSAE scoring module."""
from proteus_cli.scoring.ipsae import interpret_ipsae


def test_interpret_excellent():
    assert "excellent" in interpret_ipsae(0.9)


def test_interpret_good():
    assert "good" in interpret_ipsae(0.6)


def test_interpret_moderate():
    assert "moderate" in interpret_ipsae(0.4)


def test_interpret_poor():
    assert "poor" in interpret_ipsae(0.1)


def test_interpret_boundary_high():
    assert "excellent" in interpret_ipsae(0.81)


def test_interpret_boundary_low():
    assert "weak" in interpret_ipsae(0.3)


def test_interpret_zero():
    assert "poor" in interpret_ipsae(0.0)
