# Skill: proteus-scoring

## Overview

You are an expert at interpreting and applying Proteus custom scoring metrics for protein and antibody design. This skill covers ipSAE (interface Predicted Structural Accuracy Error) -- the primary custom metric that differentiates Proteus from generic structure prediction tools. ipSAE uses the open-source DunbrackLab formula with no proprietary dependencies. Use this skill whenever you need to score designs, interpret scoring output, troubleshoot disagreements between metrics, or advise on candidate ranking.

---

## Explicit Tool Naming

ALWAYS name tools explicitly when discussing workflows:
- "Protenix" for structure prediction/refolding (not "the structure predictor")
- "BoltzGen" for design generation (not "the design tool")
- "PXDesign" for de novo binder design (not "the binder generator")
- "Tamarind Bio" for cloud compute (not "the cloud service")
- "ipSAE" by name (not "the scoring metric")
- "ipTM" by name (not "the confidence score")

When explaining pipeline stages, always say which tool does each step:
- "BoltzGen generates backbone structures" (not "designs are generated")
- "Protenix refolding validates the designs" (not "structures are validated")
- "ipSAE scores rank the candidates" (not "candidates are scored")

---

## ipSAE Scoring

### What It Is

ipSAE is a **TM-align-inspired metric** computed from Protenix PAE (Predicted Aligned Error) matrices. It measures the structural accuracy of the **interface** between a designed binder and its target, using the same mathematical framework as TM-score but applied to predicted error matrices rather than superimposed coordinates.

Unlike ipTM (which captures global inter-chain confidence), ipSAE focuses specifically on how well the interface geometry is predicted. It is directional: the score changes depending on which chain is used as the reference frame.

Reference: Dunbrack et al., "Res ipSAE loquuntur" (2025). Open-source implementation: https://github.com/DunbrackLab/IPSAE

### Directional Scores

ipSAE produces three values for every design:

| Metric | Direction | Meaning |
|--------|-----------|---------|
| `design_to_target_ipsae` (dt_ipsae) | Design as source, target as reference | How confidently the design's interface residues are placed relative to the target |
| `target_to_design_ipsae` (td_ipsae) | Target as source, design as reference | How confidently the target's interface residues are placed relative to the design |
| `ipsae_min` | min(dt, td) | Most stringent assessment -- both directions must be confident |

Always report `ipsae_min` as the primary ranking metric. Report the directional scores when diagnosing asymmetric interfaces or when one direction is significantly stronger than the other.

### Algorithm (Step by Step)

When you need to explain ipSAE computation or debug scoring issues, this is the exact procedure:

1. **Extract PAE matrix** from Protenix output. Shape is `[N_sample, N_token, N_token]`. Each entry PAE[i][j] is the predicted error in Angstroms of token j's position when aligned on token i's predicted frame. Lower PAE = higher confidence.

2. **Build chain masks** from `token_asym_id` or `token_chain_ids`. Construct boolean masks:
   - `design_mask`: True for all tokens belonging to design chain(s)
   - `target_mask`: True for all tokens belonging to target chain(s)

3. **Extract interchain PAE block** and compute minimum PAE per target residue across all source residues.

4. **Apply PAE cutoff at 10.0 Angstroms** (for Protenix/AF3; 15.0 for AF2). Residues with min PAE above the cutoff are excluded from the score. This removes noise from high-error predictions.

5. **Compute the TM-align d0 reference distance**. For n0 residues passing the cutoff:
   ```
   d0 = 1.24 * (clamp(n0, min=19) - 15) ^ (1/3) - 1.8
   d0 = max(d0, 0.5)  # prevent division issues
   ```
   The `clamp(n0, 19)` ensures d0 is always positive. d0 normalizes the score so it is comparable across targets of different sizes.

6. **Score each residue using TM-score kernel**:
   ```
   score = 1.0 / (1.0 + (min_pae / d0)^2)
   ```
   This is the TM-score kernel applied to predicted error instead of actual distance deviation. Residues with low PAE contribute scores near 1.0; residues with PAE approaching d0 contribute ~0.5.

7. **Aggregate**: Average the scores over all residues that passed the PAE cutoff.

8. **Iterate across samples**: When Protenix generates multiple samples (seeds), compute ipSAE for each sample independently and select the sample where `ipsae_min` is highest.

### Implementation Files

- **Standalone implementation**: `compute_ipsae()` and `_directional_ipsae()` in `src/proteus_cli/scoring/ipsae.py`
- **NPZ scorer**: `score_npz()` in `src/proteus_cli/scoring/ipsae.py`
- **JSON scorer**: `score_from_protenix_output()` in `src/proteus_cli/scoring/ipsae.py`
- **Multi-seed scorer**: `score_multi_seed()` and `score_multi_seed_dir()` in `src/proteus_cli/scoring/ipsae.py`
- **Interpretation**: `interpret_ipsae()` in `src/proteus_cli/scoring/ipsae.py`

No external dependencies required beyond numpy. No BoltzGen dependency.

### How to Score via MCP

Use the `score_ipsae` tool from the `proteus-screening` MCP server:
```
Tool: score_ipsae
Args: { "npz_path": "/path/to/protenix_output.npz", "design_chain_ids": [0], "target_chain_ids": [1] }
```

For antibody designs (Fab), typical chain IDs are `[0, 1]` for VH+VL (design) and `[2]` for antigen (target). For nanobody/VHH designs, it is `[0]` for VHH (design) and `[1]` for antigen (target). Always confirm the chain ordering from the Protenix input JSON -- antibody chains come first, antigen last.

### Interpretation Table

| ipSAE Range | Interpretation | Action |
|-------------|---------------|--------|
| >= 0.8 | **Excellent** -- strong predicted binding interface | Advance to experimental validation |
| 0.6 - 0.8 | **Good** -- likely binder | Advance if other metrics agree |
| 0.4 - 0.6 | **Moderate** -- possible binder, interface partially resolved | Consider redesign or additional sampling |
| 0.2 - 0.4 | **Weak** -- unlikely to bind | Reject or redesign from scratch |
| < 0.2 | **Poor** -- no predicted binding | Reject |

### When ipSAE Disagrees with ipTM

This happens regularly. The two metrics measure different things:

| Scenario | ipTM | ipSAE | Trust | Explanation |
|----------|------|-------|-------|-------------|
| Global confidence but weak interface | High (>0.8) | Low (<0.3) | **ipSAE** | ipTM captures global chain placement but the interface contacts are not well-predicted. The chains may be in roughly the right orientation but the binding details are uncertain. |
| Strong interface but poor global packing | Low (<0.5) | High (>0.7) | **ipSAE** | Unusual but can occur when the binder has flexible regions far from the interface that reduce global ipTM. The interface itself is well-defined. |
| Both high | High | High | **Both** | Ideal case. Strong confidence in both global and interface-level prediction. |
| Both low | Low | Low | **Both** | Poor design. Neither global nor interface confidence is adequate. |

**General rule**: When they disagree, trust ipSAE for binding assessment. ipSAE is specifically designed to capture interface quality, while ipTM is a more general inter-chain metric that can be inflated by non-interface contacts (e.g., chains that are near each other but not forming productive binding interactions).

### Asymmetric ipSAE (dt vs td)

When `design_to_target_ipsae` and `target_to_design_ipsae` diverge significantly (>0.15 difference):

- **dt >> td**: The design's placement relative to the target is confident, but the target's placement relative to the design is not. This often means the design is well-folded and positioned near the target, but the target's epitope residues have high uncertainty. May indicate an intrinsically disordered epitope region.

- **td >> dt**: The target anchors the design well, but the design itself has structural uncertainty at the interface. Common with flexible loop-mediated binding (e.g., long CDR-H3 loops). Consider constraining the design.

Always report `ipsae_min` (the minimum of both directions) as the primary metric -- it requires BOTH directions to be confident.


## Combined Scoring Strategy

### Recommended Ranking Formula

Rank designs using a two-metric composite with liability penalty:

**Tier 1 -- Hard Filters (must pass all):**
- ipTM > 0.5
- pLDDT > 70 (mean over design chain atoms)
- CA-RMSD < 3.5 Angstroms (between designed and refolded structure)

**Tier 2 -- Soft Ranking (weighted composite):**
```
composite_score = 0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)
```

ipSAE has been validated as the best single predictor of binding success in meta-analysis (n=3,766 binders).

**Tier 3 -- Diversity Selection:**
After ranking by composite score, select diverse candidates by clustering on CDR-H3 sequence (for antibodies) or interface residue identity (for protein binders). Pick the top candidate from each cluster.

### Failure Modes and What They Indicate

| ipTM | ipSAE | Diagnosis | Action |
|------|-------|-----------|--------|
| High | High | Ideal candidate | Advance to experiment |
| High | Low | Global placement confident but interface uncertain | Increase sampling (more seeds); may need interface-focused redesign |
| Low | High | Strong interface, poor global fold | Check for flexible tails/loops pulling down ipTM; may still be viable |
| Low | Low | Poor design across all metrics | Reject and redesign |

### Recommended Scoring Workflow

Follow this sequence for every batch of new designs:

1. **Run Protenix refolding** on all designs to generate structure predictions and PAE matrices.

2. **Extract ipTM and pLDDT** from Protenix `summary_confidence`. Apply hard filters (ipTM > 0.5, pLDDT > 70). Report how many designs pass.

3. **Compute ipSAE** from PAE matrices for all designs passing hard filters. Report directional scores and flag any with large dt/td asymmetry (>0.15 difference).

4. **Run liability screening** (deamidation, isomerization, oxidation, free Cys, glycosylation) on all candidate sequences. Count high-severity liabilities.

5. **Compute composite score** and rank. Present results as a table:
   ```
   Rank  Design       ipSAE   ipTM   pLDDT  RMSD   Liabilities  Composite
   1     design-008   0.82    0.87   88.3   1.2A   0 high       0.86
   2     design-015   0.78    0.84   85.1   1.5A   1 medium     0.82
   3     design-003   0.71    0.81   82.7   1.8A   0 high       0.77
   ```

6. **Provide interpretation** for the top candidates, noting any disagreements between metrics and recommending next steps (e.g., visualize structure, run developability, approve for experiment).


## Multi-Seed Refolding

### Rationale

BoltzGen's built-in ipSAE (computed from its own diffusion model's confidence) is useful for initial ranking, but **Protenix refolding with multiple seeds** produces more reliable structure predictions. The two-phase workflow is:

1. BoltzGen generates N designs with initial ipSAE ranking
2. Top `budget` designs are selected
3. Each top design is refolded on Protenix with 20+ seeds
4. `score_ipsae_multi_seed` scores every seed and selects the best
5. Final ranking uses Protenix-validated ipSAE

### Minimum Seeds by Modality

| Modality | Min Seeds | Rationale |
|----------|-----------|-----------|
| VHH (nanobody) | 20 | CDR loops are flexible; need statistical coverage |
| scFv | 20 | Two variable domains + linker increase conformational space |
| De novo protein | 10 | Simpler fold topology, fewer stochastic modes |

### Implementation

Two new functions in `src/proteus_cli/scoring/ipsae.py`:

- **`score_multi_seed(npz_paths, ...)`**: Scores a list of NPZ/JSON files (one per seed), selects best seed by aggregation strategy ("best" / "mean" / "median"), returns best seed index, per-seed scores, and mean/std statistics.
- **`score_multi_seed_dir(npz_dir, ...)`**: Convenience wrapper that discovers all `*.npz` and `*confidence*.json` files in a directory.

### MCP Tool

Use `score_ipsae_multi_seed` from the `proteus-screening` MCP server:
```
Tool: score_ipsae_multi_seed
Args: { "npz_dir": "/path/to/protenix_seeds/", "design_chain_ids": [0], "target_chain_ids": [1] }
```

Or with explicit file list:
```
Tool: score_ipsae_multi_seed
Args: { "npz_paths": ["seed_0.npz", "seed_1.npz", ...], "design_chain_ids": [0], "target_chain_ids": [1] }
```

Returns: `best_seed_idx`, `best_ipsae_min`, `mean_ipsae_min`, `std_ipsae_min`, per-seed breakdown, and interpretation.

### Aggregation Strategies

| Strategy | Selects | When to Use |
|----------|---------|-------------|
| `"best"` (default) | Seed with highest `ipsae_min` | Standard workflow -- pick the most confident prediction |
| `"mean"` | Seed closest to mean `ipsae_min` | When you want a representative (not optimistic) score |
| `"median"` | Seed closest to median `ipsae_min` | Robust to outlier seeds |

### Interpreting Multi-Seed Results

- **High std_ipsae_min (>0.15)**: Prediction is unstable across seeds. The design may have conformational flexibility at the interface. Consider with caution even if best seed looks good.
- **Low std_ipsae_min (<0.05)**: Prediction is robust. The best seed score is reliable.
- **best_ipsae_min >> mean_ipsae_min**: One seed found a much better conformation. Check if this is a genuine alternative binding mode or a lucky sample.

### Key Conventions

- **Chain ordering**: Antibody chains (VH first, VL second if present) before antigen (last). This ordering is essential for correct ipSAE chain mask building.
- **Residue numbering**: Use `label_seq_id` (1-indexed, sequential) for all residue references.
- **Score precision**: Report ipTM and ipSAE to 2 decimal places. Report RMSD to 1 decimal place with Angstrom unit.
- **Sample selection**: When Protenix generates multiple samples per design, select the sample with the highest `ipsae_min`. Report which sample index was selected.
- **Missing metrics**: Always indicate when a metric is unavailable. Never substitute zeros or placeholders that could be confused with real scores. Use `--` in tables for unavailable values.
