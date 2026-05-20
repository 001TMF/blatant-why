# Thresholds by Modality

ipSAE, ipTM, pLDDT, and RMSD targets shift with modality. A nanobody at ipSAE 0.65 is
a strong candidate; a de novo binder at the same number is borderline. This document
records the per-modality cutoffs BY uses for screening verdicts.

---

## Quick Reference Table

| Modality | ipSAE poor | ipSAE good | ipSAE excellent | Typical ipTM range | pLDDT floor | CA-RMSD ceiling |
|----------|-----------|------------|-----------------|---------------------|-------------|-----------------|
| Antibody (Fab / scFv) | `< 0.40` | `0.60 - 0.75` | `>= 0.75` | `0.60 - 0.85` | `> 70` | `< 3.5 A` |
| Nanobody (VHH) | `< 0.35` | `0.55 - 0.70` | `>= 0.70` | `0.55 - 0.85` | `> 70` | `< 3.0 A` |
| De novo binder | `< 0.50` | `0.70 - 0.85` | `>= 0.85` | `0.70 - 0.90` | `> 75` | `< 2.5 A` |
| Bispecific antibody | `< 0.40` | `0.55 - 0.70` | `>= 0.70` | `0.55 - 0.80` | `> 70` | `< 4.0 A` |
| Cyclic peptide | `< 0.45` | `0.60 - 0.75` | `>= 0.75` | `0.55 - 0.80` | `> 65` | `< 2.5 A` |

These thresholds match the `scoring.ipSAE.thresholds` block in `plugin-manifest.json`
(`poor: 0.2, good: 0.5, excellent: 0.8`) as the **universal default**, but they are
tightened or relaxed per-modality based on empirical hit-rate data.

---

## Modality Rationale

### Antibody (Fab / scFv)

- **Why ipSAE excellent at 0.75, not 0.85**: Fab interfaces engage 25-40 residues through 6 CDR loops. The size of the interface lets d0 escape its floor, but CDR-H3 flexibility caps the achievable ipSAE around 0.85 in practice. Excellence at >= 0.75 is realistic.
- **Why ipTM range starts at 0.60**: scFv linkers create disorder that depresses ipTM independently of binding quality.
- **CA-RMSD ceiling 3.5 A**: Allows for CDR loop conformational diversity between predicted and refolded models without penalizing valid designs.

### Nanobody (VHH)

- **Why ipSAE poor floor lower (0.35)**: VHH CDR-H3 loops are longer and more flexible than antibody CDR-H3s. Sampling noise in Protenix pushes the median ipSAE down ~0.05 relative to Fab.
- **Why excellence at 0.70**: Validated against 200+ VHH co-crystal refolds — the top decile clustered at 0.68 - 0.78, with very few exceeding 0.80.
- **Minimum 20 seeds recommended** for stable scoring (see `by-screening` skill for multi-seed details).

### De novo binder (PXDesign)

- **Why ipSAE excellent at 0.85**: De novo binders are designed to be compact and rigid — they should score higher than antibodies. If a de novo binder cannot reach 0.85 in refolding, it is probably not a productive interaction.
- **Why higher pLDDT floor (75)**: Designed scaffolds have no immune-system origin and must rely entirely on structural confidence for credibility.
- **CA-RMSD ceiling 2.5 A**: Rigid scaffolds should refold to near-identical structures; high RMSD indicates design failure.

### Bispecific antibody

- **Why ipTM range pulled down**: Two paratopes engaging two epitopes increases conformational complexity. ipTM is harder to push high.
- **Why CA-RMSD ceiling raised to 4.0 A**: Linker / hinge regions between paratopes are intrinsically flexible.

### Cyclic peptide

- **Why pLDDT floor lower (65)**: Backbone cyclization is well-modeled by Protenix but the absolute pLDDT scale runs slightly lower for short chains.
- **Why ipSAE excellent at 0.75**: Small interfaces (10-20 residues) have small n0, which keeps d0 near its floor and depresses achievable ipSAE. 0.75 is realistic excellence.

---

## How These Map to Verdict Bands

Within each modality, the composite score (see `composite-score.md`) maps to verdicts:

| Verdict | Composite | Antibody ipSAE_min | Nanobody ipSAE_min | De novo ipSAE_min |
|---------|-----------|---------------------|---------------------|--------------------|
| LAB-READY | `>= 0.75` | `>= 0.75` | `>= 0.70` | `>= 0.85` |
| FOLLOW-UP | `0.60 - 0.75` | `0.60 - 0.75` | `0.55 - 0.70` | `0.70 - 0.85` |
| BORDERLINE | `0.45 - 0.60` | `0.45 - 0.60` | `0.40 - 0.55` | `0.55 - 0.70` |
| NOT VIABLE | `< 0.45` | `< 0.45` | `< 0.40` | `< 0.55` |

The composite score already encodes the modality threshold differences indirectly — designs with modality-typical ipSAE_min values land in the right verdict band naturally.

---

## When to Use Manifest Defaults Instead

The `plugin-manifest.json` defaults (`poor: 0.2, good: 0.5, excellent: 0.8`) apply when:

- The modality is unknown or mixed (e.g., scoring a heterogeneous panel)
- The target is genuinely novel and no modality-specific calibration exists
- You are reporting raw ipSAE values to a user without per-modality context

For all standard screening workflows on a single modality, use the per-modality table above.

---

## Implementation

`scripts/composite_score.py` accepts a `--modality` flag that swaps in the per-modality thresholds for hard filtering. Example:

```bash
python scripts/composite_score.py --input scored.csv --output ranked.csv --modality nanobody
```

The `by-screening` agent reads the modality from `campaign_plan.json` and passes it through automatically.

---

## Calibration Provenance

The numbers in the Quick Reference Table come from:

- Antibody / Fab: 1,200+ refolded designs scored against SAbDab co-crystal validation set.
- Nanobody / VHH: 200+ refolded designs scored against published nanobody-antigen complexes.
- De novo: 350+ PXDesign outputs scored against Tamarind cloud Protenix benchmarks.
- Bispecific: 80+ designs; calibration confidence is lower — adjust with caution.
- Cyclic peptide: 60+ designs; treat as preliminary calibration.

For methodology details on calibration runs, see the `by-knowledge` skill — calibration data is persisted in the project knowledge graph.

---

## See Also

- `ipsae-algorithm.md` — formula derivation explains why interface size affects achievable ipSAE.
- `composite-score.md` — how thresholds factor into the composite formula.
- `scoring-pitfalls.md` — modality confusion is a top-3 source of misinterpretation.
