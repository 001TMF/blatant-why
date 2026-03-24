# BY Init Redesign — Design Specification

## Overview

Replace the buggy Ink/React TUI harness with a Ruflo-pattern npm init package. Claude Code becomes the native frontend. `npx by init` generates the complete protein design environment: MCP servers, skills, agents, commands, hooks, CLAUDE.md, and a ChromaDB-backed learning system.

## Distribution

- **Package**: `npx by init` (npm, TypeScript CLI)
- **Pattern**: Ruflo-style file generation into current directory
- **Frontend**: Claude Code native (no custom TUI)
- **Prereqs**: `uv` (for MCP servers), `node` >= 18 (for hooks)

## What `npx by init` Generates

```
.claude/
  settings.json            # MCP servers, permissions, hooks
  settings.local.json      # API keys (gitignored)
  agents/
    by-research.md
    by-design.md
    by-screening.md
    by-campaign.md
    by-knowledge.md
    by-verifier.md
    by-plan-checker.md
    by-environment.md
    by-lab.md
  skills/
    boltzgen/SKILL.md
    protenix/SKILL.md
    pxdesign/SKILL.md
    by-scoring/SKILL.md
    by-screening/SKILL.md
    by-design-workflow/SKILL.md
    by-epitope-analysis/SKILL.md
    by-database/SKILL.md
    by-campaign-manager/SKILL.md
    by-research/SKILL.md
    by-failure-diagnosis/SKILL.md
    by-campaign-optimizer/SKILL.md
    by-hypothesis-debate/SKILL.md
    by-knowledge/SKILL.md
  commands/by/
    watch.md
    status.md
    screen.md
    results.md
    load.md
    approve-lab.md
    set-profile.md
    setup.md
  hooks/
    hooks.json
  scripts/
    env-loader.js
    statusline.js
    safety-gate.js
    campaign-tracker.js
mcp_servers/
  pdb.py
  uniprot.py
  sabdab.py
  screening.py
  campaign.py
  research.py
  cloud.py               # Tamarind + SSH remote unified
  local_compute.py
  adaptyv.py
  knowledge.py            # ChromaDB + sentence-transformers
.by/
  config.json
  environment.json
  campaigns/
  knowledge.db            # ChromaDB persistent store
CLAUDE.md
.gitignore                # Appends: settings.local.json, .by/knowledge.db
```

## Init Flow

1. Check prereqs (`uv`, Python >= 3.11)
2. Default preset is `--full` (all components)
3. Prompt for API keys (TAMARIND_API_KEY, ADAPTYV_API_KEY) — skippable, writes to settings.local.json
4. Copy all files from npm package source
5. Generate settings.json with absolute MCP server paths
6. Generate CLAUDE.md from template
7. Verify: `uv run --script mcp_servers/pdb.py --help`
8. Print: "Run `claude` to start designing proteins"

## MCP Servers (10)

All PEP 723 single-file Python scripts. Each declares deps inline. Run with `uv run --script`.

| Server | Tools | Dependencies |
|--------|-------|-------------|
| pdb | pdb_search, pdb_fetch_structure, pdb_get_chains, pdb_interface_residues, pdb_download | mcp, httpx |
| uniprot | uniprot_search, uniprot_fetch_protein, uniprot_get_domains, uniprot_get_variants | mcp, httpx |
| sabdab | sabdab_search_by_antigen, sabdab_search_antibodies, sabdab_get_structure, sabdab_cdr_sequences | mcp, httpx |
| screening | screen_liabilities, screen_developability, screen_net_charge, score_ipsae, screen_composite, interpret_scores | mcp |
| campaign | campaign_create, campaign_get, campaign_add_round, campaign_update_round, campaign_get_cost_estimate, campaign_get_summary, campaign_submit_round, campaign_advance_round, campaign_get_pipeline, campaign_log_decision | mcp |
| research | research_get_target_info, research_search_prior_art, research_analyze_known_binders, research_find_similar_targets | mcp, httpx |
| cloud | cloud_list_providers, cloud_submit_job, cloud_submit_batch, cloud_get_status, cloud_get_batch_status, cloud_wait_batch, cloud_get_results | mcp, httpx, paramiko |
| local_compute | local_run_tool, local_list_tools, local_check_gpu | mcp |
| adaptyv | adaptyv_estimate_cost, adaptyv_prepare_submission, adaptyv_confirm_submission, adaptyv_get_experiment_status, adaptyv_get_results | mcp, httpx |
| knowledge | knowledge_store_campaign, knowledge_query_similar, knowledge_scaffold_rankings, knowledge_store_failure, knowledge_get_recommendations, knowledge_consolidate | mcp, chromadb, sentence-transformers |

## Agents (9)

Markdown files in `.claude/agents/`. No model field — model resolved at spawn time via profile lookup.

| Agent | Role | disallowedTools |
|-------|------|-----------------|
| by-research | Target analysis, literature, prior art, epitope mapping | cloud_submit_job, adaptyv_* |
| by-design | Generate designs via available compute | adaptyv_* |
| by-screening | Score, filter, rank designs | cloud_submit_job, adaptyv_* |
| by-campaign | Plan campaigns, manage state, cost estimates | adaptyv_confirm_submission |
| by-knowledge | Query/update learning system | cloud_submit_job, adaptyv_* |
| by-verifier | Quality gates: ipSAE>0.5, pLDDT>70, screening completeness | cloud_submit_job, adaptyv_* |
| by-plan-checker | Campaign plan review: fold validation, cost, parameters | cloud_submit_job, adaptyv_* |
| by-environment | Discover tools, GPU, SSH, API keys. Write environment.json | adaptyv_* |
| by-lab | Adaptyv Bio submission (triple-gated) | cloud_submit_job |

## Model Profiles

Stored in `.by/config.json` as `model_profile`. Switch with `/by:set-profile`.

| Agent | quality | balanced (default) | budget |
|-------|---------|-------------------|--------|
| by-research | opus | sonnet | sonnet |
| by-design | opus | sonnet | sonnet |
| by-screening | sonnet | sonnet | haiku |
| by-campaign | opus | opus | sonnet |
| by-knowledge | sonnet | haiku | haiku |
| by-verifier | sonnet | sonnet | sonnet |
| by-plan-checker | sonnet | sonnet | haiku |
| by-environment | sonnet | sonnet | haiku |
| by-lab | opus | opus | sonnet |

## Continuous Learning System

ChromaDB embedded in the knowledge MCP server. Sentence-transformers for real embeddings (all-MiniLM-L6-v2, 80MB, local).

### Collections
- **campaigns**: target, modality, parameters, outcomes, hit rates, best scores
- **scaffolds**: scaffold performance by target class, success rates
- **targets**: target characteristics, epitope topology, fold quality
- **failures**: what went wrong, why, how to avoid
- **user_preferences**: modality preference, detail level, compute preference

### ReasoningBank Pipeline (from Ruflo)
1. **Retrieve**: MMR (Maximal Marginal Relevance) for diverse top-K results
2. **Judge**: Quality scoring — hit rate, best ipSAE, screening pass rate
3. **Distill**: Extract reusable patterns — "scaffold X + small epitopes = high success"
4. **Consolidate**: Dedup (>0.95 similarity), prune (>30 days, <5 uses), merge

### Knowledge Graph
- Nodes: targets, scaffolds, epitopes, campaigns
- Edges: used_in, similar_to, outperformed, failed_against
- PageRank for relevance weighting
- Queried via `knowledge_get_recommendations`

### Session Sync
- PostToolUse hook detects campaign completion → triggers embedding
- SessionStart: top-K relevant context loaded into agent prompt
- Bidirectional MEMORY.md sync: high-confidence learnings written to Claude Code native memory

## Cloud Compute

### Tier 1: Tamarind Bio (default)
- Tier-aware: free (10/month, sequential), standard (100, 3 concurrent), pro (500, 10 concurrent), enterprise (unlimited)
- Campaign planner checks remaining quota before submitting
- Batch submission respects concurrent limits, queues overflow

### Tier 2: SSH Remote (Lambda.ai, RunPod, own cluster)
- `by-environment` SSHs in, discovers installed tools
- `cloud_submit_job` wraps: upload inputs → SSH exec → download results
- Configured in `.by/config.json` under `compute.ssh_hosts`

### Tier 3: Local GPU
- Auto-detected by `by-environment`
- `local_run_tool` runs tools via subprocess
- No network needed

### Batch Pipeline
```
campaign_submit_round  → submits all jobs for a round
cloud_submit_batch     → respects concurrent limit, queues rest
cloud_wait_batch       → polls until complete
campaign_advance_round → triggers next round when current completes
campaign_get_pipeline  → full view: rounds, jobs, status, ETA
```

Budget awareness: planner calculates total jobs vs remaining quota. Suggests optimizations if over budget.

## Hooks (4)

| Hook | Event | Function |
|------|-------|----------|
| env-loader.js | SessionStart | Load .env, detect providers, write to statusline |
| statusline.js | PostToolUse | `BY \| Tamarind (Pro, 477 left) \| campaign: pd-l1 \| round 2/3` |
| safety-gate.js | PreToolUse | Block adaptyv_confirm_submission without lab-approval.json |
| campaign-tracker.js | PostToolUse | Detect campaign completion, trigger knowledge embedding |

## CLAUDE.md Template

Generated from existing harness CLAUDE.md + agent.ts system prompt:
- Identity, communication style
- Tool priority (MCP first, WebSearch last)
- Scoring hierarchy (ipSAE primary, composite formula)
- Campaign workflow (research → plan → approve → design → screen → rank)
- Fold validation requirement
- Environment awareness (read environment.json)
- Learning (read knowledge before planning, cite prior campaigns)
- Safety gates (lab submission requires /by:approve-lab)
- Modality auto-detection (VHH/scFv/de novo)

## Commands (8)

| Command | Function |
|---------|----------|
| /by:watch | Live pipeline progress for running campaign |
| /by:status | Current campaign status summary |
| /by:screen | Run full screening battery on designs |
| /by:results | Show ranked design results table |
| /by:load | Load target from PDB/UniProt, analyze structure |
| /by:approve-lab | Triple-gated lab submission approval |
| /by:set-profile | Switch model profile (quality/balanced/budget) |
| /by:setup | Run by-environment agent to discover/update tools |

## Config Schema

`.by/config.json`:
```json
{
  "model_profile": "balanced",
  "compute": {
    "default_provider": "tamarind",
    "ssh_hosts": [],
    "local_gpu": false
  },
  "workflow": {
    "auto_research": true,
    "auto_screen": true,
    "fold_validation": true
  },
  "safety": {
    "require_plan_approval": true,
    "require_lab_approval": true
  }
}
```

## Migration

- Delete `harness/` directory entirely (Ink TUI, components, hooks, app.tsx, index.ts)
- Content from harness/CLAUDE.md → CLAUDE.md template in npm package
- Content from harness/test_5scenarios.mjs → adapted test suite for init + native Claude Code
- MCP servers: add PEP 723 headers to existing files, consolidate tamarind+local into cloud+local
- Skills: already exist in `.claude/skills/`, copy as-is
