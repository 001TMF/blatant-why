"""Generate PyMOL and ChimeraX visualization scripts for protein design complexes."""
from __future__ import annotations

from pathlib import Path


def generate_pymol_script(
    structure_path: str,
    design_chains: list[str] | None = None,
    target_chains: list[str] | None = None,
    hotspot_residues: list[int] | None = None,
    output_path: str | None = None,
) -> str:
    """Generate a PyMOL .pml script for visualizing a design-target complex.

    Renders the target as a semi-transparent gray surface, the binder as a
    palegreen cartoon, and annotates CDR loops using approximate IMGT numbering
    (suitable for VHH / nanobody designs).

    Args:
        structure_path: Path to the PDB or mmCIF structure file to load.
        design_chains: Chain IDs for the designed binder (default ``["A"]``).
        target_chains: Chain IDs for the target protein (default ``["B"]``).
        hotspot_residues: Optional list of target residue numbers to highlight
            as red sticks (e.g. key epitope positions).
        output_path: If provided, write the script to this file path.

    Returns:
        The generated PyMOL script as a string.
    """
    if design_chains is None:
        design_chains = ["A"]
    if target_chains is None:
        target_chains = ["B"]

    lines: list[str] = [
        f"load {structure_path}",
        "",
        "# Display settings",
        "bg_color white",
        "set ray_shadow, 0",
        "",
        "# Target as surface",
    ]

    for chain in target_chains:
        lines.append(f"show surface, chain {chain}")
        lines.append(f"color gray80, chain {chain}")
        lines.append(f"set transparency, 0.3, chain {chain}")

    lines.append("")
    lines.append("# Binder as cartoon")
    for chain in design_chains:
        lines.append(f"show cartoon, chain {chain}")
        lines.append(f"color palegreen, chain {chain}")

    # CDR coloring (approximate IMGT positions for VHH)
    lines.extend([
        "",
        "# CDR loops (IMGT numbering, approximate)",
        f"color cyan, chain {design_chains[0]} and resi 26-33",
        f"color lime, chain {design_chains[0]} and resi 51-58",
        f"color magenta, chain {design_chains[0]} and resi 95-120",
        "# CDR1=cyan, CDR2=lime, CDR3=magenta",
    ])

    if hotspot_residues:
        res_sel = "+".join(str(r) for r in hotspot_residues)
        lines.extend([
            "",
            "# Hotspot residues",
            f"show sticks, chain {target_chains[0]} and resi {res_sel}",
            f"color red, chain {target_chains[0]} and resi {res_sel}",
        ])

    lines.extend([
        "",
        "# Interface view",
        "zoom",
        "orient",
        "set_view auto",
    ])

    script = "\n".join(lines)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(script)
    return script


def generate_chimerax_script(
    structure_path: str,
    design_chains: list[str] | None = None,
    target_chains: list[str] | None = None,
    hotspot_residues: list[int] | None = None,
    output_path: str | None = None,
) -> str:
    """Generate a ChimeraX .cxc script for visualizing a design-target complex.

    Renders the target as a semi-transparent gray surface, the binder as a
    green cartoon, and annotates CDR loops using approximate IMGT numbering
    (suitable for VHH / nanobody designs).

    Args:
        structure_path: Path to the PDB or mmCIF structure file to load.
        design_chains: Chain IDs for the designed binder (default ``["A"]``).
        target_chains: Chain IDs for the target protein (default ``["B"]``).
        hotspot_residues: Optional list of target residue numbers to highlight
            as red sticks (e.g. key epitope positions).
        output_path: If provided, write the script to this file path.

    Returns:
        The generated ChimeraX script as a string.
    """
    if design_chains is None:
        design_chains = ["A"]
    if target_chains is None:
        target_chains = ["B"]

    lines: list[str] = [
        f"open {structure_path}",
        "",
        "# Display settings",
        "set bgColor white",
        "lighting simple",
        "",
        "# Target as surface",
    ]

    for chain in target_chains:
        lines.append(f"surface /{chain}")
        lines.append(f"color /{chain} gray")
        lines.append(f"transparency /{chain} 30 surfaces")

    lines.append("")
    lines.append("# Binder as cartoon")
    for chain in design_chains:
        lines.append(f"cartoon /{chain}")
        lines.append(f"color /{chain} #4CAF50")
        lines.append(f"hide /{chain} atoms")

    # CDR coloring (approximate IMGT positions for VHH)
    lines.extend([
        "",
        "# CDR loops (IMGT numbering, approximate)",
        f"color /{design_chains[0]}:26-33 cyan",
        f"color /{design_chains[0]}:51-58 lime",
        f"color /{design_chains[0]}:95-120 magenta",
        "# CDR1=cyan, CDR2=lime, CDR3=magenta",
    ])

    if hotspot_residues:
        res_sel = ",".join(str(r) for r in hotspot_residues)
        lines.extend([
            "",
            "# Hotspot residues",
            f"show /{target_chains[0]}:{res_sel} atoms",
            f"style /{target_chains[0]}:{res_sel} stick",
            f"color /{target_chains[0]}:{res_sel} red",
        ])

    lines.extend([
        "",
        "# Interface view",
        "view",
    ])

    script = "\n".join(lines)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(script)
    return script
