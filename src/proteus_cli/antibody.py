"""Wrapper for boltzgen (BoltzGen antibody/nanobody design)."""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from proteus_cli.common import ToolResult, get_tool_env, run_command, validate_tool_path


PROTOCOLS: dict[str, str] = {
    "nanobody-anything": "nanobody-anything",
    "antibody-anything": "antibody-anything",
}


def _residues_to_ranges(residues: list[int]) -> str:
    """Convert a sorted list of residue indices into ``..`` range notation.

    Examples
    --------
    >>> _residues_to_ranges([7, 8, 9, 10, 11, 12, 27, 28, 29, 30, 31, 32, 33, 34])
    '7..12,27..34'
    """
    if not residues:
        return ""
    residues = sorted(residues)
    ranges: list[str] = []
    start = residues[0]
    end = residues[0]
    for r in residues[1:]:
        if r == end + 1:
            end = r
        else:
            ranges.append(f"{start}..{end}" if end > start else str(start))
            start = end = r
    ranges.append(f"{start}..{end}" if end > start else str(start))
    return ",".join(ranges)


def build_design_spec(
    target_pdb: str | Path,
    target_chains: list[str],
    binding_residues: dict[str, list[int]] | None = None,
    scaffold_paths: list[str] | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    """Create a YAML design spec file for boltzgen and return its path.

    The spec follows the ``entities`` list format expected by
    ``boltzgen run <spec.yaml>``.

    Parameters
    ----------
    target_pdb:
        Path to the target structure file (CIF or PDB).
    target_chains:
        Chain identifiers on the target to include (e.g. ``["A"]``).
    binding_residues:
        Per-chain binding residue indices, e.g. ``{"A": [7,8,9,10,11,12,27,28,29,30,31,32,33,34]}``.
        These are converted to ``..`` range notation in the spec.
    scaffold_paths:
        List of scaffold YAML template paths.  If ``None``, a default
        adalimumab scaffold is used.
    output_dir:
        Directory for outputs.  Defaults to the parent directory of *target_pdb*.

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

    # Build the target entity
    include_list = []
    binding_types_list = []
    for chain in target_chains:
        include_list.append({"chain": {"id": chain}})
        if binding_residues and chain in binding_residues:
            binding_str = _residues_to_ranges(binding_residues[chain])
            binding_types_list.append(
                {"chain": {"id": chain, "binding": binding_str}}
            )

    target_entity: dict = {
        "file": {
            "path": str(target_pdb),
            "include": include_list,
        },
    }
    if binding_types_list:
        target_entity["file"]["binding_types"] = binding_types_list

    entities: list[dict] = [target_entity]

    # Add scaffold entity if scaffold paths are provided
    if scaffold_paths:
        scaffold_entity: dict = {
            "file": {
                "path": scaffold_paths if len(scaffold_paths) > 1 else scaffold_paths[0],
            },
        }
        entities.append(scaffold_entity)

    spec: dict = {"entities": entities}

    spec_path = output_dir / "design_spec.yaml"
    with open(spec_path, "w") as fh:
        yaml.dump(spec, fh, default_flow_style=False, sort_keys=False)

    return spec_path


def run_antibody_design(
    spec_path: str | Path,
    protocol: str = "nanobody-anything",
    num_designs: int = 50,
    output_dir: str | Path | None = None,
    msa_mode: str = "none",
    prefilter: bool = False,
    budget: int = 10,
) -> ToolResult:
    """Run ``boltzgen run`` for antibody/nanobody design.

    Parameters
    ----------
    spec_path:
        Path to the YAML spec file produced by :func:`build_design_spec`.
    protocol:
        Design protocol (``"nanobody-anything"`` or ``"antibody-anything"``).
    num_designs:
        Number of designs to generate.
    output_dir:
        Optional override for the output directory.
    msa_mode:
        MSA generation mode (``"none"``, ``"mmseqs2"``).
    prefilter:
        Whether to enable prefiltering of designs.
    budget:
        Computational budget for the design run.

    Returns
    -------
    ToolResult
        Standardized result with status ``"success"`` or ``"error"``.
    """
    tool_path = validate_tool_path("boltzgen")
    spec_path = Path(spec_path)

    cmd: list[str] = [
        "boltzgen", "run",
        str(spec_path),
        "--protocol", protocol,
        "--num_designs", str(num_designs),
        "--msa-mode", msa_mode,
        "--budget", str(budget),
    ]
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--output", str(out)])
    if prefilter:
        cmd.append("--prefilter")

    env = get_tool_env("boltzgen")
    proc = run_command(cmd, cwd=tool_path, env=env)

    if proc.returncode != 0:
        return ToolResult(
            tool="boltzgen",
            status="error",
            error=proc.stderr or proc.stdout,
        )

    resolved_output = Path(output_dir) if output_dir else spec_path.parent
    return ToolResult(
        tool="boltzgen",
        status="success",
        output_dir=resolved_output,
    )


def parse_antibody_results(output_dir: str | Path) -> list[dict]:
    """Parse boltzgen ``final_designs_metrics_*.csv`` into a list of design dicts.

    BoltzGen writes results to
    ``<output_dir>/final_ranked_designs/final_designs_metrics_*.csv``.

    Parameters
    ----------
    output_dir:
        Root output directory of a boltzgen run.

    Returns
    -------
    list[dict]
        Design records sorted by *iptm* descending.  Each dict contains
        ``design_id``, ``iptm``, ``ptm``, ``plddt``, ``design_iptm``,
        ``ipsae_min``, ``rmsd``, and ``sequence``.
        Returns an empty list when no matching CSV files are found.
    """
    out = Path(output_dir)
    if not out.exists():
        return []

    # Look in the expected final_ranked_designs/ subdirectory first
    ranked_dir = out / "final_ranked_designs"
    if ranked_dir.exists():
        csv_files = sorted(ranked_dir.glob("final_designs_metrics_*.csv"))
    else:
        csv_files = []

    # Fallback: search recursively
    if not csv_files:
        csv_files = sorted(out.rglob("final_designs_metrics_*.csv"))
    if not csv_files:
        return []

    key_columns = [
        "design_id", "iptm", "ptm", "plddt",
        "design_iptm", "ipsae_min", "rmsd", "sequence",
    ]
    float_columns = {"iptm", "ptm", "plddt", "design_iptm", "ipsae_min", "rmsd"}

    designs: list[dict] = []
    for csv_file in csv_files:
        with open(csv_file, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                entry: dict = {}
                for col in key_columns:
                    val = row.get(col, "")
                    if col in float_columns:
                        try:
                            entry[col] = float(val)
                        except (ValueError, TypeError):
                            entry[col] = val
                    else:
                        entry[col] = val
                designs.append(entry)

    designs.sort(key=lambda d: float(d.get("iptm", 0.0) or 0.0), reverse=True)
    return designs


def convert_fab_to_scfv(vh_sequence: str, vl_sequence: str, linker: str = "GGGGSGGGGSGGGGS") -> str:
    """Convert Fab VH + VL chains to single-chain scFv format.

    BoltzGen designs with Fab templates produce separate VH and VL chains.
    This function joins them into a single scFv: VH-linker-VL.

    Args:
        vh_sequence: Variable heavy chain sequence.
        vl_sequence: Variable light chain sequence.
        linker: Flexible peptide linker (default: (G4S)3).

    Returns:
        Single-chain scFv sequence: VH + linker + VL.

    Raises:
        ValueError: If either sequence is empty or contains non-standard amino acids.
    """
    VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")

    if not vh_sequence.strip():
        raise ValueError("VH sequence must not be empty")
    if not vl_sequence.strip():
        raise ValueError("VL sequence must not be empty")

    vh = vh_sequence.strip().upper()
    vl = vl_sequence.strip().upper()

    invalid_vh = set(vh) - VALID_AA
    if invalid_vh:
        raise ValueError(f"Invalid amino acids in VH: {invalid_vh}")
    invalid_vl = set(vl) - VALID_AA
    if invalid_vl:
        raise ValueError(f"Invalid amino acids in VL: {invalid_vl}")

    return vh + linker + vl
