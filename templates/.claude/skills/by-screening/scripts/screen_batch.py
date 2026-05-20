#!/usr/bin/env python3
"""Apply the full BY screening battery to a batch of designs.

Reads a CSV or JSON file of designs with their scoring metrics, applies all
configured hard filters and computes the composite ranking score, and writes a
PASS/FAIL/MARGINAL verdict per design with semicolon-separated reason codes.

Inputs (CSV columns or JSON object keys per design):
  - name (str): unique design identifier
  - sequence (str): single-letter amino acid sequence of the design chain
  - iptm (float): interface predicted TM-score
  - plddt (float): mean pLDDT over the design chain
  - rmsd_ca (float): refolding CA-RMSD in Angstroms
  - ipsae_min (float): minimum directional ipSAE from `score_ipsae`
  - modality (str, optional): one of {antibody, nanobody, binder}; falls
    back to the --modality CLI flag
  - cdr_regions (JSON, optional): list of [start, end] tuples (0-indexed,
    end-exclusive) for IMGT/Kabat CDRs

Outputs (CSV):
  - all input columns
  - verdict (PASS | MARGINAL | FAIL)
  - reason_codes (semicolon-separated machine tags)
  - liability_count (int)
  - weighted_liability_count (int)
  - net_charge (float)
  - hydrophobic_fraction (float)
  - total_cdr_length (int)
  - composite_score (float, sortable descending)

Example:
  python screen_batch.py \\
    --designs designs.csv \\
    --modality nanobody \\
    --thresholds-profile production \\
    --output screened.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


HYDROPHOBIC_AAS = set("AILMFWVP")

# Per-modality threshold table. Mirrors references/filter-thresholds.md.
THRESHOLDS: dict[str, dict[str, dict[str, float]]] = {
    "production": {
        "antibody": {
            "iptm_min": 0.50,
            "plddt_min": 70.0,
            "rmsd_max": 5.0,
            "ipsae_min": 0.40,
            "charge_abs_max": 10.0,
            "hydro_frac_max": 0.55,
            "total_cdr_max": 70,
            "cdr_h3_max": 20,
        },
        "nanobody": {
            "iptm_min": 0.50,
            "plddt_min": 70.0,
            "rmsd_max": 5.0,
            "ipsae_min": 0.35,
            "charge_abs_max": 10.0,
            "hydro_frac_max": 0.55,
            "total_cdr_max": 45,
            "cdr_h3_max": 25,
        },
        "binder": {
            "iptm_min": 0.50,
            "plddt_min": 70.0,
            "rmsd_max": 3.5,
            "ipsae_min": 0.45,
            "charge_abs_max": 10.0,
            "hydro_frac_max": 0.50,
            "total_cdr_max": 9_999,  # n/a
            "cdr_h3_max": 9_999,
        },
    },
    "exploratory": {
        "antibody": {
            "iptm_min": 0.40,
            "plddt_min": 65.0,
            "rmsd_max": 6.0,
            "ipsae_min": 0.30,
            "charge_abs_max": 12.0,
            "hydro_frac_max": 0.58,
            "total_cdr_max": 75,
            "cdr_h3_max": 22,
        },
        "nanobody": {
            "iptm_min": 0.40,
            "plddt_min": 65.0,
            "rmsd_max": 6.0,
            "ipsae_min": 0.30,
            "charge_abs_max": 12.0,
            "hydro_frac_max": 0.58,
            "total_cdr_max": 50,
            "cdr_h3_max": 28,
        },
        "binder": {
            "iptm_min": 0.40,
            "plddt_min": 65.0,
            "rmsd_max": 5.0,
            "ipsae_min": 0.35,
            "charge_abs_max": 12.0,
            "hydro_frac_max": 0.55,
            "total_cdr_max": 9_999,
            "cdr_h3_max": 9_999,
        },
    },
    "strict": {
        "antibody": {
            "iptm_min": 0.60,
            "plddt_min": 75.0,
            "rmsd_max": 3.5,
            "ipsae_min": 0.50,
            "charge_abs_max": 8.0,
            "hydro_frac_max": 0.50,
            "total_cdr_max": 65,
            "cdr_h3_max": 18,
        },
        "nanobody": {
            "iptm_min": 0.60,
            "plddt_min": 75.0,
            "rmsd_max": 3.5,
            "ipsae_min": 0.45,
            "charge_abs_max": 8.0,
            "hydro_frac_max": 0.50,
            "total_cdr_max": 42,
            "cdr_h3_max": 23,
        },
        "binder": {
            "iptm_min": 0.60,
            "plddt_min": 75.0,
            "rmsd_max": 3.0,
            "ipsae_min": 0.55,
            "charge_abs_max": 8.0,
            "hydro_frac_max": 0.48,
            "total_cdr_max": 9_999,
            "cdr_h3_max": 9_999,
        },
    },
}


DEAMIDATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"NG"), "high"),
    (re.compile(r"NS"), "medium"),
    (re.compile(r"NT"), "medium"),
    (re.compile(r"NA"), "low"),
]
ISOMERIZATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"DG"), "high"),
    (re.compile(r"DS"), "medium"),
]
GLYCOSYLATION_PATTERN = re.compile(r"N[^P][ST]")
CDR_REJECT_PATTERNS = [re.compile(r"NG"), re.compile(r"DG")]


@dataclass
class Liability:
    """A detected sequence liability with location tag."""

    type: str
    position: int
    motif: str
    severity: str
    location: str = "framework"  # "cdr" | "interface" | "framework"


@dataclass
class ScreenResult:
    """Per-design screening verdict and computed columns."""

    name: str
    verdict: str
    reason_codes: list[str] = field(default_factory=list)
    liability_count: int = 0
    weighted_liability_count: int = 0
    net_charge: float = 0.0
    hydrophobic_fraction: float = 0.0
    total_cdr_length: int = 0
    composite_score: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


def compute_net_charge(sequence: str, ph: float = 7.4) -> float:
    """Henderson-Hasselbalch net charge with standard pKa values."""
    if not sequence:
        return 0.0
    pka = {"D": 3.65, "E": 4.25, "H": 6.00, "C": 8.18, "Y": 10.07, "K": 10.53, "R": 12.48}
    charge = 0.0
    seq = sequence.upper()
    for aa in seq:
        if aa in ("D", "E", "C", "Y"):
            charge -= 1.0 / (1.0 + 10 ** (pka.get(aa, 7.0) - ph))
        elif aa in ("K", "R", "H"):
            charge += 1.0 / (1.0 + 10 ** (ph - pka.get(aa, 7.0)))
    charge += 1.0 / (1.0 + 10 ** (ph - 9.69))
    charge -= 1.0 / (1.0 + 10 ** (2.34 - ph))
    return charge


def scan_liabilities(
    sequence: str,
    cdr_regions: list[tuple[int, int]] | None = None,
) -> list[Liability]:
    """Scan a sequence for PTM and sequence liabilities; tag each by location."""
    sequence = sequence.upper()
    liabilities: list[Liability] = []
    cdr_regions = cdr_regions or []

    def loc_for(pos: int) -> str:
        for start, end in cdr_regions:
            if start <= pos < end:
                return "cdr"
        return "framework"

    for pattern, severity in DEAMIDATION_PATTERNS:
        for m in pattern.finditer(sequence):
            liabilities.append(
                Liability("deamidation", m.start(), m.group(), severity, loc_for(m.start()))
            )
    for pattern, severity in ISOMERIZATION_PATTERNS:
        for m in pattern.finditer(sequence):
            liabilities.append(
                Liability("isomerization", m.start(), m.group(), severity, loc_for(m.start()))
            )
    for m in GLYCOSYLATION_PATTERN.finditer(sequence):
        liabilities.append(
            Liability("glycosylation", m.start(), m.group(), "medium", loc_for(m.start()))
        )

    cys_count = sequence.count("C")
    if cys_count % 2 != 0:
        liabilities.append(
            Liability("free_cysteine", -1, f"{cys_count} Cys", "high", "framework")
        )

    return liabilities


def weighted_count(liabilities: list[Liability]) -> int:
    """Apply location weights (CDR=3, interface=2, framework=1)."""
    weights = {"cdr": 3, "interface": 2, "framework": 1}
    return sum(weights.get(L.location, 1) for L in liabilities)


def cdr_has_critical_liability(
    sequence: str,
    cdr_regions: list[tuple[int, int]],
) -> bool:
    """True if any CDR contains NG or DG (HIGH severity, rejection trigger)."""
    for start, end in cdr_regions:
        segment = sequence[start:end]
        for pat in CDR_REJECT_PATTERNS:
            if pat.search(segment):
                return True
    return False


def total_cdr_len(cdr_regions: list[tuple[int, int]]) -> int:
    """Sum of all CDR lengths."""
    return sum(end - start for start, end in cdr_regions)


def cdr_h3_len(cdr_regions: list[tuple[int, int]]) -> int:
    """Length of CDR-H3 (assumed last entry)."""
    if not cdr_regions:
        return 0
    start, end = cdr_regions[-1]
    return end - start


def parse_cdr_regions(raw: Any) -> list[tuple[int, int]]:
    """Parse cdr_regions from JSON string or list-like."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [(int(s), int(e)) for s, e in raw]


def load_designs(path: Path) -> list[dict[str, Any]]:
    """Load a designs CSV or JSON file into a list of dicts."""
    if path.suffix.lower() == ".json":
        with path.open() as f:
            data = json.load(f)
        if isinstance(data, dict) and "designs" in data:
            data = data["designs"]
        return list(data)
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def screen_one(
    design: dict[str, Any],
    modality: str,
    thresholds: dict[str, float],
    allow_free_cys: bool,
) -> ScreenResult:
    """Apply all screening filters to a single design row."""
    name = str(design.get("name", "unknown"))
    sequence = str(design.get("sequence", "")).upper()
    iptm = _to_float(design.get("iptm"))
    plddt = _to_float(design.get("plddt"))
    rmsd = _to_float(design.get("rmsd_ca"), default=999.0)
    ipsae = _to_float(design.get("ipsae_min"))
    cdr_regions = parse_cdr_regions(design.get("cdr_regions"))

    liabilities = scan_liabilities(sequence, cdr_regions)
    if allow_free_cys:
        liabilities = [L for L in liabilities if L.type != "free_cysteine"]

    weighted = weighted_count(liabilities)
    charge = compute_net_charge(sequence)
    hydro = (
        sum(1 for aa in sequence if aa in HYDROPHOBIC_AAS) / len(sequence)
        if sequence
        else 0.0
    )
    cdr_total = total_cdr_len(cdr_regions)
    h3 = cdr_h3_len(cdr_regions)

    reasons: list[str] = []
    if iptm < thresholds["iptm_min"]:
        reasons.append("LOW_IPTM")
    if plddt < thresholds["plddt_min"]:
        reasons.append("LOW_PLDDT")
    if rmsd > thresholds["rmsd_max"]:
        reasons.append("FAIL_RMSD")
    if ipsae < thresholds["ipsae_min"]:
        reasons.append("LOW_IPSAE")
    if abs(charge) > thresholds["charge_abs_max"]:
        reasons.append("EXTREME_CHARGE")
    if hydro > thresholds["hydro_frac_max"]:
        reasons.append("HIGH_HYDROPHOBIC")
    if any(L.type == "free_cysteine" for L in liabilities):
        reasons.append("ODD_CYS")
    if cdr_regions and cdr_has_critical_liability(sequence, cdr_regions):
        reasons.append("CDR_NG_OR_DG")
    if cdr_regions and cdr_total > thresholds["total_cdr_max"]:
        reasons.append("LONG_CDR_TOTAL")
    if cdr_regions and h3 > thresholds["cdr_h3_max"]:
        reasons.append("LONG_CDR3")

    if reasons:
        verdict = "FAIL"
    elif plddt < thresholds["plddt_min"] + 5 or ipsae < thresholds["ipsae_min"] + 0.05:
        verdict = "MARGINAL"
    else:
        verdict = "PASS"

    return ScreenResult(
        name=name,
        verdict=verdict,
        reason_codes=reasons,
        liability_count=len(liabilities),
        weighted_liability_count=weighted,
        net_charge=charge,
        hydrophobic_fraction=hydro,
        total_cdr_length=cdr_total,
        composite_score=0.0,  # computed in second pass after batch max
        raw={**design, "iptm": iptm, "plddt": plddt, "rmsd_ca": rmsd, "ipsae_min": ipsae},
    )


def compute_composite(results: list[ScreenResult], liability_cap: int = 5) -> None:
    """Compute composite scores in place: 0.50 ipSAE + 0.30 ipTM + 0.20 (1 - norm liab).

    Normalises weighted liability count by an ABSOLUTE cap (default 5) so the
    same design produces the same composite_score regardless of batch
    composition. This matches by-scoring/composite_score.py and the formula
    documented in by-scoring/references/composite-score.md.
    """
    if not results:
        return
    if liability_cap <= 0:
        liability_cap = 1  # avoid div-by-zero; treat any liability as full
    for r in results:
        iptm = _to_float(r.raw.get("iptm"))
        ipsae = _to_float(r.raw.get("ipsae_min"))
        norm_liab = min(1.0, r.weighted_liability_count / liability_cap)
        r.composite_score = round(
            0.50 * ipsae + 0.30 * iptm + 0.20 * (1.0 - norm_liab),
            4,
        )


def write_output(results: list[ScreenResult], out_path: Path) -> None:
    """Write screening results to CSV."""
    fieldnames = [
        "name",
        "verdict",
        "reason_codes",
        "iptm",
        "plddt",
        "rmsd_ca",
        "ipsae_min",
        "liability_count",
        "weighted_liability_count",
        "net_charge",
        "hydrophobic_fraction",
        "total_cdr_length",
        "composite_score",
    ]
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "name": r.name,
                    "verdict": r.verdict,
                    "reason_codes": ";".join(r.reason_codes),
                    "iptm": r.raw.get("iptm"),
                    "plddt": r.raw.get("plddt"),
                    "rmsd_ca": r.raw.get("rmsd_ca"),
                    "ipsae_min": r.raw.get("ipsae_min"),
                    "liability_count": r.liability_count,
                    "weighted_liability_count": r.weighted_liability_count,
                    "net_charge": round(r.net_charge, 3),
                    "hydrophobic_fraction": round(r.hydrophobic_fraction, 3),
                    "total_cdr_length": r.total_cdr_length,
                    "composite_score": r.composite_score,
                }
            )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--designs", required=True, type=Path, help="Input CSV or JSON")
    parser.add_argument("--output", required=True, type=Path, help="Output CSV path")
    parser.add_argument(
        "--modality",
        default="antibody",
        choices=["antibody", "nanobody", "binder"],
        help="Default modality if not provided per design",
    )
    parser.add_argument(
        "--thresholds-profile",
        default="production",
        choices=["exploratory", "production", "strict"],
        help="Threshold profile (see references/filter-thresholds.md)",
    )
    parser.add_argument(
        "--allow-free-cys",
        action="store_true",
        help="Skip the odd-Cys parity check (for engineered free Cys designs)",
    )
    args = parser.parse_args()

    if not args.designs.exists():
        sys.exit(f"Input file not found: {args.designs}")

    designs = load_designs(args.designs)
    results: list[ScreenResult] = []
    for design in designs:
        modality = str(design.get("modality") or args.modality)
        if modality not in THRESHOLDS[args.thresholds_profile]:
            modality = args.modality
        thresholds = THRESHOLDS[args.thresholds_profile][modality]
        results.append(screen_one(design, modality, thresholds, args.allow_free_cys))

    compute_composite(results)
    results.sort(key=lambda r: r.composite_score, reverse=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_output(results, args.output)

    n = len(results)
    n_pass = sum(1 for r in results if r.verdict == "PASS")
    n_marg = sum(1 for r in results if r.verdict == "MARGINAL")
    n_fail = sum(1 for r in results if r.verdict == "FAIL")
    pct = (n_pass / n * 100) if n else 0.0
    print(
        f"✓ screening completed: {n} designs / {n_pass} PASS ({pct:.1f}%) / "
        f"{n_marg} MARGINAL / {n_fail} FAIL -> {args.output}"
    )


if __name__ == "__main__":
    main()
