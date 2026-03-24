#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "numpy>=1.24",
# ]
# ///
"""Screening MCP Server — protein sequence screening and scoring tools for BY agent.

Self-contained: all screening logic is inlined. No proteus_cli dependency.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("by-screening")


# ===========================================================================
# Inlined screening logic (replaces proteus_cli.screening.*)
# ===========================================================================


# ---------------------------------------------------------------------------
# Liability scanning  (replaces proteus_cli.screening.liabilities)
# ---------------------------------------------------------------------------

@dataclass
class Liability:
    """A single detected sequence liability."""
    type: str
    position: int
    motif: str
    severity: str  # "high", "medium", "low"
    description: str


_DEAMIDATION_MOTIFS = [
    (re.compile(r"N[GS]"), "high",   "Asn deamidation hotspot (N{m})"),
    (re.compile(r"N[T]"),  "medium", "Asn deamidation (NT)"),
    (re.compile(r"N[A]"),  "low",    "Asn deamidation (NA, low risk)"),
]

_ISOMERIZATION_MOTIFS = [
    (re.compile(r"D[GS]"), "high",   "Asp isomerization hotspot (D{m})"),
    (re.compile(r"D[T]"),  "medium", "Asp isomerization (DT)"),
]

_GLYCOSYLATION_RE = re.compile(r"N(?=[^P][ST])")  # NX[ST] where X != P


def _scan_liabilities(sequence: str) -> list[Liability]:
    """Scan a protein sequence for PTM liabilities."""
    seq = sequence.upper()
    liabilities: list[Liability] = []

    # Deamidation
    for pattern, severity, desc_tmpl in _DEAMIDATION_MOTIFS:
        for m in pattern.finditer(seq):
            liabilities.append(Liability(
                type="deamidation",
                position=m.start() + 1,  # 1-indexed
                motif=m.group(),
                severity=severity,
                description=desc_tmpl.replace("{m}", m.group()),
            ))

    # Isomerization
    for pattern, severity, desc_tmpl in _ISOMERIZATION_MOTIFS:
        for m in pattern.finditer(seq):
            liabilities.append(Liability(
                type="isomerization",
                position=m.start() + 1,
                motif=m.group(),
                severity=severity,
                description=desc_tmpl.replace("{m}", m.group()),
            ))

    # Met oxidation
    for i, aa in enumerate(seq):
        if aa == "M":
            liabilities.append(Liability(
                type="oxidation",
                position=i + 1,
                motif="M",
                severity="medium",
                description="Methionine oxidation risk",
            ))

    # Free Cys
    cys_positions = [i for i, aa in enumerate(seq) if aa == "C"]
    # If odd number of Cys, at least one is unpaired; flag all for review
    if len(cys_positions) % 2 != 0:
        for pos in cys_positions:
            liabilities.append(Liability(
                type="free_cysteine",
                position=pos + 1,
                motif="C",
                severity="high",
                description="Potentially unpaired cysteine (odd total Cys count)",
            ))

    # N-linked glycosylation NX[ST] where X != P
    for m in _GLYCOSYLATION_RE.finditer(seq):
        liabilities.append(Liability(
            type="glycosylation",
            position=m.start() + 1,
            motif=seq[m.start():m.start() + 3],
            severity="medium",
            description=f"N-linked glycosylation motif ({seq[m.start():m.start()+3]})",
        ))

    # Sort by position
    liabilities.sort(key=lambda l: l.position)
    return liabilities


# ---------------------------------------------------------------------------
# Net charge  (replaces proteus_cli.screening.liabilities.compute_net_charge)
# ---------------------------------------------------------------------------

# Standard pKa values
_PKA = {
    "D": 3.65,   # Asp
    "E": 4.25,   # Glu
    "H": 6.00,   # His
    "C": 8.18,   # Cys (free)
    "Y": 10.07,  # Tyr
    "K": 10.54,  # Lys
    "R": 12.48,  # Arg
}
_PKA_NTERM = 9.69
_PKA_CTERM = 2.34


def _compute_net_charge(sequence: str, ph: float = 7.4) -> float:
    """Estimate net charge using Henderson-Hasselbalch."""
    seq = sequence.upper()
    charge = 0.0

    # N-terminal amino group (positive when protonated)
    charge += 1.0 / (1.0 + 10 ** (ph - _PKA_NTERM))
    # C-terminal carboxyl group (negative when deprotonated)
    charge -= 1.0 / (1.0 + 10 ** (_PKA_CTERM - ph))

    for aa in seq:
        if aa in ("D", "E"):
            # Acidic: negative when deprotonated
            charge -= 1.0 / (1.0 + 10 ** (_PKA[aa] - ph))
        elif aa in ("C", "Y"):
            # Weakly acidic side chains
            charge -= 1.0 / (1.0 + 10 ** (_PKA[aa] - ph))
        elif aa in ("K", "R", "H"):
            # Basic: positive when protonated
            charge += 1.0 / (1.0 + 10 ** (ph - _PKA[aa]))

    return charge


# ---------------------------------------------------------------------------
# Developability assessment  (replaces proteus_cli.screening.developability)
# ---------------------------------------------------------------------------

_HYDROPHOBIC = set("AVILFWMP")


@dataclass
class DevelopabilityReport:
    """Developability assessment result."""
    overall_risk: str  # "low", "medium", "high"
    hydrophobic_fraction: float
    proline_fraction: float
    glycine_fraction: float
    net_charge: float
    total_cdr_length: int
    liability_count: int
    flags: list[str] = field(default_factory=list)


def _assess_developability(
    sequence: str,
    cdr_regions: list[tuple[int, int]] | None = None,
    liabilities: list[Liability] | None = None,
) -> DevelopabilityReport:
    """TAP-inspired developability assessment."""
    seq = sequence.upper()
    n = len(seq)
    if n == 0:
        return DevelopabilityReport(
            overall_risk="high", hydrophobic_fraction=0, proline_fraction=0,
            glycine_fraction=0, net_charge=0, total_cdr_length=0,
            liability_count=0, flags=["Empty sequence"],
        )

    hydro_frac = sum(1 for aa in seq if aa in _HYDROPHOBIC) / n
    pro_frac = seq.count("P") / n
    gly_frac = seq.count("G") / n
    charge = _compute_net_charge(seq)

    total_cdr = 0
    if cdr_regions:
        for start, end in cdr_regions:
            total_cdr += max(0, end - start)

    liab_count = len(liabilities) if liabilities is not None else len(_scan_liabilities(seq))

    flags: list[str] = []
    risk_score = 0

    if hydro_frac > 0.55:
        flags.append(f"High hydrophobic fraction: {hydro_frac:.2%}")
        risk_score += 2
    elif hydro_frac > 0.45:
        flags.append(f"Elevated hydrophobic fraction: {hydro_frac:.2%}")
        risk_score += 1

    if abs(charge) > 10:
        flags.append(f"Extreme net charge: {charge:.1f}")
        risk_score += 2
    elif abs(charge) > 6:
        flags.append(f"High net charge: {charge:.1f}")
        risk_score += 1

    if total_cdr > 0:
        # CDR length checks (typical for VHH: CDR3 ~12-18aa)
        if cdr_regions:
            for i, (start, end) in enumerate(cdr_regions):
                cdr_len = end - start
                if cdr_len > 25:
                    flags.append(f"CDR{i+1} unusually long: {cdr_len}aa")
                    risk_score += 1
                elif cdr_len < 3:
                    flags.append(f"CDR{i+1} unusually short: {cdr_len}aa")
                    risk_score += 1

    if liab_count > 5:
        flags.append(f"High liability count: {liab_count}")
        risk_score += 2
    elif liab_count > 3:
        flags.append(f"Moderate liability count: {liab_count}")
        risk_score += 1

    if pro_frac > 0.12:
        flags.append(f"High proline fraction: {pro_frac:.2%}")
        risk_score += 1

    if gly_frac > 0.15:
        flags.append(f"High glycine fraction: {gly_frac:.2%}")
        risk_score += 1

    if risk_score >= 4:
        overall = "high"
    elif risk_score >= 2:
        overall = "medium"
    else:
        overall = "low"

    return DevelopabilityReport(
        overall_risk=overall,
        hydrophobic_fraction=round(hydro_frac, 4),
        proline_fraction=round(pro_frac, 4),
        glycine_fraction=round(gly_frac, 4),
        net_charge=round(charge, 4),
        total_cdr_length=total_cdr,
        liability_count=liab_count,
        flags=flags,
    )


# ---------------------------------------------------------------------------
# ipSAE scoring  (replaces proteus_cli.scoring.ipsae)
# ---------------------------------------------------------------------------

def _ipsae_d0(n0: int) -> float:
    """Compute d0 normalization factor for ipSAE."""
    clamped = max(n0, 19)
    return 1.24 * (clamped - 15) ** (1.0 / 3.0) - 1.8


def _compute_ipsae(
    pae_matrix,  # numpy 2D array
    design_indices: list[int],
    target_indices: list[int],
    pae_cutoff: float = 10.0,
) -> dict[str, float]:
    """Compute directional ipSAE scores from a PAE matrix.

    Args:
        pae_matrix: (N, N) numpy array of predicted aligned errors.
        design_indices: Row/col indices for design chain residues.
        target_indices: Row/col indices for target chain residues.
        pae_cutoff: PAE threshold (default 10.0 for Protenix/AF3).

    Returns:
        Dict with design_to_target_ipsae, target_to_design_ipsae, design_ipsae_min.
    """
    import numpy as np

    d_idx = np.array(design_indices)
    t_idx = np.array(target_indices)

    # Design-to-target: rows=design, cols=target
    dt_block = pae_matrix[np.ix_(d_idx, t_idx)]
    # Target-to-design: rows=target, cols=design
    td_block = pae_matrix[np.ix_(t_idx, d_idx)]

    def _score_block(block: "np.ndarray", n_aligned: int) -> float:
        if n_aligned < 1:
            return 0.0
        d0 = _ipsae_d0(n_aligned)
        if d0 <= 0:
            return 0.0
        # For each row, find contacts below cutoff and compute TM-like sum
        contact_mask = block < pae_cutoff
        total = 0.0
        n_rows = block.shape[0]
        for i in range(n_rows):
            row_contacts = block[i][contact_mask[i]]
            if len(row_contacts) > 0:
                total += np.sum(1.0 / (1.0 + (row_contacts / d0) ** 2))
        # Normalize by number of aligned residues (columns)
        n_cols = block.shape[1]
        if n_cols == 0:
            return 0.0
        score = total / (n_rows * n_cols)
        return float(min(score, 1.0))

    dt_score = _score_block(dt_block, len(target_indices))
    td_score = _score_block(td_block, len(design_indices))

    return {
        "design_to_target_ipsae": round(dt_score, 4),
        "target_to_design_ipsae": round(td_score, 4),
        "design_ipsae_min": round(min(dt_score, td_score), 4),
    }


def _interpret_ipsae(score: float) -> str:
    """Human-readable interpretation of an ipSAE score."""
    if score > 0.8:
        return "Excellent binding interface (ipSAE > 0.8)"
    elif score > 0.5:
        return "Good binding interface (ipSAE > 0.5)"
    elif score > 0.3:
        return "Moderate — may need refinement (ipSAE 0.3-0.5)"
    elif score > 0.1:
        return "Weak — likely poor binding (ipSAE 0.1-0.3)"
    else:
        return "Very poor — consider redesign (ipSAE < 0.1)"


def _score_npz(
    npz_path: Path,
    design_chain_ids: list[int],
    target_chain_ids: list[int],
    pae_cutoff: float = 10.0,
) -> dict[str, float]:
    """Score ipSAE from a Protenix NPZ file."""
    import numpy as np

    data = np.load(str(npz_path))
    if "pae" not in data:
        raise ValueError(f"NPZ file missing 'pae' key. Available keys: {list(data.keys())}")

    pae = data["pae"]
    if pae.ndim == 3:
        # Multi-model: use the first model
        pae = pae[0]

    # Build index arrays from chain IDs
    if "asym_id" in data:
        asym = data["asym_id"]
        if asym.ndim > 1:
            asym = asym[0]
        design_idx = [i for i, a in enumerate(asym) if int(a) in design_chain_ids]
        target_idx = [i for i, a in enumerate(asym) if int(a) in target_chain_ids]
    else:
        raise ValueError("NPZ file missing 'asym_id' key needed to map chain IDs to residue indices.")

    return _compute_ipsae(pae, design_idx, target_idx, pae_cutoff)


def _score_multi_seed(
    npz_paths: list[str],
    design_chain_ids: list[int] | None,
    target_chain_ids: list[int] | None,
    design_chain: str = "A",
    target_chain: str = "B",
    pae_cutoff: float = 10.0,
    aggregation: str = "best",
) -> dict[str, Any]:
    """Score ipSAE across multiple seed outputs."""
    import numpy as np

    per_seed: list[dict] = []

    for idx, path_str in enumerate(npz_paths):
        p = Path(path_str)
        if not p.exists():
            per_seed.append({"seed_idx": idx, "file": path_str, "error": "File not found"})
            continue

        try:
            if p.suffix == ".json":
                # Confidence JSON format
                raw = json.loads(p.read_text())
                pae = np.array(raw.get("pae", raw.get("predicted_aligned_error", [])))
                if pae.ndim == 0 or pae.size == 0:
                    per_seed.append({"seed_idx": idx, "error": "No PAE data in JSON"})
                    continue

                # JSON uses chain letters — build indices
                chain_ids = raw.get("chain_ids", raw.get("chain_id", []))
                if not chain_ids:
                    per_seed.append({"seed_idx": idx, "error": "No chain IDs in JSON"})
                    continue
                d_idx = [i for i, c in enumerate(chain_ids) if c == design_chain]
                t_idx = [i for i, c in enumerate(chain_ids) if c == target_chain]

                scores = _compute_ipsae(pae, d_idx, t_idx, pae_cutoff)
            else:
                # NPZ format
                if design_chain_ids is None or target_chain_ids is None:
                    per_seed.append({"seed_idx": idx, "error": "NPZ requires design/target chain IDs"})
                    continue
                scores = _score_npz(p, design_chain_ids, target_chain_ids, pae_cutoff)

            scores["seed_idx"] = idx
            scores["file"] = str(p)
            per_seed.append(scores)

        except Exception as exc:
            per_seed.append({"seed_idx": idx, "file": path_str, "error": str(exc)})

    # Filter successful scores
    valid = [s for s in per_seed if "design_ipsae_min" in s]
    if not valid:
        return {"error": "No valid seed scores computed", "per_seed": per_seed}

    mins = [s["design_ipsae_min"] for s in valid]
    mean_val = float(np.mean(mins))
    std_val = float(np.std(mins))

    if aggregation == "mean":
        best = min(valid, key=lambda s: abs(s["design_ipsae_min"] - mean_val))
    elif aggregation == "median":
        median_val = float(np.median(mins))
        best = min(valid, key=lambda s: abs(s["design_ipsae_min"] - median_val))
    else:  # "best"
        best = max(valid, key=lambda s: s["design_ipsae_min"])

    return {
        "best_seed_idx": best["seed_idx"],
        "best_ipsae_min": best["design_ipsae_min"],
        "best_file": best.get("file", ""),
        "mean_ipsae_min": round(mean_val, 4),
        "std_ipsae_min": round(std_val, 4),
        "num_seeds": len(valid),
        "num_failed": len(per_seed) - len(valid),
        "aggregation": aggregation,
        "per_seed": per_seed,
    }


def _score_multi_seed_dir(
    npz_dir: str,
    design_chain_ids: list[int] | None,
    target_chain_ids: list[int] | None,
    design_chain: str = "A",
    target_chain: str = "B",
    pae_cutoff: float = 10.0,
    aggregation: str = "best",
) -> dict[str, Any]:
    """Score ipSAE for all NPZ/JSON files in a directory."""
    d = Path(npz_dir)
    if not d.is_dir():
        return {"error": f"Not a directory: {npz_dir}"}

    files = sorted(
        list(d.glob("*.npz")) + list(d.glob("*confidence*.json"))
    )
    if not files:
        return {"error": f"No NPZ or confidence JSON files found in {npz_dir}"}

    return _score_multi_seed(
        [str(f) for f in files],
        design_chain_ids, target_chain_ids,
        design_chain, target_chain, pae_cutoff, aggregation,
    )


# ---------------------------------------------------------------------------
# Diversity analysis  (replaces proteus_cli.screening.diversity)
# ---------------------------------------------------------------------------

def _pairwise_identity(seq1: str, seq2: str) -> float:
    """Compute pairwise sequence identity (matching positions / min length)."""
    s1, s2 = seq1.upper(), seq2.upper()
    min_len = min(len(s1), len(s2))
    if min_len == 0:
        return 0.0
    matches = sum(1 for a, b in zip(s1, s2) if a == b)
    return matches / min_len


def _diversity_report(
    sequences: list[dict],
    identity_threshold: float = 0.9,
) -> dict[str, Any]:
    """Analyze sequence diversity by single-linkage clustering."""
    seqs = [s["sequence"].upper() for s in sequences]
    n = len(seqs)
    if n == 0:
        return {"num_sequences": 0, "num_clusters": 0, "diversity_ratio": 0}

    # Build pairwise identity matrix and cluster
    # Simple single-linkage clustering
    cluster_id = list(range(n))

    total_identity = 0.0
    num_pairs = 0

    for i in range(n):
        for j in range(i + 1, n):
            ident = _pairwise_identity(seqs[i], seqs[j])
            total_identity += ident
            num_pairs += 1
            if ident >= identity_threshold:
                # Merge clusters
                old_id = cluster_id[j]
                new_id = cluster_id[i]
                for k in range(n):
                    if cluster_id[k] == old_id:
                        cluster_id[k] = new_id

    num_clusters = len(set(cluster_id))
    avg_identity = total_identity / num_pairs if num_pairs > 0 else 0.0

    # Cluster sizes
    from collections import Counter
    cluster_sizes = Counter(cluster_id)
    largest = max(cluster_sizes.values()) if cluster_sizes else 0
    singletons = sum(1 for v in cluster_sizes.values() if v == 1)

    diversity_ratio = num_clusters / n if n > 0 else 0.0
    redundancy_warning = diversity_ratio < 0.3

    return {
        "num_sequences": n,
        "num_clusters": num_clusters,
        "diversity_ratio": round(diversity_ratio, 4),
        "avg_pairwise_identity": round(avg_identity, 4),
        "largest_cluster_size": largest,
        "singleton_clusters": singletons,
        "redundancy_warning": redundancy_warning,
    }


def _format_diversity(report: dict) -> str:
    """Format diversity report as text."""
    lines = [
        f"Sequences: {report['num_sequences']}",
        f"Clusters:  {report['num_clusters']}",
        f"Diversity: {report['diversity_ratio']:.1%}",
        f"Avg identity: {report['avg_pairwise_identity']:.1%}",
        f"Largest cluster: {report['largest_cluster_size']}",
        f"Singletons: {report['singleton_clusters']}",
    ]
    if report.get("redundancy_warning"):
        lines.append("WARNING: Low diversity — consider broadening search parameters")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Failure diagnosis  (replaces proteus_cli.screening.diagnosis)
# ---------------------------------------------------------------------------

@dataclass
class FeatureAnalysis:
    feature_name: str
    test_type: str
    statistic: float
    p_value: float
    effect_size: float
    passed_mean: float
    failed_mean: float
    interpretation: str


@dataclass
class DiagnosisReport:
    total_designs: int
    passed: int
    failed: int
    pass_rate: float
    discriminating_features: list[FeatureAnalysis]
    summary: str
    recommendations: list[str]


def _diagnose_failures(
    designs: list[dict],
    pass_key: str = "status",
    pass_value: str = "PASS",
) -> DiagnosisReport:
    """Diagnose why designs fail screening using simple statistics."""
    passed = [d for d in designs if d.get(pass_key) == pass_value]
    failed = [d for d in designs if d.get(pass_key) != pass_value]

    total = len(designs)
    n_pass = len(passed)
    n_fail = len(failed)
    rate = n_pass / total if total > 0 else 0.0

    # Identify numeric features
    numeric_keys: set[str] = set()
    for d in designs:
        for k, v in d.items():
            if isinstance(v, (int, float)) and k != pass_key:
                numeric_keys.add(k)

    features: list[FeatureAnalysis] = []

    for key in sorted(numeric_keys):
        p_vals = [d[key] for d in passed if key in d and isinstance(d[key], (int, float))]
        f_vals = [d[key] for d in failed if key in d and isinstance(d[key], (int, float))]

        if len(p_vals) < 2 or len(f_vals) < 2:
            continue

        p_mean = sum(p_vals) / len(p_vals)
        f_mean = sum(f_vals) / len(f_vals)

        # Cohen's d as effect size
        p_var = sum((x - p_mean) ** 2 for x in p_vals) / (len(p_vals) - 1)
        f_var = sum((x - f_mean) ** 2 for x in f_vals) / (len(f_vals) - 1)
        pooled_std = math.sqrt((p_var + f_var) / 2) if (p_var + f_var) > 0 else 1.0
        effect = abs(p_mean - f_mean) / pooled_std

        # Simple Mann-Whitney U approximation using rank-sum
        combined = [(v, "p") for v in p_vals] + [(v, "f") for v in f_vals]
        combined.sort(key=lambda x: x[0])
        rank_sum_p = sum(i + 1 for i, (_, g) in enumerate(combined) if g == "p")
        n1, n2 = len(p_vals), len(f_vals)
        u = rank_sum_p - n1 * (n1 + 1) / 2
        # Normal approximation for p-value
        mu = n1 * n2 / 2
        sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12) if (n1 + n2 + 1) > 0 else 1.0
        z = (u - mu) / sigma if sigma > 0 else 0.0
        # Two-tailed p-value approximation
        p_value = min(1.0, 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2)))))

        if effect > 0.5:
            interp = f"{key}: large difference (passed mean={p_mean:.3f} vs failed mean={f_mean:.3f})"
        elif effect > 0.2:
            interp = f"{key}: moderate difference"
        else:
            interp = f"{key}: small difference"

        features.append(FeatureAnalysis(
            feature_name=key,
            test_type="Mann-Whitney U (approximation)",
            statistic=round(u, 4),
            p_value=round(p_value, 6),
            effect_size=round(effect, 4),
            passed_mean=round(p_mean, 4),
            failed_mean=round(f_mean, 4),
            interpretation=interp,
        ))

    features.sort(key=lambda f: f.p_value)

    # Generate recommendations
    recs: list[str] = []
    for feat in features[:3]:
        if feat.effect_size > 0.5:
            if feat.passed_mean > feat.failed_mean:
                recs.append(f"Increase {feat.feature_name} threshold (passed designs have higher values)")
            else:
                recs.append(f"Reduce {feat.feature_name} threshold (passed designs have lower values)")

    if rate < 0.1:
        recs.append("Consider relaxing screening thresholds — pass rate is very low")
    if n_fail > 0 and not recs:
        recs.append("No strong discriminating features found — failures may be stochastic")

    summary = (
        f"Pass rate: {rate:.1%} ({n_pass}/{total}). "
        f"Top discriminating feature: {features[0].feature_name if features else 'none'}"
    )

    return DiagnosisReport(
        total_designs=total,
        passed=n_pass,
        failed=n_fail,
        pass_rate=rate,
        discriminating_features=features,
        summary=summary,
        recommendations=recs,
    )


def _format_diagnosis(diag: DiagnosisReport) -> str:
    """Format diagnosis report as text."""
    lines = [
        f"Pass rate: {diag.pass_rate:.1%} ({diag.passed}/{diag.total_designs})",
        "",
        "Discriminating features:",
    ]
    for f in diag.discriminating_features[:5]:
        lines.append(f"  {f.feature_name}: effect={f.effect_size:.2f}, p={f.p_value:.4f}")
    lines.append("")
    lines.append("Recommendations:")
    for r in diag.recommendations:
        lines.append(f"  - {r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pareto front  (replaces proteus_cli.screening.pareto)
# ---------------------------------------------------------------------------

def _is_dominated(a: dict, b: dict, objectives: list[tuple[str, str]]) -> bool:
    """Check if design 'a' is dominated by design 'b'."""
    dominated = True
    strictly_worse = False
    for metric, direction in objectives:
        va = a.get(metric, 0)
        vb = b.get(metric, 0)
        if direction == "maximize":
            if va > vb:
                dominated = False
            if vb > va:
                strictly_worse = True
        else:  # minimize
            if va < vb:
                dominated = False
            if vb < va:
                strictly_worse = True
    return dominated and strictly_worse


def _pareto_front(
    designs: list[dict],
    objectives: list[tuple[str, str]] | None = None,
) -> list[dict]:
    """Extract Pareto-optimal designs."""
    if objectives is None:
        objectives = [
            ("ipsae_min", "maximize"),
            ("iptm", "maximize"),
            ("liabilities", "minimize"),
        ]

    front: list[dict] = []
    for i, d in enumerate(designs):
        is_dom = False
        for j, other in enumerate(designs):
            if i != j and _is_dominated(d, other, objectives):
                is_dom = True
                break
        if not is_dom:
            d_copy = dict(d)
            d_copy["pareto_rank"] = 1
            front.append(d_copy)

    # Sort by first objective
    if objectives:
        first_metric, first_dir = objectives[0]
        front.sort(
            key=lambda x: x.get(first_metric, 0),
            reverse=(first_dir == "maximize"),
        )

    return front


def _format_pareto(front: list[dict], objectives: list[tuple[str, str]] | None = None) -> str:
    """Format Pareto front as text table."""
    if objectives is None:
        objectives = [
            ("ipsae_min", "maximize"),
            ("iptm", "maximize"),
            ("liabilities", "minimize"),
        ]
    metrics = [o[0] for o in objectives]
    header = "Name\t" + "\t".join(metrics)
    lines = [header, "-" * len(header) * 2]
    for d in front:
        name = d.get("design_name", d.get("name", "?"))
        vals = "\t".join(f"{d.get(m, 'N/A')}" for m in metrics)
        lines.append(f"{name}\t{vals}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sequence alignment  (replaces proteus_cli.screening.alignment)
# Minimal implementation without BioPython dependency
# ---------------------------------------------------------------------------

def _pairwise_align(seq1: str, seq2: str) -> dict:
    """Simple pairwise alignment using Needleman-Wunsch-like identity."""
    s1, s2 = seq1.upper(), seq2.upper()
    min_len = min(len(s1), len(s2))
    max_len = max(len(s1), len(s2))
    matches = sum(1 for a, b in zip(s1, s2) if a == b) if min_len > 0 else 0
    identity = matches / max_len if max_len > 0 else 0.0

    return {
        "mode": "pairwise",
        "length_1": len(s1),
        "length_2": len(s2),
        "matches": matches,
        "identity": round(identity, 4),
        "aligned_1": s1[:min_len],
        "aligned_2": s2[:min_len],
    }


def _cdr_align(sequences: list[dict], cdr_key: str = "cdr3_sequence") -> dict:
    """Compute CDR3 pairwise identity matrix."""
    cdrs = [s.get(cdr_key, "").upper() for s in sequences]
    names = [s.get("name", s.get("design_name", f"seq_{i}")) for i, s in enumerate(sequences)]
    n = len(cdrs)
    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            elif i < j:
                ident = _pairwise_identity(cdrs[i], cdrs[j])
                matrix[i][j] = round(ident, 4)
                matrix[j][i] = round(ident, 4)
    return {
        "mode": "cdr",
        "names": names,
        "identity_matrix": matrix,
        "num_sequences": n,
    }


def _multiple_align(sequences: list[dict], key: str = "sequence") -> dict:
    """Star alignment from centroid — simplified consensus."""
    seqs = [s.get(key, "").upper() for s in sequences]
    names = [s.get("name", s.get("design_name", f"seq_{i}")) for i, s in enumerate(sequences)]

    if not seqs:
        return {"mode": "multiple", "consensus": "", "num_sequences": 0}

    # Find centroid (sequence with highest avg identity to all others)
    best_avg = -1.0
    centroid_idx = 0
    for i, s1 in enumerate(seqs):
        avg = sum(_pairwise_identity(s1, s2) for j, s2 in enumerate(seqs) if i != j)
        if avg > best_avg:
            best_avg = avg
            centroid_idx = i

    # Build consensus from centroid
    centroid = seqs[centroid_idx]
    consensus = list(centroid)
    for i, pos_aa in enumerate(centroid):
        counts: dict[str, int] = {}
        for seq in seqs:
            if i < len(seq):
                aa = seq[i]
                counts[aa] = counts.get(aa, 0) + 1
        if counts:
            consensus[i] = max(counts, key=lambda x: counts[x])

    return {
        "mode": "multiple",
        "centroid": names[centroid_idx],
        "consensus": "".join(consensus),
        "num_sequences": len(seqs),
        "names": names,
    }


def _format_alignment(result: dict) -> str:
    """Format alignment result as text."""
    mode = result.get("mode", "")
    if mode == "pairwise":
        return (
            f"Identity: {result['identity']:.1%} ({result['matches']} matches)\n"
            f"Seq1 ({result['length_1']}aa): {result['aligned_1'][:60]}...\n"
            f"Seq2 ({result['length_2']}aa): {result['aligned_2'][:60]}..."
        )
    elif mode == "cdr":
        lines = [f"CDR3 identity matrix ({result['num_sequences']} sequences):"]
        names = result["names"]
        matrix = result["identity_matrix"]
        header = "     " + "  ".join(f"{n[:5]:>5}" for n in names)
        lines.append(header)
        for i, row in enumerate(matrix):
            line = f"{names[i][:5]:>5} " + "  ".join(f"{v:5.2f}" for v in row)
            lines.append(line)
        return "\n".join(lines)
    elif mode == "multiple":
        return (
            f"Centroid: {result.get('centroid', '?')}\n"
            f"Consensus: {result['consensus'][:60]}...\n"
            f"Sequences: {result['num_sequences']}"
        )
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Cross-validation  (replaces proteus_cli.screening.cross_validation)
# ---------------------------------------------------------------------------

@dataclass
class CrossValidationResult:
    name: str
    status: str  # "consensus", "divergent", "rejected"
    confidence: str
    iptm_delta: float
    ipsae_agreement: bool
    predictor_1_iptm: float
    predictor_2_iptm: float
    predictor_1_ipsae: float
    predictor_2_ipsae: float


def _cross_validate_designs(
    designs: list[dict],
    predictor_1_key: str = "boltzgen",
    predictor_2_key: str = "protenix",
) -> list[CrossValidationResult]:
    """Cross-validate designs using dual predictor scores."""
    results: list[CrossValidationResult] = []

    for d in designs:
        name = d.get("name", d.get("design_name", "?"))
        p1_iptm = d.get(f"{predictor_1_key}_iptm", 0.0)
        p2_iptm = d.get(f"{predictor_2_key}_iptm", 0.0)
        p1_ipsae = d.get(f"{predictor_1_key}_ipsae", 0.0)
        p2_ipsae = d.get(f"{predictor_2_key}_ipsae", 0.0)

        delta = abs(p1_iptm - p2_iptm)
        both_ipsae_ok = p1_ipsae > 0.3 and p2_ipsae > 0.3
        both_ipsae_bad = p1_ipsae < 0.1 and p2_ipsae < 0.1

        if delta > 0.5 or both_ipsae_bad:
            status = "rejected"
            confidence = "low"
        elif delta < 0.3 and both_ipsae_ok:
            status = "consensus"
            confidence = "high"
        else:
            status = "divergent"
            confidence = "medium"

        results.append(CrossValidationResult(
            name=name,
            status=status,
            confidence=confidence,
            iptm_delta=round(delta, 4),
            ipsae_agreement=both_ipsae_ok,
            predictor_1_iptm=p1_iptm,
            predictor_2_iptm=p2_iptm,
            predictor_1_ipsae=p1_ipsae,
            predictor_2_ipsae=p2_ipsae,
        ))

    return results


def _format_cross_validation(results: list[CrossValidationResult]) -> str:
    """Format cross-validation results as text."""
    lines = ["Name\tStatus\tConfidence\tipTM Delta\tipSAE Agreement"]
    for r in results:
        lines.append(f"{r.name}\t{r.status}\t{r.confidence}\t{r.iptm_delta:.3f}\t{r.ipsae_agreement}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shape complementarity  (replaces proteus_cli.screening.shape_complementarity)
# Simplified: requires BioPython if called, with graceful fallback
# ---------------------------------------------------------------------------

def _compute_interface_metrics(
    structure_path: str,
    design_chains: list[str],
    target_chains: list[str],
    contact_distance: float = 8.0,
) -> dict:
    """Compute interface contact metrics from a PDB/CIF file.

    Falls back gracefully if BioPython is not installed.
    """
    try:
        from Bio.PDB import PDBParser, MMCIFParser, NeighborSearch
    except ImportError:
        return {
            "error": (
                "BioPython not installed. Install with: pip install biopython. "
                "Shape complementarity scoring requires BioPython for structure parsing."
            )
        }

    p = Path(structure_path)
    if p.suffix.lower() in (".cif", ".mmcif"):
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)

    structure = parser.get_structure("s", str(p))
    model = structure[0]

    design_atoms = []
    target_atoms = []

    for chain in model:
        cid = chain.id
        for residue in chain:
            for atom in residue:
                if cid in design_chains:
                    design_atoms.append(atom)
                elif cid in target_chains:
                    target_atoms.append(atom)

    if not design_atoms or not target_atoms:
        return {"error": "No atoms found for specified chains"}

    ns = NeighborSearch(target_atoms)

    interface_design_residues: set = set()
    interface_target_residues: set = set()
    contact_count = 0

    for atom in design_atoms:
        neighbors = ns.search(atom.get_vector().get_array(), contact_distance, "A")
        if neighbors:
            contact_count += len(neighbors)
            res = atom.get_parent()
            interface_design_residues.add((res.get_parent().id, res.id[1]))
            for nb in neighbors:
                tres = nb.get_parent()
                interface_target_residues.add((tres.get_parent().id, tres.id[1]))

    total_if_res = len(interface_design_residues) + len(interface_target_residues)
    density = contact_count / total_if_res if total_if_res > 0 else 0.0

    return {
        "interface_contacts": contact_count,
        "interface_residues_design": len(interface_design_residues),
        "interface_residues_target": len(interface_target_residues),
        "total_interface_residues": total_if_res,
        "contact_density": round(density, 2),
        "design_chains": design_chains,
        "target_chains": target_chains,
    }


# ---------------------------------------------------------------------------
# Naturalness scoring  (replaces proteus_cli.screening.naturalness)
# Falls back gracefully when ablang2 is not available
# ---------------------------------------------------------------------------

def _score_naturalness(sequence: str, chain_type: str = "heavy") -> dict:
    """Score antibody naturalness using AbLang2 PLL."""
    try:
        import ablang2
    except ImportError:
        return {
            "naturalness_score": None,
            "chain_type": chain_type,
            "interpretation": "AbLang2 not installed — cannot compute naturalness score",
            "source": "unavailable",
            "install_hint": "pip install ablang2",
            "tamarind_alternative": (
                "Use Tamarind Bio cloud API for naturalness scoring: "
                "cloud_submit_job(tool='ablang2', ...)"
            ),
        }

    try:
        model = ablang2.pretrained(chain_type)
        pll = model.pseudo_log_likelihood(sequence)
        score = float(pll)

        if score > -2:
            interp = "Highly natural sequence"
        elif score > -3:
            interp = "Natural sequence"
        elif score > -5:
            interp = "Moderately natural"
        else:
            interp = "Low naturalness — may benefit from humanization"

        return {
            "naturalness_score": round(score, 4),
            "chain_type": chain_type,
            "interpretation": interp,
            "source": "ablang2_local",
        }
    except Exception as exc:
        return {
            "naturalness_score": None,
            "chain_type": chain_type,
            "interpretation": f"AbLang2 scoring failed: {exc}",
            "source": "error",
        }


# ===========================================================================
# MCP Tool definitions
# ===========================================================================


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


# ---------------------------------------------------------------------------
# Tool 1: screen_liabilities
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_liabilities(sequence: str) -> str:
    """Scan a protein sequence for PTM liabilities.

    Identifies deamidation hotspots (NG, NS, NT, NA), aspartate
    isomerization (DG, DS), methionine/tryptophan oxidation, free
    cysteines, and N-linked glycosylation motifs.

    Args:
        sequence: Amino acid sequence (one-letter codes, uppercase).

    Returns:
        JSON list of liabilities, each with type, position, motif,
        severity, and description.
    """
    if not sequence or not sequence.strip():
        return _error("Sequence must not be empty.")

    try:
        liabilities = _scan_liabilities(sequence.strip().upper())
        return json.dumps([asdict(l) for l in liabilities], indent=2)
    except Exception as exc:
        return _error(f"Liability scan failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 2: screen_developability
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_developability(
    sequence: str,
    cdr_regions: list[list[int]] | None = None,
) -> str:
    """TAP-inspired developability assessment for an antibody sequence.

    Evaluates hydrophobic content, proline/glycine fractions, net charge,
    CDR length, and PTM liability count. Returns an overall risk rating
    (low / medium / high) and any flags raised.

    Args:
        sequence: Amino acid sequence (one-letter codes, uppercase).
        cdr_regions: Optional list of [start, end] pairs defining CDR
            boundaries (0-indexed, exclusive end). Example:
            [[26, 38], [56, 65], [105, 117]].

    Returns:
        JSON object with overall_risk, hydrophobic_fraction,
        proline_fraction, glycine_fraction, liability_count, flags,
        total_cdr_length, and net_charge.
    """
    if not sequence or not sequence.strip():
        return _error("Sequence must not be empty.")

    try:
        cdr_tuples = None
        if cdr_regions is not None:
            cdr_tuples = [(r[0], r[1]) for r in cdr_regions]

        report = _assess_developability(
            sequence.strip().upper(),
            cdr_regions=cdr_tuples,
        )
        return json.dumps(asdict(report), indent=2)
    except Exception as exc:
        return _error(f"Developability assessment failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: screen_net_charge
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_net_charge(sequence: str, ph: float = 7.4) -> str:
    """Estimate the net charge of a protein sequence at a given pH.

    Uses Henderson-Hasselbalch equation with standard pKa values for
    ionizable amino acids, plus N-terminal and C-terminal contributions.

    Args:
        sequence: Amino acid sequence (one-letter codes, uppercase).
        ph: pH value for charge calculation (default 7.4).

    Returns:
        JSON object with net_charge (float) and ph (float).
    """
    if not sequence or not sequence.strip():
        return _error("Sequence must not be empty.")

    try:
        charge = _compute_net_charge(sequence.strip().upper(), ph=ph)
        return json.dumps({"net_charge": round(charge, 4), "ph": ph}, indent=2)
    except Exception as exc:
        return _error(f"Net charge calculation failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 4: score_ipsae
# ---------------------------------------------------------------------------


@mcp.tool()
async def score_ipsae(
    npz_path: str,
    design_chain_ids: list[int],
    target_chain_ids: list[int],
) -> str:
    """Compute ipSAE scores from a Protenix NPZ output file.

    Uses the standalone DunbrackLab ipSAE formula (no BoltzGen dependency).
    Calculates directional interface predicted Structural Alignment Error
    (ipSAE) scores: design-to-target, target-to-design, and the minimum
    of both. Higher scores indicate better predicted binding interfaces.

    Reference: Dunbrack et al., "Res ipSAE loquuntur" (2025)

    Args:
        npz_path: Path to Protenix output NPZ file with 'pae' key.
        design_chain_ids: List of asym_id integers for the design chains.
        target_chain_ids: List of asym_id integers for the target chains.

    Returns:
        JSON object with design_to_target_ipsae, target_to_design_ipsae,
        design_ipsae_min, and human-readable interpretation.
    """
    npz = Path(npz_path)
    if not npz.exists():
        return _error(f"NPZ file not found: {npz_path}")

    try:
        scores = _score_npz(npz, design_chain_ids, target_chain_ids)
        scores["interpretation"] = _interpret_ipsae(scores["design_ipsae_min"])
        return json.dumps(scores, indent=2)
    except Exception as exc:
        return _error(f"ipSAE scoring failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 5: score_ipsae_multi_seed
# ---------------------------------------------------------------------------


@mcp.tool()
async def score_ipsae_multi_seed(
    npz_paths: list[str] | None = None,
    npz_dir: str | None = None,
    design_chain_ids: list[int] | None = None,
    target_chain_ids: list[int] | None = None,
    design_chain: str = "A",
    target_chain: str = "B",
    pae_cutoff: float = 10.0,
    aggregation: str = "best",
) -> str:
    """Score ipSAE across multiple Protenix seed outputs and select the best seed.

    For the refolding workflow: BoltzGen top designs are refolded on Protenix
    with 20+ seeds, then ipSAE is computed from each seed's PAE and the best
    seed is selected.

    Provide EITHER ``npz_paths`` (explicit list of files) OR ``npz_dir``
    (directory to scan for *.npz and *confidence*.json files).

    Aggregation modes:
    - "best" (default): seed with highest ipsae_min
    - "mean": seed closest to mean ipsae_min
    - "median": seed closest to median ipsae_min

    Args:
        npz_paths: List of paths to Protenix NPZ or confidence JSON files.
        npz_dir: Directory containing seed output files (alternative to npz_paths).
        design_chain_ids: asym_id integers for design chains (NPZ format).
        target_chain_ids: asym_id integers for target chains (NPZ format).
        design_chain: Chain letter for design (JSON format, default "A").
        target_chain: Chain letter for target (JSON format, default "B").
        pae_cutoff: PAE threshold (default 10.0 for Protenix/AF3).
        aggregation: Seed selection strategy — "best", "mean", or "median".

    Returns:
        JSON object with best_seed_idx, best_ipsae_min, per-seed scores,
        mean/std statistics, and interpretation.
    """
    if not npz_paths and not npz_dir:
        return _error("Provide either npz_paths (list) or npz_dir (directory).")

    try:
        if npz_dir:
            result = _score_multi_seed_dir(
                npz_dir, design_chain_ids, target_chain_ids,
                design_chain, target_chain, pae_cutoff, aggregation,
            )
        else:
            result = _score_multi_seed(
                npz_paths, design_chain_ids, target_chain_ids,
                design_chain, target_chain, pae_cutoff, aggregation,
            )

        if "error" not in result:
            result["interpretation"] = _interpret_ipsae(result["best_ipsae_min"])

        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Multi-seed ipSAE scoring failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 6: screen_composite
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_composite(
    sequence: str,
    iptm: float | None = None,
    ipsae: float | None = None,
    plddt: float | None = None,
    rmsd: float | None = None,
) -> str:
    """Run the full BY screening battery on a design.

    Combines liability scanning, developability assessment, and
    interpretation of any supplied structure/binding scores. Returns a
    binary pass/fail verdict based on hard threshold screening (not a
    weighted composite score).

    Pass/fail thresholds:
        - ipTM > 0.5
        - pLDDT > 70
        - RMSD < 3.5 A
        - ipsae: interpreted by ipSAE scale
        - Developability: overall_risk != "high"

    Args:
        sequence: Amino acid sequence (one-letter codes, uppercase).
        iptm: Interface predicted TM-score (optional).
        ipsae: ipSAE min score (optional).
        plddt: Predicted LDDT (optional).
        rmsd: RMSD in Angstroms (optional).

    Returns:
        JSON object with pass (bool), composite_score (float or null),
        liabilities, developability, scores, interpretation, and flags.
        composite_score uses the formula: 0.50*ipSAE_min + 0.30*ipTM + 0.20*(1-normalized_liability_count).
        Returns null if ipTM or ipSAE not provided.
    """
    if not sequence or not sequence.strip():
        return _error("Sequence must not be empty.")

    try:
        seq = sequence.strip().upper()

        # Liability scan
        liabilities = _scan_liabilities(seq)
        liabilities_json = [asdict(l) for l in liabilities]

        # Developability
        report = _assess_developability(seq, liabilities=liabilities)
        dev_json = asdict(report)

        # Score interpretation
        scores: dict = {}
        interpretation: dict = {}
        flags: list[str] = []

        if iptm is not None:
            scores["iptm"] = iptm
            if iptm > 0.8:
                interpretation["iptm"] = "Excellent structural confidence"
            elif iptm > 0.5:
                interpretation["iptm"] = "Good structural confidence"
            elif iptm > 0.3:
                interpretation["iptm"] = "Moderate — may need refinement"
            else:
                interpretation["iptm"] = "Poor — consider redesign"
            if iptm <= 0.5:
                flags.append(f"ipTM below threshold: {iptm:.3f} <= 0.5")

        if plddt is not None:
            scores["plddt"] = plddt
            if plddt > 90:
                interpretation["plddt"] = "Very high confidence"
            elif plddt > 70:
                interpretation["plddt"] = "Confident prediction"
            elif plddt > 50:
                interpretation["plddt"] = "Low confidence — likely disordered"
            else:
                interpretation["plddt"] = "Very low confidence"
            if plddt <= 70:
                flags.append(f"pLDDT below threshold: {plddt:.1f} <= 70")

        if rmsd is not None:
            scores["rmsd"] = rmsd
            if rmsd < 1.0:
                interpretation["rmsd"] = "Excellent structural agreement"
            elif rmsd < 2.0:
                interpretation["rmsd"] = "Good structural agreement"
            elif rmsd < 3.5:
                interpretation["rmsd"] = "Acceptable structural agreement"
            else:
                interpretation["rmsd"] = "Poor structural agreement"
            if rmsd >= 3.5:
                flags.append(f"RMSD above threshold: {rmsd:.2f} >= 3.5 A")

        if ipsae is not None:
            scores["ipsae"] = ipsae
            interpretation["ipsae"] = _interpret_ipsae(ipsae)

        # Composite pass/fail
        passes = True
        if iptm is not None and iptm <= 0.5:
            passes = False
        if plddt is not None and plddt <= 70:
            passes = False
        if rmsd is not None and rmsd >= 3.5:
            passes = False
        if report.overall_risk == "high":
            passes = False
            flags.append("Developability risk is HIGH")

        # Composite ranking score (CLAUDE.md authoritative formula)
        # composite = 0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)
        composite_score = None
        if iptm is not None and ipsae is not None:
            max_liabilities = 10  # normalization cap
            liability_count = len(liabilities)
            normalized_liability = min(liability_count / max_liabilities, 1.0)
            composite_score = (
                0.50 * ipsae
                + 0.30 * iptm
                + 0.20 * (1.0 - normalized_liability)
            )
            composite_score = round(composite_score, 4)

        return json.dumps(
            {
                "pass": passes,
                "composite_score": composite_score,
                "liabilities": liabilities_json,
                "developability": dev_json,
                "scores": scores,
                "interpretation": interpretation,
                "flags": flags,
            },
            indent=2,
        )
    except Exception as exc:
        return _error(f"Composite screening failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 7: interpret_scores
# ---------------------------------------------------------------------------


@mcp.tool()
async def interpret_scores(
    iptm: float | None = None,
    ipsae: float | None = None,
    plddt: float | None = None,
) -> str:
    """Provide human-readable interpretation of structure/binding scores.

    Interprets any combination of ipTM, ipSAE, and pLDDT scores
    using the BY scoring scales.

    Args:
        iptm: Interface predicted TM-score (optional).
        ipsae: ipSAE min score (optional).
        plddt: Predicted LDDT (optional).

    Returns:
        JSON object with per-metric interpretation and a summary.
    """
    if all(v is None for v in (iptm, ipsae, plddt)):
        return _error("At least one score must be provided.")

    try:
        result: dict = {}

        if iptm is not None:
            if iptm > 0.8:
                label = "Excellent structural confidence"
            elif iptm > 0.5:
                label = "Good structural confidence"
            elif iptm > 0.3:
                label = "Moderate — may need refinement"
            else:
                label = "Poor — consider redesign"
            result["iptm"] = {"value": iptm, "interpretation": label}

        if ipsae is not None:
            result["ipsae"] = {
                "value": ipsae,
                "interpretation": _interpret_ipsae(ipsae),
            }

        if plddt is not None:
            if plddt > 90:
                label = "Very high confidence"
            elif plddt > 70:
                label = "Confident prediction"
            elif plddt > 50:
                label = "Low confidence — likely disordered"
            else:
                label = "Very low confidence"
            result["plddt"] = {"value": plddt, "interpretation": label}

        # Build a one-line summary
        summaries = []
        for key in ("iptm", "ipsae", "plddt"):
            if key in result:
                summaries.append(f"{key}={result[key]['value']:.3f}")
        result["summary"] = ", ".join(summaries)

        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Score interpretation failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 8: screen_diversity
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_diversity(
    sequences_json: str,
    identity_threshold: float = 0.9,
) -> str:
    """Analyze sequence diversity of a candidate set.

    Clusters sequences by pairwise identity and reports diversity metrics
    including cluster count, diversity ratio, average pairwise identity,
    and a redundancy warning if the set is too homogeneous.

    Args:
        sequences_json: JSON array of objects, each with at least a
            "sequence" key containing the amino acid string. May also
            include "name" or other metadata fields.
        identity_threshold: Clustering threshold (0.0-1.0). Sequences
            with identity >= this value are placed in the same cluster.
            Default 0.9 (90% identity).

    Returns:
        JSON object with num_sequences, num_clusters, diversity_ratio,
        avg_pairwise_identity, largest_cluster_size, singleton_clusters,
        redundancy_warning, and a formatted text report.
    """
    try:
        sequences = json.loads(sequences_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid sequences JSON: {exc}")

    if not isinstance(sequences, list):
        return _error("sequences_json must be a JSON array.")

    for i, seq in enumerate(sequences):
        if not isinstance(seq, dict) or "sequence" not in seq:
            return _error(
                f"Entry {i} must be an object with a 'sequence' key."
            )

    try:
        report = _diversity_report(sequences, identity_threshold=identity_threshold)
        report["threshold"] = int(identity_threshold * 100)
        report["formatted"] = _format_diversity(report)
        return json.dumps(report, indent=2)
    except Exception as exc:
        return _error(f"Diversity analysis failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 9: screen_diagnose_failures
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_diagnose_failures(
    scores_json: str,
    pass_key: str = "status",
    pass_value: str = "PASS",
) -> str:
    """Diagnose why a design campaign has a low hit rate.

    Performs Mann-Whitney U tests comparing passed vs failed designs
    across continuous features (ipSAE, ipTM, pLDDT, RMSD, liabilities,
    etc.) to identify which metrics most strongly discriminate between
    successful and unsuccessful designs.

    Trigger this tool when pass rate drops below ~20%.

    Args:
        scores_json: JSON array of design score dicts. Each dict should
            include a status field (configurable via pass_key) and numeric
            feature columns such as ipsae, iptm, plddt, rmsd, liabilities,
            net_charge, hydrophobic_fraction, cdr3_length.
        pass_key: Key in each dict indicating pass/fail status
            (default "status").
        pass_value: Value of pass_key that means the design passed
            (default "PASS").

    Returns:
        JSON object with total_designs, passed, failed, pass_rate,
        discriminating_features (sorted by p-value), summary, and
        actionable recommendations.
    """
    try:
        designs = json.loads(scores_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid scores JSON: {exc}")

    if not isinstance(designs, list):
        return _error("scores_json must be a JSON array.")

    try:
        diag = _diagnose_failures(
            designs, pass_key=pass_key, pass_value=pass_value
        )
        result = {
            "total_designs": diag.total_designs,
            "passed": diag.passed,
            "failed": diag.failed,
            "pass_rate": round(diag.pass_rate, 4),
            "discriminating_features": [
                {
                    "feature_name": a.feature_name,
                    "test_type": a.test_type,
                    "statistic": a.statistic,
                    "p_value": a.p_value,
                    "effect_size": a.effect_size,
                    "passed_mean": a.passed_mean,
                    "failed_mean": a.failed_mean,
                    "interpretation": a.interpretation,
                }
                for a in diag.discriminating_features
            ],
            "summary": diag.summary,
            "recommendations": diag.recommendations,
            "formatted": _format_diagnosis(diag),
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Failure diagnosis failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 10: screen_pareto_front
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_pareto_front(
    designs_json: str,
    objectives_json: str | None = None,
) -> str:
    """Extract Pareto-optimal designs from a candidate set.

    Instead of a single composite ranking, identifies non-dominated
    candidates that represent optimal trade-offs across multiple
    objectives (e.g., maximize binding affinity while minimizing
    liabilities).

    Default objectives: maximize ipsae_min, maximize iptm, minimize
    liabilities count.

    Args:
        designs_json: JSON array of design objects, each with metric
            fields (e.g., ipsae_min, iptm, liabilities). Must also
            include a "design_name" or "name" key for labeling.
        objectives_json: Optional JSON array of [metric, direction]
            pairs. Direction is "maximize" or "minimize". Example:
            [["ipsae_min", "maximize"], ["iptm", "maximize"],
             ["liabilities", "minimize"]].

    Returns:
        JSON object with pareto_front (list of non-dominated designs
        annotated with pareto_rank and tradeoff), front_size, total,
        and a formatted text table.
    """
    try:
        designs = json.loads(designs_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid designs JSON: {exc}")

    if not isinstance(designs, list):
        return _error("designs_json must be a JSON array.")

    objectives = None
    if objectives_json is not None:
        try:
            raw = json.loads(objectives_json)
            objectives = [(o[0], o[1]) for o in raw]
        except (json.JSONDecodeError, IndexError, TypeError) as exc:
            return _error(f"Invalid objectives JSON: {exc}")

    try:
        front = _pareto_front(designs, objectives=objectives)
        formatted = _format_pareto(front, objectives=objectives)
        return json.dumps(
            {
                "pareto_front": front,
                "front_size": len(front),
                "total": len(designs),
                "formatted": formatted,
            },
            indent=2,
        )
    except Exception as exc:
        return _error(f"Pareto front extraction failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 11: screen_align_sequences
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_align_sequences(
    sequences_json: str,
    mode: str = "pairwise",
    key: str = "sequence",
    cdr_key: str = "cdr3_sequence",
) -> str:
    """Align protein sequences for candidate comparison.

    Supports three alignment modes:

    - **pairwise**: Align exactly two sequences and report score, identity,
      and aligned strings.
    - **cdr**: Extract CDR3 from each design and compute a pairwise
      identity matrix across the set.
    - **multiple**: Star alignment from centroid — returns consensus
      sequence and MSA.

    Args:
        sequences_json: JSON array of objects. Each object must have a
            sequence field (configurable via *key*). For ``cdr`` mode,
            each object needs a CDR3 field (configurable via *cdr_key*).
            May also include "name" or "design_name" for labeling.
        mode: Alignment mode — "pairwise" (exactly 2 sequences),
            "cdr" (CDR3 identity matrix), or "multiple" (star MSA).
            Default "pairwise".
        key: Dict key for the full amino acid sequence (default "sequence").
        cdr_key: Dict key for CDR3 sequence, used in "cdr" mode
            (default "cdr3_sequence").

    Returns:
        JSON object with alignment results and a ``formatted`` text
        representation.
    """
    try:
        sequences = json.loads(sequences_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid sequences JSON: {exc}")

    if not isinstance(sequences, list):
        return _error("sequences_json must be a JSON array.")

    valid_modes = ("pairwise", "cdr", "multiple")
    if mode not in valid_modes:
        return _error(f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}")

    try:
        if mode == "pairwise":
            if len(sequences) != 2:
                return _error(
                    f"Pairwise mode requires exactly 2 sequences, got {len(sequences)}."
                )
            result = _pairwise_align(
                sequences[0].get(key, ""),
                sequences[1].get(key, ""),
            )
        elif mode == "cdr":
            result = _cdr_align(sequences, cdr_key=cdr_key)
        else:
            result = _multiple_align(sequences, key=key)

        result["formatted"] = _format_alignment(result)
        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Sequence alignment failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 12: screen_cross_validate
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_cross_validate(
    designs_json: str,
    predictor_1: str = "boltzgen",
    predictor_2: str = "protenix",
) -> str:
    """Cross-validate designs using dual structure predictor scores.

    Compares binding predictions from two independent predictors (e.g.,
    BoltzGen and Protenix) to identify consensus high-confidence candidates
    and reject designs where predictors strongly disagree.

    Classification:
    - CONSENSUS (high confidence): ipTM delta < 0.3, both ipSAE > 0.3
    - DIVERGENT (medium confidence): one metric fails threshold
    - REJECTED (low confidence): ipTM delta > 0.5 or both ipSAE < 0.1

    Args:
        designs_json: JSON array of design objects. Each must have scores
            from both predictors, keyed as e.g. "boltzgen_iptm",
            "protenix_iptm", "boltzgen_ipsae", "protenix_ipsae". Also
            include "name" or "design_name" for labeling.
        predictor_1: Key prefix for the first predictor (default "boltzgen").
        predictor_2: Key prefix for the second predictor (default "protenix").

    Returns:
        JSON object with per-design results (status, confidence, ipTM delta,
        ipSAE agreement), summary counts, and a formatted text report.
    """
    try:
        designs = json.loads(designs_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid designs JSON: {exc}")

    if not isinstance(designs, list):
        return _error("designs_json must be a JSON array.")

    try:
        results = _cross_validate_designs(
            designs,
            predictor_1_key=predictor_1,
            predictor_2_key=predictor_2,
        )
        results_json = [asdict(r) for r in results]
        formatted = _format_cross_validation(results)

        consensus = sum(1 for r in results if r.status == "consensus")
        divergent = sum(1 for r in results if r.status == "divergent")
        rejected = sum(1 for r in results if r.status == "rejected")

        return json.dumps(
            {
                "results": results_json,
                "summary": {
                    "total": len(results),
                    "consensus": consensus,
                    "divergent": divergent,
                    "rejected": rejected,
                },
                "formatted": formatted,
            },
            indent=2,
        )
    except Exception as exc:
        return _error(f"Cross-validation failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 13: screen_shape_complementarity
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_shape_complementarity(
    structure_path: str,
    design_chains: list[str] | None = None,
    target_chains: list[str] | None = None,
    contact_distance: float = 8.0,
) -> str:
    """Compute interface shape complementarity metrics from a PDB/CIF structure.

    Uses BioPython NeighborSearch to detect atom-level contacts between
    design and target chains, then reports interface contact count,
    per-side interface residue counts, and contact density (contacts per
    interface residue).

    Useful for evaluating how well a designed binder packs against its
    target — higher contact density indicates tighter shape complementarity.

    Args:
        structure_path: Path to a PDB or mmCIF structure file.
        design_chains: Chain IDs for the designed binder (default ["A"]).
        target_chains: Chain IDs for the target protein (default ["B"]).
        contact_distance: Distance cutoff in Angstroms for contact
            detection (default 8.0).

    Returns:
        JSON object with interface_contacts, interface_residues_design,
        interface_residues_target, total_interface_residues,
        contact_density, design_chains, and target_chains.
    """
    if design_chains is None:
        design_chains = ["A"]
    if target_chains is None:
        target_chains = ["B"]

    p = Path(structure_path)
    if not p.exists():
        return _error(f"Structure file not found: {structure_path}")

    try:
        result = _compute_interface_metrics(
            structure_path=str(p),
            design_chains=design_chains,
            target_chains=target_chains,
            contact_distance=contact_distance,
        )
        if "error" in result:
            return _error(result["error"])
        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Shape complementarity scoring failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 14: screen_naturalness
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_naturalness(
    sequence: str,
    chain_type: str = "heavy",
) -> str:
    """Score antibody sequence naturalness using AbLang2.

    Uses AbLang2 pseudo log-likelihood (PLL) scoring to assess how
    "natural" an antibody sequence looks compared to the observed
    human antibody repertoire. Higher (less negative) PLL scores
    indicate more natural sequences.

    Falls back gracefully if ablang2 is not installed, suggesting the
    Tamarind Bio cloud alternative.

    Typical PLL ranges:
    - Natural antibodies: -1 to -3
    - Random / unnatural sequences: -5 to -8

    Args:
        sequence: Amino acid sequence (VH, VHH, or VL, one-letter codes).
        chain_type: "heavy" (default, for VH/VHH) or "light" (for VL).

    Returns:
        JSON object with naturalness_score, chain_type, interpretation,
        source, and install_hint / tamarind_alternative if ablang2 is
        not available.
    """
    if not sequence or not sequence.strip():
        return _error("Sequence must not be empty.")

    if chain_type not in ("heavy", "light"):
        return _error(
            f"Invalid chain_type '{chain_type}'. Must be 'heavy' or 'light'."
        )

    try:
        result = _score_naturalness(sequence.strip().upper(), chain_type=chain_type)
        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Naturalness scoring failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
