---
name: by:results
description: Show ranked design results with scores
argument-hint: "[campaign_id]"
---

# /results — Ranked Design Results

Display screened and ranked designs with full score breakdown.

## Instructions

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command:
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| by-verifier | opus | sonnet | sonnet |

### Step 1: Resolve campaign

If argument provided, look up campaign by ID in `.by/campaigns/`.
Otherwise, use the active campaign from `.by/active_campaign`.

Fail if no campaign found or no screening results exist.

### Step 2: Load results

Read `{campaign_dir}/screening/results.json` for the full scored design list.
Read `{campaign_dir}/state.json` for campaign metadata.

### Step 3: Spawn by-verifier agent

Delegate to a **by-verifier** agent (model per profile table above):

> Validate the screening results in `{campaign_dir}/screening/results.json`.
> Check for:
> - Score consistency (ipSAE and ipTM should correlate)
> - Outlier detection (flag designs with unusual score combinations)
> - Duplicate or near-duplicate designs (by sequence similarity)
> - Missing scores (any design with incomplete scoring)
>
> Return a validation report with any flags or warnings.

### Step 4: Review verification

Check the verifier's output. If critical issues are found, warn the user
before displaying results.

### Step 5: Render results table

Display designs ranked by composite score, descending:

```
Rank  Design ID       ipSAE   ipTM   pLDDT  p_bind  Liabilities  Status
----  --------------  ------  -----  -----  ------  -----------  ------
1     design_042      0.87    0.92   85.3   0.94    none         PASS
2     design_017      0.84    0.89   82.1   0.91    NG@H3        WARN
...
```

Columns: Rank, Design ID, ipSAE, ipTM, pLDDT, p_bind, Liabilities, Status.

### Step 6: Show summary stats

Below the table, show:
- Total designs: X passed, Y warned, Z failed
- Score ranges (min/max/mean for ipSAE, ipTM, pLDDT)
- Diversity: number of unique sequence clusters
- Recommendation: top N designs for lab submission
