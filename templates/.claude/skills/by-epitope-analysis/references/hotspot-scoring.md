# Hotspot Scoring Reference

Quantitative rubric for ranking interface residues as candidate hotspots.
The `scripts/select_hotspots.py` implementation follows this rubric exactly —
treat this document as the spec.

---

## 1. Scoring Components

Each interface residue receives four sub-scores in `[0, 1]`; the composite is a
weighted sum. Default weights are tuned for biologics design (favoring polar
anchors slightly over raw hydrophobic packing).

| Component | Weight | What it measures |
|-----------|--------|------------------|
| Contact frequency | 0.35 | Number of heavy-atom contacts with the binder chain(s) |
| Burial / surface accessibility | 0.25 | Fraction of residue SASA buried at the interface |
| Conservation | 0.15 | Multi-species or paralog conservation (optional input) |
| Energy proxy | 0.25 | Per-residue interaction-type score (polar anchor, hydrophobic core, etc.) |

Composite: `score = 0.35 * contact + 0.25 * burial + 0.15 * conservation + 0.25 * energy_proxy`

If conservation data are absent, the conservation weight is redistributed
equally to contact and energy_proxy (each gains 0.075).

---

## 2. Contact Frequency

### Definition
Number of unique partner heavy atoms within the cutoff distance of any heavy
atom of the residue. Normalized by the residue with the maximum contact count
in the same interface so each interface is scored on its own scale.

### Cutoff strategy
Run interface analysis at two cutoffs and combine:

| Cutoff | Purpose | Weight in combined score |
|--------|---------|--------------------------|
| 4.0 A  | Direct contacts (H-bonds, salt bridges, van der Waals minima) | 0.6 |
| 5.0 A  | Extended packing (second-shell vdW) | 0.4 |

Residues present at both cutoffs receive a `dual_cutoff_bonus` of `+0.10`
(saturating at 1.0).

### Thresholds

| Contact count (raw, 5.0 A) | Interpretation |
|---------------------------|-----------------|
| 0-2 | Rim residue — exclude unless polar anchor |
| 3-5 | Peripheral contact — secondary candidate |
| 6-10 | Core contact — strong candidate |
| 11+ | Anchor residue — almost always select |

---

## 3. Burial / Surface Accessibility

### Definition
Solvent-accessible surface area (SASA) of the residue in the complex divided by
its SASA in the isolated target chain. A burial fraction of 1.0 means the
residue is fully buried by the binder; 0.0 means it is exposed to solvent in
both states (not in interface).

### Calculation
- Target SASA in isolation: SASA of the target chain alone.
- Target SASA in complex: SASA of the target chain in the full structure.
- Burial fraction: `(isolated_SASA - complex_SASA) / isolated_SASA`.

Implemented via BioPython `Bio.PDB.SASA.ShrakeRupley` with default probe radius
(1.40 A).

### Thresholds

| Burial fraction | Classification | Hotspot priority |
|-----------------|----------------|------------------|
| < 0.10 | Solvent-exposed | Drop |
| 0.10 - 0.30 | Rim | Polar anchors only |
| 0.30 - 0.60 | Partially buried | Standard candidate |
| 0.60 - 0.85 | Buried | High priority |
| > 0.85 | Fully buried | Anchor — must include |

---

## 4. Conservation

### Definition
Per-residue conservation across an MSA or known orthologs. Source options:

1. **ConSurf** scores (preferred when available) — 1-9 scale, normalized to [0, 1].
2. **UniProt feature annotations** — variants, mutagenesis records → conserved
   residues have few reported variants.
3. **Manual override** — caller can supply per-residue conservation in the
   `--conservation` JSON input.

### Thresholds

| Normalized conservation | Interpretation |
|-------------------------|----------------|
| > 0.85 | Strictly conserved — likely functional, prioritize |
| 0.60 - 0.85 | Conserved across close orthologs |
| 0.30 - 0.60 | Variable — secondary priority |
| < 0.30 | Hypervariable — usually exclude (specificity risk) |

If no conservation data are provided, this component is skipped and weights are
redistributed (see Section 1).

---

## 5. Energy Proxy (Interaction Type)

Per-residue score derived from amino acid identity + spatial context. Higher
score = higher expected per-residue binding energy contribution.

| Residue class | Examples | Base score | Bonus condition | Bonus |
|---------------|----------|------------|-----------------|-------|
| Aromatic anchor | Trp, Tyr, Phe | 0.85 | Contact with aromatic partner (pi-stacking) | +0.10 |
| Polar anchor (charged) | Arg, Lys, Asp, Glu | 0.75 | Charge-complementary partner at < 4.0 A | +0.15 |
| Polar anchor (uncharged) | Asn, Gln, His, Ser, Thr | 0.65 | H-bond donor/acceptor within 3.5 A | +0.10 |
| Hydrophobic core | Leu, Ile, Val, Met | 0.55 | Burial fraction > 0.7 | +0.10 |
| Small/flexible | Ala, Gly, Pro | 0.35 | At a turn or hinge | +0.05 |
| Cysteine | Cys | 0.60 | Disulfide bridge | +0.30 (rare) |

Saturating at 1.0.

Tyr's dual-role behavior (aromatic + H-bond donor) is captured by allowing both
aromatic and uncharged-polar bonuses simultaneously.

---

## 6. Selection Logic

After all interface residues have a composite score, select hotspots:

1. **Rank descending by composite score.**
2. **Force diversity:** at least 30% of the selection must be polar anchors
   (charged or uncharged). If the top-N by score is < 30% polar, swap in the
   highest-scoring polar anchor.
3. **Enforce contiguity:** for every selected residue, at least one other
   selected residue must be within 12 A C-alpha distance. Drop isolated
   residues; replace with the next-highest-scoring contiguous candidate.
4. **Cap the count:** see "Hotspot count by interface size" in SKILL.md.
5. **Exclude flagged residues:** glycosylation sites (N-X-S/T motif when N is
   the candidate), catalytic residues (if provided), and user `--exclude` list.

---

## 7. Spatial Contiguity

### Why it matters
Backbone-design engines (PXDesign, BoltzGen) sample protrusions/loops that
contact a contiguous patch. Isolated hotspots force the engine to either ignore
one or generate an unrealistic geometry.

### Algorithm
1. Build C-alpha distance matrix for selected residues.
2. Compute graph: edge between residues `i, j` if `d(Ca_i, Ca_j) < 12 A`.
3. Find largest connected component.
4. Drop residues outside the largest component.
5. If the largest component has fewer than the requested top-N, expand search
   radius to 15 A.

### Acceptable patch span
- Longest dimension 15-25 A (typical interface diameter)
- < 15 A: too small — accept but warn
- > 25 A: too spread — re-cluster and pick the densest sub-patch

---

## 8. Balance Between Buried and Polar

Final selection must satisfy:

| Property | Target | Hard minimum |
|----------|--------|--------------|
| Buried fraction (burial > 0.6) | 60-70% of selection | ≥ 50% |
| Polar anchors (charged or uncharged) | 30-40% of selection | ≥ 25% |
| Hydrophobic core (Leu/Ile/Val/Phe/Trp/Met) | 30-50% of selection | ≥ 1 residue |

All-hydrophobic selections produce nonspecific binders; all-polar selections
have weak binding energy. The script auto-corrects toward these ratios in
Selection Logic Step 2.

---

## 9. Contact Density Sanity Checks

After scoring, sanity-check the interface:

| Metric | Healthy range | Action if outside |
|--------|---------------|-------------------|
| Total interface residues (5.0 A) | 12-40 | < 12: widen to 6.0 A. > 40: tighten to 4.0 A. |
| Interface SASA (estimated) | 600-2000 A^2 | < 600: small binder territory. > 2000: split into sub-patches. |
| Top contact count | 8-25 | < 8: weak interface, designs may struggle. > 25: crystal-packing artifact, verify assembly. |
| Polar/hydrophobic ratio | 0.4-1.5 | < 0.4: extreme hydrophobic — review for crystal artifacts. > 1.5: review for solvent-mediated artifacts. |

---

## 10. Output Fields

The script emits these fields per residue (keep field names stable; downstream
tools depend on them):

```json
{
  "chain": "A",
  "resseq": 56,
  "resname": "TYR",
  "contact_count_4a": 8,
  "contact_count_5a": 12,
  "burial_fraction": 0.78,
  "conservation": null,
  "interaction_type": "polar_anchor_uncharged",
  "sub_scores": {"contact": 0.85, "burial": 0.78, "conservation": null, "energy_proxy": 0.75},
  "score": 0.81,
  "classification": "polar_anchor",
  "rationale": "Aromatic + H-bond donor, buried (0.78), 12 contacts at 5 A"
}
```
