---
id: "skill_c170f6b9f5464c23b9969f7ca78fa96b"
name: "by-scoring"
display-name: "BY Scoring"
short-description: "Interpret and apply BY scoring metrics — ipSAE, ipTM, pLDDT, RMSD, liability counts, and the composite ranking formula. Use when scoring designs, interpreting screening output, troubleshooting metric disagreements, or advising on candidate ranking."
category: "scoring"
keywords: "ipSAE, ipTM, pLDDT, composite score, scoring, ranking, PAE, Protenix, BoltzGen, antibody, nanobody, design"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: ["mcp__by-screening__score_ipsae", "mcp__by-screening__score_ipsae_multi_seed", "mcp__by-screening__compute_composite", "mcp__by-screening__screen_liabilities"]
---

# BY Scoring Skill

Interpret and apply BY custom scoring metrics for protein and antibody design. This
skill covers ipSAE (interface Predicted Structural Accuracy Error) — the primary
custom metric that differentiates BY from generic structure prediction tools — along
with ipTM, pLDDT, RMSD, liability scoring, and the BY composite ranking formula.

ipSAE uses the open-source DunbrackLab formula (Dunbrack et al. 2025) with no
proprietary dependencies. Use this skill whenever you need to score designs,
interpret scoring output, troubleshoot disagreements between metrics, or advise on
candidate ranking.

---

## When to Use This Skill

**Use this skill when:**

- ✅ Scoring designs after Protenix refolding — you have NPZ or confidence JSON output
- ✅ Computing the BY composite score on a panel of screened designs
- ✅ Explaining why two metrics (ipSAE vs ipTM) disagree on a candidate
- ✅ Setting modality-specific thresholds (antibody vs nanobody vs de novo)
- ✅ Diagnosing why an entire panel failed screening (zero LAB-READY)
- ✅ Auditing whether a multi-seed result is stable or driven by one lucky seed
- ✅ Interpreting asymmetric ipSAE (`dt >> td` or `td >> dt`)
- ✅ Selecting the right PAE cutoff (10 A Protenix/AF3 vs 15 A AF2)

**Don't use this skill for:**

- ❌ Generating designs — use the **by-design-workflow** skill instead
- ❌ Running liability or developability screening directly — use the **by-screening** skill
- ❌ Choosing which target to design against — use the **by-research** skill
- ❌ Submitting candidates to a lab — use the **by-lab** agent (triple-gated)
- ❌ Predicting raw structures — use the **protenix** skill

---

## Quick Start

Compute ipSAE for a single Protenix output:

```bash
# JSON confidence file (Protenix /summary_confidence.json)
python scripts/calc_ipsae.py \
    --pae confidence.json \
    --chains confidence.json \
    --design A --target B \
    --pae-cutoff 10.0

# Or run the worked numerical example from references/
python scripts/calc_ipsae.py --example
# Expected: ipsae_min = 0.0396
```

Rank a panel by composite score:

```bash
python scripts/composite_score.py \
    --input scored.csv \
    --output ranked.csv \
    --modality nanobody

# Expected verification:
# ✓ Composite scoring completed: 95 rows -> ranked.csv
#   LAB-READY=10  FOLLOW-UP=18  BORDERLINE=32  NOT-VIABLE=20  FILTER-FAIL=15
```

Visualize score distributions:

```bash
python scripts/plot_score_distributions.py \
    --input ranked.csv \
    --output distributions.pdf \
    --modality nanobody
```

Via MCP (preferred inside the agent loop):

```
Tool: mcp__by-screening__score_ipsae
Args: { "npz_path": "/path/to/protenix.npz",
        "design_chain_ids": [0],
        "target_chain_ids": [1] }
```

---

## Explicit Tool Naming

ALWAYS name tools explicitly when discussing workflows:
- "Protenix" for structure prediction/refolding (not "the structure predictor")
- "BoltzGen" for antibody/nanobody design generation (not "the design tool")
- "PXDesign" for de novo binder design (not "the binder generator")
- "ipSAE" by name (not "the scoring metric") — capital S-A-E
- "ipTM" by name (not "the confidence score")

When explaining pipeline stages, always say which tool does each step:
- "BoltzGen generates backbone structures" (not "designs are generated")
- "Protenix refolding validates the designs" (not "structures are validated")
- "ipSAE scores rank the candidates" (not "candidates are scored")

---

## Inputs

**Required for scoring a single design:**

- **Protenix NPZ output** (`*.npz`) with `pae` key of shape `[N_sample, N_token, N_token]` and `token_asym_id` key of shape `[N_token]`.
- **OR Protenix confidence JSON** with `pae` (or `predicted_aligned_error`) and `token_chain_ids` keys, plus optional `iptm`, `ptm`, `plddt`.
- **Design chain ID(s)** — integer asym_ids (NPZ) or chain letters (JSON). Convention: antibody/VHH first, antigen last.
- **Target chain ID(s)** — same format as design chains.

**Required for composite ranking:**

- **Scored CSV** with columns: `design_id`, `ipsae_min`, `iptm`. Optional: `liability_count`, `plddt_mean`, `ca_rmsd`, `scaffold`.

**Required for multi-seed scoring:**

- **Directory of Protenix outputs** — one NPZ or confidence JSON per seed. Minimum 20 seeds for VHH/scFv, 10 for de novo.

**Optional:**

- `--pae-cutoff`: 10.0 (default, Protenix/AF3) or 15.0 (AF2).
- `--modality`: `antibody`, `nanobody`, `vhh`, `denovo`, `bispecific`, `peptide`. Switches hard-filter thresholds. See [references/thresholds-by-modality.md](references/thresholds-by-modality.md).
- `--weight-ipsae` / `--weight-iptm` / `--weight-liability`: override default composite weights `(0.50, 0.30, 0.20)`. Weights must sum to 1.0. See [references/composite-score.md](references/composite-score.md).

---

## Outputs

**Primary results (per design):**

- `design_to_target_ipsae` (dt_ipsae) — directional ipSAE, design as source frame, in `[0.0, 1.0)`.
- `target_to_design_ipsae` (td_ipsae) — directional ipSAE, target as source frame.
- `ipsae_min` — `min(dt, td)`, the primary ranking metric.
- `iptm` — global inter-chain confidence from Protenix.
- `plddt_mean` — mean pLDDT over the **design chain only** (never over both chains).
- `ca_rmsd` — CA-RMSD between predicted and refolded design (Angstroms).

**Composite ranking outputs:**

- `composite_score` — weighted blend in `[0.0, 1.0]`. Written as `--` for designs failing any hard filter.
- `rank` — integer rank by composite score among passing designs.
- `verdict` — `LAB-READY` / `FOLLOW-UP` / `BORDERLINE` / `NOT-VIABLE` / `FILTER-FAIL`.

**Multi-seed outputs:**

- `best_seed_idx` — index of the best-scoring seed.
- `best_ipsae_min`, `mean_ipsae_min`, `std_ipsae_min` — statistics over all seeds.
- `all_ipsae_min` — list of per-seed scores. Flag `std > 0.15` as conformationally unstable.

**Visualizations:**

- `distributions.pdf` — multi-panel histograms (ipSAE_min, ipTM, composite, optional pLDDT) with verdict-band threshold lines, 300 DPI.

**Score precision conventions:**

- ipTM and ipSAE: 2 decimal places in tables, 4 internally.
- RMSD: 1 decimal place with `A` (Angstrom) unit.
- Composite: 3 decimal places in summaries.
- Missing metrics: `--` in tables. NEVER substitute zeros.

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST.** Always confirm the user has scoring inputs before running anything.

1. **Input Files** (ASK THIS FIRST):
   - Do you have Protenix output already? If yes, NPZ file(s) or confidence JSON?
   - Or is the input a CSV that already has `ipsae_min`/`iptm` columns (e.g., from a previous screening run)?
   - If neither: you likely need the **by-screening** skill or the **protenix** skill first.

2. **Modality**:
   - Is this an antibody (Fab/scFv), nanobody (VHH), de novo binder, bispecific, or cyclic peptide?
   - Determines hard-filter thresholds and ipSAE excellence bands. See [references/thresholds-by-modality.md](references/thresholds-by-modality.md).

3. **Chain Ordering**:
   - Which chain ID(s) belong to the design vs the target?
   - Convention: antibody/VHH first (chains 0 or 0+1), antigen last. Confirm from the Protenix input JSON before scoring.

4. **PAE Cutoff Source**:
   - Was the prediction run with Protenix/AF3 (use 10.0) or AF2 (use 15.0)?
   - Using the wrong cutoff inflates ipSAE by ~0.05-0.10. See [references/scoring-pitfalls.md](references/scoring-pitfalls.md) §4.

5. **Single Seed vs Multi-Seed**:
   - How many Protenix seeds were run per design?
   - For VHH/scFv, single-seed scoring is unreliable. Recommend re-running with >= 20 seeds if seed count is low.

6. **Composite Weights**:
   - Use defaults `(0.50, 0.30, 0.20)`, or override for the panel context (lab-bound vs exploratory)?
   - See [references/composite-score.md](references/composite-score.md) for override scenarios.

7. **Downstream Use**:
   - Lab submission? -> Strict thresholds, multi-seed required, liability scan mandatory.
   - Internal triage? -> Defaults are fine, can skip multi-seed for first pass.
   - Diversity panel selection? -> Use the **by-diversity** agent after composite ranking.

---

## ipSAE Scoring

### What It Is

ipSAE is a **TM-align-inspired metric** computed from Protenix PAE (Predicted Aligned
Error) matrices. It measures the structural accuracy of the **interface** between a
designed binder and its target, using the same mathematical framework as TM-score but
applied to predicted error matrices rather than superimposed coordinates.

Unlike ipTM (which captures global inter-chain confidence), ipSAE focuses specifically
on how well the interface geometry is predicted. It is directional: the score changes
depending on which chain is used as the reference frame.

Reference: Dunbrack et al., "Res ipSAE loquuntur" (2025).
Open-source implementation: <https://github.com/DunbrackLab/IPSAE>

For the full formula derivation, step-by-step algorithm, and a worked numerical
example, see [references/ipsae-algorithm.md](references/ipsae-algorithm.md).

### Directional Scores

ipSAE produces three values for every design:

| Metric | Direction | Meaning |
|--------|-----------|---------|
| `design_to_target_ipsae` (dt_ipsae) | Design as source, target as reference | How confidently the design's interface residues are placed relative to the target |
| `target_to_design_ipsae` (td_ipsae) | Target as source, design as reference | How confidently the target's interface residues are placed relative to the design |
| `ipsae_min` | `min(dt, td)` | Most stringent assessment — both directions must be confident |

Always report `ipsae_min` as the primary ranking metric. Report the directional scores
when diagnosing asymmetric interfaces or when one direction is significantly stronger
than the other.

### Algorithm Summary

The full algorithm is documented in [references/ipsae-algorithm.md](references/ipsae-algorithm.md).
The key steps:

1. Extract PAE matrix and build chain masks.
2. Slice the interchain PAE block (intra-chain entries ignored).
3. Reduce to minimum PAE per target residue across source residues.
4. Apply PAE cutoff (10.0 A for Protenix/AF3, 15.0 for AF2) to count `n0` passing residues.
5. Compute TM-score `d0 = 1.24 * (max(n0, 19) - 15)^(1/3) - 1.8`, floored at 0.5.
6. Score each passing residue: `score_j = 1 / (1 + (min_pae_j / d0)^2)`.
7. Average over passing residues to get the directional score.
8. Symmetrize: `ipsae_min = min(dt, td)`.

Reproduce the worked example with `python scripts/calc_ipsae.py --example`.

### Implementation Files

Reference Python implementation lives in `src/proteus_cli/scoring/ipsae.py`:

- `compute_ipsae()` and `_directional_ipsae()` — core formula (JSON / chain-letter API).
- `score_npz()` — Protenix NPZ scorer (asym_id API).
- `score_from_protenix_output()` — confidence JSON scorer.
- `score_multi_seed()` and `score_multi_seed_dir()` — multi-seed aggregation.
- `interpret_ipsae()` — human-readable verdict for a single score.

No external dependencies beyond numpy. No BoltzGen dependency.

### How to Score via MCP

Use the `mcp__by-screening__score_ipsae` tool from the `by-screening` MCP server:

```
Tool: mcp__by-screening__score_ipsae
Args: { "npz_path": "/path/to/protenix_output.npz",
        "design_chain_ids": [0],
        "target_chain_ids": [1] }
```

For antibody designs (Fab), typical chain IDs are `[0, 1]` for VH+VL (design) and `[2]`
for antigen (target). For nanobody/VHH designs, it is `[0]` for VHH (design) and `[1]`
for antigen (target). Always confirm the chain ordering from the Protenix input JSON —
antibody chains come first, antigen last.

### Interpretation Table

| ipSAE Range | Interpretation | Action |
|-------------|---------------|--------|
| `>= 0.8` | **Excellent** — strong predicted binding interface | Advance to experimental validation |
| `0.6 - 0.8` | **Good** — likely binder | Advance if other metrics agree |
| `0.4 - 0.6` | **Moderate** — possible binder, interface partially resolved | Consider redesign or additional sampling |
| `0.2 - 0.4` | **Weak** — unlikely to bind | Reject or redesign from scratch |
| `< 0.2` | **Poor** — no predicted binding | Reject |

These are the universal defaults from `plugin-manifest.json`. For modality-specific
overrides, see [references/thresholds-by-modality.md](references/thresholds-by-modality.md).

### When ipSAE Disagrees with ipTM

This happens regularly. The two metrics measure different things:

| Scenario | ipTM | ipSAE | Trust | Explanation |
|----------|------|-------|-------|-------------|
| Global confidence but weak interface | High (>0.8) | Low (<0.3) | **ipSAE** | ipTM captures global chain placement but the interface contacts are not well-predicted. The chains may be in roughly the right orientation but the binding details are uncertain. |
| Strong interface but poor global packing | Low (<0.5) | High (>0.7) | **ipSAE** | Unusual but can occur when the binder has flexible regions far from the interface that reduce global ipTM. The interface itself is well-defined. |
| Both high | High | High | **Both** | Ideal case. Strong confidence in both global and interface-level prediction. |
| Both low | Low | Low | **Both** | Poor design. Neither global nor interface confidence is adequate. |

**General rule**: When they disagree, trust ipSAE for binding assessment. ipSAE is
specifically designed to capture interface quality, while ipTM is a more general
inter-chain metric that can be inflated by non-interface contacts.

### Asymmetric ipSAE (dt vs td)

When `design_to_target_ipsae` and `target_to_design_ipsae` diverge significantly (>0.15 difference):

- **dt >> td**: The design's placement relative to the target is confident, but the target's placement relative to the design is not. This often means the design is well-folded and positioned near the target, but the target's epitope residues have high uncertainty. May indicate an intrinsically disordered epitope region.

- **td >> dt**: The target anchors the design well, but the design itself has structural uncertainty at the interface. Common with flexible loop-mediated binding (e.g., long CDR-H3 loops). Consider constraining the design.

Always report `ipsae_min` (the minimum of both directions) as the primary metric — it
requires BOTH directions to be confident.

---

## Combined Scoring Strategy

### Recommended Ranking Formula

Rank designs using a two-metric composite with liability penalty:

**Tier 1 — Hard Filters (must pass all):**
- `ipTM > 0.5`
- `pLDDT > 70` (mean over design chain atoms — never over both chains)
- `CA-RMSD < 3.5 A` (between designed and refolded structure)

Modality-specific overrides (e.g., pLDDT > 75 for de novo binders) are documented in
[references/thresholds-by-modality.md](references/thresholds-by-modality.md).

**Tier 2 — Soft Ranking (weighted composite):**

```
composite_score = 0.50 * ipSAE_min
                + 0.30 * ipTM
                + 0.20 * (1 - normalized_liability_count)
```

where `normalized_liability_count = min(high_severity_count / 5, 1.0)`.

ipSAE has been validated as the best single predictor of binding success in
meta-analysis (n=3,766 binders). For the full weight rationale and override scenarios,
see [references/composite-score.md](references/composite-score.md).

**Tier 3 — Diversity Selection:**

After ranking by composite score, select diverse candidates by clustering on CDR-H3
sequence (for antibodies) or interface residue identity (for protein binders). Pick
the top candidate from each cluster. Use the **by-diversity** agent.

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

4. **Run liability screening** (deamidation, isomerization, oxidation, free Cys, glycosylation) on all candidate sequences. Count HIGH severity liabilities.

5. **Compute composite score** with `scripts/composite_score.py` and rank. Present results as a table:

   ```
   Rank  Design       ipSAE   ipTM   pLDDT  RMSD   Liabilities  Composite
   1     design-008   0.82    0.87   88.3   1.2A   0 high       0.871
   2     design-015   0.78    0.84   85.1   1.5A   1 high       0.802
   3     design-003   0.71    0.81   82.7   1.8A   0 high       0.798
   ```

6. **Provide interpretation** for the top candidates, noting any disagreements between metrics and recommending next steps (visualize structure, run developability, approve for experiment).

---

## Calibrated Interpretation

### ipSAE Interpretation Guide

| ipSAE Range | Confidence | Biological Context | Recommendation |
|-------------|------------|-------------------|----------------|
| 0.85-1.0 | **Exceptional** | Comparable to co-crystal structures of approved therapeutics (e.g., pembrolizumab-PD1). | Lab-ready. Prioritize for experimental validation. |
| 0.70-0.85 | **Strong** | Comparable to successful computational designs in published literature (17-82% hit rates). | Strong candidate. Recommend for first-round lab testing. |
| 0.50-0.70 | **Moderate** | Predicted binding mode is plausible but interface confidence has gaps. | Consider for diverse panel; may benefit from follow-up design round. |
| 0.30-0.50 | **Weak** | Interface prediction is uncertain — binding mode may not reflect reality. | Do not send to lab. Redesign with different hotspots or scaffold. |
| Below 0.30 | **Poor** | Essentially random interface placement. | Discard. Investigate target suitability for this modality. |

### ipTM Interpretation Guide

| ipTM Range | Confidence | Context |
|------------|------------|---------|
| Above 0.85 | **High** | Strong predicted interaction; complex geometry is reliable. |
| 0.70-0.85 | **Good** | Reasonable confidence; consistent with successful designs. |
| 0.50-0.70 | **Marginal** | May bind but prediction reliability is lower. |
| Below 0.50 | **Low** | Complex prediction unreliable; do not trust placement. |

### Composite Score Interpretation

| Composite Range | Verdict | Action |
|-----------------|---------|--------|
| Above 0.75 | **LAB-READY** | Submit for experimental validation. |
| 0.60-0.75 | **FOLLOW-UP** | Include in testing panel. |
| 0.45-0.60 | **BORDERLINE** | Include only for diversity; do not prioritize. |
| Below 0.45 | **NOT-VIABLE** | Do not advance. Redesign or discard. |

### Score Bar Display Format

When presenting individual metric scores, use the score bar format:

```
{metric}  {value}  {bar}  {label}
```

Where `{bar}` is 10 Unicode blocks filled proportionally to the value:
- `█` (U+2588, FULL BLOCK) for filled portion
- `░` (U+2591, LIGHT SHADE) for empty portion

Each `█` represents 10%. Round to nearest whole block. Examples:

| Value | Bar | Label |
|-------|-----|-------|
| 0.85 | `████████░░` | EXCELLENT |
| 0.72 | `███████░░░` | STRONG |
| 0.50 | `█████░░░░░` | MODERATE |
| 0.30 | `███░░░░░░░` | WEAK |
| 91.2 (pLDDT) | `█████████░` | VERY HIGH |

**Label mapping for ipSAE:**
- `>= 0.85`: EXCEPTIONAL
- `0.70-0.85`: STRONG
- `0.50-0.70`: MODERATE
- `0.30-0.50`: WEAK
- `< 0.30`: POOR

**Label mapping for ipTM:**
- `>= 0.85`: HIGH
- `0.70-0.85`: GOOD
- `0.50-0.70`: MARGINAL
- `< 0.50`: LOW

**Label mapping for pLDDT (0-100 scale, divide by 100 for bar):**
- `>= 90`: VERY HIGH
- `70-90`: GOOD
- `50-70`: LOW
- `< 50`: VERY LOW

**Full example (Score Context block after results table):**

```markdown
## Score Context
ipSAE  0.85  ████████░░  EXCELLENT  (top 5% of approved therapeutics)
ipTM   0.82  ████████░░  STRONG     (confident interface prediction)
pLDDT  91.2  █████████░  VERY HIGH  (reliable fold prediction)
```

Always include the Score Context block with score bars after any ranked results table
or individual design screening report.

### Presenting Results — Required Elements

When presenting a ranked results table, ALWAYS include these three elements after the table:

1. **Score context sentence** for the top candidate. Example: "The top candidate has ipSAE 0.87 — exceptional confidence, comparable to approved therapeutics (e.g., pembrolizumab-PD1 co-crystal structures)."

2. **Actionable categorization** grouping candidates into tiers:
   - **Lab-ready** (N designs): ipSAE above 0.70 — strong confidence, recommend for experimental validation.
   - **Worth testing** (M designs): ipSAE 0.50-0.70 — moderate confidence, include in diverse panel.
   - **Redesign needed** (K designs): ipSAE below 0.50 — insufficient confidence, do not advance.

3. **Numbered next steps** based on result quality:
   - If lab-ready candidates exist: suggest submitting top candidates to Adaptyv Bio and running Protenix ensemble validation (20+ seeds) on the top 3-5.
   - If no lab-ready candidates but worth-testing candidates exist: suggest increasing compute budget, trying alternative scaffolds, or refining epitope selection.
   - If all candidates need redesign: suggest re-examining the epitope, switching modality, or investigating target tractability.

### Zero-Candidate Failure Diagnosis

When zero designs pass screening, do NOT show an empty table. Instead provide:

1. **Failure summary**: "0 of N designs passed screening. This suggests [diagnosis]."

2. **Diagnosis** (check in order):
   - All ipSAE below 0.3: epitope may be too flat, flexible, or heavily glycosylated for productive binding.
   - All pLDDT below 70: designs are not folding stably — structural quality is the bottleneck.
   - Good scores but all fail liabilities: manufacturing issues (deamidation, glycosylation, free Cys) — consider liability engineering.
   - Mixed failure modes: target may be genuinely difficult; multiple issues compound.

3. **Specific remedies** (always provide 2-3 concrete actions):
   - Try a different epitope region (identify alternative binding sites from structure analysis).
   - Switch scaffold (e.g., from caplacizumab to ozoralizumab for more CDR diversity).
   - Increase compute budget to explore more backbone conformations.
   - Switch modality (e.g., from VHH to de novo binder if epitope is concave).
   - Run fold validation on the target to confirm the epitope is structurally stable.

---

## Multi-Seed Refolding

### Rationale

BoltzGen's built-in ipSAE (computed from its own diffusion model's confidence) is
useful for initial ranking, but **Protenix refolding with multiple seeds** produces
more reliable structure predictions. The two-phase workflow is:

1. BoltzGen generates N designs with initial ipSAE ranking.
2. Top `budget` designs are selected.
3. Each top design is refolded on Protenix with 20+ seeds.
4. `score_ipsae_multi_seed` scores every seed and selects the best.
5. Final ranking uses Protenix-validated ipSAE.

### Minimum Seeds by Modality

| Modality | Min Seeds | Rationale |
|----------|-----------|-----------|
| VHH (nanobody) | 20 | CDR loops are flexible; need statistical coverage |
| scFv / Fab | 20 | Two variable domains + linker increase conformational space |
| De novo binder | 10 | Simpler fold topology, fewer stochastic modes |
| Bispecific | 30 | Two paratopes; doubled conformational space |

### Implementation

Two functions in `src/proteus_cli/scoring/ipsae.py`:

- **`score_multi_seed(npz_paths, ...)`**: Scores a list of NPZ/JSON files (one per seed), selects best seed by aggregation strategy (`best` / `mean` / `median`), returns best seed index, per-seed scores, and mean/std statistics.
- **`score_multi_seed_dir(npz_dir, ...)`**: Convenience wrapper that discovers all `*.npz` and `*confidence*.json` files in a directory.

### MCP Tool

Use `mcp__by-screening__score_ipsae_multi_seed`:

```
Tool: mcp__by-screening__score_ipsae_multi_seed
Args: { "npz_dir": "/path/to/protenix_seeds/",
        "design_chain_ids": [0],
        "target_chain_ids": [1] }
```

Or with explicit file list:

```
Tool: mcp__by-screening__score_ipsae_multi_seed
Args: { "npz_paths": ["seed_0.npz", "seed_1.npz", ...],
        "design_chain_ids": [0],
        "target_chain_ids": [1] }
```

Returns: `best_seed_idx`, `best_ipsae_min`, `mean_ipsae_min`, `std_ipsae_min`,
per-seed breakdown, and interpretation.

### Aggregation Strategies

| Strategy | Selects | When to Use |
|----------|---------|-------------|
| `"best"` (default) | Seed with highest `ipsae_min` | Standard workflow — pick the most confident prediction |
| `"mean"` | Seed closest to mean `ipsae_min` | When you want a representative (not optimistic) score |
| `"median"` | Seed closest to median `ipsae_min` | Robust to outlier seeds |

### Interpreting Multi-Seed Results

- **High `std_ipsae_min` (>0.15)**: Prediction is unstable across seeds. The design may have conformational flexibility at the interface. Consider with caution even if best seed looks good.
- **Low `std_ipsae_min` (<0.05)**: Prediction is robust. The best seed score is reliable.
- **`best_ipsae_min >> mean_ipsae_min`**: One seed found a much better conformation. Check if this is a genuine alternative binding mode or a lucky sample.

For full discussion of these patterns, see [references/scoring-pitfalls.md](references/scoring-pitfalls.md) §11.

---

## Standard Workflow

🚨 **MANDATORY: USE SCRIPTS EXACTLY AS SHOWN — DO NOT WRITE INLINE CODE** 🚨

This skill ships three scripts. Use them as-is for repeatable scoring.

### Step 1. Per-design ipSAE (if not already in CSV)

```bash
python scripts/calc_ipsae.py \
    --pae /path/to/confidence.json \
    --chains /path/to/confidence.json \
    --design A --target B \
    --pae-cutoff 10.0 \
    --output /path/to/ipsae_result.json
```

✅ **VERIFICATION**: `✓ ipSAE computed: /path/to/ipsae_result.json (ipsae_min=0.78)`

### Step 2. Composite ranking

```bash
python scripts/composite_score.py \
    --input /path/to/scored.csv \
    --output /path/to/ranked.csv \
    --modality nanobody
```

✅ **VERIFICATION**: `✓ Composite scoring completed: N rows -> ranked.csv` followed by verdict counts.

### Step 3. Distribution plot

```bash
python scripts/plot_score_distributions.py \
    --input /path/to/ranked.csv \
    --output /path/to/distributions.pdf \
    --modality nanobody
```

✅ **VERIFICATION**: `✓ Distribution plot written: /path/to/distributions.pdf (N designs, M LAB-READY)`

### Anti-patterns

⚠️ **CRITICAL — DO NOT:**

- ❌ Write inline ipSAE math — STOP: Use `calc_ipsae.py` or `mcp__by-screening__score_ipsae`.
- ❌ Use absolute paths like `/mnt/...` in scripts — they take I/O via CLI args.
- ❌ Substitute zero for missing metrics — use `--` in tables.
- ❌ Skip hard filters and rank everything by composite — filter first, then rank.
- ❌ Report `pTM` and call it `ipTM` — they are different metrics; see [scoring-pitfalls.md](references/scoring-pitfalls.md) §1.

---

## When Scripts Fail

Use this hierarchy when a script errors:

1. **Fix and Retry (90%)** — Install missing package (`pip install numpy pandas matplotlib`), re-run.
2. **Modify Script (5%)** — Edit the script file itself if your input format differs (e.g., different CSV column names).
3. **Use as Reference (4%)** — Read the script, adapt the formula in a one-off Python session.
4. **Write from Scratch (1%)** — Only if impossible; explain why in writing.

Decision tree:

- Missing numpy/pandas/matplotlib? -> **Step 1**, install per the script's error message.
- CSV missing `liability_count` column? -> **Step 2**, script will warn and treat as 0; or add the column upstream.
- Need a different aggregation than best/mean/median? -> **Step 3**, adapt `score_multi_seed()` in a notebook.
- Cannot use scipy/matplotlib for licensing reasons? -> **Step 4**, document and use raw numpy.

---

## Decision Points

### PAE Cutoff Selection

| Source | Cutoff | When |
|--------|--------|------|
| Protenix | 10.0 A | Default for all Protenix outputs |
| AlphaFold3 | 10.0 A | Same as Protenix |
| AlphaFold2 | 15.0 A | Legacy AF2 only |

See [references/scoring-pitfalls.md](references/scoring-pitfalls.md) §4 for the cost of getting this wrong.

### Composite Weight Selection

Default `(0.50, 0.30, 0.20)` is calibrated for antibody/nanobody screening with
balanced binding + manufacturability concerns. Override when:

- Pure binding-mode exploration -> `(0.60, 0.40, 0.00)`
- Manufacturability-first panel -> `(0.40, 0.20, 0.40)`
- De novo binder panel -> `(0.55, 0.35, 0.10)`
- High target difficulty (sparse field) -> `(0.70, 0.25, 0.05)`
- Bispecific / multi-paratope -> `(0.45, 0.40, 0.15)`

Full rationale in [references/composite-score.md](references/composite-score.md).

### Modality Threshold Selection

See [references/thresholds-by-modality.md](references/thresholds-by-modality.md) for
the full table. Quick reference:

- Antibody / Fab: ipSAE excellent `>= 0.75`
- Nanobody / VHH: ipSAE excellent `>= 0.70`
- De novo binder: ipSAE excellent `>= 0.85`

---

## Common Issues

| Issue | Possible Cause | Solution | Details |
|-------|----------------|----------|---------|
| Composite scores all `--` | All designs failed hard filters | Inspect `filter_failures` column; relax modality or redesign | [composite-score.md](references/composite-score.md) |
| ipSAE much lower than BoltzGen's native score | Wrong `pae_cutoff` (15 vs 10) or off-by-one chain mask | Use 10.0 for Protenix/AF3; confirm chain ordering | [scoring-pitfalls.md](references/scoring-pitfalls.md) §4, §12 |
| `dt_ipsae` and `td_ipsae` differ by >0.15 | Asymmetric interface — disordered epitope or flexible CDR | Report both directions; still use `ipsae_min` for ranking | SKILL.md "Asymmetric ipSAE" section |
| `ipTM` very high but `ipsae_min` very low | Chains placed near each other but interface contacts uncertain | Trust ipSAE; do not ship | [scoring-pitfalls.md](references/scoring-pitfalls.md) §7 |
| Single-seed scoring of VHH gives unstable rankings | Insufficient sampling for flexible CDR-H3 | Re-run with >= 20 seeds | [scoring-pitfalls.md](references/scoring-pitfalls.md) §2 |
| `std_ipsae_min` > 0.15 across seeds | Conformationally unstable interface | Downgrade verdict one band or run 40+ seeds | [scoring-pitfalls.md](references/scoring-pitfalls.md) §11 |
| pLDDT mean passes filter but design chain looks bad | Mean computed over both chains, target dominates | Restrict mean to design chain only | [scoring-pitfalls.md](references/scoring-pitfalls.md) §14 |
| `mcp__by-screening__score_ipsae` returns `error: No PAE matrix` | Confidence JSON missing `pae` key | Use Protenix `summary_confidence.json`, not the run config | `scoring/ipsae.py` `score_from_protenix_output` |
| Tiny interface (n0 < 15) gives ipSAE near 0 | TM-score d0 clamped to floor (0.5) | Note interface size; rely on visual inspection + ipTM | [scoring-pitfalls.md](references/scoring-pitfalls.md) §3 |
| Mixed-modality panel ranked unfairly (de novo always wins) | Raw ipSAE_min has different baselines per modality | Rank within modality or z-score normalize | [scoring-pitfalls.md](references/scoring-pitfalls.md) §10 |
| All liabilities counted, not just HIGH severity | Filter not applied before normalization | Filter to HIGH before counting; default cap = 5 HIGH | [scoring-pitfalls.md](references/scoring-pitfalls.md) §9 |
| BoltzGen ipSAE accepted as final score | Skipped Protenix refolding step | Always refold on Protenix; BoltzGen ipSAE is for early ranking | [scoring-pitfalls.md](references/scoring-pitfalls.md) §8 |
| Composite formula weights do not sum to 1.0 | User-supplied weights not normalized | `composite_score.py` asserts sum=1.0 (tol 1e-6); fix weights | [composite-score.md](references/composite-score.md) |

---

## Best Practices

1. 🚨 **CRITICAL**: Use scripts (`calc_ipsae.py`, `composite_score.py`, `plot_score_distributions.py`) — do not write inline scoring code.
2. ✅ **REQUIRED**: Always report `ipsae_min` as the primary ranking metric; report dt/td only when asymmetry > 0.15.
3. ✅ **REQUIRED**: Use `pae_cutoff = 10.0` for Protenix/AF3; `15.0` only for legacy AF2.
4. ✅ **REQUIRED**: Apply hard filters (`ipTM > 0.5`, `pLDDT > 70`, `CA-RMSD < 3.5 A`) before composite ranking.
5. ✅ **REQUIRED**: Use multi-seed scoring (>= 20 seeds) for VHH/Fab/scFv; >= 10 seeds for de novo.
6. ✅ **REQUIRED**: Report missing metrics as `--` in tables. Never substitute zeros.
7. ✅ Restrict `pLDDT` mean to the design chain only — never average over both chains.
8. ✅ Use modality-aware thresholds — antibody, nanobody, de novo, bispecific, peptide each have their own bands.
9. ✅ When ipSAE and ipTM disagree, trust ipSAE for binding assessment.
10. ✅ Always include a Score Context block (with score bars) after ranked tables.
11. ✨ Visualize distributions with `plot_score_distributions.py` for any panel of >= 20 designs.
12. ✨ For diversity selection, run **by-diversity** after composite ranking — do not just take top-N by composite.

---

## Suggested Next Steps

After scoring is complete, the most common next moves:

1. **Run developability checks** (Lonza in-silico, MOE descriptors) — use the **by-screening** skill. Composite already accounts for HIGH-severity liabilities; developability tooling adds aggregation / charge / hydrophobicity insights.

2. **Diversify the panel** — use the **by-diversity** agent. Cluster on CDR-H3 (antibody) or interface residue identity (binder), pick top per cluster. Prevents shipping 10 near-identical sequences.

3. **Visualize top structures** — use the **by-display** skill (or `/by:view`). Confirm visually that high-composite candidates have plausible interface packing.

4. **Persist the panel to campaign state** — use the **by-campaign-manager** skill. Writes `screening_results.json` for resume + audit.

5. **Submit lab-ready candidates** — use the **by-lab** agent (triple-gated). Only invoke after composite >= 0.75 AND modality-appropriate ipSAE band AND zero HIGH-severity liabilities AND user runs `/by:approve-lab`.

6. **Re-score with more seeds if uncertain** — re-invoke this skill with `score_ipsae_multi_seed` on 40+ seeds for borderline candidates where `std_ipsae_min > 0.10`.

---

## Related Skills

**Upstream (run before this skill):**

- **protenix** — generates the PAE matrices and confidence JSON this skill scores.
- **boltzgen** — generates antibody/nanobody designs that get refolded.
- **pxdesign** — generates de novo binder designs.

**Downstream (run after this skill):**

- **by-screening** — broader screening pipeline (liabilities, developability, batch composite).
- **by-diversity** — picks a diverse panel from a composite-ranked list.
- **by-lab** — gated submission of LAB-READY candidates.

**Alternative / Complementary:**

- **by-research** — if the panel quality is poor, return to research and re-examine the target.
- **by-failure-diagnosis** — for systemic failure (zero LAB-READY across multiple runs).

---

## Key Conventions

- **Chain ordering**: Antibody chains (VH first, VL second if present) before antigen (last). This ordering is essential for correct ipSAE chain mask building.
- **Residue numbering**: Use `label_seq_id` (1-indexed, sequential) for all residue references.
- **Score precision**: Report ipTM and ipSAE to 2 decimal places in tables (4 internally). Report RMSD to 1 decimal place with `A` (Angstrom) unit.
- **Sample selection**: When Protenix generates multiple samples per design, select the sample with the highest `ipsae_min`. Report which sample index was selected.
- **Missing metrics**: Always indicate when a metric is unavailable. Never substitute zeros or placeholders that could be confused with real scores. Use `--` in tables for unavailable values.

---

## References

### Detailed documentation (this skill's `references/` directory)

- [references/ipsae-algorithm.md](references/ipsae-algorithm.md) — Full formula derivation from the DunbrackLab paper, step-by-step algorithm, and a worked numerical example reproducible with `scripts/calc_ipsae.py --example`.
- [references/composite-score.md](references/composite-score.md) — Composite formula `0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)` with rationale for each weight and override scenarios.
- [references/thresholds-by-modality.md](references/thresholds-by-modality.md) — Per-modality (antibody, nanobody, de novo, bispecific, peptide) ipSAE / ipTM / pLDDT / RMSD thresholds.
- [references/scoring-pitfalls.md](references/scoring-pitfalls.md) — 14 common misinterpretations and silent errors, with symptoms and fixes.

### Scripts (this skill's `scripts/` directory)

- `scripts/calc_ipsae.py` — Reference implementation of the DunbrackLab formula. CLI for scoring a single PAE matrix; verifies a worked numerical example.
- `scripts/composite_score.py` — Batch composite scoring of a scored CSV with modality-aware hard filters and configurable weights.
- `scripts/plot_score_distributions.py` — Multi-panel PDF (ipSAE, ipTM, composite, pLDDT) histograms at 300 DPI with verdict-band threshold lines.

### Implementation in the BY repository

- `src/proteus_cli/scoring/ipsae.py` — Production implementation used by the `by-screening` MCP server. Functions: `compute_ipsae`, `_directional_ipsae`, `score_npz`, `score_from_protenix_output`, `score_multi_seed`, `score_multi_seed_dir`, `interpret_ipsae`.

### External documentation

- DunbrackLab IPSAE reference implementation: <https://github.com/DunbrackLab/IPSAE>
- Protenix documentation: <https://github.com/bytedance/Protenix>
- BoltzGen repository: <https://github.com/HannesStark/boltzgen>

### Key papers

- Dunbrack et al. (2025), *"Res ipSAE loquuntur — Standalone interface scoring from PAE matrices"*. Primary reference for the ipSAE formula.
- Zhang & Skolnick (2004), *"Scoring function for automated assessment of protein structure template quality"*, Proteins 57:702-710. Source of the TM-score d0 formula adopted by ipSAE.
- Abramson et al. (2024), *"Accurate structure prediction of biomolecular interactions with AlphaFold 3"*, Nature 630:493-500. Origin of the PAE matrix outputs scored by ipSAE.
