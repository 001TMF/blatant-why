# Entities YAML Specification — proteus-ab

Full specification for the entities YAML file consumed by `proteus-ab run`.
This file defines the target protein, binding residues (epitope), and optional
scaffold templates.

---

## Top-Level Structure

```yaml
entities:
- file:
    path: <target_structure_path>
    include:
    - chain:
        id: <chain_letter>
    binding_types:
    - chain:
        id: <chain_letter>
        binding: <range_notation>
- file:
    path: <scaffold_yaml_path>    # optional
```

The `entities` list contains one or more `file:` blocks. The first entity is
always the target. Additional entities are scaffold templates.

---

## Target Entity

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Path to target structure (CIF or PDB). Relative to spec file location or absolute |
| `include` | list | Chains to include from the structure |
| `include[].chain.id` | string | Single-letter chain identifier (e.g., `A`, `B`) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `binding_types` | list | Epitope specification — which residues to target |
| `binding_types[].chain.id` | string | Chain containing the epitope |
| `binding_types[].chain.binding` | string | Residue ranges in `..` notation |

---

## Include Blocks

Each `include` entry specifies a chain to use from the structure file.

### Single Chain

```yaml
include:
- chain:
    id: A
```

### Multiple Chains (multi-chain target)

```yaml
include:
- chain:
    id: A
- chain:
    id: B
```

All listed chains will be present in the design context. The binder will be
designed to interact with the specified binding residues across these chains.

---

## Binding Types (Epitope Specification)

The `binding_types` block defines which residues the designed binder should
target. Each entry specifies a chain and a set of residues in range notation.

### Single-Chain Epitope

```yaml
binding_types:
- chain:
    id: A
    binding: 45..52,78..85
```

### Multi-Chain Epitope

When the epitope spans multiple chains:

```yaml
binding_types:
- chain:
    id: A
    binding: 22..28,55..55
- chain:
    id: B
    binding: 10..16
```

### No Epitope Specified

If `binding_types` is omitted entirely, the tool will attempt to design a
binder without epitope guidance. This is not recommended — designs will be
less focused and success rates lower.

---

## Range Notation

Binding residues use `..` range notation to compactly represent contiguous
stretches of residues. Ranges are comma-separated.

### Format

```
<start>..<end>[,<start>..<end>]*
```

### Rules

1. All residue numbers are **`label_seq_id`**: 1-indexed, sequential, per-chain, no gaps
2. Contiguous residues are collapsed: `[7,8,9,10]` → `7..10`
3. Singletons use same start and end: `[15]` → `15..15`
4. Multiple ranges separated by commas, no spaces: `7..12,27..34`

### Conversion Examples

| Input Residue List | Range Notation |
|-------------------|---------------|
| `[7, 8, 9, 10, 11, 12]` | `7..12` |
| `[7, 8, 9, 10, 11, 12, 27, 28, 29, 30, 31, 32, 33, 34]` | `7..12,27..34` |
| `[5]` | `5..5` |
| `[5, 10, 15]` | `5..5,10..10,15..15` |
| `[1, 2, 3, 20, 21, 22, 50]` | `1..3,20..22,50..50` |
| `[100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 140, 141, 142]` | `100..110,140..142` |

### From Residue Lists

When specifying binding residues, map chain IDs to integer lists which are then
converted to range notation:

```python
binding_residues = {"A": [7, 8, 9, 10, 11, 12, 27, 28, 29, 30, 31, 32, 33, 34]}
```

This is converted internally to range notation `7..12,27..34` in the YAML.

---

## Scaffold Entity (Optional)

Scaffold templates provide a starting antibody/nanobody framework for the
design. If omitted, the tool uses its built-in default scaffolds.

### Built-In Scaffold Locations

Scaffold YAML files are in the BoltzGen examples directory:
```
$BOLTZGEN_DIR/example/  # from BoltzGen repo: fab_scaffolds/
```

### Adding a Scaffold

```yaml
- file:
    path: $BOLTZGEN_DIR/example/  # from BoltzGen repo: fab_scaffolds/adalimumab.6cr1.yaml
```

Scaffold entities have no `include` or `binding_types` — just the `path`.

### When to Use Scaffolds

| Scenario | Scaffold Recommendation |
|----------|----------------------|
| Default design run | Omit scaffold entity (uses built-in defaults) |
| Specific antibody framework needed | Point to scaffold YAML matching desired framework |
| Humanized template required | Use a scaffold from a known humanized antibody |
| Nanobody design | Most nanobody runs work well without explicit scaffold |

---

## Complete Examples

### Minimal: Single-Chain Target, No Scaffold

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
```

### With Scaffold Template

```yaml
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
    path: $BOLTZGEN_DIR/example/  # from BoltzGen repo: fab_scaffolds/adalimumab.6cr1.yaml
```

### Multi-Chain Target, Multi-Region Epitope

```yaml
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

### Target Only, No Epitope Guidance (Not Recommended)

```yaml
entities:
- file:
    path: ./target.cif
    include:
    - chain:
        id: A
```

---

## Common Mistakes

| Mistake | Effect | Fix |
|---------|--------|-----|
| Using `auth_seq_id` numbers | Wrong residues targeted | Convert to `label_seq_id` first |
| Spaces in range notation (`7..12, 27..34`) | Parse error | No spaces: `7..12,27..34` |
| Missing `include` block | No chains loaded | Always list target chains |
| Relative scaffold path from wrong directory | File not found | Use absolute paths for scaffolds |
| Binding residues on buried residues | Designs can't reach epitope | Verify SASA > 0.25 for all epitope residues |
| Chain ID mismatch between `include` and `binding_types` | Binding residues ignored | Ensure chain IDs match exactly |
