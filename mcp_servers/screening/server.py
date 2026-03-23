"""Screening MCP Server — protein sequence screening and scoring tools for Proteus agent.

Wraps the Phase 1 screening (liabilities, developability) and scoring (ipSAE)
modules into MCP tools for the Proteus harness.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure the project src directory is on sys.path for proteus_cli imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("proteus-screening")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        from proteus_cli.screening.liabilities import scan_liabilities as _scan

        liabilities = _scan(sequence.strip().upper())
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
        from proteus_cli.screening.developability import assess_developability

        # Convert list-of-lists to list-of-tuples as expected by the module.
        cdr_tuples = None
        if cdr_regions is not None:
            cdr_tuples = [(r[0], r[1]) for r in cdr_regions]

        report = assess_developability(
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
        from proteus_cli.screening.liabilities import compute_net_charge

        charge = compute_net_charge(sequence.strip().upper(), ph=ph)
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
        from proteus_cli.scoring.ipsae import score_npz, interpret_ipsae

        scores = score_npz(npz, design_chain_ids, target_chain_ids)
        scores["interpretation"] = interpret_ipsae(scores["design_ipsae_min"])
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
        from proteus_cli.scoring.ipsae import (
            score_multi_seed,
            score_multi_seed_dir,
            interpret_ipsae,
        )

        if npz_dir:
            result = score_multi_seed_dir(
                npz_dir, design_chain_ids, target_chain_ids,
                design_chain, target_chain, pae_cutoff, aggregation,
            )
        else:
            result = score_multi_seed(
                npz_paths, design_chain_ids, target_chain_ids,
                design_chain, target_chain, pae_cutoff, aggregation,
            )

        if "error" not in result:
            result["interpretation"] = interpret_ipsae(result["best_ipsae_min"])

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
    """Run the full Proteus screening battery on a design.

    Combines liability scanning, developability assessment, and
    interpretation of any supplied structure/binding scores. Returns a
    composite pass/fail verdict based on the screening battery thresholds.

    Composite score: 0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)

    Thresholds:
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
        JSON object with pass (bool), liabilities, developability,
        scores, interpretation, and flags.
    """
    if not sequence or not sequence.strip():
        return _error("Sequence must not be empty.")

    try:
        from proteus_cli.screening.liabilities import scan_liabilities as _scan
        from proteus_cli.screening.developability import assess_developability
        from proteus_cli.scoring.ipsae import interpret_ipsae

        seq = sequence.strip().upper()

        # Liability scan
        liabilities = _scan(seq)
        liabilities_json = [asdict(l) for l in liabilities]

        # Developability
        report = assess_developability(seq, liabilities=liabilities)
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
            interpretation["ipsae"] = interpret_ipsae(ipsae)

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

        return json.dumps(
            {
                "pass": passes,
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
    using the Proteus scoring scales.

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
        from proteus_cli.scoring.ipsae import interpret_ipsae

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
                "interpretation": interpret_ipsae(ipsae),
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
        from proteus_cli.screening.diversity import (
            diversity_report,
            format_diversity,
        )

        report = diversity_report(sequences, identity_threshold=identity_threshold)
        report["threshold"] = int(identity_threshold * 100)
        report["formatted"] = format_diversity(report)
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
        from proteus_cli.screening.diagnosis import (
            diagnose_failures,
            format_diagnosis,
        )

        diag = diagnose_failures(
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
            "formatted": format_diagnosis(diag),
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
        from proteus_cli.screening.pareto import pareto_front, format_pareto

        front = pareto_front(designs, objectives=objectives)
        formatted = format_pareto(front, objectives=objectives)
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

    Uses BioPython PairwiseAligner (global mode) under the hood.

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
        from proteus_cli.screening.alignment import (
            pairwise_align,
            cdr_align,
            multiple_align,
            format_alignment,
        )

        if mode == "pairwise":
            if len(sequences) != 2:
                return _error(
                    f"Pairwise mode requires exactly 2 sequences, got {len(sequences)}."
                )
            result = pairwise_align(
                sequences[0].get(key, ""),
                sequences[1].get(key, ""),
            )
        elif mode == "cdr":
            result = cdr_align(sequences, cdr_key=cdr_key)
        else:
            result = multiple_align(sequences, key=key)

        result["formatted"] = format_alignment(result)
        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Sequence alignment failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 12: screen_shape_complementarity
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
        from proteus_cli.screening.shape_complementarity import (
            compute_interface_metrics,
        )

        result = compute_interface_metrics(
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
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
