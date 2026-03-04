"""Wrapper for PXDesign (proteus-prot) de novo binder design."""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from proteus_cli.common import ToolResult, run_command, validate_tool_path


PRESETS: dict[str, str] = {
    "preview": "preview",
    "extended": "extended",
}


def build_pxdesign_config(
    target_pdb: str | Path,
    target_chains: list[str],
    hotspot_residues: list[str] | None = None,
    output_dir: str | Path | None = None,
    preset: str = "extended",
    num_designs: int = 10,
) -> Path:
    """Create a YAML config file for PXDesign and return its path.

    Parameters
    ----------
    target_pdb:
        Path to the target PDB file.
    target_chains:
        Chain identifiers to target (e.g. ``["A"]``).
    hotspot_residues:
        Optional list of hotspot residue identifiers (e.g. ``["A45", "A50"]``).
    output_dir:
        Directory for outputs.  Defaults to the parent directory of *target_pdb*.
    preset:
        PXDesign preset name (``"preview"`` or ``"extended"``).
    num_designs:
        Number of designs to generate.

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

    config: dict = {
        "target": {
            "pdb_path": str(target_pdb),
            "chains": list(target_chains),
        },
        "design": {
            "preset": preset,
            "num_designs": num_designs,
        },
        "output": {
            "directory": str(output_dir),
        },
    }

    if hotspot_residues:
        config["target"]["hotspot_residues"] = list(hotspot_residues)

    config_path = output_dir / "pxdesign_config.yaml"
    with open(config_path, "w") as fh:
        yaml.dump(config, fh, default_flow_style=False, sort_keys=False)

    return config_path


def run_protein_design(
    config_path: str | Path,
    preset: str = "extended",
    nproc: int = 1,
    gpu_ids: str = "0",
) -> ToolResult:
    """Run PXDesign pipeline.

    Parameters
    ----------
    config_path:
        Path to the YAML config file produced by :func:`build_pxdesign_config`.
    preset:
        PXDesign preset name.
    nproc:
        Number of processes per node.  If > 1, ``--nproc_per_node`` is appended.
    gpu_ids:
        Comma-separated GPU device IDs.

    Returns
    -------
    ToolResult
        Standardized result with status ``"success"`` or ``"error"``.
    """
    tool_path = validate_tool_path("proteus-prot")
    config_path = Path(config_path)

    cmd: list[str] = [
        "pxdesign",
        "pipeline",
        "--config",
        str(config_path),
        "--preset",
        preset,
    ]

    if nproc > 1:
        cmd.extend(["--nproc_per_node", str(nproc)])

    proc = run_command(cmd, cwd=tool_path)

    if proc.returncode != 0:
        return ToolResult(
            tool="proteus-prot",
            status="error",
            error=proc.stderr or proc.stdout,
        )

    return ToolResult(
        tool="proteus-prot",
        status="success",
        output_dir=config_path.parent,
    )


def parse_design_results(output_dir: str | Path) -> list[dict]:
    """Parse PXDesign ``summary.csv`` into a list of design dicts.

    Parameters
    ----------
    output_dir:
        Directory containing the ``summary.csv`` produced by PXDesign.

    Returns
    -------
    list[dict]
        Design records sorted by *score* descending.  Each dict contains at
        least ``design_name``, ``score``, ``sc_score``, and ``mpnn_score``.
        Returns an empty list when the file is missing.
    """
    summary_path = Path(output_dir) / "summary.csv"
    if not summary_path.exists():
        return []

    designs: list[dict] = []
    with open(summary_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            designs.append(
                {
                    "design_name": row.get("design_name", ""),
                    "score": float(row.get("score", 0.0)),
                    "sc_score": float(row.get("sc_score", 0.0)),
                    "mpnn_score": float(row.get("mpnn_score", 0.0)),
                }
            )

    designs.sort(key=lambda d: d["score"], reverse=True)
    return designs
