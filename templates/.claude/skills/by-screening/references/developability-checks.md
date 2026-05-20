# Developability Checks — CDR, Charge, Hydrophobicity, Stability

TAP-inspired developability assessments applied during screening. This document covers the *methodology* behind each check; numeric defaults and modality overrides live in [filter-thresholds.md](filter-thresholds.md).

The five TAP guidelines (Raybould et al. 2019) form the backbone. BY adds composition flags, predicted Tm cutoffs, and structural patch detection.

---

## 1. CDR Length Analysis

### Why it matters

Total CDR length correlates with manufacturability. Clinical-stage antibodies have a tight distribution (median total CDR ≈ 55 residues for Fv). Unusually long CDRs — especially CDR-H3 — correlate with:
- Higher aggregation propensity
- Lower thermal stability
- Increased polyreactivity
- Manufacturing yield loss

### How BY measures it

Requires explicit CDR region annotations (`cdr_regions` parameter): list of `[start, end]` tuples (0-indexed, end-exclusive) in IMGT or Kabat numbering.

```
total_cdr_length = sum(end - start for start, end in cdr_regions)
cdr_h3_length = cdr_regions[2][1] - cdr_regions[2][0]   # 3rd CDR by convention
```

### Default cutoffs

| Modality | Total CDR | CDR-H3 |
|----------|-----------|--------|
| Antibody (Fv, 6 CDRs) | ideal < 55, acceptable 55–70, FLAG > 70 | typical 10–15, FLAG > 20 |
| Nanobody (VHH, 3 CDRs) | ideal < 35, acceptable 35–45, FLAG > 45 | typical 12–18, FLAG > 25 |

### Common pitfalls

- Not providing CDR annotations → screen computes length from full chain → false PASS
- Using Kabat numbering when IMGT was expected → off-by-a-few residues; usually still triggers the right action but rough
- Counting Fc residues in an IgG → use Fv variable region only

---

## 2. Net Charge at Physiological pH

### Why it matters

Net charge at pH 7.4 governs:
- **Viscosity** at high concentration (formulations)
- **Polyreactivity** (high + charge → off-target binding)
- **Pharmacokinetics** (extreme charge → fast clearance)
- **Solubility** (near-zero charge near pI can precipitate)

### How BY measures it

Henderson-Hasselbalch with standard side-chain pKa values:

| Residue | pKa | Charge at neutral pH |
|---------|-----|----------------------|
| Asp (D) | 3.65 | negative |
| Glu (E) | 4.25 | negative |
| His (H) | 6.00 | partial positive |
| Cys (C) | 8.18 | partial negative |
| Tyr (Y) | 10.07 | mostly neutral |
| Lys (K) | 10.53 | positive |
| Arg (R) | 12.48 | positive |
| N-terminus | 9.69 | positive |
| C-terminus | 2.34 | negative |

Formula:
```
for acidic in D,E,C,Y: charge -= 1/(1 + 10^(pKa - pH))
for basic in K,R,H:    charge += 1/(1 + 10^(pH - pKa))
charge += 1/(1 + 10^(pH - 9.69))   # N-term
charge -= 1/(1 + 10^(2.34 - pH))   # C-term
```

### Default cutoffs

| Net Charge | Verdict |
|------------|---------|
| -2 to +5 | IDEAL |
| +5 to +8 | ACCEPTABLE |
| -5 to -2 | ACCEPTABLE |
| > +8 or < -5 | FLAG |
| > +10 or < -10 | REJECT |

### Common pitfalls

- Including signal peptide → false high charge → strip before computing
- Comparing across tools that use different pKa tables (EMBOSS pepstats uses different values) → stick with BY's HH defaults
- Single-residue mutations to neutralize charge: prefer non-contact surface positions

---

## 3. Hydrophobic Fraction and Surface Patches

### Why it matters

Surface hydrophobic patches drive aggregation. The TAP "PSH" (patches of surface hydrophobicity) score is a primary developability filter; BY uses a two-tier approximation:

1. **Sequence-level**: fraction of hydrophobic AAs in the design chain (cheap, no structure needed)
2. **Structural patch**: DBSCAN clustering of solvent-accessible hydrophobic atoms (requires PDB coordinates)

### Sequence-level

Hydrophobic AA set: `{A, I, L, M, F, W, V, P}`

```
hydro_frac = sum(1 for aa in seq if aa in HYDROPHOBIC_AAS) / len(seq)
```

| Hydrophobic Fraction | Verdict |
|----------------------|---------|
| < 0.35 | Good |
| 0.35 – 0.45 | Acceptable |
| > 0.45 | FLAG |
| > 0.55 | REJECT |

### Structural patch detection

When PDB coordinates are available:
1. Compute solvent-accessible surface area per atom (e.g., FreeSASA)
2. Select hydrophobic atoms with SASA > 0 Å²
3. DBSCAN cluster by 3D distance (default eps = 5 Å, min_samples = 5)
4. Report patch area = sum of SASA over cluster atoms

| Largest Patch | Verdict |
|---------------|---------|
| < 400 Å² | Good |
| 400 – 600 Å² | Acceptable |
| > 600 Å² | FLAG (single-patch threshold) |
| > 1000 Å² | REJECT |

### Common pitfalls

- Computing hydrophobic fraction on IgG vs Fv → Fc skews the result
- Treating `P` (proline) as hydrophobic — BY does, because of its aggregation contribution; some tools (e.g., Kyte-Doolittle scale) treat P differently
- Patch detection requires correctly assigned chains; an incorrectly assigned hetatm/ligand can inflate counts

---

## 4. Composition Flags

Beyond charge and hydrophobicity, certain compositional anomalies flag potential design artifacts.

| Flag | Condition | Severity | Why |
|------|-----------|----------|-----|
| High glycine | `count(G) / length > 0.15` | MEDIUM | Excessive flexibility, possibly degenerate design |
| High proline | `count(P) / length > 0.10` | LOW | Disrupts beta-sheets in framework |
| Low diversity | `max(count(AA)) / length > 0.20` | MEDIUM | Composition bias |
| Missing canonical | conserved Trp / Cys absent | HIGH | Structural fold likely broken (canonical residues at fixed positions) |

Canonical positions for antibodies (Kabat numbering):
- Cys22, Cys92 (Vh internal disulfide)
- Trp36 (framework H1)
- Trp103 (CDR-H3 boundary)

Missing any of these is HIGH severity and usually indicates a templating error during generation.

---

## 5. Predicted Thermal Stability (Tm)

### Why it matters

Low Tm (< 60 °C) correlates with manufacturing problems: protein unfolds during purification, storage, or high-concentration formulation.

### Tools

Predicted Tm is not computed in-line by the by-screening MCP server. Use external tools and pass the value as an input column to `scripts/screen_batch.py`:

- **ThermoMPNN** — sequence-only Tm prediction. See `by-deploy-compute` for setup.
- **DeepStab / NetSurfP-3** — surface stability predictions
- **Structure-based**: FoldX `--stability` flag on the refolded structure

### Default cutoff

| Predicted Tm | Verdict |
|--------------|---------|
| >= 70 °C | Excellent |
| 60 – 70 °C | Acceptable |
| < 60 °C | FLAG (advisory; not a hard filter) |

Tm is a soft criterion. Designs are not REJECTED on Tm alone, but a low Tm combined with other developability flags lowers the composite rank.

---

## 6. Hand-off to Downstream Checks

After developability assessment passes, the following downstream checks may run:

- **Cross-validation (dual predictor)** — required before lab submission; see SKILL.md "Cross-Validation Protocol"
- **Naturalness** (`mcp__by-screening__screen_naturalness`) — protein language model perplexity; flags artifacts
- **Shape complementarity** (`mcp__by-screening__screen_shape_complementarity`) — Sc (Lawrence & Colman) when interface looks suspicious

Developability is a Stage-1 filter for charge / hydrophobic / CDR length hard cutoffs, and a Stage-2 soft input for composition flags and Tm.

---

## References

- Raybould et al., "Five computational developability guidelines for therapeutic antibody profiling" (PNAS 2019) — TAP
- Jain et al., "Biophysical properties of the clinical-stage antibody landscape" (PNAS 2017) — polyreactivity benchmarks
- Robinson et al., "Charge-based interactions and antibody developability" (mAbs 2017)
- Lauer et al., "Developability index: A rapid in silico tool for the screening of antibody aggregation propensity" (J Pharm Sci 2012)
- For tool setup (ThermoMPNN, AGGRESCAN, FreeSASA): see the **by-deploy-compute** skill.
