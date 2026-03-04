# Proteus Screening Skill

Comprehensive screening battery for evaluating protein binder and antibody designs produced by proteus-prot (PXDesign) and proteus-ab (Proteus-AB). This skill encodes all quality filters, scoring thresholds, liability checks, and developability assessments used to triage designs before experimental validation.

Always run the full screening pipeline before presenting final candidates to the user. Never present unscreened designs as ready for validation.

---

## Structural Screening

Structural confidence metrics come from Protenix (proteus-fold) refolding predictions.

### ipTM (Interface Predicted TM-score)

| ipTM Range | Verdict | Action |
|------------|---------|--------|
| > 0.7 | PASS | High confidence interface. Proceed to further screening. |
| 0.5 - 0.7 | MARGINAL | Viable but cautious. Examine PAE maps for local disorder. Consider more refolding samples. |
| < 0.5 | REJECT | Interface prediction unreliable. Do not advance. |

Also check pTM (global TM-score). High ipTM with low pTM suggests the overall fold may be wrong even if the interface looks plausible.

### pLDDT (Predicted Local Distance Difference Test)

Report mean pLDDT over the design chain and over interface residues separately.

| pLDDT Range | Level | Interpretation |
|-------------|-------|----------------|
| > 90 | Excellent | Backbone and sidechain placement are reliable. |
| 80 - 90 | High | Good confidence. Minor rotamer uncertainty acceptable. |
| 70 - 80 | Moderate | Backbone likely correct, sidechains uncertain. Check interface residues individually. |
| < 70 | Low | Unreliable. If interface residues fall here, flag the design. |

For antibodies: CDR-H3 commonly has lower pLDDT due to intrinsic flexibility; values above 60 in CDR-H3 are acceptable if other CDRs are above 80.

### RMSD (Root Mean Square Deviation)

Use CA-RMSD (alpha-carbon only) from independent refolding as the primary designability metric.

| CA-RMSD | Verdict | Interpretation |
|---------|---------|----------------|
| < 2.0 A | Excellent | Highly self-consistent design. |
| 2.0 - 3.5 A | PASS | Acceptable refolding fidelity. |
| 3.5 - 5.0 A | MARGINAL | Check whether deviations are in loops vs core. |
| > 5.0 A | REJECT | Does not refold reliably. Likely a structural artifact. |

When RMSD is high, examine per-residue deviation. Isolated loop deviations (especially CDR-H3) are less concerning than core or interface deviations.

---

## Custom Scores

These are Proteus-specific scoring metrics. See the proteus-scoring skill for algorithmic details.

### ipSAE (Interfacial Predicted Structural Accuracy Error)

TM-align-inspired interface quality from Protenix PAE. Directional: dt_ipsae and td_ipsae. Always report design_ipsae_min = min(dt, td) as the most stringent assessment.

| ipSAE (min) | Interpretation | Action |
|-------------|---------------|--------|
| > 0.8 | Excellent interface | Top-tier candidate. Prioritize for validation. |
| 0.5 - 0.8 | Good, likely binder | Strong candidate. Proceed through remaining filters. |
| 0.3 - 0.5 | Moderate, possible binder | Include only if other metrics are strong. Consider redesign. |
| < 0.3 | Poor, unlikely to bind | Reject unless retaining for diversity. |

Use `score_ipsae` MCP tool or `proteus_cli.scoring.ipsae.score_npz()` with Protenix NPZ. Requires design_chain_ids and target_chain_ids (asym_id integers). When dt and td diverge (ratio > 2:1), the interface is asymmetric -- inspect manually but do not automatically disqualify.

### p_bind (Binding Probability)

Learned binding probability from a 3-layer MLP on Protenix trunk features. Requires a trained checkpoint.

| p_bind | Interpretation | Action |
|--------|---------------|--------|
| > 0.8 | High confidence binder | Weight heavily in ranking. |
| 0.5 - 0.8 | Likely binder | Combine with structural metrics for ranking. |
| 0.3 - 0.5 | Marginal | Only advance if ipTM and ipSAE are strong. |
| < 0.3 | Unlikely to bind | Deprioritize. Retain only for diversity. |

If no checkpoint is available, skip this metric and note "p_bind: not available (awaiting trained model)" in the report. Never fabricate scores. Use `score_pbind` MCP tool or `proteus_cli.scoring.pbind.predict_binding()`. Critical: chain_design_mask must cover FULL VH/VL chains (not CDR-only). CDR-only mask (v1) ROC 0.60; full-chain mask (v2) ROC 0.906.

---

## PTM Liability Screening

Sequence motifs causing chemical degradation. Scan every design before advancing. Use `screen_liabilities` MCP tool or `proteus_cli.screening.liabilities.scan_liabilities()`.

### Deamidation

Asn followed by specific residues converts to Asp/isoAsp, altering charge and structure.

| Motif | Severity | Notes |
|-------|----------|-------|
| NG | HIGH | Fastest rate, half-life can be days. Almost always problematic. |
| NS | MEDIUM | Context-dependent. Buried NS is lower risk. |
| NT | MEDIUM | Similar to NS. Check solvent exposure. |
| NA | LOW | Slow. Monitor but do not reject on this alone. |

### Isomerization

Asp can isomerize to isoAsp, disrupting backbone geometry.

| Motif | Severity | Notes |
|-------|----------|-------|
| DG | HIGH | Rapid. Glycine provides no steric protection. Flag in CDRs especially. |
| DS | MEDIUM | Moderate rate. Context-dependent. |

### Oxidation

| Residue | Severity | Notes |
|---------|----------|-------|
| Met (M) | MEDIUM | Sulfoxide formation. Flag in CDR/interface positions. Framework Met is lower risk. |
| Trp (W) | LOW | Slower oxidation. Flag only in direct contact residues. |

### Free Cysteines

Antibodies require even Cys count for disulfide bonds. Odd count = unpaired Cys = aggregation risk. **Odd Cys count is HIGH severity -- reject or investigate.** Even count: verify pairings match expected disulfide topology.

### N-linked Glycosylation

Motif N[^P][ST] creates a glycosylation sequon (MEDIUM severity). If in CDR or interface, strongly consider mutating. Framework glycosylation may be tolerable.

### Triage Rules for Liabilities

Location determines severity more than motif type:

1. **CDR liabilities (high severity in CDR)**: REJECT the design or require redesign of the affected CDR. Liabilities in CDR loops directly impact binding and are the highest risk.
2. **Interface liabilities (high severity at interface)**: Strong flag. These can alter binding geometry over time. Consider redesign.
3. **Framework liabilities (high severity)**: TOLERABLE in most cases. Framework regions are more structurally constrained and less exposed. Monitor but do not automatically reject.
4. **Framework liabilities (medium/low severity)**: ACCEPTABLE. Document but do not penalize in ranking.

When counting liabilities for ranking, weight by location: CDR = 3x, interface = 2x, framework = 1x.

---

## Developability Assessment

TAP-inspired filters predicting manufacturability and stability. Use `screen_developability` MCP tool or `proteus_cli.screening.developability.assess_developability()`.

### TAP 5 Guidelines Summary

Five properties correlated with clinical-stage antibody success: (1) CDR length, (2) surface hydrophobicity patches, (3) net charge at physiological pH, (4) sequence composition, (5) aggregation-prone structural motifs.

### CDR Length Limits

| Metric | Threshold | Verdict | Notes |
|--------|-----------|---------|-------|
| Total CDR length (6 CDRs) | < 55 residues | Ideal | Well within clinical antibody distribution. |
| Total CDR length (6 CDRs) | 55 - 70 residues | Acceptable | Upper range but still developable. |
| Total CDR length (6 CDRs) | > 70 residues | FLAG | Unusually long CDRs. Higher aggregation risk, harder to manufacture. |
| Total CDR length (3 CDRs, nanobody) | < 35 residues | Ideal | Nanobodies naturally have longer CDR-H3. |
| Total CDR length (3 CDRs, nanobody) | > 45 residues | FLAG | Very long for a nanobody. Check CDR-H3 specifically. |

CDR-H3 is the most variable loop. Lengths 10-15 are typical; above 20 is unusual.

### Net Charge at pH 7.4

Computed via Henderson-Hasselbalch with standard pKa values (`proteus_cli.screening.liabilities.compute_net_charge()`).

| Net Charge | Verdict | Notes |
|------------|---------|-------|
| -2 to +5 | IDEAL | Optimal range for solubility and viscosity. Most approved antibodies fall here. |
| +5 to +8 | ACCEPTABLE | Slightly positive. May increase nonspecific binding (polyreactivity). |
| -5 to -2 | ACCEPTABLE | Slightly negative. Generally fine for solubility. |
| > +8 or < -5 | FLAG | Extreme charge. Risk of poor pharmacokinetics, high viscosity, or aggregation. |
| > +10 or < -10 | REJECT | Very likely to have developability issues. Redesign required. |

### Hydrophobic Fraction

Fraction of hydrophobic amino acids (A, I, L, M, F, W, V, P) in the design chain.

| Hydrophobic Fraction | Verdict | Notes |
|---------------------|---------|-------|
| < 0.35 | Good | Favorable solubility. |
| 0.35 - 0.45 | Acceptable | Normal range for antibodies. |
| > 0.45 | FLAG | Risk of aggregation and nonspecific binding. |
| > 0.55 | REJECT | Almost certain developability problems. |

### Composition Flags

| Flag | Condition | Severity | Notes |
|------|-----------|----------|-------|
| High glycine | Gly > 15% | MEDIUM | Excessive flexibility, possible design artifact. |
| High proline | Pro > 10% | LOW | Can disrupt beta-sheet structure in frameworks. |
| Low diversity | Any single AA > 20% | MEDIUM | Composition bias, possibly degenerate design. |
| Absent conserved | Missing canonical residues | HIGH | Check for conserved Trp, Cys, structural residues. |

### Hydrophobic Patches (Advanced)

When structural coordinates are available, use DBSCAN clustering on solvent-accessible hydrophobic atoms. A single patch exceeding 600 A^2 is a strong aggregation signal. Reported in proteus-ab results CSV.

---

## Composite Filtering Pipeline

Three stages: hard filters (binary pass/fail), soft ranking (continuous scores), diversity selection.

### Stage 1: Hard Filters

Binary pass/fail. Any failure eliminates the design. Apply all simultaneously and report which filter(s) caused rejection.

| Filter | Criterion | Rationale |
|--------|-----------|-----------|
| ipTM | >= 0.5 | Interface prediction unreliable below this. |
| pLDDT (interface mean) | >= 70 | Low confidence invalidates other metrics. |
| CA-RMSD | <= 5.0 A | Does not refold. Structural hypothesis invalid. |
| Free cysteine | Even Cys count | Unpaired Cys causes aggregation. Non-negotiable. |
| CDR liability | No NG or DG in CDRs | Rapid degradation at binding site. |
| Extreme charge | abs(charge) <= 10 | Developability compromised. |
| Hydrophobic fraction | <= 0.55 | Severe aggregation risk. |

### Stage 2: Soft Ranking

Designs that pass all hard filters are ranked by a composite score. Each metric contributes to a weighted sum.

**Ranking formula:**

```
composite = (0.30 * norm_iptm) + (0.25 * norm_ipsae) + (0.20 * norm_pbind) + (0.15 * norm_liability) + (0.10 * norm_developability)
```

Where:
- `norm_iptm` = ipTM value (already 0-1)
- `norm_ipsae` = design_ipsae_min (already 0-1)
- `norm_pbind` = p_bind probability (already 0-1; use 0.5 if unavailable)
- `norm_liability` = 1.0 - (weighted_liability_count / max_liability_count_in_batch), clamped to [0, 1]
- `norm_developability` = 1.0 if risk=="low", 0.5 if risk=="medium", 0.0 if risk=="high"

If p_bind is not available (no trained checkpoint), redistribute its weight equally to ipTM and ipSAE:

```
composite_no_pbind = (0.40 * norm_iptm) + (0.35 * norm_ipsae) + (0.15 * norm_liability) + (0.10 * norm_developability)
```

Present the top designs sorted by composite score descending.

### Stage 3: Diversity Selection

Ensure sequence diversity among top-ranked designs. Do not present 10 designs that are >95% identical.

1. Cluster passing designs by sequence identity (90% for antibodies, 70% for protein binders).
2. From each cluster, select the highest-composite-scoring representative.
3. Present one design per cluster, ordered by composite score.
4. Report cluster sizes so the user knows how many similar alternatives exist.

For antibody designs, compute sequence identity over CDR regions only (not framework), since frameworks are largely conserved.

---

## Failure Recovery

When screening eliminates all or most designs, do not simply report failure. Diagnose the cause and recommend corrective action.

### All Designs Fail ipTM (< 0.5)

The target-design interface is not forming a confident complex. Recovery:
1. Re-examine the target structure -- epitope accessibility, crystal packing, missing cofactors.
2. Try different hotspot residues. Current hotspots may not be druggable.
3. For proteus-ab: switch between nanobody-anything and antibody-anything protocols.
4. For proteus-prot: try the extended preset with more backbone samples.
5. Check whether the target is intrinsically disordered at the binding site (AlphaFold pLDDT).

### All Designs Fail RMSD (> 5.0 A)

Designs do not refold to their designed conformation. Recovery:
1. Increase refolding samples (5 to 20) to improve conformational sampling.
2. Check if deviations are in loops vs core. Loop RMSD is less concerning.
3. If pLDDT is high but RMSD is high, design may refold to a different valid conformation.
4. Reduce design complexity: shorter CDR-H3, fewer mutations from template.
5. Run proteus-fold on just the design chain (no target) to check intrinsic stability.

### All Designs Have PTM Liabilities

Recovery:
1. Filter to fewest liabilities, not zero. Some liabilities are tolerable.
2. Separate CDR vs framework liabilities. Framework is usually acceptable.
3. For NG/DG: try conservative mutations (NG->NA, DG->DA) at non-contact positions.
4. Accept medium-severity liabilities (NS, NT, DS) in framework if no alternatives exist.

### All Designs Fail Developability

Recovery:
1. Identify which flag triggers: charge, hydrophobicity, CDR length, or composition.
2. Charge: consider charge-neutralizing mutations at non-contact positions.
3. Hydrophobicity: single-point mutations (e.g., Leu->Thr) at non-contact surface positions.
4. CDR length: consider shorter-loop template.
5. Relax soft thresholds if structural metrics are excellent (ipTM 0.9 + slight charge excess is still testable).

### Few Designs Pass All Filters

When only 1-3 designs survive from a batch of 30+, this is a common and acceptable outcome. Present passing designs with full scoring details, report attrition per stage, and recommend a second campaign with adjusted parameters if more diversity is needed.

---

## MCP Tools Reference

The following MCP tools are available via the proteus-screening server for programmatic screening.

### screen_liabilities

Scan a protein sequence for PTM liabilities (deamidation, isomerization, oxidation, free cysteines, glycosylation motifs).

Input: `{ "sequence": "EVQLV...", "cdr_regions": [[26,35], [50,66], [93,102]] }`
Output: List of `Liability` objects with type, position, motif, severity, description. Liabilities within CDR regions are annotated with `in_cdr: true`.

### screen_developability

Run TAP-inspired developability assessment on a design sequence.

Input: `{ "sequence": "EVQLV...", "cdr_regions": [[26,35], [50,66], [93,102]] }`
Output: `DevelopabilityReport` with total_cdr_length, net_charge, liability_count, hydrophobic_fraction, proline_fraction, glycine_fraction, overall_risk, flags.

### screen_composite

Run the full three-stage screening pipeline on a batch of designs.

Input: `{ "designs": [{"id": "design-1", "sequence": "...", "iptm": 0.85, "plddt": 82.3, "rmsd": 1.5, "ipsae_min": 0.72, "pbind": 0.88, "cdr_regions": [...]}] }`
Output: Ordered list of passing designs with composite scores, rejection reasons for filtered designs, cluster assignments for diversity, and attrition summary per stage.

### interpret_scores

Generate human-readable interpretation of all scoring metrics for a single design.

Input: `{ "iptm": 0.85, "plddt": 82.3, "rmsd": 1.5, "ipsae_min": 0.72, "pbind": 0.88, "liability_count": 2, "high_severity_count": 0, "developability_risk": "low" }`
Output: Markdown-formatted interpretation with verdict for each metric and overall recommendation.

---

## Quick Reference Card

```
HARD FILTERS (any fail = reject):
  ipTM >= 0.5    pLDDT >= 70    CA-RMSD <= 5.0 A
  Even Cys count    No NG/DG in CDRs    |charge| <= 10    hydro_frac <= 0.55

RANKING WEIGHTS (when p_bind available):
  ipTM: 0.30    ipSAE: 0.25    p_bind: 0.20    liabilities: 0.15    developability: 0.10

RANKING WEIGHTS (without p_bind):
  ipTM: 0.40    ipSAE: 0.35    liabilities: 0.15    developability: 0.10

LIABILITY TRIAGE:
  CDR + high severity    = REJECT
  Interface + high sev   = STRONG FLAG
  Framework + high sev   = TOLERABLE
  Framework + med/low    = ACCEPTABLE

DIVERSITY CLUSTERING:
  Antibodies: 90% seq ID over CDRs
  Protein binders: 70% seq ID overall
```
