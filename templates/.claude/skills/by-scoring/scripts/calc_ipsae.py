#!/usr/bin/env python3
"""Compute ipSAE from a PAE matrix and chain assignments.

Reference implementation of the DunbrackLab ipSAE formula
(Dunbrack et al., "Res ipSAE loquuntur", 2025).

Inputs:
    - PAE matrix as JSON or NumPy .npy file (shape [N, N])
    - Chain assignments as a JSON list (length N) — chain ID per token
    - Design chain ID(s) and target chain ID(s)
    - Optional PAE cutoff (default 10.0 A for Protenix/AF3)

Outputs:
    - Stdout: design_to_target_ipsae, target_to_design_ipsae, ipsae_min,
      n0 per direction, d0 per direction

Example invocation:
    python calc_ipsae.py --pae pae.json --chains chains.json \\
        --design A --target B
    python calc_ipsae.py --example          # run the worked example from references/

Dependencies:
    numpy >= 1.20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:
    sys.exit("Install with: pip install 'numpy>=1.20'")


def _directional_ipsae(
    pae: np.ndarray,
    from_mask: np.ndarray,
    to_mask: np.ndarray,
    pae_cutoff: float,
) -> dict[str, float]:
    """Compute directional ipSAE (from -> to).

    Returns a dict with the directional ipSAE plus diagnostics (n0, d0).
    """
    interchain_pae = pae[np.ix_(from_mask, to_mask)]

    if interchain_pae.size == 0:
        return {"ipsae": 0.0, "n0": 0, "d0": 0.0}

    min_pae_per_to_residue = interchain_pae.min(axis=0)
    n0 = int(np.sum(min_pae_per_to_residue < pae_cutoff))

    if n0 == 0:
        return {"ipsae": 0.0, "n0": 0, "d0": 0.0}

    n0_clamped = max(n0, 19)
    d0 = 1.24 * (n0_clamped - 15) ** (1.0 / 3.0) - 1.8
    d0 = max(d0, 0.5)

    scores = 1.0 / (1.0 + (min_pae_per_to_residue / d0) ** 2)
    good_mask = min_pae_per_to_residue < pae_cutoff

    if good_mask.sum() == 0:
        return {"ipsae": 0.0, "n0": n0, "d0": d0}

    return {
        "ipsae": float(scores[good_mask].mean()),
        "n0": n0,
        "d0": float(d0),
    }


def compute_ipsae(
    pae_matrix: np.ndarray,
    chain_ids: np.ndarray,
    design_chains: list[Any],
    target_chains: list[Any],
    pae_cutoff: float = 10.0,
) -> dict[str, Any]:
    """Compute full ipSAE (both directions plus min) from a PAE matrix.

    Args:
        pae_matrix: [N, N] predicted aligned error matrix in Angstroms.
        chain_ids: [N] chain ID per token. Can be strings or ints.
        design_chains: list of chain IDs belonging to the design.
        target_chains: list of chain IDs belonging to the target.
        pae_cutoff: PAE threshold (10.0 for Protenix/AF3, 15.0 for AF2).

    Returns:
        Dict with directional ipSAE, ipsae_min, n0, d0 per direction.
    """
    design_mask = np.isin(chain_ids, design_chains)
    target_mask = np.isin(chain_ids, target_chains)

    if design_mask.sum() == 0:
        raise ValueError(f"No tokens match design chains {design_chains}")
    if target_mask.sum() == 0:
        raise ValueError(f"No tokens match target chains {target_chains}")

    dt = _directional_ipsae(pae_matrix, design_mask, target_mask, pae_cutoff)
    td = _directional_ipsae(pae_matrix, target_mask, design_mask, pae_cutoff)

    ipsae_min = min(dt["ipsae"], td["ipsae"])

    return {
        "design_to_target_ipsae": round(dt["ipsae"], 4),
        "target_to_design_ipsae": round(td["ipsae"], 4),
        "ipsae_min": round(ipsae_min, 4),
        "n0_design_to_target": dt["n0"],
        "n0_target_to_design": td["n0"],
        "d0_design_to_target": round(dt["d0"], 4),
        "d0_target_to_design": round(td["d0"], 4),
        "pae_cutoff": pae_cutoff,
    }


def load_pae(pae_path: Path) -> np.ndarray:
    """Load a PAE matrix from JSON or .npy."""
    if pae_path.suffix == ".npy":
        return np.array(np.load(pae_path), dtype=np.float64)
    if pae_path.suffix == ".json":
        with pae_path.open() as f:
            data = json.load(f)
        if isinstance(data, dict):
            # Protenix-style JSON with "pae" or "predicted_aligned_error" key
            matrix = data.get("pae", data.get("predicted_aligned_error"))
            if matrix is None:
                raise ValueError("PAE JSON has no 'pae' or 'predicted_aligned_error' key")
            return np.array(matrix, dtype=np.float64)
        return np.array(data, dtype=np.float64)
    raise ValueError(f"Unsupported PAE format: {pae_path.suffix}")


def load_chains(chain_path: Path) -> np.ndarray:
    """Load chain assignments from a JSON list."""
    with chain_path.open() as f:
        data = json.load(f)
    if isinstance(data, dict):
        chains = data.get("token_chain_ids", data.get("chain_ids"))
        if chains is None:
            raise ValueError("Chain JSON has no 'token_chain_ids' or 'chain_ids' key")
        return np.array(chains)
    return np.array(data)


def run_worked_example() -> dict[str, Any]:
    """Reproduce the numerical example from references/ipsae-algorithm.md.

    Returns the ipSAE result dict for the toy 4x5 interface.
    """
    # 4-residue design (D) + 5-residue target (T); full 9x9 PAE,
    # with the interchain block matching the worked example.
    pae = np.zeros((9, 9), dtype=np.float64)

    # Intra-chain PAE values: low (~1.0) to avoid affecting interchain extraction.
    for i in range(9):
        for j in range(9):
            pae[i, j] = 1.0 if i != j else 0.0

    # D = tokens 0..3, T = tokens 4..8
    interchain = np.array([
        [2.1, 3.5, 8.2, 12.0, 15.3],   # D1
        [3.0, 1.8, 4.5, 11.0, 14.2],   # D2
        [7.8, 5.2, 2.9, 9.5, 13.5],    # D3
        [10.5, 9.8, 8.0, 7.5, 12.1],   # D4
    ])
    pae[0:4, 4:9] = interchain
    pae[4:9, 0:4] = interchain.T

    chain_ids = np.array(["D"] * 4 + ["T"] * 5)

    result = compute_ipsae(
        pae_matrix=pae,
        chain_ids=chain_ids,
        design_chains=["D"],
        target_chains=["T"],
        pae_cutoff=10.0,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute ipSAE from a PAE matrix and chain assignments.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--pae",
        type=Path,
        help="Path to PAE matrix (.json or .npy).",
    )
    parser.add_argument(
        "--chains",
        type=Path,
        help="Path to chain assignments JSON (list or {token_chain_ids: [...]}).",
    )
    parser.add_argument(
        "--design",
        nargs="+",
        default=["A"],
        help="Chain ID(s) of the designed binder.",
    )
    parser.add_argument(
        "--target",
        nargs="+",
        default=["B"],
        help="Chain ID(s) of the target protein.",
    )
    parser.add_argument(
        "--pae-cutoff",
        type=float,
        default=10.0,
        help="PAE cutoff in Angstroms (10.0 for Protenix/AF3, 15.0 for AF2).",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Run the worked example from references/ipsae-algorithm.md and exit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write JSON output (otherwise prints to stdout).",
    )

    args = parser.parse_args()

    if args.example:
        result = run_worked_example()
        print(json.dumps(result, indent=2))
        expected_min = 0.0396
        actual_min = result["ipsae_min"]
        if abs(actual_min - expected_min) < 1e-3:
            print(
                f"✓ Worked example verified: ipsae_min={actual_min:.4f} "
                f"(expected {expected_min})"
            )
        else:
            print(
                f"✗ Worked example MISMATCH: ipsae_min={actual_min:.4f} "
                f"(expected {expected_min})"
            )
            sys.exit(1)
        return

    if args.pae is None or args.chains is None:
        parser.error("--pae and --chains are required unless --example is given")

    pae = load_pae(args.pae)
    chains = load_chains(args.chains)

    if pae.ndim != 2 or pae.shape[0] != pae.shape[1]:
        sys.exit(f"PAE matrix must be square 2D; got shape {pae.shape}")
    if len(chains) != pae.shape[0]:
        sys.exit(
            f"Chain assignment length {len(chains)} does not match PAE "
            f"matrix size {pae.shape[0]}"
        )

    # Try to coerce chain IDs to int if the provided design/target args are ints.
    def _coerce(values: list[str]) -> list[Any]:
        try:
            return [int(v) for v in values]
        except ValueError:
            return values

    result = compute_ipsae(
        pae_matrix=pae,
        chain_ids=chains,
        design_chains=_coerce(args.design),
        target_chains=_coerce(args.target),
        pae_cutoff=args.pae_cutoff,
    )

    output_text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text + "\n")
        print(f"✓ ipSAE computed: {args.output} (ipsae_min={result['ipsae_min']})")
    else:
        print(output_text)
        print(
            f"✓ ipSAE computed: ipsae_min={result['ipsae_min']} "
            f"(dt={result['design_to_target_ipsae']}, td={result['target_to_design_ipsae']})"
        )


if __name__ == "__main__":
    main()
