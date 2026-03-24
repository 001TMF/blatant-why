"""Developability assessment for antibody designs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DevelopabilityReport:
    total_cdr_length: int
    net_charge: float
    liability_count: int
    hydrophobic_fraction: float
    proline_fraction: float
    glycine_fraction: float
    overall_risk: str  # "low", "medium", "high"
    flags: list[str]


HYDROPHOBIC_AAS = set("AILMFWVP")


def assess_developability(
    sequence: str,
    cdr_regions: list[tuple[int, int]] | None = None,
    liabilities: list | None = None,
) -> DevelopabilityReport:
    """Run TAP-inspired developability assessment."""
    if not sequence:
        return DevelopabilityReport(
            total_cdr_length=0,
            net_charge=0.0,
            liability_count=0,
            hydrophobic_fraction=0.0,
            proline_fraction=0.0,
            glycine_fraction=0.0,
            overall_risk="low",
            flags=["Empty sequence provided"],
        )

    from proteus_cli.screening.liabilities import scan_liabilities, compute_net_charge

    if liabilities is None:
        liabilities = scan_liabilities(sequence)

    charge = compute_net_charge(sequence)
    hydro_frac = sum(1 for aa in sequence if aa in HYDROPHOBIC_AAS) / len(sequence)
    pro_frac = sequence.count("P") / len(sequence)
    gly_frac = sequence.count("G") / len(sequence)

    total_cdr_len = 0
    if cdr_regions:
        total_cdr_len = sum(end - start for start, end in cdr_regions)

    flags = []
    if len([l for l in liabilities if l.severity == "high"]) > 2:
        flags.append("Multiple high-severity PTM liabilities")
    if abs(charge) > 10:
        flags.append(f"Extreme net charge: {charge:.1f}")
    if hydro_frac > 0.45:
        flags.append(f"High hydrophobic content: {hydro_frac:.1%}")
    if gly_frac > 0.15:
        flags.append(f"High glycine content: {gly_frac:.1%}")
    if total_cdr_len > 70:
        flags.append(f"Long total CDR length: {total_cdr_len}")

    risk = "low"
    if len(flags) >= 3:
        risk = "high"
    elif len(flags) >= 1:
        risk = "medium"

    return DevelopabilityReport(
        total_cdr_length=total_cdr_len,
        net_charge=charge,
        liability_count=len(liabilities),
        hydrophobic_fraction=hydro_frac,
        proline_fraction=pro_frac,
        glycine_fraction=gly_frac,
        overall_risk=risk,
        flags=flags,
    )
