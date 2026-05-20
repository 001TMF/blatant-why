---
id: "skill_3242953289f649778bba608ab7bad3e2"
name: "pxdesign"
display-name: "PXDesign Binder Designer"
short-description: "De novo protein binder design using PXDesign — YAML config, CLI invocation, output parsing, and result interpretation for non-antibody binders. Use when designing a non-antibody, non-nanobody protein binder against a target structure."
category: "tool"
keywords: "pxdesign, binder design, de novo, protein design, cli, hotspots, scaffold, preset, preview, extended, ipTM, ipSAE, label_asym_id"
version: "1.0"
last-updated: "2026-05-20"
---

# PXDesign — De Novo Protein Binder Design

You are an expert at designing de novo protein binders using PXDesign. This skill
covers YAML config construction, CLI invocation, output parsing, and result
interpretation. PXDesign achieves 17–82% pass rate for de novo binder design
depending on target difficulty (see `references/de-novo-strategy.md`).

PXDesign is invoked from the command line via the `pxdesign` binary. This skill
uses a strict **Write → Bash → Read** pattern: write a YAML config, run the CLI,
read the `summary.csv`. Do not call internal Python wrappers.

---

## When to Use This Skill

Use PXDesign when you have:

- ✅ **A non-antibody, non-nanobody binder target** — a small globular protein binder is acceptable
- ✅ **A target structure file** (CIF preferred, PDB acceptable)
- ✅ **A defined epitope or hotspot list** (or willingness to let PXDesign explore)
- ✅ **Local GPU available** (A100/H100/RTX PRO 6000) OR HPC/Tamarind fallback configured
- ✅ **A clear quality bar** — preview for exploration, extended for production designs

Do NOT use this skill when:

- ❌ **The user wants an antibody or nanobody** → use the `boltzgen` skill
- ❌ **The user wants structure prediction only** → use the `protenix` skill
- ❌ **The user wants to score or screen existing designs** → use `by-scoring` / `by-screening`
- ❌ **No target structure exists** → predict it with Protenix first
- ❌ **The target is membrane-embedded with no soluble construct** → restate the problem; PXDesign requires a soluble target

---

## Quick Start

Design a 100-residue binder against chain A of `IL6R.cif`, preview preset, 10 samples:

```bash
# Step 1 — Write config.yaml (see references/yaml-config-spec.md)
cat > /tmp/il6r/config.yaml <<'EOF'
target:
  file: "/data/targets/IL6R.cif"
  chains:
    A: "all"
binder_length: 100
EOF

# Step 2 — Run PXDesign on local GPU
PATH=/path/to/conda/envs/protenix/bin:$PATH \
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
CUTLASS_PATH=$HOME/cutlass \
CUDA_HOME=$CUDA_HOME \
pxdesign pipeline \
  --preset preview \
  -i /tmp/il6r/config.yaml \
  --N_sample 10 \
  --dtype bf16 \
  --use_fast_ln True \
  -o /tmp/il6r/output

# Step 3 — Parse outputs
python scripts/parse_pxdesign_output.py \
  --output-dir /tmp/il6r/output \
  --out /tmp/il6r/designs.csv
```

Expected runtime: ~10–20 min on A100 for preview; ~60–120 min for extended.
Expected output: `summary.csv` with 10 rows ranked by `ptx_iptm`.

---

## Installation

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| PXDesign binary | as shipped in `$PROTEUS_PROT_DIR` | Internal | ✅ Permitted | Pre-installed by BY environment |
| Protenix conda env | matches binary | Apache-2.0 | ✅ Permitted | `conda env create -f $PROTEUS_PROT_DIR/env.yml` |
| CUTLASS | ≥3.5 | BSD-3 | ✅ Permitted | `git clone https://github.com/NVIDIA/cutlass.git $HOME/cutlass` |
| CUDA toolkit | matches GPU driver | NVIDIA EULA | ✅ Permitted | Bundled with conda env or system CUDA |
| Biopython | ≥1.81 | Biopython License (BSD-like) | ✅ Permitted | `pip install biopython` |
| pandas | ≥2.0 | BSD-3 | ✅ Permitted | `pip install pandas` |
| PyYAML | ≥6.0 | MIT | ✅ Permitted | `pip install pyyaml` |

**License compliance:** All packages permit commercial use in AI applications.

### Required environment variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `PROTENIX_DATA_ROOT_DIR` | `$PROTEUS_PROT_DIR/release_data/ccd_cache` | CCD chemical component cache |
| `TOOL_WEIGHTS_ROOT` | `$PROTEUS_PROT_DIR/tool_weights` | PXDesign model weights |
| `CUTLASS_PATH` | `$HOME/cutlass` | NVIDIA CUTLASS kernel library |
| `CUDA_HOME` | Path to CUDA toolkit (conda env with `nvcc`) | DeepSpeed GPU arch detection |
| `PATH` | must include protenix env bin | JAX/XLA needs `ptxas` |

### Hardware

CUDA-capable GPU with bf16 support. Recommended: A100 40GB+ for extended preset.
Preview preset fits on 24GB GPUs. Blackwell GPUs (sm_100+, e.g. RTX PRO 6000)
must use `--use_fast_ln False` — the fastfold LayerNorm kernels do not compile
for sm_100+.

### Compute provider order

1. **Local GPU** (default in `.by/config.json`) — fastest iteration, no queue
2. **HPC (RunPod)** — see the `by-deploy-compute` skill for setup
3. **Tamarind** — cloud fallback

---

## Inputs

**Required:**

- **Target structure**: `.cif` (preferred) or `.pdb` file with absolute path
  - Chain IDs must use `label_asym_id` (PDB-standardized), NOT `auth_asym_id`
  - Parse the CIF before writing the YAML — see Common Issues for the snippet
- **Binder length**: integer, recommended 60–150 (default 100)

**Optional:**

- **Hotspot residues**: integer list per chain (`label_seq_id` numbering)
  - User-supplied `"A40, B12"` format must be parsed → `{A: [40], B: [12]}`
- **Crop ranges**: list of `"start-end"` strings to limit which residues participate
- **MSA directory**: precomputed alignment for the target chain
- **Preset**: `preview` (fast, exploration) or `extended` (slow, production)
- **`--N_sample`**: number of designs to generate (default 10)

See `references/yaml-config-spec.md` for the full YAML schema.

---

## Outputs

**Primary results:**

- `<output_dir>/design_outputs/<task_name>/summary.csv` — ranked design table

**Tidy CSV produced by `parse_pxdesign_output.py`:**

| Column | Type | Description |
|--------|------|-------------|
| `rank` | int | Design rank (1 = best, by `ptx_iptm` desc) |
| `name` | str | Design identifier |
| `sequence` | str | Designed binder amino acid sequence |
| `binder_length` | int | Sequence length |
| `af2_easy_success` | bool | AF2-IG easy filter (PASS/FAIL) |
| `af2_opt_success` | bool | AF2-IG strict filter (PASS/FAIL) |
| `ptx_basic_success` | bool | Protenix basic filter (PASS/FAIL) |
| `ptx_success` | bool | Protenix strict filter (PASS/FAIL) |
| `ptx_iptm` | float | Protenix ipTM (0–1, higher = better) |
| `af2_binder_plddt` | float | AF2 binder pLDDT (0–1) |
| `af2_complex_pred_design_rmsd` | float | RMSD predicted vs designed (Å) |
| `task_name` | str | PXDesign task batch (preserves per-hotspot grouping) |

**Design structures:** `<output_dir>/design_outputs/<task_name>/<name>.cif` per design.

See `references/filter-thresholds.md` for filter definitions and interpretation.

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST** — do not skip Q1.

1. **Target structure** (ASK THIS FIRST): Do you have a CIF or PDB file for the
   target? If not, do you have a UniProt ID or PDB code so we can fetch/predict
   one first? PXDesign cannot start without a structure.

2. **Modality check**: Confirm this is a non-antibody binder. If it is an
   antibody, nanobody, or VHH, switch to the `boltzgen` skill before continuing.

3. **Epitope / hotspots**: Do you know which residues on the target should be
   contacted? Provide them in `"A40, A50, B12"` notation. If unknown, we can
   start untargeted or use `proteus-research` to infer hotspots from literature.

4. **Binder size**: How long should the binder be? Default 100. Smaller targets
   or pocket epitopes favor 60–80; large/flat epitopes favor 100–150. See
   `references/de-novo-strategy.md`.

5. **Quality target**: Exploration / feasibility (`preview`) or production
   designs for experimental testing (`extended`)? Extended is ~5–10× slower.

6. **Sample size**: How many designs (`--N_sample`)? Default 10 for preview,
   20–50 for extended. Expected pass rate depends on target difficulty — see
   `references/de-novo-strategy.md`.

7. **Compute provider**: Local GPU (default), HPC (RunPod), or Tamarind?
   Confirm against `.by/config.json`. If local, which GPU architecture
   (Ampere/Hopper/Blackwell)? Blackwell needs `--use_fast_ln False`.

---

## Standard Workflow

🚨 **MANDATORY: USE THE WRITE → BASH → READ PATTERN. DO NOT CALL INTERNAL
PYTHON WRAPPERS.** 🚨

### Pre-flight validation (before first launch)

Run ALL checks before the first `pxdesign` command. Do not debug one error at a
time.

```bash
# 1. GPU architecture
GPU_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)
echo "GPU arch: sm_${GPU_ARCH/./}"
# If >= 10.0: MUST use --use_fast_ln False

# 2. CUDA toolkit
echo "nvcc:  $(which nvcc 2>/dev/null  || echo 'NOT FOUND — set CUDA_HOME')"
echo "ptxas: $(which ptxas 2>/dev/null || echo 'NOT FOUND — add protenix env to PATH')"

# 3. CUDA_HOME
echo "CUDA_HOME: ${CUDA_HOME:-NOT SET}"

# 4. Chain IDs in target CIF (must match what you write in YAML)
python3 -c "
from Bio.PDB import MMCIFParser
s = MMCIFParser(QUIET=True).get_structure('t', 'TARGET.cif')
for chain in s[0]:
    print(f'  Chain {chain.id}: {len(list(chain.get_residues()))} residues')
"

# 5. Confirm each hotspot residue number exists in the target chain
```

✅ **VERIFICATION:** All five checks succeed. If ANY check fails, fix it before
launching. After one failed launch, switch to BoltzGen `protein-anything` as a
fallback (rare path).

### Step 1 — Build the YAML config

Use the helper script (recommended) or write directly:

```bash
python scripts/build_config.py \
  --target /data/targets/IL6R.cif \
  --hotspots "A40,A50,A55,B12" \
  --binder-length 80 \
  --preset extended \
  --out /tmp/il6r/config.yaml
```

✅ **VERIFICATION:** `✓ Config written: /tmp/il6r/config.yaml (3 chains, 4 hotspots)`

The script validates against the schema in `references/yaml-config-spec.md`
before writing. It parses the CIF, confirms each chain exists under
`label_asym_id`, and confirms each hotspot residue number is present.

### Step 2 — Run the CLI via Bash

```bash
PATH=/path/to/conda/envs/protenix/bin:$PATH \
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
CUTLASS_PATH=$HOME/cutlass \
CUDA_HOME=$CUDA_HOME \
pxdesign pipeline \
  --preset preview \
  -i /tmp/il6r/config.yaml \
  --N_sample 10 \
  --dtype bf16 \
  --use_fast_ln True \
  -o /tmp/il6r/output
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `pipeline` | Yes | — | Subcommand (always `pipeline`) |
| `--preset` | Yes | — | `preview` (fast) or `extended` (production) |
| `-i` | Yes | — | Path to YAML config |
| `--N_sample` | No | 10 | Number of design samples |
| `--dtype` | No | `bf16` | Always `bf16` |
| `--use_fast_ln` | No | `True` | `True` for sm_80–sm_90; `False` for sm_100+ |
| `-o` | No | auto | Output directory |

✅ **VERIFICATION:** `summary.csv` exists at
`<output_dir>/design_outputs/<task_name>/summary.csv`.

### Step 3 — Parse the output

```bash
python scripts/parse_pxdesign_output.py \
  --output-dir /tmp/il6r/output \
  --out /tmp/il6r/designs.csv
```

✅ **VERIFICATION:** `✓ Parsed 10 designs across 1 task batch → /tmp/il6r/designs.csv`

The script auto-discovers the `summary.csv` (handles per-hotspot batching when
PXDesign produces multiple task directories) and emits a single tidy CSV.

### Step 4 — Inspect & advance

Sort by `ptx_iptm` desc, then pass designs with `ptx_basic_success=True` to the
`by-screening` skill for liability and developability checks.

---

## When Scripts Fail

Follow this hierarchy (taken from the BY quality bar):

1. **Fix and retry (90%)** — missing env var, wrong chain ID, wrong GPU flag.
   Re-read the error, fix one thing, re-run. Use the pre-flight checklist.
2. **Modify the script (5%)** — `build_config.py` or `parse_pxdesign_output.py`
   has a wrong column name or missed an edge case. Edit it directly.
3. **Use as reference (4%)** — read the script, adapt the approach inline. Only
   when the script's contract does not fit (e.g. PXDesign emits a new column).
4. **Write from scratch (1%)** — only if PXDesign output format changed
   incompatibly. Document why in the campaign log.

---

## Decision Points

### Preset selection

| Preset | Use Case | Speed | Quality |
|--------|----------|-------|---------|
| `preview` | Exploration, feasibility, quick iteration | Fast (10–20 min) | Good — suitable for triage |
| `extended` | Final designs for experimental validation | Slow (60–120+ min) | Best — full refinement pipeline |

Do not send `preview` results to experimental validation without re-running on
`extended`.

### Binder length by target geometry

| Target Size | Recommended `binder_length` | Notes |
|-------------|-----------------------------|-------|
| Small (<150 residues) | 60–80 | Shorter binders avoid steric clashes |
| Medium (150–400 residues) | 80–120 | Default 100 works well |
| Large (>400 residues) | 100–150 | Longer binders for larger interfaces |
| Flat epitope | +20 above default | More residues for shape complementarity |
| Concave pocket | −20 below default | Compact binders fit pockets |

See `references/de-novo-strategy.md` for scaffold preset selection and
expected pass rates by target difficulty.

### Sample size

Set `--N_sample` based on expected pass rate × desired output count:

- Easy targets (~80% pass rate): `--N_sample 10` → ~8 passing
- Standard (~50%): `--N_sample 20` → ~10 passing
- Hard (~25%): `--N_sample 40` → ~10 passing
- Novel (<15%): `--N_sample 80+` and consider re-targeting

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `ModuleNotFoundError` on import | Missing env vars | Set all five (`PROTENIX_DATA_ROOT_DIR`, `TOOL_WEIGHTS_ROOT`, `CUTLASS_PATH`, `CUDA_HOME`, `PATH`) in the same Bash command | See Installation |
| CUDA OOM | Binder too long or target too large | Reduce `binder_length`, add `crop:`, or use a larger GPU | `references/yaml-config-spec.md` |
| Empty `summary.csv` | All designs filtered out | Lower thresholds, switch to `extended`, increase `--N_sample` | `references/filter-thresholds.md` |
| No `summary.csv` found | Wrong output path or run crashed early | Check stderr; search recursively for any `summary.csv` | — |
| `cutlass` errors | Missing or wrong `CUTLASS_PATH` | Verify `$HOME/cutlass` exists and is built | — |
| Very slow on preview | GPU not detected, running on CPU | Check `nvidia-smi`; confirm CUDA is visible inside the conda env | — |
| `FileNotFoundError` for target | Wrong path in YAML | Use absolute paths for `target.file` | `references/yaml-config-spec.md` |
| `fastfold_layer_norm_cuda` compilation failure | Blackwell sm_100+ | Use `--use_fast_ln False` | Pre-flight check 1 |
| `ValueError: Chain X does not exist` | Used `auth_asym_id` from PDB instead of `label_asym_id` | Parse the CIF first (pre-flight check 4); use the chain IDs that script prints | `references/yaml-config-spec.md` |
| DeepSpeed import error | Missing `CUDA_HOME` | Point at the conda env containing `bin/nvcc` | — |
| `XlaRuntimeError: NOT_FOUND: ptxas` | `ptxas` not on `PATH` | Prepend protenix env bin to `PATH` | — |
| Hotspots silently ignored | Wrong YAML type — strings like `"A40"` instead of integers | Use integers under the chain key: `A: { hotspots: [40] }` | `references/yaml-config-spec.md` |
| Preview results look great, extended looks worse | Preview filters are looser; extended uses stricter pipeline | Trust `extended`. Re-tune `binder_length` or hotspots, do not regress to preview | `references/filter-thresholds.md` |
| Per-hotspot batches scatter outputs | PXDesign creates one task directory per hotspot group | Use `scripts/parse_pxdesign_output.py` — it concatenates all batches into one CSV | Script docstring |

---

## Best Practices

1. 🚨 **CRITICAL:** Run the pre-flight checklist before the first launch. Do not
   debug one error at a time.
2. 🚨 **CRITICAL:** Hotspots are **integers** under the chain key. Strings like
   `"A40"` are silently ignored.
3. ✅ **REQUIRED:** Parse the CIF to confirm `label_asym_id` chain letters
   before writing the YAML. PDB `auth_asym_id` is NOT what PXDesign reads.
4. ✅ **REQUIRED:** Use absolute paths for `target.file` and the output
   directory.
5. ✅ Always specify `--dtype bf16` explicitly.
6. ✅ Use `preview` for exploration; only graduate to `extended` once the
   target / hotspot / length combination looks promising.
7. ✅ Sort designs by `ptx_iptm` descending and gate on
   `ptx_basic_success=True` before screening.
8. ✅ When Protenix and AF2 filters disagree, **trust Protenix** for de novo
   designs. PXDesign is internally aligned with Protenix.
9. ✨ **Optional:** Provide a precomputed MSA via `chains.<id>.msa` if available
   — improves target representation.
10. ❌ **DON'T:** Send `preview` results to experimental validation. Re-run on
    `extended` first.
11. ❌ **DON'T:** Use Tamarind silently if `.by/config.json` says `"local"`.
    Report the local failure first.

---

## Suggested Next Steps

After PXDesign returns a parsed `designs.csv`:

1. **Screen** all designs with the `by-screening` skill — runs ipSAE,
   liability checks, developability filters, and composite ranking. Required
   before any experimental decision.
2. **Refold** top-N candidates with the `protenix` skill for an independent
   structure validation (multi-seed if possible).
3. **Score** refolded structures with the `by-scoring` skill for ipSAE
   interface quality and composite ranking.
4. **Rank & present** final candidates via `by-display` formatting.
5. **Lab submission** (only when triple-gated approval is in hand) — see the
   BY campaign workflow in `templates/CLAUDE.md`.

If no designs pass `ptx_basic_success`:

- Increase `--N_sample`
- Switch `preview` → `extended`
- Re-tune hotspots (see `references/de-novo-strategy.md`)
- Adjust `binder_length` (see Decision Points)
- Add a tighter `crop:` to focus compute on the epitope region

---

## Related Skills

**Upstream (run before):**
- `by-research` — target dossier, epitope identification, prior art search
- `protenix` — predict a target structure when none is available

**Downstream (run after):**
- `by-screening` — ipSAE + liabilities + developability + composite ranking
- `by-scoring` — interface quality scoring on refolded structures
- `by-display` — present ranked results to the user

**Alternative / complementary:**
- `boltzgen` — antibody / nanobody binder design (use this instead for
  Ig-fold modalities)
- `by-design-workflow` — master orchestration when running a full campaign

---

## References

**Detailed documentation in this skill:**

- `references/yaml-config-spec.md` — complete YAML schema, validation rules, and
  the `label_asym_id` vs `auth_asym_id` gotcha
- `references/filter-thresholds.md` — AF2-IG easy/strict, Protenix basic/strict
  thresholds with PASS/FAIL interpretation
- `references/de-novo-strategy.md` — hotspot selection strategy, scaffold preset
  selection (compact/extended/diverse), expected pass rates by target
  difficulty with the sample sizes that justified those numbers

**Scripts:**

- `scripts/build_config.py` — CLI that takes a target CIF + hotspot list +
  preset and emits a validated PXDesign YAML config
- `scripts/parse_pxdesign_output.py` — CLI that reads a PXDesign output
  directory (handles per-hotspot batching) and emits a tidy CSV ranked by
  `ptx_iptm`

**Related BY skills:** `boltzgen`, `protenix`, `by-scoring`, `by-screening`,
`by-research`, `by-design-workflow`, `by-deploy-compute`.

**License:** All third-party packages used by this skill (Biopython, pandas,
PyYAML, CUTLASS) permit commercial use in AI applications.
