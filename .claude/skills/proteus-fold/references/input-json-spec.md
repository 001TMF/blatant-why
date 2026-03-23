# Protenix Input JSON Specification

Complete reference for the input JSON format used by `protenix pred -i <file>`.

---

## Top-Level Structure

The input file is a **JSON array** containing exactly one prediction object.

```json
[
  {
    "name": "<string>",
    "sequences": [ <entity>, ... ],
    "modelSeeds": [ <int>, ... ],
    "sampleCount": <int>
  }
]
```

**Critical:** The outer container MUST be a JSON array `[...]`, not a bare object `{...}`.

---

## Fields

### `name` (string, required)

Identifier for this prediction. Used in output directory and file naming.
- Use alphanumeric characters and underscores only.
- Example: `"lysozyme_fold"`, `"binder_target_complex"`, `"vhh_revalidation_01"`

### `sequences` (array, required)

Array of entity objects defining what to predict. Each entry represents one
molecular entity (protein chain, ligand, etc.).

### `modelSeeds` (array of int, required)

Random seeds for the diffusion sampling. Each seed produces an independent
prediction in a separate output subdirectory.

| Use Case | Recommended Seeds |
|----------|-------------------|
| Quick single prediction | `[42]` |
| Standard validation | `[42, 123, 456]` |
| Ensemble (high confidence) | `[42, 123, 456, 789, 1024]` |

More seeds = more predictions = longer runtime. Each seed runs the full model.

### `sampleCount` (int, required)

Number of diffusion samples per seed. Each sample is an independent structure
generated from the same seed with different diffusion noise.

| Value | Use Case |
|-------|----------|
| `1` | Standard prediction, validation |
| `3` | Complex prediction where best-of-3 helps |
| `5` | Maximum diversity sampling (slow) |

Total structures generated = `len(modelSeeds) * sampleCount`.

---

## Entity Types

Entities go in the `sequences` array. Each entity is an object with one key
indicating the type.

### proteinChain

Standard protein sequence.

```json
{"proteinChain": {"sequence": "MKWVTFISLL...", "count": 1}}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sequence` | string | Yes | Amino acid sequence (1-letter codes, uppercase) |
| `count` | int | No | Number of copies of this chain (default: 1). Use for homo-oligomers |

**Example — homodimer:**
```json
{"proteinChain": {"sequence": "MKWVTFISLL...", "count": 2}}
```

### ligand

Small molecule ligand.

```json
{"ligand": {"smiles": "CCO", "count": 1}}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `smiles` | string | Yes | SMILES string for the ligand |
| `count` | int | No | Number of copies (default: 1) |

### Plain string shorthand

Plain strings in the `sequences` array are automatically wrapped as `proteinChain`:

```json
"sequences": ["MKWVTFISLL...", "DIQMTQSPSS..."]
```

is equivalent to:

```json
"sequences": [
  {"proteinChain": {"sequence": "MKWVTFISLL...", "count": 1}},
  {"proteinChain": {"sequence": "DIQMTQSPSS...", "count": 1}}
]
```

The explicit dict form is preferred for clarity and when you need `count > 1`.

---

## Multi-Chain Complex Examples

### Two-chain protein complex (e.g., binder + target)

```json
[
  {
    "name": "binder_target_refold",
    "sequences": [
      {"proteinChain": {"sequence": "MKTAYIAKQRQISFVK...", "count": 1}},
      {"proteinChain": {"sequence": "DIQMTQSPSSLSASVG...", "count": 1}}
    ],
    "modelSeeds": [42],
    "sampleCount": 1
  }
]
```

### Antibody Fab + antigen

```json
[
  {
    "name": "fab_antigen_complex",
    "sequences": [
      {"proteinChain": {"sequence": "EVQLVESGGGLVQPGG...", "count": 1}},
      {"proteinChain": {"sequence": "DIQMTQSPSSLSASVG...", "count": 1}},
      {"proteinChain": {"sequence": "MKTAYIAKQRQISFVK...", "count": 1}}
    ],
    "modelSeeds": [42, 123, 456],
    "sampleCount": 1
  }
]
```

Chain order: VH, VL, antigen. Order does not affect prediction but aids output interpretation.

### Homodimer

```json
[
  {
    "name": "homodimer_pred",
    "sequences": [
      {"proteinChain": {"sequence": "MKWVTFISLL...", "count": 2}}
    ],
    "modelSeeds": [42],
    "sampleCount": 1
  }
]
```

### Protein-ligand complex

```json
[
  {
    "name": "protein_ligand",
    "sequences": [
      {"proteinChain": {"sequence": "MKWVTFISLL...", "count": 1}},
      {"ligand": {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "count": 1}}
    ],
    "modelSeeds": [42],
    "sampleCount": 1
  }
]
```

---

## Edge Cases and Notes

### Sequence length limits

- No hard limit in the JSON format, but GPU memory constrains practical length.
- Single chain > 1500 residues may require `mini` model or high-memory GPU.
- Total residues across all chains matters more than per-chain length.

### Special characters in sequences

- Sequences must be uppercase single-letter amino acid codes: `ACDEFGHIKLMNPQRSTVWY`
- Non-standard amino acids are NOT supported in the plain sequence format.
- No spaces, dashes, or newlines in the sequence string.

### Empty sequences array

Invalid. Must contain at least one entity.

### Single chain prediction

Valid and common. ipTM will not be meaningful (no interface), but pTM and pLDDT
will report fold confidence.

### Name collisions

If you run multiple predictions with the same `name`, output directories may
overwrite. Use unique names per prediction.

### modelSeeds values

Any positive integer. Commonly used: `42, 123, 456, 789, 1024`. The specific
values don't matter for quality — they just ensure reproducibility and diversity.
Using the same seed twice produces identical results.

### sampleCount = 0

Invalid. Must be >= 1.
