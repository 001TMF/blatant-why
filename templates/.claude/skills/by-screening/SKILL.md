---
id: "skill_e7c1ce2e57a74e8188dafa78231781c6"
name: "by-screening"
display-name: "BY Screening"
short-description: "Comprehensive screening battery — structural confidence (ipTM/pLDDT/RMSD), ipSAE interface quality, PTM liabilities, and developability filters for protein/antibody designs. Use when triaging design outputs from BoltzGen or PXDesign before lab submission."
category: "filtering"
keywords: "screening, ipSAE, ipTM, pLDDT, RMSD, liabilities, developability, PTM, CDR, antibody, nanobody, filter, triage"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools:
  - "mcp__by-screening__screen_liabilities"
  - "mcp__by-screening__screen_developability"
  - "mcp__by-screening__screen_net_charge"
  - "mcp__by-screening__screen_composite"
  - "mcp__by-screening__screen_diversity"
  - "mcp__by-screening__screen_diagnose_failures"
  - "mcp__by-screening__screen_pareto_front"
  - "mcp__by-screening__screen_align_sequences"
  - "mcp__by-screening__screen_cross_validate"
  - "mcp__by-screening__screen_shape_complementarity"
  - "mcp__by-screening__screen_naturalness"
  - "mcp__by-screening__interpret_scores"
---

# BY Screening Skill

Comprehensive screening battery for evaluating protein binder and antibody designs produced by PXDesign and BoltzGen. This skill encodes all quality filters, scoring thresholds, liability checks, and developability assessments used to triage designs before experimental validation.

Always run the full screening pipeline before presenting final candidates to the user. Never present unscreened designs as ready for validation.

---

## When to Use This Skill

Use **by-screening** when you have:

- ✅ Raw design outputs from BoltzGen or PXDesign with refolding predictions (Protenix NPZ + scores)
- ✅ A set of candidate sequences that need PASS/FAIL classification before lab submission
- ✅ A campaign nearing the `/by:approve-lab` gate — screening MUST run first
- ✅ Designs that need PTM liability and developability triage prior to ranking
- ✅ A need to diagnose batch-level failures (all FAIL ipTM, all FAIL RMSD, etc.)
- ✅ The need to apply diversity clustering before presenting top-N candidates

**Don't use this skill for:**

- ❌ Computing raw scoring metrics → use **by-scoring** (ipSAE NPZ math, composite formula derivation, multi-seed aggregation)
- ❌ Diagnosing root cause of a failed campaign at the *strategy* level → use **by-failure-diagnosis** (modality choice, scaffold selection, target druggability)
- ❌ Generating designs → use **boltzgen** or **pxdesign**
- ❌ Selecting which designs to advance to lab AFTER screening — that is the **by-design-workflow** orchestration step
- ❌ Looking up reference epitopes or target biology → use **by-research**

**Cross-skill hand-off:**

| Situation | Skill to call |
|-----------|---------------|
| Need raw ipSAE/ipTM numbers from NPZ | **by-scoring** first, then this skill |
| Need to apply PASS/FAIL filters to a batch | **by-screening** (this skill) |
| Whole batch fails screening (>80% FAIL) | **by-failure-diagnosis** for strategy correction |
| Designs pass screening, need rank/select | **by-screening** Stage 2 + 3, then **by-design-workflow** |

---

## Quick Start

Run the full composite screen on a single design:

```bash
python scripts/screen_batch.py \
  --designs path/to/designs.csv \
  --modality antibody \
  --output path/to/screened.csv
```

Generate a campaign-ready markdown report:

```bash
python scripts/generate_screening_report.py \
  --screened path/to/screened.csv \
  --output path/to/screening_report.md
```

Parse raw MCP tool output into a tidy table:

```bash
python scripts/parse_scores.py \
  --input raw_mcp_output.json \
  --output scores_tidy.csv
```

Expected runtime: ~2 seconds for 100 designs (pure CPU; no GPU compute).

---

## Inputs

**Required:**

- **Design sequences**: CSV or JSON with columns `name`, `sequence` (single-letter AAs)
- **Scoring metrics**: per-design `iptm`, `plddt` (mean over design chain), `rmsd_ca` (refolding CA-RMSD), `ipsae_min` (from `mcp__by-screening__score_ipsae`)
- **Modality**: one of `antibody`, `nanobody`, `binder` (controls threshold table — see [filter-thresholds.md](references/filter-thresholds.md))

**Optional:**

- **CDR regions**: list of `[start, end]` tuples (0-indexed, end-exclusive) — required for CDR-localized liability triage and CDR length checks
- **Interface residue indices**: list of positions for per-residue pLDDT analysis
- **Dual-predictor scores**: BoltzGen + Protenix ipTM/ipSAE pairs for `screen_cross_validate`
- **CDR pLDDT**: mean pLDDT computed over CDR residues only

**Input format example (CSV):**

```csv
name,sequence,iptm,plddt,rmsd_ca,ipsae_min,modality
d_001,EVQLVESGGGLVQPGGSLR...,0.82,84.5,1.7,0.65,antibody
d_002,QVQLVQSGAEVKKPGAS...,0.45,72.1,4.8,0.32,antibody
```

See [filter-thresholds.md](references/filter-thresholds.md) for the master table of all metrics, defaults, and modality overrides.

---

## Outputs

**Primary results:**

- **Screened CSV** (per-design row): `name`, `verdict` (PASS/FAIL/MARGINAL), `reason_codes` (semicolon-separated), all input scores, plus computed columns `liability_count`, `weighted_liability_count`, `net_charge`, `hydrophobic_fraction`, `total_cdr_length`, `composite_score`
- **Reason codes**: machine-readable failure tags, e.g. `LOW_IPTM`, `FAIL_RMSD`, `CDR_NG`, `ODD_CYS`, `EXTREME_CHARGE`, `LONG_CDR3`
- **PASS rate**: aggregate fraction of designs that cleared all hard filters

**Reports:**

- **Markdown screening report** (`generate_screening_report.py` output):
  - PASS rate summary (overall + per-modality)
  - Distribution histograms (ipTM, pLDDT, RMSD, ipSAE)
  - Top failed criteria (which reason codes are most common)
  - Liability breakdown by location (CDR / interface / framework)
  - Top-N PASS candidates ranked by composite score
- **Tidy scores CSV** (`parse_scores.py` output): one row per design, one column per metric — suitable for downstream notebooks or Pareto-front analysis

**Verdict semantics:**

- `PASS` — clears all Stage 1 hard filters
- `MARGINAL` — clears hard filters but flagged on at least one soft criterion (e.g., interface pLDDT 70–75)
- `FAIL` — one or more hard filters tripped; `reason_codes` lists which

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST.** Before running any screening, always confirm you have the required inputs.

1. **Input data location** (ASK THIS FIRST):
   - Where are the design sequences and refolding scores? (campaign dir, CSV path, NPZ files?)
   - Have you already run `mcp__by-screening__score_ipsae` on the Protenix outputs? If not, run **by-scoring** first.

2. **Modality of the designs**:
   - Antibody (Fv / scFv), nanobody (VHH), or de novo protein binder? Each has different default thresholds (see [filter-thresholds.md](references/filter-thresholds.md)).

3. **CDR annotations**:
   - For antibodies/nanobodies, do you have IMGT or Kabat CDR boundaries? Without them, liability location (CDR vs framework) cannot be assessed.

4. **Screening stringency**:
   - Default thresholds (production-grade), relaxed (exploratory tier, accept marginal), or strict (lab-ready only)?

5. **Output format**:
   - Tidy CSV for downstream analysis, markdown report for the campaign summary, or both?

6. **Cross-validation needed?**:
   - Are these designs heading to `/by:approve-lab`? If yes, dual-predictor cross-validation is REQUIRED.

7. **Failure recovery**:
   - If all designs fail, do you want automatic diagnosis (calls **by-failure-diagnosis**) or a raw failure report?

---

## Standard Workflow

🚨 **MANDATORY: USE SCRIPTS EXACTLY AS SHOWN — DO NOT WRITE INLINE CODE** 🚨

The screening pipeline has three sequential stages plus optional cross-validation. Run them in order.

### Step 1: Parse raw scoring outputs

```bash
python scripts/parse_scores.py \
  --input campaigns/{target}/design_run_{id}/raw_scores.json \
  --output campaigns/{target}/design_run_{id}/scores_tidy.csv
```

✅ **VERIFICATION:** `✓ parsed scores: 247 designs / scores_tidy.csv`

### Step 2: Apply screening battery (hard filters + soft ranking)

```bash
python scripts/screen_batch.py \
  --designs campaigns/{target}/design_run_{id}/scores_tidy.csv \
  --modality nanobody \
  --output campaigns/{target}/design_run_{id}/screened.csv \
  --thresholds-profile production
```

✅ **VERIFICATION:** `✓ screening completed: 247 designs / 38 PASS (15.4%) / 12 MARGINAL / 197 FAIL`

### Step 3: Generate the campaign-ready report

```bash
python scripts/generate_screening_report.py \
  --screened campaigns/{target}/design_run_{id}/screened.csv \
  --output campaigns/{target}/design_run_{id}/screening_report.md
```

✅ **VERIFICATION:** `✓ report written: screening_report.md (PASS rate 15.4%, top reason: LOW_IPTM)`

### Step 4 (optional): Cross-validate with second predictor

Only required when designs are heading to lab. Use `mcp__by-screening__screen_cross_validate`:

```python
mcp__by-screening__screen_cross_validate(
    designs_json='[{"name":"d_001","boltzgen_iptm":0.82,"protenix_iptm":0.78,...}]'
)
```

### Anti-patterns

⚠️ **CRITICAL — DO NOT:**
- ❌ Re-implement the composite formula inline → it lives in `screen_batch.py` and is also a tested MCP tool
- ❌ Hard-code absolute paths in scripts → pass via CLI flags
- ❌ Skip Step 1 and parse MCP output ad-hoc → reason codes will be inconsistent
- ❌ Lower the hard-filter thresholds without documenting why → audit trail required
- ❌ Present FAIL designs as candidates "because they look interesting" → MARGINAL is the only escape valve

---

## When Scripts Fail

Follow the script failure hierarchy:

1. **Fix and Retry (90%)** — Missing package? Install. Schema drift in input CSV? Run `parse_scores.py` first.
2. **Modify Script (5%)** — Threshold needs adjusting for a specific campaign? Edit the script's `THRESHOLDS` dict and re-run.
3. **Use as Reference (4%)** — Custom screening flow? Read scripts, adapt the approach.
4. **Write from Scratch (1%)** — Only if the input format is fundamentally incompatible (e.g., non-protein design). Document the reason.

If the failure is at the *campaign* level (whole batch fails, multiple metrics fail together), stop and call **by-failure-diagnosis** instead of patching scripts.

---

## Decision Points

### Threshold profile selection

| Profile | When to use | Effect |
|---------|-------------|--------|
| `exploratory` | First-pass triage on a novel target | Loosens ipTM to ≥0.4, RMSD to ≤6.0 Å |
| `production` (default) | Standard campaign screening | Defaults from [filter-thresholds.md](references/filter-thresholds.md) |
| `strict` | Lab-ready candidates only | Raises ipTM to ≥0.6, ipSAE-min to ≥0.5 |

### Modality threshold overrides

- **Antibody (Fv/scFv)**: total CDR length ≤70, sequence identity clustering at 90% over CDRs only
- **Nanobody (VHH)**: total CDR length ≤45, CDR-H3 ≤25, lower CDR-H3 pLDDT acceptable (≥60)
- **De novo binder**: no CDR concept; cluster at 70% sequence identity across full chain

### Liability triage decision tree

```
For each liability:
  IF location == CDR AND severity == high      → REJECT design
  ELIF location == interface AND severity == high → MARGINAL + flag
  ELIF location == framework AND severity == high → TOLERABLE, document
  ELSE → ACCEPTABLE, count toward soft ranking penalty (weighted)
```

Weights: CDR=3x, interface=2x, framework=1x. See [liability-rules.md](references/liability-rules.md).

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| Missed liabilities — design later fails QC at the bench | CDR regions not provided, all liabilities scored as framework | Always pass `cdr_regions` via the CSV or MCP call; verify IMGT numbering | [liability-rules.md](references/liability-rules.md) |
| False PASS — designs ranked high but bind weakly in vitro | Skipped dual-predictor cross-validation | Run `screen_cross_validate` before `/by:approve-lab`; require CONSENSUS | SKILL.md "Cross-Validation Protocol" |
| All antibodies FAIL CDR length | Used nanobody threshold (≤45) on a Fab design | Set `--modality antibody`; antibody total CDR limit is ≤70 | [filter-thresholds.md](references/filter-thresholds.md) |
| Net charge artifacts — designs flagged with charge > +10 but look fine | Sequence includes signal peptide or tag | Strip non-design residues before computing charge; use design chain only | [developability-checks.md](references/developability-checks.md) |
| Low CDR-H3 pLDDT triggers REJECT on every nanobody | Generic pLDDT threshold ≥70 applied uniformly | Use nanobody-specific override: CDR-H3 pLDDT ≥60 is acceptable | SKILL.md "pLDDT" section |
| ipSAE_min = 0 across whole batch | NPZ scoring failed silently; PAE matrix missing or chain IDs wrong | Re-run `score_ipsae` with correct `design_chain_ids` / `target_chain_ids` (asym_id integers, not letters) | **by-scoring** skill |
| Odd cysteine count flagged but disulfides are correctly paired | Free Cys check assumes even count = paired; engineered free Cys (e.g., for conjugation) trips it | Add `--allow-free-cys` flag or annotate the engineered Cys in the input CSV | [liability-rules.md](references/liability-rules.md) |
| Hydrophobic fraction always FAIL | Using full IgG sequence including Fc region | Screen variable region only (Fv); Fc is not the design | [developability-checks.md](references/developability-checks.md) |
| Multiple high glycine flags on nanobodies | Nanobody CDR-H3 naturally has Gly-rich loops | Increase glycine threshold to 18% for nanobodies, or treat as MARGINAL not FAIL | [developability-checks.md](references/developability-checks.md) |
| Threshold mismatch — strict profile rejects 100% of designs | Production-grade thresholds applied to exploratory-tier campaign | Switch `--thresholds-profile exploratory`; document in campaign metadata | [filter-thresholds.md](references/filter-thresholds.md) |
| Cross-validation returns DIVERGENT for all designs | BoltzGen and Protenix disagree systematically — usually means input MSA mismatch | Verify both predictors received same target+design pairing; re-run with consistent MSA | SKILL.md "Cross-Validation Protocol" |
| Diversity clustering collapses to one cluster | Using full-chain identity on antibodies (frameworks are conserved) | Use CDR-only identity for antibodies (default); 90% threshold | SKILL.md "Stage 3: Diversity Selection" |
| `screen_composite` returns ipSAE = null | Sequence-only call without NPZ — ipSAE requires structural input | Provide `ipsae` value computed via **by-scoring**'s `score_ipsae`; pass it as input | **by-scoring** skill |
| Net charge differs between Henderson-Hasselbalch and EMBOSS pepstats | Different pKa tables; HH uses Sillero/Lehninger pKas | Default HH values are documented in `compute_net_charge()`; do not mix sources | [developability-checks.md](references/developability-checks.md) |
| All designs PASS screening but fail at lab | Screening passed cross-validation was skipped, or thresholds too loose | Require strict profile + CONSENSUS cross-validation before lab gate | SKILL.md "Cross-Validation Protocol" |

---

## Best Practices

1. 🚨 **CRITICAL:** Always run `parse_scores.py` first — never trust raw MCP output shape; normalize before filtering
2. ✅ **REQUIRED:** Provide CDR regions for every antibody/nanobody design — without them, liability triage is wrong
3. ✅ **REQUIRED:** Pass modality explicitly; thresholds differ by modality (see [filter-thresholds.md](references/filter-thresholds.md))
4. ✅ Set `--thresholds-profile` consciously per campaign tier (preview/standard/production)
5. ✅ For lab-bound designs, require CONSENSUS cross-validation; never bypass
6. ✅ Use weighted liability count (CDR=3x, interface=2x, framework=1x) for ranking, not raw count
7. ✅ Apply diversity clustering before presenting top-N — never show 10 near-identical designs
8. ✅ Persist `screening_report.md` to the campaign directory — it is part of the campaign audit trail
9. ❌ Never lower thresholds silently to "save" a campaign — escalate to **by-failure-diagnosis** instead
10. ✨ **Optional:** Run shape complementarity (`screen_shape_complementarity`) when an interface looks suspicious despite passing other filters

---

## Suggested Next Steps

After screening completes:

- **PASS rate >20%, ≥10 PASS designs** → Use **by-design-workflow** to advance to ranking and lab submission preparation
- **PASS rate <5%** → Call **by-failure-diagnosis** to investigate strategy-level issues (modality choice, hotspots, scaffold)
- **Lab submission pending** → Run `screen_cross_validate` to require CONSENSUS classification before `/by:approve-lab`
- **Need diversity-aware selection** → Use **by-campaign-manager** to record diversity clusters in campaign state
- **Designs ranked, ready to display** → Use **by-display** for standard candidate-table formatting
- **Want learning persistence** → Pass screening verdicts to **by-knowledge** so future campaigns benefit from this batch's outcomes

---

## Related Skills

**Upstream (run before):**
- **by-scoring** — Computes raw ipSAE from Protenix NPZ; feeds into this skill
- **boltzgen** / **pxdesign** — Produce the designs that this skill triages
- **protenix** — Refolds designs to produce ipTM/pLDDT/PAE inputs

**Downstream (run after):**
- **by-design-workflow** — Orchestrates ranking and advancement after screening
- **by-failure-diagnosis** — Investigates root cause when screening eliminates most designs
- **by-display** — Formats final PASS candidates for user-facing presentation

**Alternative/Complementary:**
- **by-epitope-analysis** — When screening fails for interface-related reasons, re-examine epitope choice
- **by-campaign-optimizer** — Active-learning loop that feeds screening outcomes back into design parameters

---

## Structural Screening

Structural confidence metrics come from Protenix refolding predictions.

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
| < 2.0 Å | Excellent | Highly self-consistent design. |
| 2.0 - 3.5 Å | PASS | Acceptable refolding fidelity. |
| 3.5 - 5.0 Å | MARGINAL | Check whether deviations are in loops vs core. |
| > 5.0 Å | REJECT | Does not refold reliably. Likely a structural artifact. |

When RMSD is high, examine per-residue deviation. Isolated loop deviations (especially CDR-H3) are less concerning than core or interface deviations.

---

## Custom Scores

These are BY-specific scoring metrics. See the **by-scoring** skill for algorithmic details.

### ipSAE (Interfacial Predicted Structural Accuracy Error)

TM-align-inspired interface quality from Protenix PAE. Uses the open-source DunbrackLab formula (no proprietary dependencies). Directional: dt_ipsae and td_ipsae. Always report ipsae_min = min(dt, td) as the most stringent assessment.

Reference: Dunbrack et al., "Res ipSAE loquuntur" (2025)

| ipSAE (min) | Interpretation | Action |
|-------------|---------------|--------|
| >= 0.8 | Excellent interface | Top-tier candidate. Prioritize for validation. |
| 0.6 - 0.8 | Good, likely binder | Strong candidate. Proceed through remaining filters. |
| 0.4 - 0.6 | Moderate, possible binder | Include only if other metrics are strong. Consider redesign. |
| < 0.4 | Weak/poor, unlikely to bind | Reject unless retaining for diversity. |

Use `mcp__by-screening__score_ipsae` (lives on the by-screening MCP server; algorithmic ownership documented in **by-scoring**) with a Protenix NPZ. Requires `design_chain_ids` and `target_chain_ids` (asym_id integers). When dt and td diverge (ratio > 2:1), the interface is asymmetric — inspect manually but do not automatically disqualify.

---

## PTM Liability Screening

Sequence motifs causing chemical degradation. Scan every design before advancing. Use `mcp__by-screening__screen_liabilities`.

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

Antibodies require even Cys count for disulfide bonds. Odd count = unpaired Cys = aggregation risk. **Odd Cys count is HIGH severity — reject or investigate.** Even count: verify pairings match expected disulfide topology.

### N-linked Glycosylation

Motif `N[^P][ST]` creates a glycosylation sequon (MEDIUM severity). If in CDR or interface, strongly consider mutating. Framework glycosylation may be tolerable.

### Triage Rules for Liabilities

Location determines severity more than motif type:

1. **CDR liabilities (high severity in CDR)**: REJECT the design or require redesign of the affected CDR. Liabilities in CDR loops directly impact binding and are the highest risk.
2. **Interface liabilities (high severity at interface)**: Strong flag. These can alter binding geometry over time. Consider redesign.
3. **Framework liabilities (high severity)**: TOLERABLE in most cases. Framework regions are more structurally constrained and less exposed. Monitor but do not automatically reject.
4. **Framework liabilities (medium/low severity)**: ACCEPTABLE. Document but do not penalize in ranking.

When counting liabilities for ranking, weight by location: CDR = 3x, interface = 2x, framework = 1x.

---

## Developability Assessment

TAP-inspired filters predicting manufacturability and stability. Use `mcp__by-screening__screen_developability`.

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

Computed via Henderson-Hasselbalch with standard pKa values.

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

When structural coordinates are available, use DBSCAN clustering on solvent-accessible hydrophobic atoms. A single patch exceeding 600 Å² is a strong aggregation signal. For predicted Tm cutoffs and surface-patch tooling (ThermoMPNN etc.), see [developability-checks.md](references/developability-checks.md) and the **by-deploy-compute** skill for tool setup.

---

## Composite Filtering Pipeline

Three stages: hard filters (binary pass/fail), soft ranking (continuous scores), diversity selection.

### Stage 1: Hard Filters

Binary pass/fail. Any failure eliminates the design. Apply all simultaneously and report which filter(s) caused rejection.

| Filter | Criterion | Rationale |
|--------|-----------|-----------|
| ipTM | >= 0.5 | Interface prediction unreliable below this. |
| pLDDT (interface mean) | >= 70 | Low confidence invalidates other metrics. |
| CA-RMSD | <= 5.0 Å | Does not refold. Structural hypothesis invalid. |
| Free cysteine | Even Cys count | Unpaired Cys causes aggregation. Non-negotiable. |
| CDR liability | No NG or DG in CDRs | Rapid degradation at binding site. |
| Extreme charge | abs(charge) <= 10 | Developability compromised. |
| Hydrophobic fraction | <= 0.55 | Severe aggregation risk. |

### Stage 2: Soft Ranking

Designs that pass all hard filters are ranked by a composite score.

**Ranking formula:**

```
composite = 0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)
```

Where:
- `ipSAE_min` = ipsae_min value (already 0-1)
- `ipTM` = ipTM value (already 0-1)
- `normalized_liability_count` = weighted_liability_count / max_liability_count_in_batch, clamped to [0, 1]

Present the top designs sorted by composite score descending.

### Stage 3: Diversity Selection

Ensure sequence diversity among top-ranked designs. Do not present 10 designs that are >95% identical.

1. Cluster passing designs by sequence identity (90% for antibodies, 70% for protein binders).
2. From each cluster, select the highest-composite-scoring representative.
3. Present one design per cluster, ordered by composite score.
4. Report cluster sizes so the user knows how many similar alternatives exist.

For antibody designs, compute sequence identity over CDR regions only (not framework), since frameworks are largely conserved.

---

## Cross-Validation Protocol (Dual Predictor)

After composite ranking, take the top N candidates (default: top 10 or top 20% of survivors) and validate with a second structure predictor to filter out false positives.

### Step 1: Submit Refolding Jobs

For each top candidate, submit to a second predictor:
- Use local Protenix when available (preferred; see **by-deploy-compute** for setup)
- Fall back to HPC (RunPod) per `compute.providers_priority`
- Tamarind is the cloud-of-last-resort fallback
- Include both design and target sequences in the submission

### Step 2: Compare Predictions

| Metric | Threshold | Description |
|--------|-----------|-------------|
| ipTM agreement | \|predictor1_ipTM - predictor2_ipTM\| < 0.3 | Interface confidence must converge |
| ipSAE agreement | Both > 0.3 | Both predictors see a viable interface |
| Pose RMSD | CA-RMSD < 3.0 Å between predictions | Structural poses must agree |

### Step 3: Classification

| Status | Criteria | Confidence | Action |
|--------|----------|------------|--------|
| CONSENSUS | All thresholds pass | HIGH | Advance to lab submission |
| DIVERGENT | One metric fails | MEDIUM | Flag for manual review |
| REJECTED | ipTM delta > 0.5 OR both ipSAE < 0.1 | LOW | Remove from candidate set |

### When to Run

- **Always**: When candidates will be submitted to lab (`/by:approve-lab` pending)
- **Skip**: Preview campaigns, iteration rounds where compute budget is tight

### MCP Tool

Use `mcp__by-screening__screen_cross_validate` to run programmatic cross-validation on a batch of designs with dual-predictor scores. Input: JSON array of design objects with scores from both predictors. Output: classification, confidence, and formatted report.

---

## Failure Recovery

When screening eliminates all or most designs, do not simply report failure. Diagnose the cause and recommend corrective action. For deep root-cause investigation, escalate to **by-failure-diagnosis**.

### All Designs Fail ipTM (< 0.5)

The target-design interface is not forming a confident complex. Recovery:
1. Re-examine the target structure — epitope accessibility, crystal packing, missing cofactors.
2. Try different hotspot residues. Current hotspots may not be druggable.
3. For BoltzGen: switch between nanobody-anything and antibody-anything protocols.
4. For PXDesign: try the extended preset with more backbone samples.
5. Check whether the target is intrinsically disordered at the binding site (AlphaFold pLDDT).

### All Designs Fail RMSD (> 5.0 Å)

Designs do not refold to their designed conformation. Recovery:
1. Increase refolding samples (5 to 20) to improve conformational sampling.
2. Check if deviations are in loops vs core. Loop RMSD is less concerning.
3. If pLDDT is high but RMSD is high, design may refold to a different valid conformation.
4. Reduce design complexity: shorter CDR-H3, fewer mutations from template.
5. Run Protenix on just the design chain (no target) to check intrinsic stability.

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

The following MCP tools are available via the by-screening server for programmatic screening.

### `mcp__by-screening__screen_liabilities`

Scan a protein sequence for PTM liabilities (deamidation, isomerization, oxidation, free cysteines, glycosylation motifs).

Input: `{ "sequence": "EVQLV..." }`
Output: List of `Liability` objects with type, position, motif, severity, and description.

### `mcp__by-screening__screen_developability`

Run TAP-inspired developability assessment on a design sequence.

Input: `{ "sequence": "EVQLV...", "cdr_regions": [[26,35], [50,66], [93,102]] }`
Output: `DevelopabilityReport` with total_cdr_length, net_charge, liability_count, hydrophobic_fraction, proline_fraction, glycine_fraction, overall_risk, flags.

### `mcp__by-screening__screen_net_charge`

Compute net charge at a specified pH using Henderson-Hasselbalch.

Input: `{ "sequence": "EVQLV...", "ph": 7.4 }`
Output: `{ "net_charge": float }`

### `mcp__by-screening__screen_composite`

Run the full three-stage screening pipeline on a design.

Input: `{ "sequence": "EVQLV...", "iptm": 0.85, "ipsae": 0.72, "plddt": 82.3, "rmsd": 1.5 }`
Output: Composite PASS/FAIL verdict with liabilities, developability, scores, interpretation, and flags.

### `mcp__by-screening__interpret_scores`

Generate human-readable interpretation of scoring metrics for a single design.

Input: `{ "iptm": 0.85, "ipsae": 0.72, "plddt": 82.3 }`
Output: JSON with per-metric interpretation and summary.

### `mcp__by-screening__screen_diversity`

Cluster a batch of designs by sequence identity and return cluster assignments.

### `mcp__by-screening__screen_diagnose_failures`

Aggregate-level diagnosis of why a batch failed (which filter dominated). For strategy-level root cause, escalate to **by-failure-diagnosis**.

### `mcp__by-screening__screen_pareto_front`

Multi-objective Pareto-front selection across configurable metrics (default: ipsae_min maximize, liability_count minimize).

### `mcp__by-screening__screen_align_sequences`

Pairwise/multiple sequence alignment for diversity analysis.

### `mcp__by-screening__screen_cross_validate`

Cross-validate designs using dual-predictor scores. Classifies each design as CONSENSUS (high confidence), DIVERGENT (medium, needs review), or REJECTED (low confidence, remove).

Input: `{ "designs_json": "[{\"name\": \"d1\", \"boltzgen_iptm\": 0.8, \"protenix_iptm\": 0.75, \"boltzgen_ipsae\": 0.6, \"protenix_ipsae\": 0.55}]" }`
Output: JSON with per-design classification (status, confidence, ipTM delta, ipSAE agreement) and summary counts.

### `mcp__by-screening__screen_shape_complementarity`

Compute Sc (Lawrence & Colman) for an interface — useful when ipTM looks high but binding is uncertain.

### `mcp__by-screening__screen_naturalness`

Score sequence naturalness against a reference protein language model. Low naturalness can indicate design artifacts.

---

## Quick Reference Card

```
HARD FILTERS (any fail = reject):
  ipTM >= 0.5    pLDDT >= 70    CA-RMSD <= 5.0 Å
  Even Cys count    No NG/DG in CDRs    |charge| <= 10    hydro_frac <= 0.55

RANKING WEIGHTS:
  ipSAE_min: 0.50    ipTM: 0.30    liability_penalty: 0.20

LIABILITY TRIAGE:
  CDR + high severity    = REJECT
  Interface + high sev   = STRONG FLAG
  Framework + high sev   = TOLERABLE
  Framework + med/low    = ACCEPTABLE

CROSS-VALIDATION (dual predictor):
  CONSENSUS: ipTM delta < 0.3, both ipSAE > 0.3 -> HIGH confidence
  DIVERGENT: one metric fails -> MEDIUM confidence
  REJECTED: ipTM delta > 0.5 or both ipSAE < 0.1 -> LOW confidence

DIVERSITY CLUSTERING:
  Antibodies: 90% seq ID over CDRs
  Protein binders: 70% seq ID overall
```

---

## Screening Battery Summary

Always run before presenting final candidates. Never present unscreened designs as final.

### Liabilities
- NG/NS deamidation sites
- DG isomerization sites
- Met oxidation (exposed methionines)
- Free Cys (unpaired cysteines)
- NXS/T glycosylation motifs (N-linked)

### Developability
- Net charge at pH 7.4
- CDR loop lengths (flag outliers)
- Hydrophobic fraction
- Composition flags (unusual amino acid distributions)

### Structure
- ipTM > 0.5 (minimum PASS)
- pLDDT > 70 (minimum PASS)
- RMSD < 3.5 Å (minimum PASS)

---

## Hotspot Identification

When analyzing interface residues, classify each as:
- **Core packing**: Hydrophobic, BSA > 100 Å²
- **Polar anchor**: Tyr/Trp/His forming H-bonds at interface
- **Salt bridge**: Charged residues paired across interface
- **H-bond network**: Polar residues (Asn/Gln/Ser/Thr)
- **Buried contact**: BSA > 50 Å² at interface core
- **Rim contact**: Peripheral, BSA < 50 Å²

Present as a residue table with AA, Type, BSA, Classification columns. End with recommended hotspot array and range notation for entities YAML.

---

## References

**Detailed documentation (this skill's references/):**
- [references/filter-thresholds.md](references/filter-thresholds.md) — Master table of every screening filter with default thresholds, modality overrides, rationale, and citation.
- [references/liability-rules.md](references/liability-rules.md) — Each PTM/sequence liability with regex/algorithm and severity classification.
- [references/developability-checks.md](references/developability-checks.md) — CDR analysis, charge distribution, hydrophobic patch detection, predicted Tm cutoffs.

**Scripts (this skill's scripts/):**
- `scripts/screen_batch.py` — Apply all configured filters to a CSV/JSON batch; emit PASS/FAIL with reason codes
- `scripts/parse_scores.py` — Normalize raw MCP tool output (JSON) into a tidy per-design CSV
- `scripts/generate_screening_report.py` — Render a campaign-ready markdown report from a screened CSV

**Related skills:**
- **by-scoring** — Owns ipSAE algorithmic details and multi-seed aggregation
- **by-failure-diagnosis** — Strategy-level root cause when whole batches fail
- **by-deploy-compute** — Setup for Protenix/BoltzGen/PXDesign across local/HPC/Tamarind

**Key Papers:**
- Dunbrack et al., "Res ipSAE loquuntur" (2025) — ipSAE formulation
- Raybould et al., "Five computational developability guidelines for therapeutic antibody profiling" (TAP, 2019)
- Robinson et al., "Charge-based interactions and antibody developability" (2017)
- Lawrence & Colman, "Shape complementarity at protein/protein interfaces" (1993)

**License:** All packages and reference algorithms used in this skill permit commercial use in AI applications.
