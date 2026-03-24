---
name: by:watch
description: Live pipeline progress for a running design campaign
---

# /watch — Live Pipeline Progress

Display real-time progress for the currently active design campaign.

## Instructions

This command does NOT spawn agents. Read campaign state directly and render progress.

### Step 1: Load campaign state

```bash
CAMPAIGN_DIR=$(cat .by/active_campaign 2>/dev/null || echo "")
```

If no active campaign, report "No active campaign. Run /by:load to start one."

### Step 2: Read pipeline state

Read the following files from `$CAMPAIGN_DIR/`:
- `state.json` — current phase, round, timestamps
- `pipeline.json` — stage definitions and completion status
- `designs/` — count completed design files
- `screening/` — count screened results

### Step 3: Render pipeline stages

Display a pipeline diagram with these stages and their status:

| Stage | Key | Status Values |
|-------|-----|---------------|
| Target Analysis | research | pending / complete |
| Cost Estimate | cost | pending / complete |
| Design Generation | design | pending / running / complete |
| Screening Battery | screening | pending / running / complete |
| Ranking | ranking | pending / complete |
| Lab Submission | lab | pending / approved / submitted |

Use status indicators:
- `[====]` complete
- `[==>..]` running (show % if available)
- `[....]` pending

### Step 4: Show live stats

Display below the pipeline:
- **Designs generated**: X / Y target
- **Designs screened**: X / Y
- **Current provider**: Tamarind / Local
- **Elapsed time**: from state.json start timestamp
- **Estimated remaining**: based on throughput rate

### Step 5: Tail recent logs

Show last 10 lines from `$CAMPAIGN_DIR/logs/pipeline.log` if it exists.

Report the rendered progress view to the user.
