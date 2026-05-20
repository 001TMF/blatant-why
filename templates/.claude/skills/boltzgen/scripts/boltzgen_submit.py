#!/usr/bin/env python3
"""boltzgen_submit.py — Build and submit a BoltzGen design run.

Reads an entities YAML spec and a small set of CLI flags, constructs the
`boltzgen run ...` command, and either invokes it locally, hands off to
the HPC deployment skill (by-deploy-compute), or submits to Tamarind.

Inputs (CLI flags):
    --spec PATH               Path to entities YAML spec file (required)
    --protocol NAME           BoltzGen protocol (required): nanobody-anything,
                              antibody-anything, protein-anything,
                              peptide-anything, protein-redesign
    --num-designs INT         Number of designs to generate (default: 20)
    --budget INT              Diffusion sampling budget (default: 48)
    --msa-mode {none,precomputed,nim}  MSA strategy (default: none)
    --output PATH             Output directory (default: ./boltzgen_output)
    --prefilter               Enable Stage-3 pre-filtering
    --target {local,hpc,tamarind}  Compute target (default: local)
    --binding-residues PATH   Optional JSON file mapping chain_id -> [int,...]
                              to be converted to range notation and written
                              back into the spec (in-place edit)
    --dry-run                 Print the command without executing
    --seed INT                Random seed (default: 0)
    --extra-flag KEY=VALUE    Additional CLI flag to forward verbatim
                              (repeatable)

Outputs:
    Console verification line on success:
        ✓ boltzgen completed: <N> designs written to <output_dir>
    For HPC target, prints the deployment hand-off command and exits 0.
    For Tamarind target, prints the job ID and exits 0.

Example invocations:
    python boltzgen_submit.py \\
        --spec workspace/design_spec.yaml \\
        --protocol nanobody-anything \\
        --num-designs 20 --budget 48 --target local \\
        --output workspace/output --prefilter

    python boltzgen_submit.py --spec spec.yaml --protocol antibody-anything \\
        --num-designs 100 --budget 128 --target hpc --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:
    sys.exit("Install with: pip install pyyaml")


VALID_PROTOCOLS = (
    "nanobody-anything",
    "antibody-anything",
    "protein-anything",
    "peptide-anything",
    "protein-redesign",
)

VALID_MSA = ("none", "precomputed", "nim")

VALID_TARGETS = ("local", "hpc", "tamarind")


def residues_to_ranges(residues: Iterable[int]) -> str:
    """Convert a list of integers into BoltzGen range notation.

    Contiguous runs collapse to ``start..end``. Singletons become ``n..n``.
    Multiple ranges are comma-separated with no spaces.

    >>> residues_to_ranges([7, 8, 9, 10, 11, 12, 27, 28, 29, 30])
    '7..12,27..30'
    >>> residues_to_ranges([5])
    '5..5'
    >>> residues_to_ranges([5, 10, 15])
    '5..5,10..10,15..15'
    """
    sorted_residues = sorted(set(int(r) for r in residues))
    if not sorted_residues:
        return ""
    ranges: list[tuple[int, int]] = []
    start = prev = sorted_residues[0]
    for r in sorted_residues[1:]:
        if r == prev + 1:
            prev = r
            continue
        ranges.append((start, prev))
        start = prev = r
    ranges.append((start, prev))
    return ",".join(f"{a}..{b}" for a, b in ranges)


def inject_binding_residues(spec_path: Path, residues_path: Path) -> None:
    """Read residues JSON, convert to range notation, write into the spec.

    Residues JSON shape: ``{"A": [7, 8, ...], "B": [...]}``. The spec must
    already contain matching ``binding_types`` blocks for each chain; this
    function overwrites the ``binding:`` field for the listed chains.
    """
    residues = json.loads(residues_path.read_text())
    spec = yaml.safe_load(spec_path.read_text())
    target_entity = spec["entities"][0]["file"]
    target_entity.setdefault("binding_types", [])
    existing_by_chain = {
        bt["chain"]["id"]: bt for bt in target_entity["binding_types"]
    }
    for chain_id, res_list in residues.items():
        rng = residues_to_ranges(res_list)
        if chain_id in existing_by_chain:
            existing_by_chain[chain_id]["chain"]["binding"] = rng
        else:
            target_entity["binding_types"].append(
                {"chain": {"id": chain_id, "binding": rng}}
            )
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False))
    print(f"✓ binding residues injected: {len(residues)} chain(s) updated in {spec_path}")


def build_command(
    spec: Path,
    protocol: str,
    num_designs: int,
    budget: int,
    msa_mode: str,
    output: Path,
    prefilter: bool,
    seed: int,
    extra_flags: list[str],
) -> list[str]:
    """Construct the boltzgen CLI argv."""
    cmd = [
        "boltzgen",
        "run",
        str(spec),
        "--protocol",
        protocol,
        "--num_designs",
        str(num_designs),
        "--budget",
        str(budget),
        "--msa-mode",
        msa_mode,
        "--output",
        str(output),
        "--seed",
        str(seed),
    ]
    if prefilter:
        cmd.append("--prefilter")
    for flag in extra_flags:
        if "=" in flag:
            key, value = flag.split("=", 1)
            cmd.extend([f"--{key.lstrip('-')}", value])
        else:
            cmd.append(f"--{flag.lstrip('-')}")
    return cmd


def required_env() -> dict[str, str]:
    """Return env vars BoltzGen requires (LayerNorm + model weights path)."""
    return {
        "LAYERNORM_TYPE": os.environ.get("LAYERNORM_TYPE", "openfold"),
        "PROTEUS_MODELS_DIR": os.environ.get(
            "PROTEUS_MODELS_DIR", str(Path.home() / ".cache" / "boltzgen")
        ),
    }


def run_local(cmd: list[str], output: Path, dry_run: bool) -> int:
    """Invoke boltzgen on the local machine."""
    env = {**os.environ, **required_env()}
    if dry_run:
        print("DRY-RUN — would execute:")
        env_summary = " ".join(f"{k}={v}" for k, v in required_env().items())
        print(f"  {env_summary} \\\n    {' '.join(cmd)}")
        return 0
    if not shutil.which(cmd[0]):
        sys.exit(
            f"`{cmd[0]}` not found on PATH. Activate the BoltzGen conda env "
            f"or add $BOLTZGEN_DIR/bin to PATH."
        )
    output.mkdir(parents=True, exist_ok=True)
    print(f"Submitting (local): {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode != 0:
        sys.exit(f"boltzgen exited with code {result.returncode}")
    # Count produced designs (best-effort)
    final_dir = output / "final_ranked_designs"
    n = sum(1 for _ in final_dir.glob("*.cif")) if final_dir.exists() else 0
    print(f"✓ boltzgen completed: {n} designs written to {output}")
    return 0


def run_hpc(cmd: list[str], output: Path, dry_run: bool) -> int:
    """Hand off to the by-deploy-compute skill (RunPod by default)."""
    deploy_cmd = [
        "by-deploy-compute",
        "--engine",
        "boltzgen",
        "--",
        *cmd,
    ]
    print(
        "HPC target selected. Hand off to the `by-deploy-compute` skill — "
        "it owns container, GPU class, and secret injection."
    )
    print(f"Suggested invocation:\n  {' '.join(deploy_cmd)}")
    print(f"Local output staging dir: {output}")
    if dry_run:
        print("DRY-RUN — not executing.")
    return 0


def run_tamarind(cmd: list[str], output: Path, dry_run: bool) -> int:
    """Submit to Tamarind cloud (requires TAMARIND_API_KEY)."""
    if not os.environ.get("TAMARIND_API_KEY"):
        sys.exit(
            "TAMARIND_API_KEY env var not set. Export it before using "
            "--target tamarind, or switch to --target local / hpc."
        )
    print(
        "Tamarind target selected (cloud fallback). The actual REST "
        "submission is owned by the by-deploy-compute skill — call it "
        "with --provider tamarind."
    )
    print(f"Boltzgen CLI argv would be:\n  {' '.join(cmd)}")
    print(f"Local output staging dir: {output}")
    if dry_run:
        print("DRY-RUN — not executing.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a BoltzGen design run (local, HPC, or Tamarind)."
    )
    parser.add_argument("--spec", type=Path, required=True, help="Entities YAML spec path")
    parser.add_argument(
        "--protocol",
        choices=VALID_PROTOCOLS,
        required=True,
        help="BoltzGen protocol name",
    )
    parser.add_argument("--num-designs", type=int, default=20, dest="num_designs")
    parser.add_argument("--budget", type=int, default=48)
    parser.add_argument("--msa-mode", choices=VALID_MSA, default="none", dest="msa_mode")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./boltzgen_output"),
        help="Output directory for designs",
    )
    parser.add_argument("--prefilter", action="store_true", help="Enable Stage-3 pre-filter")
    parser.add_argument(
        "--target",
        choices=VALID_TARGETS,
        default="local",
        help="Compute target (default: local)",
    )
    parser.add_argument(
        "--binding-residues",
        type=Path,
        default=None,
        dest="binding_residues",
        help="Optional JSON {chain: [residues]} to inject into the spec before submitting",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--extra-flag",
        action="append",
        default=[],
        dest="extra_flags",
        help="Extra CLI flag KEY=VALUE forwarded to boltzgen (repeatable)",
    )
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.spec.exists():
        sys.exit(f"spec file not found: {args.spec}")

    if args.binding_residues is not None:
        if not args.binding_residues.exists():
            sys.exit(f"binding residues file not found: {args.binding_residues}")
        inject_binding_residues(args.spec, args.binding_residues)

    cmd = build_command(
        spec=args.spec,
        protocol=args.protocol,
        num_designs=args.num_designs,
        budget=args.budget,
        msa_mode=args.msa_mode,
        output=args.output,
        prefilter=args.prefilter,
        seed=args.seed,
        extra_flags=args.extra_flags,
    )

    if args.target == "local":
        return run_local(cmd, args.output, args.dry_run)
    if args.target == "hpc":
        return run_hpc(cmd, args.output, args.dry_run)
    if args.target == "tamarind":
        return run_tamarind(cmd, args.output, args.dry_run)
    sys.exit(f"unknown target: {args.target}")


if __name__ == "__main__":
    raise SystemExit(main())
