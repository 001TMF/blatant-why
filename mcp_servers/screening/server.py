"""Screening MCP Server — protein sequence screening and scoring tools for Proteus agent.

Wraps the Phase 1 screening (liabilities, developability) and scoring (ipSAE, p_bind)
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

    Calculates directional interface predicted Structural Alignment Error
    (ipSAE) scores: design-to-target, target-to-design, and the minimum
    of both. Higher scores indicate better predicted binding interfaces.

    Requires BoltzGen to be installed.

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
    except ImportError as exc:
        return _error(
            f"BoltzGen is required for ipSAE scoring but could not be imported: {exc}. "
            "Install from https://github.com/HannesStark/boltzgen"
        )
    except Exception as exc:
        return _error(f"ipSAE scoring failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 5: score_pbind
# ---------------------------------------------------------------------------


@mcp.tool()
async def score_pbind(
    checkpoint_path: str,
    v_ab_path: str,
    v_ag_path: str,
    v_if_path: str,
) -> str:
    """Run p_bind inference to predict binding probability.

    Loads pre-extracted Protenix trunk features (v_ab, v_ag, v_if) from
    NPY files and runs them through a trained PBindHead model to predict
    binding probability.

    Args:
        checkpoint_path: Path to a trained p_bind model checkpoint.
        v_ab_path: Path to NPY file with antibody representation [1, 384].
        v_ag_path: Path to NPY file with antigen representation [1, 384].
        v_if_path: Path to NPY file with interface representation [1, 256].

    Returns:
        JSON object with binding_probability, interpretation, and
        feature paths used.
    """
    ckpt = Path(checkpoint_path)
    if not ckpt.exists():
        return _error(
            f"p_bind checkpoint not found at: {checkpoint_path}. "
            "The model may not be trained yet. Run p_bind training first, "
            "then provide the checkpoint path."
        )

    for label, fpath in [("v_ab", v_ab_path), ("v_ag", v_ag_path), ("v_if", v_if_path)]:
        if not Path(fpath).exists():
            return _error(f"Feature file not found for {label}: {fpath}")

    try:
        import numpy as np
        import torch

        from proteus_cli.scoring.pbind import load_pbind_model, predict_binding, interpret_pbind

        model = load_pbind_model(ckpt)

        v_ab = torch.from_numpy(np.load(v_ab_path)).float()
        v_ag = torch.from_numpy(np.load(v_ag_path)).float()
        v_if = torch.from_numpy(np.load(v_if_path)).float()

        prob = predict_binding(model, v_ab, v_ag, v_if)

        return json.dumps(
            {
                "binding_probability": round(prob, 6),
                "interpretation": interpret_pbind(prob),
                "checkpoint": checkpoint_path,
                "features": {
                    "v_ab": v_ab_path,
                    "v_ag": v_ag_path,
                    "v_if": v_if_path,
                },
            },
            indent=2,
        )
    except ImportError as exc:
        return _error(
            f"Required dependency not available for p_bind inference: {exc}. "
            "Ensure BoltzGen and PyTorch are installed."
        )
    except Exception as exc:
        return _error(f"p_bind inference failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 6: screen_composite
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_composite(
    sequence: str,
    iptm: float | None = None,
    ipsae: float | None = None,
    pbind: float | None = None,
    plddt: float | None = None,
    rmsd: float | None = None,
) -> str:
    """Run the full Proteus screening battery on a design.

    Combines liability scanning, developability assessment, and
    interpretation of any supplied structure/binding scores. Returns a
    composite pass/fail verdict based on the screening battery thresholds.

    Thresholds:
        - ipTM > 0.5
        - pLDDT > 70
        - RMSD < 3.5 A
        - ipsae: interpreted by ipSAE scale
        - pbind: interpreted by p_bind scale
        - Developability: overall_risk != "high"

    Args:
        sequence: Amino acid sequence (one-letter codes, uppercase).
        iptm: Interface predicted TM-score (optional).
        ipsae: ipSAE min score (optional).
        pbind: Binding probability from p_bind (optional).
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
        from proteus_cli.scoring.pbind import interpret_pbind

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

        if pbind is not None:
            scores["pbind"] = pbind
            interpretation["pbind"] = interpret_pbind(pbind)

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
    pbind: float | None = None,
    plddt: float | None = None,
) -> str:
    """Provide human-readable interpretation of structure/binding scores.

    Interprets any combination of ipTM, ipSAE, p_bind, and pLDDT scores
    using the Proteus scoring scales.

    Args:
        iptm: Interface predicted TM-score (optional).
        ipsae: ipSAE min score (optional).
        pbind: Binding probability from p_bind (optional).
        plddt: Predicted LDDT (optional).

    Returns:
        JSON object with per-metric interpretation and a summary.
    """
    if all(v is None for v in (iptm, ipsae, pbind, plddt)):
        return _error("At least one score must be provided.")

    try:
        from proteus_cli.scoring.ipsae import interpret_ipsae
        from proteus_cli.scoring.pbind import interpret_pbind

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

        if pbind is not None:
            result["pbind"] = {
                "value": pbind,
                "interpretation": interpret_pbind(pbind),
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
        for key in ("iptm", "ipsae", "pbind", "plddt"):
            if key in result:
                summaries.append(f"{key}={result[key]['value']:.3f}")
        result["summary"] = ", ".join(summaries)

        return json.dumps(result, indent=2)
    except Exception as exc:
        return _error(f"Score interpretation failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
