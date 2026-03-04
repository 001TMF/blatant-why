"""p_bind inference — binding probability prediction from Protenix features.

Wraps BoltzGen's PBindHead model for inference on new designs.
Uses Protenix trunk features (s_trunk, z_trunk) extracted during refolding.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_pbind_model(checkpoint_path: Path, device: str = "cpu"):
    """Load a trained p_bind checkpoint."""
    from boltzgen.pbind.model import PBindHead
    return PBindHead.from_checkpoint(str(checkpoint_path), device=device)


def predict_binding(
    model: Any,
    v_ab,  # [1, 384] antibody representation
    v_ag,  # [1, 384] antigen representation
    v_if,  # [1, 256] interface representation
) -> float:
    """Predict binding probability for a single design."""
    import torch
    with torch.no_grad():
        output = model(v_ab, v_ag, v_if)
        return output["binding_prob"][0].item()


def extract_features_from_trunk(
    s_trunk,     # [1, N, 384]
    z_trunk,     # [1, N, N, 128]
    asym_id,     # [N] or [1, N]
) -> dict:
    """Extract p_bind features from Protenix trunk outputs.

    Uses the v2 chain_design_mask (full VH/VL chains, NOT CDR-only).
    """
    import torch
    from boltzgen.model.layers.binding_utils import extract_pbind_features
    from proteus_ab.pbind.trunk import build_chain_design_mask

    chain_mask = build_chain_design_mask(asym_id)
    token_pad_mask = torch.ones(1, s_trunk.shape[1], device=s_trunk.device)

    feats = extract_pbind_features(
        s_trunk=s_trunk,
        z_trunk=z_trunk,
        design_mask=chain_mask,
        chain_design_mask=chain_mask,
        token_pad_mask=token_pad_mask,
    )
    return feats


def interpret_pbind(prob: float) -> str:
    """Human-readable interpretation of binding probability."""
    if prob > 0.8:
        return "High confidence binder"
    elif prob > 0.5:
        return "Likely binder"
    elif prob > 0.3:
        return "Marginal — consider redesign"
    else:
        return "Unlikely to bind"
