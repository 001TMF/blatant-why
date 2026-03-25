---
name: pxdesign
description: >
  De novo protein binder design using PXDesign. Use this skill when designing
  non-antibody protein binders against a target structure. Covers YAML config
  creation, CLI invocation, output parsing, and result interpretation.
  For antibody/nanobody binders, use boltzgen instead.
  For structure prediction only, use proteus-fold.
  For scoring and screening, use by-scoring and by-screening.
category: tool
tags: [pxdesign, binder-design, de-novo, protein-design, cli]
---

# BY-Prot -- De Novo Protein Binder Design (PXDesign)

You are an expert at designing de novo protein binders using PXDesign via the
`pxdesign` CLI. This skill covers YAML config construction, CLI invocation,
output parsing, and result interpretation. PXDesign achieves 17-82% hit rates
for de novo binder design.

---

## 1. Prerequisites

### Environment Variables (all four required)

| Variable | Value | Purpose |
|----------|-------|---------|
| `PROTENIX_DATA_ROOT_DIR` | `$PROTEUS_PROT_DIR/release_data/ccd_cache` | CCD chemical component dictionary cache |
| `TOOL_WEIGHTS_ROOT` | `$PROTEUS_PROT_DIR/tool_weights` | PXDesign model weights |
| `CUTLASS_PATH` | `$HOME/cutlass` | NVIDIA CUTLASS kernel library |
| `CUDA_HOME` | Path to CUDA toolkit (e.g. conda env with `nvcc`) | Required by DeepSpeed for GPU architecture detection |

### Tool Path

`$PROTEUS_PROT_DIR` -- all PXDesign files, weights, and release data live here.

### PATH Requirements

`PATH` must include the protenix conda env's bin directory for JAX/XLA
compilation. The Protenix evaluation filters use JAX, which requires `ptxas`
(PTX assembler) on PATH. `ptxas` is typically in the protenix env, not the
pxdesign env.

```bash
export PATH=/path/to/conda/envs/protenix/bin:$PATH
```

### Hardware

Requires a CUDA-capable GPU with bf16 support. Recommended: A100 40GB+ for
extended preset. Preview preset fits on 24GB GPUs.

**GPU Architecture Note:** Blackwell GPUs (sm_100+, e.g. RTX PRO 6000) must use
`--use_fast_ln False`. The fastfold LayerNorm CUDA kernels only compile for
sm_70/80/86/90 and will fail on sm_100+.

---

## Pre-flight Validation (MANDATORY before first design launch)

Run ALL checks before the first pxdesign command. Do NOT launch and debug one error at a time.

```bash
# 1. GPU architecture
GPU_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)
echo "GPU arch: sm_${GPU_ARCH/./}"
# If >= 10.0: MUST use --use_fast_ln False

# 2. CUDA toolkit
echo "nvcc: $(which nvcc 2>/dev/null || echo 'NOT FOUND — set CUDA_HOME')"
echo "ptxas: $(which ptxas 2>/dev/null || echo 'NOT FOUND — add protenix env to PATH')"

# 3. CUDA_HOME
echo "CUDA_HOME: ${CUDA_HOME:-NOT SET}"

# 4. Chain IDs in target CIF
python3 -c "
from Bio.PDB import MMCIFParser
s = MMCIFParser(QUIET=True).get_structure('t', 'TARGET.cif')
for chain in s[0]:
    print(f'  Chain {chain.id}: {len(list(chain.get_residues()))} residues')
"

# 5. Hotspot residues exist in chain
# Verify each hotspot residue number exists in the target chain
```

If ANY check fails, fix it before launching. After 1 failed pxdesign launch,
switch to BoltzGen protein-anything as fallback.

---

## 2. When to Use proteus-prot

```
User wants a BINDER that is NOT an antibody/nanobody
|
+-- Quick exploration or feasibility check?
|   --> preset: preview  (faster, fewer refinement steps)
|
+-- Production-quality designs for experimental testing?
    --> preset: extended  (full pipeline, higher quality)
```

### Preset Comparison

| Preset | Use Case | Speed | Quality |
|--------|----------|-------|---------|
| `preview` | Exploration, feasibility, quick iteration | Fast | Good -- suitable for triage |
| `extended` | Final designs for experimental validation | Slower | Best -- full refinement pipeline |

### Binder Length Guide

| Target Size | Recommended binder_length | Notes |
|-------------|--------------------------|-------|
| Small (<150 residues) | 60-80 | Shorter binders avoid steric clashes |
| Medium (150-400 residues) | 80-120 | Default 100 works well |
| Large (>400 residues) | 100-150 | Longer binders for larger interfaces |
| Flat epitope | +20 above default | More residues to create shape complementarity |
| Concave pocket | -20 below default | Compact binders fit pockets better |

---

## 3. How to Run -- Write / Bash / Read Pattern

### Step 1: Write YAML Config

Use the **Write** tool to create a YAML configuration file. See
`references/yaml-config-spec.md` for the full specification.

**Basic config (target with one chain, no hotspots):**

```yaml
target:
  file: "/path/to/target.cif"
  chains:
    A: "all"
binder_length: 100
```

**Config with hotspots and crop ranges:**

```yaml
target:
  file: "/path/to/target.cif"
  chains:
    A:
      crop: ["1-116"]
      hotspots: [40, 50, 55, 99]
      msa: "./msa/chain_A"
    B: "all"
binder_length: 80
```

Write the config to a working directory:

```
Write tool -> /path/to/workdir/config.yaml
```

### Step 2: Run PXDesign CLI via Bash

```bash
PATH=/path/to/conda/envs/protenix/bin:$PATH \
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
CUTLASS_PATH=$HOME/cutlass \
CUDA_HOME=$CUDA_HOME \
pxdesign pipeline \
  --preset preview \
  -i /path/to/workdir/config.yaml \
  --N_sample 10 \
  --dtype bf16 \
  --use_fast_ln True \
  -o /path/to/workdir/output
```

**All CLI flags:**

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `pipeline` | Yes | -- | Subcommand (always `pipeline`) |
| `--preset` | Yes | -- | `preview` or `extended` |
| `-i` | Yes | -- | Path to YAML config file |
| `--N_sample` | No | 10 | Number of design samples to generate |
| `--dtype` | No | `bf16` | Data type. Always use `bf16` |
| `--use_fast_ln` | No | `True` | Fast LayerNorm kernels. Use `True` for Ampere/Hopper (sm_80-sm_90). Use `False` for Blackwell (sm_100+) |
| `-o` | No | auto | Output directory. If omitted, PXDesign chooses one |

### Step 3: Read Output

The primary output is a CSV summary file at:

```
<output_dir>/design_outputs/<task_name>/summary.csv
```

If the expected path does not exist, search recursively for any `summary.csv`
under the output directory.

Use the **Read** tool to load and parse the CSV. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| `rank` | int | Design rank (1 = best) |
| `name` | str | Design identifier |
| `sequence` | str | Designed binder amino acid sequence |
| `af2_opt_success` | bool | AF2 optimization filter pass |
| `af2_easy_success` | bool | AF2-IG easy filter pass |
| `ptx_success` | bool | Protenix filter pass |
| `ptx_basic_success` | bool | Protenix basic filter pass |
| `ptx_iptm` | float | Protenix ipTM score (0-1, higher = better) |
| `af2_binder_plddt` | float | AF2 binder pLDDT confidence (0-1) |
| `af2_complex_pred_design_rmsd` | float | RMSD between predicted and designed complex (Angstroms) |

Results are sorted by `ptx_iptm` descending. Present the top candidates in a
table, highlighting which filters each design passed.

---

## 4. YAML Config Quick Reference

Full specification in `references/yaml-config-spec.md`.

### Required Fields

- `target.file` -- path to target structure (`.cif` or `.pdb`)
- `target.chains` -- dict of chain IDs to include
- `binder_length` -- integer, number of residues for the designed binder

### Hotspot Format

Hotspot residues are specified as **integers** (residue numbers) under the
per-chain config. The chain letter is determined by the YAML key:

```yaml
chains:
  A:
    hotspots: [40, 50, 55]   # residues 40, 50, 55 on chain A
```

When the user provides hotspots in "A40, A50, B10" format, parse the chain
letter from the first character and the residue number from the rest, then
group by chain.

### Crop Ranges

Crop ranges restrict which residues of a chain are included. Format is a list
of `"start-end"` strings:

```yaml
chains:
  A:
    crop: ["1-116", "200-250"]   # only include residues 1-116 and 200-250
```

---

## 5. Filter Thresholds

PXDesign applies built-in validation filters. See `references/filter-thresholds.md`
for complete details.

**Quick reference:**

| Filter | Key Thresholds | Stringency |
|--------|---------------|------------|
| AF2-IG easy | ipAE<10.85, ipTM>0.5, pLDDT>0.8, RMSD<3.5A | Standard |
| AF2-IG strict | ipAE<7.0, pLDDT>0.9, RMSD<1.5A | High |
| Protenix basic | ipTM>0.8, pTM>0.8, RMSD<2.5A | Standard |
| Protenix strict | ipTM>0.85, pTM>0.88, RMSD<2.5A | High |

A design marked `ptx_success=True` passed Protenix strict. A design with
`ptx_basic_success=True` but `ptx_success=False` passed basic but not strict.

---

## 6. Common Mistakes

1. **Missing environment variables.** All four env vars must be set in the
   same Bash command. If any are missing, `pxdesign` will fail with import or
   file-not-found errors.

2. **Using MCP function calls instead of CLI.** This skill uses Write + Bash +
   Read. Always use the CLI directly -- do not call internal Python wrapper
   functions. The CLI is the only supported interface.

3. **Wrong hotspot format in YAML.** Hotspots are **integers** in the YAML,
   not strings like `"A40"`. The chain letter comes from the YAML key, not the
   hotspot value. Wrong: `hotspots: ["A40"]`. Right: `hotspots: [40]`.

4. **Setting `--use_fast_ln` incorrectly.** This flag enables optimized LayerNorm
   kernels. Use `True` for Ampere/Hopper (sm_80-sm_90) and `False` for
   Blackwell (sm_100+). Using `True` on Blackwell causes nvcc compilation failure.

5. **Omitting `--dtype bf16`.** Always specify bf16 for correct GPU precision.

6. **Reading wrong output path.** Look for `summary.csv` under
   `<output_dir>/design_outputs/<task_name>/`. If not found, search
   recursively for `summary.csv` in the output directory tree.

7. **Using auth_asym_id instead of label_asym_id.** PXDesign uses `label_asym_id`
   internally, NOT `auth_asym_id` from PDB. When you download a CIF from PDB,
   the chain letters in `auth_asym_id` (e.g. R, H, L) may differ from
   `label_asym_id` (e.g. A, B, C). Always parse the CIF to find the correct
   `label_asym_id` chain letters before writing the YAML config. See the
   pre-flight validation section for a parsing snippet.

8. **Confusing presets.** `preview` is for exploration; `extended` is for
   production. Do not send preview results to experimental validation without
   re-running on extended.

---

## 7. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError` on import | Missing `PROTENIX_DATA_ROOT_DIR` or `TOOL_WEIGHTS_ROOT` | Set all 4 env vars in the Bash command |
| CUDA OOM | Binder too long or target too large for GPU memory | Reduce `binder_length`, use crop ranges, or use a larger GPU |
| Empty `summary.csv` | All designs filtered out | Lower thresholds or increase `--N_sample` |
| No `summary.csv` found | Wrong output path or run crashed early | Check Bash stderr for errors; search recursively for any CSV |
| `cutlass` errors | Missing or wrong `CUTLASS_PATH` | Verify `$HOME/cutlass` exists and contains CUTLASS build |
| Very slow on preview | GPU not detected, running on CPU | Verify CUDA is available; check `nvidia-smi` |
| `FileNotFoundError` for target | Wrong path in YAML config | Use absolute paths for `target.file` |
| `fastfold_layer_norm_cuda` compilation failure | GPU arch not in gencode list (Blackwell sm_100+) | Use `--use_fast_ln False` |
| `ValueError: Chain X does not exist` | Using `auth_asym_id` instead of `label_asym_id` | Parse CIF for `label_asym_id` chain letters; see pre-flight validation |
| DeepSpeed import error | Missing `CUDA_HOME` | Set `CUDA_HOME` to the directory containing `bin/nvcc` (e.g. protenix conda env) |
| `XlaRuntimeError: NOT_FOUND: ptxas` | `ptxas` not on PATH for JAX/XLA compilation | Add protenix conda env bin to PATH: `PATH=/path/to/protenix/bin:$PATH` |

---

## 8. Examples

### Example 1: Basic Binder Design (Preview)

Design a 100-residue binder against chain A of a target structure.

**Step 1 -- Write config:**
```yaml
target:
  file: "/data/targets/IL6R.cif"
  chains:
    A: "all"
binder_length: 100
```
Write to `/data/runs/il6r_binder/config.yaml`.

**Step 2 -- Run CLI:**
```bash
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
CUTLASS_PATH=$HOME/cutlass \
CUDA_HOME=$CUDA_HOME \
pxdesign pipeline \
  --preset preview \
  -i /data/runs/il6r_binder/config.yaml \
  --N_sample 10 \
  --dtype bf16 \
  --use_fast_ln True \
  -o /data/runs/il6r_binder/output
```

**Step 3 -- Read results:**
Read `/data/runs/il6r_binder/output/design_outputs/*/summary.csv` and present
the top designs ranked by `ptx_iptm`.

### Example 2: Hotspot-Directed Design (Extended)

Design a compact 80-residue binder targeting specific epitope residues on two
chains. User specified hotspots: A40, A50, A55, B10, B15.

**Step 1 -- Write config:**
```yaml
target:
  file: "/data/targets/receptor_complex.cif"
  chains:
    A:
      hotspots: [40, 50, 55]
    B:
      hotspots: [10, 15]
binder_length: 80
```
Write to `/data/runs/receptor_hotspot/config.yaml`.

**Step 2 -- Run CLI:**
```bash
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
CUTLASS_PATH=$HOME/cutlass \
CUDA_HOME=$CUDA_HOME \
pxdesign pipeline \
  --preset extended \
  -i /data/runs/receptor_hotspot/config.yaml \
  --N_sample 20 \
  --dtype bf16 \
  --use_fast_ln True \
  -o /data/runs/receptor_hotspot/output
```

**Step 3 -- Read and interpret.** Rank by `ptx_iptm`, verify `ptx_success`
or `ptx_basic_success` flags, and run through screening (by-screening
skill) before presenting to user.

### Example 3: Large Target with Crop Ranges and MSA

Target has a 600-residue chain but the binding site is in residues 200-350.
Crop to focus compute on the relevant region.

**Step 1 -- Write config:**
```yaml
target:
  file: "/data/targets/large_target.cif"
  chains:
    A:
      crop: ["200-350"]
      hotspots: [250, 275, 290, 310]
      msa: "/data/msas/large_target_A"
binder_length: 120
```
Write to `/data/runs/large_target_crop/config.yaml`.

**Step 2 -- Run CLI:**
```bash
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
CUTLASS_PATH=$HOME/cutlass \
CUDA_HOME=$CUDA_HOME \
pxdesign pipeline \
  --preset extended \
  -i /data/runs/large_target_crop/config.yaml \
  --N_sample 15 \
  --dtype bf16 \
  --use_fast_ln True \
  -o /data/runs/large_target_crop/output
```

**Step 3 -- Read results** and screen as usual. Crop ranges significantly
reduce GPU memory usage and runtime for large targets.

---

## 9. Residue Numbering Utility

PDB structures have two numbering schemes: `auth_asym_id`/`auth_seq_id` (from
the original publication) and `label_asym_id`/`label_seq_id` (standardized by
PDB). PXDesign uses the `label_*` scheme. Use this snippet to translate:

```python
# Parse CIF for label_asym_id mapping
from Bio.PDB import MMCIFParser
parser = MMCIFParser(QUIET=True)
structure = parser.get_structure('target', 'target.cif')
for model in structure:
    for chain in model:
        residues = list(chain.get_residues())
        print(f"Chain {chain.id} (label_asym_id): {len(residues)} residues, range {residues[0].id[1]}-{residues[-1].id[1]}")
```

When the user provides hotspot residues in auth numbering (e.g. from UniProt or
literature), use this script to find the matching `label_seq_id` values before
writing the YAML config.

---

## 10. Post-Design Workflow

After collecting PXDesign results:

1. **Screen** all designs using the by-screening skill (structural
   confidence, liability checks, developability).
2. **Refold** top candidates with proteus-fold for independent structure
   validation.
3. **Score** refolded structures with ipSAE (by-scoring skill) for
   interface quality assessment.
4. **Rank** using composite scoring (by-scoring skill).
5. **Present** final candidates with all metrics in a results table.

If no designs pass screening, consider:
- Increasing `--N_sample` (more designs = more chances)
- Switching from `preview` to `extended` preset
- Adding or adjusting hotspot residues
- Modifying `binder_length` (see sizing guide in Section 2)
- Using crop ranges to focus on a smaller epitope region
