---
name: by:resume
description: Resume an interrupted campaign from the last checkpoint
---

# /resume -- Resume Campaign from Last Checkpoint

Resume an interrupted or failed campaign from its most recent checkpoint.

## Instructions

This command reads checkpoint files to determine exactly where the campaign
stopped, then dispatches the appropriate agent to continue from that point.

### Step 1: Find the campaign directory

```bash
CAMPAIGN_DIR=$(cat .by/active_campaign 2>/dev/null || echo "")
```

If no active campaign is set, scan `.by/campaigns/` for the most recently
modified campaign directory. If multiple campaigns exist, list them and ask the
user which one to resume.

### Step 2: Read checkpoint files

Scan `$CAMPAIGN_DIR/checkpoints/` for checkpoint files. They are named by phase
with numeric prefix for ordering:

```
checkpoints/
  00_draft.json           -- campaign created
  01_configured.json      -- plan approved, parameters set
  02_designing.json       -- jobs submitted (includes job_ids)
  03_design_complete.json -- results received
  04_screening.json       -- screening started
  05_screening_complete.json -- scores computed
  06_ranking.json         -- composite scores computed
  07_complete.json        -- campaign done
```

Identify the **latest** checkpoint file (highest numeric prefix). This is the
resume point.

### Step 3: Read checkpoint contents

Each checkpoint file contains:

```json
{
  "phase": "designing",
  "timestamp": "2026-03-24T15:00:00Z",
  "campaign_id": "pd-l1-20260324-150000",
  "completed_actions": ["research", "plan_approval", "job_submission"],
  "pending_actions": ["monitor_jobs", "collect_results"],
  "job_ids": ["by_boltzgen_abc123"],
  "partial_results": {
    "designs_received": 5,
    "designs_expected": 20,
    "designs_scored": 3
  },
  "next_action": "poll_job_status",
  "agent_to_dispatch": "by-design",
  "resume_context": "Jobs submitted to Tamarind. 5/20 designs returned before interruption."
}
```

### Step 4: Build resume plan

Present the resume plan to the user:

```
------------------------------------------------------
 BY > RESUME CAMPAIGN
------------------------------------------------------

**Campaign:** {campaign_id}
**Last checkpoint:** {phase} ({timestamp})
**Interrupted at:** {resume_context}

**Completed phases:**
{for each completed_action: "  * {action}"}

**Resume action:** {next_action}
**Agent:** {agent_to_dispatch}

**Partial results (if any):**
- Designs received: {designs_received}/{designs_expected}
- Designs scored: {designs_scored}

------------------------------------------------------
> Type "go" to resume, or describe adjustments
------------------------------------------------------
```

### Step 5: Handle resume scenarios

Based on the latest checkpoint phase, dispatch the correct agent:

| Last Checkpoint | Resume Action | Agent |
|-----------------|---------------|-------|
| `00_draft` | Restart from research | by-research |
| `01_configured` | Re-submit design jobs | by-design |
| `02_designing` | Poll job status, collect partial results | by-design |
| `03_design_complete` | Start screening | by-screening |
| `04_screening` | Continue screening remaining designs | by-screening |
| `05_screening_complete` | Compute rankings | by-screening |
| `06_ranking` | Present final results | orchestrator |
| `07_complete` | Campaign already complete -- show results | orchestrator |

### Step 6: Handle partial failures (Saga compensation)

If the checkpoint includes `failed_jobs` or `partial_success` flags:

1. **Some jobs failed, some succeeded:**
   Report: "X/Y jobs completed successfully. Z jobs failed."
   Offer options:
   - **Resume with partial results** -- screen what succeeded, skip failures
   - **Retry failed jobs** -- resubmit only the failed job IDs
   - **Restart design phase** -- resubmit all jobs with same parameters

2. **Screening partial completion:**
   Report: "X/Y designs screened before interruption."
   Action: Screen only the unscreened designs, merge with existing scores.

3. **Zero candidates after screening:**
   Trigger `screen_diagnose_failures` automatically.
   Present diagnosis and recommend parameter adjustments.

### Step 7: Dispatch agent

On user confirmation ("go", "yes", "resume"):
- Pass the checkpoint data as context to the dispatched agent
- Include `partial_results` so the agent knows what work is already done
- Set `resume_mode: true` in the agent dispatch so it skips completed steps

### Step 2b: Fallback — infer phase from output files

If no checkpoint files are found in `$CAMPAIGN_DIR/checkpoints/`, scan the
campaign directory for known output files and infer the completed phase:

| File present | Inferred state | Resume from |
|---|---|---|
| `ranked_results.json` | Screening complete | Verification / final results |
| `design_summary.json` | Design complete | Screening |
| `campaign_plan.json` | Planning complete | Design |
| `target_report.json` | Research complete | Campaign planning |
| None of the above | Campaign not started | Research (or suggest new campaign) |

Check files in **reverse order** (most advanced phase first). Use the first
match as the resume point. When using this fallback, warn the user:

```
⚠ No checkpoint files found — inferring state from output files.
  Detected: {file} → resuming from {phase}
```

Then continue with Step 3 (read checkpoint contents) by constructing a
synthetic checkpoint from the detected file. Read the detected file's
`timestamp` field if available; otherwise use the file's modification time.

### Error Handling

- **No checkpoints found and no output files:** Report "No checkpoint files or
  output files found. Campaign may not have started. Use `/by:status` to check
  campaign state, or start a new campaign."
- **Corrupted checkpoint:** If checkpoint JSON fails to parse, report the error
  and fall back to the previous valid checkpoint.
- **Stale checkpoint (>24h old):** Warn the user that the checkpoint may be
  outdated. Ask whether to resume anyway or restart.
- **Tamarind job expired:** If the checkpoint references job IDs that are no
  longer available on Tamarind, report this and offer to resubmit.
