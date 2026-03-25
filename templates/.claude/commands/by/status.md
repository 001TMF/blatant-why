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

Display a summary block:

```
Campaign:   {name}
Phase:      {RESEARCH | COST | DESIGN | SCREENING | RANKING | LAB}
Round:      {N}
Created:    {timestamp}
Provider:   {Tamarind Bio | Local GPU}

Designs:    {generated} generated, {screened} screened, {passed} passed
Cost:       ~${estimated_cost} ({seeds} seeds x {designs_per_seed} designs)

Environment:
  proteus-fold:  {version or "not found"}
  proteus-prot:  {version or "not found"}
  boltzgen:      {version or "not found"}
  GPU:           {name or "none detected"}
  Tamarind API:  {configured | missing}
```

### Step 4: Show warnings

Flag any issues:
- Missing API keys for the selected provider
- Tools not found on expected paths
- Campaign stalled (no progress in >30 min)
- Designs awaiting screening

Report the rendered status to the user.
