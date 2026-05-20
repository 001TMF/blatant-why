# Druggability Metrics for Biologics Epitopes

When to consider an epitope druggable by a biologic (antibody, nanobody, or de
novo protein binder). Adapted from small-molecule druggability scorers
(DoGSiteScorer, FPocket) with biologics-specific thresholds.

---

## 1. Why Druggability Matters for Biologics

Small-molecule druggability assumes a deep enclosed pocket. Biologics are larger
and can engage flat, exposed, or extended epitopes — so the small-molecule
"druggable" thresholds are too strict. We use:

- **Small-molecule druggable** (DoGSite score > 0.6): also great for biologics.
- **Biologics-druggable** (DoGSite score 0.3-0.6): typical antibody territory.
- **Biologics-marginal** (score 0.1-0.3): possible but lower pass rate.
- **Biologics-untargetable** (score < 0.1): extremely flat or solvent-exposed
  region — consider a different epitope on the same protein.

---

## 2. DoGSiteScorer-Style Metrics

DoGSiteScorer is the reference small-molecule druggability tool. We compute a
similar set of metrics scaled for biologics interfaces.

### Core metrics

| Metric | Description | Biologics-acceptable range |
|--------|-------------|----------------------------|
| Volume (A^3) | Enclosed cavity volume | > 200 A^3 (lower for flat epitopes) |
| Surface area (A^2) | Solvent-accessible surface of cavity | 400-2000 A^2 |
| Depth (A) | Distance from pocket mouth to bottom | > 2 A (small-molecule needs > 6 A) |
| Enclosure | Fraction of cavity walls that are protein vs solvent | > 0.40 (small-molecule needs > 0.65) |
| Hydrophobicity ratio | Hydrophobic surface / total cavity surface | 0.30-0.70 (balanced) |
| H-bond donors/acceptors | Count of polar atoms in cavity | ≥ 3 for specificity |
| Aromaticity | Aromatic atoms in cavity | ≥ 2 preferred (pi-stacking anchors) |

### DoGSite-like composite score (biologics-scaled)

```
score = 0.20 * normalized_volume
      + 0.15 * normalized_surface
      + 0.10 * normalized_depth
      + 0.15 * enclosure
      + 0.15 * (1 - |hydrophobicity_ratio - 0.5| * 2)
      + 0.15 * normalized_polar_count
      + 0.10 * normalized_aromatic_count
```

All `normalized_*` values map to [0, 1] using empirical population-based
percentile cutoffs from the SAbDab interface dataset.

### Interpretation

| Composite score | Biologics druggability |
|-----------------|------------------------|
| > 0.70 | Excellent — pocket-like, biologics + small-molecule druggable |
| 0.50 - 0.70 | Strong — typical antibody epitope, good campaign target |
| 0.30 - 0.50 | Moderate — flat/groove epitope, requires careful design |
| 0.10 - 0.30 | Marginal — only attempt with extensive prior art |
| < 0.10 | Untargetable — consider different epitope or different modality |

---

## 3. FPocket-Style Pocket Detection

FPocket uses alpha-sphere geometry to detect cavities. We adapt the
biologics-relevant outputs:

### FPocket metrics

| Metric | What it measures | Biologics target |
|--------|------------------|------------------|
| Number of alpha spheres | Cavity packing density | > 15 for a "real" pocket |
| Mean alpha-sphere radius (A) | Cavity tightness | 3-5 A (tight); > 5 A means open groove |
| Polar/apolar alpha-sphere ratio | Cavity chemistry | 0.3-1.0 |
| Drug score (FPocket internal) | Composite ML score | > 0.5 small-molecule druggable; > 0.3 biologics-druggable |
| Hydrophobic pocket density | Hydrophobic Ca count / total Ca | 0.3-0.6 |

### When to run FPocket vs DoGSiteScorer

| Use case | Tool |
|----------|------|
| Quick pocket detection on a new structure | FPocket (faster, simpler) |
| Detailed druggability scoring with pharmacophore | DoGSiteScorer |
| Ranking multiple pockets on the same protein | Either; FPocket has cleaner ranking |
| Computing the chemistry of a known interface | DoGSiteScorer |

For BY workflows, we primarily compute these scores on the *interface* (not
arbitrary pockets) — see Section 5.

---

## 4. Biologics-Specific Adjustments

Standard druggability tools target small molecules. We adjust:

### Depth tolerance

Small molecules need depth > 6 A. Antibody CDR loops (especially CDR-H3, often
15-20 A long) can engage shallow features. We lower the depth threshold to
2-4 A and weight depth at 0.10 instead of DoGSite's 0.20.

### Enclosure tolerance

Small molecules need > 65% enclosure (cavity walls). Biologics CDRs can engage
30-50% enclosed epitopes by wrapping convex surfaces. We lower the enclosure
threshold and weight at 0.15.

### Hydrophobic balance

Small molecules tolerate hydrophobic pockets (ligand H-bond donors are limited
by molecular weight). Biologics need ~30-70% polar content for specificity —
all-hydrophobic patches lead to nonspecific binding.

### Volume tolerance

Small-molecule cavities need > 250 A^3 to fit a drug-like molecule. Biologics
engage surfaces, not cavities — we count "engaged volume" (volume within 8 A
of any interface residue) instead. Engaged volume > 800 A^3 is the
biologics-druggable threshold.

---

## 5. Computing Metrics on an Existing Interface

For BY workflows, the "epitope" is defined by the binder chain. We don't search
for pockets — we score the interface as-is.

### Procedure

1. Identify interface residues (use `mcp__by-pdb__pdb_interface_residues`).
2. Compute interface SASA (BioPython ShrakeRupley).
3. Compute mean depth: average distance of interface residue C-alpha to the
   convex hull of the target chain surface.
4. Compute enclosure: fraction of interface SASA facing the binder vs solvent.
5. Compute polar/apolar ratio: weighted by residue type.
6. Compose with the DoGSite-like formula (Section 2).

### Implementation note
The `scripts/select_hotspots.py` script reports these metrics in the output
JSON under `druggability_metrics`. Use these alongside the hotspot scores —
high hotspot scores on a low-druggability epitope mean the binder will struggle
even with perfect hotspot selection.

---

## 6. When an Epitope is "Druggable" for Biologics

Apply this checklist before launching a campaign:

- [ ] Composite druggability score > 0.30
- [ ] At least one polar anchor (Tyr, Arg, Asp, Glu, Asn, Gln, His) in interface
- [ ] At least one aromatic residue (Trp, Tyr, Phe) for pi-stacking
- [ ] Interface area > 500 A^2 (smaller = nanobody only, > 1500 = consider Fab)
- [ ] Resolution adequate (< 3.0 A preferred)
- [ ] Not buried inside the protein (interface SASA fraction > 0.10)
- [ ] No essential glycosylation site within the interface (N-X-S/T motif)
- [ ] No high mobility / disordered loops covering > 30% of interface

If 6+ checks pass: druggable, proceed.
If 4-5: marginal, document risks in design recommendation.
If < 4: not druggable, return to research for an alternative epitope.

---

## 7. Glycans and Post-Translational Modifications

### N-linked glycosylation

Sequence motif: N-X-S/T (X ≠ P). When the asparagine is in the interface:

- Most design engines do not model glycans → the design may collide with the
  glycan when expressed.
- BoltzGen handles some glycan-aware design via specific protocols.
- PXDesign does not model glycans.

Action:
- Exclude glycosylated Asn from hotspots (`--exclude` in script).
- If glycan is structurally essential to the epitope, route to BoltzGen with
  a glycan-aware protocol; document the constraint.

### O-linked glycosylation

Less common in design targets. Excluded automatically if the structure shows
attached carbohydrate density near the residue.

### Other PTMs

Phosphorylation, sulfation, methylation: not modeled by standard design
engines. Exclude the modified residue from hotspots unless using a custom
parameterization.

---

## 8. Reporting Druggability

The hotspot JSON should include a `druggability_metrics` block:

```json
{
  "druggability_metrics": {
    "interface_sasa_a2": 1080.0,
    "mean_depth_a": 3.2,
    "enclosure_fraction": 0.42,
    "hydrophobicity_ratio": 0.55,
    "polar_count": 6,
    "aromatic_count": 3,
    "composite_score": 0.58,
    "classification": "strong",
    "warnings": []
  }
}
```

Use the `classification` field to decide whether to proceed, proceed with
caveats, or escalate back to research.

---

## 9. Citations

- [Volkamer et al. 2012](https://doi.org/10.1093/bioinformatics/bts310) —
  DoGSiteScorer: a web server for automatic binding-site prediction, analysis,
  and druggability assessment.
- [Le Guilloux et al. 2009](https://doi.org/10.1186/1471-2105-10-168) —
  FPocket: open source platform for ligand pocket detection.
- [Cheng et al. 2007](https://doi.org/10.1038/nbt1284) — Structure-based maximal
  affinity model predicts small-molecule druggability.
- [Hopkins & Groom 2002](https://doi.org/10.1038/nrd892) — The druggable genome
  (basis for druggability concept).
