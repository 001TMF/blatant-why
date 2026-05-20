# Interface Classification Reference

How to classify an epitope's surface topology and route to the right design
engine. Topology drives engine selection, expected hit rate, and hotspot
geometry.

---

## 1. Four Topology Classes

| Class | Geometry | Typical interface area | Recommended engine | Expected pass rate |
|-------|----------|-----------------------|--------------------|---------------------|
| Pocket | Concave, deep (> 8 A depth) | 500-1200 A^2 | PXDesign | 15-30% |
| Groove | Concave, elongated (linear cleft) | 800-1500 A^2 | PXDesign or BoltzGen | 10-25% |
| Flat | Planar, shallow (< 4 A depth) | 1000-2000 A^2 | BoltzGen | 5-15% |
| Linear epitope | Peptide-like, extended strand | 400-900 A^2 | BoltzGen (antibody-anything) | 10-20% |

Pass rates are rough campaign-manager priors; replace with measured rates once
the target has a baseline campaign run.

---

## 2. Detection Algorithm

### Step 1: Compute depth field
For each interface residue:
1. Find the residue's C-alpha coordinate.
2. Compute the local normal direction to the binder partner's centroid.
3. Measure depth: distance from C-alpha to the protein-side "exit plane"
   along the inward normal.

### Step 2: Compute interface plane fit
1. Fit a plane (least squares) to the interface residue C-alpha coordinates.
2. Compute the root-mean-square deviation (RMSD) of points from the plane.
3. Compute the longest principal axis length (eigenvector of covariance matrix).

### Step 3: Classify

| Decision rule | Class |
|---------------|-------|
| Mean depth > 6 A AND aspect ratio (longest / shortest axis) < 2.0 | Pocket |
| Mean depth > 4 A AND aspect ratio > 2.5 | Groove |
| Mean depth < 4 A AND plane RMSD < 2 A AND interface > 12 residues | Flat |
| Residues lie on a single extended strand (5+ consecutive sequence positions) | Linear epitope |

A target can satisfy multiple rules (e.g., a "shallow groove" — moderately
concave + elongated). Pick the more specific class; if tied, default to the
class with higher expected pass rate.

---

## 3. Implications for Design Strategy

### Pocket (concave, deep)

Why PXDesign wins:
- RFdiffusion (the diffusion backbone in PXDesign) excels at generating convex
  protrusions that complement pockets.
- Pocket walls constrain the design space — high signal-to-noise in scoring.

Hotspot placement:
- Cluster hotspots at the pocket bottom (deepest residues).
- Include 2-3 polar anchors at the rim for specificity.
- Do NOT place hotspots on the rim only — designs will protrude past the
  pocket without engaging.

Expected output character:
- Short binders (60-90 aa) with a single dominant loop or helix entering the pocket.
- Hit rate: 15-30% (after ipSAE filtering).

### Groove (concave, elongated)

Why either tool can work:
- PXDesign generates ridge-like protrusions matching the groove length.
- BoltzGen CDR-H3 loops can also span grooves; long CDR-H3 (> 18 residues)
  preferred.

Hotspot placement:
- Distribute hotspots along the groove axis (3-5 residues spaced 5-8 A apart).
- Anchor with one polar residue at each end of the groove.

Expected output character:
- PXDesign: 70-120 aa binders with an extended helix or strand.
- BoltzGen: Antibodies with elongated CDR-H3.

### Flat (planar, shallow)

Why BoltzGen wins:
- Antibody CDR loops naturally form broad contact patches.
- PXDesign struggles — diffusion generates protrusions that find no purchase
  on a flat surface.

Hotspot placement:
- Spread hotspots across the patch (6-8 residues).
- 2+ polar anchors at the patch edges for specificity.
- Include any aromatic islands (Trp, Tyr clusters) as anchor points.

Expected output character:
- Antibodies (Fab or scFv) with multi-CDR engagement (H1+H2+H3+L3 typical).
- Pass rate: 5-15% — flat interfaces are the hardest topology.

### Linear epitope (peptide-like)

Why BoltzGen antibody-anything wins:
- Designed for linear peptide engagement (single extended strand).
- CDR-H3 loops can wrap around linear epitopes from both sides.

Hotspot placement:
- All hotspots from a contiguous sequence segment (typically 6-10 residues).
- Include the central anchor residue (highest contact count) and flanking
  polar anchors.

Expected output character:
- Nanobodies or Fabs with deeply engaged CDR-H3.
- Pass rate: 10-20%.

---

## 4. Resolution Considerations

| Resolution | Trust interface contacts? | Action |
|-----------|---------------------------|--------|
| < 2.0 A | Yes — atomic detail reliable | Proceed |
| 2.0 - 2.5 A | Yes — standard for biologics design | Proceed |
| 2.5 - 3.0 A | Mostly — interface side chains usually resolved | Proceed; double-check rotamers |
| 3.0 - 3.5 A | Partial — Ca trace reliable, side chains less so | Use Ca-based metrics; verify with mutagenesis data |
| > 3.5 A | No — side-chain placement unreliable | Refold with Protenix; use predicted complex |
| Cryo-EM at any resolution | Verify local map quality | Check Q-score or local resolution per residue |

For low-resolution structures: read `references/druggability-metrics.md` — the
DoGSite-like scoring requires resolved side chains.

---

## 5. Chain Labels and Identifiers

### label_seq_id vs auth_seq_id

PDB/mmCIF files carry two residue numbering schemes:
- `label_seq_id`: continuous integer starting at 1 per chain. Used internally.
- `auth_seq_id`: the "author" numbering, often matching UniProt sequence position.
  Can have gaps, insertion codes, negative values.

Design tools differ:
- **PXDesign**: expects `label_seq_id`.
- **BoltzGen**: accepts either; check the entity YAML schema for the specific
  version.
- **`mcp__by-pdb__pdb_interface_residues`**: returns `label_seq_id` as `resseq`.

The `scripts/select_hotspots.py` script defaults to `label_seq_id`. To emit
`auth_seq_id` instead, pass `--use-auth-seq`.

### Chain ID conventions

- Author chain IDs (`A`, `H`, `L`) are what `pdb_get_chains` returns.
- Label asym IDs (`A`, `B`, `C`) are the internal mmCIF identifiers.
- For most structures they match; for some (large complexes, virus capsids)
  they differ — always verify with `pdb_get_chains`.

---

## 6. Biological Assemblies

Asymmetric units often contain multiple copies of the biological complex due
to crystallographic packing. Always work with the **biological assembly** (often
"assembly 1") rather than the asymmetric unit.

Detection:
- Multiple chains with identical sequences → likely symmetry mates.
- Interface residues on opposite faces of the target → likely crystal packing.

Action:
- Use `mcp__by-pdb__pdb_download` with `assembly=1` if available.
- If working with raw mmCIF, parse `_pdbx_struct_assembly` records.

---

## 7. Disordered Loops in Interfaces

Common in flexible epitopes:
- Sequence positions appear in the FASTA but have no coordinates in the structure.
- BioPython will skip these silently.

Action:
- Flag missing residues in the script output (`missing_residues` field).
- If a missing residue is within 8 A of the interface, consider:
  - Predicting structure with Protenix.
  - Using a different co-crystal where the loop is ordered.
  - Excluding the loop from hotspot consideration but noting it as a "design
    avoid zone".

---

## 8. Multiple Distinct Epitopes

A target with multiple binding sites (e.g., dimerization interface + receptor
interface) requires careful chain pair selection:

1. Run interface analysis for each candidate binder chain pair.
2. If the same target residues appear in multiple pairs, they may be at a
   dimerization interface — usually a poor design target.
3. Pick the chain pair matching the desired functional epitope (use
   `by-research` Phase 2 to confirm which epitope is therapeutically relevant).

---

## 9. Troubleshooting Interface Detection

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 0 contacts at 5.0 A | Wrong chain pair OR chains not in contact | Verify with `pdb_get_chains`; widen cutoff to 8 A as a sanity probe |
| > 100 contacts at 5.0 A | Crystal packing OR oversized cutoff | Tighten to 4.0 A; switch to biological assembly |
| Contacts only on one face | Asymmetric biological assembly OR crystal contact | Confirm with chain pair geometry; pick the biologically relevant copy |
| Many polar contacts, no hydrophobics | Solvent-mediated interface | Mostly H-bonds via water; check resolution and reconsider druggability |
| Sparse, scattered contacts | Weak interface OR rigid-body docking artifact | Affinity probably weak — verify with literature; consider better co-crystal |
