---
name: by:plan-campaign
description: Pre-campaign discussion -- capture design preferences before launching
argument-hint: "<target name or PDB/UniProt ID>"
---

# /plan-campaign — Pre-Campaign Discussion

Capture design preferences through a focused discussion before launching a
campaign. This ensures the right modality, epitope strategy, compute tier,
scaffolds, and success criteria are locked in before any compute runs.

## Instructions

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command (runs in main session, no agent spawn):
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| main session | opus | sonnet | sonnet |

### Step 1: Parse target input

Determine the input type from the user's argument:
- **PDB ID**: 4-character alphanumeric (e.g., `1ABC`, `7XYZ`)
- **UniProt accession**: alphanumeric with pattern like `P12345` or `Q9UHD2`
- **Free text**: treat as a target name or description for search

Record the parsed target identifier for use in Step 2.

### Step 2: Quick target lookup (SILENT — no raw output to user)

Use a subagent (Task tool) to research the target in the background. The user should NOT see raw MCP tool responses.

```
Task(
  prompt="Research the target '[target]'. Call mcp__by-uniprot__uniprot_search, mcp__by-pdb__pdb_search, and mcp__by-sabdab__sabdab_search_by_antigen. Return a 3-line summary: target name/organism/length, PDB entry count with best resolution, and known binder count. Return ONLY the summary text, no JSON.",
  model="sonnet"
)
```

If Task tool is not available, call the MCP tools directly but do NOT display the raw JSON responses. Parse results silently and present only:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► PLAN-CAMPAIGN: [target name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Target: [name] ([organism]) — [length] aa
Structures: [N] PDB entries (best: [ID] at [X.X]Å)
Known binders: [N] in SAbDab
```

### Step 3: Adaptive discussion using AskUserQuestion

Use the **AskUserQuestion** tool for structured multiple-choice popups. Do NOT present questions as inline text — use the popup UI.

**Determine which questions to ask** based on what the user already provided in their initial request:
- If modality is stated (e.g., "de novo", "nanobody", "scFv"), skip modality question
- If epitope is stated, skip epitope question
- If compute tier is implied ("quick test", "production"), skip tier question
- **Minimum**: always ask at least 1 question via AskUserQuestion
- **Maximum**: 4 questions

**Use AskUserQuestion for each remaining question:**

For epitope (if not already specified):
```
AskUserQuestion(
  header: "Epitope",
  question: "Which binding surface on [target]?",
  options: [
    "Structure-derived (Recommended)" — Let analysis identify the most druggable surface,
    "[Known interface 1]" — [description based on PDB data],
    "[Known interface 2]" — [description based on PDB data],
    "Custom residues" — I'll provide specific residue numbers
  ]
)
```

For compute tier (if not already specified):
```
AskUserQuestion(
  header: "Compute",
  question: "How many designs to generate?",
  options: [
    "Preview (~1,000)" — Fast test, a few minutes,
    "Standard (~5,000) (Recommended)" — Good sampling,
    "Production (~20,000)" — Thorough coverage
  ]
)
```

For success criteria:
```
AskUserQuestion(
  header: "Ranking",
  question: "What matters most for the top 10?",
  options: [
    "Balanced (Recommended)" — Confidence + diversity + developability,
    "Maximum confidence" — Highest ipSAE/ipTM scores,
    "Diverse panel" — Structurally distinct candidates
  ]
)
```

### Step 4: Store answers as campaign_context.json

Create the campaign directory if it does not exist:

```bash
CAMPAIGN_ID="campaign_$(date +%Y%m%d_%H%M%S)"
mkdir -p .by/campaigns/$CAMPAIGN_ID
echo ".by/campaigns/$CAMPAIGN_ID" > .by/active_campaign
```

Write `campaign_context.json` to the campaign directory with this schema:

```json
{
  "target": {
    "name": "PD-L1",
    "pdb_id": "5JDS",
    "uniprot_id": "Q9NZQ7",
    "organism": "Homo sapiens"
  },
  "modality": "VHH",
  "epitope": {
    "known": false,
    "residues": [],
    "description": "To be determined from structure analysis"
  },
  "compute": {
    "tier": "standard",
    "designs_per_scaffold": 5000
  },
  "scaffolds": ["caplacizumab", "ozoralizumab"],
  "success_criteria": "balanced",
  "discussion_duration_seconds": 45,
  "timestamp": "2026-03-24T14:30:00Z"
}
```

**Field definitions:**

| Field | Type | Values | Default |
|-------|------|--------|---------|
| `modality` | string | `"VHH"`, `"scFv"`, `"de_novo"` | `"VHH"` |
| `epitope.known` | boolean | `true` / `false` | `false` |
| `epitope.residues` | array of int | residue numbers (label_seq_id) | `[]` |
| `compute.tier` | string | `"preview"`, `"standard"`, `"production"`, `"exploratory"` | `"standard"` |
| `compute.designs_per_scaffold` | int | 500 / 5000 / 20000 / custom | 5000 |
| `scaffolds` | array of string | scaffold names | modality defaults |
| `success_criteria` | string | `"hit_rate"`, `"diversity"`, `"confidence"`, `"balanced"` | `"balanced"` |

**Downstream consumption:** All agents read `campaign_context.json` when it exists:
- **by-research** focuses on user-specified epitope regions if `epitope.known` is true.
- **by-design** uses the specified modality, scaffolds, and compute tier.
- **by-screening** applies success criteria to weight composite scoring (e.g., diversity-weighted vs confidence-weighted ranking).

### Step 5: Confirm and hand off

Display a compact summary table of captured preferences:

```
Preference        | Value
------------------|--------------------------
Target            | PD-L1 (5JDS, Q9NZQ7)
Modality          | VHH nanobody
Epitope           | Structure-derived (unknown)
Compute tier      | Standard (~5,000/scaffold)
Scaffolds         | caplacizumab, ozoralizumab
Success criteria  | Balanced (hit rate + diversity + confidence)
```

Then say: **"Ready to launch. Say 'go' to start the full pipeline, or adjust any preference."**

**Important:** Do NOT spawn sub-agents for the discussion. This entire flow runs in the main session. The goal is a focused, under-3-minute exchange that produces `campaign_context.json` for all downstream agents to consume.

### Step 6: On user approval — launch the campaign pipeline

When the user says "go", "yes", "launch", or similar:

1. Show the campaign launch banner:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► LAUNCHING CAMPAIGN: {target_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

2. Follow the Agent Delegation (MANDATORY for campaigns) section in CLAUDE.md:
   - Spawn `by-research` via Task() — passes campaign_context.json path, writes target_report.json
   - Read target_report.json, build campaign_plan.json, present to user for final confirmation
   - Spawn `by-design` via Task() — submits compute jobs, writes design_summary.json
   - Spawn `by-screening` via Task() — scores all designs, writes ranked_results.json
   - Spawn `by-verifier` via Task() — quality check, writes verification_report.json
   - Present final ranked results using Display Patterns

3. Each sub-agent call should:
   - Use the model from the active profile (`.by/config.json`)
   - Pass the campaign directory path
   - Pass the input file path
   - Receive a short summary string back (NOT raw JSON)

4. Between each agent, show a progress update:
```
| Phase    | Status     | Time   | Details             |
|----------|------------|--------|---------------------|
| Research | ✓ Complete | 45s    | 3 PDB, 12 prior art |
| Design   | ◆ Active   | —      | Spawning agent...   |
| Screen   | ○ Pending  | —      |                     |
| Rank     | ○ Pending  | —      |                     |
```
