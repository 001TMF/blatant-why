# Skill: Proteus Campaign Manager

Plan, execute, monitor, and assess protein/antibody design campaigns. This skill
governs how to size a campaign, track run state, coordinate multi-run efforts,
estimate cost and time, monitor progress, and evaluate campaign health.

---

## 1. Campaign Planning

### 1.1 Assess Target Difficulty

Before sizing a campaign, classify the target:

| Category | Indicators | Expected Hit Rate |
|----------|-----------|-------------------|
| **Well-studied** | Crystal structure <2.5A, known binders in PDB/SAbDab, clear pocket | 30-80% (prot), 20-50% (ab) |
| **Moderate** | Homology model or AF2 structure, some known interactors | 15-40% (prot), 10-30% (ab) |
| **Novel/difficult** | No known binders, flat/flexible surface, disordered, glycosylated | 5-20% (prot), 5-15% (ab) |

For well-studied targets, a preview campaign often suffices. For novel targets,
plan at least two rounds with parameter variation.

### 1.2 Choose the Right Tool

| Goal | Tool | CLI | Notes |
|------|------|-----|-------|
| De novo protein binder | **proteus-prot** | `pxdesign pipeline --preset extended -i config.yaml` | See `proteus-prot` skill |
| Antibody / nanobody | **proteus-ab** | `proteus-ab run spec.yaml --protocol <proto>` | See `proteus-ab` skill |
| Structure validation | **proteus-fold** | `protenix pred -i input.json` | See `proteus-fold` skill |

If the user wants an antibody or nanobody scaffold, always use proteus-ab. For
general protein binders (non-immunoglobulin), use proteus-prot. Use proteus-fold
for independent structure validation of top candidates.

### 1.3 Size the Campaign

| Tier | Designs | When to Use | Wall Time |
|------|---------|-------------|-----------|
| **Preview** | 5-10 | Feasibility check, new target, hotspot validation | 10-30 min (prot), 30-60 min (ab) |
| **Standard** | 20-50 | Production-quality, moderate targets, sufficient diversity | 1-4 hr (prot), 1-3 hr (ab) |
| **Production** | 100+ | Difficult targets, maximum diversity, high-throughput | 4-12 hr (prot), 3-8 hr (ab) |

Always start with **preview** before committing to standard or production.

### 1.4 Campaign Directory Structure

```
campaigns/{target_name}/campaign_{YYYYMMDD}_{NNN}/
  config.yaml                # Campaign parameters
  run_001/                   # Individual run output
    designs/                 # Generated design structures
    scores/                  # ipSAE, screening results
    summary.csv              # Per-design metrics
  run_002/...
  aggregated_results.csv     # Cross-run merged ranking
  campaign_log.json          # State tracking
```

---

## 2. State Tracking

### 2.1 Run Lifecycle

```
pending --> running --> screening --> complete
              |                         |
              +--> failed               +--> complete_with_warnings
```

- **pending**: Config written, awaiting GPU resources.
- **running**: Tool process active (backbone generation, sequence design, refolding).
- **screening**: Designs generated; running ipSAE, liability, developability checks.
- **complete**: All scores computed, results ranked, summary written.
- **failed**: Tool process crashed or timed out. Check stderr logs.
- **complete_with_warnings**: Finished but fewer designs passed than requested.

### 2.2 Tracking State

Maintain `campaign_log.json` in the campaign directory with fields: campaign_id,
target, tool, tier, and a runs array. Each run entry tracks: run_id, status,
started_at, completed_at, designs_requested, designs_generated, designs_passed,
top_iptm, and top_ipsae. Update at each state transition. The `/status` command
reads this file.

---

## 3. Multi-Run Coordination

### 3.1 When to Run Additional Campaigns

Trigger a follow-up run when:

- **Low pass rate**: Fewer than 20% of designs pass screening.
- **Poor top scores**: Best ipTM < 0.6 or best ipSAE_min < 0.4.
- **Insufficient diversity**: All passing designs cluster to a single topology.
- **User requests variation**: Different hotspots, protocol, or budget.

### 3.2 Parameter Variation Between Runs

Vary one axis at a time to diagnose improvements:

| Run | Variation | Rationale |
|-----|-----------|-----------|
| Run 1 | Default hotspots, standard budget | Baseline |
| Run 2 | Alternative hotspot set | Different epitope region |
| Run 3 | Increased budget / diversity alpha | More backbone diversity |
| Run 4 | Different protocol (e.g., nanobody to antibody) | Scaffold architecture change |

For proteus-prot, vary: hotspot residues, num_designs, preset (preview vs extended).
For proteus-ab, vary: protocol, budget, diversity_alpha, MSA mode, prefilter toggle.

### 3.3 Aggregating Cross-Run Results

1. Merge all `summary.csv` files into `aggregated_results.csv`.
2. De-duplicate by sequence identity (>95% identity = same design).
3. Re-rank: ipSAE_min (0.50) + ipTM (0.30) + liability_penalty (0.20).
4. Select top N diverse candidates via sequence clustering (Hamming distance).

---

## 4. Cost and Time Estimation

### 4.1 Per-Tool Compute Estimates (Single GPU)

| Tool | Operation | Time | GPU Memory |
|------|-----------|------|------------|
| **proteus-fold** | Single prediction | 2-5 min | 16-24 GB |
| **proteus-fold** | 5-seed ensemble | 10-25 min | 16-24 GB |
| **proteus-prot** | Preview (5-10 designs) | 10-30 min | 24-40 GB |
| **proteus-prot** | Extended (20-50 designs) | 1-4 hr | 24-40 GB |
| **proteus-prot** | Production (100+ designs) | 4-12 hr | 24-40 GB |
| **proteus-ab** | Nanobody (10-20 designs) | 30-60 min | 24-40 GB |
| **proteus-ab** | Antibody (20-50 designs) | 1-2 hr | 40-80 GB |
| **proteus-ab** | Large (50-100 designs) | 2-4 hr | 40-80 GB |

### 4.2 Screening Overhead

Screening adds minimal time: ipSAE 5-15 sec/design (CPU)
(GPU, requires checkpoint), liability+developability <1 sec/design (CPU). Full
battery for 30 designs takes 3-8 min total.

### 4.3 Total Campaign Time

```
total_time = design_generation + (num_designs * screening_per_design) + ranking
```

Example -- standard proteus-prot, 30 designs: ~2 hr generation + ~5 min screening
+ ~1 min ranking = **~2 hours 6 min**. Always report estimated time before launching.

---

## 5. Progress Monitoring

### 5.1 Slash Commands

| Command | Purpose |
|---------|---------|
| `/status` | Campaign overview: all runs, states, pass rates, top scores |
| `/watch <run_id>` | Live progress: current stage, designs completed, ETA |
| `/results` | Ranked design table with ipSAE, ipTM, pLDDT, RMSD, liabilities |
| `/screen <design_id>` | Full screening on one design: liabilities, developability, scores |

### 5.2 Pipeline Stage Display

When a run is active, show:

```
Design Run: run_001
  ○ Generating backbones     PXDesign / BoltzGen
  ● Designing sequences      ProteinMPNN / AntiFold          <-- active
  ○ Screening quality        ipSAE + liabilities
  ○ Evaluating structures    Protenix refolding
  ○ Filtering & ranking      Composite score
  ○ Design complete          Ready for review
Progress: 12/30 designs | ETA: ~45 min
```

### 5.3 Health Checks During Monitoring

- **Design generation stall**: If designs/ directory stops growing, tool may have crashed.
- **Early score check**: If first 5 designs all have ipTM < 0.3, hotspot selection is likely poor.
- **GPU utilization**: Drops may indicate errors or resource contention.

---

## 6. Campaign Health Assessment

### 6.1 Expected Pass Rates

| Tool | Target Type | Expected | Alarm |
|------|-------------|----------|-------|
| **proteus-prot** | Well-studied | 30-60% | < 15% |
| **proteus-prot** | Novel | 10-30% | < 5% |
| **proteus-ab** (nanobody) | Standard | 20-40% | < 10% |
| **proteus-ab** (antibody) | Standard | 15-35% | < 8% |

Pass = ipTM > 0.5, pLDDT > 70, RMSD < 3.5A, no high-severity CDR liabilities.

### 6.2 When to Abort

Abort if:
- Zero passing designs after 50% of the run completes.
- Tool unresponsive >15 min with no new output.
- GPU out-of-memory errors (reduce batch size or switch model variant).

Do NOT abort if:
- Pass rate is low but nonzero (2-3 good candidates can be valuable).
- Early scores are poor but improving (tool exploring topology space).

### 6.3 Historical Baselines

| Metric | Good | Acceptable | Concerning |
|--------|------|------------|------------|
| Best ipTM | > 0.8 | 0.6-0.8 | < 0.6 |
| Best ipSAE_min | > 0.7 | 0.4-0.7 | < 0.4 |
| Mean pLDDT (passing) | > 80 | 70-80 | < 70 |
| Pass rate | > 30% | 15-30% | < 15% |
| Diversity (clusters) | > 5 | 3-5 | < 3 |

### 6.4 Post-Campaign Actions

- **Healthy (good scores, >30% pass):** Present top 3-5 candidates. Offer proteus-fold
  ensemble validation. Suggest experimental ordering.
- **Marginal (acceptable, 15-30% pass):** Present with caveats. Recommend follow-up
  run with varied parameters. Consider production tier.
- **Poor (<15% pass or concerning scores):** Do not present as viable. Re-examine target
  prep, try different hotspots, or switch tools. Evaluate target tractability.

---

## Quick Reference: Campaign Launch Checklist

1. Classify target difficulty (well-studied / moderate / novel).
2. Select tool (proteus-prot or proteus-ab) and protocol.
3. Choose campaign tier (preview first, then escalate).
4. Identify hotspot residues from epitope analysis.
5. Estimate compute time and confirm GPU availability.
6. Create campaign directory structure.
7. Initialize campaign_log.json with pending state.
8. Launch run and confirm transition to running state.
9. Monitor with `/watch` and `/status`.
10. On completion, run full screening battery and aggregate results.
11. Assess campaign health against baselines.
12. Present ranked candidates or recommend follow-up actions.
