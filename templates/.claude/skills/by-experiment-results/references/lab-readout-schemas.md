# Lab Readout Schemas

Every lab partner exports their results in slightly different shapes. This document defines the **canonical schema** BY normalizes to, then maps each common vendor / assay format onto it.

The canonical schema is what `ingest_lab_results.py` writes; downstream tooling (`diagnose_silico_vs_lab.py`, `by-campaign-optimizer`) only knows about canonical column names.

---

## Canonical Schema

After running `ingest_lab_results.py`, every record conforms to:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `design_id` | str | yes | Stable design identifier matching `screening_results.json` |
| `lab_outcome` | str | yes | One of `PASS`, `FAIL`, `CENSORED` (uppercase) |
| `assay` | str | yes | One of `affinity_elisa`, `affinity_bli`, `affinity_octet`, `expression_qc`, `polyspecificity_panel` |
| `kd_nm` | float | when affinity | Equilibrium dissociation constant in nM (NaN if censored) |
| `ka_per_M_per_s` | float | optional | Association rate (1/M/s), kinetic assays only |
| `kd_per_s` | float | optional | Dissociation rate (1/s), kinetic assays only |
| `binding_signal` | float | optional | ELISA OD, BLI nm shift, or fluorescence (a.u.) |
| `expression_mg_per_L` | float | when expression | Soluble yield in mg / L |
| `polyspecificity_score` | float | when polyspec | Off-target binding score, normalized 0-1 |
| `aggregation_pct` | float | optional | SEC monomer % (HMW species deducted) |
| `replicate_id` | str | optional | Set only if `--aggregate keep-all` |
| `batch_id` | str | optional | Lab batch (instrument run, plate) for tracking drift |
| `source_file` | str | yes | Provenance — path to source file |
| `source_row` | int | yes | Provenance — row in source file |

The canonical schema is intentionally narrow. If a vendor exports 40 columns of plate-level metadata, ingest keeps only the columns that map onto canonical fields plus anything passed via `--keep-extra-col`.

---

## Adaptyv Batch CSV

Adaptyv Bio's standard export for protein binder screening. Pulled via `mcp__by-adaptyv__adaptyv_get_results(experiment_id=...)` or downloaded from the dashboard.

| Adaptyv column | Canonical column | Notes |
|----------------|------------------|-------|
| `sequence_name` | `design_id` | Use `--alias design_id=sequence_name` |
| `binding_signal` | `binding_signal` | Direct map |
| `kd_nm` | `kd_nm` | Direct map; `null` → NaN |
| `specificity` | `polyspecificity_score` | Inverted: Adaptyv reports specificity (1.0 = specific), canonical expects polyspecificity (1.0 = polyspecific). Pass `--invert polyspecificity_score=specificity`. |
| `notes` | (drop) | Not consumed downstream; `--keep-extra-col notes` to retain |

**Outcome derivation (Adaptyv):** Adaptyv does not export `lab_outcome` directly. Pass `--kd-threshold-nm 100` and `--binding-threshold 0.3` to derive PASS/FAIL.

**Adaptyv JSON format:** When fetched via the MCP tool, the response is a JSON object `{experiment_id, results: [...]}`. Pass `--format adaptyv-json` to ingest the `results` array directly.

---

## Internal ELISA Plate-Reader Output

Typical output from a Tecan / BioTek plate reader after manual annotation.

| Source column | Canonical column | Notes |
|---------------|------------------|-------|
| `well_id` or `variant_name` | `design_id` | Choose the one stable across batches |
| `OD450` | `binding_signal` | Raw signal; default PASS threshold 0.3 OD above background |
| `binding_call` | `lab_outcome` | Manual annotation, values usually `binder`/`no-binder` |
| `plate_id` | `batch_id` | Useful for drift tracking |
| `replicate` | `replicate_id` | Drop if `--aggregate median`/`mean` |

**Outcome encoding for ELISA:** Two common conventions:
- Categorical (manual annotation): `binder` / `no-binder` → pass `--outcome-pass-value binder`
- Continuous (OD): `binding_signal` → pass `--binding-threshold 0.3`

If BOTH are present, prefer the categorical column (the curator added domain knowledge).

---

## BLI / Octet Kinetics Table

Output from a ForteBio Octet or Sartorius BLI run; one row per design per concentration, OR one row per design with fitted parameters.

| Source column | Canonical column | Notes |
|---------------|------------------|-------|
| `sample_id` | `design_id` | Often a position code; align with submission manifest |
| `KD_(M)` | `kd_nm` | Convert with `--unit-convert kd_nm=M_to_nM` |
| `kon_(1/Ms)` | `ka_per_M_per_s` | Direct map |
| `koff_(1/s)` | `kd_per_s` | Direct map |
| `R^2` or `chi^2` | (use for QC) | Filter rows with poor fit before ingest |

**Multi-row issue:** BLI exports may have one row per concentration point per design. Aggregate by `design_id` BEFORE ingest, OR pass `--aggregate median` so the script keeps only the fitted-parameter row.

---

## Expression QC

From an internal small-scale expression screen (analytical SEC + Bradford or A280).

| Source column | Canonical column | Notes |
|---------------|------------------|-------|
| `construct` | `design_id` | |
| `yield_mg_per_L` | `expression_mg_per_L` | |
| `monomer_pct` | `aggregation_pct` | Inverted name: BY's `aggregation_pct` is monomer % (high = good) |
| `pass_call` | `lab_outcome` | Usually `expressed` / `not_expressed` |

**Pass threshold:** Default is `expression_mg_per_L >= 5` AND `monomer_pct >= 90`. Pass both flags or derive on ingest.

---

## Polyspecificity Panel

Cross-reactivity screen against a small panel of off-target antigens (e.g. baculovirus particles, polyspecificity reagent).

| Source column | Canonical column | Notes |
|---------------|------------------|-------|
| `sample_name` | `design_id` | |
| `psr_score` | `polyspecificity_score` | 0-1, higher = more polyspecific (bad) |
| `clean_call` | `lab_outcome` | `clean` / `polyspecific` — pass `--outcome-pass-value clean` |

---

## Replicate Handling

Lab batches commonly have technical replicates (2-4 wells per design). Aggregation policy is set by `--aggregate`:

| Policy | When to use |
|--------|-------------|
| `median` | Default for affinity (Kd) — robust to outliers and to one bad well |
| `mean` | Default for continuous signal (OD, binding_signal) when all replicates pass QC |
| `keep-all` | When you want to expose per-replicate variance downstream; the join in `diagnose_silico_vs_lab.py` will then operate on a long table |

**Aggregation rules per column:**
- `kd_nm` → geometric mean (log-normal) when `mean`; median otherwise
- `binding_signal`, `expression_mg_per_L` → arithmetic mean or median
- `lab_outcome` → majority vote; tie → FAIL (conservative)

---

## ID Normalization

The single most common ingest failure is `design_id` mismatch. Patterns we have seen:

| In-silico | Lab CSV | Normalization |
|-----------|---------|---------------|
| `BY-001` | `by_001` | Lowercase + replace `-` with `_`: `--id-regex 's/-/_/g;y/A-Z/a-z/'` |
| `tnf_round2_001` | `Variant_001` | Lab dropped prefix; maintain a mapping CSV via `--id-map ids.csv` |
| `design_a1b2c3` | `A1B2C3` | Strip prefix + uppercase: `--id-regex 's/design_//;y/a-z/A-Z/'` |

Always inspect `head -3` of BOTH files before ingest. The script emits a warning if fewer than 80% of lab `design_id`s match silico after normalization.

---

## Outcome Encoding

If the user is unsure which column is ground truth:

1. **Prefer categorical** (`lab_outcome` ∈ {PASS, FAIL, binder, no-binder}) over continuous when both exist — curator annotation usually outperforms naive thresholding.
2. **For continuous Kd**: 100 nM is a common therapeutic-relevance bar; confirm with the user.
3. **For binding signal**: pick the threshold that produces a 30-70% PASS rate on the cohort — that's the most informative regime.
4. **Never** use a percentile threshold (e.g. "top 25% are PASS"). That makes PASS a moving target across batches.

---

## Batch Drift

Lab assays drift week-over-week. Mitigation:

- **Always submit a control design** in every batch (e.g. a known binder + a known non-binder).
- **Compute drift** as the ratio of control measurements between batches. If drift > 20%, normalize numeric columns by the control before ingest.
- **Track batches** via `batch_id` and run calibration per batch when drift is suspected.

---

## Censored Data

Affinity measurements have a limit of detection (LOD). Values reported as `> LOD` (e.g. `Kd > 1000 nM`) are right-censored:

- **Categorical view**: treat as FAIL.
- **Continuous view**: drop from Mann-Whitney (excluding distorts the rank distribution less than including a fake high value).

Pass `--lod-kd-nm 1000` to declare the LOD. Ingest writes `lab_outcome=CENSORED` for those rows; `diagnose_silico_vs_lab.py` then treats them as FAIL for categorical analysis and drops them for continuous tests.

---

## Provenance

Every canonical record carries `source_file` and `source_row` so you can trace back any anomalous result to the exact CSV row. **Do not drop these fields** even when they look redundant — they save hours when a lab batch is later revoked.
