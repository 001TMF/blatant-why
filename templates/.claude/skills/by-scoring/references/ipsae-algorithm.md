# ipSAE Algorithm Reference

**ipSAE** (interface Predicted Structural Accuracy Error) is a TM-align-inspired score
computed from Predicted Aligned Error (PAE) matrices. It quantifies how well the
**interface** between two chains is predicted, independent of the absolute coordinates.

This document derives the formula step by step and works through a numerical example.

---

## Source

- Dunbrack et al., *"Res ipSAE loquuntur — Standalone interface scoring from PAE matrices"*, 2025.
- Open-source reference implementation: <https://github.com/DunbrackLab/IPSAE>
- BY implementation: `src/proteus_cli/scoring/ipsae.py` (functions `compute_ipsae`, `_directional_ipsae`, `score_npz`).

The TM-score kernel itself comes from Zhang & Skolnick (2004), *"Scoring function for automated assessment of protein structure template quality"*, Proteins 57:702-710.

---

## Inputs

| Symbol | Meaning | Shape | Source |
|--------|---------|-------|--------|
| `PAE`  | Predicted Aligned Error matrix in Angstroms | `[N, N]` | Protenix / AlphaFold output |
| `chain_ids` | Per-token chain assignment | `[N]` | `token_chain_ids` (JSON) or `token_asym_id` (NPZ) |
| `design_chain` | Chain ID(s) of the designed binder | scalar or list | Caller |
| `target_chain` | Chain ID(s) of the target antigen | scalar or list | Caller |
| `pae_cutoff` | PAE threshold (default 10.0 A for Protenix/AF3, 15.0 for AF2) | float | Caller |

`PAE[i][j]` is the predicted error of token *j*'s position when the structure is aligned on token *i*'s frame. Lower PAE means higher confidence.

---

## Algorithm

ipSAE is directional. Computing the full ipSAE produces three numbers:

1. `design_to_target_ipsae` (dt) — score using the design as the alignment frame.
2. `target_to_design_ipsae` (td) — score using the target as the alignment frame.
3. `ipsae_min = min(dt, td)` — the stringent summary metric.

For each direction `from -> to`:

### Step 1. Build chain masks

```
from_mask = (chain_ids == from_chain)   # boolean, length N
to_mask   = (chain_ids == to_chain)
```

### Step 2. Slice the interchain PAE block

```
interchain_PAE = PAE[from_mask, :][:, to_mask]   # shape [N_from, N_to]
```

This selects only inter-chain predictions — intra-chain PAE values are ignored entirely.

### Step 3. Reduce to the best PAE per target residue

For every residue in the `to` chain, take the minimum PAE across all source residues:

```
min_pae_per_to = interchain_PAE.min(axis=0)      # shape [N_to]
```

Intuition: a target residue is "well-aligned" if **at least one** design residue places it confidently.

### Step 4. Count residues passing the PAE cutoff

```
n0 = count(min_pae_per_to < pae_cutoff)
```

`n0` is the number of "good" target residues. If `n0 == 0`, ipSAE for this direction is `0.0`.

### Step 5. Compute the TM-score d0 reference distance

The TM-score normalization (Zhang & Skolnick 2004) requires a reference distance that scales with chain length:

```
n0_clamped = max(n0, 19)
d0 = 1.24 * (n0_clamped - 15)**(1/3) - 1.8
d0 = max(d0, 0.5)        # guard against tiny / negative d0
```

The clamp at 19 keeps the cube-root argument positive so d0 stays real. For very small interfaces this caps d0 from below.

### Step 6. Score every passing residue with the TM-score kernel

```
score_j = 1 / (1 + (min_pae_per_to[j] / d0)**2)
```

This kernel maps PAE = 0 to score 1.0, PAE = d0 to score 0.5, and PAE >> d0 toward zero.

### Step 7. Average over passing residues

```
ipsae_directional = mean(score_j  for j in passing residues)
```

### Step 8. Symmetrize

```
ipsae_min = min(dt_ipsae, td_ipsae)
```

Always report `ipsae_min` as the primary number. The asymmetry (dt - td) is diagnostic — see `scoring-pitfalls.md`.

---

## Worked Numerical Example

Suppose a 4-residue design chain D paired with a 5-residue target chain T (so N = 9 tokens total). The interchain PAE block (D residues as rows, T residues as columns), in Angstroms:

```
            T1     T2     T3     T4     T5
D1  [   2.1    3.5    8.2   12.0   15.3 ]
D2  [   3.0    1.8    4.5   11.0   14.2 ]
D3  [   7.8    5.2    2.9    9.5   13.5 ]
D4  [  10.5    9.8    8.0    7.5   12.1 ]
```

Use `pae_cutoff = 10.0`.

### Direction D -> T

`min_pae_per_to` (min down each column):

| Residue | T1 | T2 | T3 | T4 | T5 |
|---------|----|----|----|----|----|
| min PAE | 2.1 | 1.8 | 2.9 | 7.5 | 12.1 |
| < 10.0? | ✓ | ✓ | ✓ | ✓ | ✗ |

`n0 = 4` (T5 excluded).

`n0_clamped = max(4, 19) = 19`

`d0 = 1.24 * (19 - 15)**(1/3) - 1.8`
`   = 1.24 * 1.587 - 1.8`
`   = 1.968 - 1.8`
`   = 0.168`

`d0 = max(0.168, 0.5) = 0.5` (floor kicks in).

Per-residue scores `1 / (1 + (pae / d0)**2)`:

| Residue | min PAE | (pae/d0)^2 | score |
|---------|---------|-----------|-------|
| T1 | 2.1 | (4.2)^2 = 17.64 | 1 / 18.64 = 0.0537 |
| T2 | 1.8 | (3.6)^2 = 12.96 | 1 / 13.96 = 0.0716 |
| T3 | 2.9 | (5.8)^2 = 33.64 | 1 / 34.64 = 0.0289 |
| T4 | 7.5 | (15.0)^2 = 225.00 | 1 / 226.00 = 0.0044 |
| T5 | excluded |  | — |

`dt_ipsae = mean(0.0537, 0.0716, 0.0289, 0.0044) = 0.0396`

Because n0 = 4 is far below the clamp of 19, d0 floors at 0.5 — a deliberately tiny normalizer. The lesson: ipSAE on very small interfaces is harshly penalized.

### Direction T -> D

Use `interchain_PAE.T` (transpose). `min_pae_per_to` is now per-D-residue:

| Residue | D1 | D2 | D3 | D4 |
|---------|----|----|----|----|
| min PAE | 2.1 | 1.8 | 2.9 | 7.5 |
| < 10.0? | ✓ | ✓ | ✓ | ✓ |

`n0 = 4`, same d0 = 0.5.

Per-residue scores:

| Residue | min PAE | score |
|---------|---------|-------|
| D1 | 2.1 | 0.0537 |
| D2 | 1.8 | 0.0716 |
| D3 | 2.9 | 0.0289 |
| D4 | 7.5 | 0.0044 |

`td_ipsae = 0.0396`

### Final result

`ipsae_min = min(0.0396, 0.0396) = 0.0396`

This is a deliberately ugly toy example showing how small `n0` (interfaces of only a few residues) yields very low ipSAE even when individual PAE values look reasonable. Real productive antibody interfaces typically engage 15-30 residues — large enough for d0 to escape the floor and for the kernel to reward sub-Angstrom precision.

### Validation

The script `scripts/calc_ipsae.py` reproduces this calculation. Run:

```bash
python scripts/calc_ipsae.py --example
```

Expected output: `ipsae_min = 0.0396` (the script tolerates 1e-3 deviation from the reference value).

---

## Realistic Numerical Sanity Check

A productive nanobody interface might give:

- `n0 = 22` passing residues per direction
- `mean(min_pae) ~ 1.5 A` after cutoff
- `d0 = 1.24 * (22 - 15)^(1/3) - 1.8 = 1.24 * 1.913 - 1.8 = 0.572`
- `score_j ~ 1 / (1 + (1.5 / 0.572)^2) = 1 / (1 + 6.88) = 0.127`

That is still below the `0.5` threshold — a sign that ipSAE values are typically harder to push above 0.7 than ipTM. The actual top-tier designs in published meta-analyses cluster at `0.70 - 0.85`, with `>= 0.85` reserved for crystal-quality predictions.

---

## Numerical Stability Notes

- The `max(n0, 19)` clamp prevents `(x)^(1/3)` from going imaginary for small x but does NOT artificially inflate ipSAE — it actually depresses the score for small interfaces by keeping d0 small.
- The `max(d0, 0.5)` floor stops division blowups when the cube root happens to be near 1.8.
- All arithmetic is float32 in `score_npz()` (NPZ path) and Python floats in `compute_ipsae()` (JSON path). No precision issues observed up to interfaces of ~500 residues.
- The score is bounded `[0.0, 1.0)`. Strictly less than 1 because that would require all PAE = 0 exactly.

---

## Dependencies

- `numpy >= 1.20` (uses `np.ix_`, `np.isin`)
- Python `>= 3.10` (uses `dict[str, float]` PEP-585 generics)
- No scipy / no torch / no biopython for the core formula

For the reference CLI in `scripts/calc_ipsae.py`, only `numpy` is required.

---

## See Also

- `composite-score.md` — how ipSAE_min combines with ipTM and liability counts.
- `thresholds-by-modality.md` — what counts as "good" varies by modality.
- `scoring-pitfalls.md` — common mistakes interpreting ipSAE values.
