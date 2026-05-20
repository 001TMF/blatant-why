---
id: "skill_d4e763ef03f044248cc5202d582f28d7"
name: "by-campaign-manager"
display-name: "BY Campaign Manager"
short-description: "Plan, size, monitor, checkpoint, and assess protein/antibody design campaigns end-to-end. Use when starting a campaign, tracking run state, estimating cost/time, resuming after interruption, or evaluating campaign health mid-run."
category: "orchestration"
keywords: "campaign, planning, state machine, checkpoint, resume, cost estimate, health, multi-run, orchestration, tier, modality"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: ["mcp__by-campaign__campaign_get", "mcp__by-campaign__campaign_create", "mcp__by-campaign__campaign_update", "mcp__by-campaign__campaign_list", "mcp__by-knowledge__knowledge_query_similar", "mcp__by-knowledge__knowledge_scaffold_rankings", "mcp__by-knowledge__knowledge_get_recommendations", "mcp__by-knowledge__knowledge_store_campaign", "mcp__by-knowledge__knowledge_store_failure", "mcp__by-cloud__cloud_get_batch_status"]
---

# BY Campaign Manager

Plan, execute, monitor, and assess protein/antibody design campaigns. This skill
governs how to size a campaign, track run state, coordinate multi-run efforts,
estimate cost and time on each compute target (local GPU, HPC, Tamarind),
monitor progress, and evaluate campaign health.

---

## When to Use This Skill

Use this skill when you need to:

- ✅ **Start a new design campaign** — size designs/scaffolds, pick modality, choose compute tier
- ✅ **Track run state** through the campaign state machine (draft → configured → designing → screening → ranked → submitted)
- ✅ **Estimate cost and time** before launching (local GPU hours, HPC $/hr, Tamarind credits)
- ✅ **Resume an interrupted campaign** from the last checkpoint without re-doing work
- ✅ **Assess mid-run health** — pass rate trajectory, score distributions, abort/continue decisions
- ✅ **Coordinate multi-run efforts** — vary one parameter axis at a time, aggregate cross-run results
- ✅ **Decide when to iterate** — low pass rate, poor scores, insufficient diversity

**Don't use this skill for:**
- ❌ Target research and epitope mapping → use `by-research`
- ❌ Submitting individual jobs or scoring single designs → use `by-design` / `by-screening`
- ❌ Lab submission gating → use `by-lab` (triple-gated)
- ❌ HPC infrastructure setup → use `by-deploy-compute`
- ❌ Sequence/structure clustering for diverse panels → use `by-diversity`

---

## Quick Start

A typical campaign launch from the planner sub-agent:

```bash
# 1. Capture user preferences (modality, tier, scaffolds)
/by:plan-campaign

# 2. Estimate cost on each compute target before approval
python scripts/estimate_campaign.py \
  --target PD-L1 \
  --modality vhh \
  --tier standard \
  --scaffolds 2

# 3. Initialize campaign state and launch design phase
#    (delegate via Task(by-design, ...))

# 4. Monitor mid-run
python scripts/track_progress.py \
  --campaign-dir campaigns/pdl1/campaign_20260520_001
```

Expected `estimate_campaign.py` output: cost table for local / HPC RunPod / Tamarind,
with wall-clock hours and confidence intervals.

Expected `track_progress.py` output: designs submitted / scored / passed counts,
running pass rate, ETA, and spend-to-date.

---

## Inputs

**Required:**
- **`campaign_context.json`** — captured by `/by:plan-campaign`; contains modality, tier, scaffolds, epitope, success_criteria
- **`research/recommended_hotspots.json`** — from `by-research`; residue list for design agent
- **`research/design_recommendation.json`** — from `by-research`; modality, scaffolds, tier rationale

**Alternative inputs:**
- **User-supplied target name and PDB ID only** — falls back to auto-detection (modality from keywords, scaffolds from modality defaults, tier=standard)

**Optional:**
- **`.by/config.json`** — compute provider, model profile, fallback policy. If missing, defaults to `local` provider, `balanced` profile.
- **Prior campaign IDs** — queried via `mcp__by-knowledge__knowledge_query_similar` to bias scaffold and parameter choices.

See [references/state-machine.md](references/state-machine.md#required-artifacts) for the full artifact contract at each state.

---

## Outputs

**Primary results:**
- **`campaign_log.json`** — top-level campaign state (campaign_id, target, tool, status, rounds, costs, history). Updated at every state transition.
- **`checkpoints/NN_<state>.json`** — one file per phase transition. Resume reads the highest numeric prefix. See [references/state-machine.md](references/state-machine.md#checkpoint-file-format).

**Per-run outputs (under `run_NNN/`):**
- `designs/` — generated structures
- `scores/` — ipSAE, ipTM, liability JSON
- `summary.csv` — per-design metrics

**Cross-run outputs:**
- `aggregated_results.csv` — merged ranking across rounds with composite score
- `cost_estimate.json` — pre-launch breakdown by compute target (local/HPC/Tamarind)
- `progress_snapshot.json` — written by `track_progress.py` on demand

**Reports:**
- `campaign_plan.md` — approved plan with rationale, written by the `by-campaign` agent
- `verification_report.md` — final independent verification by `by-verifier`

---

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — confirm the user has an approved plan before any compute is spent.

1. **Plan approval (ASK THIS FIRST):**
   - Has `/by:plan-campaign` been run, and has the user approved the resulting plan?
   - If no: route to plan capture first. Do not estimate costs against a plan that does not exist.

2. **Target and modality:**
   - What is the target (name, PDB ID or UniProt accession)?
   - Antibody, nanobody (VHH), or de novo protein binder?
   - Example: "PD-L1 (PDB 7S4S), VHH" → triggers `nanobody-anything` protocol.

3. **Compute provider:**
   - Local GPU (default), HPC (RunPod), or Tamarind cloud?
   - Read `.by/config.json` `compute.default_provider`. Confirm with the user before overriding.
   - See [references/cost-model.md](references/cost-model.md#provider-selection) for trade-offs.

4. **Tier / budget:**
   - Preview (5–10 designs), Standard (20–50), or Production (100+)?
   - Default = Standard. Recommend Preview first for novel targets.

5. **Epitope / hotspots:**
   - Specific residues to target, or let the research agent derive from structure?

6. **Resume vs new campaign:**
   - Is there an existing campaign directory to resume? Run `/by:resume` first.

7. **Success criteria weighting:**
   - Hit rate, diversity, confidence, or balanced? Affects composite score in screening.

---

## Standard Workflow

🚨 **MANDATORY: USE SCRIPTS EXACTLY AS SHOWN — DO NOT WRITE INLINE CODE** 🚨

This skill orchestrates other agents. The campaign-manager itself runs two CLI scripts
(estimate, track) and dispatches sub-agents via `Task()`. Do not inline cost math or
progress polling — the scripts are the source of truth.

### 0. Pre-Campaign Discussion

Before any campaign planning begins, run `/by:plan-campaign` to capture user preferences.
This command produces `campaign_context.json` in the active campaign directory.

#### What campaign_context.json Controls

| Field | Overrides | Default if Missing |
|-------|-----------|--------------------|
| `modality` | Tool selection (VHH → nanobody-anything, scFv → antibody-anything, de_novo → protein-anything) | VHH |
| `epitope.residues` | Hotspot selection — research agent focuses on specified residues | Structure-derived from interface analysis |
| `compute.tier` | Campaign sizing (preview: 500, standard: 5,000, production: 20,000) | Standard (5,000/scaffold) |
| `scaffolds` | Template selection for design agent | Modality defaults (VHH: caplacizumab + ozoralizumab; scFv: adalimumab + tezepelumab) |
| `success_criteria` | Composite score weighting in screening (hit_rate, diversity, confidence, balanced) | Balanced |

#### When campaign_context.json Exists

All downstream agents read it:
- **by-research** focuses on user-specified epitope regions and target features relevant to the chosen modality.
- **by-design** uses the specified modality, scaffolds, and compute tier without guessing.
- **by-screening** applies success criteria to weight composite scoring (e.g., diversity mode promotes cluster variety over raw scores).

#### When campaign_context.json Does Not Exist

Fall back to auto-detection: modality from keywords, scaffolds from modality defaults, compute tier standard, epitope from structure analysis.

✅ **VERIFICATION:** `campaign_context.json` exists in campaign directory; modality, tier, scaffolds populated.

### 1. Campaign Planning

#### 1.1 Assess Target Difficulty

Before sizing a campaign, classify the target:

| Category | Indicators | Expected Pass Rate |
|----------|-----------|--------------------|
| **Well-studied** | Crystal structure <2.5Å, known binders in PDB/SAbDab, clear pocket | 30–80% (PXDesign), 20–50% (BoltzGen) |
| **Moderate** | Homology model or AF2 structure, some known interactors | 15–40% (PXDesign), 10–30% (BoltzGen) |
| **Novel/difficult** | No known binders, flat/flexible surface, disordered, glycosylated | 5–20% (PXDesign), 5–15% (BoltzGen) |

For well-studied targets, a preview campaign often suffices. For novel targets,
plan at least two rounds with parameter variation.

#### 1.2 Choose the Right Tool

| Goal | Engine | CLI | Notes |
|------|--------|-----|-------|
| De novo protein binder | **PXDesign** | `pxdesign pipeline --preset extended -i config.yaml` | See `pxdesign` skill |
| Antibody / nanobody | **BoltzGen** | `boltzgen run spec.yaml --protocol <proto>` | See `boltzgen` skill |
| Structure validation | **Protenix** | `protenix pred -i input.json` | See `protenix` skill |

If the user wants an antibody or nanobody scaffold, always use BoltzGen. For
general protein binders (non-immunoglobulin), use PXDesign. Use Protenix
for independent structure validation of top candidates.

#### 1.3 Size the Campaign

| Tier | Designs | When to Use | Wall Time (local A100) |
|------|---------|-------------|------------------------|
| **Preview** | 5–10 | Feasibility check, new target, hotspot validation | 10–30 min (PXDesign), 30–60 min (BoltzGen) |
| **Standard** | 20–50 | Production-quality, moderate targets, sufficient diversity | 1–4 hr (PXDesign), 1–3 hr (BoltzGen) |
| **Production** | 100+ | Difficult targets, maximum diversity, high-throughput | 4–12 hr (PXDesign), 3–8 hr (BoltzGen) |

Always start with **preview** before committing to standard or production.

#### 1.4 Estimate Cost on Each Compute Target

🚨 **MANDATORY:** Run the estimator BEFORE launching any GPU job.

```bash
python scripts/estimate_campaign.py \
  --target <target_name> \
  --modality <vhh|scfv|denovo> \
  --tier <preview|standard|production> \
  --scaffolds <N> \
  --provider <local|hpc|tamarind|all>
```

✅ **VERIFICATION:** Output shows three rows (local, HPC RunPod, Tamarind) with
wall-clock hours, cost USD, and a confidence interval. Cost JSON written to
`cost_estimate.json`.

See [references/cost-model.md](references/cost-model.md) for the full per-engine
hours/cost breakdown.

#### 1.5 Campaign Directory Structure

```
campaigns/{target_name}/campaign_{YYYYMMDD}_{NNN}/
  campaign_context.json      # User preferences (from /by:plan-campaign)
  campaign_log.json          # Top-level state (updated every transition)
  cost_estimate.json         # Pre-launch cost breakdown
  config.yaml                # Engine parameters (passed to BoltzGen/PXDesign)
  checkpoints/
    00_draft.json
    01_configured.json
    02_designing.json
    ...
  research/                  # by-research outputs
  run_001/                   # Individual run output
    designs/
    scores/
    summary.csv
  run_002/...
  aggregated_results.csv     # Cross-run merged ranking
```

### 2. State Tracking

#### 2.1 Campaign State Machine

```
draft → configured → designing → screening → ranked → submitted
                          ↘ failed     ↘ failed   ↘ iterated → designing
```

See [references/state-machine.md](references/state-machine.md) for the full
diagram, transition triggers, and required artifacts at each state.

#### 2.2 Run Lifecycle (within a round)

```
pending → running → screening → complete
            ↓                      ↓
            failed                 complete_with_warnings
```

- **pending**: Config written, awaiting GPU resources.
- **running**: Engine process active (backbone generation, sequence design, refolding).
- **screening**: Designs generated; running ipSAE, liability, developability checks.
- **complete**: All scores computed, results ranked, summary written.
- **failed**: Engine process crashed or timed out. Check stderr logs.
- **complete_with_warnings**: Finished but fewer designs passed than requested.

#### 2.3 Tracking State

Maintain `campaign_log.json` with fields: `campaign_id`, `target`, `tool`, `tier`,
and a `runs` array. Each run entry tracks: `run_id`, `status`, `started_at`,
`completed_at`, `designs_requested`, `designs_generated`, `designs_passed`,
`top_iptm`, `top_ipsae`. Update at each state transition. The `/by:status` command
reads this file.

### 3. Multi-Run Coordination

#### 3.1 When to Run Additional Campaigns

Trigger a follow-up run when:

- **Low pass rate**: Fewer than 20% of designs PASS screening.
- **Poor top scores**: Best ipTM < 0.6 or best ipSAE_min < 0.4.
- **Insufficient diversity**: All passing designs cluster to a single topology.
- **User requests variation**: Different hotspots, protocol, or budget.

#### 3.2 Parameter Variation Between Runs

Vary one axis at a time to diagnose improvements:

| Run | Variation | Rationale |
|-----|-----------|-----------|
| Run 1 | Default hotspots, standard budget | Baseline |
| Run 2 | Alternative hotspot set | Different epitope region |
| Run 3 | Increased budget / diversity alpha | More backbone diversity |
| Run 4 | Different protocol (e.g., nanobody → antibody) | Scaffold architecture change |

For PXDesign, vary: hotspot residues, num_designs, preset (preview vs extended).
For BoltzGen, vary: protocol, budget, diversity_alpha, MSA mode, prefilter toggle.

#### 3.3 Aggregating Cross-Run Results

1. Merge all `summary.csv` files into `aggregated_results.csv`.
2. De-duplicate by sequence identity (>95% identity = same design).
3. Re-rank: `composite_score = 0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)`.
4. Select top N diverse candidates via sequence clustering (Hamming distance).

### 4. Progress Monitoring

#### 4.1 Slash Commands

| Command | Purpose |
|---------|---------|
| `/by:status` | Campaign overview: all runs, states, pass rates, top scores |
| `/by:watch <run_id>` | Live progress: current stage, designs completed, ETA |
| `/by:results` | Ranked design table with ipSAE, ipTM, pLDDT, RMSD, liabilities |
| `/by:screen <design_id>` | Full screening on one design: liabilities, developability, scores |

#### 4.2 Progress Dashboard Script

```bash
python scripts/track_progress.py --campaign-dir campaigns/<target>/campaign_<date>_<NNN>
```

✅ **VERIFICATION:** Output shows: designs submitted, scored, PASSed; ETA; running spend.

#### 4.3 Pipeline Stage Display

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

#### 4.4 Mid-Run Health Checks

- **Design generation stall**: If `designs/` directory stops growing, engine may have crashed.
- **Early score check**: If first 5 designs all have ipTM < 0.3, hotspot selection is likely poor.
- **GPU utilization**: Drops may indicate errors or resource contention.

See [references/health-metrics.md](references/health-metrics.md) for thresholds and
abort-vs-continue decision logic.

### 5. Checkpoint and Resume Integration

#### 5.1 Checkpoint File Contract

Every campaign state transition writes a checkpoint file to
`campaigns/{target_name}/campaign_{date}_{NNN}/checkpoints/`. The file name
encodes the phase order for resume logic.

| File | Phase | Written By | Contains |
|------|-------|-----------|----------|
| `00_draft.json` | Draft | campaign agent | campaign_id, target, parameters |
| `01_configured.json` | Configured | campaign agent | approved plan, user confirmation |
| `02_designing.json` | Designing | design agent | job_ids, batch_id, provider, engine |
| `03_design_complete.json` | Design done | design agent | designs_produced, results_path, provenance |
| `04_screening.json` | Screening | screening agent | designs_to_screen, screening start |
| `05_screening_complete.json` | Screened | screening agent | pass/fail counts, top scores, pass rate |
| `06_ranking.json` | Ranked | screening agent | ranked_results_path, diversity_clusters |
| `07_complete.json` | Complete | campaign agent | final summary, knowledge_stored flag |

See [references/state-machine.md](references/state-machine.md#checkpoint-file-format) for full schemas.

#### 5.2 Resume Protocol

The `/by:resume` command follows this algorithm:

1. Find campaign directory (active or most recent).
2. List checkpoint files, sort by numeric prefix.
3. Read latest checkpoint to determine resume point.
4. Check for partial results or failed jobs.
5. Present resume plan to user for confirmation.
6. Dispatch the agent specified in `agent_to_dispatch`.
7. Pass checkpoint data as context so the agent skips completed work.

#### 5.3 Saga Compensation Rules

When a phase fails partially, apply compensation:

| Phase | Partial Failure | Compensation |
|-------|----------------|--------------|
| Design | Some HPC/Tamarind jobs failed | Proceed with successful; offer retry for failed |
| Design | Compute timeout | Resubmit timed-out jobs |
| Screening | Some designs fail to score | Skip failed, screen rest, report gap |
| Screening | Zero designs PASS | Auto-diagnose, present recovery options |
| Ranking | Too few candidates | Warn user, present with caveats |

### 6. Knowledge Integration at Campaign Boundaries

**Pre-campaign (during planning):**
- Query `mcp__by-knowledge__knowledge_query_similar` for same/similar targets
- Query `mcp__by-knowledge__knowledge_scaffold_rankings` for scaffold performance
- Query `mcp__by-knowledge__knowledge_get_recommendations` for parameter suggestions
- Cite all prior evidence in the campaign plan

**Post-campaign (after ranking):**
- Store outcomes via `mcp__by-knowledge__knowledge_store_campaign`
- Store failures via `mcp__by-knowledge__knowledge_store_failure` (if pass rate < 15%)
- Record design provenance (design_id → job_id → scaffold → epitope → engine)
- Write round summary for cross-campaign comparison

---

## When Scripts Fail

Follow the script failure hierarchy:

1. **Fix and Retry (90%)** — Install missing package, re-run. Most common cause: missing `pyyaml` or `pandas`.
2. **Modify Script (5%)** — Edit the script file itself if a config field name changed.
3. **Use as Reference (4%)** — Read script, adapt approach for an unusual campaign shape (e.g., multi-target).
4. **Write from Scratch (1%)** — Only if impossible, explain why in the campaign log.

⚠️ **CRITICAL — DO NOT:**
- ❌ Inline cost math in the main session → use `estimate_campaign.py`
- ❌ Hardcode provider rates → read from script config
- ❌ Skip the cost estimate before launching → users must approve $ spend
- ❌ Poll batch status manually → use `track_progress.py`

---

## Decision Points

### Compute Provider Selection

| Provider | When to Use | Cost Profile |
|----------|-------------|--------------|
| **local** (default) | User has on-prem GPU; small/medium campaigns; iterative work | Zero $; bound by GPU memory + wall clock |
| **hpc** (RunPod) | Local GPU insufficient; need 40–80 GB cards; bursty workloads | $/hr by GPU class; see by-deploy-compute |
| **tamarind** | Fallback when local+HPC unavailable | $/credit; managed runtime |

Read `.by/config.json` `compute.default_provider`. Never silently switch providers.
See [references/cost-model.md](references/cost-model.md#provider-selection).

### Abort vs Continue Mid-Run

| Signal | Action |
|--------|--------|
| Zero PASS designs after 50% of run completed | **Abort.** Re-examine hotspots or tool. |
| Engine unresponsive >15 min, no new output | **Abort.** Check logs; resubmit. |
| GPU OOM repeated | **Abort.** Reduce batch size or switch model variant. |
| Pass rate low but nonzero (2–3 candidates) | **Continue.** Valuable hits possible. |
| Early scores poor but improving | **Continue.** Engine exploring topology space. |

See [references/health-metrics.md](references/health-metrics.md#abort-criteria).

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `campaign_log.json` missing after dispatch | Agent crashed before writing checkpoint | Run `/by:resume`; auto-detects partial state | [state-machine.md](references/state-machine.md#recovery) |
| Cost estimate shows $0 across providers | `compute.default_provider` not set | Set in `.by/config.json`; defaults to local | [cost-model.md](references/cost-model.md#provider-selection) |
| Pass rate < 5% on well-studied target | Wrong scaffold or hotspot selection | Vary scaffold (run 2); re-check epitope from `by-research` | [health-metrics.md](references/health-metrics.md#low-pass-rate) |
| Resume picks wrong phase | Checkpoint files out of order (numeric prefix mismatch) | Verify filenames; rename to canonical `NN_<phase>.json` | [state-machine.md](references/state-machine.md#checkpoint-file-format) |
| Progress script reports ETA = ∞ | First design not yet completed | Wait until at least one design finishes for rate calibration | — |
| Local GPU OOM at BoltzGen antibody stage | Antibody protocol needs 40+ GB; local card is 24 GB | Switch to HPC for antibody; keep VHH on local | [cost-model.md](references/cost-model.md#gpu-requirements) |
| Tamarind selected despite local config | Code path ignored `compute.default_provider` | Bug — file issue; do NOT silently fall back | CLAUDE.md compute policy |
| Aggregated results show duplicates | De-dup threshold too lenient | Tighten to >95% sequence identity | — |
| Pass rate drops sharply mid-run | Score distribution drift (engine exploring weak region) | Continue if recovering; abort if 50%+ remains and pass=0 | [health-metrics.md](references/health-metrics.md#pass-rate-trajectory) |
| Cost overruns budget | Tier auto-escalated without confirmation | Always reconfirm tier change with user before relaunch | — |
| `knowledge_store_campaign` fails post-campaign | MCP server unreachable | Retry 2×, then write to `pending_knowledge.json` for replay | — |
| Mid-run health check fails but user approved | Override path not enforced | Document in `campaign_log.json.history`; surface in final report | — |

---

## Best Practices

1. 🚨 **CRITICAL:** Always run `estimate_campaign.py` BEFORE launching any GPU job — surface cost on every provider.
2. 🚨 **CRITICAL:** Respect `compute.default_provider` in `.by/config.json`. Never silently switch.
3. ✅ **REQUIRED:** Use `/by:plan-campaign` to capture preferences before delegation; do not auto-detect when context exists.
4. ✅ **REQUIRED:** Write a checkpoint at EVERY state transition (no exceptions, even on partial failure).
5. ✅ **REQUIRED:** Start with a Preview tier for novel targets — confirm hit potential before spending Production budget.
6. ✅ Vary ONE parameter axis per follow-up run; otherwise you cannot diagnose what improved.
7. ✅ Query `mcp__by-knowledge__knowledge_query_similar` before sizing — prior campaigns predict pass rate.
8. ✅ Use composite score `0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)` for cross-run ranking.
9. ❌ Do NOT skip Preview just because a target "looks easy" — surprises are expensive.
10. ❌ Do NOT inline cost math or progress polling in the main session — use the scripts.
11. ✨ Persist target-specific learnings post-campaign via `mcp__by-knowledge__knowledge_store_campaign` even on failure.

---

## Suggested Next Steps

After campaign planning completes (state = `configured`):

1. **`by-design`** — Submit and monitor design jobs. Reads `campaign_log.json` + `campaign_context.json`.
2. **`by-screening`** — Score and filter generated designs. Triggered when run transitions to `screening`.
3. **`by-verifier`** — Independent verification of top candidates before lab submission.
4. **`by-diversity`** — Cluster and select diverse panels when assembling final ranked list.
5. **`by-lab`** — Triple-gated lab submission (only after verification passes).

After campaign completion:
- **`by-knowledge`** — Store outcomes for future cross-campaign learning.
- **`by-campaign-optimizer`** — Use active-learning recommendations to size the next round.

Why chain these: modular agent design means each step writes a known artifact
that the next step reads. Re-running any step is idempotent given the checkpoint.

---

## Related Skills

**Upstream (run before):**
- `by-research` — target analysis, hotspot recommendations, design recommendation JSON
- `by-session` — environment + config initialization

**Downstream (run after):**
- `by-design` — execute design phase
- `by-screening` — filter and rank designs
- `by-verifier` — final quality gate
- `by-knowledge` — persist learnings

**Alternative / Complementary:**
- `by-deploy-compute` — HPC infrastructure setup (call when switching from local → HPC)
- `by-design-workflow` — higher-level orchestrator covering the full pipeline
- `by-hypothesis-debate` — strategy selection before committing to a design approach
- `by-campaign-optimizer` — active-learning recommendations for follow-up rounds

---

## Error Recovery

### Checkpoint Files

Campaign state is checkpointed at every state transition. Each agent writes its
output to a known path before updating campaign status:

| Transition | Checkpoint File | Written By |
|------------|----------------|------------|
| → researching | `research_report.md` | by-research |
| → configured | `campaign_plan.md` | by-campaign |
| → designing | `design_summary.json` | by-design |
| → screening | `screening_results.json` | by-screening |
| → complete | `verification_report.md` | by-verifier |

### Session Recovery (`/by:resume`)

When a session is interrupted (timeout, crash, context limit):

1. Read `.by/campaigns/<id>/delegation_log.json` to find the last completed agent.
2. Read the campaign state via `mcp__by-campaign__campaign_get(campaign_dir)` to confirm status.
3. Identify the next agent in the 13-turn happy path that has not completed.
4. Resume from that point — do not re-run completed agents.
5. If the last agent was mid-execution (status: "running" in delegation_log), check for partial output:
   - If the checkpoint file exists and is valid, treat as completed.
   - If the checkpoint file is missing or incomplete, re-dispatch that agent.

### Partial Results Handling

When a batch of design jobs partially fails:
- Collect results from completed jobs (do not discard them).
- Record failed job IDs and error messages in `design_summary.json`.
- If >50% of jobs succeeded, proceed to screening with available designs.
- If <50% succeeded, halt and report to user with failure analysis.
- Never silently drop failed jobs from the count.

### Failure Escalation

| Failure Type | Action |
|-------------|--------|
| Single job failure | Retry up to 2x, then mark failed and continue |
| Batch >50% failure | Halt pipeline, report to user with diagnosis |
| Agent crash | Log in delegation_log.json, resume via `/by:resume` |
| MCP server unreachable | Wait 30s, retry 2x, then halt with provider status |
| Campaign state corruption | Report to user, do not attempt auto-repair |

---

## Agent Teams and Model Profiles

For complex campaigns, deploy specialized agent teams. Each agent has scoped MCP server
access and disallowed tools for safety.

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
|-------|---------|--------------------|--------|
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
2. Task(by-research) — target analysis (turn 2)
3. Review research report (turn 3)
4. Task(by-campaign) — plan campaign (turn 4)
5. Review plan, present to user (turn 5)
6. User approves plan (turn 6)
7. Task(by-design) — submit and monitor jobs (turn 7)
8. Review design results (turn 8)
9. Task(by-screening) — screen all designs (turn 9)
10. Review screening results (turn 10)
11. Task(by-verifier) — independent verification (turn 11)
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

---

## Quick Reference: Campaign Launch Checklist

0. Run `/by:plan-campaign` to capture preferences (`campaign_context.json`).
1. Classify target difficulty (well-studied / moderate / novel).
2. Select engine (PXDesign or BoltzGen) and protocol.
3. Choose campaign tier (preview first, then escalate).
4. Identify hotspot residues from epitope analysis.
5. Run `estimate_campaign.py` to get cost on local / HPC / Tamarind.
6. Confirm compute provider from `.by/config.json` (default `local`).
7. Create campaign directory structure.
8. Initialize `campaign_log.json` with `draft` state.
9. Launch run via `Task(by-design, ...)` and confirm transition to `designing`.
10. Monitor with `track_progress.py`, `/by:watch`, and `/by:status`.
11. On completion, run full screening battery and aggregate results.
12. Assess campaign health against baselines ([health-metrics.md](references/health-metrics.md)).
13. Present ranked candidates or recommend follow-up actions.

---

## References

**Detailed documentation:**
- [references/state-machine.md](references/state-machine.md) — Campaign state diagram, transitions, checkpoint file schemas, ASCII diagram, recovery rules.
- [references/cost-model.md](references/cost-model.md) — Cost estimation by deployment target (local GPU, HPC RunPod, Tamarind). Per-engine wall-clock + per-modality scaling.
- [references/health-metrics.md](references/health-metrics.md) — Mid-run health assessment: pass-rate trajectory, score distribution shifts, compute failure rate, abort criteria.

**Scripts:**
- [scripts/estimate_campaign.py](scripts/estimate_campaign.py) — CLI: target difficulty + modality + budget → cost estimate per compute target with confidence intervals.
- [scripts/track_progress.py](scripts/track_progress.py) — CLI: read campaign checkpoint JSON → progress dashboard (submitted, scored, PASSed; ETA; spend).

**Related skills (cross-link):**
- `by-research` — produces research outputs consumed at campaign start.
- `by-design`, `by-screening`, `by-verifier` — execute the phases this skill orchestrates.
- `by-deploy-compute` — HPC setup details (do not re-document them here).
- `by-knowledge` — pre/post-campaign learning system integration.

**License:** This skill and its scripts are part of the BY project. All dependencies
(Python stdlib, pyyaml, pandas) permit commercial use.
