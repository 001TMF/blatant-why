"""Select hotspot residues from a co-crystal structure for design tool input.

Purpose
-------
Given a PDB or CIF file with a target chain and one or more binder chains,
detect interface residues, score them using contact frequency + burial +
interaction type, classify the interface topology, compute druggability
metrics, and emit a ranked hotspot list with rationale.

Inputs
------
- PDB/CIF structure file (path)
- Target chain ID (string)
- Binder chain IDs (comma-separated string)
- Optional: cutoff distance, top-N count, exclude list, polar minimum
- Optional: conservation JSON {chain_id-resseq: float in [0, 1]}

Outputs
-------
- JSON file with ranked hotspots, scores, classification, druggability
  metrics, and pre-formatted strings for BoltzGen and PXDesign input.
- Console table summary.

Example
-------
    python select_hotspots.py \\
      --pdb /tmp/5JXE.cif \\
      --target-chain A \\
      --binder-chains H,L \\
      --cutoff 5.0 \\
      --top-n 6 \\
      --out /tmp/5JXE_hotspots.json

See references/hotspot-scoring.md for the scoring rubric and
references/interface-classification.md for topology rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from Bio.PDB import MMCIFParser, PDBParser, NeighborSearch
    from Bio.PDB.SASA import ShrakeRupley
    from Bio.PDB.Polypeptide import is_aa
    import numpy as np
except ImportError:
    sys.exit("Install with: pip install biopython numpy")


# -- Constants -----------------------------------------------------------------

AROMATIC = {"TRP", "TYR", "PHE"}
POLAR_CHARGED = {"ARG", "LYS", "ASP", "GLU"}
POLAR_UNCHARGED = {"ASN", "GLN", "HIS", "SER", "THR"}
HYDROPHOBIC_CORE = {"LEU", "ILE", "VAL", "MET"}
SMALL_FLEX = {"ALA", "GLY", "PRO"}

ENERGY_PROXY: dict[str, float] = {
    **{r: 0.85 for r in AROMATIC},
    **{r: 0.75 for r in POLAR_CHARGED},
    **{r: 0.65 for r in POLAR_UNCHARGED},
    **{r: 0.55 for r in HYDROPHOBIC_CORE},
    **{r: 0.35 for r in SMALL_FLEX},
    "CYS": 0.60,
}


# -- Data classes --------------------------------------------------------------


@dataclass
class ResidueScore:
    """Per-residue scoring record."""

    chain: str
    resseq: int
    resname: str
    contact_count_4a: int = 0
    contact_count_5a: int = 0
    burial_fraction: float = 0.0
    conservation: Optional[float] = None
    interaction_type: str = "other"
    sub_scores: dict[str, Optional[float]] = field(default_factory=dict)
    score: float = 0.0
    classification: str = "other"
    rationale: str = ""
    ca_coord: Optional[tuple[float, float, float]] = None


# -- Structure loading ---------------------------------------------------------


def load_structure(path: Path):
    """Parse a PDB or CIF file and return the first model."""
    if path.suffix.lower() in {".cif", ".mmcif"}:
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)
    structure = parser.get_structure(path.stem, str(path))
    return next(structure.get_models())


# -- Interface detection -------------------------------------------------------


def detect_interface(
    model,
    target_chain_id: str,
    binder_chain_ids: list[str],
    cutoff: float,
) -> dict[tuple[str, int], int]:
    """Return {(chain_id, resseq): contact_count} for target residues at cutoff."""
    try:
        target_chain = model[target_chain_id]
    except KeyError:
        sys.exit(f"Target chain '{target_chain_id}' not found in structure")

    binder_chains = []
    for bid in binder_chain_ids:
        try:
            binder_chains.append(model[bid])
        except KeyError:
            sys.exit(f"Binder chain '{bid}' not found in structure")

    binder_atoms = [a for c in binder_chains for a in c.get_atoms() if a.element != "H"]
    if not binder_atoms:
        sys.exit("No binder heavy atoms found")
    ns = NeighborSearch(binder_atoms)

    contacts: dict[tuple[str, int], int] = {}
    for residue in target_chain:
        if not is_aa(residue, standard=True):
            continue
        resseq = residue.id[1]
        n_contacts = 0
        for atom in residue:
            if atom.element == "H":
                continue
            close = ns.search(atom.coord, cutoff, level="A")
            n_contacts += len(close)
        if n_contacts > 0:
            contacts[(target_chain_id, resseq)] = n_contacts
    return contacts


# -- SASA and burial -----------------------------------------------------------


def compute_burial(
    model,
    target_chain_id: str,
    binder_chain_ids: list[str],
    interface_resseqs: set[int],
) -> dict[int, float]:
    """Compute burial fraction for each interface residue."""
    sr = ShrakeRupley()

    # Build a structure copy for the isolated target chain
    # Easiest path: compute SASA on the full complex (with binder), then compute SASA
    # on a temporary "isolated" snapshot by detaching binder chains, computing,
    # then re-attaching.
    target_chain = model[target_chain_id]

    binder_chain_objs = [model[b] for b in binder_chain_ids]

    # SASA in complex
    sr.compute(model, level="R")
    sasa_complex: dict[int, float] = {}
    for residue in target_chain:
        if not is_aa(residue, standard=True):
            continue
        resseq = residue.id[1]
        if resseq in interface_resseqs:
            sasa_complex[resseq] = float(getattr(residue, "sasa", 0.0))

    # Detach binders to compute isolated SASA on target chain
    detached_pairs = []
    for chain in binder_chain_objs:
        parent = chain.get_parent()
        detached_pairs.append((parent, chain))
        parent.detach_child(chain.id)

    sr.compute(model, level="R")
    sasa_isolated: dict[int, float] = {}
    for residue in target_chain:
        if not is_aa(residue, standard=True):
            continue
        resseq = residue.id[1]
        if resseq in interface_resseqs:
            sasa_isolated[resseq] = float(getattr(residue, "sasa", 0.0))

    # Reattach
    for parent, chain in detached_pairs:
        parent.add(chain)

    burial: dict[int, float] = {}
    for resseq in interface_resseqs:
        iso = sasa_isolated.get(resseq, 0.0)
        comp = sasa_complex.get(resseq, 0.0)
        burial[resseq] = max(0.0, (iso - comp) / iso) if iso > 0 else 0.0
    return burial


# -- Classification ------------------------------------------------------------


def classify_residue(resname: str, burial: float, contacts_5a: int) -> tuple[str, str]:
    """Return (interaction_type, classification) labels."""
    if resname in AROMATIC:
        itype = "polar_anchor_aromatic" if resname in {"TYR"} else "aromatic_anchor"
        clf = "polar_anchor" if resname == "TYR" else "hydrophobic_core"
    elif resname in POLAR_CHARGED:
        itype = "polar_anchor_charged"
        clf = "polar_anchor"
    elif resname in POLAR_UNCHARGED:
        itype = "polar_anchor_uncharged"
        clf = "polar_anchor"
    elif resname in HYDROPHOBIC_CORE:
        itype = "hydrophobic_core"
        clf = "hydrophobic_core" if burial > 0.6 else "core_packing"
    elif resname in SMALL_FLEX:
        itype = "small_flexible"
        clf = "core_packing" if burial > 0.5 else "rim"
    elif resname == "CYS":
        itype = "cysteine"
        clf = "core_packing"
    else:
        itype = "other"
        clf = "other"

    if burial > 0.85:
        clf = "buried_anchor"
    return itype, clf


# -- Scoring -------------------------------------------------------------------


def score_residue(
    rs: ResidueScore,
    max_contacts_5a: int,
    have_conservation: bool,
) -> None:
    """Compute composite score in-place."""
    contact_norm = rs.contact_count_5a / max_contacts_5a if max_contacts_5a else 0.0
    if rs.contact_count_4a > 0 and rs.contact_count_5a > 0:
        contact_norm = min(1.0, contact_norm + 0.10)
    energy = ENERGY_PROXY.get(rs.resname, 0.30)

    sub = {
        "contact": round(contact_norm, 3),
        "burial": round(rs.burial_fraction, 3),
        "conservation": round(rs.conservation, 3) if rs.conservation is not None else None,
        "energy_proxy": round(energy, 3),
    }
    if have_conservation and rs.conservation is not None:
        w_c, w_b, w_cons, w_e = 0.35, 0.25, 0.15, 0.25
        score = (
            w_c * contact_norm
            + w_b * rs.burial_fraction
            + w_cons * rs.conservation
            + w_e * energy
        )
    else:
        # Redistribute conservation weight to contact + energy
        w_c, w_b, w_e = 0.425, 0.25, 0.325
        score = w_c * contact_norm + w_b * rs.burial_fraction + w_e * energy

    rs.sub_scores = sub
    rs.score = round(min(1.0, score), 3)


# -- Topology classification ---------------------------------------------------


def classify_topology(coords: list[tuple[float, float, float]]) -> tuple[str, dict]:
    """Classify the interface topology from C-alpha coordinates."""
    if len(coords) < 4:
        return "linear", {"n_residues": len(coords)}
    arr = np.array(coords)
    centroid = arr.mean(axis=0)
    centered = arr - centroid
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # eigvals sorted ascending
    span_long = float(np.sqrt(eigvals[-1]) * 4.0)  # rough patch length
    span_short = float(np.sqrt(eigvals[0]) * 4.0)
    aspect_ratio = span_long / span_short if span_short > 0 else 1.0

    # Plane fit using smallest eigenvector as normal
    normal = eigvecs[:, 0]
    plane_rmsd = float(np.sqrt(np.mean((centered @ normal) ** 2)))

    # Mean "depth" approximated by RMSD perpendicular to plane
    depth = plane_rmsd * 2.0

    metrics = {
        "n_residues": len(coords),
        "patch_long_a": round(span_long, 2),
        "patch_short_a": round(span_short, 2),
        "aspect_ratio": round(aspect_ratio, 2),
        "plane_rmsd_a": round(plane_rmsd, 2),
        "mean_depth_a": round(depth, 2),
    }

    if depth > 6.0 and aspect_ratio < 2.0:
        return "pocket", metrics
    if depth > 4.0 and aspect_ratio > 2.5:
        return "groove", metrics
    if depth < 4.0 and plane_rmsd < 2.0 and len(coords) > 12:
        return "flat", metrics
    if aspect_ratio > 3.0 and len(coords) < 10:
        return "linear", metrics
    return "flat", metrics


# -- Druggability metrics ------------------------------------------------------


def compute_druggability(
    residue_scores: list[ResidueScore],
    topology_metrics: dict,
) -> dict:
    """Compute DoGSite-like composite druggability metrics."""
    if not residue_scores:
        return {"composite_score": 0.0, "classification": "untargetable"}
    n_residues = len(residue_scores)
    # SASA proxy: residue count x average per-residue area
    interface_sasa = n_residues * 50.0  # 40-60 A^2 typical per residue
    polar_count = sum(
        1 for r in residue_scores
        if r.resname in POLAR_CHARGED | POLAR_UNCHARGED | {"TYR"}
    )
    aromatic_count = sum(1 for r in residue_scores if r.resname in AROMATIC)
    hydrophobic_count = sum(
        1 for r in residue_scores if r.resname in HYDROPHOBIC_CORE
    )
    total = max(1, polar_count + hydrophobic_count + aromatic_count)
    hydrophobicity_ratio = (hydrophobic_count + aromatic_count) / total

    depth = topology_metrics.get("mean_depth_a", 3.0)
    enclosure = min(1.0, depth / 8.0)  # rough proxy

    normalized_volume = min(1.0, (interface_sasa * 0.8) / 1500.0)
    normalized_surface = min(1.0, interface_sasa / 1500.0)
    normalized_depth = min(1.0, depth / 8.0)
    normalized_polar = min(1.0, polar_count / 6.0)
    normalized_aromatic = min(1.0, aromatic_count / 3.0)

    balance = 1.0 - abs(hydrophobicity_ratio - 0.5) * 2.0
    balance = max(0.0, balance)

    composite = (
        0.20 * normalized_volume
        + 0.15 * normalized_surface
        + 0.10 * normalized_depth
        + 0.15 * enclosure
        + 0.15 * balance
        + 0.15 * normalized_polar
        + 0.10 * normalized_aromatic
    )
    composite = round(composite, 3)

    if composite > 0.70:
        clf = "excellent"
    elif composite > 0.50:
        clf = "strong"
    elif composite > 0.30:
        clf = "moderate"
    elif composite > 0.10:
        clf = "marginal"
    else:
        clf = "untargetable"

    warnings: list[str] = []
    if polar_count == 0:
        warnings.append("No polar anchors in interface — specificity risk")
    if aromatic_count == 0:
        warnings.append("No aromatic residues — limited pi-stacking opportunities")
    if hydrophobicity_ratio > 0.85:
        warnings.append("All-hydrophobic interface — nonspecific binding risk")
    if interface_sasa < 500:
        warnings.append("Small interface (< 500 A^2) — nanobody territory only")

    return {
        "interface_sasa_a2": round(interface_sasa, 1),
        "mean_depth_a": depth,
        "enclosure_fraction": round(enclosure, 3),
        "hydrophobicity_ratio": round(hydrophobicity_ratio, 3),
        "polar_count": polar_count,
        "aromatic_count": aromatic_count,
        "composite_score": composite,
        "classification": clf,
        "warnings": warnings,
    }


# -- Selection -----------------------------------------------------------------


def select_hotspots(
    scored: list[ResidueScore],
    top_n: int,
    polar_min_fraction: float = 0.30,
    contiguity_cutoff: float = 12.0,
) -> list[ResidueScore]:
    """Pick top-N hotspots enforcing diversity and contiguity."""
    if not scored:
        return []

    # Rank descending by score
    ranked = sorted(scored, key=lambda r: r.score, reverse=True)
    chosen: list[ResidueScore] = ranked[:top_n]

    # Diversity enforcement: at least polar_min_fraction polar anchors
    target_polar = max(1, int(round(polar_min_fraction * top_n)))
    n_polar = sum(1 for r in chosen if r.classification == "polar_anchor")
    if n_polar < target_polar:
        polars_remaining = [
            r for r in ranked if r.classification == "polar_anchor" and r not in chosen
        ]
        # Swap weakest non-polar for highest-scoring polar
        for polar in polars_remaining:
            if n_polar >= target_polar:
                break
            non_polar = [r for r in chosen if r.classification != "polar_anchor"]
            if not non_polar:
                break
            weakest = min(non_polar, key=lambda r: r.score)
            chosen.remove(weakest)
            chosen.append(polar)
            n_polar += 1

    # Contiguity: drop isolated residues, replace with next ranked contiguous
    chosen = enforce_contiguity(chosen, ranked, contiguity_cutoff)
    chosen.sort(key=lambda r: r.score, reverse=True)
    return chosen


def enforce_contiguity(
    chosen: list[ResidueScore],
    candidates: list[ResidueScore],
    cutoff: float,
) -> list[ResidueScore]:
    """Drop hotspots with no neighbor within cutoff; replace with contiguous alternatives."""
    if len(chosen) < 2:
        return chosen

    def dist(a: ResidueScore, b: ResidueScore) -> float:
        if a.ca_coord is None or b.ca_coord is None:
            return 999.0
        ax, ay, az = a.ca_coord
        bx, by, bz = b.ca_coord
        return ((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2) ** 0.5

    final = list(chosen)
    changed = True
    iters = 0
    while changed and iters < 10:
        changed = False
        iters += 1
        for r in list(final):
            others = [o for o in final if o is not r]
            if not others:
                continue
            nearest = min(dist(r, o) for o in others)
            if nearest > cutoff:
                # Find a replacement that is contiguous with the remaining set
                final.remove(r)
                for cand in candidates:
                    if cand in final:
                        continue
                    if any(dist(cand, o) <= cutoff for o in final):
                        final.append(cand)
                        changed = True
                        break
                else:
                    # No replacement found — leave the slot empty
                    pass
    return final


# -- Output formatting ---------------------------------------------------------


def format_outputs(
    chosen: list[ResidueScore],
    target_chain: str,
) -> tuple[str, str, list[int]]:
    """Return (range_notation, boltzgen_binding, pxdesign_hotspots)."""
    seqs = sorted(r.resseq for r in chosen)
    range_notation = ",".join(f"{target_chain}{s}" for s in seqs)
    boltzgen_binding = ",".join(str(s) for s in seqs)
    pxdesign_hotspots = list(seqs)
    return range_notation, boltzgen_binding, pxdesign_hotspots


def rationale_for(rs: ResidueScore) -> str:
    parts: list[str] = []
    if rs.resname in AROMATIC:
        parts.append("aromatic")
    if rs.resname in POLAR_CHARGED:
        parts.append("charged")
    if rs.resname in POLAR_UNCHARGED or rs.resname == "TYR":
        parts.append("H-bond")
    if rs.resname in HYDROPHOBIC_CORE:
        parts.append("hydrophobic core")
    if rs.burial_fraction > 0.6:
        parts.append(f"buried ({rs.burial_fraction:.2f})")
    parts.append(f"{rs.contact_count_5a} contacts at 5 A")
    return ", ".join(parts)


# -- CLI -----------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Select hotspot residues from a co-crystal structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--pdb", required=True, type=Path, help="Path to PDB or CIF file")
    p.add_argument("--target-chain", required=True, help="Target (antigen) chain ID")
    p.add_argument(
        "--binder-chains",
        required=True,
        help="Comma-separated binder chain IDs (e.g., H,L for Fab; H for VHH)",
    )
    p.add_argument(
        "--cutoff", type=float, default=5.0, help="Interface distance cutoff in A (default 5.0)"
    )
    p.add_argument(
        "--top-n", type=int, default=6, help="Number of hotspots to select (default 6)"
    )
    p.add_argument(
        "--exclude",
        default="",
        help="Comma-separated residue seq numbers to exclude from hotspot selection",
    )
    p.add_argument(
        "--polar-min", type=int, default=None, help="Hard minimum polar anchors in selection"
    )
    p.add_argument(
        "--conservation",
        type=Path,
        default=None,
        help="Optional JSON {chain-resseq: float in [0,1]} of conservation scores",
    )
    p.add_argument("--out", required=True, type=Path, help="Output JSON path")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.pdb.exists():
        sys.exit(f"PDB file not found: {args.pdb}")
    model = load_structure(args.pdb)
    print(f"✓ Loaded structure {args.pdb.stem}")

    binder_chain_ids = [c.strip() for c in args.binder_chains.split(",") if c.strip()]
    exclude = set()
    if args.exclude:
        for tok in args.exclude.split(","):
            tok = tok.strip()
            if tok.isdigit():
                exclude.add(int(tok))
            elif len(tok) >= 2 and tok[1:].isdigit():
                exclude.add(int(tok[1:]))

    conservation: dict[str, float] = {}
    have_conservation = False
    if args.conservation and args.conservation.exists():
        conservation = json.loads(args.conservation.read_text())
        have_conservation = True

    # Interface detection at both cutoffs
    contacts_5a = detect_interface(model, args.target_chain, binder_chain_ids, args.cutoff)
    contacts_4a = detect_interface(model, args.target_chain, binder_chain_ids, 4.0)
    print(f"✓ Interface residues detected: {len(contacts_5a)} (cutoff {args.cutoff} A)")

    if not contacts_5a:
        sys.exit("No interface residues found — check chain assignments and cutoff")

    interface_resseqs = {rs for (_c, rs) in contacts_5a.keys()}
    burial = compute_burial(model, args.target_chain, binder_chain_ids, interface_resseqs)

    target_chain_obj = model[args.target_chain]
    scored: list[ResidueScore] = []
    for residue in target_chain_obj:
        if not is_aa(residue, standard=True):
            continue
        resseq = residue.id[1]
        if resseq not in interface_resseqs:
            continue
        if resseq in exclude:
            continue
        resname = residue.get_resname()
        c5 = contacts_5a.get((args.target_chain, resseq), 0)
        c4 = contacts_4a.get((args.target_chain, resseq), 0)
        b = burial.get(resseq, 0.0)
        itype, clf = classify_residue(resname, b, c5)
        ca = residue["CA"].coord if "CA" in residue else None
        rs = ResidueScore(
            chain=args.target_chain,
            resseq=resseq,
            resname=resname,
            contact_count_4a=c4,
            contact_count_5a=c5,
            burial_fraction=b,
            conservation=conservation.get(f"{args.target_chain}-{resseq}"),
            interaction_type=itype,
            classification=clf,
            ca_coord=tuple(float(x) for x in ca) if ca is not None else None,
        )
        scored.append(rs)

    if not scored:
        sys.exit("All interface residues excluded; nothing to score")

    max_c5 = max(r.contact_count_5a for r in scored) or 1
    for rs in scored:
        score_residue(rs, max_c5, have_conservation)
        rs.rationale = rationale_for(rs)

    # Topology
    coords = [r.ca_coord for r in scored if r.ca_coord is not None]
    topology, topology_metrics = classify_topology(coords)
    druggability = compute_druggability(scored, topology_metrics)

    # Selection
    polar_min_fraction = (
        args.polar_min / args.top_n if args.polar_min is not None else 0.30
    )
    chosen = select_hotspots(scored, top_n=args.top_n, polar_min_fraction=polar_min_fraction)
    print(f"✓ Ranked {len(scored)} candidates; selected {len(chosen)} hotspots")

    range_notation, boltzgen_binding, pxdesign_hotspots = format_outputs(
        chosen, args.target_chain
    )

    # Build output JSON
    out_doc = {
        "pdb_file": str(args.pdb),
        "pdb_id": args.pdb.stem,
        "target_chain": args.target_chain,
        "binder_chains": binder_chain_ids,
        "cutoff_a": args.cutoff,
        "interface_residues_n": len(scored),
        "topology": topology,
        "topology_metrics": topology_metrics,
        "druggability_metrics": druggability,
        "hotspots": [
            {
                "chain": r.chain,
                "resseq": r.resseq,
                "resname": r.resname,
                "contact_count_4a": r.contact_count_4a,
                "contact_count_5a": r.contact_count_5a,
                "burial_fraction": round(r.burial_fraction, 3),
                "conservation": r.conservation,
                "interaction_type": r.interaction_type,
                "sub_scores": r.sub_scores,
                "score": r.score,
                "classification": r.classification,
                "rationale": r.rationale,
            }
            for r in chosen
        ],
        "all_candidates": [
            {
                "chain": r.chain,
                "resseq": r.resseq,
                "resname": r.resname,
                "score": r.score,
                "classification": r.classification,
            }
            for r in sorted(scored, key=lambda r: r.score, reverse=True)
        ],
        "range_notation": range_notation,
        "boltzgen_binding": boltzgen_binding,
        "pxdesign_hotspots": pxdesign_hotspots,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_doc, indent=2))
    print(f"✓ Wrote {args.out}")

    # Console summary
    print()
    print(f"  Topology: {topology}  (depth {topology_metrics.get('mean_depth_a', 0)} A, "
          f"aspect {topology_metrics.get('aspect_ratio', 0)})")
    print(f"  Druggability: {druggability['classification']} "
          f"(score {druggability['composite_score']})")
    print()
    print(f"  {'Residue':<12} {'Score':<7} {'Class':<18} Rationale")
    print(f"  {'-'*12} {'-'*7} {'-'*18} {'-'*40}")
    for r in chosen:
        tag = f"{r.chain}{r.resseq} {r.resname}"
        print(f"  {tag:<12} {r.score:<7} {r.classification:<18} {r.rationale}")
    print()
    print(f"  BoltzGen binding: {boltzgen_binding}")
    print(f"  PXDesign hotspots: {pxdesign_hotspots}")


if __name__ == "__main__":
    main()
