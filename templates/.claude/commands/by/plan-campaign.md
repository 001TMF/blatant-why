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

### Step 2: Quick target lookup (automated, no questions yet)

Use MCP research tools to get basic target information:

1. If PDB ID provided: `pdb_fetch_structure` to get name, organism, chains.
2. If UniProt ID provided: `uniprot_fetch_protein` to get name, organism, length, function.
3. If free text: `uniprot_search` then `pdb_search` to resolve to identifiers.
4. `sabdab_search_by_antigen` to check for known antibodies/nanobodies.

Present a 3-line target summary:
```
Target: [name] ([organism])
Structures: [N] PDB entries (best resolution: [X.X]A)
Known binders: [N] antibodies/nanobodies in SAbDab
```

### Step 3: Adaptive discussion

Ask questions **in a single message** as a numbered list. The user answers all at once.

**Full question set (ask 2-5 depending on what is already known):**

1. **Modality**: "What format? (1) VHH nanobody (2) scFv antibody (3) De novo binder -- or I'll default to VHH"
2. **Epitope knowledge**: "Do you have a known epitope or binding site? If yes, provide residue numbers or description. If no, I'll identify candidates from structure analysis."
3. **Compute budget**: "Compute tier? (1) Preview ~500 designs (2) Standard ~5,000 (3) Production ~20,000 -- or specify a number"
4. **Scaffold preferences**: "Scaffold preference? For VHH: caplacizumab (stable) or ozoralizumab (diverse) or both. For Fab: adalimumab or tezepelumab. Or 'default' for recommended set."
5. **Success criteria**: "What matters most? (1) Maximum hit rate (2) Diverse candidates for panel (3) Highest confidence scores (4) All of the above"

**Adaptive rules -- skip questions when answers are already provided:**

- If the user's initial message specifies modality (e.g., "design nanobodies against PD-L1"), skip question 1. Note the detected modality.
- If the user mentions specific residues or epitopes (e.g., "target the RBD ACE2-binding face"), skip question 2.
- If the user says "quick", "preview", or "just a quick test", skip question 3 and default to Preview tier.
- If the user gives enough context to infer scaffold (e.g., names a specific scaffold), skip question 4.
- **Minimum**: always ask at least 2 questions.
- **Maximum**: 5 questions.
- If the user gives terse answers ("1, no, 2, default, 4"), parse the numbers against the question order.

**Present the questions as a compact numbered list with clear defaults.** The entire exchange should take a single back-and-forth.

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
