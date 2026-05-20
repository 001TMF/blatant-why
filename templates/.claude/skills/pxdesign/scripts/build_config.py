#!/usr/bin/env python3
"""Build a validated PXDesign YAML config from a target structure and hotspot list.

Purpose
-------
Translate a user request ("design a binder against IL6R, hotspots A40, A50,
A55, B12, binder length 80, preset extended") into a syntactically and
semantically valid PXDesign YAML config file. Validates against the schema
documented in ``references/yaml-config-spec.md``:

- ``target.file`` exists and is .cif or .pdb
- chain IDs use ``label_asym_id`` (parsed from the structure)
- every hotspot residue number exists in its chain (within crop ranges if given)
- ``binder_length`` is a positive integer
- crop range strings are ``"start-end"`` with start <= end

Inputs (CLI)
------------
--target            Path to target structure (.cif preferred, .pdb accepted)
--hotspots          Comma-separated hotspot list in "A40,A50,B12" notation
                    (chain letter + residue number). Optional.
--chains            Comma-separated chain IDs to include with "all" residues
                    (used when no hotspots are given for that chain). Optional.
--crop              Per-chain crop ranges, e.g. "A:1-116;A:200-250;B:1-90".
                    Optional.
--msa               Per-chain MSA directory paths, e.g. "A:/data/msa/chainA".
                    Optional.
--binder-length     Integer binder length (default: 100).
--preset            Preset name; recorded as a comment in the YAML for trace.
                    One of: preview, extended. Default: preview.
--out               Output YAML path. Required.

Outputs
-------
- A YAML file at ``--out`` matching the PXDesign config schema.
- On stdout: ``✓ Config written: <path> (N chains, M hotspots)``

Example
-------
    python build_config.py \\
        --target /data/targets/IL6R.cif \\
        --hotspots "A40,A50,A55,B12" \\
        --binder-length 80 \\
        --preset extended \\
        --out /tmp/il6r/config.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    sys.exit("Install with: pip install pyyaml")

try:
    from Bio.PDB import MMCIFParser, PDBParser
except ImportError:
    sys.exit("Install with: pip install biopython")


VALID_PRESETS = {"preview", "extended"}


def parse_hotspots(spec: Optional[str]) -> Dict[str, List[int]]:
    """Parse a ``"A40,A50,B12"`` style hotspot spec into ``{chain: [resnums]}``.

    Accepts whitespace around commas. Chain letter must be A-Z (single char).
    Residue number must be a positive integer.
    """
    if not spec:
        return {}
    out: Dict[str, List[int]] = {}
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if len(token) < 2 or not token[0].isalpha():
            raise ValueError(
                f"Hotspot '{token}' must start with a chain letter and a residue "
                f"number, e.g. 'A40'."
            )
        chain = token[0].upper()
        try:
            resnum = int(token[1:])
        except ValueError as e:
            raise ValueError(f"Hotspot '{token}': residue number not an integer.") from e
        if resnum < 1:
            raise ValueError(f"Hotspot '{token}': residue number must be >= 1.")
        out.setdefault(chain, []).append(resnum)
    # Stable sort and de-dup per chain
    for chain in out:
        out[chain] = sorted(set(out[chain]))
    return out


def parse_crop(spec: Optional[str]) -> Dict[str, List[str]]:
    """Parse ``"A:1-116;A:200-250;B:1-90"`` into ``{chain: ["1-116", "200-250"]}``."""
    if not spec:
        return {}
    out: Dict[str, List[str]] = {}
    for token in spec.split(";"):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"Crop entry '{token}' must be 'CHAIN:start-end'.")
        chain, rng = token.split(":", 1)
        chain = chain.strip().upper()
        rng = rng.strip()
        if "-" not in rng:
            raise ValueError(f"Crop range '{rng}' must be 'start-end'.")
        start_s, end_s = rng.split("-", 1)
        try:
            start, end = int(start_s), int(end_s)
        except ValueError as e:
            raise ValueError(f"Crop range '{rng}': start/end must be integers.") from e
        if start > end:
            raise ValueError(f"Crop range '{rng}': start ({start}) > end ({end}).")
        out.setdefault(chain, []).append(f"{start}-{end}")
    return out


def parse_msa(spec: Optional[str]) -> Dict[str, str]:
    """Parse ``"A:/data/msa/A;B:/data/msa/B"`` into ``{chain: path}``."""
    if not spec:
        return {}
    out: Dict[str, str] = {}
    for token in spec.split(";"):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"MSA entry '{token}' must be 'CHAIN:/path'.")
        chain, path = token.split(":", 1)
        out[chain.strip().upper()] = path.strip()
    return out


def load_structure_chains(target_path: str) -> Dict[str, Set[int]]:
    """Return ``{chain_id: {residue_numbers...}}`` keyed by ``label_asym_id``.

    Biopython's chain.id corresponds to ``label_asym_id`` for mmCIF files and
    to the auth chain ID for PDB files. We document this nuance in
    ``references/yaml-config-spec.md``.
    """
    ext = os.path.splitext(target_path)[1].lower()
    if ext == ".cif":
        parser = MMCIFParser(QUIET=True)
    elif ext == ".pdb":
        parser = PDBParser(QUIET=True)
    else:
        raise ValueError(f"Target must be .cif or .pdb (got '{ext}').")
    structure = parser.get_structure("target", target_path)
    chains: Dict[str, Set[int]] = {}
    for model in structure:
        for chain in model:
            resnums = {
                res.id[1] for res in chain.get_residues() if res.id[0] == " "
            }
            chains.setdefault(chain.id, set()).update(resnums)
        break  # only first model
    return chains


def validate_hotspots(
    hotspots: Dict[str, List[int]],
    available: Dict[str, Set[int]],
    crops: Dict[str, List[str]],
) -> None:
    """Raise ValueError if any hotspot is not present in its chain (or crop)."""
    for chain, resnums in hotspots.items():
        if chain not in available:
            raise ValueError(
                f"Hotspot chain '{chain}' not found in target. "
                f"Available label_asym_id chains: {sorted(available)}"
            )
        chain_residues = available[chain]
        crop_set: Optional[Set[int]] = None
        if chain in crops and crops[chain]:
            crop_set = set()
            for rng in crops[chain]:
                start_s, end_s = rng.split("-", 1)
                crop_set.update(range(int(start_s), int(end_s) + 1))
        for resnum in resnums:
            if resnum not in chain_residues:
                raise ValueError(
                    f"Hotspot {chain}{resnum} is not present in chain {chain} "
                    f"(chain spans residues "
                    f"{min(chain_residues)}-{max(chain_residues)})."
                )
            if crop_set is not None and resnum not in crop_set:
                raise ValueError(
                    f"Hotspot {chain}{resnum} falls outside the crop range "
                    f"{crops[chain]} for chain {chain}."
                )


def build_config_dict(
    target_path: str,
    hotspots: Dict[str, List[int]],
    crops: Dict[str, List[str]],
    msa: Dict[str, str],
    extra_chains: List[str],
    binder_length: int,
) -> Tuple[Dict, int, int]:
    """Assemble the PXDesign YAML dict. Returns (config, n_chains, n_hotspots)."""
    chain_keys: Set[str] = set(hotspots) | set(crops) | set(msa) | set(extra_chains)
    if not chain_keys:
        raise ValueError(
            "No chains specified. Provide --hotspots, --chains, --crop, or --msa."
        )

    chains_block: Dict[str, object] = {}
    for chain in sorted(chain_keys):
        entry: Dict[str, object] = {}
        if chain in crops and crops[chain]:
            entry["crop"] = crops[chain]
        if chain in hotspots and hotspots[chain]:
            entry["hotspots"] = hotspots[chain]
        if chain in msa and msa[chain]:
            entry["msa"] = msa[chain]
        chains_block[chain] = entry if entry else "all"

    config: Dict[str, object] = {
        "target": {
            "file": os.path.abspath(target_path),
            "chains": chains_block,
        },
        "binder_length": binder_length,
    }
    n_hotspots = sum(len(v) for v in hotspots.values())
    return config, len(chain_keys), n_hotspots


def write_yaml(config: Dict, out_path: str, preset: str) -> None:
    """Write the YAML with a header comment recording the preset choice."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(f"# PXDesign config — preset hint: {preset}\n")
        fh.write("# Generated by build_config.py\n")
        yaml.safe_dump(config, fh, sort_keys=False, default_flow_style=False)


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Build a validated PXDesign YAML config.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python build_config.py --target IL6R.cif "
            '--hotspots "A40,A50,A55,B12" --binder-length 80 '
            "--preset extended --out config.yaml"
        ),
    )
    ap.add_argument("--target", required=True, help="Path to target .cif or .pdb")
    ap.add_argument(
        "--hotspots",
        default=None,
        help='Comma-separated "A40,A50,B12" notation. Optional.',
    )
    ap.add_argument(
        "--chains",
        default=None,
        help='Comma-separated chain IDs to include with "all" residues. Optional.',
    )
    ap.add_argument(
        "--crop",
        default=None,
        help='Per-chain crop ranges, e.g. "A:1-116;A:200-250". Optional.',
    )
    ap.add_argument(
        "--msa",
        default=None,
        help='Per-chain MSA paths, e.g. "A:/data/msa/A". Optional.',
    )
    ap.add_argument("--binder-length", type=int, default=100, help="Binder length (default 100).")
    ap.add_argument(
        "--preset",
        default="preview",
        choices=sorted(VALID_PRESETS),
        help="Preset hint recorded in the YAML header (default preview).",
    )
    ap.add_argument("--out", required=True, help="Output YAML path.")
    args = ap.parse_args()

    if not os.path.exists(args.target):
        sys.exit(f"ERROR: target file not found: {args.target}")
    if args.binder_length < 1:
        sys.exit("ERROR: --binder-length must be a positive integer.")

    try:
        hotspots = parse_hotspots(args.hotspots)
        crops = parse_crop(args.crop)
        msa = parse_msa(args.msa)
        extra_chains = (
            [c.strip().upper() for c in args.chains.split(",") if c.strip()]
            if args.chains
            else []
        )
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    try:
        available = load_structure_chains(args.target)
    except Exception as e:  # noqa: BLE001 — surface any parsing failure to user
        sys.exit(f"ERROR parsing target structure: {e}")

    try:
        validate_hotspots(hotspots, available, crops)
        for chain in crops:
            if chain not in available:
                raise ValueError(
                    f"Crop chain '{chain}' not in target "
                    f"(available: {sorted(available)})."
                )
        for chain in extra_chains:
            if chain not in available:
                raise ValueError(
                    f"Chain '{chain}' from --chains not in target "
                    f"(available: {sorted(available)})."
                )
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    try:
        config, n_chains, n_hotspots = build_config_dict(
            target_path=args.target,
            hotspots=hotspots,
            crops=crops,
            msa=msa,
            extra_chains=extra_chains,
            binder_length=args.binder_length,
        )
    except ValueError as e:
        sys.exit(f"ERROR: {e}")

    write_yaml(config, args.out, preset=args.preset)
    print(
        f"✓ Config written: {args.out} "
        f"({n_chains} chain{'s' if n_chains != 1 else ''}, "
        f"{n_hotspots} hotspot{'s' if n_hotspots != 1 else ''}, "
        f"binder_length={args.binder_length}, preset={args.preset})"
    )


if __name__ == "__main__":
    main()
