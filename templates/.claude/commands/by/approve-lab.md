---
name: by:approve-lab
description: Approve lab submission to Adaptyv Bio (triple-gated)
---

# /approve-lab — Approve Lab Submission (Triple-Gated)

Initiate the lab submission approval process for sending designs to
Adaptyv Bio for experimental validation. This is a GATED operation
requiring explicit confirmation.

## Instructions

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command:
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| by-lab | opus | opus | sonnet |

### Step 1: Pre-flight checks

Verify before proceeding:
- An active campaign exists with completed screening
- At least 1 design has PASS status in screening results
- Environment has Adaptyv API key configured
- Campaign state is at RANKING phase or later

If any check fails, report the issue and stop. Do NOT proceed.

### Step 2: Show submission summary

Display what will be submitted:
- Campaign ID and target name
- Number of designs to submit (PASS status only)
- Top designs with scores (ipSAE, ipTM, p_bind)
- Estimated cost and turnaround time
- Adaptyv Bio endpoint being used

### Step 3: Require explicit confirmation

Ask the user to type **CONFIRM** to proceed.

If the user does not type CONFIRM, abort with:
"Lab submission cancelled. No data was sent."

### Step 4: Write approval file (Layer 3)

```bash
cat > .by/campaigns/$CAMPAIGN_ID/lab/approval.json << EOF
{
  "approved": true,
  "approved_by": "user",
  "approved_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "ttl_minutes": 5,
  "campaign_id": "$CAMPAIGN_ID",
  "design_count": $DESIGN_COUNT
}
EOF
```

### Step 5: Update campaign state (Layer 2)

Set `labApproved: true` in `state.json`.

### Step 6: Spawn by-lab agent

Delegate to a **by-lab** agent (model per profile table above):

> Submit approved designs from `{campaign_dir}` to Adaptyv Bio.
> Use the MCP confirmation code from the adaptyv server (Layer 1).
> Verify approval.json exists and TTL has not expired (5 minutes).
> Verify campaignState.labApproved is true.
> Log all submission details to `{campaign_dir}/logs/lab_submission.log`.

### Step 7: Report outcome

Show submission confirmation or failure details.
Include order ID and expected turnaround if successful.

**CRITICAL: NEVER bypass any of the three approval layers.**
