# Skill: BY Campaign Manager

Plan, execute, monitor, and assess protein/antibody design campaigns. This skill
governs how to size a campaign, track run state, coordinate multi-run efforts,
estimate cost and time, monitor progress, and evaluate campaign health.

---

## 0. Pre-Campaign Discussion

Before any campaign planning begins, run `/by:plan-campaign` to capture user preferences. This command produces `campaign_context.json` in the active campaign directory.

### What campaign_context.json Controls

| Field | Overrides | Default if Missing |
|-------|-----------|-------------------|
| `modality` | Tool selection (VHH -> nanobody-anything, scFv -> antibody-anything, de_novo -> protein-anything) | VHH |
| `epitope.residues` | Hotspot selection -- research agent focuses on specified residues | Structure-derived from interface analysis |
| `compute.tier` | Campaign sizing (preview: 500, standard: 5,000, production: 20,000) | Standard (5,000/scaffold) |
| `scaffolds` | Template selection for design agent | Modality defaults (VHH: caplacizumab + ozoralizumab; scFv: adalimumab + tezepelumab) |
| `success_criteria` | Composite score weighting in screening (hit_rate, diversity, confidence, or balanced) | Balanced |

### When campaign_context.json Exists

All downstream agents read it:
- **by-research** focuses on user-specified epitope regions and target features relevant to the chosen modality.
- **by-design** uses the specified modality, scaffolds, and compute tier without guessing.
- **by-screening** applies success criteria to weight composite scoring (e.g., diversity mode promotes cluster variety over raw scores).

### When campaign_context.json Does Not Exist

Fall back to auto-detection: modality from keywords, scaffolds from modality defaults, compute tier standard, epitope from structure analysis.

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
| Antibody / nanobody | **boltzgen** | `boltzgen run spec.yaml --protocol <proto>` | See `boltzgen` skill |
| Structure validation | **proteus-fold** | `protenix pred -i input.json` | See `proteus-fold` skill |

If the user wants an antibody or nanobody scaffold, always use boltzgen. For
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
For boltzgen, vary: protocol, budget, diversity_alpha, MSA mode, prefilter toggle.

### 3.3 Aggregating Cross-Run Results

1. Merge all `summary.csv` files into `aggregated_results.csv`.
2. De-duplicate by sequence identity (>95% identity = same design).
3. Re-rank: composite_score = 0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count).
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
| **boltzgen** | Nanobody (10-20 designs) | 30-60 min | 24-40 GB |
| **boltzgen** | Antibody (20-50 designs) | 1-2 hr | 40-80 GB |
| **boltzgen** | Large (50-100 designs) | 2-4 hr | 40-80 GB |

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
| **boltzgen** (nanobody) | Standard | 20-40% | < 10% |
| **boltzgen** (antibody) | Standard | 15-35% | < 8% |

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

0. Run `/by:plan-campaign` to capture preferences (`campaign_context.json`).
1. Classify target difficulty (well-studied / moderate / novel).
2. Select tool (proteus-prot or boltzgen) and protocol.
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

---

## 7. Checkpoint and Resume Integration

### 7.1 Checkpoint File Contract

Every campaign state transition writes a checkpoint file to
`campaigns/{target_name}/campaign_{date}_{NNN}/checkpoints/`. The checkpoint file
name encodes the phase order for resume logic.

| File | Phase | Written By | Contains |
|------|-------|-----------|----------|
| `00_draft.json` | Draft | campaign agent | campaign_id, target, parameters |
| `01_configured.json` | Configured | campaign agent | approved plan, user confirmation |
| `02_designing.json` | Designing | design agent | job_ids, batch_id, provider, tool |
| `03_design_complete.json` | Design done | design agent | designs_produced, results_path, provenance |
| `04_screening.json` | Screening | screening agent | designs_to_screen, screening start |
| `05_screening_complete.json` | Screened | screening agent | pass/fail counts, top scores, hit_rate |
| `06_ranking.json` | Ranked | screening agent | ranked_results_path, diversity_clusters |
| `07_complete.json` | Complete | campaign agent | final summary, knowledge_stored flag |

### 7.2 Resume Protocol

The `/by:resume` command follows this algorithm:

1. Find campaign directory (active or most recent)
2. List checkpoint files, sort by numeric prefix
3. Read latest checkpoint to determine resume point
4. Check for partial results or failed jobs
5. Present resume plan to user for confirmation
6. Dispatch the agent specified in `agent_to_dispatch`
7. Pass checkpoint data as context so agent skips completed work

### 7.3 Saga Compensation Rules

When a phase fails partially, apply compensation:

| Phase | Partial Failure | Compensation |
|-------|----------------|--------------|
| Design | Some Tamarind jobs failed | Proceed with successful; offer retry for failed |
| Design | Tamarind timeout | Resubmit timed-out jobs |
| Screening | Some designs fail to score | Skip failed, screen rest, report gap |
| Screening | Zero designs pass | Auto-diagnose, present recovery options |
| Ranking | Too few candidates | Warn user, present with caveats |

### 7.4 Knowledge Integration at Campaign Boundaries

**Pre-campaign (during planning):**
- Query `mcp__by-knowledge__knowledge_query_similar` for same/similar targets
- Query `mcp__by-knowledge__knowledge_scaffold_rankings` for scaffold performance
- Query `mcp__by-knowledge__knowledge_get_recommendations` for parameter suggestions
- Cite all prior evidence in the campaign plan

**Post-campaign (after ranking):**
- Store outcomes via `mcp__by-knowledge__knowledge_store_campaign`
- Store failures via `mcp__by-knowledge__knowledge_store_failure` (if hit rate < 15%)
- Record design provenance (design_id -> job_id -> scaffold -> epitope -> tool)
- Write round summary for cross-campaign comparison

### 7.5 Progress Monitoring During Campaigns

Track and report progress at each phase:

- **Design phase**: Poll `mcp__by-cloud__cloud_get_batch_status` every 30s. Report designs
  returned and best ipTM so far. Screen individual designs as they arrive
  (scatter-gather pattern).
- **Screening phase**: Report after every 5 designs scored. Show running pass
  rate and best composite score.
- **Cost tracking**: Maintain running cost counter if Tamarind tier info
  available.
- **Turn awareness**: Track turns used vs 25-turn budget. Checkpoint if
  approaching limit.

### 7.6 Campaign Health + Resume Decision Matrix

When resuming, assess campaign health before continuing:

| Checkpoint State | Health Check | Action |
|-----------------|-------------|--------|
| `02_designing` (no results) | Jobs may have expired | Check status; resubmit if expired |
| `02_designing` (partial) | Some results exist | Continue monitoring; screen partial |
| `03_design_complete` | Results on disk | Verify file integrity; start screening |
| `04_screening` (partial) | Some scores exist | Screen only remaining designs |
| `05_screening_complete` | Scores computed | Proceed to ranking |
| Checkpoint > 24h old | May be stale | Warn user; offer restart option |

---

## 8. Error Recovery

### Checkpoint Files

Campaign state is checkpointed at every state transition. Each agent writes its output to a known path before updating campaign status:

| Transition | Checkpoint File | Written By |
|------------|----------------|------------|
| -> researching | `research_report.md` | by-research |
| -> configured | `campaign_plan.md` | by-campaign |
| -> designing | `design_summary.json` | by-design |
| -> screening | `screening_results.json` | by-screening |
| -> complete | `verification_report.md` | by-verifier |

### Session Recovery (`/by:resume`)

When a session is interrupted (timeout, crash, context limit):
1. Read `.by/campaigns/<id>/delegation_log.json` to find the last completed agent
2. Read the campaign state via `campaign_get(campaign_dir)` to confirm current status
3. Identify the next agent in the 13-turn happy path that has not completed
4. Resume from that point -- do not re-run completed agents
5. If the last agent was mid-execution (status: "running" in delegation_log), check for partial output:
   - If the checkpoint file exists and is valid, treat as completed
   - If the checkpoint file is missing or incomplete, re-dispatch that agent

### Partial Results Handling

When a batch of design jobs partially fails:
- Collect results from completed jobs (do not discard them)
- Record failed job IDs and error messages in `design_summary.json`
- If >50% of jobs succeeded, proceed to screening with available designs
- If <50% succeeded, halt and report to user with failure analysis
- Never silently drop failed jobs from the count

### Failure Escalation

| Failure Type | Action |
|-------------|--------|
| Single job failure | Retry up to 2x, then mark failed and continue |
| Batch >50% failure | Halt pipeline, report to user with diagnosis |
| Agent crash | Log in delegation_log.json, resume via `/by:resume` |
| MCP server unreachable | Wait 30s, retry 2x, then halt with provider status |
| Campaign state corruption | Report to user, do not attempt auto-repair |

---

## 9. Learning System

Before planning any campaign, query the knowledge base for prior evidence:
1. `mcp__by-knowledge__knowledge_query_similar` -- find past campaigns against similar targets
2. `mcp__by-knowledge__knowledge_scaffold_rankings` -- best scaffolds for this target class
3. `mcp__by-knowledge__knowledge_get_recommendations` -- parameter suggestions based on historical data

Cite prior evidence in recommendations:
- "Based on 3 prior campaigns against PD-L1, caplacizumab scaffold achieved 23% hit rate vs 12% for ozoralizumab"
- "Similar epitope topology in prior CD47 campaign yielded best results with budget=100, alpha=0.001"

After campaign completion, store results via `mcp__by-knowledge__knowledge_store_campaign`. Record failures via `mcp__by-knowledge__knowledge_store_failure`.

---

## 10. Agent Teams and Model Profiles

For complex campaigns, deploy specialized agent teams. Each agent has scoped MCP server access and disallowed tools for safety.

| Agent | Role | Disallowed Tools |
|-------|------|-----------------|
| by-research | Target analysis, literature, prior art, epitope mapping | mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__* |
| by-design | Generate designs via available compute | mcp__by-adaptyv__* |
| by-screening | Score, filter, rank designs | mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__* |
| by-campaign | Plan campaigns, manage state, cost estimates | mcp__by-adaptyv__adaptyv_confirm_submission |
| by-knowledge | Query/update learning system | mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__* |
| by-verifier | Quality gates: ipSAE>0.5, pLDDT>70, screening completeness | mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__* |
| by-plan-checker | Campaign plan review: fold validation, cost, parameters | mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__* |
| by-environment | Discover tools, GPU, SSH, API keys. Write environment.json | mcp__by-adaptyv__* |
| by-lab | Adaptyv Bio submission (triple-gated) | mcp__by-cloud__cloud_submit_job |
| by-evaluator | Deep structural evaluation: refolding, interface quality | mcp__by-adaptyv__* |
| by-visualization | Generate PyMOL/ChimeraX session scripts | mcp__by-cloud__*, mcp__by-adaptyv__* |
| by-diversity | Sequence/structural clustering, Pareto fronts, diverse panel selection | mcp__by-cloud__*, mcp__by-adaptyv__* |
| by-epitope | Deep epitope analysis: interface mapping, druggability, hotspot arrays | mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__* |
| by-humanization | Humanize non-human antibodies: CDR grafting, back-mutations | mcp__by-cloud__*, mcp__by-adaptyv__* |
| by-liability-engineer | Propose mutations to fix liabilities: structural context, impact scoring | mcp__by-cloud__*, mcp__by-adaptyv__* |
| by-formatter | Format designs: scFv conversion, FASTA/GenBank/YAML/Adaptyv output | mcp__by-cloud__*, mcp__by-adaptyv__adaptyv_confirm_submission |

### Model Profiles

Agents resolve model at spawn time based on the active profile in `.by/config.json`.

| Agent | quality | balanced (default) | budget |
|-------|---------|-------------------|--------|
| by-research | opus | sonnet | sonnet |
| by-design | opus | sonnet | sonnet |
| by-screening | sonnet | sonnet | haiku |
| by-campaign | opus | opus | sonnet |
| by-knowledge | sonnet | haiku | haiku |
| by-verifier | sonnet | sonnet | sonnet |
| by-plan-checker | sonnet | sonnet | haiku |
| by-environment | sonnet | sonnet | haiku |
| by-lab | opus | opus | sonnet |
| by-evaluator | opus | sonnet | sonnet |
| by-visualization | sonnet | sonnet | haiku |
| by-diversity | sonnet | sonnet | haiku |
| by-epitope | opus | sonnet | sonnet |
| by-humanization | opus | sonnet | haiku |
| by-liability-engineer | sonnet | sonnet | haiku |
| by-formatter | sonnet | haiku | haiku |

### Agent Delegation Protocol

For any design campaign, you MUST delegate to specialized sub-agents via the Task tool.
Do NOT do research, design, or screening inline in the main session.

**Why:** Each agent has scoped MCP tool access, quality gates, and specific expertise.
Running inline wastes turns and misses quality checks.

**Task() invocation syntax:**

```
Task(agent="by-research", prompt="Analyze target {target_name}. PDB: {pdb_id}. Write report to {campaign_dir}/research_report.md")
Task(agent="by-campaign", prompt="Plan campaign for {target_name}. Research: {campaign_dir}/research_report.md. Write plan to {campaign_dir}/campaign_plan.md")
Task(agent="by-design", prompt="Execute designs for campaign {campaign_id}. Plan: {campaign_dir}/campaign_plan.md. Write summary to {campaign_dir}/design_summary.json")
Task(agent="by-screening", prompt="Screen designs for campaign {campaign_id}. Designs: {campaign_dir}/design_summary.json. Write results to {campaign_dir}/screening_results.json")
Task(agent="by-verifier", prompt="Verify campaign {campaign_id}. Screening: {campaign_dir}/screening_results.json. Write report to {campaign_dir}/verification_report.md")
```

**13-turn happy path:**
1. User requests campaign (turn 1)
2. Task(by-research) -- target analysis (turn 2)
3. Review research report (turn 3)
4. Task(by-campaign) -- plan campaign (turn 4)
5. Review plan, present to user (turn 5)
6. User approves plan (turn 6)
7. Task(by-design) -- submit and monitor jobs (turn 7)
8. Review design results (turn 8)
9. Task(by-screening) -- screen all designs (turn 9)
10. Review screening results (turn 10)
11. Task(by-verifier) -- independent verification (turn 11)
12. Review verification, compile final ranked table (turn 12)
13. Present results to user with next steps (turn 13)

**Model resolution:** Before spawning any agent, resolve the model from `.by/config.json`:
- Read `.by/config.json` `profile` field (default: `balanced`)
- Look up the agent row in the Model Profiles table above
- Pass the resolved model to the Task() call

**Delegation log:** After each Task() dispatch, append to `.by/campaigns/<id>/delegation_log.json`:
```json
{
  "entries": [
    {
      "timestamp": "2026-03-24T10:00:00Z",
      "agent": "by-research",
      "model": "sonnet",
      "prompt_summary": "Analyze target PD-L1",
      "status": "completed",
      "output_path": "research_report.md",
      "duration_s": 45
    }
  ]
}
```
This log enables `/by:resume` to pick up where a session left off.

**Only skip delegation for:**
- Quick tests or single fold validations (one tool call, no pipeline)
- Single-tool operations (e.g., one screening call, one PDB lookup)
