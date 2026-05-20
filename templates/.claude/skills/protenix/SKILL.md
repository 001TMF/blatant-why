---
id: "skill_e18f7e05c7e74168bf07a630d9d6a611"
name: "protenix"
display-name: "Protenix Structure Prediction"
short-description: "Run Protenix v1 (AF3-class, 368M params) structure prediction from a sequence-level JSON spec; emits confidence metrics (ipTM, pTM, pLDDT, ranking_score) for fold validation and complex refolding. Use when predicting a protein or complex structure, validating a designed binder by refolding, or running a multi-seed ensemble to assess prediction stability."
category: "tool"
keywords: "protenix, structure prediction, fold, refold, validation, confidence, ipTM, pTM, pLDDT, multi-seed ensemble, complex prediction, protein-ligand"
version: "1.0"
last-updated: "2026-05-20"
---

# Protenix — Structure Prediction Skill

Protenix v1 is an AF3-class structure prediction model (368M parameters) for proteins,
complexes, and protein-ligand systems. This skill wraps the `protenix` CLI with a
documented input spec, an input-validating Python entry point, and a multi-seed
ensemble aggregator so that callers can drive predictions through scripts instead of
ad-hoc bash invocations.

The default compute target is the **local GPU**. HPC (RunPod) is the second choice
and Tamarind cloud is the fallback — set the target via `--target` (see scripts).

## When to Use This Skill

Use Protenix when you have:

- ✅ **A sequence (or set of sequences) and need a 3D structure** — single chain, complex, homo-oligomer, or protein-ligand.
- ✅ **A designed binder to validate by refolding** — predict the binder + target complex and inspect ipTM / interface pLDDT.
- ✅ **A need for explicit confidence metrics** — ipTM, pTM, pLDDT, ranking_score.
- ✅ **A need for multi-seed ensemble stability** — 3-25 seeds with variance reported.
- ✅ **A protein-ligand complex** — SMILES + protein chain via the `ligand` entity type.
- ✅ **A local GPU available** (CUDA, bf16 capable) or an approved HPC / Tamarind path.

Do NOT use Protenix when:

- ❌ **You need to design a new binder** → use `pxdesign` (de novo binder) or `boltzgen` (antibody / nanobody).
- ❌ **You only need to score an existing prediction** (ipSAE from PAE matrices) → use `by-scoring`.
- ❌ **You need the full liability + developability battery** → use `by-screening`.
- ❌ **You need to fetch sequences from PDB/UniProt** → use `by-database` first, then return here.
- ❌ **You are running on CPU only** → Protenix requires a CUDA-capable GPU; no CPU fallback.
- ❌ **You want pipeline orchestration across research → design → screen** → use `by-design-workflow`.

## Quick Start

Local GPU (default). Write an input JSON, then run the wrapper script:

```bash
# 1. Write input spec (one prediction object, JSON array form)
cat > /tmp/fold_run/input.json <<'JSON'
[
  {
    "name": "lysozyme_pred",
    "sequences": [
      {"proteinChain": {"sequence": "KVFGRCELAA...", "count": 1}}
    ],
    "modelSeeds": [42],
    "sampleCount": 1
  }
]
JSON

# 2. Run via the wrapper (validates input, invokes local GPU CLI)
python scripts/protenix_fold.py \
  --input /tmp/fold_run/input.json \
  --output-dir /tmp/fold_run/output \
  --model protenix_base_default_v1.0.0 \
  --target local

# 3. Read confidence
ls /tmp/fold_run/output/lysozyme_pred/seed_42/*_summary_confidence_sample_*.json
```

✅ **VERIFICATION:** Expect `✓ Protenix prediction completed: <output-dir>` on success and at least one `*_summary_confidence_sample_*.json` plus matching `*_sample_*.cif` structure file per seed.

For HPC dispatch, swap `--target local` for `--target hpc` (see `by-deploy-compute` skill for RunPod setup). For Tamarind, use `--target tamarind`.

## Installation

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| Protenix CLI | v1.0 | Apache 2.0 | ✅ Permitted | Install per Protenix repo; expose binary on `PATH` |
| Python | ≥ 3.10 | PSF | ✅ Permitted | `pyenv install 3.10` / system package manager |
| CUDA toolkit | ≥ 11.8 | NVIDIA EULA | ✅ Permitted (research/commercial per EULA) | Per NVIDIA install guide |
| `numpy` | ≥ 1.24 | BSD-3 | ✅ Permitted | `pip install numpy` |

**Environment variables (required for local target):**

| Variable | Value | Notes |
|----------|-------|-------|
| `PROTEUS_FOLD_DIR` | absolute path to the Protenix install | Owned by the user — do not edit |
| `PROTENIX_ROOT_DIR` | `$PROTEUS_FOLD_DIR` | Read by the CLI binary |

**System requirements:**
- CUDA-capable GPU with sufficient VRAM (24 GB+ recommended for `base_*` on complexes > 600 residues).
- bf16 precision required (default `--dtype bf16`).
- HPC/RunPod and Tamarind paths handled by `by-deploy-compute`; this skill only routes to them via `--target`.

**License compliance:** All listed software permits commercial use under the cited licenses.

## Inputs

**Required:**

- **Input JSON** — JSON array containing exactly one prediction object:
  - `name` (string): identifier for output naming, alphanumeric + underscores.
  - `sequences` (array): at least one entity (`proteinChain` or `ligand`).
  - `modelSeeds` (array of int): one or more seeds; each generates an independent prediction subdir.
  - `sampleCount` (int ≥ 1): diffusion samples per seed.
  - See `references/input-json-spec.md` for the full schema, entity types, and edge cases.
- **Output directory** — writable absolute path; the script creates it if missing.

**Optional:**

- **Model name** — defaults to `protenix_base_default_v1.0.0`. See model table below.
- **Compute target** — `local` (default) | `hpc` | `tamarind`.
- **Dtype** — `bf16` (default). Do not change unless you understand the precision/VRAM trade-off.

**Model selection table:**

| Key | Full model name | Use case |
|-----|-----------------|----------|
| `base_default` | `protenix_base_default_v1.0.0` | **Recommended.** Production predictions, validation. |
| `base_20250630` | `protenix_base_20250630_v1.0.0` | Latest checkpoint. Try when `base_default` gives borderline confidence. |
| `mini` | `protenix_mini_default_v0.5.0` | Fast screening. Lower accuracy, 3-5x faster. |
| `tiny` | `protenix_tiny_default_v0.5.0` | Pipeline-debug only. Never for real predictions. |
| `mini_esm` | `protenix_mini_esm_v0.5.0` | Mini + ESM embeddings; better single-chain accuracy. |

## Outputs

All outputs land under the `--output-dir` provided to `protenix_fold.py`.

**Per-prediction directory layout:**

```
<output-dir>/
  <name>/
    seed_<int>/
      <name>_summary_confidence_sample_<i>.json   # confidence metrics, JSON
      <name>_sample_<i>.cif                       # structure, mmCIF
      <name>_full_data_sample_<i>.json            # full per-residue arrays (if model emits)
```

**Confidence JSON fields (`*_summary_confidence_sample_*.json`):**

| Field | Type | Description |
|-------|------|-------------|
| `iptm` | float or list[float] | Interface predicted TM-score (0-1). Key metric for complexes. |
| `ptm` | float or list[float] | Predicted TM-score (0-1). Overall fold quality. |
| `plddt` | float or list[float] | Per-residue confidence average (0-100). |
| `ranking_score` | float or list[float] | Composite ranking score — use to pick the best sample. |

**Note:** Metrics may be wrapped as single-element lists. Always index `[0]` or handle both forms.

**Ensemble outputs (from `scripts/multi_seed_ensemble.py`):**

| File | Format | Description |
|------|--------|-------------|
| `ensemble_summary.json` | JSON | Mean / std / min / max for ipTM, pTM, pLDDT, ranking_score across all (seed, sample) pairs; agreement metric; best (seed, sample) pointer. |
| `ensemble_ranked.csv` | CSV | One row per (seed, sample), columns: `seed`, `sample`, `iptm`, `ptm`, `plddt`, `ranking_score`, sorted by `ranking_score` desc. |

For confidence-acceptance thresholds and failure modes, see `references/confidence-metrics.md`.

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST.** Always confirm the input spec exists before calling the CLI.

1. **Input spec** (ASK THIS FIRST):
   - Have you written the input JSON, or should I draft it from a sequence (or set of sequences)?
   - If drafting: provide the sequence(s), chain count(s), and whether ligands are involved.

2. **Prediction goal:**
   - Single-fold prediction, refold validation of a designed binder, or multi-seed ensemble?
   - This decides `modelSeeds` (1 vs 3 vs 5-25) and `sampleCount`.

3. **Complex composition:**
   - For complexes, list every chain — missing the target chain makes `ipTM` meaningless (no interface to score).

4. **Confidence acceptance bar:**
   - Are you validating (need a YES/NO call), ranking (pick best of N), or submitting for production?
   - See `references/confidence-metrics.md` for thresholds per use case.

5. **Compute target:**
   - Local GPU (default), HPC (RunPod), or Tamarind? Default is `local`; only switch if the user explicitly chose another provider or local fails.

6. **Output location:**
   - Where should outputs land? Default: `/tmp/fold_run/output/` for ad-hoc, or `campaigns/<target>/.../fold/` for a campaign.

7. **Model choice:**
   - Default `base_default`. Switch to `mini` only for rapid feasibility; `tiny` is debug-only.

## Standard Workflow

🚨 **MANDATORY: USE THE SCRIPTS — DO NOT WRITE INLINE PROTENIX CLI INVOCATIONS** 🚨

Driving Protenix through `scripts/protenix_fold.py` ensures input validation, target routing, and structured logging.

1. **Write the input JSON** (per `references/input-json-spec.md`).

   ✅ **VERIFICATION:** The file parses as a JSON array containing one object with `name`, `sequences`, `modelSeeds`, `sampleCount`.

2. **Run the prediction:**

   ```bash
   python scripts/protenix_fold.py \
     --input <path-to-input.json> \
     --output-dir <output-dir> \
     --model protenix_base_default_v1.0.0 \
     --target local
   ```

   ✅ **VERIFICATION:** `✓ Protenix prediction completed: <output-dir>` printed; at least one `*_summary_confidence_sample_*.json` per seed.

3. **(Optional) Multi-seed ensemble aggregation:**

   ```bash
   python scripts/multi_seed_ensemble.py \
     --output-dir <output-dir>/<name> \
     --summary-json <output-dir>/<name>/ensemble_summary.json \
     --ranked-csv  <output-dir>/<name>/ensemble_ranked.csv
   ```

   ✅ **VERIFICATION:** `✓ Ensemble aggregated: <N> (seed,sample) records → <summary path>` printed.

4. **Interpret confidence** using `references/confidence-metrics.md` (acceptance thresholds, failure modes).

❌ **DON'T:**
- ❌ Run `protenix pred …` directly without `protenix_fold.py` — you skip input validation.
- ❌ Use absolute paths baked into the repo — pass paths via CLI flags.
- ❌ Conclude binding from a single seed — always re-run with ≥ 3 seeds for any acceptance decision.

## When Scripts Fail

Follow the script-failure hierarchy (fix 90% / modify 5% / reference 4% / scratch 1%):

1. **Fix and retry (90%)** — usually a missing env var (`PROTENIX_ROOT_DIR`), an invalid JSON spec, or insufficient GPU memory. Set env, fix JSON, reduce `sampleCount` / chains, retry.
2. **Modify the script (5%)** — edit `scripts/protenix_fold.py` if the underlying CLI flags change (e.g., new dtype, new model). Keep the validation step.
3. **Use as reference (4%)** — read the wrapper to learn the call shape, then adapt for an exotic input (custom MSA, frozen residues) the wrapper does not cover.
4. **Write from scratch (1%)** — only if Protenix gains a flag the wrapper cannot express, and you document why.

When `--target local` fails: report the error and offer to dispatch via HPC (`--target hpc`). Do **not** silently switch providers — see `CLAUDE.md` "Compute Provider Selection".

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `protenix: command not found` | `PROTENIX_ROOT_DIR` / `PATH` not set | `export PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR` and ensure binary is on `PATH` | Installation section |
| Input parse error | JSON not wrapped in outer array | Wrap as `[{...}]`, not `{...}` | `references/input-json-spec.md` |
| `ipTM = 0` with reasonable `pLDDT` | Only one chain in `sequences` (no interface) | Include every chain of the intended complex | `references/confidence-metrics.md` |
| Unknown model | Used model key instead of full name | Use full name e.g. `protenix_base_default_v1.0.0` | Model table above |
| CUDA out of memory | Sequence(s) too long or too many samples | Reduce `sampleCount`, drop to `mini`, or split the system | Installation section |
| All confidence ≈ 0 | Malformed input JSON (e.g., lowercase sequence, bad SMILES) | Re-validate against the input spec | `references/input-json-spec.md` |
| Output directory empty | CLI errored mid-run | Inspect stderr from the script | When Scripts Fail |
| Very slow prediction | Large complex on `base_*` | Expected for > 1000 residues; use `mini` for first-pass triage | Model table |
| Single-seed acceptance call | Diffusion variance underestimated | Re-run with ≥ 3 seeds; use ensemble script | `references/confidence-metrics.md` |
| Metric type mismatch (`float > 0.5` errors on list) | Metric returned as `[0.83]` | Always handle both `float` and `[float]` forms (the ensemble script does this) | Outputs section |
| `ranking_score` ties across samples | Diffusion produced near-identical structures | Either accept the top one or increase `sampleCount` | Outputs section |
| Local target fails repeatedly | GPU busy / driver issue | Report; offer HPC dispatch via `--target hpc`; do not silently switch | `by-deploy-compute` skill |

## Best Practices

1. 🚨 **CRITICAL:** Always drive predictions through `scripts/protenix_fold.py`; never call the CLI inline.
2. 🚨 **CRITICAL:** Use ≥ 3 seeds for any acceptance / rejection decision. One seed is informational only.
3. ✅ **REQUIRED:** Include every chain of the intended complex — missing the target chain makes `ipTM` meaningless.
4. ✅ **REQUIRED:** Validate inputs (the wrapper does this) before submitting expensive HPC / Tamarind jobs.
5. ✅ Use `base_default` for production; switch to `mini` only for rapid triage.
6. ✅ Pick the best sample by `ranking_score`, not by `ipTM` alone.
7. ✅ Record the full model name in any downstream artifact (so results are reproducible).
8. ✅ Respect the user's compute-provider choice. Default is `local`; never silently fall back.
9. ✨ Keep input JSON alongside outputs (drop a copy in `<output-dir>/<name>/input.json`) for audit.
10. ❌ Don't use `tiny` for anything except pipeline plumbing tests.

## Suggested Next Steps

After a Protenix run completes:

- **`by-scoring`** — compute ipSAE from PAE matrices for finer interface ranking; ipSAE is the primary metric in the BY composite score.
- **`by-screening`** — run the full liability + developability battery on the predicted complex (only after the fold passes the confidence bar).
- **`by-epitope-analysis`** — when validating a binder, confirm the predicted interface matches the intended epitope.
- **`multi_seed_ensemble.py`** (this skill) — aggregate confidence across seeds before any acceptance call.

Chain rationale: Protenix produces structure + confidence; downstream skills convert those into a defensible accept/reject call. Skipping `by-scoring` / `by-screening` after a fold means you have a structure but no ranked decision.

## Related Skills

**Upstream:**
- `by-database` — fetch target sequences from PDB / UniProt / SAbDab before writing the input JSON.
- `by-research` — characterise the target and epitope before designing/validating.

**Downstream:**
- `by-scoring` — ipSAE and PAE-derived metrics.
- `by-screening` — liability + developability + composite scoring.
- `by-epitope-analysis` — confirm the interface is on the intended epitope.

**Alternative / complementary:**
- `pxdesign` — design a new non-antibody binder (then refold with Protenix).
- `boltzgen` — design antibodies / nanobodies (then refold with Protenix).
- `by-deploy-compute` — how to dispatch to HPC (RunPod) when `--target hpc` is needed.

**Workflow context:**
- `by-design-workflow` — overall pipeline that calls Protenix at the fold-validation step.

## References

**Detailed documentation in `references/`:**

- [`references/input-json-spec.md`](references/input-json-spec.md) — complete input JSON schema: fields, entity types, multi-chain examples, edge cases.
- [`references/confidence-metrics.md`](references/confidence-metrics.md) — how to read ipTM / pTM / pLDDT / ranking_score, multi-seed ensemble guidance, acceptance thresholds by use case, failure-mode taxonomy.

**Scripts in `scripts/`:**

- `scripts/protenix_fold.py` — CLI wrapper: validates the input JSON, invokes Protenix locally (default) or routes to HPC / Tamarind via `--target`, writes outputs.
- `scripts/multi_seed_ensemble.py` — aggregates Protenix outputs across N seeds: emits `ensemble_summary.json` (mean / std / agreement / best pointer) and `ensemble_ranked.csv` (one row per (seed, sample)).

**Related project documentation:**
- `CLAUDE.md` — BY agent identity, compute provider selection rules.
- `by-deploy-compute` skill — RunPod / HPC dispatch details.

**License:** All packages and tools listed above permit commercial use under their stated licenses.
