---
id: "skill_4e182a2c2fad4dcd97f1f24db39eb949"
name: "by-experiment-results"
display-name: "BY Experiment Results"
short-description: "Closes the wet-lab feedback loop — ingests lab readouts (Adaptyv batch CSVs, internal ELISA/BLI/Octet, expression QC), joins them to in-silico features per design_id, diagnoses which predictions matched reality, and pipes calibration findings into the optimizer and knowledge graph. Use when a lab readout file arrives, when validating round-N predictions against round-N-1 lab data, or when computing calibration metrics across an internal screening batch."
category: "diagnosis"
keywords: "lab readout, experimental validation, calibration, in-silico vs in-vitro, wet-lab feedback, ELISA, BLI, Octet, Adaptyv, ground truth, precision at K, Mann-Whitney, validated finding, falsified finding"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: ["mcp__by-adaptyv__adaptyv_get_results", "mcp__by-knowledge__knowledge_store_campaign", "mcp__by-knowledge__knowledge_store_failure"]
---

# BY Experiment Results Skill

A design campaign only learns when lab outcomes are joined back to the in-silico predictions that produced them. This skill is the wet-lab feedback loop closer: it ingests lab readouts (Adaptyv batch CSVs, internal ELISA plate-reader output, BLI/Octet kinetics, expression QC), joins them to the per-design feature table the screener emitted, and runs a calibration analysis that asks one question for every in-silico feature:

> **Did this feature actually predict whether the design worked in the lab?**

The answer for each feature is one of: **validated** (in-silico PASS correlated with lab PASS), **contradicted** (predictor pointed the opposite direction), or **inconclusive** (no signal). The diagnosis goes into the knowledge graph with that confidence label so future campaigns start from real-world-calibrated priors, not silicon-only priors.

This skill sits between **by-screening** (which produces in-silico PASS/FAIL) and **by-campaign-optimizer** (which trains the next round). It is the only skill in BY that consumes **ground-truth lab data**.

---

## When to Use This Skill

✅ **Use this skill when:**
- A lab readout file (CSV or Excel) has arrived from Adaptyv Bio for a previously submitted batch
- An internal ELISA, BLI, or Octet run has produced a tidy results table for designs the BY pipeline scored
- You need to validate round-N in-silico predictions against round-N-1 lab outcomes
- A user asks "did our predictions hold up?", "calibrate the screener", or "did ipSAE correlate with Kd?"
- A round of designs has come back from the lab and you need to update the campaign-optimizer training data with ground truth
- You want to write a **calibration report** showing precision at top-K and lift over random
- You want to publish findings to the knowledge graph as **validated** or **contradicted** with confidence levels

❌ **Don't use this skill for:**
- A campaign that has not yet been submitted to lab — there is no ground truth to compare. Use **by-screening** + **by-failure-diagnosis** first.
- Pre-submission ranking of designs — that is **by-screening** and **by-design-workflow**.
- Computing raw in-silico scores from PDB / NPZ — use **by-scoring**.
- Diagnosing why a campaign produced low in-silico pass rate — use **by-failure-diagnosis** (no lab data needed).
- Lab submission itself — use the gated `/by:approve-lab` flow and **by-adaptyv** MCP tools.
- Curating raw structural files (CIF / PDB) — those stay in the campaign directory.

---

## Quick Start

The shortest path from a lab CSV to a calibration report and knowledge-graph update is three CLI calls:

```bash
# 1) Normalize the lab readout to canonical schema
python3 scripts/ingest_lab_results.py \
    --input  experiments/batch_001_adaptyv.csv \
    --output campaigns/<target>/<campaign_id>/lab_results.normalized.json \
    --assay  affinity_bli \
    --aggregate median

# 2) Join with in-silico features and run calibration
python3 scripts/diagnose_silico_vs_lab.py \
    --lab          campaigns/<target>/<campaign_id>/lab_results.normalized.json \
    --silico       campaigns/<target>/<campaign_id>/screening_results.json \
    --output-json  campaigns/<target>/<campaign_id>/calibration.json \
    --output-md    campaigns/<target>/<campaign_id>/calibration_report.md

# 3) Push validated / contradicted findings to the knowledge graph
python3 scripts/update_knowledge_from_lab.py \
    --calibration campaigns/<target>/<campaign_id>/calibration.json \
    --campaign-id <campaign_id> \
    --target      <target>
```

✅ **VERIFICATION:** `calibration.json` contains a `features[]` array where each feature has a `verdict` of `validated`, `contradicted`, or `inconclusive`, and `calibration_report.md` opens with a one-line headline like "12 / 18 lab-tested designs bound (67%); ipSAE_min was the strongest validated predictor (p=0.004, AUC=0.81)."

---

## Installation

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| Python | >= 3.10 | PSF | ✅ Permitted | system |
| pandas | >= 2.0 | BSD-3 | ✅ Permitted | `pip install pandas` |
| numpy | >= 1.24 | BSD-3 | ✅ Permitted | `pip install numpy` |
| scipy | >= 1.11 | BSD-3 | ✅ Permitted | `pip install scipy` |
| openpyxl | >= 3.1 | MIT | ✅ Permitted | `pip install openpyxl` (only for `.xlsx` ingestion) |
| scikit-learn | >= 1.3 | BSD-3 | ✅ Permitted | `pip install scikit-learn` (for AUC in calibration) |

**License Compliance:** All third-party packages permit commercial use in AI applications.

**System requirements:** CPU-only; no GPU; no internet (unless pulling Adaptyv results via the MCP tool). All scripts run in seconds for batches up to ~1,000 designs.

---

## Inputs

**Required:**
- **Lab readout file** (CSV or Excel; `.csv` / `.tsv` / `.xlsx`):
  - Must contain a `design_id` column (canonical) **or** a renameable alias mapped via `--alias design_id=<src>`. The `design_id` MUST match the identifiers used in the campaign's `screening_results.json`.
  - Must contain a ground-truth outcome column. Acceptable shapes:
    - **Categorical**: `lab_outcome` ∈ {`PASS`, `FAIL`} or {`binder`, `no-binder`} — set via `--outcome-col` and `--outcome-pass-value`.
    - **Continuous Kd (nM)**: `kd_nm` with a `--kd-threshold-nm` flag (default 100 nM) to derive PASS/FAIL.
    - **Continuous binding signal**: `binding_signal` (a.u.) with `--binding-threshold` flag.
  - Optional columns: `ka_per_M_per_s`, `kd_per_s`, `expression_mg_per_L`, `polyspecificity_score`, `aggregation_pct`, `replicate_id`.
- **In-silico feature file** (`screening_results.json` from **by-screening**, or a CSV):
  - One row per design, with a `design_id` column and any subset of: `ipsae`, `ipsae_min`, `iptm`, `plddt`, `rmsd`, `liabilities`, `cdr3_length`, `net_charge`, `hydrophobic_fraction`, `aggregation_predicted`, `polyspecificity_predicted`.
- **Assay type** (CLI arg `--assay`): one of `affinity_elisa`, `affinity_bli`, `affinity_octet`, `expression_qc`, `polyspecificity_panel`. Determines which canonical columns are expected and how the calibration metrics are interpreted.

**Alternative inputs:**
- **Adaptyv API** — fetch results via `mcp__by-adaptyv__adaptyv_get_results(experiment_id=...)`, save the response, then feed to `ingest_lab_results.py --input <saved.json> --format adaptyv-json`.
- **Multi-batch CSV** — pass `--batch-col batch` to keep batches separate when aggregating replicates.

**Optional:**
- **Replicate aggregation policy** (`--aggregate`): one of `mean`, `median`, `keep-all` (default `median` for affinity, `mean` for signal). Replicates are aggregated on `(design_id, replicate_id)`.
- **Column aliases** (`--alias canonical=source`, repeatable): handles lab-batch column drift (e.g. `--alias design_id=variant_name --alias kd_nm=KD_nM`).
- **Censored-data threshold** (`--lod-kd-nm`): values reported as `> LOD` are treated as right-censored and excluded from continuous tests (but still kept as FAIL for categorical).

See [references/lab-readout-schemas.md](references/lab-readout-schemas.md) for column-rename tables for each lab partner and assay.

---

## Outputs

**Primary results:**
- `lab_results.normalized.json` — canonical schema lab data (one record per design after aggregation), with provenance fields (`source_file`, `aggregation_policy`, `assay`, `batch_id`).
- `enriched_dataset.csv` — wide table joining the normalized lab outcomes to every in-silico feature on `design_id`. This is the **training data** that **by-campaign-optimizer** picks up for the next round.
- `calibration.json` — per-feature verdicts:
  - `features[].name`, `.verdict` (`validated` / `contradicted` / `inconclusive`)
  - `.statistic` (Mann-Whitney U), `.p_value`, `.q_value` (BH-corrected), `.effect_size`
  - `.passed_mean`, `.failed_mean` (in-lab groups)
  - `.precision_at_top_k`, `.lift_over_random`, `.auc` (if classifier-style)
  - `.interpretation` — one-line natural language summary
- `calibration_report.md` — human-readable report with headline, top validated predictors, top contradicted predictors, and a recommended action for the next round.

**Updates to the knowledge graph** (from `update_knowledge_from_lab.py`):
- One `knowledge_store_campaign` record with the lab outcomes appended to the `outcomes` dict and the joined `designs[]` carrying both in-silico and lab fields.
- One `knowledge_store_failure` record per **contradicted** feature (so future campaigns know not to trust that predictor for similar targets).

**Persistence:**
- Write `calibration.json` next to `screening_results.json` in the campaign directory so **by-campaign-optimizer** can pick it up without further configuration.

---

## Clarification Questions

⚠️ **CRITICAL:** Always ask question #1 first to confirm the lab file exists and the ground-truth column is identified before any compute runs.

1. **Lab readout file and outcome column (ASK THIS FIRST):**
   - Where is the lab readout file (path)? What format (CSV, TSV, Excel, Adaptyv JSON)?
   - Which column holds the ground-truth outcome? Is it categorical (PASS/FAIL, binder/no-binder) or continuous (Kd in nM, binding signal a.u.)?
   - Without confirmed outcome semantics, the calibration is meaningless. Stop here if uncertain.

2. **Design ID alignment:**
   - Does the `design_id` column in the lab file match the design IDs in `screening_results.json` exactly? Lab partners often re-encode IDs (e.g. `BY-001` ↔ `by_001` ↔ `BY001`). Decide an alias map before running ingest.

3. **Assay type:**
   - Affinity (ELISA, BLI, Octet), expression QC, or polyspecificity panel? Different assays have different canonical columns and different PASS thresholds.

4. **Replicate handling:**
   - Are there technical replicates per design? Do we aggregate by median (default for Kd), mean (default for signal), or keep all rows for downstream variance analysis?

5. **Continuous → categorical threshold:**
   - If the outcome is continuous (Kd, signal), what threshold defines PASS? Default: Kd ≤ 100 nM = PASS. The user should confirm — every target has a different therapeutic-relevance bar.

6. **Censored data:**
   - Were any measurements reported as `> LOD` (above limit of detection)? These are right-censored — treat as FAIL for categorical analysis, exclude from continuous tests.

7. **Knowledge-graph write authority:**
   - Should we push findings to the knowledge graph now (default: yes), or stage them for review first? Findings are append-only and influence future campaigns.

For a fuller pre-flight when the lab file is from a new vendor, walk through [references/lab-readout-schemas.md](references/lab-readout-schemas.md).

---

## Standard Workflow

🚨 **MANDATORY: USE THE SHIPPED SCRIPTS — DO NOT REIMPLEMENT THE JOIN OR STATISTICS INLINE** 🚨

Inline joins on `design_id` invariably mis-handle column drift, replicate aggregation, censored values, and BH correction. The shipped scripts encode all of these consistently with **by-failure-diagnosis** (same Mann-Whitney + BH approach), so calibration numbers stay comparable across rounds.

### Step 1: Verify file presence and outcome semantics

Before running anything, confirm the lab file exists and you know which column holds the ground truth.

```bash
ls -lh experiments/batch_001_adaptyv.csv
head -3 experiments/batch_001_adaptyv.csv
```

✅ **VERIFICATION:** File is non-empty; you can identify a `design_id` column and an outcome column.

### Step 2: Normalize the lab readout

```bash
python3 scripts/ingest_lab_results.py \
    --input  experiments/batch_001_adaptyv.csv \
    --output campaigns/<target>/<campaign_id>/lab_results.normalized.json \
    --assay  affinity_bli \
    --aggregate median \
    --kd-threshold-nm 100
```

If the lab CSV uses non-canonical column names, pass aliases:

```bash
python3 scripts/ingest_lab_results.py \
    --input  experiments/batch_002_internal.xlsx \
    --output campaigns/<target>/<campaign_id>/lab_results.normalized.json \
    --assay  affinity_elisa \
    --alias  design_id=variant_name \
    --alias  kd_nm=KD_nM \
    --alias  lab_outcome=binding_call
```

✅ **VERIFICATION:** Output ends with `✓ Ingest completed: N rows -> <path>` and the JSON contains a `metadata.assay` field matching what you passed.

### Step 3: Join with in-silico features and diagnose

```bash
python3 scripts/diagnose_silico_vs_lab.py \
    --lab          campaigns/<target>/<campaign_id>/lab_results.normalized.json \
    --silico       campaigns/<target>/<campaign_id>/screening_results.json \
    --output-json  campaigns/<target>/<campaign_id>/calibration.json \
    --output-md    campaigns/<target>/<campaign_id>/calibration_report.md \
    --top-k        10
```

✅ **VERIFICATION:** stdout reports `joined N designs (X with lab outcome, Y with silico features)` and writes both output files.

### Step 4: Read the calibration report

Open `calibration_report.md`. The report has three sections:

1. **Headline** — one line: total tested, fraction PASSed, top validated feature, top contradicted feature.
2. **Validated predictors** — features whose in-silico value reliably tracked lab outcome (Mann-Whitney p<0.05, BH q<0.10, effect size >0.5, lift>1.2 over random at top-K).
3. **Contradicted predictors** — features whose in-silico value pointed the **wrong** direction (PASS designs had statistically worse silico scores than FAIL designs).
4. **Inconclusive features** — no significant signal either way.

| Verdict | Meaning | Action |
|---------|---------|--------|
| `validated` | Silico predicted reality | Keep this feature in the screener; consider tightening its threshold |
| `contradicted` | Silico pointed the wrong way | **Stop trusting this feature** for this target class; record as a failure in the knowledge graph |
| `inconclusive` | No signal | Sample size too small, or feature is truly orthogonal — defer decision |

### Step 5: Update the knowledge graph

```bash
python3 scripts/update_knowledge_from_lab.py \
    --calibration campaigns/<target>/<campaign_id>/calibration.json \
    --campaign-id <campaign_id> \
    --target      <target> \
    --modality    VHH
```

✅ **VERIFICATION:** stdout lists `✓ Wrote 1 campaign record + N failure records`. Idempotent — re-running with the same `--campaign-id` does NOT duplicate (the script checks before writing).

### Step 6: Hand off to optimizer

The enriched dataset (`enriched_dataset.csv`) is the input **by-campaign-optimizer** picks up. Invoke that skill next with the calibration as a prior:

```bash
python3 ../by-campaign-optimizer/scripts/optimize_from_csv.py \
    --scores campaigns/<target>/<campaign_id>/enriched_dataset.csv \
    --output campaigns/<target>/<campaign_id>/optimizer_output.json
```

⚠️ **CRITICAL - DO NOT:**
- ❌ Skip Step 2's alias map when you know columns drifted → silent NaN joins and bogus statistics
- ❌ Mix assays (ELISA + BLI) in one diagnosis → different noise profiles, comparison invalid
- ❌ Treat censored Kd values as numerical → biases the Mann-Whitney; exclude or treat categorically
- ❌ Write to the knowledge graph before reviewing the contradicted list → false findings poison future campaigns

---

## When Scripts Fail

Follow the standard Script Failure Hierarchy:

1. **Fix and Retry (90%)** — Most failures are missing `openpyxl` (for Excel), `scipy`, `pandas`, or `scikit-learn`. Run `pip install pandas scipy openpyxl scikit-learn`.
2. **Modify Script (5%)** — If the lab vendor uses an entirely new column convention not covered by `--alias`, extend the `CANONICAL_COLUMNS` map in `ingest_lab_results.py`.
3. **Use as Reference (4%)** — Read `diagnose_silico_vs_lab.py` and adapt the join + Mann-Whitney pattern for a one-off cross-target comparison.
4. **Write from Scratch (1%)** — Only when the assay produces fundamentally different data (e.g. cryo-EM hit confirmation). Document the deviation in a campaign phase note.

| Failure | Triage |
|---------|--------|
| `KeyError: 'design_id'` from ingest | Pass `--alias design_id=<source-column>` |
| `ValueError: outcome column missing` | Confirm `--outcome-col` and that the lab file has it |
| `openpyxl not installed` | `pip install openpyxl` |
| `All NaN in joined feature column` | The in-silico file uses a different design_id format — fix at Step 2 with alias |
| `Mann-Whitney returns all p=1.0` | One of the lab groups is empty after join; check `joined N` line |
| `update_knowledge_from_lab.py: duplicate campaign_id` | Already written; safe to ignore (idempotent guard) |

For the deeper rationale on each failure mode and how the in-silico feature ought to have predicted it, see [references/silico-vs-lab-divergence.md](references/silico-vs-lab-divergence.md).

---

## Decision Points

### When to declare a feature "validated"

Require **all four** of:
- Mann-Whitney p < 0.05
- BH-corrected q < 0.10
- Effect size > 0.5 (Cohen's d analog)
- Precision at top-K (K=10) ≥ 0.6 (i.e. ≥6 of the 10 top-silico-ranked designs were lab-PASS)

Anything less is `inconclusive`, not `validated`. Over-confident validation poisons the knowledge graph.

### When to declare a feature "contradicted"

The PASS group has a **statistically lower** silico score than the FAIL group (or higher for features where lower is better), with p < 0.05 and effect size > 0.5. This is the dangerous case: the screener is actively pushing in the wrong direction. Always emit a `knowledge_store_failure` for these so future campaigns avoid the trap.

### How many lab data points are enough?

| Designs tested in lab | Confidence | Recommended action |
|-----------------------|------------|--------------------|
| < 10 | Cannot calibrate — too few | Use ranked observation only; do not write knowledge findings |
| 10 – 30 | Weak — point estimates only | Report observations; flag findings as `inconclusive` unless effect is enormous |
| 30 – 100 | Moderate — most decisions safe | Standard pipeline; trust validated/contradicted verdicts |
| > 100 | Strong — full pipeline + cross-validation | Run with `--cross-validate` flag for held-out AUC |

### When to escalate

If the calibration report shows **most** features contradicted (≥ 3 of 6 with effect > 0.5 in the wrong direction), the screener is mis-specified for this target. Invoke **by-hypothesis-debate** to pick a new strategy; do not just adjust thresholds.

---

## Common Issues

| Issue | Possible Cause | Solution | Details |
|-------|----------------|----------|---------|
| `KeyError: design_id` on ingest | Lab CSV uses different identifier (`variant_name`, `seq_id`, `well_id`) | Pass `--alias design_id=<source>` to `ingest_lab_results.py` | [lab-readout-schemas.md#aliases](references/lab-readout-schemas.md) |
| Ambiguous outcome encoding (mix of `binder`/`no-binder` and `Kd_nM`) | Vendor exported both raw kinetics and a derived call | Pick ONE source-of-truth column; pass via `--outcome-col` | [lab-readout-schemas.md#outcome-encoding](references/lab-readout-schemas.md) |
| Column renamed across batches (`KD_nM` → `kd_nm` → `kdNM`) | Lab updated their LIMS export schema | Maintain a per-batch `aliases.yaml`; reference it with `--alias-file` | [lab-readout-schemas.md#batch-drift](references/lab-readout-schemas.md) |
| Multiple replicates per design produce different verdicts | Replicates were not aggregated before join | Re-run ingest with `--aggregate median` (or `mean`) | [lab-readout-schemas.md#replicates](references/lab-readout-schemas.md) |
| One-class result (all PASS or all FAIL) | Threshold too lenient/strict, or all designs in a tight regime | Lower bar to produce mixed cohort, OR submit a wider design panel next time | [silico-vs-lab-divergence.md#one-class](references/silico-vs-lab-divergence.md) |
| Design IDs join with 0 matches | ID format drift (`BY-001` vs `by_001`) | Inspect `head` of both files; build alias map; consider a normalization regex | [lab-readout-schemas.md#id-normalization](references/lab-readout-schemas.md) |
| Outliers dominate the Mann-Whitney | A single design with extreme Kd (e.g. 0.1 nM vs cluster at 200 nM) | Mann-Whitney is rank-based and robust, but inspect violins; consider Hodges-Lehmann shift | [silico-vs-lab-divergence.md#outliers](references/silico-vs-lab-divergence.md) |
| Censored Kd values (`> LOD`) | Affinity below detection floor | Pass `--lod-kd-nm <limit>`; values above are treated as FAIL categorically, dropped from continuous tests | [lab-readout-schemas.md#censored](references/lab-readout-schemas.md) |
| Week-over-week assay drift produces shifted distributions | Reagent batch change, instrument recalibration | Always include a control design across batches; normalize via control if drift > 20% | [silico-vs-lab-divergence.md#assay-drift](references/silico-vs-lab-divergence.md) |
| Mixing assays in one diagnosis (ELISA + BLI in same call) | Convenience over correctness | Run one diagnosis per assay; cross-reference reports separately | [feedback-loop.md#per-assay](references/feedback-loop.md) |
| Silico file uses `ipsae` but lab CSV-derived enriched file uses `ipsae_min` | Naming inconsistency between scoring runs | Use `--silico-feature-alias ipsae=ipsae_min` | [silico-vs-lab-divergence.md#feature-aliases](references/silico-vs-lab-divergence.md) |
| Knowledge graph keeps growing duplicates | `update_knowledge_from_lab.py` called with different `--campaign-id` each time | Use canonical campaign directory name as `--campaign-id`; the idempotency guard keys off it | [feedback-loop.md#idempotency](references/feedback-loop.md) |

---

## Best Practices

1. 🚨 **CRITICAL:** Always inspect `head` of the lab file before ingest — column names drift constantly and silent NaN joins are the #1 source of bogus calibration.
2. 🚨 **CRITICAL:** Run **one diagnosis per assay**. Mixing ELISA and BLI inflates noise and invalidates the test.
3. ✅ **REQUIRED:** Persist `calibration.json` next to `screening_results.json` in the campaign directory before invoking **by-campaign-optimizer**.
4. ✅ **REQUIRED:** Use the same effect-size + BH-correction rules as **by-failure-diagnosis** so calibration metrics are directly comparable across rounds.
5. ✅ Treat `contradicted` features as urgent — emit a knowledge-graph failure record AND surface the finding in the user-facing summary.
6. ✅ Cross-check the top validated predictor with a violin plot before declaring it the new "trusted" feature. Strong overlap in violins despite low p is a false-positive smell.
7. ✅ Carry the in-silico → lab ID mapping (`alias_map`) into the enriched dataset so downstream tooling can re-trace provenance.
8. ✅ Re-run calibration after every lab batch — calibration drift is the early warning of target-class divergence.
9. ❌ Do NOT write `validated` findings to the knowledge graph when N_lab < 30. Use `inconclusive` instead.
10. ❌ Do NOT compare calibration across different target classes (e.g. cytokines vs ion channels). Calibrations are target-specific.
11. ✨ **Optional:** After 3+ lab batches on the same target, average per-feature effect sizes for a "stable" calibration profile suitable for cross-campaign warm-starts.

---

## Suggested Next Steps

After running this skill, route to one of:

1. **by-campaign-optimizer** — Reads `enriched_dataset.csv` (in-silico features + ground-truth lab outcomes) as the new training data for the next round's Random Forest. This is the default downstream path; calibration findings become priors on feature importance.

2. **by-knowledge** — Already invoked by `update_knowledge_from_lab.py`, but you may want to manually call `mcp__by-knowledge__knowledge_query_similar` after the write to confirm the new finding surfaces in future recommendations.

3. **by-failure-diagnosis** — When the calibration shows multiple contradicted predictors, run failure-diagnosis on the **lab-FAIL** subset using in-silico features. The cross-tabulation between "silico said PASS but lab said FAIL" reveals which in-silico knob you're over-trusting.

4. **by-hypothesis-debate** — When ≥3 features are contradicted (the screener is systematically wrong for this target), use hypothesis-debate to pick a new strategy before spending more lab money.

5. **by-research** — If the contradicted features point to biology the screener doesn't model (e.g. cryptic epitope, polyspecificity), re-research the target with the lab data as a new prior.

6. **by-campaign-manager** — Record this calibration as a milestone in the campaign state so resume sessions know lab data has been folded in.

Chaining rationale: a lab result is a **single most-valuable signal** in the entire pipeline. Pushing it into the optimizer (parameters), knowledge graph (cross-campaign memory), and diagnosis (root cause) at once is the only way to keep round-on-round improvement compounding.

---

## Related Skills

**Upstream (run before):**
- **by-screening** — Produces the `screening_results.json` in-silico feature table that this skill joins to lab data.
- **by-adaptyv** — Submits the designs and exposes `mcp__by-adaptyv__adaptyv_get_results` to retrieve the lab CSV.
- **by-campaign-manager** — Stores the campaign state and `design_id` registry that the lab file must align with.

**Downstream (run after):**
- **by-campaign-optimizer** — Consumes the enriched dataset (in-silico + lab) as new training data.
- **by-knowledge** — Receives the validated / contradicted findings via `update_knowledge_from_lab.py`.
- **by-failure-diagnosis** — Runs on the lab-FAIL subset to identify which in-silico features were over-trusted.

**Alternative / complementary:**
- **by-hypothesis-debate** — When the calibration shows systemic screener mis-specification.
- **by-display** — Formats the calibration report for human review in the chat UI.

---

## References

**Detailed documentation:**
- [references/lab-readout-schemas.md](references/lab-readout-schemas.md) — Canonical schema; per-vendor column maps (Adaptyv batch CSV, internal ELISA plate-reader, BLI/Octet kinetics, expression QC); replicate-handling rules; censored-data conventions; ID-normalization patterns.
- [references/silico-vs-lab-divergence.md](references/silico-vs-lab-divergence.md) — Catalog of why in-silico PASS becomes lab FAIL (expression issues, aggregation, polyspecificity, cryptic epitope, kinetic vs thermodynamic mismatch); per-failure-mode mapping of which in-silico feature SHOULD have caught it; calibration-metric definitions (precision at K, lift over random, AUC).
- [references/feedback-loop.md](references/feedback-loop.md) — How this skill chains: lab → diagnose → optimizer + knowledge; explicit MCP tool call shapes; idempotency rules; state diagram for the feedback loop.

**Scripts:**
- `scripts/ingest_lab_results.py` — CLI: read CSV / TSV / Excel / Adaptyv JSON, apply alias map, validate against canonical schema, aggregate replicates, emit normalized JSON.
- `scripts/diagnose_silico_vs_lab.py` — CLI: join lab + silico on `design_id`, run Mann-Whitney U per silico feature with BH correction, compute precision at top-K and AUC, emit `calibration.json` and `calibration_report.md`.
- `scripts/update_knowledge_from_lab.py` — CLI: read calibration, write one campaign record + one failure record per contradicted feature to the knowledge graph via MCP tools; idempotent on `campaign_id`.

**MCP tools:**
- `mcp__by-adaptyv__adaptyv_get_results` — Pull lab results from Adaptyv Bio (upstream source).
- `mcp__by-knowledge__knowledge_store_campaign` — Write enriched campaign record (downstream sink).
- `mcp__by-knowledge__knowledge_store_failure` — Record contradicted features as failure patterns (downstream sink).

**Official documentation:**
- [scipy.stats.mannwhitneyu](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html) — Non-parametric test used for per-feature group comparison.
- [scikit-learn roc_auc_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html) — AUC computation in the calibration step.
- [Benjamini-Hochberg FDR control](https://www.jstor.org/stable/2346101) — Multiple-testing correction.

**Key Papers:**
- [Adams, Nguyen & Wittrup 2009 — Avidity of binding to cell-surface antigens and the apparent affinity-avidity puzzle](https://doi.org/10.1006/jmbi.1996.0858) — Why in-silico Kd and lab Kd diverge for membrane targets.
- [Norman et al. 2020 — Computational approaches to therapeutic antibody design](https://doi.org/10.1093/bib/bbz095) — Review of in-silico features and their empirical correlations with lab outcomes.
- [Hie et al. 2024 — Active learning for protein engineering](https://doi.org/10.1126/science.adk8946) — Closing the wet-lab feedback loop with model retraining on ground truth.

**License:** All third-party packages used by this skill (pandas, numpy, scipy, openpyxl, scikit-learn) permit commercial use in AI applications.
