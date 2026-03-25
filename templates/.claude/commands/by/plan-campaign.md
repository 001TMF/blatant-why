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

Model lookup for research agents (spawned via Task):
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| researchers (x4) | opus | sonnet | haiku |
| synthesizer (x1) | opus | sonnet | sonnet |

### Step 1: Parse target input

Determine the input type from the user's argument:
- **PDB ID**: 4-character alphanumeric (e.g., `1ABC`, `7XYZ`)
- **UniProt accession**: alphanumeric with pattern like `P12345` or `Q9UHD2`
- **Free text**: treat as a target name or description for search

Record the parsed target identifier for use in Step 2.

### Step 2: Quick target lookup (MUST use Agent tool — keeps MCP calls hidden)

You MUST use the Agent tool to research the target. This is NOT optional. When you call MCP tools directly, Claude Code shows raw JSON to the user which looks terrible. The Agent tool runs in background and returns only the summary.

**DO THIS:**
```
Agent(
  prompt="Research the protein target '[target]'.

  1. Call mcp__by-uniprot__uniprot_search with query '[target] human' to get accession, name, length
  2. Call mcp__by-pdb__pdb_search with query '[target]' to get PDB structures
  3. Call mcp__by-sabdab__sabdab_search_by_antigen with antigen_name '[target]' for known binders

  Return ONLY this exact format (no JSON, no tool output, just this text):
  Target: [full name] ([organism]) — [length] aa | UniProt: [accession]
  Structures: [N] PDB entries (best: [PDB ID] at [resolution]Å)
  Known binders: [N] antibodies/nanobodies in SAbDab
  ",
  description="Research [target]"
)
```

**DO NOT call mcp__by-uniprot__*, mcp__by-pdb__*, or mcp__by-sabdab__* directly in the main session for this step.** Always use the Agent tool so the raw JSON stays hidden.

After the Agent returns, display the banner with the summary:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► PLAN-CAMPAIGN: [target name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Agent's 3-line summary here]
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

**Downstream consumption:** All research agents read `campaign_context.json` when it exists:
- **by-structure-researcher** uses PDB ID and UniProt ID from context for focused search.
- **by-sequence-researcher** uses UniProt ID and organism from context.
- **by-prior-art-researcher** uses target name and modality preference to focus landscape analysis.
- **by-epitope-researcher** respects `epitope.known` and `epitope.residues` if specified.
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

#### Step 6a: Spawn 4 parallel research agents via Task()

Spawn all four researchers **simultaneously** (do NOT wait for one to finish before starting the next). This is the GSD-style parallel research pattern — all four agents query independent data sources in parallel for maximum speed.

```
# All four run in parallel — spawn them in the same message
structure_result = Task(
  agent="by-structure-researcher",
  prompt="Research target structures for '{target_name}'. Campaign dir: {campaign_dir}. PDB ID: {pdb_id or 'auto'}. UniProt: {uniprot_id or 'auto'}. Write target_structures.json to the campaign dir. Return a one-line summary.",
  model=MODEL_PROFILE_AGENT
)

sequence_result = Task(
  agent="by-sequence-researcher",
  prompt="Research target sequence for '{target_name}'. Campaign dir: {campaign_dir}. UniProt: {uniprot_id or 'auto'}. PDB: {pdb_id or 'auto'}. Write target_sequence.json to the campaign dir. Return a one-line summary.",
  model=MODEL_PROFILE_AGENT
)

prior_art_result = Task(
  agent="by-prior-art-researcher",
  prompt="Research prior art for '{target_name}'. Campaign dir: {campaign_dir}. UniProt: {uniprot_id or 'auto'}. Write prior_art.json to the campaign dir. Return a one-line summary.",
  model=MODEL_PROFILE_AGENT
)

epitope_result = Task(
  agent="by-epitope-researcher",
  prompt="Analyze epitope landscape for '{target_name}'. Campaign dir: {campaign_dir}. PDB: {pdb_id or 'auto'}. UniProt: {uniprot_id or 'auto'}. Epitope preference: {epitope_pref or 'structure-derived'}. Write epitope_analysis.json to the campaign dir. Return a one-line summary.",
  model=MODEL_PROFILE_AGENT
)
```

Show progress while researchers are running:
```
| Phase         | Status     | Time   | Details                |
|---------------|------------|--------|------------------------|
| Structure     | ◆ Active   | —      | Querying PDB...        |
| Sequence      | ◆ Active   | —      | Querying UniProt...    |
| Prior Art     | ◆ Active   | —      | Querying SAbDab...     |
| Epitope       | ◆ Active   | —      | Analyzing surfaces...  |
| Synthesizer   | ○ Pending  | —      |                        |
| Design        | ○ Pending  | —      |                        |
| Screen        | ○ Pending  | —      |                        |
```

#### Step 6b: Wait for all 4 researchers to complete

After all four return, show the updated progress with their summaries:
```
| Phase         | Status     | Time   | Details                           |
|---------------|------------|--------|-----------------------------------|
| Structure     | ✓ Complete | {Xs}   | {structure_result summary}        |
| Sequence      | ✓ Complete | {Xs}   | {sequence_result summary}         |
| Prior Art     | ✓ Complete | {Xs}   | {prior_art_result summary}        |
| Epitope       | ✓ Complete | {Xs}   | {epitope_result summary}          |
| Synthesizer   | ◆ Active   | —      | Compiling target report...        |
| Design        | ○ Pending  | —      |                                   |
| Screen        | ○ Pending  | —      |                                   |
```

If any researcher fails, log the error and continue — the synthesizer handles missing inputs gracefully.

#### Step 6c: Spawn synthesizer to compile target_report.json

The synthesizer reads all four research outputs, cross-validates, and produces the unified report:

```
synthesizer_result = Task(
  agent="by-research-synthesizer",
  prompt="Synthesize research outputs for campaign at {campaign_dir}. Read target_structures.json, target_sequence.json, prior_art.json, and epitope_analysis.json. Cross-validate, assess druggability, identify risks, and write target_report.json and research_report.md. Return a one-line summary.",
  model=MODEL_PROFILE_SYNTHESIZER
)
```

After the synthesizer completes, write the research checkpoint (the synthesizer agent writes this too, but write it here as a safety net in case the synthesizer was interrupted before reaching that step):

```bash
mkdir -p {campaign_dir}/checkpoints
```

Write `{campaign_dir}/checkpoints/01_research_complete.json`:
```json
{
  "checkpoint": "research_complete",
  "timestamp": "<current ISO timestamp>",
  "files_produced": ["target_structures.json", "target_sequence.json", "prior_art.json", "epitope_analysis.json", "target_report.json", "research_report.md"],
  "next_phase": "campaign_planning"
}
```

Only include files in `files_produced` that actually exist in the campaign directory.

#### Step 6d: Build campaign plan from synthesized research

After the synthesizer completes:
- Read `{campaign_dir}/target_report.json`
- Spawn `by-campaign` via Task() to build `campaign_plan.json` from the synthesized research
- Present the campaign plan to the user for final confirmation

#### Step 6e: Present research summary and plan to user

Show the synthesizer's research summary, then the campaign plan table. Ask for user approval before proceeding to the design phase.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► RESEARCH COMPLETE: {target_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Display key findings from research_report.md]
[Display campaign plan from campaign_plan.json]

Ready to proceed with design? Say 'approve' to start compute.
```

#### Step 6f: Continue pipeline (on plan approval)

After user approves the campaign plan:
   - Spawn `by-design` via Task() — submits compute jobs, writes design_summary.json
   - Spawn `by-screening` via Task() — scores all designs, writes ranked_results.json
   - Spawn `by-verifier` via Task() — quality check, writes verification_report.json
   - Present final ranked results using Display Patterns

2. Each sub-agent call should:
   - Use the model from the active profile (`.by/config.json`)
   - Pass the campaign directory path
   - Pass the input file path
   - Receive a short summary string back (NOT raw JSON)

3. Between each phase, show an updated progress table:
```
| Phase         | Status     | Time   | Details                           |
|---------------|------------|--------|-----------------------------------|
| Structure     | ✓ Complete | 12s    | 45 PDB hits, best 5JDR at 1.8A   |
| Sequence      | ✓ Complete | 8s     | 290 aa, 4 glyc sites, druggable   |
| Prior Art     | ✓ Complete | 15s    | 42 binders, 3 approved drugs      |
| Epitope       | ✓ Complete | 18s    | 2 sites, best 0.85 druggability   |
| Synthesizer   | ✓ Complete | 5s     | Druggability 0.89, VHH recommended|
| Design        | ◆ Active   | —      | Spawning agent...                 |
| Screen        | ○ Pending  | —      |                                   |
| Rank          | ○ Pending  | —      |                                   |
```

### Research Output Files

The parallel research system produces these files in `{campaign_dir}/`:

| File | Agent | Description |
|------|-------|-------------|
| `target_structures.json` | by-structure-researcher | PDB structures, chains, interfaces |
| `target_sequence.json` | by-sequence-researcher | UniProt sequence, domains, PTMs, variants |
| `prior_art.json` | by-prior-art-researcher | SAbDab binders, literature, landscape |
| `epitope_analysis.json` | by-epitope-researcher | Druggable sites, hotspots, scores |
| `target_report.json` | by-research-synthesizer | Unified report (machine-readable) |
| `research_report.md` | by-research-synthesizer | Unified report (human-readable) |
