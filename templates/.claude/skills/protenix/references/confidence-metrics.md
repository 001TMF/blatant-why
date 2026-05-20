# Protenix Confidence Metrics — Interpretation Guide

How to read the four confidence outputs Protenix emits, how to ensemble across
seeds, what acceptance thresholds to apply by use case, and the most common
failure-mode patterns to recognise on inspection.

---

## 1. The Four Metrics

Each `*_summary_confidence_sample_*.json` carries four headline fields. Treat
each as answering a different question.

| Metric | Range | Scope | Question it answers |
|--------|-------|-------|---------------------|
| `iptm` | 0 – 1 | Inter-chain (interface only) | Is the relative pose between chains correct? |
| `ptm` | 0 – 1 | Whole-complex topology | Is the overall fold topology correct? |
| `plddt` | 0 – 100 | Per-residue average | Are the local geometries (backbone, sidechain) confident? |
| `ranking_score` | unbounded float | Composite | Which sample (across seeds × samples) should I pick? |

**Note:** Any of these may arrive wrapped as a single-element list, e.g. `[0.83]`.
Handle both the scalar and list forms (the ensemble script does this with a
`_unwrap()` helper).

### ipTM — Interface Predicted TM-score

- The single most important metric for a **complex** (binder + target, antibody +
  antigen, protein + ligand).
- Computed over inter-chain residue pairs only — so ipTM is meaningless for a
  single chain (you will see `iptm = 0` or near-zero).
- A model that confidently predicts each chain in isolation but has no idea
  where they sit relative to each other will show **high pTM, high pLDDT, low ipTM**.
  This is the classic "two correct chains in the wrong pose" pattern.

### pTM — Predicted TM-score

- Whole-complex (or whole-chain) topology.
- For a single chain, pTM is your primary fold-quality readout.
- For a complex, pTM remains high as long as each chain folds — it does not
  by itself tell you the pose is correct (that is ipTM's job).

### pLDDT — Per-residue confidence (0-100)

- Averaged over all residues in the prediction.
- Interpretation: > 90 very high, 70-90 confident, 50-70 low, < 50 disordered or
  wrong.
- The per-residue breakdown (when written in the full-data JSON) is where you
  detect localised failures: a high mean pLDDT can still hide a low-pLDDT loop
  at the interface, which often correlates with a spurious ipTM.

### ranking_score — Composite ranker

- Protenix-internal composite. Use it as the **tiebreaker** when picking a
  sample from a multi-seed / multi-sample run.
- Do not interpret it as a calibrated probability — use it strictly for ordering.

---

## 2. Multi-Seed Ensemble Guidance

Diffusion models produce different structures for different random seeds. The
spread across seeds tells you whether the prediction is **stable** (low
variance, can be trusted) or **fragile** (high variance, model is uncertain).

| Seeds | When to use |
|-------|-------------|
| 1 seed | Quick look-only / pipeline plumbing test. **Never** an acceptance call. |
| 3 seeds | Standard validation — minimum for any accept/reject decision. |
| 5 seeds | Borderline cases or production submission of a designed binder. |
| 15-25 seeds | Hero campaigns: regulatory submission, lead asset, or anything you cannot afford to retract. |

### Reading the ensemble

`scripts/multi_seed_ensemble.py` produces:

- `ensemble_summary.json` — `{metric: {mean, std, min, max}}`, an agreement
  score, and a pointer to the best (seed, sample) pair.
- `ensemble_ranked.csv` — one row per (seed, sample), sorted by `ranking_score`.

**Agreement** is the fraction of (seed, sample) records that agree with the
ensemble's median ipTM bin (low / mid / high). High agreement (> 0.8) means the
model is converging on a single answer.

### Variance thresholds

| std(ipTM) across seeds | Interpretation |
|------------------------|----------------|
| ≤ 0.05 | Robust prediction — the mean is trustworthy. |
| 0.05 – 0.10 | Some sensitivity — report mean ± std, do not over-claim. |
| > 0.10 | Fragile — single-seed numbers are misleading; either run more seeds or treat the prediction as inconclusive. |

A high-mean / high-variance ensemble (e.g. mean ipTM 0.78, std 0.18) typically
indicates the model finds *a* binding pose but is not sure which one — useful
for ranking but not for declaring a winner.

---

## 3. Acceptance Thresholds by Use Case

Different use cases tolerate different confidence bars. The table below is a
default that the skill applies unless the user states otherwise.

### Use case: Structure validation (does this protein fold?)

| Metric | Minimum | Good | Excellent |
|--------|---------|------|-----------|
| `pTM` | > 0.5 | > 0.7 | > 0.85 |
| mean `pLDDT` | > 70 | > 80 | > 90 |

ipTM does not apply to single-chain validation.

### Use case: Ranking (pick best of N designs)

- Use `ranking_score` to order.
- Tiebreak with mean `ipTM` across seeds.
- Accept the top-K relative to the cohort, not against a fixed threshold —
  ranking is comparative.

### Use case: Refold validation (does this designed binder hold its pose?)

| Metric | Minimum | Good | Excellent |
|--------|---------|------|-----------|
| `ipTM` | > 0.5 | > 0.7 | > 0.85 |
| `pTM` | > 0.5 | > 0.7 | > 0.85 |
| mean `pLDDT` | > 70 | > 80 | > 90 |
| std(`ipTM`) across ≥ 3 seeds | < 0.10 | < 0.05 | < 0.03 |

A binder that passes refold validation is one where ≥ 3 of 3 seeds report
`ipTM > 0.5` and the variance is low. If 1 of 3 seeds gives `ipTM ≈ 0.3`, the
mean is misleading — re-run with 5 seeds and look at the distribution.

### Use case: Production / lab-submission gate

| Metric | Minimum |
|--------|---------|
| mean `ipTM` across ≥ 5 seeds | > 0.70 |
| std(`ipTM`) | < 0.10 |
| mean `pLDDT` | > 80 |
| Interface pLDDT (per-residue at contact residues) | > 75 |
| Agreement (ensemble script) | ≥ 0.80 |

A design that scrapes through validation (e.g. ipTM 0.55) should not be the
asset you submit to the wet lab. Use the production gate to filter the tail.

---

## 4. Failure-Mode Taxonomy

These are the patterns to look for when a prediction looks suspicious.

### "ipTM = 0.5 trap" — false-positive interface

Symptom: ipTM hovers exactly around 0.45-0.55 across all seeds, pTM high,
pLDDT high, the chains are docked but the interface looks unphysical (no
buried hydrophobics, no complementary charge).

Cause: the model has nothing in its training distribution that resembles the
queried interface and falls back to "any plausible contact". `ranking_score`
will not separate samples meaningfully.

Action: declare the prediction inconclusive. Do not accept.

### Low-pLDDT loops at the interface

Symptom: mean pLDDT > 80 but the per-residue breakdown shows pLDDT < 60 at the
contact residues, while ipTM is moderate.

Cause: the model is confident about the bulk of each chain but is hallucinating
flexible interface loops. The reported `ipTM` is misleading because the
interface itself is low-confidence.

Action: re-run with more seeds and inspect the per-residue pLDDT at contact
residues. If interface pLDDT < 75 across seeds, do not accept.

### High pTM, high pLDDT, low ipTM

Symptom: each chain folds correctly on its own but ipTM < 0.4.

Cause: the model can't find a pose. Either the chains don't actually bind, or
the input is missing context (e.g. a glycan, cofactor, or third chain).

Action: confirm the biology. If they should bind, check that every required
chain is in the input JSON. Re-check `references/input-json-spec.md` for the
entity types you need.

### Single-seed jackpot

Symptom: one of three seeds reports ipTM 0.85, the other two report ipTM 0.45.

Cause: diffusion variance — the model occasionally finds a low-energy pose. A
single "lucky" seed is not evidence of a real interaction.

Action: re-run with 5-10 seeds. If the high-ipTM result reproduces in ≥ 60% of
seeds, treat it as real. Otherwise it was noise.

### List-vs-scalar metric type confusion

Symptom: code crashes with `'>' not supported between instances of 'list' and
'float'`.

Cause: Protenix sometimes emits metrics as `[0.83]` and sometimes as `0.83`.

Action: always unwrap before comparing. The ensemble script does this
automatically via its `_unwrap()` helper.

### "Empty output directory" after a successful return code

Symptom: `protenix pred` exits 0 but `<output-dir>/<name>/` is empty.

Cause: model failed to load (env var unset) or the model name was a key like
`base_default` instead of the full `protenix_base_default_v1.0.0`.

Action: re-check `PROTENIX_ROOT_DIR` and use the full model name. See
`SKILL.md` Common Issues.

---

## 5. Cross-References

- `references/input-json-spec.md` — input JSON schema and entity types.
- `scripts/multi_seed_ensemble.py` — produces the ensemble summary and ranked CSV.
- `by-scoring` skill — ipSAE from PAE matrices; the primary BY composite metric.
- `by-screening` skill — full liability + developability battery on accepted folds.
