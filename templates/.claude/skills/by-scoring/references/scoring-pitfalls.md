# Scoring Pitfalls

A catalog of misinterpretations and silent errors that have caused real campaigns to
chase non-viable designs or reject viable ones. Read this before reporting scores or
making panel decisions.

---

## 1. Confusing pTM with ipTM

**The mistake**: Reporting `ptm` instead of `iptm` from `summary_confidence.json`.

**Why it matters**: `pTM` is the global complex prediction confidence including *all* chain pairs (and intra-chain confidence). `ipTM` is restricted to *inter-chain* token pairs and is the correct metric for a binder-target complex. They typically differ by 0.05 - 0.20.

**Symptom**: Composite scores look 0.10 higher than reality. Designs flagged LAB-READY underperform in vitro.

**Fix**: Always read `iptm` from Protenix output. The MCP tool `mcp__by-screening__score_ipsae` returns ipTM correctly; if you parse Protenix JSON manually, the key is `iptm`, not `ptm`.

---

## 2. Single-seed Scoring on Flexible Modalities

**The mistake**: Computing ipSAE from a single Protenix seed for a nanobody (VHH) or scFv design.

**Why it matters**: VHH CDR-H3 loops are conformationally flexible. A single seed can swing 0.10 - 0.20 in ipSAE based on stochastic sampling. Single-seed ipSAE = 0.78 may have true mean ipSAE = 0.62.

**Symptom**: High variance in lab outcomes for "high-confidence" picks.

**Fix**: Use `score_ipsae_multi_seed` with **>= 20 seeds for VHH and scFv**, >= 10 seeds for de novo. The `by-screening` skill enforces this; do not bypass with single-seed shortcuts.

---

## 3. ipSAE on Tiny Interfaces

**The mistake**: Reporting ipSAE values for designs with fewer than ~15 interface residues (n0 < 15).

**Why it matters**: The TM-score d0 normalizer clamps at n0 = 19. Below this, d0 is artificially small (often the 0.5 floor), and the TM-score kernel becomes brutally sensitive to even small PAE values. A 6-residue interface with all PAE ~1 A will still score ~0.05.

**Symptom**: Small designs (peptides, short CDR mini-interfaces) get rejected as `POOR` even when they look reasonable structurally.

**Fix**: For interfaces with n0 < 15, report ipSAE with an asterisk noting the interface size, and lean more heavily on ipTM + visual inspection of the predicted structure. Do not blindly compare to standard ipSAE thresholds.

---

## 4. PAE Cutoff Mismatch (10 A vs 15 A)

**The mistake**: Using `pae_cutoff = 15.0` on Protenix output.

**Why it matters**: The 15 A cutoff is for AlphaFold2 outputs. Protenix and AlphaFold3 calibrate PAE differently — their distributions are tighter, so the appropriate cutoff is 10 A. Using 15 A on Protenix admits noisy residues into the score, inflating ipSAE by typically 0.05 - 0.10.

**Symptom**: ipSAE values systematically higher than reported in the Dunbrack 2025 paper for the same targets.

**Fix**: Always pass `pae_cutoff = 10.0` for Protenix and AF3 outputs. The BY default is 10.0 in `compute_ipsae()` and `score_npz()`.

---

## 5. Chain ID Direction Swap

**The mistake**: Computing ipSAE with `design_chain_ids` and `target_chain_ids` swapped.

**Why it matters**: For a symmetric metric like `ipsae_min`, swapping is harmless. But for the directional reports (`design_to_target_ipsae` vs `target_to_design_ipsae`), a swap inverts the interpretation. The "dt >> td" diagnosis (design anchored, target uncertain) becomes the opposite story.

**Symptom**: Asymmetry diagnoses contradict structural reality.

**Fix**: Confirm chain ordering from the Protenix input. Convention: **antibody / VHH first, antigen last**. For antibody designs (Fab), VH = chain 0, VL = chain 1, antigen = chain 2. For VHH: VHH = chain 0, antigen = chain 1.

---

## 6. Composite Score on Failed Hard Filters

**The mistake**: Computing the composite for a design that failed an ipTM, pLDDT, or RMSD hard filter and reporting it alongside passing designs.

**Why it matters**: A design with ipTM = 0.35 that still has ipSAE_min = 0.6 and no liabilities can produce a composite of ~0.51, which would otherwise land in the BORDERLINE band. But it should not even appear in the ranking — its hard-filter failure means the structural prediction is unreliable.

**Symptom**: Borderline-tier candidates that look "good enough to try" but cannot reproduce in vitro.

**Fix**: Report composite as `--` for any design failing a hard filter. The `scripts/composite_score.py` CLI does this automatically; do not override.

---

## 7. Conflating ipSAE with DockQ or PISA

**The mistake**: Treating ipSAE as a structural geometry score (like DockQ) or a buried-surface-area score (like PISA).

**Why it matters**: ipSAE is a *confidence* score derived from PAE — it measures how confident the predictor is about the interface, not how good the interface geometry actually is. A perfectly designed interface can have low ipSAE if Protenix happens to be uncertain. Conversely, a high ipSAE on a chemically nonsense interface is possible if the predictor confidently places the chains.

**Symptom**: "High ipSAE" designs that look great on paper but show no buried hydrophobic packing on visual inspection.

**Fix**: Always pair ipSAE with at least one geometric metric: buried surface area, shape complementarity, or visual inspection. The `by-screening` skill runs these as secondary filters.

---

## 8. Using BoltzGen's Native ipSAE for Final Ranking

**The mistake**: Reporting BoltzGen's built-in ipSAE (from its own confidence model) as the final ranking metric, without Protenix refolding.

**Why it matters**: BoltzGen's internal ipSAE is computed from its diffusion-model confidence, which is calibrated for generation, not validation. It is useful for early ranking inside the BoltzGen pipeline but is NOT independent validation. Top candidates by BoltzGen ipSAE may collapse when re-scored with Protenix.

**Symptom**: 50%+ of "top by BoltzGen ipSAE" designs lose ranking after Protenix refolding.

**Fix**: Always run Protenix refolding on candidates (top `budget`, e.g., top 200) and use Protenix-derived ipSAE for final ranking. The two-phase workflow (BoltzGen rank -> Protenix re-rank) is mandatory.

---

## 9. Liability Severity Confusion

**The mistake**: Counting all liabilities (LOW + MEDIUM + HIGH) in the composite's liability term.

**Why it matters**: The default `normalized_liability_count` uses **HIGH severity only**. Including MEDIUM and LOW inflates the count and unfairly penalizes designs with cosmetic issues (e.g., one isolated borderline deamidation site in framework, not in CDR).

**Symptom**: Designs with no real manufacturability concerns get composite scores 0.05 - 0.10 lower than they should.

**Fix**: Filter liabilities to HIGH severity before counting. The `mcp__by-screening__screen_liabilities` tool returns severity per finding; aggregate with severity filtering.

---

## 10. Comparing ipSAE Across Modalities Without Adjustment

**The mistake**: Ranking a mixed panel (antibody + nanobody + de novo) by raw ipSAE_min.

**Why it matters**: De novo binders typically reach 0.80+, antibodies 0.65 - 0.80, nanobodies 0.60 - 0.75. A raw cross-modality ranking always puts de novo on top, even when the antibody candidates are better relative to their modality baseline.

**Symptom**: De novo binders dominate "best designs" lists regardless of target tractability.

**Fix**: Rank within modality, or use the modality-adjusted bands in `thresholds-by-modality.md`. If a mixed ranking is required, use a modality-normalized z-score over ipSAE_min.

---

## 11. Ignoring std_ipsae_min in Multi-Seed Output

**The mistake**: Reporting only `best_ipsae_min` from a multi-seed run, ignoring the per-seed standard deviation.

**Why it matters**: `best_ipsae_min = 0.82` with `std_ipsae_min = 0.04` is a confident prediction. `best_ipsae_min = 0.82` with `std_ipsae_min = 0.18` means one lucky seed found a much better conformation than the others — the design is conformationally unstable and likely to disappoint in vitro.

**Symptom**: High-variance picks fail validation; low-variance picks succeed.

**Fix**: Always report mean_ipsae_min and std_ipsae_min alongside best. If `std > 0.15`, downgrade the verdict by one band or recommend additional seeds (40+).

---

## 12. Off-by-One Residue Numbering

**The mistake**: Indexing into PAE matrices with 0-based residue numbers when the manifest expects 1-based, or vice versa.

**Why it matters**: A one-residue shift in chain masks shifts the entire interchain PAE block, changing which residues count as "interface" and silently producing wrong ipSAE values.

**Symptom**: ipSAE values that don't match the BoltzGen / Protenix native scores by ~0.05 - 0.10.

**Fix**: Use `label_seq_id` (1-indexed, sequential) consistently. The `score_npz()` function uses `token_asym_id` from the NPZ, which is already 1-indexed in Protenix outputs.

---

## 13. Reporting a Composite for a Design Without a Liability Scan

**The mistake**: Computing the composite using `normalized_liability_count = 0` because no liability scan was run, then presenting the result as a passable composite.

**Why it matters**: Missing data is not the same as zero. A design with no liability scan should not get full developability credit by default — that silently rewards skipping the scan.

**Symptom**: Composite scores that look 0.20 higher than they should be on incompletely screened panels.

**Fix**: If liability data is missing, report composite as `--` (not 0, not full credit). Force the liability scan as part of the screening pipeline.

---

## 14. Mean pLDDT Without Chain Restriction

**The mistake**: Reporting the mean pLDDT over all chains (design + target) and using it as the design quality metric.

**Why it matters**: A target chain often has pLDDT 90+ (it is the input structure), which can mask a low pLDDT on the design chain. Mean over both chains is dominated by the target.

**Symptom**: pLDDT passes the >70 filter even when the design chain is unfolded.

**Fix**: Always compute pLDDT mean **over the design chain only**. The BY screening pipeline does this; if scoring manually, mask to design chain atoms before averaging.

---

## See Also

- `ipsae-algorithm.md` — formula details that explain why some pitfalls produce specific symptoms.
- `composite-score.md` — full composite formula and weight rationale.
- `thresholds-by-modality.md` — modality-specific cutoffs.
