"""Wrapper for PXDesign (proteus-prot) de novo binder design."""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from proteus_cli.common import ToolResult, get_tool_env, run_command, validate_tool_path


PRESETS: dict[str, str] = {
    "preview": "preview",
    "extended": "extended",
}


def build_pxdesign_config(
    target_pdb: str | Path,
    target_chains: list[str],
    hotspot_residues: list[str] | None = None,
    output_dir: str | Path | None = None,
    binder_length: int = 100,
    crop_ranges: dict[str, list[str]] | None = None,
    msa_dirs: dict[str, str] | None = None,
) -> Path:
    """Create a YAML config file for PXDesign and return its path.

    Parameters
    ----------
    target_pdb:
        Path to the target structure file (CIF or PDB).
    target_chains:
        Chain identifiers to target (e.g. ``["A"]``).
    hotspot_residues:
        Optional list of hotspot residue identifiers prefixed by chain
        (e.g. ``["A45", "A50"]``).  The chain letter is used to assign
        hotspots to the correct chain config entry.
    output_dir:
        Directory for outputs.  Defaults to the parent directory of *target_pdb*.
    binder_length:
        Length of the designed binder sequence.
    crop_ranges:
        Per-chain crop ranges, e.g. ``{"A": ["1-116"]}``.
    msa_dirs:
        Per-chain MSA directory paths, e.g. ``{"A": "./msa/chain_A"}``.

    Returns
    -------
    Path
        Path to the written ``pxdesign_config.yaml`` file.
    """
    target_pdb = Path(target_pdb)
    if output_dir is None:
        output_dir = target_pdb.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chains_config: dict = {}
    for chain in target_chains:
        chain_conf: dict = {}
        if crop_ranges and chain in crop_ranges:
            chain_conf["crop"] = crop_ranges[chain]
        if hotspot_residues:
            # Parse hotspot residues like ["A45", "A50"] to just indices for this chain
            chain_hotspots = [int(r[1:]) for r in hotspot_residues if r[0] == chain]
            if chain_hotspots:
                chain_conf["hotspots"] = chain_hotspots
        if msa_dirs and chain in msa_dirs:
            chain_conf["msa"] = msa_dirs[chain]
        chains_config[chain] = chain_conf if chain_conf else "all"

    config: dict = {
        "target": {
            "file": str(target_pdb),
            "chains": chains_config,
        },
        "binder_length": binder_length,
    }

    config_path = output_dir / "pxdesign_config.yaml"
    with open(config_path, "w") as fh:
        yaml.dump(config, fh, default_flow_style=False, sort_keys=False)

    return config_path


def run_protein_design(
    config_path: str | Path,
    preset: str = "extended",
    num_samples: int = 500,
    output_dir: str | Path | None = None,
) -> ToolResult:
    """Run PXDesign pipeline.

    Parameters
    ----------
    config_path:
        Path to the YAML config file produced by :func:`build_pxdesign_config`.
    preset:
        PXDesign preset name (``"preview"`` or ``"extended"``).
    num_samples:
        Number of design samples to generate.
    output_dir:
        Optional override for the output directory.

    Returns
    -------
    ToolResult
        Standardized result with status ``"success"`` or ``"error"``.
    """
    tool_path = validate_tool_path("pxdesign")
    config_path = Path(config_path)

    cmd: list[str] = [
        "pxdesign", "pipeline",
        "--preset", preset,
        "-i", str(config_path),
        "--N_sample", str(num_samples),
        "--dtype", "bf16",
        "--use_fast_ln", "True",
    ]
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-o", str(out)])

    env = get_tool_env("pxdesign")
    proc = run_command(cmd, cwd=tool_path, env=env)

    if proc.returncode != 0:
        return ToolResult(
            tool="pxdesign",
            status="error",
            error=proc.stderr or proc.stdout,
        )

    resolved_output = Path(output_dir) if output_dir else config_path.parent
    return ToolResult(
        tool="pxdesign",
        status="success",
        output_dir=resolved_output,
    )


def parse_design_results(output_dir: str | Path) -> list[dict]:
    """Parse PXDesign ``summary.csv`` into a list of design dicts.

    PXDesign writes results to
    ``<output_dir>/design_outputs/<task_name>/summary.csv``.

    Parameters
    ----------
    output_dir:
        Root output directory of a PXDesign run.

    Returns
    -------
    list[dict]
        Design records sorted by *ptx_iptm* descending.  Each dict contains
        ``rank``, ``name``, ``sequence``, and validation metrics.
        Returns an empty list when no summary CSV is found.
    """
    out = Path(output_dir)
    if not out.exists():
        return []

    # Search for summary.csv inside design_outputs/<task_name>/
    summary_files = sorted(out.rglob("design_outputs/*/summary.csv"))
    if not summary_files:
        # Fallback: look for any summary.csv
        summary_files = sorted(out.rglob("summary.csv"))
    if not summary_files:
        return []

    key_columns = [
        "rank", "name", "sequence",
        "af2_opt_success", "af2_easy_success",
        "ptx_success", "ptx_basic_success",
        "ptx_iptm", "af2_binder_plddt",
        "af2_complex_pred_design_rmsd",
    ]

    designs: list[dict] = []
    for summary_path in summary_files:
        with open(summary_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entry: dict = {}
                for col in key_columns:
                    val = row.get(col, "")
                    # Convert numeric-looking values
                    if col in ("rank",):
                        try:
                            entry[col] = int(val)
                        except (ValueError, TypeError):
                            entry[col] = val
                    elif col in ("ptx_iptm", "af2_binder_plddt", "af2_complex_pred_design_rmsd"):
                        try:
                            entry[col] = float(val)
                        except (ValueError, TypeError):
                            entry[col] = val
                    else:
                        entry[col] = val
                designs.append(entry)

    designs.sort(key=lambda d: float(d.get("ptx_iptm", 0.0) or 0.0), reverse=True)
    return designs
