"""ipSAE scoring — standalone interface to BoltzGen's compute_ipsae_score.

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

from pathlib import Path
from typing import Any

import numpy as np

# Re-export from BoltzGen for direct use
# NOTE: This import requires BoltzGen to be installed.
# For environments without BoltzGen, use interpret_ipsae() directly.
try:
    from boltzgen.model.layers.confidence_utils import compute_ipsae_score
except ImportError:
    compute_ipsae_score = None


def score_npz(npz_path: Path, design_chain_ids: list[int], target_chain_ids: list[int]) -> dict[str, float]:
    """Score a Protenix output NPZ file for ipSAE metrics.

    Args:
        npz_path: Path to NPZ with 'pae' key [N_sample, N_token, N_token]
        design_chain_ids: asym_id integers for design chains
        target_chain_ids: asym_id integers for target chains

    Returns:
        Dict with best-sample ipSAE metrics.
    """
    if compute_ipsae_score is None:
        raise ImportError("BoltzGen is required for ipSAE scoring. Install it from /data/proteus/proteus-design/deps/BoltzGen/")

    import torch

    data = np.load(npz_path, allow_pickle=True)
    pae = torch.from_numpy(data["pae"]).float()  # [N_sample, N_token, N_token]

    # Build masks from asym_id if available
    if "token_asym_id" in data:
        asym_id = torch.from_numpy(data["token_asym_id"])
    else:
        n_tokens = pae.shape[1]
        asym_id = torch.zeros(n_tokens, dtype=torch.long)

    design_ids_t = torch.tensor(design_chain_ids)
    target_ids_t = torch.tensor(target_chain_ids)

    design_mask = torch.isin(asym_id, design_ids_t).unsqueeze(0).float()
    target_mask = torch.isin(asym_id, target_ids_t).unsqueeze(0).float()
    frame_mask = torch.ones_like(design_mask)
    pad_mask = torch.ones_like(design_mask)

    best_dt = -1.0
    best_td = -1.0
    best_min = -1.0

    for i in range(pae.shape[0]):
        pae_i = pae[i].unsqueeze(0)
        dt = compute_ipsae_score(design_mask, target_mask, pae_i, frame_mask, pad_mask).item()
        td = compute_ipsae_score(target_mask, design_mask, pae_i, frame_mask, pad_mask).item()
        mn = min(dt, td)
        if mn > best_min:
            best_dt, best_td, best_min = dt, td, mn

    return {
        "design_to_target_ipsae": best_dt,
        "target_to_design_ipsae": best_td,
        "design_ipsae_min": best_min,
    }


def interpret_ipsae(score: float) -> str:
    """Human-readable interpretation of ipSAE score."""
    if score > 0.8:
        return "Excellent interface — high confidence binding"
    elif score > 0.5:
        return "Good interface — likely binder"
    elif score > 0.3:
        return "Moderate interface — possible binder, consider redesign"
    else:
        return "Poor interface — unlikely to bind"
