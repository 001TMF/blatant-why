---
name: protenix
description: >
  Structure prediction using Protenix v1 (AF3-class, 368M params). Use this skill
  when: (1) Predicting protein or complex structure from sequence, (2) Validating
  designed binders by refolding, (3) Generating confidence metrics (ipTM, pTM, pLDDT),
  (4) Multi-seed ensemble validation, (5) Predicting protein-ligand complexes.

  For design generation, use proteus-prot or proteus-ab instead.
  For scoring existing predictions, use proteus-scoring.
  For full pipeline orchestration, use proteus-design-workflow.
category: tool
tags: [structure-prediction, protenix, fold, validation, confidence]
---

# proteus-fold — Structure Prediction Skill

Protenix v1 is an AF3-class structure prediction model (368M params). This skill
teaches you to run predictions via the CLI using the Write → Bash → Read pattern.

---

## 1. Prerequisites

| Requirement | Value |
|-------------|-------|
| Tool path | `$PROTEUS_FOLD_DIR` |
| Env var | `PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR` |
| GPU | Required (CUDA). bf16 precision by default |
| CLI binary | `protenix` (on PATH when env var is set) |

---

## 2. When to Use

```
User wants to...
|
+-- Predict structure from sequence(s)
|   --> proteus-fold (this skill)
|
+-- Validate a designed binder (refold test)
|   --> proteus-fold with binder + target chains
|
+-- Get confidence metrics (ipTM, pLDDT, pTM)
|   --> proteus-fold, then read confidence JSON
|
+-- Predict protein-ligand complex
|   --> proteus-fold with ligand entity type
|
+-- Design a NEW binder
|   --> NOT this skill. Use proteus-prot or proteus-ab
```

---

## 3. How to Run (Write → Bash → Read)

### Step 1: Write input JSON

Use the `Write` tool to create the input JSON file:

```json
[
  {
    "name": "my_prediction",
    "sequences": [
      {"proteinChain": {"sequence": "MKWVTFISLL...", "count": 1}},
      {"proteinChain": {"sequence": "DIQMTQSPSS...", "count": 1}}
    ],
    "modelSeeds": [42],
    "sampleCount": 1
  }
]
```

Write this to a working directory, e.g. `/tmp/fold_run/input.json`.

### Step 2: Run CLI via Bash

```bash
PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR protenix pred \
  -i /tmp/fold_run/input.json \
  -n protenix_base_default_v1.0.0 \
  --use_default_params true \
  --dtype bf16 \
  -o /tmp/fold_run/output
```

### Step 3: Read output

Use `Glob` to find confidence files:
```
*_summary_confidence_sample_*.json
```

Then `Read` the JSON to extract metrics: `iptm`, `ptm`, `plddt`, `ranking_score`.

Structure files are `*_sample_*.cif` in the same output directory tree.

---

## 4. Models

| Key | Full Model Name | Use Case |
|-----|----------------|----------|
| `base_default` | `protenix_base_default_v1.0.0` | **Recommended.** Production predictions, validation |
| `base_20250630` | `protenix_base_20250630_v1.0.0` | Latest checkpoint. Try if base_default underperforms |
| `mini` | `protenix_mini_default_v0.5.0` | Fast screening. Lower accuracy, 3-5x faster |
| `tiny` | `protenix_tiny_default_v0.5.0` | Debugging and pipeline testing only |
| `mini_esm` | `protenix_mini_esm_v0.5.0` | Mini with ESM embeddings. Better single-chain accuracy |

**Model selection:**
- Default to `base_default` for all real predictions.
- Use `mini` only for rapid iteration / feasibility checks.
- Use `tiny` only for testing the pipeline, never for real predictions.
- Try `base_20250630` when `base_default` gives borderline confidence.

---

## 5. CLI Parameters

| Flag | Value | Required | Notes |
|------|-------|----------|-------|
| `-i` | Path to input JSON | Yes | JSON array format (see Section 7) |
| `-n` | Model name string | Yes | Full name from Models table |
| `--use_default_params` | `true` | Yes | Always set to true |
| `--dtype` | `bf16` | Yes | bf16 precision (GPU required) |
| `-o` | Output directory path | No | Defaults to `./output/` if omitted |

---

## 6. Output Format

### Directory structure
```
output/
  my_prediction/
    seed_42/
      my_prediction_summary_confidence_sample_0.json
      my_prediction_sample_0.cif
```

### Confidence JSON fields

| Field | Type | Description |
|-------|------|-------------|
| `iptm` | float or list[float] | Interface predicted TM-score (0-1). Key metric for complexes |
| `ptm` | float or list[float] | Predicted TM-score (0-1). Overall fold quality |
| `plddt` | float or list[float] | Per-residue confidence average (0-100) |
| `ranking_score` | float or list[float] | Composite ranking score. **Use this to pick best sample** |

**Note:** Metrics may be single-element lists. Always index `[0]` or handle both forms.

### Best sample selection

When running multiple samples (`sampleCount > 1`) or seeds, select the sample with
the highest `ranking_score` across all seed/sample combinations.

### Quality interpretation

| Metric | Minimum | Good | Excellent |
|--------|---------|------|-----------|
| ipTM | > 0.5 | > 0.7 | > 0.85 |
| pLDDT | > 70 | > 80 | > 90 |
| pTM | > 0.5 | > 0.7 | > 0.85 |

---

## 7. Input JSON Specification

The input is a **JSON array** containing one prediction object. See
`references/input-json-spec.md` for the complete specification.

### Quick reference

```json
[
  {
    "name": "prediction_name",
    "sequences": [ ...entity objects... ],
    "modelSeeds": [42],
    "sampleCount": 1
  }
]
```

### Entity types in `sequences` array

| Type | Format |
|------|--------|
| Protein chain | `{"proteinChain": {"sequence": "MKWV...", "count": 1}}` |
| Ligand | `{"ligand": {"smiles": "CCO", "count": 1}}` |

Plain strings in `sequences` are auto-wrapped as `proteinChain` entities.

---

## 8. Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Forgetting `PROTENIX_ROOT_DIR` env var | `protenix` command not found or model loading fails | Always set `PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR` |
| Using model key instead of full name | CLI error: unknown model | Use full name: `protenix_base_default_v1.0.0` |
| Input JSON not wrapped in array | Parse error | Input must be `[{...}]`, not `{...}` |
| Single seed for validation decisions | Overconfident conclusions | Use 3-5 seeds for validation: `[42, 123, 456, 789, 1024]` |
| Using `mini`/`tiny` for production | Poor accuracy, unreliable confidence | Use `base_default` or `base_20250630` |
| Omitting target chain in complex validation | ipTM will be meaningless (no interface) | Include ALL chains in the complex |
| Not checking for list-wrapped metrics | Code crash on `float > 0.5` with a list | Always handle `metric[0]` or check type |
| Using MCP function names | Functions don't exist in CLI context | Use `Write` → `Bash` → `Read` pattern only |

---

## 9. Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| `protenix: command not found` | Missing env var | Set `PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR` |
| CUDA out of memory | Sequence too long or too many samples | Reduce `sampleCount`, use `mini` model, or split chains |
| All confidence scores near zero | Malformed input JSON | Verify JSON structure matches spec exactly |
| ipTM = 0 but pLDDT is reasonable | Single chain predicted (no interface) | Ensure multiple chains are in `sequences` |
| Output directory empty | CLI error during run | Check stderr from Bash for error messages |
| Very slow prediction | Large complex + base model | Expected for >1000 residues. Use `mini` for quick check |

---

## 10. Examples

### Example 1: Single protein structure prediction

```
Step 1 — Write /tmp/fold_run/input.json:
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

Step 2 — Bash:
PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR protenix pred \
  -i /tmp/fold_run/input.json \
  -n protenix_base_default_v1.0.0 \
  --use_default_params true \
  --dtype bf16 \
  -o /tmp/fold_run/output

Step 3 — Read confidence JSON and .cif structure file.
```

### Example 2: Multi-chain complex (binder validation)

Validate a designed binder against its target by predicting the complex:

```
Step 1 — Write /tmp/fold_complex/input.json:
[
  {
    "name": "binder_target_complex",
    "sequences": [
      {"proteinChain": {"sequence": "MKTAYIAKQR...", "count": 1}},
      {"proteinChain": {"sequence": "DIQMTQSPSS...", "count": 1}}
    ],
    "modelSeeds": [42],
    "sampleCount": 3
  }
]

Step 2 — Bash:
PROTENIX_ROOT_DIR=$PROTEUS_FOLD_DIR protenix pred \
  -i /tmp/fold_complex/input.json \
  -n protenix_base_default_v1.0.0 \
  --use_default_params true \
  --dtype bf16 \
  -o /tmp/fold_complex/output

Step 3 — Glob for *_summary_confidence_sample_*.json files.
         Read each, pick sample with highest ranking_score.
         ipTM > 0.7 = confident complex. ipTM < 0.5 = likely not binding.
```

### Example 3: Multi-seed ensemble validation

For critical validation decisions, use multiple seeds to assess prediction stability:

```
Step 1 — Write /tmp/fold_ensemble/input.json:
[
  {
    "name": "ensemble_validation",
    "sequences": [
      {"proteinChain": {"sequence": "MKTAYIAKQR...", "count": 1}},
      {"proteinChain": {"sequence": "EVQLVESGG...", "count": 1}}
    ],
    "modelSeeds": [42, 123, 456, 789, 1024],
    "sampleCount": 1
  }
]

Step 2 — Bash (same CLI command as above).

Step 3 — Read confidence JSON from each seed directory.
         Report: mean ipTM, std ipTM, per-seed breakdown.
         Low variance (std < 0.05) = robust prediction.
         High variance (std > 0.1) = uncertain, interpret with caution.
```

---

## 11. Integration with Other Skills

- **After proteus-fold:** Use `proteus-scoring` for ipSAE from PAE matrices, `proteus-screening` for full liability battery.
- **Before proteus-fold:** Use `proteus-database` to fetch target sequences from PDB/UniProt.
- **Workflow context:** `proteus-design-workflow` orchestrates when to call proteus-fold in the overall pipeline.
