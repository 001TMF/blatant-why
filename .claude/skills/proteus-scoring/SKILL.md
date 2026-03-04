# Skill: proteus-scoring

## Overview

You are an expert at interpreting and applying Proteus custom scoring metrics for protein and antibody design. This skill covers ipSAE (interface Predicted Structural Accuracy Error) and p_bind (binding probability prediction) -- the two custom metrics that differentiate Proteus from generic structure prediction tools. Use this skill whenever you need to score designs, interpret scoring output, troubleshoot disagreements between metrics, or advise on candidate ranking.

---

## ipSAE Scoring

### What It Is

ipSAE is a **TM-align-inspired metric** computed from Protenix PAE (Predicted Aligned Error) matrices. It measures the structural accuracy of the **interface** between a designed binder and its target, using the same mathematical framework as TM-score but applied to predicted error matrices rather than superimposed coordinates.

Unlike ipTM (which captures global inter-chain confidence), ipSAE focuses specifically on how well the interface geometry is predicted. It is directional: the score changes depending on which chain is used as the reference frame.

### Directional Scores

ipSAE produces three values for every design:

| Metric | Direction | Meaning |
|--------|-----------|---------|
| `design_to_target_ipsae` (dt_ipsae) | Design as source, target as reference | How confidently the design's interface residues are placed relative to the target |
| `target_to_design_ipsae` (td_ipsae) | Target as source, design as reference | How confidently the target's interface residues are placed relative to the design |
| `design_ipsae_min` | min(dt, td) | Most stringent assessment -- both directions must be confident |

Always report `design_ipsae_min` as the primary ranking metric. Report the directional scores when diagnosing asymmetric interfaces or when one direction is significantly stronger than the other.

### Algorithm (Step by Step)

When you need to explain ipSAE computation or debug scoring issues, this is the exact procedure:

1. **Extract PAE matrix** from Protenix output. Shape is `[N_sample, N_token, N_token]`. Each entry PAE[i][j] is the predicted error in Angstroms of token j's position when aligned on token i's predicted frame. Lower PAE = higher confidence.

2. **Build chain masks** from `token_asym_id`. Protenix assigns integer asym_ids (0, 1, 2, ...) to chains in entity order. Construct boolean masks:
   - `design_mask`: True for all tokens belonging to design chain(s)
   - `target_mask`: True for all tokens belonging to target chain(s)
   - `frame_mask`: True for all tokens with valid backbone frames (`token_has_frame`)
   - `pad_mask`: True for all real (non-padding) tokens

3. **Apply PAE cutoff at 15.0 Angstroms**. Pairs with PAE above 15.0A are excluded from the score. This removes noise from high-error predictions.

4. **Compute the TM-align d0 reference distance**. For a target of length n0 residues:
   ```
   d0 = 1.24 * (clamp(n0, min=19) - 15) ^ (1/3) - 1.8
   ```
   The `clamp(n0, 19)` ensures d0 is always positive. d0 normalizes the score so it is comparable across targets of different sizes.

5. **Score each valid pair**:
   ```
   pair_score = 1.0 / (1.0 + (pae / d0)^2)
   ```
   This is the TM-score kernel applied to predicted error instead of actual distance deviation. Pairs with low PAE contribute scores near 1.0; pairs with PAE approaching d0 contribute ~0.5.

6. **Aggregate**: For each source residue, average the pair scores over all valid target residues. Then take the **maximum** across all source residues. This makes ipSAE robust to partial interfaces where only a subset of residues are confidently placed.

7. **Iterate across samples**: When Protenix generates multiple samples (seeds), compute ipSAE for each sample independently and select the sample where `min(dt, td)` is highest.

### Implementation Files

- **Core function**: `compute_ipsae_score()` in BoltzGen at `deps/BoltzGen/src/boltzgen/model/layers/confidence_utils.py`
- **Protenix wrapper**: `compute_ipsae_from_protenix()` in `/data/proteus/proteus-design/src/proteus_ab/pipeline/scoring.py`
- **CLI wrapper**: `score_npz()` in `src/proteus_cli/scoring/ipsae.py`
- **Interpretation**: `interpret_ipsae()` in `src/proteus_cli/scoring/ipsae.py`

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
| > 0.8 | **Excellent** -- high confidence interface, strong predicted binding geometry | Advance to experimental validation |
| 0.5 - 0.8 | **Good** -- likely binder, confident interface | Advance if other metrics agree |
| 0.3 - 0.5 | **Moderate** -- possible binder, interface partially resolved | Consider redesign or additional sampling |
| < 0.3 | **Poor** -- unlikely to bind, interface poorly predicted | Reject or redesign from scratch |

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

Always report `design_ipsae_min` (the minimum of both directions) as the primary metric -- it requires BOTH directions to be confident.

---

## p_bind Scoring

### What It Is

p_bind is a **learned binding probability predictor** -- a small MLP that takes Protenix trunk representations as input and outputs a probability (0 to 1) that the antibody-antigen complex actually binds. It provides an orthogonal signal to structure-based metrics like ipTM and ipSAE.

### Architecture

```
Input: v_ab(384) + v_ag(384) + v_if(256) = 1024 dimensions
  |
  v
Linear(1024, 512) + ReLU + Dropout(0.2)
  |
Linear(512, 256) + ReLU + Dropout(0.2)
  |
Linear(256, 128) + ReLU + Dropout(0.2)
  |
Linear(128, 1) + Sigmoid
  |
  v
Output: binding probability [0, 1]
```

The three input feature vectors are:
- **v_ab (384-dim)**: Antibody single-representation summary, pooled from Protenix's pairformer `s_trunk` output over all antibody chain tokens
- **v_ag (384-dim)**: Antigen single-representation summary, pooled over antigen chain tokens
- **v_if (256-dim)**: Interface pair-representation summary, pooled from `z_trunk` over design-target token pairs

These features are extracted by `extract_pbind_features()` in BoltzGen's `binding_utils.py`. The extraction uses `chain_design_mask` to determine which tokens are antibody vs antigen.

### CRITICAL: chain_design_mask Must Use Full VH/VL Chains

This is the single most important implementation detail for p_bind accuracy:

- **v1 (CDR-only mask)**: `chain_design_mask` covered only CDR loop residues. Result: **ROC AUC = 0.60** (barely above random).
- **v2 (full chain mask)**: `chain_design_mask` covers the ENTIRE VH and VL chains, including framework residues. Result: **ROC AUC = 0.906**.

The fix is in `build_chain_design_mask()` at `/data/proteus/proteus-design/src/proteus_ab/pbind/trunk.py`. The logic is simple: all chains except the last one (antigen) are marked as design (antibody). This ensures framework residues contribute to v_ab and v_if representations.

**If you see anyone using CDR-only masks for p_bind feature extraction, flag it immediately.** The performance difference is catastrophic.

### Feature Extraction Pipeline

p_bind features come from a **trunk-only forward pass** through Protenix. The pipeline:

1. Build Protenix JSON input from sequences (chain order: VH first, then VL if present, then antigen last)
2. Run `get_pairformer_output()` to get `s_trunk [1, N, 384]` and `z_trunk [1, N, N, 128]`
3. Build `chain_design_mask` from `asym_id` using `build_chain_design_mask()` (full chains, NOT CDR-only)
4. Call `extract_pbind_features(s_trunk, z_trunk, design_mask, chain_design_mask, token_pad_mask)`
5. Concatenate `[v_ab, v_ag, v_if]` into 1024-dim input vector
6. Pass through trained MLP to get binding probability

This is a **trunk-only** pass -- no diffusion, no coordinate generation, no confidence heads. It is significantly faster than full Protenix inference (~2s per sample vs ~30s).

### When to Use p_bind

- **After proteus-ab designs are refolded** by Protenix. The trunk features come from the refolding prediction, which gives a more accurate representation than the design-stage backbone alone.
- **Before final candidate selection**, as an additional discriminator alongside ipTM and ipSAE.
- **NOT as a standalone metric**. p_bind should always be used in combination with structure-based metrics. A design with high p_bind but low ipTM/ipSAE may have a sequence that looks binding-like but folds incorrectly.

### Implementation Files

- **MLP model**: `PBindHead` in BoltzGen at `deps/BoltzGen/src/boltzgen/pbind/model.py`
- **Feature extraction**: `extract_pbind_features()` in `deps/BoltzGen/src/boltzgen/model/layers/binding_utils.py`
- **Chain mask construction**: `build_chain_design_mask()` in `/data/proteus/proteus-design/src/proteus_ab/pbind/trunk.py`
- **Trunk forward pass**: `get_trunk_output()` in `/data/proteus/proteus-design/src/proteus_ab/pbind/trunk.py`
- **CLI wrapper**: `predict_binding()` and `load_pbind_model()` in `src/proteus_cli/scoring/pbind.py`
- **Training configs**: `/data/proteus/proteus-design/src/proteus_ab/pbind/train_config.py`
- **Featurization**: `/data/proteus/proteus-design/src/proteus_ab/pbind/featurize.py`

### How to Score via MCP

Use the `score_pbind` tool from the `proteus-screening` MCP server:
```
Tool: score_pbind
Args: { "checkpoint_path": "/path/to/pbind_checkpoint.pt", "npz_path": "/path/to/refolded_output.npz" }
```

### Interpretation Table

| p_bind | Interpretation | Action |
|--------|---------------|--------|
| > 0.8 | **High confidence binder** | Strong candidate for experimental validation |
| 0.5 - 0.8 | **Likely binder** | Include in shortlist, verify with structural metrics |
| 0.3 - 0.5 | **Marginal** -- borderline binding signal | Consider redesign; only advance if ipTM and ipSAE are strong |
| < 0.3 | **Unlikely to bind** | Reject unless structural metrics are exceptional |

### Current Status

p_bind code is **complete** but the model is **awaiting GPU featurization and training**. The 5 training configurations are defined in `train_config.py`:

| Config Name | Loss Function | Optimizer |
|-------------|--------------|-----------|
| `mlp_sam` | Weighted BCE (default) | SAM (rho=0.05) |
| `adaptive_focal_sam` | Adaptive focal loss | SAM (rho=0.05) |
| `poly1_sam` | Poly-1 loss | SAM (rho=0.05) |
| `focal_gamma1` | Focal loss (gamma=1.0) | Standard AdamW |
| `focal_mega` | Focal loss (gamma=2.0) | Standard AdamW |

All configs use hidden_dims=[512, 256, 128], dropout=0.2, batch_size=512, max_epochs=100, patience=15.

**When p_bind is not yet available**: Report it as unavailable with a warning. Do NOT fabricate p_bind scores. Instead, rely on ipTM + ipSAE for ranking, and note in the results that p_bind scoring will be available once the model is trained.

---

## Combined Scoring Strategy

### Recommended Ranking Formula

When all three metrics are available, rank designs using this composite approach:

**Tier 1 -- Hard Filters (must pass all):**
- ipTM > 0.5
- pLDDT > 70 (mean over design chain atoms)
- CA-RMSD < 3.5 Angstroms (between designed and refolded structure)

**Tier 2 -- Soft Ranking (weighted composite):**
```
composite_score = 0.35 * ipSAE_min + 0.30 * p_bind + 0.20 * ipTM + 0.15 * (1 - normalized_liability_count)
```

When p_bind is unavailable, re-weight:
```
composite_score = 0.45 * ipSAE_min + 0.35 * ipTM + 0.20 * (1 - normalized_liability_count)
```

**Tier 3 -- Diversity Selection:**
After ranking by composite score, select diverse candidates by clustering on CDR-H3 sequence (for antibodies) or interface residue identity (for protein binders). Pick the top candidate from each cluster.

### Failure Modes and What They Indicate

| ipTM | ipSAE | p_bind | Diagnosis | Action |
|------|-------|--------|-----------|--------|
| High | High | High | Ideal candidate | Advance to experiment |
| High | High | Low | Structure looks good but learned model disagrees | Verify interface contacts manually; may have unusual binding mode |
| High | Low | High | Global placement confident but interface uncertain | Increase sampling (more seeds); may need interface-focused redesign |
| High | Low | Low | Likely false positive from ipTM | Reject -- ipTM inflated by non-interface chain proximity |
| Low | High | High | Strong interface, poor global fold | Check for flexible tails/loops pulling down ipTM; may still be viable |
| Low | High | Low | Conflicting signals | Increase sampling; investigate structural details manually |
| Low | Low | High | Learned model sees binding signal in sequence features | Suspicious -- verify sequence is not trivially similar to training data |
| Low | Low | Low | Poor design across all metrics | Reject and redesign |

### Recommended Scoring Workflow

Follow this sequence for every batch of new designs:

1. **Run Protenix refolding** on all designs to generate structure predictions and PAE matrices.

2. **Extract ipTM and pLDDT** from Protenix `summary_confidence`. Apply hard filters (ipTM > 0.5, pLDDT > 70). Report how many designs pass.

3. **Compute ipSAE** from PAE matrices for all designs passing hard filters. Report directional scores and flag any with large dt/td asymmetry (>0.15 difference).

4. **Compute p_bind** (when checkpoint is available) using trunk features from the refolding run. Flag any designs where p_bind and ipSAE strongly disagree.

5. **Run liability screening** (deamidation, isomerization, oxidation, free Cys, glycosylation) on all candidate sequences. Count high-severity liabilities.

6. **Compute composite score** and rank. Present results as a table:
   ```
   Rank  Design       ipTM   ipSAE   p_bind  RMSD   Liabilities  Composite
   1     design-008   0.87   0.82    0.91    1.2A   0 high       0.86
   2     design-015   0.84   0.78    0.88    1.5A   1 medium     0.82
   3     design-003   0.81   0.71    --      1.8A   0 high       0.77
   ```

7. **Provide interpretation** for the top candidates, noting any disagreements between metrics and recommending next steps (e.g., visualize structure, run developability, approve for experiment).

### Key Conventions

- **Chain ordering**: Antibody chains (VH first, VL second if present) before antigen (last). This ordering is essential for correct `chain_design_mask` construction and ipSAE chain mask building.
- **Residue numbering**: Use `label_seq_id` (1-indexed, sequential) for all residue references.
- **Score precision**: Report ipTM and ipSAE to 2 decimal places. Report p_bind to 2 decimal places. Report RMSD to 1 decimal place with Angstrom unit.
- **Sample selection**: When Protenix generates multiple samples per design, select the sample with the highest `design_ipsae_min`. Report which sample index was selected.
- **Missing metrics**: Always indicate when a metric is unavailable (p_bind before training, ipSAE without PAE matrix). Never substitute zeros or placeholders that could be confused with real scores. Use `--` in tables for unavailable values.
