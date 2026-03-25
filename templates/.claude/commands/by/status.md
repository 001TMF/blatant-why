---
name: by:status
description: Show current campaign status summary
---

# /status — Campaign Status Summary

Show a concise summary of the current campaign and compute environment.

## Instructions

This command does NOT spawn agents. Read state files directly.

### Step 1: Load environment

Read `.by/environment.json` for:
- Available compute providers (Tamarind, Local GPU)
- Detected tools and versions
- API key status (present/missing, never show values)

### Step 2: Load campaign state

Read `.by/active_campaign` to find the campaign directory, then read:
- `state.json` — campaign name, phase, round, created timestamp
- `designs/` — count design output files
- `screening/results.json` — screening pass/fail counts if exists

If no active campaign, show environment info only and note "No active campaign."

### Step 3: Render status summary

Use the **Campaign Status Banner** display pattern. Format the output exactly as shown:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► CAMPAIGN: {campaign_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Phase    | Status     | Time   | Details              |
|----------|------------|--------|----------------------|
| Research | {status}   | {time} | {details}            |
| Plan     | {status}   | {time} | {details}            |
| Design   | {status}   | {time} | {details}            |
| Screen   | {status}   | {time} | {details}            |
| Rank     | {status}   | {time} | {details}            |
```

Status values: `✓ Complete`, `◆ Active`, `○ Pending`.
Time: elapsed time for completed/active phases, `—` for pending.
Details: key metrics for each phase (design count, screening pass rate, etc.).

Below the table, show provider and environment info:

```markdown
**Provider:** {Tamarind Bio | Local GPU}
**Environment:** proteus-fold {version} | proteus-prot {version} | boltzgen {version} | GPU: {name}
**Tamarind API:** {configured | missing}
```

If no active campaign, show environment info only with: `No active campaign. Run /by:load to start one.`

### Step 4: Show warnings

Flag any issues:
- Missing API keys for the selected provider
- Tools not found on expected paths
- Campaign stalled (no progress in >30 min)
- Designs awaiting screening

Report the rendered status to the user.
