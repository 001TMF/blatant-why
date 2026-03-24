---
name: proteus:load
description: Load a protein target and analyze it for design
argument-hint: "<target name or PDB/UniProt ID>"
---

# /load — Load and Analyze a Protein Target

Load a protein target by name, PDB ID, or UniProt accession and run
initial research analysis to prepare for a design campaign.

## Instructions

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .proteus/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command:
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| proteus-research | opus | sonnet | sonnet |

### Step 1: Parse input

Determine the input type:
- **PDB ID**: 4-character alphanumeric (e.g., `1ABC`, `7XYZ`)
- **UniProt accession**: alphanumeric with pattern like `P12345` or `Q9UHD2`
- **Free text**: treat as a target name or description for search

### Step 2: Create campaign directory

```bash
CAMPAIGN_ID="campaign_$(date +%Y%m%d_%H%M%S)"
mkdir -p .proteus/campaigns/$CAMPAIGN_ID/{designs,screening,logs,research}
echo ".proteus/campaigns/$CAMPAIGN_ID" > .proteus/active_campaign
```

Initialize `state.json` with phase=RESEARCH, round=1, target info.

### Step 3: Spawn proteus-research agent

Delegate to a **proteus-research** agent (model per profile table above):

> Analyze target: `{user_argument}`
>
> Tasks:
> 1. Resolve the target to a PDB structure and UniProt entry
> 2. Identify chains, domains, and key binding interfaces
> 3. Search SAbDab for existing antibodies against this target
> 4. Identify known epitopes and druggable sites
> 5. Assess target difficulty (structured/disordered, glycosylation, flexibility)
> 6. Recommend design strategy: binder vs antibody vs nanobody
> 7. Suggest initial parameters (scaffold, CDR lengths, seed count)
>
> Write analysis to `{campaign_dir}/research/target_analysis.json`.
> Write human-readable summary to `{campaign_dir}/research/summary.md`.

### Step 4: Review research output

Verify the agent produced:
- Valid target_analysis.json with required fields
- A clear design strategy recommendation
- Reasonable parameter suggestions

### Step 5: Report to user

Display:
- Target name and identifiers (PDB, UniProt)
- Key structural features
- Design strategy recommendation
- Suggested next step (usually: review analysis, then start design)
- Campaign ID for reference
