"""Wrapper for proteus-ab (Proteus-AB antibody/nanobody design)."""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from proteus_cli.common import ToolResult, run_command, validate_tool_path


PROTOCOLS: dict[str, str] = {
    "nanobody-anything": "nanobody-anything",
    "antibody-anything": "antibody-anything",
}


def build_design_spec(
    target_pdb: str | Path,
    target_chains: list[str],
    epitope_residues: list[int],
    protocol: str = "nanobody-anything",
    num_designs: int = 10,
    output_dir: str | Path | None = None,
    prefilter: bool = True,
    msa_mode: str = "mmseqs2",
    budget: int = 100,
    diversity_alpha: float = 0.5,
) -> Path:
    """Create a YAML design spec file for proteus-ab and return its path.

    Parameters
    ----------
    target_pdb:
        Path to the target PDB file.
    target_chains:
        Chain identifiers to target (e.g. ``["A"]``).
    epitope_residues:
        Residue indices defining the epitope (e.g. ``[45, 50, 52]``).
    protocol:
        Design protocol (``"nanobody-anything"`` or ``"antibody-anything"``).
    num_designs:
        Number of designs to generate.
    output_dir:
        Directory for outputs.  Defaults to the parent directory of *target_pdb*.
    prefilter:
        Whether to enable prefiltering of designs.
    msa_mode:
        MSA generation mode (e.g. ``"mmseqs2"``).
    budget:
        Computational budget for the design run.
    diversity_alpha:
        Diversity weight controlling sequence diversity (0.0--1.0).

    Returns
    -------
    Path
        Path to the written ``design_spec.yaml`` file.
    """
    target_pdb = Path(target_pdb)
    if output_dir is None:
        output_dir = target_pdb.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    spec: dict = {
        "target": {
            "pdb_path": str(target_pdb),
            "chains": list(target_chains),
            "epitope_residues": list(epitope_residues),
        },
        "protocol": protocol,
        "design": {
            "num_designs": num_designs,
            "budget": budget,
            "diversity_alpha": diversity_alpha,
            "prefilter": prefilter,
            "msa_mode": msa_mode,
        },
        "output": {
            "directory": str(output_dir),
        },
    }

    spec_path = output_dir / "design_spec.yaml"
    with open(spec_path, "w") as fh:
        yaml.dump(spec, fh, default_flow_style=False, sort_keys=False)

    return spec_path


def run_antibody_design(
    spec_path: str | Path,
    gpu_ids: str = "0",
) -> ToolResult:
    """Run ``proteus-ab run`` for antibody/nanobody design.

    Parameters
    ----------
    spec_path:
        Path to the YAML spec file produced by :func:`build_design_spec`.
    gpu_ids:
        Comma-separated GPU device IDs.

    Returns
    -------
    ToolResult
        Standardized result with status ``"success"`` or ``"error"``.
    """
    tool_path = validate_tool_path("proteus-ab")
    spec_path = Path(spec_path)

    cmd: list[str] = [
        "proteus-ab",
        "run",
        str(spec_path),
    ]

    proc = run_command(cmd, cwd=tool_path)

    if proc.returncode != 0:
        return ToolResult(
            tool="proteus-ab",
            status="error",
            error=proc.stderr or proc.stdout,
        )

    return ToolResult(
        tool="proteus-ab",
        status="success",
        output_dir=spec_path.parent,
    )


def parse_antibody_results(output_dir: str | Path) -> list[dict]:
    """Parse proteus-ab ``final_designs_metrics_*.csv`` into a list of design dicts.

    Parameters
    ----------
    output_dir:
        Directory containing the ``final_designs_metrics_*.csv`` files
        produced by proteus-ab.

    Returns
    -------
    list[dict]
        Design records sorted by *ipTM* descending.  Each dict contains
        ``design_name``, ``ipTM``, ``pLDDT``, ``ca_rmsd``, and ``sequence``.
        Returns an empty list when no matching CSV files are found.
    """
    out = Path(output_dir)
    if not out.exists():
        return []

    csv_files = sorted(out.glob("final_designs_metrics_*.csv"))
    if not csv_files:
        return []

    designs: list[dict] = []
    for csv_file in csv_files:
        with open(csv_file, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                designs.append(
                    {
                        "design_name": row.get("design_name", ""),
                        "ipTM": float(row.get("ipTM", 0.0)),
                        "pLDDT": float(row.get("pLDDT", 0.0)),
                        "ca_rmsd": float(row.get("ca_rmsd", 0.0)),
                        "sequence": row.get("sequence", ""),
                    }
                )

    designs.sort(key=lambda d: d["ipTM"], reverse=True)
    return designs
