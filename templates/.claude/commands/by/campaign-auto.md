---
name: by:campaign-auto
description: Full autonomous campaign — research, design, screen, rank with minimal interruption
argument-hint: "<target name or PDB/UniProt ID>"
---

# /campaign-auto — Autonomous Campaign Pipeline

Run a complete design campaign end-to-end with minimal user interaction.
Only stops for critical decisions (compute provider selection, cost approval).
Everything else runs automatically with smart defaults.

## Instructions

### Step 0: Read config

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

If `.by/config.json` does not exist, run the by-session skill first-run setup before continuing.

### Step 1: Parse target and auto-detect modality

Parse the user's input for target name/ID and any modality hints.
Apply the modality detection table from the by-design-workflow skill.
If ambiguous, default to VHH nanobody.

### Step 2: Silent research (Agent tool — NO raw output)

Use the Agent tool to research the target. Do NOT call MCP tools directly.

```
Agent(
  prompt="Research the protein target '[target]'. Call mcp__by-uniprot__uniprot_search, mcp__by-pdb__pdb_search, and mcp__by-sabdab__sabdab_search_by_antigen. Return ONLY: target name, organism, length, best PDB ID + resolution, known binder count. No JSON.",
  description="Research [target]"
)
```

### Step 3: Auto-configure campaign (smart defaults, no questions)

Use these defaults unless the user specified otherwise in their request:
- **Modality**: auto-detected from request text
- **Epitope**: structure-derived (automated)
- **Tier**: read from `.by/config.json` campaign_defaults.tier (or "standard")
- **Scaffolds**: modality defaults
- **Success criteria**: balanced

Write `campaign_context.json` automatically. Do NOT ask AskUserQuestion.

### Step 4: ONE confirmation — compute only

The ONLY question to ask the user:

```
AskUserQuestion(
  header: "Compute",
  question: "Ready to launch [N] designs on [provider]. Proceed?",
  options: [
    "Go" — Launch immediately,
    "Change provider" — Switch compute (local/Tamarind/SSH),
    "Adjust count" — Change number of designs
  ]
)
```

If "Change provider" — ask ONE follow-up about which provider, then proceed.
If "Adjust count" — ask ONE follow-up about the number, then proceed.
If "Go" — proceed immediately.

### Step 5: Full autonomous pipeline

Show the launch banner, then run everything without stopping:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► AUTO CAMPAIGN: {target_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Execute the full pipeline sequentially with Agent tool calls:

**5a. Parallel Research** (4 agents via Agent tool, run_in_background):
- by-structure-researcher
- by-sequence-researcher
- by-prior-art-researcher
- by-epitope-researcher

Wait for all 4, then spawn by-research-synthesizer.

**5b. Design** — spawn by-design agent with campaign_context.json + target_report.json
- For local GPU: launch with nohup, report ETA
- For Tamarind/SSH: submit and report job ID + ETA

**5c. Screen** — spawn by-screening agent with design_summary.json

**5d. Verify** — spawn by-verifier agent with ranked_results.json

**5e. Present results** — show ranked table using by-display skill format

Between each phase, update the progress table. Do NOT ask for approval between phases — this is full auto.

### Step 6: Final output

Present the ranked results and export FASTA if requested:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► CAMPAIGN COMPLETE: {target_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Ranked results table with verdicts]
[Score interpretation]
[Next steps]

FASTA exported to: {campaign_dir}/exports/top_10.fasta
```
