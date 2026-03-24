# PXDesign YAML Config Specification

Complete reference for the YAML configuration file passed to `pxdesign pipeline -i`.

---

## Top-Level Structure

```yaml
target:
  file: <string>       # REQUIRED - path to target structure
  chains:              # REQUIRED - dict of chain configurations
    <chain_id>: <chain_config>
binder_length: <int>   # REQUIRED - number of residues for designed binder
```

---

## Field Reference

### `target.file` (required, string)

Absolute path to the target structure file. Supported formats: `.cif`, `.pdb`.

```yaml
target:
  file: "/data/targets/IL6R.cif"
```

Always use **absolute paths**. Relative paths may resolve incorrectly depending
on the working directory of the `pxdesign` process.

### `target.chains` (required, dict)

Dictionary mapping chain IDs (single uppercase letters) to their configuration.
Each chain can be configured in two ways:

**Simple form** -- include all residues, no hotspots:

```yaml
chains:
  A: "all"
  B: "all"
```

**Detailed form** -- with optional crop, hotspots, and MSA:

```yaml
chains:
  A:
    crop: ["1-116"]
    hotspots: [40, 50, 55]
    msa: "/data/msas/chain_A"
```

You can mix simple and detailed forms for different chains:

```yaml
chains:
  A:
    hotspots: [40, 50]
  B: "all"
```

### `target.chains.<id>.crop` (optional, list of strings)

Residue ranges to include from this chain. Each element is a `"start-end"`
string using label_seq_id numbering (1-indexed). Only residues within these
ranges are included in the design task.

```yaml
crop: ["1-116"]              # single range
crop: ["1-50", "200-300"]    # multiple ranges (disjoint regions)
```

Use crop ranges when:
- The target is very large and only a specific region is relevant
- You want to reduce GPU memory usage
- The binding site spans a defined structural domain

### `target.chains.<id>.hotspots` (optional, list of integers)

Residue numbers (label_seq_id, 1-indexed) on this chain that PXDesign should
prioritize for binder contacts. These guide the design toward the specified
epitope.

```yaml
hotspots: [40, 50, 55, 99]
```

**Important**: Hotspot values are **integers**, not strings. The chain is
determined by the YAML key, not by a prefix on the residue number.

When the user provides hotspots in `"A40, A50, B10"` notation:
1. Parse the first character as the chain letter
2. Parse the remaining characters as the residue number (integer)
3. Group by chain and place under the appropriate chain key

Example: `["A40", "A50", "A55", "B10"]` becomes:

```yaml
chains:
  A:
    hotspots: [40, 50, 55]
  B:
    hotspots: [10]
```

### `target.chains.<id>.msa` (optional, string)

Path to a directory containing precomputed MSA (Multiple Sequence Alignment)
files for this chain. If provided, PXDesign uses the MSA to improve target
representation.

```yaml
msa: "/data/msas/chain_A"
```

If omitted, PXDesign runs without MSA context for that chain.

### `binder_length` (required, integer)

Number of amino acid residues for the designed binder protein. Typical range:
60-150. Default recommendation: 100.

```yaml
binder_length: 100
```

See the binder length guide in SKILL.md Section 2 for sizing recommendations
based on target size and epitope geometry.

---

## Complete Examples

### Minimal Config

```yaml
target:
  file: "/data/targets/my_target.cif"
  chains:
    A: "all"
binder_length: 100
```

### Multi-Chain Target with Hotspots

```yaml
target:
  file: "/data/targets/receptor_complex.cif"
  chains:
    A:
      hotspots: [40, 50, 55, 99]
    B:
      hotspots: [10, 15]
    C: "all"
binder_length: 80
```

### Large Target with Crop, MSA, and Hotspots

```yaml
target:
  file: "/data/targets/large_protein.cif"
  chains:
    A:
      crop: ["200-350"]
      hotspots: [250, 275, 290, 310]
      msa: "/data/msas/large_protein_A"
binder_length: 120
```

### Two Chains with Mixed Configuration

```yaml
target:
  file: "/data/targets/dimer.cif"
  chains:
    A:
      crop: ["1-200"]
      hotspots: [45, 78, 112]
    B: "all"
binder_length: 90
```

---

## Validation Rules

1. `target.file` must point to an existing `.cif` or `.pdb` file
2. Chain IDs in `target.chains` must exist in the structure file
3. `binder_length` must be a positive integer (recommended: 60-150)
4. Hotspot residue numbers must exist within the chain (and within crop ranges if crop is specified)
5. Crop range format must be `"start-end"` where start <= end
6. MSA directory must exist if specified
