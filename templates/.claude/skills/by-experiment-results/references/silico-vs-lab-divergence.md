# In-Silico vs Lab Divergence

In-silico PASS does not guarantee lab PASS. This document catalogs **why** designs that look good on paper fail at the bench, and — for each failure mode — names the in-silico feature that *should* have caught it.

The point of the catalog is twofold:

1. When a calibration shows a contradicted feature, this list tells you which downstream issue is most likely upstream.
2. When you are designing the next screening cascade, this list tells you which feature to add to the cascade if a class of failures keeps slipping through.

---

## Failure Modes

### 1. Expression problems

**What happens at the bench:** The construct expresses at <1 mg/L, or not at all, despite predicted structural soundness.

**Likely causes:**
- Rare codons in the host (E. coli, HEK293) creating ribosome stalls.
- N-terminal Met-X rule violations (X = bulky hydrophobic destabilizes).
- Aggregation-prone regions (APRs) leading to inclusion bodies.
- pI very close to expression pH causing precipitation.

**In-silico feature that SHOULD have caught it:**
- `aggregation_predicted` (APR predictor: TANGO, AggreScan3D-style score)
- `net_charge` at pH 7.4 (should not be near zero for soluble expression)
- Sequence-level codon usage bias (not currently in BY's canonical features — add if expression is a recurring failure mode)

**Calibration signature:** If `expression_mg_per_L` is the lab outcome and `aggregation_predicted` shows up as `inconclusive` or `contradicted`, your aggregation model is mis-calibrated for the production host. Re-train the predictor or add codon-usage features.

---

### 2. Aggregation during purification

**What happens at the bench:** Construct expresses fine but SEC shows >30% high-molecular-weight (HMW) species, monomer % below 70%.

**Likely causes:**
- Surface-exposed hydrophobic patch encouraging self-association.
- Free cysteine forming intermolecular disulfide.
- High net charge promoting electrostatic aggregation at concentration.

**In-silico feature that SHOULD have caught it:**
- `hydrophobic_fraction` (surface, not buried)
- `aggregation_predicted` (APR predictor)
- Free-cysteine count (sequence-level scan, not in BY's canonical features — add if relevant)

**Calibration signature:** If `aggregation_pct` is the lab outcome and `hydrophobic_fraction` is contradicted (PASS designs are more hydrophobic than FAIL), the predictor is computing **total** hydrophobicity instead of **surface-exposed** hydrophobicity. Fix the feature definition.

---

### 3. Polyspecificity (off-target binding)

**What happens at the bench:** Construct binds the on-target antigen well (good Kd) but also binds an unrelated panel of antigens (baculovirus particles, polyspecificity reagent). Bad therapeutic property — high clearance, off-target tox.

**Likely causes:**
- Hydrophobic patch on the CDR loops (especially CDR3) that sticks to anything.
- Excess positive charge near the paratope binding non-specifically to negatively charged surfaces.
- CDR length outside canonical range (very long CDR3 = flexible, promiscuous).

**In-silico feature that SHOULD have caught it:**
- `polyspecificity_predicted` (CDR hydrophobic patch screen, isoelectric point of paratope)
- `hydrophobic_fraction` (specifically of CDR residues)
- `cdr3_length`

**Calibration signature:** If `polyspecificity_score` is the lab outcome and `polyspecificity_predicted` does not validate (or is contradicted), the in-silico predictor is using a different definition of polyspecificity than the lab assay. Cross-check the assay's panel.

---

### 4. Epitope inaccessibility (cryptic epitope)

**What happens at the bench:** Designs predicted to bind well show very weak signal on the cell-surface or membrane-bound target, despite working on the recombinant antigen.

**Likely causes:**
- The predicted epitope is partially buried in the membrane.
- The epitope is glycosylated on the native protein but not on the recombinant antigen used for in-silico design.
- Conformational state during prediction differs from the in-vivo state.

**In-silico feature that SHOULD have caught it:**
- Epitope SASA in the membrane / cellular context (not currently in BY's canonical features — needs MD or cryo-EM context)
- Glycosylation site proximity (`liabilities` should include NxS/T motif scan)

**Calibration signature:** If lab Kd against the cell-surface target is much worse than lab Kd against recombinant, neither will calibrate against `ipsae` — both will look inconclusive. That's a target-class warning to inspect epitope accessibility before the next design round.

---

### 5. Kinetic vs thermodynamic mismatch

**What happens at the bench:** Predicted Kd looks great, but on-rate (ka) is glacial (10^3 1/Ms instead of 10^5) — practically inactive in cellular contexts despite great equilibrium affinity.

**Likely causes:**
- Designed interface relies on rare conformational alignment (high entropy cost).
- Predicted complex is a local minimum, not the kinetically accessible bound state.

**In-silico feature that SHOULD have caught it:**
- BY's `ipsae` and `iptm` are equilibrium (structural) confidence metrics; neither models kinetics.
- Add a per-residue interface flexibility score, or compute ipTM across multiple conformations and report the **minimum** (worst-case).

**Calibration signature:** If `ka_per_M_per_s` is the lab outcome and `ipsae` is inconclusive, the equilibrium predictor is silent on kinetics. Add a kinetic feature; do not declare `ipsae` contradicted here — it is simply orthogonal.

---

### 6. Format mismatch (avidity, monovalent vs bivalent)

**What happens at the bench:** Monovalent affinity (lab BLI) is 10x worse than the cell-surface signal (lab ELISA), because the ELISA was avidity-amplified by a bivalent format.

**Likely causes:**
- BY designs are monovalent (single VHH, single binder); cell-surface signals reflect avidity for multimerized native target.

**In-silico feature that SHOULD have caught it:**
- This is an experimental design issue, not a predictor issue. Mitigate by running BOTH ELISA and BLI on every batch and calibrating per-assay.

**Calibration signature:** Calibration is fine within each assay; it is the cross-assay comparison that diverges. Always run per-assay diagnosis; never pool ELISA + BLI in one calibration.

---

### 7. Misfolded but high-confidence structure

**What happens at the bench:** Construct expresses, but circular dichroism shows it is in a non-native fold; binding is non-specific.

**Likely causes:**
- BoltzGen produced a structure with high ipTM but local geometry is non-physical.
- Refolding with Protenix matches the design but with an unusual disulfide pattern.

**In-silico feature that SHOULD have caught it:**
- `plddt` per-residue (a uniformly high pLDDT is suspicious for short loops)
- `rmsd` between BoltzGen output and Protenix refold (should be small but not zero)
- Disulfide bond count and topology check (add if recurring)

**Calibration signature:** If `lab_outcome=FAIL` and `plddt` is high while `rmsd` is also high, you have a refold-mismatch failure. Tighten the `rmsd` threshold or add a topology check.

---

## Calibration Metrics

The diagnosis script computes the following per in-silico feature:

### Mann-Whitney U (rank-sum test)

Non-parametric test asking: do PASS designs and FAIL designs have different distributions in this feature? Output: `statistic`, `p_value`. Robust to outliers, no normality assumption. Same test as **by-failure-diagnosis** for consistency across rounds.

### BH-corrected q-value

Apply Benjamini-Hochberg correction across all features tested. Required because with 6-9 features you expect ~0.3-0.45 false positives at α=0.05.

### Effect size (Cohen's d analog from U)

`r = 1 - (2U) / (n1 * n2)`, then convert to Cohen's d via `d = 2r / sqrt(1 - r^2)`. Useful interpretation:

| |d| | Strength |
|------|----------|
| > 0.8 | Large |
| 0.5 – 0.8 | Medium |
| 0.2 – 0.5 | Small |
| < 0.2 | Negligible |

Only declare a feature `validated` or `contradicted` when |d| > 0.5 AND p < 0.05 AND q < 0.10.

### Precision at top-K

`precision_at_K = (# lab-PASS in the top-K silico-ranked designs) / K`

K defaults to 10. Compare to the cohort base rate (e.g. if 30% of all lab-tested designs are PASS, then a precision of 0.6 at K=10 is 2x lift). This is the **most directly useful** metric for the user — it says "if I take the top 10 silico picks, how many will work?"

### Lift over random

`lift = precision_at_K / base_rate`

Lift = 1.0 means the silico ranking is random; lift > 1.5 is meaningful; lift > 2.5 is strong. Lift < 1.0 means the silico ranking is **worse than random** — a contradicted predictor.

### AUC (when N >= 30 and both classes present)

Area under the ROC curve of silico feature vs lab outcome. Computed with `sklearn.metrics.roc_auc_score`. Interpretation:

| AUC | Calibration verdict |
|-----|---------------------|
| > 0.75 | Strong validated |
| 0.65 – 0.75 | Validated |
| 0.55 – 0.65 | Weak / inconclusive |
| 0.45 – 0.55 | No signal |
| 0.35 – 0.45 | Inconclusive (could be inversion) |
| < 0.35 | Contradicted (predictor is inverted) |

A contradicted predictor with AUC ~0.30 is sometimes salvageable by inversion — pass `--invert <feature>` in the next round. But always confirm the biology makes sense before flipping a sign.

---

## Outliers

Mann-Whitney is rank-based so single outliers do not break the test. But they do show up in violin plots and can mislead human review.

- If one design has Kd 0.1 nM and the next-best is 200 nM, that design dominates the lift calculation.
- Inspect the violin; consider Hodges-Lehmann shift estimate alongside the Mann-Whitney p.

---

## One-Class Results

When all lab-tested designs PASS (or all FAIL), no calibration is possible — there is no contrast to diagnose. The script returns `verdict: inconclusive` for every feature and a `warnings` note. Next-round action:

- **All PASS** → the silico screen was too strict, the lab assay was too lenient, or you got lucky. Loosen silico thresholds to produce a mixed cohort next time, OR submit a broader panel.
- **All FAIL** → the silico screen is calibrated against the wrong target / epitope / modality. Stop and re-research (`by-research`, `by-hypothesis-debate`).

---

## Feature Aliases

In-silico files sometimes use different feature names than the canonical list (`ipsae` vs `ipsae_min`, `iptm` vs `iptm_mean`). Pass `--silico-feature-alias <canonical>=<source>` to the diagnosis script. Always alias to the canonical name on the LEFT so the calibration report uses consistent column names.
