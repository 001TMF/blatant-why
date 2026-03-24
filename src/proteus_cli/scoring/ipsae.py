"""Open-source ipSAE scoring from Protenix/AF3 PAE output.

Reference: Dunbrack et al., "Res ipSAE loquuntur" (2025)
Implementation: https://github.com/DunbrackLab/IPSAE
Provides both the raw scoring function and a high-level API that works
with Protenix NPZ output files directly.

Compatibility note (2026-03-23):
  BoltzGen (github.com/HannesStark/boltzgen) has merged PRs adding ipSAE
  ranking into its pipeline (see closed PRs mentioning "ipSAE ranking").
  If using BoltzGen >= v0.3 with --rank-by ipsae, the pipeline computes
  ipSAE natively during the filter stage and writes scores to the output CSV.
  This standalone module remains useful for:
    - Scoring Protenix/AF3 predictions outside the BoltzGen pipeline
    - Re-scoring with different PAE cutoffs (AF2=15.0 vs AF3/Protenix=10.0)
    - Batch scoring NPZ files from arbitrary sources
    - Verifying BoltzGen's built-in scores against our reference implementation
"""
from __future__ import annotations

# Key naming conventions:
# - compute_ipsae() returns "ipsae_min" (chain-letter API, used with JSON confidence files)
# - score_npz() returns "design_ipsae_min" (asym_id API, used with NPZ files)
# - score_multi_seed() handles both via _get_ipsae_min() helper

import json
from pathlib import Path
from typing import Any

import numpy as np


def compute_ipsae(
    pae_matrix: np.ndarray,
    chain_ids: np.ndarray,
    design_chain: str,
    target_chain: str,
    pae_cutoff: float = 10.0,  # 10 for AF3/Protenix, 15 for AF2
) -> dict:
    """Compute ipSAE from PAE matrix.

    Args:
        pae_matrix: [N, N] predicted aligned error matrix
        chain_ids: [N] chain ID for each residue
        design_chain: chain ID of the designed binder
        target_chain: chain ID of the target protein
        pae_cutoff: PAE threshold (10.0 for Protenix/AF3)

    Returns:
        dict with design_to_target_ipsae, target_to_design_ipsae, ipsae_min
    """
    design_mask = chain_ids == design_chain
    target_mask = chain_ids == target_chain

    # Design -> Target: how well does the design predict target positions?
    dt_ipsae = _directional_ipsae(pae_matrix, design_mask, target_mask, pae_cutoff)

    # Target -> Design: how well does the target predict design positions?
    td_ipsae = _directional_ipsae(pae_matrix, target_mask, design_mask, pae_cutoff)

    return {
        "design_to_target_ipsae": round(dt_ipsae, 4),
        "target_to_design_ipsae": round(td_ipsae, 4),
        "ipsae_min": round(min(dt_ipsae, td_ipsae), 4),
    }


def _directional_ipsae(
    pae: np.ndarray,
    from_mask: np.ndarray,
    to_mask: np.ndarray,
    pae_cutoff: float,
) -> float:
    """Compute directional ipSAE (from -> to)."""
    # Extract interchain PAE block
    interchain_pae = pae[np.ix_(from_mask, to_mask)]

    # Count residues in 'to' chain with at least one good PAE from 'from' chain
    min_pae_per_to_residue = interchain_pae.min(axis=0)
    n0 = int(np.sum(min_pae_per_to_residue < pae_cutoff))

    if n0 == 0:
        return 0.0

    # TM-score d0 formula (Zhang & Skolnick 2004)
    n0_clamped = max(n0, 19)
    d0 = 1.24 * (n0_clamped - 15) ** (1.0 / 3.0) - 1.8
    d0 = max(d0, 0.5)  # prevent division issues

    # Score each pair using TM-score kernel
    scores = 1.0 / (1.0 + (min_pae_per_to_residue / d0) ** 2)

    # Average over residues that passed the cutoff
    good_mask = min_pae_per_to_residue < pae_cutoff
    if good_mask.sum() == 0:
        return 0.0

    return float(scores[good_mask].mean())


def score_from_protenix_output(
    confidence_json_path: str,
    design_chain: str = "A",
    target_chain: str = "B",
) -> dict:
    """Compute ipSAE from Protenix confidence output.

    Args:
        confidence_json_path: path to Protenix confidence JSON file
        design_chain: chain letter for the designed binder
        target_chain: chain letter for the target

    Returns:
        dict with ipsae scores + protenix confidence metrics
    """
    with open(confidence_json_path) as f:
        confidence = json.load(f)

    # Extract PAE matrix and chain info
    pae_matrix = np.array(confidence.get("pae", confidence.get("predicted_aligned_error", [])))

    if pae_matrix.size == 0:
        return {"error": "No PAE matrix found in confidence file"}

    # Build chain_ids from token_chain_ids or chain info
    chain_ids = np.array(confidence.get("token_chain_ids", []))

    if chain_ids.size == 0:
        return {"error": "No chain ID information found"}

    # Compute ipSAE
    ipsae = compute_ipsae(pae_matrix, chain_ids, design_chain, target_chain)

    # Add standard Protenix metrics
    ipsae["iptm"] = confidence.get("iptm", 0.0)
    ipsae["ptm"] = confidence.get("ptm", 0.0)
    ipsae["plddt_mean"] = float(np.mean(confidence.get("plddt", [0.0]))) if "plddt" in confidence else 0.0

    return ipsae


def score_npz(
    npz_path: Path,
    design_chain_ids: list[int],
    target_chain_ids: list[int],
    pae_cutoff: float = 10.0,
) -> dict[str, float]:
    """Score a Protenix output NPZ file for ipSAE metrics.

    Standalone implementation using the DunbrackLab formula.
    No BoltzGen dependency required.

    Args:
        npz_path: Path to NPZ with 'pae' key [N_sample, N_token, N_token]
        design_chain_ids: asym_id integers for design chains
        target_chain_ids: asym_id integers for target chains
        pae_cutoff: PAE threshold (10.0 for Protenix/AF3, 15.0 for AF2)

    Returns:
        Dict with best-sample ipSAE metrics.
    """
    data = np.load(npz_path, allow_pickle=True)
    pae = data["pae"].astype(np.float32)  # [N_sample, N_token, N_token]

    # Build masks from asym_id if available
    if "token_asym_id" in data:
        asym_id = data["token_asym_id"]
    else:
        n_tokens = pae.shape[1]
        asym_id = np.zeros(n_tokens, dtype=np.int64)

    design_mask = np.isin(asym_id, design_chain_ids)
    target_mask = np.isin(asym_id, target_chain_ids)

    best_dt = -1.0
    best_td = -1.0
    best_min = -1.0

    for i in range(pae.shape[0]):
        pae_i = pae[i]
        interchain_dt = pae_i[np.ix_(design_mask, target_mask)]
        interchain_td = pae_i[np.ix_(target_mask, design_mask)]

        dt = _score_block(interchain_dt, pae_cutoff)
        td = _score_block(interchain_td, pae_cutoff)
        mn = min(dt, td)

        if mn > best_min:
            best_dt, best_td, best_min = dt, td, mn

    return {
        "design_to_target_ipsae": round(best_dt, 4),
        "target_to_design_ipsae": round(best_td, 4),
        "design_ipsae_min": round(best_min, 4),
    }


def _score_block(interchain_pae: np.ndarray, pae_cutoff: float) -> float:
    """Score a single interchain PAE block [from_residues, to_residues]."""
    if interchain_pae.size == 0:
        return 0.0

    min_pae_per_to = interchain_pae.min(axis=0)
    n0 = int(np.sum(min_pae_per_to < pae_cutoff))

    if n0 == 0:
        return 0.0

    n0_clamped = max(n0, 19)
    d0 = 1.24 * (n0_clamped - 15) ** (1.0 / 3.0) - 1.8
    d0 = max(d0, 0.5)

    scores = 1.0 / (1.0 + (min_pae_per_to / d0) ** 2)
    good_mask = min_pae_per_to < pae_cutoff

    if good_mask.sum() == 0:
        return 0.0

    return float(scores[good_mask].mean())


def score_multi_seed(
    npz_paths: list[str],
    design_chain_ids: list[int] | None = None,
    target_chain_ids: list[int] | None = None,
    design_chain: str = "A",
    target_chain: str = "B",
    pae_cutoff: float = 10.0,
    aggregation: str = "best",
) -> dict:
    """Score ipSAE across multiple Protenix seed outputs.

    For antibody design, minimum 20 seeds recommended.

    Args:
        npz_paths: List of paths to Protenix NPZ output files (one per seed).
        design_chain_ids: Integer chain IDs for design (for NPZ format).
        target_chain_ids: Integer chain IDs for target (for NPZ format).
        design_chain: String chain ID for design (for JSON format).
        target_chain: String chain ID for target (for JSON format).
        pae_cutoff: PAE threshold (10.0 for Protenix/AF3).
        aggregation: How to select best seed — "best" (max ipsae_min), "mean", "median".

    Returns:
        dict with best_seed_idx, best_ipsae_min, all_seed_scores, aggregation, num_seeds
    """
    all_scores: list[dict[str, Any]] = []
    for i, path_str in enumerate(npz_paths):
        p = Path(path_str)
        try:
            if p.suffix == ".json":
                score = score_from_protenix_output(str(p), design_chain, target_chain)
            else:
                score = score_npz(
                    str(p), design_chain_ids or [], target_chain_ids or [], pae_cutoff
                )
        except Exception as exc:
            score = {"error": str(exc)}
        score["seed_idx"] = i
        score["source_file"] = str(p)
        all_scores.append(score)

    # Filter out errored seeds
    valid_scores = [s for s in all_scores if "error" not in s]
    if not valid_scores:
        return {"error": "No valid seed outputs found", "num_seeds": 0, "all_seed_scores": all_scores}

    # Extract ipsae_min from each seed.  score_npz uses "design_ipsae_min";
    # score_from_protenix_output uses "ipsae_min".  Accept either key.
    def _get_ipsae_min(s: dict) -> float:
        return float(s.get("ipsae_min", s.get("design_ipsae_min", 0.0)))

    ipsae_values = [_get_ipsae_min(s) for s in valid_scores]

    if aggregation == "mean":
        target_val = float(np.mean(ipsae_values))
        best_valid_idx = int(np.argmin([abs(v - target_val) for v in ipsae_values]))
    elif aggregation == "median":
        target_val = float(np.median(ipsae_values))
        best_valid_idx = int(np.argmin([abs(v - target_val) for v in ipsae_values]))
    else:  # "best" (default)
        best_valid_idx = int(np.argmax(ipsae_values))

    best_seed = valid_scores[best_valid_idx]

    return {
        "best_seed_idx": best_seed["seed_idx"],
        "best_ipsae_min": float(ipsae_values[best_valid_idx]),
        "best_seed_scores": best_seed,
        "aggregation": aggregation,
        "num_seeds": len(all_scores),
        "num_valid_seeds": len(valid_scores),
        "all_ipsae_min": [round(v, 4) for v in ipsae_values],
        "mean_ipsae_min": round(float(np.mean(ipsae_values)), 4),
        "std_ipsae_min": round(float(np.std(ipsae_values)), 4),
    }


def score_multi_seed_dir(
    npz_dir: str,
    design_chain_ids: list[int] | None = None,
    target_chain_ids: list[int] | None = None,
    design_chain: str = "A",
    target_chain: str = "B",
    pae_cutoff: float = 10.0,
    aggregation: str = "best",
) -> dict:
    """Score ipSAE across all NPZ/JSON files in a directory.

    Convenience wrapper around :func:`score_multi_seed` that discovers
    all ``*.npz`` and ``*confidence*.json`` files in *npz_dir*.

    Args:
        npz_dir: Directory containing Protenix seed output files.
        design_chain_ids: Integer chain IDs for design (for NPZ format).
        target_chain_ids: Integer chain IDs for target (for NPZ format).
        design_chain: String chain ID for design (for JSON format).
        target_chain: String chain ID for target (for JSON format).
        pae_cutoff: PAE threshold (10.0 for Protenix/AF3).
        aggregation: How to select best seed — "best", "mean", or "median".

    Returns:
        Same as :func:`score_multi_seed`.
    """
    d = Path(npz_dir)
    if not d.is_dir():
        return {"error": f"Directory not found: {npz_dir}"}
    paths = sorted(list(d.glob("*.npz")) + list(d.glob("*confidence*.json")))
    if not paths:
        return {"error": f"No NPZ or confidence JSON files found in {npz_dir}"}
    return score_multi_seed(
        [str(p) for p in paths],
        design_chain_ids,
        target_chain_ids,
        design_chain,
        target_chain,
        pae_cutoff,
        aggregation,
    )


def interpret_ipsae(score: float) -> str:
    """Human-readable interpretation of ipSAE score."""
    if score >= 0.8:
        return "excellent — strong predicted binding interface"
    elif score >= 0.6:
        return "good — likely binder"
    elif score >= 0.4:
        return "moderate — possible binder, consider more designs"
    elif score >= 0.2:
        return "weak — unlikely to bind"
    else:
        return "poor — no predicted binding"
