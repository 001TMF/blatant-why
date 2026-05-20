# Campaign State Machine

This reference defines every state a BY campaign can occupy, the legal transitions
between them, and the artifact each state must produce on disk. The state machine
is the contract between the campaign-manager skill and every sub-agent it
dispatches (`by-research`, `by-design`, `by-screening`, `by-verifier`, `by-lab`).

Resume logic depends on this contract: when `/by:resume` runs, it reads the latest
checkpoint file and dispatches the next agent in the happy path. If checkpoints
are missing or malformed, resume cannot succeed.

---

## State Diagram

```
              ┌─────────┐
              │  draft  │  (campaign_id assigned, parameters captured)
              └────┬────┘
                   │ plan written
                   ▼
            ┌─────────────┐
            │ configured  │  (plan approved by user)
            └──────┬──────┘
                   │ /by:approve
                   ▼
              ┌─────────┐         ┌────────┐
        ┌────►│ planned │────────►│ failed │◄────┐
        │     └────┬────┘         └────┬───┘     │
        │          │ launch             │ retry  │
        │          ▼                    │        │
        │    ┌──────────┐               │        │
        │    │designing │───────────────┘        │
        │    └────┬─────┘                        │
        │         │ designs produced             │
        │         ▼                              │
        │    ┌──────────┐                        │
        │    │screening │────────────────────────┤
        │    └────┬─────┘                        │
        │         │ scores written               │
        │         ▼                              │
        │    ┌────────┐                          │
        │    │ ranked │──────────────────────────┘
        │    └────┬───┘
        │         │ user requests iteration
        │         ▼
        │    ┌──────────┐
        └────┤ iterated │
             └────┬─────┘
                  │ lab gate passed (triple-gated)
                  ▼
           ┌──────────────┐
           │ lab_pending  │
           └──────┬───────┘
                  │ submission confirmed
                  ▼
          ┌────────────────┐
          │ lab_submitted  │
          └──────┬─────────┘
                 │ results returned
                 ▼
          ┌───────────────┐
          │ lab_complete  │
          └──────┬────────┘
                 │
                 ▼
            ┌────────┐
            │ closed │
            └────────┘
```

---

## States and Triggers

| State | Entered When | Exit Trigger | Next States |
|-------|--------------|--------------|-------------|
| `draft` | Campaign created via `/by:plan-campaign` | User confirms parameters | `configured` |
| `configured` | `campaign_plan.md` written, user approves | Plan checker passes | `planned`, `debating`, `designing` |
| `debating` | Hypothesis-debate strategy selection in flight | Strategy chosen | `planned`, `designing`, `failed` |
| `planned` | Plan checker confirmed; compute config bound | `Task(by-design)` dispatched | `designing`, `failed` |
| `designing` | Design job(s) submitted | Designs returned (≥1 success) | `screening`, `failed` |
| `screening` | Designs handed to `by-screening` | All designs scored | `ranked`, `failed` |
| `ranked` | Composite scores computed, diversity clustered | User chooses next action | `lab_pending`, `designing` (iterate), `closed` |
| `iterated` | Follow-up round triggered | New `designing` started | `designing`, `closed` |
| `lab_pending` | Triple-gated lab approval initiated | `mcp__by-adaptyv__adaptyv_confirm_submission` returns code | `lab_submitted`, `failed` |
| `lab_submitted` | Adaptyv accepted batch | Lab results returned | `lab_complete`, `failed` |
| `lab_complete` | Wet-lab data integrated | Decision: iterate or close | `iterated`, `closed`, `failed` |
| `failed` | Any phase encountered unrecoverable error | User decides path | `draft`, `closed` |
| `closed` | Final state; campaign archived | — | (terminal) |

The full transition table is enforced by `src/proteus_cli/campaign/state.py`
(`VALID_TRANSITIONS`). Agents that attempt illegal transitions must abort and
log the violation.

---

## Required Artifacts by State

Each state has a **required artifact contract**. The artifact MUST exist on disk
before the state transition is recorded in `campaign_log.json`.

| State | Required Artifact | Path (relative to campaign dir) | Writer |
|-------|-------------------|----------------------------------|--------|
| `draft` | `campaign_context.json` | — | `by-campaign` |
| `configured` | `campaign_plan.md` | — | `by-campaign` |
| `planned` | `cost_estimate.json` | — | `by-campaign` |
| `designing` | `design_jobs.json` (job ids + provider) | `run_NNN/` | `by-design` |
| `screening` | `screening_input.json` (designs to score) | `run_NNN/scores/` | `by-design` |
| `ranked` | `ranked_results.csv`, `aggregated_results.csv` | — | `by-screening` |
| `lab_pending` | `lab/approval.json`, MCP confirmation code | `lab/` | `by-lab` |
| `lab_submitted` | `lab/submission_receipt.json` | `lab/` | `by-lab` |
| `lab_complete` | `lab/results.csv` | `lab/` | `by-lab` |

Missing artifacts trigger compensation under [saga rules](#saga-compensation).

---

## Checkpoint File Format

Checkpoints live under `campaigns/{target}/campaign_{date}_{NNN}/checkpoints/`.
The numeric prefix encodes phase order; resume reads the highest-numbered file.

### Canonical filenames

| File | Phase | Written by |
|------|-------|------------|
| `00_draft.json` | Draft | `by-campaign` |
| `01_configured.json` | Configured | `by-campaign` |
| `02_designing.json` | Designing | `by-design` |
| `03_design_complete.json` | Design complete | `by-design` |
| `04_screening.json` | Screening start | `by-screening` |
| `05_screening_complete.json` | Screening complete | `by-screening` |
| `06_ranking.json` | Ranked | `by-screening` |
| `07_complete.json` | Complete | `by-campaign` |

### Schema (shared across all checkpoints)

```json
{
  "campaign_id": "pdl1_20260520_001",
  "phase": "designing",
  "phase_index": 2,
  "written_at": "2026-05-20T10:00:00Z",
  "agent_to_dispatch": "by-design",
  "writer_agent": "by-design",
  "writer_model": "sonnet",
  "previous_phase": "configured",
  "campaign_dir": "campaigns/pdl1/campaign_20260520_001",
  "state_snapshot": {
    "target": {"name": "PD-L1", "pdb": "7S4S"},
    "tool": "boltzgen",
    "protocol": "nanobody-anything",
    "tier": "standard",
    "compute_provider": "local",
    "rounds": [
      {
        "round_id": 1,
        "status": "running",
        "runs": [{"run_id": "run_001", "scaffold": "caplacizumab", "status": "running"}]
      }
    ]
  },
  "phase_specific": {
    "job_ids": ["job_abc123", "job_def456"],
    "batch_id": "batch_xyz",
    "provider": "local",
    "engine": "boltzgen"
  },
  "next_action": "Poll job status; on completion write 03_design_complete.json",
  "expected_next_artifact": "checkpoints/03_design_complete.json"
}
```

### Phase-specific payload

Each checkpoint extends the base schema with a `phase_specific` block.

| Phase | `phase_specific` keys |
|-------|-----------------------|
| `00_draft` | `target`, `parameters` |
| `01_configured` | `approved_plan_path`, `user_confirmation_at` |
| `02_designing` | `job_ids`, `batch_id`, `provider`, `engine` |
| `03_design_complete` | `designs_produced`, `results_path`, `provenance` |
| `04_screening` | `designs_to_screen`, `screening_started_at` |
| `05_screening_complete` | `passed`, `failed`, `top_ipsae`, `top_iptm`, `pass_rate` |
| `06_ranking` | `ranked_results_path`, `diversity_clusters`, `composite_top_score` |
| `07_complete` | `final_summary_path`, `knowledge_stored` |

---

## Resume Algorithm

1. Locate campaign directory:
   - Prefer the active campaign in `.by/active_campaign.txt`.
   - Fall back to the most recently modified directory under `campaigns/`.
2. List files in `checkpoints/`, sort lexically (numeric prefix → order).
3. Read the latest checkpoint into memory.
4. Validate the schema (campaign_id, phase, agent_to_dispatch all present).
5. Confirm the expected artifact for the latest phase exists. If missing,
   apply [saga compensation](#saga-compensation).
6. Present the resume plan to the user (phase, agent, expected duration).
7. On confirmation, dispatch `agent_to_dispatch` via `Task()` and pass
   the checkpoint payload as context.
8. The dispatched agent must skip any sub-step whose output already exists
   on disk (idempotency requirement).

---

## Saga Compensation

When a phase fails partially, apply these rules. The campaign-manager skill
chooses the compensation; the dispatched agent executes it.

| Phase | Partial Failure Mode | Compensation Action |
|-------|----------------------|---------------------|
| Designing | Some HPC/Tamarind jobs failed; >50% succeeded | Proceed to screening with successful designs; record failed job IDs in `design_summary.json` |
| Designing | <50% succeeded | Halt; report; offer retry for failed jobs only |
| Designing | Compute timeout | Resubmit timed-out job IDs to the same provider |
| Screening | Some designs fail to score | Skip failed, screen rest, report gap in `screening_results.json` |
| Screening | Zero designs PASS | Transition to `failed`; auto-diagnose; present recovery options |
| Ranking | Too few candidates (<5) | Warn user; present with caveats; do NOT auto-iterate |
| Lab | MCP confirmation code expires (5-min TTL) | Re-request approval; never auto-bypass |

---

## Recovery

Missing or corrupt checkpoints are the most common failure mode. Recovery steps:

1. **Missing latest checkpoint, expected artifact exists:**
   - The writer agent crashed after producing artifact but before writing the checkpoint.
   - Reconstruct the checkpoint from the artifact and `campaign_log.json`. Mark `recovered_at`.

2. **Latest checkpoint exists, expected artifact missing:**
   - The writer wrote the checkpoint pre-flight. Treat the phase as not started.
   - Re-dispatch the writer agent with the checkpoint context.

3. **Checkpoint schema invalid:**
   - Do NOT attempt auto-repair. Surface to user with the malformed file path.
   - Offer two paths: (a) manually edit and `/by:resume`, or (b) reset to last valid checkpoint.

4. **Checkpoint numeric prefix mismatch (e.g., `2_designing.json` instead of `02_designing.json`):**
   - Rename to canonical form. Resume sorts lexically; non-zero-padded prefixes break order.

5. **Two checkpoints with the same prefix:**
   - Read both. The later `written_at` wins. Move the older to `checkpoints/archive/`.

---

## Anti-Patterns

- ❌ Writing the checkpoint BEFORE the artifact exists — leads to resume picking up nothing.
- ❌ Skipping checkpoints on "small" transitions — every state change writes one.
- ❌ Overwriting prior checkpoints in-place — append new file with next prefix instead.
- ❌ Hardcoding `phase_index` outside the canonical sequence — drift breaks resume order.
- ❌ Silently mutating `state_snapshot` without recording in `campaign_log.json.history`.
