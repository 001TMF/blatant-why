"""Tests for the screening module — PTM liabilities and developability."""
from proteus_cli.screening.liabilities import Liability, scan_liabilities, compute_net_charge
from proteus_cli.screening.developability import assess_developability, HYDROPHOBIC_AAS


# ---------------------------------------------------------------------------
# scan_liabilities tests
# ---------------------------------------------------------------------------

def test_scan_no_liabilities():
    """Clean sequence with no known liability motifs returns empty list."""
    result = scan_liabilities("AAAKKK")
    assert result == []


def test_scan_deamidation_ng():
    """NG motif should be flagged as high-severity deamidation."""
    result = scan_liabilities("AANGAA")
    deam = [l for l in result if l.type == "deamidation" and l.motif == "NG"]
    assert len(deam) == 1
    assert deam[0].severity == "high"
    assert deam[0].position == 2


def test_scan_deamidation_ns():
    """NS motif should be flagged as medium-severity deamidation."""
    result = scan_liabilities("AANSAA")
    deam = [l for l in result if l.type == "deamidation" and l.motif == "NS"]
    assert len(deam) == 1
    assert deam[0].severity == "medium"


def test_scan_isomerization_dg():
    """DG motif should be flagged as high-severity isomerization."""
    result = scan_liabilities("AADGAA")
    iso = [l for l in result if l.type == "isomerization" and l.motif == "DG"]
    assert len(iso) == 1
    assert iso[0].severity == "high"
    assert iso[0].position == 2


def test_scan_free_cysteine_odd():
    """Odd number of cysteines should flag free_cysteine liability."""
    result = scan_liabilities("AACAA")
    cys = [l for l in result if l.type == "free_cysteine"]
    assert len(cys) == 1
    assert cys[0].severity == "high"
    assert "1 Cys" in cys[0].motif


def test_scan_free_cysteine_even():
    """Even number of cysteines should NOT flag free_cysteine."""
    result = scan_liabilities("AACCAA")
    cys = [l for l in result if l.type == "free_cysteine"]
    assert len(cys) == 0


def test_scan_glycosylation_nxs():
    """NAS motif (N[^P][ST]) should be flagged as glycosylation."""
    result = scan_liabilities("AANASAA")
    glyc = [l for l in result if l.type == "glycosylation"]
    assert len(glyc) >= 1
    # The NAS match should be present
    nas_matches = [l for l in glyc if l.motif == "NAS"]
    assert len(nas_matches) == 1
    assert nas_matches[0].severity == "medium"


def test_scan_glycosylation_nps_not_flagged():
    """NPS should NOT be flagged — proline blocks N-linked glycosylation."""
    result = scan_liabilities("AANPSAA")
    glyc = [l for l in result if l.type == "glycosylation"]
    # NPS should not match N[^P][ST]
    nps_matches = [l for l in glyc if "NPS" in l.motif]
    assert len(nps_matches) == 0


# ---------------------------------------------------------------------------
# compute_net_charge tests
# ---------------------------------------------------------------------------

def test_net_charge_basic():
    """All-lysine sequence should have positive charge at pH 7.4."""
    charge = compute_net_charge("KKKKKKKKKK")
    assert charge > 5.0  # ~10 positive charges from K, minor terminus adjustments


def test_net_charge_acidic():
    """All-aspartate sequence should have negative charge at pH 7.4."""
    charge = compute_net_charge("DDDDDDDDDD")
    assert charge < -5.0  # ~10 negative charges from D


def test_net_charge_neutral_ish():
    """Alanine-only sequence should be near zero (only terminus contributions)."""
    charge = compute_net_charge("AAAAAAAAAA")
    assert abs(charge) < 2.0  # Only N/C terminus


# ---------------------------------------------------------------------------
# assess_developability tests
# ---------------------------------------------------------------------------

def test_developability_low_risk():
    """Clean, short sequence should score low risk."""
    # Use E+K: non-hydrophobic, charge-balanced, no liability motifs
    report = assess_developability("EEKKEEKKEEKK")
    assert report.overall_risk == "low"
    assert len(report.flags) == 0
    assert report.liability_count == 0


def test_developability_flags_high_hydrophobic():
    """Sequence with >45% hydrophobic AAs should be flagged."""
    # AILMFWVP are hydrophobic. Build a sequence that's >45% hydrophobic.
    seq = "AAAAAIIIIIILLLL"  # A=6, I=6, L=4 => 16 chars, hydro = A(6)+I(6)+L(4)=16/16=100%
    # Actually all of AILMFWVP are hydrophobic, so let's be precise
    seq = "IIIIILLLLLAAKKK"  # I=5, L=5, A=2, K=3 => 15 chars, hydro(AILMFWVP): I(5)+L(5)+A(2)=12/15=80%
    report = assess_developability(seq)
    assert report.hydrophobic_fraction > 0.45
    assert any("hydrophobic" in f.lower() for f in report.flags)


def test_developability_risk_escalation():
    """Enough flags should escalate risk to high."""
    # Need >= 3 flags. Construct sequence with:
    # 1) >2 high-severity liabilities (3x NG + 1x DG = 4 high)
    # 2) Extreme charge (lots of K => charge > 10)
    # 3) High hydrophobic content (lots of I => >45%)
    seq = "NGNGNGDG" + "K" * 15 + "I" * 25  # 48 chars
    report = assess_developability(seq)
    assert report.overall_risk == "high"
    assert len(report.flags) >= 3


def test_developability_with_cdr_regions():
    """CDR regions should be measured correctly."""
    seq = "A" * 100
    cdr_regions = [(10, 30), (50, 70), (80, 95)]  # total = 20+20+15 = 55
    report = assess_developability(seq, cdr_regions=cdr_regions)
    assert report.total_cdr_length == 55
    # Not > 70, so no CDR flag
    cdr_flags = [f for f in report.flags if "CDR" in f]
    assert len(cdr_flags) == 0


def test_developability_long_cdr_flagged():
    """Total CDR length > 70 should be flagged."""
    seq = "A" * 100
    cdr_regions = [(0, 30), (40, 70), (75, 100)]  # total = 30+30+25 = 85
    report = assess_developability(seq, cdr_regions=cdr_regions)
    assert report.total_cdr_length == 85
    cdr_flags = [f for f in report.flags if "CDR" in f]
    assert len(cdr_flags) == 1


def test_developability_precomputed_liabilities():
    """Passing pre-computed liabilities should skip internal scan."""
    from proteus_cli.screening.liabilities import Liability
    fake_liabilities = [
        Liability("deamidation", 0, "NG", "high", "test"),
        Liability("deamidation", 2, "NG", "high", "test"),
        Liability("deamidation", 4, "NG", "high", "test"),
    ]
    report = assess_developability("AAAAAA", liabilities=fake_liabilities)
    assert report.liability_count == 3
    assert any("high-severity" in f.lower() for f in report.flags)
