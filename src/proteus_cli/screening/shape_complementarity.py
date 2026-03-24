"""Interface shape complementarity and buried surface area scoring."""
from __future__ import annotations

from pathlib import Path


def compute_interface_metrics(
    structure_path: str,
    design_chains: list[str] | None = None,
    target_chains: list[str] | None = None,
    contact_distance: float = 8.0,
) -> dict:
    """Compute interface metrics from a structure file.

    Uses BioPython's NeighborSearch for contact detection.

    Returns dict with:
        - interface_contacts: number of atom pairs within contact_distance
        - interface_residues_design: residues on design side
        - interface_residues_target: residues on target side
        - contact_density: contacts per interface residue
    """
    if design_chains is None:
        design_chains = ["A"]
    if target_chains is None:
        target_chains = ["B"]

    from Bio.PDB import MMCIFParser, NeighborSearch, PDBParser

    # Parse structure
    p = Path(structure_path)
    if p.suffix in ('.cif', '.mmcif'):
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)
    structure = parser.get_structure("complex", str(p))
    model = structure[0]

    # Get atoms by chain
    design_atoms = []
    target_atoms = []
    for chain in model:
        cid = chain.id
        atoms = list(chain.get_atoms())
        if cid in design_chains:
            design_atoms.extend(atoms)
        elif cid in target_chains:
            target_atoms.extend(atoms)

    if not design_atoms or not target_atoms:
        available_chain_ids = sorted(chain.id for chain in model)
        missing = []
        if not design_atoms:
            missing.append(f"design chains {design_chains}")
        if not target_atoms:
            missing.append(f"target chains {target_chains}")
        return {
            "error": (
                f"No atoms found for {' or '.join(missing)}. "
                f"Available chain IDs in structure: {available_chain_ids}"
            )
        }

    # Find interface contacts using NeighborSearch
    ns = NeighborSearch(target_atoms)
    interface_design_residues: set[tuple[str, int]] = set()
    interface_target_residues: set[tuple[str, int]] = set()
    contact_count = 0

    for atom in design_atoms:
        neighbors = ns.search(atom.coord, contact_distance, "A")
        if neighbors:
            contact_count += len(neighbors)
            res = atom.get_parent()
            interface_design_residues.add((res.get_parent().id, res.id[1]))
            for neighbor in neighbors:
                tres = neighbor.get_parent()
                interface_target_residues.add((tres.get_parent().id, tres.id[1]))

    total_interface_residues = len(interface_design_residues) + len(
        interface_target_residues
    )

    return {
        "interface_contacts": contact_count,
        "interface_residues_design": len(interface_design_residues),
        "interface_residues_target": len(interface_target_residues),
        "total_interface_residues": total_interface_residues,
        "contact_density": round(
            contact_count / max(total_interface_residues, 1), 1
        ),
        "design_chains": design_chains,
        "target_chains": target_chains,
    }
