"""PTM liability and sequence quality scanning."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Liability:
    type: str
    position: int
    motif: str
    severity: str  # "high", "medium", "low"
    description: str


# Deamidation hotspots
DEAMIDATION_PATTERNS = [
    (re.compile(r"NG"), "high", "Asparagine deamidation (NG)"),
    (re.compile(r"NS"), "medium", "Asparagine deamidation (NS)"),
    (re.compile(r"NT"), "medium", "Asparagine deamidation (NT)"),
    (re.compile(r"NA"), "low", "Asparagine deamidation (NA)"),
]

# Isomerization
ISOMERIZATION_PATTERNS = [
    (re.compile(r"DG"), "high", "Aspartate isomerization (DG)"),
    (re.compile(r"DS"), "medium", "Aspartate isomerization (DS)"),
]

# Oxidation
OXIDATION_PATTERNS = [
    (re.compile(r"M"), "medium", "Methionine oxidation"),
    (re.compile(r"W"), "low", "Tryptophan oxidation"),
]

# Glycosylation
GLYCOSYLATION_PATTERN = re.compile(r"N[^P][ST]")


def scan_liabilities(sequence: str) -> list[Liability]:
    """Scan a protein sequence for PTM liabilities."""
    sequence = sequence.upper()
    liabilities = []

    for pattern, severity, desc in DEAMIDATION_PATTERNS:
        for match in pattern.finditer(sequence):
            liabilities.append(Liability("deamidation", match.start(), match.group(), severity, desc))

    for pattern, severity, desc in ISOMERIZATION_PATTERNS:
        for match in pattern.finditer(sequence):
            liabilities.append(Liability("isomerization", match.start(), match.group(), severity, desc))

    for pattern, severity, desc in OXIDATION_PATTERNS:
        for match in pattern.finditer(sequence):
            liabilities.append(Liability("oxidation", match.start(), match.group(), severity, desc))

    # Free cysteines (odd count = unpaired)
    cys_count = sequence.count("C")
    if cys_count % 2 != 0:
        liabilities.append(Liability("free_cysteine", -1, f"{cys_count} Cys", "high", "Odd number of cysteines — likely unpaired"))

    # N-linked glycosylation
    for match in GLYCOSYLATION_PATTERN.finditer(sequence):
        liabilities.append(Liability("glycosylation", match.start(), match.group(), "medium", "N-linked glycosylation motif (NXS/T)"))

    return liabilities


def compute_net_charge(sequence: str, ph: float = 7.4) -> float:
    """Estimate net charge at given pH using Henderson-Hasselbalch."""
    sequence = sequence.upper()
    if not sequence:
        return 0.0
    pka = {"D": 3.65, "E": 4.25, "H": 6.00, "C": 8.18, "Y": 10.07, "K": 10.53, "R": 12.48}
    charge = 0.0
    for aa in sequence:
        if aa in ("D", "E", "C", "Y"):
            charge -= 1.0 / (1.0 + 10 ** (pka.get(aa, 7.0) - ph))
        elif aa in ("K", "R", "H"):
            charge += 1.0 / (1.0 + 10 ** (ph - pka.get(aa, 7.0)))
    # N-terminus and C-terminus
    charge += 1.0 / (1.0 + 10 ** (ph - 9.69))  # N-term
    charge -= 1.0 / (1.0 + 10 ** (2.34 - ph))   # C-term
    return charge
