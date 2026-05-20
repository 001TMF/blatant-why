# Threshold and Parameter Tuning from Diagnosis Output

Translating `screen_diagnose_failures` output into concrete next-round actions. Each section maps a diagnosis pattern (from `failure-patterns.md`) to specific parameter changes in screening, BoltzGen, or PXDesign.

---

## Decision tree

Use this top-down to pick an action:

```
Diagnosis output → 
  ├─ ≥ 1 feature with effect_size > 1.0 ?
  │   ├─ YES → Threshold tuning (pick the dominant feature)
  │   │         └─ See pattern-specific section below
  │   └─ NO →
  │       ├─ ≥ 2 features with 0.5 < effect_size ≤ 1.0 ?
  │       │   ├─ YES → Design-parameter changes (CDR3 length, hotspots)
  │       │   │         └─ Combine signals; do NOT tune thresholds individually
  │       │   └─ NO → No actionable statistical signal
  │       │           ├─ Pass rate < 10% → Strategy change via by-hypothesis-debate
  │       │           └─ Pass rate ≥ 10% → Accept current cohort, move to lab triage
```

---

## Pattern → Action Table

| Diagnosis pattern | Primary action | Secondary action | Risk if applied wrongly |
|-------------------|----------------|------------------|-------------------------|
| Low ipSAE cluster | Raise `ipsae` threshold to PASS mean | Re-run BoltzGen with tighter hotspots | Eliminates marginal designs without fixing root cause |
| CDR3 liability spike | Add liability scan pre-fold | Constrain CDR3 length range | May overly restrict design space |
| Hydrophobic patch bias | Add `hydrophobic_fraction < 0.45` filter | Bias BoltzGen toward polar residues | Reduces affinity diversity |
| Charge skew | Enforce net_charge window | Broaden hotspot set | May reject high-affinity binders |
| pLDDT-ipSAE decoupling | Filter on ipSAE only | Multi-seed Protenix | Loss of well-folded but non-binding designs |
| RMSD drift | Tighten `rmsd < 2.5 Å` | More Protenix seeds per design | Higher compute cost |
| Doublet artifacts | Diversity filter (not Mann-Whitney) | Raise BoltzGen sampling temperature | Lower per-design quality |
| CDR3 length bias | Constrain CDR3 length range | n/a | Lowest risk — usually safe |
| No signal in features | Strategy change | New feature engineering | Wasted compute if mistargeted |
| Inverted recommendation (stuck) | Switch to design parameters | New scaffold pool | Without root-cause fix, no improvement |
| Round-mixing artifact | Filter to single round; re-run diagnosis | n/a | Garbage in, garbage out |

---

## Section: ipsae-cluster

**When:** `ipsae` is top feature, effect size > 0.8, PASS mean clearly above FAIL mean.

**Action:**
```python
# Bump threshold to the PASS-group mean
new_ipsae_threshold = diag["discriminating_features"][0]["passed_mean"]
# Or use the 10th percentile of PASS distribution for less aggressive cutoff
```

**Side effects:** Eliminates ~half of FAIL designs while keeping ~90% of PASS. Pass rate goes up but absolute PASS count goes down. If absolute count drops below 5, generate more designs before raising threshold.

**When NOT to apply:** If `passed_mean` is already within 5% of the current threshold (stuck-thresholds case below).

---

## Section: cdr3-liabilities

**When:** `liabilities` is top feature, FAIL mean > 1, PASS mean ~0.

**Action 1 (immediate):** Move liability scan **before** the fold step. This is the highest-leverage change because every design with a liability is wasted compute.
```bash
# In the screening pipeline config, reorder:
#   1. sequence_filter (liabilities)
#   2. structure_predict (Protenix)
#   3. score (ipSAE)
```

**Action 2 (next round):** Constrain CDR3 length and sequence composition in BoltzGen:
```yaml
# entities.yaml
cdr3:
  length_range: [11, 14]
  avoid_motifs: ["NG", "DG", "DS", "DP", "NS"]  # deamidation, isomerization
```

**When NOT to apply:** If only 1-2 liability motifs are driving the result, those may be acceptable risk for high-affinity designs — surface to user for decision.

---

## Section: hydrophobic-bias

**When:** `hydrophobic_fraction` is top, FAIL > PASS, effect size > 0.6.

**Action:** Add a hard ceiling to screening (default 0.45 for antibodies, 0.50 for non-antibody binders). In BoltzGen, increase the polar-residue bias at solvent-exposed positions.

**Compound action:** If `net_charge` is also significant in the same direction, the fix is hotspot reselection — see `charge-skew`.

**Risk:** Affinity loss. Track binding affinity in the next round; if it drops below baseline, the ceiling is too tight.

---

## Section: charge-skew

**When:** `net_charge` is significant; FAIL designs are at an extreme.

**Action:** 
1. Inspect the target's hotspot residues — if all of one charge type, expand the hotspot set to include adjacent polar residues.
2. Add a `net_charge` window filter: typically −5 to +5 for systemic antibodies, −8 to +8 for topical or local-delivery contexts.

**Compound case:** Charge skew + hydrophobic bias often indicates the model is "burying" or "shielding" hotspots inappropriately. Consider a different epitope (`by-epitope-analysis`).

---

## Section: plddt-decoupling

**When:** pLDDT discriminates well but ipSAE does not. PASS designs have moderate pLDDT but high ipSAE; FAIL designs have high pLDDT but low ipSAE.

**Action:** Filter on ipSAE only; ignore pLDDT in the next round. High pLDDT FAIL designs are well-folded *binders* that happen not to *bind*. The fold confidence is a confounder.

**Diagnostic:** Run Protenix with 5+ seeds and look for pose consistency. If high-pLDDT/low-ipSAE designs show inconsistent poses across seeds, the model is hallucinating folds; consider switching to PXDesign for non-antibody modalities.

---

## Section: rmsd-drift

**When:** `rmsd` between BoltzGen output and Protenix refold is the top discriminator.

**Action:** Tighten the RMSD filter (default 3.0 Å → 2.5 Å). Increase Protenix seed count from 5 to 10 to improve refold reliability. Designs with high BoltzGen→Protenix drift indicate the initial pose was unstable.

**Side effect:** Compute cost doubles per design with more seeds. Budget accordingly.

---

## Section: cluster-artifacts

**When:** No feature has effect size > 0.5, but you observe by eye that FAIL designs look nearly identical.

**Action:** This is NOT detectable via Mann-Whitney. Run:
```python
from proteus_cli.screening.diversity import cluster_designs
clusters = cluster_designs(designs, threshold=0.85)
```

If `len(clusters) < 5` for 100 designs, the diffusion sampler has collapsed. Raise BoltzGen sampling temperature (`temperature=0.8 → 1.2`) and/or increase the number of seeds.

---

## Section: cdr3-length-bias

**When:** `cdr3_length` is the top discriminator with a clear PASS-group preferred length.

**Action:** Constrain in BoltzGen entities.yaml:
```yaml
cdr3:
  length_range: [<PASS_mean - 2>, <PASS_mean + 2>]
```

This is the safest tuning action — it directly encodes a learned constraint without affecting other dimensions of design space. Often the single highest-yield change in a campaign.

---

## Section: no-signal

**When:** All p-values > 0.1, pass rate < 10%, n ≥ 50.

**Action:** Do NOT tune thresholds. The failure is structural, not statistical.
1. Invoke **by-hypothesis-debate** with the current campaign state and target dossier.
2. Consider these strategy pivots:
   - Different scaffold family (caplacizumab → ozoralizumab, common-light → λ-only, etc.)
   - Different epitope (re-run **by-epitope-analysis** with broader site filter)
   - Different modality (VHH → scFv, antibody → de novo binder via PXDesign)
3. Document the null result in `campaigns/<target>/<id>/diagnosis.json` so future campaigns know this scaffold/epitope combo failed.

---

## Section: stuck-thresholds

**When:** Diagnosis recommends raising a threshold but the recommended value is within 5% of the current threshold.

**Diagnostic:**
```python
current = current_thresholds["ipsae"]
recommended = diag["discriminating_features"][0]["passed_mean"]
if abs(recommended - current) / max(current, 1e-6) < 0.05:
    # Stuck — switch to parameter tuning
```

**Action:** Switch from threshold tuning to design-parameter changes:
- Different scaffold pool
- New hotspot set
- New CDR length distribution
- New BoltzGen sampling temperature

Threshold tuning has diminishing returns once `passed_mean ≈ current_threshold`.

---

## Section: correlated-features

**When:** Two or more features are significant and recommendations conflict (raise A, lower B).

**Diagnostic:** Check correlation between features within FAIL group. If they are highly correlated (|r| > 0.7), they are measuring the same underlying problem.

**Action:** Pick the feature with the higher effect size and ignore the other. The fix for one will improve the other automatically.

---

## Section: order-of-operations

**When:** A feature is "perfectly discriminating" — all PASS have one value, all FAIL have another (e.g., all FAIL have ≥1 liability, all PASS have 0).

**Cause:** The feature is being applied as a hard filter elsewhere in the pipeline, but downstream of the structure-prediction step. The expensive Protenix compute is being spent on designs that the filter would reject.

**Action:** Move the filter earlier in the cascade. Liability scans, length filters, and composition filters should run on **sequence** before any structure prediction.

---

## Section: budget consideration

After diagnosis, before applying changes, sanity-check the compute cost:

| Action | Cost change | Iteration time impact |
|--------|-------------|----------------------|
| Tighten threshold (no re-run) | None | None — re-screen existing designs |
| Raise BoltzGen seed count | +N× per design | Linear in N |
| Multi-seed Protenix | +5-10× per design | Linear in seeds |
| Diversity-aware sampling | +30% per design | Adds clustering pass |
| New scaffold pool | New compute baseline | Resets campaign |
| New epitope | New compute baseline + new research | Full reset |

Tighten thresholds first (free); add seeds second (cheap); reset campaigns last (expensive).

---

## Section: validation loop

After applying a recommendation:

1. Run the next round with the change.
2. Re-run diagnosis on the new round.
3. Compare:
   - Did pass rate improve?
   - Did the feature that drove the previous diagnosis become non-significant?
   - Did a new feature emerge as discriminating?

If the previously-top feature is no longer significant AND a new one emerges, you have *moved* the failure mode rather than eliminated it. This is progress — iterate again.

If the same feature remains dominant after the change, the action did not address the root cause — revisit the decision tree at the top.
