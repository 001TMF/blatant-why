---
name: by:screen
description: Run full screening battery on designs
argument-hint: "[designs_dir or campaign_id]"
---

# /screen — Run Screening Battery

Run the full BY screening battery on a set of designs.

## Instructions

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command:
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| by-screening | opus | sonnet | haiku |

### Step 1: Resolve input

If argument is a directory path, use it directly as the designs source.
If argument is a campaign ID, look up `$CAMPAIGN_DIR/designs/`.
If no argument, use the active campaign from `.by/active_campaign`.

Fail with a clear message if no designs are found.

### Step 2: Inventory designs

Count PDB/CIF files in the designs directory. Report:
- Number of design files found
- Design method (from metadata if available)

### Step 3: Spawn by-screening agent

Delegate to a **by-screening** agent (model per profile table above) with instructions:

> Run the full screening battery on designs in `{designs_dir}`.
> Apply these filters in order:
>
> **Structure quality**: ipTM > 0.5, pLDDT > 70, RMSD < 3.5A
> **Custom scores**: ipSAE (compute via `score_ipsae` screening MCP tool), p_bind threshold
> **Liability scan**: NG/NS deamidation, DG isomerization, Met oxidation, free Cys, NXS/T glycosylation
> **Developability**: TAP guidelines, net charge, hydrophobic fraction, CDR length limits
> **Composition**: AA fractions, hydrophobic patch detection (DBSCAN)
>
> Write results to `{campaign_dir}/screening/results.json`.
> Write per-design reports to `{campaign_dir}/screening/reports/`.

### Step 4: Review screening output

After the agent completes, verify:
- results.json exists and is valid JSON
- Every input design has a corresponding screening result
- Pass/fail counts are reasonable (not 100% pass or 100% fail)

### Step 5: Report summary

Show a screening summary table:
- Total designs screened
- Passed / failed per filter stage
- Top 5 designs by composite score
- Any liability flags to investigate
