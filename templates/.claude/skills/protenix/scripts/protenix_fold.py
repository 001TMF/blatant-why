"""protenix_fold.py — Validated wrapper around the `protenix pred` CLI.

Purpose
-------
Drive a Protenix structure prediction from a JSON input spec. Validates the
input before invoking the CLI so that bad specs fail locally rather than
after a multi-minute GPU run. Routes to one of three compute targets:

    local     (default) — invoke `protenix` on the host GPU
    hpc                 — emit the planned RunPod / HPC command (see
                          `by-deploy-compute` skill for the actual dispatcher)
    tamarind            — emit the planned Tamarind cloud command (fallback)

Inputs
------
- Input JSON file (see `references/input-json-spec.md`).
- Output directory (created if missing).
- Model name (defaults to `protenix_base_default_v1.0.0`).
- Target (`local` | `hpc` | `tamarind`; default `local`).

Outputs
-------
- Protenix output tree under `<output-dir>/<name>/seed_<int>/…` for the
  `local` target. For `hpc` / `tamarind`, the planned command is printed and
  no compute is launched here (the deploy skill owns dispatch).

Example
-------
    python protenix_fold.py \\
        --input  /tmp/fold_run/input.json \\
        --output-dir /tmp/fold_run/output \\
        --model  protenix_base_default_v1.0.0 \\
        --target local
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

VALID_TARGETS: tuple[str, ...] = ("local", "hpc", "tamarind")
DEFAULT_MODEL: str = "protenix_base_default_v1.0.0"
VALID_AA: frozenset[str] = frozenset("ACDEFGHIKLMNPQRSTVWY")


def _fail(message: str) -> None:
    """Print a single error line and exit non-zero."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_input(path: Path) -> list[dict[str, Any]]:
    """Load and JSON-parse the input spec file.

    Returns the parsed list (Protenix expects a JSON array at the top level).
    """
    if not path.is_file():
        _fail(f"input file not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(f"input is not valid JSON: {exc}")
    if not isinstance(data, list):
        _fail("input must be a JSON array (wrap your object in [...])")
    if len(data) != 1:
        _fail(
            f"input array must contain exactly one prediction object (got {len(data)})"
        )
    return data


def validate_entity(entity: Any, idx: int) -> None:
    """Validate a single entry of the `sequences` array."""
    # Plain-string shorthand is allowed: Protenix auto-wraps as proteinChain.
    if isinstance(entity, str):
        if not entity:
            _fail(f"sequences[{idx}] is an empty string")
        if any(ch not in VALID_AA for ch in entity):
            _fail(
                f"sequences[{idx}] contains non-standard amino acid letters; "
                "only ACDEFGHIKLMNPQRSTVWY are supported in the plain form"
            )
        return

    if not isinstance(entity, dict):
        _fail(f"sequences[{idx}] must be a string or an object")

    if "proteinChain" in entity:
        chain = entity["proteinChain"]
        if not isinstance(chain, dict):
            _fail(f"sequences[{idx}].proteinChain must be an object")
        seq = chain.get("sequence")
        if not isinstance(seq, str) or not seq:
            _fail(f"sequences[{idx}].proteinChain.sequence missing or empty")
        if any(ch not in VALID_AA for ch in seq):
            _fail(
                f"sequences[{idx}].proteinChain.sequence contains non-standard "
                "amino acids; only ACDEFGHIKLMNPQRSTVWY are supported"
            )
        count = chain.get("count", 1)
        if not isinstance(count, int) or count < 1:
            _fail(f"sequences[{idx}].proteinChain.count must be an int >= 1")
        return

    if "ligand" in entity:
        lig = entity["ligand"]
        if not isinstance(lig, dict):
            _fail(f"sequences[{idx}].ligand must be an object")
        smiles = lig.get("smiles")
        if not isinstance(smiles, str) or not smiles:
            _fail(f"sequences[{idx}].ligand.smiles missing or empty")
        count = lig.get("count", 1)
        if not isinstance(count, int) or count < 1:
            _fail(f"sequences[{idx}].ligand.count must be an int >= 1")
        return

    _fail(
        f"sequences[{idx}] must contain one of: 'proteinChain', 'ligand', "
        "or be a plain sequence string"
    )


def validate_spec(spec: dict[str, Any]) -> None:
    """Validate the single prediction object inside the JSON array."""
    if not isinstance(spec, dict):
        _fail("prediction entry must be a JSON object")

    name = spec.get("name")
    if not isinstance(name, str) or not name:
        _fail("'name' must be a non-empty string")
    if not all(ch.isalnum() or ch == "_" for ch in name):
        _fail("'name' must contain only alphanumeric characters and underscores")

    sequences = spec.get("sequences")
    if not isinstance(sequences, list) or not sequences:
        _fail("'sequences' must be a non-empty array")
    for idx, entity in enumerate(sequences):
        validate_entity(entity, idx)

    seeds = spec.get("modelSeeds")
    if not isinstance(seeds, list) or not seeds:
        _fail("'modelSeeds' must be a non-empty array of positive integers")
    for s in seeds:
        if not isinstance(s, int) or s < 0:
            _fail(f"'modelSeeds' contains non-integer or negative value: {s!r}")

    sample_count = spec.get("sampleCount")
    if not isinstance(sample_count, int) or sample_count < 1:
        _fail("'sampleCount' must be an int >= 1")


def build_local_cmd(
    input_path: Path,
    output_dir: Path,
    model: str,
    dtype: str,
) -> list[str]:
    """Construct the local Protenix CLI invocation."""
    return [
        "protenix",
        "pred",
        "-i",
        str(input_path),
        "-n",
        model,
        "--use_default_params",
        "true",
        "--dtype",
        dtype,
        "-o",
        str(output_dir),
    ]


def run_local(
    input_path: Path,
    output_dir: Path,
    model: str,
    dtype: str,
) -> None:
    """Invoke Protenix on the local GPU."""
    if shutil.which("protenix") is None:
        _fail(
            "`protenix` not on PATH. Set PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR and "
            "ensure the binary is installed (see SKILL.md Installation)."
        )

    env = os.environ.copy()
    if "PROTENIX_ROOT_DIR" not in env:
        fold_dir = env.get("PROTEUS_FOLD_DIR")
        if fold_dir:
            env["PROTENIX_ROOT_DIR"] = fold_dir
        else:
            _fail(
                "Neither PROTENIX_ROOT_DIR nor PROTEUS_FOLD_DIR is set; "
                "the CLI will not find its model assets."
            )

    cmd = build_local_cmd(input_path, output_dir, model, dtype)
    print(f"→ Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        _fail(f"protenix CLI exited with code {exc.returncode}")
    except FileNotFoundError:
        _fail("`protenix` binary disappeared between which() and exec()")


def plan_remote(
    target: str,
    input_path: Path,
    output_dir: Path,
    model: str,
    dtype: str,
) -> None:
    """Print the planned remote command without dispatching it.

    Actual dispatch (RunPod for HPC, Tamarind for cloud) is owned by the
    `by-deploy-compute` skill — this script only emits the intended command
    so the deploy skill (or the user) can execute it.
    """
    cmd = build_local_cmd(input_path, output_dir, model, dtype)
    print(f"→ Planned {target} command (dispatch via by-deploy-compute skill):")
    print("    " + " ".join(cmd))
    print(
        f"✓ Validated input ready for {target} dispatch: {input_path}",
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run a Protenix structure prediction from a validated JSON spec.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the input JSON spec (see references/input-json-spec.md).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where Protenix output should land. Created if missing.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "Full Protenix model name "
            f"(default: {DEFAULT_MODEL}). Use the full name, not a short key."
        ),
    )
    parser.add_argument(
        "--target",
        choices=VALID_TARGETS,
        default="local",
        help=(
            "Compute target. 'local' invokes the on-host GPU CLI; "
            "'hpc' / 'tamarind' validate the input and print the planned "
            "command for the by-deploy-compute skill to dispatch."
        ),
    )
    parser.add_argument(
        "--dtype",
        default="bf16",
        help="Precision passed to the CLI (default: bf16).",
    )
    args = parser.parse_args()

    spec_list = load_input(args.input)
    validate_spec(spec_list[0])
    print(f"✓ Input spec validated: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.target == "local":
        run_local(args.input, args.output_dir, args.model, args.dtype)
        print(f"✓ Protenix prediction completed: {args.output_dir}")
    else:
        plan_remote(args.target, args.input, args.output_dir, args.model, args.dtype)


if __name__ == "__main__":
    main()
