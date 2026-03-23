---
name: proteus-hypothesis-debate
description: Hypothesis-debate pattern for design strategy selection. Spawns competing strategy agents and uses adversarial ranking to select the best approach before committing GPU compute. Use when starting a new campaign, facing a novel target, or when multiple viable approaches exist.
---

# Hypothesis-Debate Skill

## When to Trigger
- Novel targets (0-1 PDB structures, no known binders)
- Contradictory research findings (CONTRADICTED confidence level)
- Multiple viable modalities (user hasn't specified VHH vs scFv vs de novo)
- User requests "explore options" or "compare approaches"
- Target difficulty rated "novel" or "exploratory"

## When to Skip
- Well-studied targets with clear best approach
- User specifies exact parameters
- Preview/quick test campaigns
- Iteration rounds (strategy already established)

## Protocol
1. Orchestrator spawns 3 hypothesis agents in parallel (via spawnTeam)
2. Each agent receives the same research but a different strategic directive
3. Each outputs a structured JSON strategy proposal
4. Orchestrator spawns 1 reflection agent sequentially
5. Reflection agent ranks, critiques, and selects winner
6. Winner's strategy becomes the campaign config
7. Decision is logged to decision_log.jsonl

## Output
The debate produces a concrete campaign config YAML ready for execution.
