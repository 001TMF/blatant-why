---
name: boltzgen
description: >
  Antibody and nanobody binder design using Proteus-AB (BoltzGen diffusion +
  Protenix refolding). Covers entity YAML specification, CLI invocation,
  protocol selection (nanobody-anything / antibody-anything), MSA modes, and
  output parsing. Use this skill whenever the user needs to design an antibody
  or nanobody binder against a protein target.
category: tool
tags: [antibody, nanobody, binder-design, boltzgen, proteus-ab, diffusion]
---

# proteus-ab — Antibody / Nanobody Binder Design

You are an expert at running Proteus-AB for antibody and nanobody design.
This skill teaches the exact Write → Bash → Read pattern for invoking the
tool via CLI. **Never call MCP functions directly** — always use the Write
tool to create the entities YAML, the Bash tool to run the CLI, and the
Read tool to parse results.

---

## 1. Prerequisites

| Requirement | Details |
|-------------|---------|
| Tool path | Set via `PROTEUS_AB_DIR` or `BOLTZGEN_DIR` env var |
| CLI binary | `proteus-ab` (on PATH after env setup) |
| GPU | Required — CUDA-capable, ≥24 GB VRAM recommended |
| Env: `PROTEUS_MODELS_DIR` | `~/.cache/proteus-ab` (model weights) |
| Env: `LAYERNORM_TYPE` | `openfold` (required for correct inference) |
| Target structure | CIF or PDB file with clean chain IDs |

---

## 2. When to Use proteus-ab

```
User wants a binder...
│
├── Antibody or nanobody format required?
│   ├── YES, nanobody (VHH / single-domain)
│   │   └── proteus-ab  protocol: nanobody-anything
│   ├── YES, full antibody (VH/VL Fab)
│   │   └── proteus-ab  protocol: antibody-anything
│   └── NO, any format acceptable
│       └── Consider proteus-prot (de novo miniprotein) first;
│           switch to proteus-ab if proteus-prot fails
│
├── Need to validate an existing antibody structure?
│   └── Use proteus-fold instead
│
└── Need to score an existing antibody design?
    └── Use proteus-scoring skill (ipSAE)
```

---

## 3. Protocols

| Protocol | Format | Chains | Design Speed | Recommended Designs |
|----------|--------|--------|-------------|-------------------|
| `nanobody-anything` | VHH single-domain | 1 chain | Faster | 10–50 |
| `antibody-anything` | VH/VL Fab pair | 2 chains | Slower | 20–100 |

**Choose nanobody** when: smaller binder preferred, tissue penetration needed,
or faster iteration desired.

**Choose antibody** when: Fc effector function needed, higher affinity
required, or therapeutic antibody format mandated.

---

## 4. How to Run (Write → Bash → Read)

### Step 1: Write the entities YAML spec

Use the **Write** tool to create a design specification file. See
`references/entities-yaml-spec.md` for the full format.

```yaml
# /path/to/workspace/design_spec.yaml
entities:
- file:
    path: ./target.cif
    include:
    - chain:
        id: A
    binding_types:
    - chain:
        id: A
        binding: 7..12,27..34
```

**Binding residues** use `..` range notation: a list like `[7,8,9,10,11,12,27,28,29,30]`
becomes `7..12,27..30`. These are `label_seq_id` values (1-indexed, sequential, no gaps).

To include scaffold templates, add a second entity pointing to a scaffold YAML:
```yaml
- file:
    path: $BOLTZGEN_DIR/example/  # from BoltzGen repofab_scaffolds/adalimumab.6cr1.yaml
```

### Step 2: Run the CLI via Bash

```bash
PROTEUS_MODELS_DIR="$HOME/.cache/proteus-ab" \
LAYERNORM_TYPE="openfold" \
proteus-ab run /path/to/workspace/design_spec.yaml \
  --protocol nanobody-anything \
  --num_designs 20 \
  --msa-mode none \
  --budget 48 \
  --output /path/to/workspace/output \
  --prefilter
```

### Step 3: Read the output CSV

```bash
# Primary location
cat <output_dir>/final_ranked_designs/final_designs_metrics_*.csv

# Fallback: recursive search
find <output_dir> -name 'final_designs_metrics_*.csv'
```

Use the **Read** tool on the CSV. Results are sorted by `iptm` descending.

---

## 5. CLI Parameters

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<spec_path>` | positional | required | Path to entities YAML file |
| `--protocol` | string | required | `nanobody-anything` or `antibody-anything` |
| `--num_designs` | int | 10 | Number of designs to generate |
| `--msa-mode` | string | `none` | MSA strategy: `none`, `precomputed`, or `nim` |
| `--budget` | int | 48 | Sampling budget (diffusion steps) |
| `--output` | path | auto | Output directory |
| `--prefilter` | flag | off | Enable pre-filtering before Protenix refolding |

**Budget guidance:** 48 for preview, 96–128 for production. Higher budget
increases diversity but costs more GPU time.

---

## 6. MSA Modes

| Mode | Source | When to Use |
|------|--------|-------------|
| `none` | No MSA | Default. Fast. Sufficient for most design runs |
| `precomputed` | A3M files | When you have pre-built alignments from MMseqs2 or HHblits |
| `nim` | NVIDIA NIM API | Remote MSA generation. Requires NIM API access |

Start with `none`. Only use `precomputed` or `nim` if initial designs show
poor structural confidence (pLDDT < 70).

---

## 7. Entities YAML Specification (Summary)

The entities YAML defines target chains, binding residues, and optional
scaffold templates. Full specification in `references/entities-yaml-spec.md`.

**Key rules:**
- Each entity is a `file:` block with `path`, `include`, and optional `binding_types`
- `include` lists which chains to use: `- chain: { id: A }`
- `binding_types` specifies epitope residues using range notation: `binding: 7..12,27..34`
- Binding residues use **`label_seq_id`** (1-indexed, sequential, per-chain)
- Scaffolds are separate entities pointing to scaffold YAML files

### Range Notation

Convert residue lists to `..` ranges for contiguous stretches:

| Input | Range Notation |
|-------|---------------|
| `[7, 8, 9, 10, 11, 12]` | `7..12` |
| `[7, 8, 9, 27, 28, 29, 30]` | `7..9,27..30` |
| `[5, 10, 15]` | `5..5,10..10,15..15` |
| `[1, 2, 3, 4, 5, 20, 21, 22, 50]` | `1..5,20..22,50..50` |

Singletons are expressed as `N..N`.

---

## 8. Output Format

Output CSV: `<output_dir>/final_ranked_designs/final_designs_metrics_*.csv`

| Column | Type | Description |
|--------|------|-------------|
| `design_id` | string | Unique design identifier |
| `iptm` | float | Interface predicted TM-score (0–1) |
| `ptm` | float | Predicted TM-score (0–1) |
| `plddt` | float | Per-residue confidence, mean (0–100) |
| `design_iptm` | float | Design-stage ipTM before refolding |
| `ipsae_min` | float | Min of directional ipSAE scores (0–1) |
| `rmsd` | float | CA-RMSD between designed and refolded (Angstroms) |
| `sequence` | string | Full amino acid sequence |

**Sorted by `iptm` descending.** Apply hard filters: ipTM > 0.5, pLDDT > 70,
RMSD < 3.5 A. Then rank by composite score (see proteus-scoring skill).

---

## 9. Pipeline Stages

Proteus-AB runs a 6-stage internal pipeline. See `references/pipeline-stages.md`
for details.

```
Design (BoltzGen) → Inverse Fold (AntiFold) → [Pre-filter] → Protenix Refold → Analysis → Filtering
```

The `--prefilter` flag enables stage 3, which discards low-confidence designs
before the expensive Protenix refolding step. Recommended for production runs
(num_designs ≥ 50).

---

## 10. Common Mistakes

| Mistake | Consequence | Fix |
|---------|------------|-----|
| Using `auth_seq_id` instead of `label_seq_id` for binding residues | Wrong epitope, wasted campaign | Always convert author numbering to label_seq_id first |
| Missing `LAYERNORM_TYPE=openfold` env var | Silent numerical errors or crashes | Always set both env vars |
| Missing `PROTEUS_MODELS_DIR` env var | Model weights not found | Set to `~/.cache/proteus-ab` |
| Budget too low (< 32) | Poor diversity, repetitive designs | Use ≥ 48 for preview, ≥ 96 for production |
| Skipping `--prefilter` on large runs | Wastes GPU time refolding bad designs | Enable for num_designs ≥ 50 |
| Using antibody protocol when nanobody suffices | Slower, needs more designs | Match protocol to actual format need |
| Forgetting scaffold entity in YAML | Uses default scaffolds only | Add explicit scaffold if specific template desired |
| Binding residues on buried surface | Designs cannot reach epitope | Verify surface exposure (SASA > 0.25) |

---

## 11. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `FileNotFoundError` on model weights | `PROTEUS_MODELS_DIR` not set or wrong path | Verify `~/.cache/proteus-ab` exists with weights |
| CUDA out of memory | GPU VRAM insufficient | Reduce `--num_designs` or `--budget`; use smaller batch |
| All designs have ipTM < 0.4 | Bad epitope selection or target issue | Re-examine binding residues; verify target with proteus-fold |
| No CSV output found | Run failed silently or wrong output path | Check stderr; look recursively for `final_designs_metrics_*.csv` |
| Very similar sequences across all designs | Budget too low or diversity not explored | Increase `--budget`; try different binding residues |
| `LAYERNORM_TYPE` error | Env var missing | Export `LAYERNORM_TYPE=openfold` before running |
| Slow run with `--msa-mode nim` | Network latency to NIM API | Switch to `none` for faster iteration |

---

## 12. Examples

### Example 1: Nanobody against a single-chain target

```bash
# 1. Write the entities YAML (via Write tool)
# Target: chain A of cleaned PDB, epitope at residues 45-52 and 78-85
```

```yaml
# workspace/nb_design_spec.yaml
entities:
- file:
    path: ./target_clean.cif
    include:
    - chain:
        id: A
    binding_types:
    - chain:
        id: A
        binding: 45..52,78..85
```

```bash
# 2. Run CLI (via Bash tool)
PROTEUS_MODELS_DIR="$HOME/.cache/proteus-ab" \
LAYERNORM_TYPE="openfold" \
proteus-ab run workspace/nb_design_spec.yaml \
  --protocol nanobody-anything \
  --num_designs 20 \
  --msa-mode none \
  --budget 48 \
  --output workspace/nb_output
```

```bash
# 3. Read results (via Read tool)
# Look for: workspace/nb_output/final_ranked_designs/final_designs_metrics_*.csv
```

### Example 2: Antibody with scaffold template

```yaml
# workspace/ab_design_spec.yaml
entities:
- file:
    path: ./antigen.cif
    include:
    - chain:
        id: B
    binding_types:
    - chain:
        id: B
        binding: 100..115,140..148
- file:
    path: $BOLTZGEN_DIR/example/  # from BoltzGen repofab_scaffolds/adalimumab.6cr1.yaml
```

```bash
PROTEUS_MODELS_DIR="$HOME/.cache/proteus-ab" \
LAYERNORM_TYPE="openfold" \
proteus-ab run workspace/ab_design_spec.yaml \
  --protocol antibody-anything \
  --num_designs 50 \
  --msa-mode none \
  --budget 96 \
  --output workspace/ab_output \
  --prefilter
```

### Example 3: Multi-chain target with scattered epitope

```yaml
# workspace/multichain_spec.yaml
entities:
- file:
    path: ./complex.cif
    include:
    - chain:
        id: A
    - chain:
        id: B
    binding_types:
    - chain:
        id: A
        binding: 22..28,55..55
    - chain:
        id: B
        binding: 10..16
```

This targets residues on both chain A and chain B of a multi-chain complex.

---

## 13. Scaffold Templates

Pre-built scaffold YAMLs for antibody framework selection. Located at:
`$BOLTZGEN_DIR/example/  # from BoltzGen repo`

### Available Fab Scaffolds (14)

| Scaffold | PDB | File |
|----------|-----|------|
| Adalimumab | 6cr1 | `fab_scaffolds/adalimumab.6cr1.yaml` |
| Belimumab | 7m3n | `fab_scaffolds/belimumab.7m3n.yaml` |
| Crenezumab | 5vzo | `fab_scaffolds/crenezumab.5vzo.yaml` |
| Dupilumab | 8d96 | `fab_scaffolds/dupilumab.8d96.yaml` |
| Golimumab | 5wuv | `fab_scaffolds/golimumab.5wuv.yaml` |
| Guselkumab | 7unp | `fab_scaffolds/guselkumab.7unp.yaml` |
| mAb1 | 7q0g | `fab_scaffolds/mab1.7q0g.yaml` |
| Necitumumab | 5stx | `fab_scaffolds/necitumumab.5stx.yaml` |
| Nirsevimab | 8hkq | `fab_scaffolds/nirsevimab.8hkq.yaml` |
| Sarilumab | 7moe | `fab_scaffolds/sarilumab.7moe.yaml` |
| Secukinumab | 5yy2 | `fab_scaffolds/secukinumab.5yy2.yaml` |
| Tezepelumab | 6oaj | `fab_scaffolds/tezepelumab.6oaj.yaml` |
| Tralokinumab | 6ux9 | `fab_scaffolds/tralokinumab.6ux9.yaml` |
| Ustekinumab | 3hn3 | `fab_scaffolds/ustekinumab.3hn3.yaml` |

### Available Nanobody Scaffolds (4)

| Scaffold | PDB | File |
|----------|-----|------|
| Caplacizumab | 7eow | `nanobody_scaffolds/caplacizumab.7eow.yaml` |
| Vobarilizumab | 7xl0 | `nanobody_scaffolds/vobarilizumab.7xl0.yaml` |
| Gefurulimab | 8coh | `nanobody_scaffolds/gefurulimab.8coh.yaml` |
| Ozoralizumab | 8z8v | `nanobody_scaffolds/ozoralizumab.8z8v.yaml` |

### Default Behavior

If no scaffold entity is added to the entities YAML, proteus-ab uses its
built-in default scaffolds. Explicit scaffolds are useful when:
- A specific antibody framework is required (e.g., adalimumab for anti-TNF)
- The user requests a humanized template from a known therapeutic
- Nanobody design needs a specific starting framework

### Adding a Scaffold to Entities YAML

```yaml
entities:
- file:
    path: ./target.cif
    include:
    - chain:
        id: A
    binding_types:
    - chain:
        id: A
        binding: 45..52,78..85
- file:
    path: $BOLTZGEN_DIR/example/  # from BoltzGen repofab_scaffolds/adalimumab.6cr1.yaml
```
