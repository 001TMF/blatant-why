---
name: by:watch
description: Live pipeline progress for a running design campaign
---

# /watch — Pipeline Progress Snapshot

Display a ONE-TIME progress snapshot for the currently active design campaign. This command reads current state and renders it -- it does NOT continuously stream or poll. Run it again to refresh.

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

### Step 3: Render pipeline progress

Use the **Progress During Design** display pattern. Format the output as:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► WATCH — {run_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Provider:** {Tamarind Bio | Local GPU} | **Tool:** {BoltzGen | PXDesign} | **Elapsed:** {time}

  ✓ Input validation          {time}
  ✓ Backbone generation       {time}     {N}/{N} backbones
  ✓ Sequence design           {time}     {N}/{N} sequences
  ◆ Protenix refolding        {time}     {N}/{N} refolded {bar} {pct}%
  ○ ipSAE scoring             --
  ○ Liability screening       --
  ○ Composite ranking         --

**Designs generated:** {N} | **Scored so far:** {N} | **Best ipSAE:** {value}
```

Progress bar within stages: `████████░░ 75%` — 10 blocks, `█` filled proportionally, `░` for empty.

Status symbols per stage:
- `✓` — stage complete (show elapsed time and final count)
- `◆` — stage active (show elapsed time, progress count, and progress bar)
- `○` — stage pending (show `--`)

### Step 4: Tail recent log

Show last 50 lines from `$CAMPAIGN_DIR/logs/pipeline.log` if it exists. This is a ONE-TIME read (not a continuous tail). If the log file does not exist, skip this step.

### Step 5: Show refresh hint

End with:

```markdown
──────────────────────────────────────────────────────
<sub>This is a point-in-time snapshot. Run `/by:watch` again to refresh.</sub>
```

Report the rendered progress view to the user.
