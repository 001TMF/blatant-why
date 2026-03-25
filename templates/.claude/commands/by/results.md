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
| by-diversity | sonnet | sonnet | haiku |

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

### Step 3b: Spawn by-diversity agent

Delegate to a **by-diversity** agent (model per profile table above) in parallel with the verifier:

> Analyze the diversity of screened candidates in `{campaign_dir}/screening/results.json`.
> Perform:
> - Sequence clustering at 80%, 90%, 95% identity thresholds
> - Pareto front analysis (ipSAE vs ipTM)
> - Scaffold balance check
> - Recommend a maximally diverse panel from the top candidates
>
> Return a diversity report with cluster counts, redundancy rates, and a diverse panel recommendation.

### Step 4: Review verification

Check the verifier's and diversity agent's output. If critical issues are found, warn the user
before displaying results.

### Step 5: Render results table

Use the **Ranked Results Table** display pattern. Format the output exactly as shown:

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► RESULTS: {campaign_name} — {N} candidates ranked
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 #  Design       Composite  ipSAE   ipTM   pLDDT  Liabilities   Verdict
─── ──────────── ────────── ─────── ────── ────── ───────────── ──────────
 1  {design_id}  {score}    {val}   {val}  {val}  {N} crit      {verdict}
 2  ...          ...        ...     ...    ...    ...           ...
```

Verdict values: `✓ LAB-READY` (composite >= 0.75), `◆ FOLLOW-UP` (0.60-0.75), `✗ NOT VIABLE` (< 0.60).

Below the table, include **Score Context** with score bars for the top candidate:

```markdown
## Score Context
ipSAE  {value}  {bar}  {label}  ({interpretation})
ipTM   {value}  {bar}  {label}  ({interpretation})
pLDDT  {value}  {bar}  {label}  ({interpretation})
```

Score bars: 10 blocks, `█` filled proportionally, `░` for empty. Labels: EXCELLENT/STRONG/GOOD/MODERATE/WEAK per the scoring skill thresholds.

### Step 6: Show summary and next steps

```markdown
## Summary
✓ {N} lab-ready candidates | ◆ {N} needs follow-up | ✗ {N} not viable

## Next Steps
1. {Primary recommendation based on results}
2. {Secondary action}
3. {Tertiary action}
```

Include diversity information from the by-diversity agent:
- Sequence clusters, redundancy rate, scaffold balance
- Diverse panel recommendation

End with a **Next Up** block if lab-ready candidates exist:

```markdown
──────────────────────────────────────────────────────

## ▶ Next Up

**Lab submission** — {N} candidates ready for Adaptyv Bio

`/by:approve-lab`

<sub>Triple safety gate: MCP confirmation + campaign state + approval file</sub>

──────────────────────────────────────────────────────
```
