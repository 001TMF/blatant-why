# Pipeline Stages — BoltzGen

BoltzGen runs a 6-stage internal pipeline. Each stage transforms the output
of the previous stage. The `--prefilter` flag controls whether stage 3 is active.

```
Stage 1       Stage 2          Stage 3        Stage 4           Stage 5        Stage 6
Design  -->  Inverse Fold -->  Pre-filter -->  Protenix   -->  Analysis  -->  Filtering
(BoltzGen)   (AntiFold)       (optional)      Refold           (metrics)      (ranking)
```

---

## Stage 1: Design (BoltzGen Diffusion)

**Engine:** BoltzGen all-atom diffusion model

**What it does:**
- Generates antibody/nanobody 3D backbone structures conditioned on the target
  and binding residues from the entities YAML
- Uses an all-atom diffusion process to sample diverse backbone conformations
- For `nanobody-anything`: generates single VHH domain backbones
- For `antibody-anything`: generates paired VH/VL Fab backbones

**Inputs:**
- Entities YAML with target structure and binding residues
- Protocol selection (nanobody-anything / antibody-anything)
- Budget (number of diffusion steps — higher = more diversity)
- Optional scaffold template

**Outputs:**
- `num_designs` backbone structure candidates (coordinates only, no sequences)
- Each backbone is a 3D coordinate set for the designed chain(s)

**Timing:** ~1–5 seconds per design depending on budget and protocol.

---

## Stage 2: Inverse Folding (AntiFold)

**Engine:** AntiFold inverse folding model

**What it does:**
- Takes each backbone structure from Stage 1 and predicts an amino acid
  sequence that would fold into that backbone
- Optimizes for designability: the predicted sequence should refold to the
  same structure with high confidence
- Preserves framework residues that are critical for antibody stability

**Inputs:**
- Backbone coordinates from Stage 1
- Scaffold constraints (framework residue identities, if scaffold provided)

**Outputs:**
- Full amino acid sequences for each design
- Per-residue confidence scores for sequence assignment

**Timing:** ~0.5–2 seconds per design.

---

## Stage 3: Pre-filter (Optional)

**Enabled by:** `--prefilter` CLI flag

**What it does:**
- Performs a lightweight scoring pass on the designed sequences + backbones
- Discards designs that are very unlikely to refold correctly
- Saves GPU time by preventing Stage 4 (expensive Protenix refolding) from
  running on low-quality designs

**Filter criteria:**
- Internal designability score below threshold → discard
- Backbone-sequence compatibility check → discard incompatible pairs
- Typically removes 20–50% of designs from the pool

**Inputs:**
- Backbone coordinates + sequences from Stages 1–2

**Outputs:**
- Filtered subset of designs that pass the pre-filter
- Designs that fail are logged but not carried forward

**Timing:** ~0.5 seconds per design.

**When to use:** Recommended for production runs (num_designs ≥ 50). For small
preview runs (≤ 20 designs), skipping the pre-filter is fine — refolding all
designs gives more information about what the model is generating.

---

## Stage 4: Protenix Refolding

**Engine:** Protenix v1 (AF3-class structure prediction, 368M params)

**What it does:**
- Takes each designed sequence and independently predicts its structure in
  complex with the target protein
- This is an independent structure prediction — not constrained by the
  Stage 1 backbone. If the designed sequence truly folds correctly and binds
  the target, the refolded structure should match the designed backbone
- Generates PAE (Predicted Aligned Error) matrices used for ipSAE scoring
- Produces confidence metrics: ipTM, pTM, pLDDT

**Inputs:**
- Designed sequences from Stage 2 (or Stage 3 filtered subset)
- Target protein structure/sequence

**Outputs:**
- Refolded 3D structures (CIF files)
- Confidence metrics: ipTM, pTM, pLDDT per design
- PAE matrices (NPZ files) for ipSAE computation
- CA-RMSD between designed backbone (Stage 1) and refolded structure

**Timing:** ~20–60 seconds per design (GPU-bound). This is the most
expensive stage and the bottleneck of the pipeline.

**Key insight:** A large CA-RMSD between the designed and refolded structure
means the sequence does not fold as intended — the design failed even if
the sequence looks plausible. Low RMSD (< 2.0 A) indicates the design is
self-consistent.

---

## Stage 5: Analysis (Metrics Computation)

**What it does:**
- Computes all structural and interface quality metrics from the Protenix
  refolding output
- Calculates ipSAE (interface Predicted Structural Accuracy Error) from PAE
  matrices — both directional scores (dt_ipsae, td_ipsae) and the minimum
- Computes CA-RMSD between designed and refolded backbone
- Aggregates per-residue pLDDT into chain-level and design-level averages

**Inputs:**
- Refolded structures and confidence data from Stage 4
- Original designed backbones from Stage 1 (for RMSD calculation)

**Outputs:**
- Per-design metrics: iptm, ptm, plddt, design_iptm, ipsae_min, rmsd
- These are written into the final output CSV

**Timing:** ~1–3 seconds per design.

---

## Stage 6: Filtering and Ranking

**What it does:**
- Applies quality filters to remove poor designs
- Ranks remaining designs by ipTM (descending) for the output CSV
- Collects all metrics and sequences into the final output file

**Default filters:**
- Designs with structural pathologies (broken chains, steric clashes) removed
- All remaining designs included in ranked output — user applies their own
  hard filters post-hoc (ipTM > 0.5, pLDDT > 70, RMSD < 3.5 A)

**Inputs:**
- All metrics from Stage 5

**Outputs:**
- `final_ranked_designs/final_designs_metrics_*.csv`
  - Columns: design_id, iptm, ptm, plddt, design_iptm, ipsae_min, rmsd, sequence
  - Sorted by iptm descending
- Individual structure files for each design

**Timing:** Seconds (I/O only).

---

## End-to-End Timing Estimates

| Designs | Pre-filter | Approx. Total Time (1 GPU) |
|---------|-----------|---------------------------|
| 10 | off | 5–15 min |
| 20 | off | 10–25 min |
| 50 | on | 20–50 min |
| 100 | on | 45–120 min |
| 200 | on | 2–4 hours |

Stage 4 (Protenix refolding) dominates total time. Enabling pre-filter on
large runs can reduce total time by 20–50% by eliminating low-quality designs
before the expensive refolding step.

---

## Stage Dependency Graph

```
[1] Design ──────→ [2] Inverse Fold ──→ [3] Pre-filter ──→ [4] Refold ──→ [5] Analysis ──→ [6] Filter
    (backbone)         (sequence)          (optional)         (validate)      (metrics)       (rank)

Inputs flow left to right. Each stage requires the previous stage to complete.
No stages run in parallel — the pipeline is strictly sequential per design,
though multiple designs may be batched within each stage.
```

## What to Monitor

| Stage | Success Indicator | Failure Indicator |
|-------|------------------|-------------------|
| 1 Design | Backbone coordinates generated | CUDA OOM, diffusion NaN |
| 2 Inverse Fold | Sequences assigned | Empty sequences, all-glycine |
| 3 Pre-filter | 50–80% of designs pass | < 20% pass (bad backbones) or 100% pass (filter too loose) |
| 4 Refold | Structures + PAE generated | Timeout, CUDA OOM, missing NPZ |
| 5 Analysis | Metrics CSV populated | Missing columns, NaN values |
| 6 Filter | Final CSV with ranked designs | Empty CSV, zero designs passing |
