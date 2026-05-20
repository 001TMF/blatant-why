# Catalog of Common Design-Campaign Failure Patterns

Each pattern below is a *signature*: a combination of diagnosis output features that points to a specific root cause. Use this catalog as a lookup table when interpreting `screen_diagnose_failures` results.

---

## Pattern 1: Low ipSAE Cluster

**Signature:**
- `ipsae` (or `ipsae_min`) is the top discriminating feature
- Effect size > 0.8
- PASS mean ipSAE ~0.55–0.70, FAIL mean ~0.25–0.40
- pLDDT may also be lower in FAIL but with smaller effect

**Root cause:** The diffusion model is producing designs that physically dock to the target surface but do not form a high-confidence interface. Often happens with:
- Concave or shallow epitopes
- Glycosylated regions adjacent to hotspots
- Templates that are a poor fit for the target topology

**Recommendation:** Raise the ipSAE threshold to the PASS-group mean. If the resulting pass rate is too low, re-run BoltzGen with tighter hotspot constraints or a different scaffold family.

**Cross-link:** [threshold-tuning.md § ipsae-cluster](threshold-tuning.md#ipsae-cluster)

---

## Pattern 2: CDR3 Liability Spike

**Signature:**
- `liabilities` is the top discriminating feature
- Effect size > 1.0
- PASS mean liabilities ~ 0, FAIL mean ~ 1.5–3.0
- `cdr3_length` is often co-significant (longer CDR3 = more chances for liability motifs)

**Root cause:** The diffusion model is sampling sequence space that contains chemical degradation motifs (deamidation, isomerization, oxidation, glycosylation sites). Frequently driven by:
- Long CDR3 loops with high asparagine/glycine content
- Hotspot bias toward sticky residues
- Insufficient diversity in the BoltzGen MSA prompt

**Recommendation:** Move the liability scan **earlier** in the screening cascade (filter pre-fold). Constrain CDR3 length range in the next BoltzGen invocation. Bias sequence sampling away from N, G, M, W in hot positions.

**Cross-link:** [threshold-tuning.md § cdr3-liabilities](threshold-tuning.md#cdr3-liabilities)

---

## Pattern 3: Hydrophobic Patch Bias

**Signature:**
- `hydrophobic_fraction` is the top discriminating feature
- FAIL designs have higher hydrophobic_fraction than PASS
- `net_charge` may be lower (less polar) in FAIL
- Designs visually have clustered hydrophobic residues on the binder face

**Root cause:** The diffusion model finds high apparent affinity by burying hydrophobics, but downstream developability filters reject them (poor solubility, aggregation propensity). Often co-occurs with high ipSAE in FAIL — the binder is "tight" but unmanufacturable.

**Recommendation:** Add a hydrophobic-fraction ceiling to screening (e.g., < 0.45). Adjust BoltzGen design bias toward more polar residues at solvent-exposed positions. Consider Pareto trade-off analysis between affinity and developability.

**Cross-link:** [threshold-tuning.md § hydrophobic-bias](threshold-tuning.md#hydrophobic-bias)

---

## Pattern 4: Charge Skew

**Signature:**
- `net_charge` is significantly different between groups
- FAIL designs are at one extreme (e.g., highly positive for an acidic target, highly negative for a basic target)
- Often a follow-on from Pattern 3 — the model overcompensates by stacking charges

**Root cause:** Hotspot residues on the target are predominantly one charge, driving the model to recruit the opposite charge on the binder. This produces designs that look great in pTM but fail in developability (isoelectric point off-target, poor expression).

**Recommendation:** Enforce a `net_charge` window (e.g., −5 to +5) in screening. Re-examine hotspot selection — if all hotspots are negative, broaden to include polar/neutral residues nearby.

**Cross-link:** [threshold-tuning.md § charge-skew](threshold-tuning.md#charge-skew)

---

## Pattern 5: pLDDT-ipSAE Decoupling

**Signature:**
- `plddt` has effect size > 0.8 but `ipsae` has effect size < 0.3
- High pLDDT but low ipSAE in FAIL group
- PASS designs have moderate pLDDT (~70-80) and high ipSAE

**Root cause:** Designs are well-folded in isolation (high pLDDT) but do not form a confident interface with the target. The structure-prediction confidence is dominated by the binder's own fold, not the binding event. Common when:
- The binder is over-rigid (over-constrained framework)
- The epitope is correct but the binding pose is wrong
- The hotspot residues are buried in the binder rather than facing the target

**Recommendation:** Filter primarily on ipSAE, not pLDDT. Re-run Protenix with multiple seeds and look for pose consistency. Consider relaxing framework constraints in BoltzGen.

**Cross-link:** [threshold-tuning.md § plddt-decoupling](threshold-tuning.md#plddt-decoupling)

---

## Pattern 6: RMSD Drift

**Signature:**
- `rmsd` is the top discriminating feature
- PASS designs have RMSD < 2.0 Å vs initial pose; FAIL designs have RMSD > 4.0 Å
- Often co-occurs with low ipSAE in FAIL

**Root cause:** The refold step (Protenix on BoltzGen output) is moving the binder substantially. The original BoltzGen pose was not stable; refold finds a different (worse) local minimum. Indicates:
- Weak initial hotspot interactions
- Steric clashes resolved by binder repositioning
- Insufficient diversity in seed sampling

**Recommendation:** Tighten the RMSD filter to 2.5 Å. Increase the number of Protenix seeds per design (5 → 10). Investigate whether high-RMSD designs cluster around a specific scaffold or hotspot configuration.

**Cross-link:** [threshold-tuning.md § rmsd-drift](threshold-tuning.md#rmsd-drift)

---

## Pattern 7: Doublet / Cluster Artifacts

**Signature:**
- No feature has effect size > 0.5 individually
- Visual inspection shows FAIL designs are nearly identical (clustered)
- Diversity metric (not currently in the canonical 9) is low
- Pass rate looks acceptable per-design but novelty is poor

**Root cause:** The diffusion sampler is collapsing to a small region of design space. Every "failure" is a near-duplicate of every other failure. Statistical diagnosis misses this because the test compares means, not variance.

**Recommendation:** This pattern is NOT detectable via Mann-Whitney. Run `proteus_cli.screening.diversity` to cluster designs and report mode count. If < 5 modes for 100 designs, increase sampling temperature in BoltzGen.

**Cross-link:** [threshold-tuning.md § cluster-artifacts](threshold-tuning.md#cluster-artifacts)

---

## Pattern 8: CDR3 Length Bias

**Signature:**
- `cdr3_length` is the top discriminating feature
- PASS designs cluster at a specific length (e.g., 12–14 residues); FAIL cluster at extremes (< 10 or > 18)
- Effect size moderate (0.5 – 0.8)

**Root cause:** The target topology has a "sweet spot" for CDR3 length. Designs that are too short cannot reach the epitope; too long lose entropy and clash with framework. The diffusion model is not learning this constraint on its own.

**Recommendation:** Constrain CDR3 length range in the next BoltzGen invocation to the PASS-group mean ± 2. This is one of the most effective and lowest-risk parameter changes.

**Cross-link:** [threshold-tuning.md § cdr3-length](threshold-tuning.md#cdr3-length-bias)

---

## Pattern 9: No Signal in Features

**Signature:**
- All p-values > 0.1
- Pass rate is below 10%
- Sample size is adequate (n > 50)

**Root cause:** The failure mode is **not represented in the feature set**. Possible causes:
- Wrong scaffold family (no PASS designs would ever come from this scaffold)
- Wrong epitope (binder can't form a viable interface)
- Wrong modality entirely (target requires bispecific or peptide, not antibody)

**Recommendation:** This is NOT a thresholding problem. Escalate to **by-hypothesis-debate** to pick a new strategy. Consider whether the target was correctly characterized in **by-research**.

**Cross-link:** [threshold-tuning.md § no-signal](threshold-tuning.md#no-signal)

---

## Pattern 10: Inverted Recommendation

**Signature:**
- Diagnosis recommends raising a threshold (e.g., `ipsae` up to 0.55)
- Next round pass rate is unchanged or worse

**Root cause:** The previous round's threshold was already at the empirical floor of the PASS distribution. Raising it eliminates marginal PASS designs without changing the failure mode. Diagnosis is correct about the statistics but cannot tell you that the action is futile.

**Recommendation:** When `passed_mean` is within 5% of the current threshold, threshold tuning has diminishing returns. Switch to design-parameter changes (CDR3 length, hotspots, scaffold pool).

**Cross-link:** [threshold-tuning.md § stuck-thresholds](threshold-tuning.md#stuck-thresholds)

---

## Pattern 11: Round-Mixing Artifact

**Signature:**
- Diagnosis flags features that do not align with any known biological signal
- Effect sizes are unusually large (> 2.0)
- Recommendations contradict prior rounds

**Root cause:** The input dataset contains designs from multiple rounds with different screening thresholds. The PASS/FAIL label is inconsistent across rows; the test is comparing apples to oranges.

**Recommendation:** Always filter to a single round before running diagnosis. Add a `round_id` column to your screening output and assert it is unique before calling the tool.

---

## Cross-cutting concepts

### Cohort balance

The Mann-Whitney test handles unbalanced groups, but extreme imbalance (e.g., 5 PASS vs 500 FAIL) makes effect-size estimates unreliable. Aim for at least 10% PASS and at least 10% FAIL in your cohort. If you cannot achieve this, the screening thresholds need adjustment before diagnosis is meaningful.

### Missing features

If a feature is absent from > 80% of designs (e.g., `cdr3_length` for non-antibody designs), the diagnosis silently skips it. This is correct behavior but can hide problems — verify the feature columns present in your dataset before interpreting "no signal" as a real null result.

### Population vs individual

Diagnosis answers population-level questions ("on average, do PASS designs have higher X?"). It does NOT answer per-design questions ("why did design #47 fail?"). For the latter, use:
- Direct structure inspection in ProteinView
- `by-epitope-analysis` for residue-level binding rationale
- `by-failure-modes-catalog` for qualitative pattern matching on individual designs

Both can be useful simultaneously and need not agree — they answer different questions.
