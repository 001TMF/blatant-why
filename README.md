<div align="center">

```
 ██████╗ ██╗   ██╗
 ██╔══██╗╚██╗ ██╔╝
 ██████╔╝ ╚████╔╝
 ██╔══██╗  ╚██╔╝
 ██████╔╝   ██║
 ╚═════╝    ╚═╝
```

**Protein design agent for Claude Code**

</div>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-%3E%3D18-339933.svg?logo=node.js&logoColor=white" alt="Node.js >= 18"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-%3E%3D3.11-3776AB.svg?logo=python&logoColor=white" alt="Python >= 3.11"></a>
  <a href="https://docs.anthropic.com/en/docs/claude-code"><img src="https://img.shields.io/badge/Claude_Code-SDK-cc785c.svg" alt="Claude Code SDK"></a>
  <img src="https://img.shields.io/badge/MCP_Servers-10-4CAF50.svg" alt="10 MCP Servers">
  <a href="https://github.com/001TMF/blatant-why/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

<p align="center">
  <code>npx by-design init</code> turns any directory into a protein design workstation.
  Claude Code becomes your biologics design agent with 10 MCP servers, 9 specialized agents,
  15 skills, and 8 slash commands -- ready to design antibodies, nanobodies, and de novo binders
  from target research through lab submission.
</p>

---

## Quick Start

```bash
npx by-design init
claude
# Then: "Research PD-L1 as a target for nanobody design"
```

That is the entire setup. `by-design init` generates all the files Claude Code needs -- agents, skills, commands, MCP servers, hooks, and a CLAUDE.md personality file. Open Claude Code in the same directory and you have a protein design workstation.

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Latest | The runtime. Install with `npm install -g @anthropic-ai/claude-code` |
| [uv](https://docs.astral.sh/uv/) | Latest | Runs Python MCP servers with inline dependencies. Install with `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python | >= 3.11 | Required by MCP servers. Install with `uv python install 3.11` if missing |
| Node.js | >= 18 | For the init CLI |

### First Session

After running `npx by-design init`, launch Claude Code and try one of these:

```
Research PD-L1 as a target for nanobody design
Design VHH nanobodies against TNF-alpha
Load 1TNF and analyze the trimer interface
```

Claude Code will use the MCP tools to query PDB, UniProt, and SAbDab, then present a structured target dossier with epitope analysis and a campaign plan.

---

## What It Does

BY (Blatant-Why) is an `npm init` package that generates the complete protein design environment for Claude Code. There is no custom TUI, no Electron app, no separate frontend. Claude Code **is** the frontend.

This follows the Ruflo pattern: generate `.claude/` configuration files, MCP server scripts, and a CLAUDE.md personality file into any project directory. Claude Code reads these on startup and becomes a specialized protein design agent.

### What Gets Generated

| Component | Count | Purpose |
|-----------|-------|---------|
| MCP servers | 10 | PDB, UniProt, SAbDab, screening, cloud compute, knowledge, campaign, research, adaptyv, local compute |
| Agents | 9 | Research, design, screening, campaign, knowledge, verifier, plan-checker, environment, lab |
| Skills | 15 | BoltzGen, Protenix, PXDesign, scoring, screening, epitope analysis, campaign management, research, and more |
| Slash commands | 8 | `/by:load`, `/by:screen`, `/by:results`, `/by:watch`, `/by:status`, `/by:approve-lab`, `/by:set-profile`, `/by:setup` |
| Hooks | 4 | Campaign tracking, environment loading, safety gates, status line |
| Learning system | 5 collections | ChromaDB + sentence-transformers, improves with every campaign |

---

## Architecture

BY uses the Ruflo pattern: `npx by-design init` generates static files, and Claude Code is the native frontend. No custom process runs alongside Claude Code -- it reads the generated `.claude/` directory, registers the MCP servers, and gains access to all agents, skills, and commands.

```
npx by-design init
       |
       v
  +-----------+     +-----------+     +------------------+
  | .claude/  |     | mcp_      |     | .by/             |
  | agents/   |     | servers/  |     | config.json      |
  | skills/   |     | 10 Python |     | campaigns/       |
  | commands/ |     | scripts   |     | knowledge.db     |
  | hooks/    |     | (PEP 723) |     | (ChromaDB)       |
  | scripts/  |     |           |     |                  |
  +-----------+     +-----------+     +------------------+
       |                 |                     |
       +--------+--------+---------------------+
                |
                v
         Claude Code
    (reads all on startup)
                |
       +--------+--------+
       |        |        |
       v        v        v
    Research  Design  Screening
    Agent     Agent   Agent      ... (9 agents total)
```

### What Gets Generated

```
your-project/
├── .claude/
│   ├── agents/              # 9 agent definitions (.md files)
│   │   ├── by-research.md
│   │   ├── by-design.md
│   │   ├── by-screening.md
│   │   ├── by-campaign.md
│   │   ├── by-knowledge.md
│   │   ├── by-verifier.md
│   │   ├── by-plan-checker.md
│   │   ├── by-environment.md
│   │   └── by-lab.md
│   ├── skills/              # 15 skill definitions
│   │   ├── boltzgen/        # BoltzGen CLI + protocols
│   │   ├── protenix/        # Protenix CLI + seeds
│   │   ├── pxdesign/        # PXDesign CLI + presets
│   │   └── by-*/       # 12 domain skills
│   ├── commands/by/    # 8 slash commands
│   ├── hooks/               # Hook definitions (hooks.json)
│   ├── scripts/             # Hook shell scripts
│   └── settings.json        # Auto-generated MCP server registrations
├── mcp_servers/             # 10 PEP 723 Python scripts
│   ├── pdb/server.py
│   ├── uniprot/server.py
│   ├── sabdab/server.py
│   ├── screening/server.py
│   ├── cloud/server.py
│   ├── knowledge/server.py
│   ├── campaign/server.py
│   ├── research/server.py
│   ├── adaptyv/server.py
│   └── local_compute/server.py
├── .by/
│   ├── config.json          # User preferences, model profile, compute settings
│   ├── campaigns/           # Campaign state data (JSONL)
│   └── knowledge.db/        # ChromaDB persistent storage
└── CLAUDE.md                # Agent personality and tool documentation
```

### PEP 723 MCP Servers

Every MCP server is a single Python file with inline dependency metadata (PEP 723). No virtualenvs, no requirements.txt, no setup steps. `uv run --script server.py` reads the dependencies from the script header and runs in an isolated environment:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx>=0.27",
# ]
# ///
```

Claude Code launches each server via `uv run --script mcp_servers/<name>/server.py` as configured in `.claude/settings.json`.

---

## MCP Servers

| Server | Key Tools | Description |
|--------|-----------|-------------|
| **pdb** | `pdb_search`, `pdb_fetch_structure`, `pdb_get_chains`, `pdb_interface_residues`, `pdb_download` | RCSB Protein Data Bank -- structure search and analysis |
| **uniprot** | `uniprot_search`, `uniprot_fetch_protein`, `uniprot_get_domains`, `uniprot_get_variants` | UniProt protein metadata, sequence, function, variants |
| **sabdab** | `sabdab_search_by_antigen`, `sabdab_search_antibodies`, `sabdab_get_structure`, `sabdab_cdr_sequences` | Structural Antibody Database -- existing binders and novelty checking |
| **screening** | `screen_liabilities`, `screen_developability`, `score_ipsae`, `screen_composite`, `screen_diversity`, `screen_diagnose_failures`, `screen_pareto_front`, `screen_naturalness`, `screen_shape_complementarity` | 13 screening and scoring tools |
| **cloud** | `cloud_list_providers`, `cloud_submit_job`, `cloud_submit_batch`, `cloud_get_status`, `cloud_wait_batch`, `cloud_get_results` | Unified compute: Tamarind API + SSH remote + local GPU |
| **knowledge** | `knowledge_query_similar`, `knowledge_scaffold_rankings`, `knowledge_get_recommendations`, `knowledge_store_campaign`, `knowledge_store_failure`, `knowledge_consolidate` | ChromaDB semantic memory -- learns across campaigns |
| **campaign** | `campaign_create`, `campaign_get`, `campaign_add_round`, `campaign_submit_round`, `campaign_advance_round`, `campaign_get_pipeline`, `campaign_log_decision`, `campaign_get_cost_estimate` | Campaign state machine, cost tracking, decision audit trail |
| **research** | `research_get_target_info`, `research_search_prior_art`, `research_analyze_known_binders`, `research_find_similar_targets` | Literature and prior art aggregation from PubMed, bioRxiv, PDB |
| **adaptyv** | `adaptyv_estimate_cost`, `adaptyv_prepare_submission`, `adaptyv_confirm_submission`, `adaptyv_get_experiment_status`, `adaptyv_get_results` | Adaptyv Bio wet-lab integration (triple-gated) |
| **local_compute** | `local_detect_tools`, `local_detect_gpu`, `local_run_boltzgen`, `local_run_pxdesign`, `local_run_protenix`, `ssh_run_job` | Local GPU and SSH remote compute execution |

---

## Agents

BY deploys 9 specialized agents. Each has scoped MCP server access and disallowed tools for safety isolation.

| Agent | Role | MCP Access | Disallowed |
|-------|------|------------|------------|
| **by-research** | Target analysis, literature review, epitope mapping | pdb, uniprot, sabdab, research, knowledge | cloud_submit_job, adaptyv_* |
| **by-design** | Generate designs via available compute providers | pdb, screening, cloud, campaign | adaptyv_* |
| **by-screening** | Score, filter, rank, diagnose designs | screening, campaign, knowledge | cloud_submit_job, adaptyv_* |
| **by-campaign** | Plan campaigns, manage state, track costs | campaign, cloud, knowledge | adaptyv_confirm_submission |
| **by-knowledge** | Query and update learning system | knowledge | cloud_submit_job, adaptyv_* |
| **by-verifier** | Quality gates: ipSAE > 0.5, pLDDT > 70, screening completeness | screening, campaign | cloud_submit_job, adaptyv_* |
| **by-plan-checker** | Campaign plan review: fold validation, cost, parameters | campaign, screening | cloud_submit_job, adaptyv_* |
| **by-environment** | Discover tools, GPU, SSH hosts, API keys. Write environment.json | local_compute | adaptyv_* |
| **by-lab** | Adaptyv Bio submission (triple-gated safety) | adaptyv | cloud_submit_job |

### Model Profiles

Agents resolve their model at spawn time based on the active profile in `.by/config.json`. Switch profiles with `/by:set-profile`.

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

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/by:load` | Load a target protein from PDB ID, UniProt ID, or name. Analyze structure and identify epitope hotspots. |
| `/by:screen` | Run the full screening battery on designs (liabilities, developability, structure, naturalness, diversity) |
| `/by:results` | Show ranked design results table with ipSAE, ipTM, pLDDT, composite scores |
| `/by:watch` | Live pipeline progress for running campaigns (stages, job counts, ETA) |
| `/by:status` | Current campaign status summary |
| `/by:approve-lab` | Triple-gated lab submission approval (Adaptyv Bio) |
| `/by:set-profile` | Switch model profile (quality / balanced / budget) |
| `/by:setup` | Run by-environment agent to discover and configure available compute |

---

## Cloud Compute

BY supports three compute backends. The unified cloud MCP server presents a single interface regardless of backend.

### Tamarind Bio (default)

Cloud compute platform with 200+ structural biology models. Free tier available (10 jobs/month) -- enough for preview campaigns. Set `TAMARIND_API_KEY` in your environment.

```bash
export TAMARIND_API_KEY=your-key-here  # Get at https://app.tamarind.bio
```

### SSH Remote

Run jobs on remote GPU servers via SSH (Lambda.ai, RunPod, your own cluster). Configure in `.by/config.json`:

```json
{
  "compute": {
    "ssh_hosts": [
      {
        "name": "gpu-server",
        "host": "gpu.example.com",
        "user": "researcher",
        "key": "~/.ssh/id_rsa",
        "tools_path": "/opt/by",
        "workspace": "/tmp/by"
      }
    ]
  }
}
```

### Local GPU

For power users with local tool installations. Set environment variables pointing to each tool:

```bash
export PROTEUS_FOLD_DIR=/path/to/Protenix       # Structure prediction
export PROTEUS_PROT_DIR=/path/to/PXDesign        # De novo binder design
export PROTEUS_AB_DIR=/path/to/boltzgen          # Antibody/nanobody design
```

BY auto-detects available providers on session start and selects the best available.

---

## Design Modalities

| Modality | Engine | Scaffolds | Use Case |
|----------|--------|-----------|----------|
| **VHH nanobody** | BoltzGen | 7 templates (caplacizumab, ozoralizumab, etc.) | Small, stable single-domain binders. Ideal for imaging, diagnostics, bispecifics. |
| **scFv antibody** | BoltzGen | 14 Fab templates (adalimumab, tezepelumab, etc.) | Traditional antibody variable fragments. Fab-to-scFv conversion via (G4S)3 linker. |
| **De novo binder** | PXDesign | None (fully generative) | Miniprotein binders with no immunoglobulin scaffold. 17--82% experimental hit rates. |

All modalities feed into the same screening pipeline and can be mixed within a single campaign.

### Campaign Tiers

| Tier | Designs/Scaffold | Compute Cost | Best For |
|------|-----------------|--------------|----------|
| **Preview** | 500 | ~$5 | Quick feasibility check |
| **Standard** | 5,000 | ~$35/scaffold | Well-studied targets |
| **Production** | 20,000 | ~$140/scaffold | Serious campaigns, multiple scaffolds |
| **Exploratory** | 50,000 | ~$350/scaffold | Novel targets, maximum diversity |

---

## Screening Pipeline

Every design passes through a multi-stage computational funnel:

```
Designs (BoltzGen / PXDesign)
    |
    v
Structure prediction (Protenix, multi-seed for antibodies)
    |
    v
Hard filters: ipTM > 0.5, ipSAE > 0.3, pLDDT > 70, RMSD < 5.0A
    |
    v
Liability scan: NG/NS deamidation, DG isomerization, Met oxidation, free Cys, glycosylation
    |
    v
Developability: net charge, CDR length, hydrophobic fraction, TAP guidelines
    |
    v
Naturalness: AbLang2 pseudo-perplexity, germline distance
    |
    v
Shape complementarity + diversity clustering
    |
    v
Cross-validation (multi-seed ipSAE, 20+ seeds)
    |
    v
Failure diagnosis (Mann-Whitney U tests on pass/fail split)
    |
    v
Pareto front (multi-objective: ipSAE vs diversity vs developability)
    |
    v
Top candidates --> Lab (Adaptyv Bio, triple-gated)
```

### Scoring Hierarchy

**Primary: ipSAE** (interface Predicted Structural Accuracy Error) -- open-source TM-align metric from DunbrackLab. Directional scoring: design-to-target, target-to-design, min(both). Range 0--1, higher is better.

**Secondary: ipTM** -- standard interface confidence metric.

**Composite**: `0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)`

---

## Learning System

BY includes a persistent learning system powered by ChromaDB and sentence-transformers (`all-MiniLM-L6-v2`). It stores and retrieves knowledge across campaigns via semantic search with Maximal Marginal Relevance (MMR) re-ranking.

### Five Collections

| Collection | Stores | Used For |
|------------|--------|----------|
| **campaigns** | Completed campaign summaries, parameters, outcomes | Finding similar past campaigns for a new target |
| **scaffolds** | Scaffold performance data by target class | Recommending best scaffolds based on historical success rates |
| **targets** | Target dossiers, epitope data, structural features | Recognizing studied targets, surfacing prior analysis |
| **failures** | Failed designs with root cause analysis | Avoiding known failure modes, adjusting parameters |
| **user_preferences** | User-specific settings, preferred workflows | Personalizing recommendations |

### How It Works

1. Before planning a campaign, the agent queries `knowledge_query_similar` to find prior evidence
2. Scaffold rankings from `knowledge_scaffold_rankings` inform template selection
3. Parameter recommendations from `knowledge_get_recommendations` tune campaign settings
4. After campaign completion, results are stored via `knowledge_store_campaign`
5. Failures are recorded via `knowledge_store_failure` to prevent repeating mistakes
6. Periodic consolidation via `knowledge_consolidate` deduplicates and prunes the database

The knowledge base persists in `.by/knowledge.db/` and carries forward across sessions and campaigns.

---

## Safety Gates

| Resource | Gate Level | Details |
|----------|-----------|---------|
| Research tools | **None** | PDB, UniProt, SAbDab, PubMed, knowledge -- freely available |
| Compute tools | **Plan approval** | `cloud_submit_job`, `cloud_submit_batch` require the user to approve a campaign plan first |
| Lab submission | **Triple-gated** | Adaptyv Bio requires three independent safety layers |

### Lab Submission Safety (Adaptyv Bio)

| Layer | Mechanism | What It Prevents |
|-------|-----------|------------------|
| **1. Command gate** | User must invoke `/by:approve-lab` | Agent cannot autonomously initiate submissions |
| **2. Confirmation code** | `adaptyv_prepare_submission` returns a one-time code (5-minute TTL) | Stale or replayed submissions |
| **3. Explicit confirm** | User types `CONFIRM` with the exact code to execute `adaptyv_confirm_submission` | Accidental approval |

`adaptyv_estimate_cost` is always safe to call -- it never triggers a submission.

---

## Campaign Workflow

```
1. RESEARCH          Autonomous. Query PDB, UniProt, SAbDab, literature.
       |             Present structured target dossier.
       v
2. PLAN              Parameter table: modality, scaffolds, tier, epitope,
       |             cost estimate, success criteria, go-no-go gates.
       v
3. APPROVAL          Wait for explicit user "yes" / "go".
       |             Never submit compute without approval.
       v
4. DESIGN            Submit jobs to cloud / SSH / local GPU.
       |             Monitor progress via /by:watch.
       v
5. SCREEN            Full screening battery on every design.
       |             Composite scoring and ranking.
       v
6. RESULTS           Ranked table with top candidates.
       |             Numbered next steps.
       v
7. LAB (optional)    Triple-gated Adaptyv Bio submission.
                     $119--215/variant, 2--4 week turnaround.
```

---

## Environment Variables

```bash
# Cloud compute (Tamarind Bio -- default)
# Free tier: 10 jobs/month. Get your key at https://app.tamarind.bio
TAMARIND_API_KEY=

# Cloud compute (Levitate Bio -- alternative, RFAntibody pipeline)
LEVITATE_CLIENT_ID=
LEVITATE_CLIENT_SECRET=

# Lab testing (Adaptyv Bio -- requires /by:approve-lab)
ADAPTYV_API_TOKEN=

# Local GPU (power users)
# PROTEUS_FOLD_DIR=/path/to/Protenix
# PROTEUS_PROT_DIR=/path/to/PXDesign
# PROTEUS_AB_DIR=/path/to/boltzgen

# SSH remote GPU
# PROTEUS_SSH_HOST=gpu-server.example.com
# PROTEUS_SSH_USER=researcher
# PROTEUS_SSH_KEY=~/.ssh/id_rsa
```

Only `TAMARIND_API_KEY` is needed to get started. The free tier is sufficient for preview campaigns.

---

## Project Structure

```
by-design/
├── src/init-cli/              # npm init CLI
│   ├── index.ts               # Entry point, flag parsing
│   ├── init.ts                # Prerequisite checks + orchestration
│   ├── templates.ts           # File copy + settings.json generation
│   ├── api-keys.ts            # API key prompts
│   └── verify.ts              # Post-init verification
├── templates/                 # Everything that gets generated into user projects
│   ├── .claude/
│   │   ├── agents/            # 9 agent definitions
│   │   ├── skills/            # 15 skill definitions with reference docs
│   │   ├── commands/by/  # 8 slash commands
│   │   ├── hooks/             # hooks.json
│   │   └── scripts/           # Hook shell scripts
│   ├── mcp_servers/           # 10 PEP 723 Python MCP servers
│   │   ├── pdb/server.py
│   │   ├── uniprot/server.py
│   │   ├── sabdab/server.py
│   │   ├── screening/server.py
│   │   ├── cloud/server.py
│   │   ├── knowledge/server.py
│   │   ├── campaign/server.py
│   │   ├── research/server.py
│   │   ├── adaptyv/server.py
│   │   └── local_compute/server.py
│   ├── .by/
│   │   ├── config.json        # Default settings
│   │   └── campaigns/         # Campaign data directory
│   └── CLAUDE.md              # Agent personality + full tool documentation
├── mcp_servers/               # Source MCP servers (development copies)
├── src/proteus_cli/           # Python scoring, screening, campaign modules
│   ├── scoring/               # ipSAE (DunbrackLab formula)
│   ├── screening/             # 9 screening modules
│   └── campaign/              # State machine, active learning, export
├── tests/                     # Test suite
├── docs/                      # Specs and plans
└── examples/                  # Campaign config examples
    ├── tnfa-vhh/              # TNF-alpha nanobody campaign
    ├── tnfa-vhh-local/        # Local GPU variant
    ├── tnfa-vhh-ssh/          # SSH remote variant
    └── pdl1-binder/           # PD-L1 de novo binder
```

---

## Configuration

Campaigns are defined in YAML:

```yaml
name: "tnfa_vhh_standard"
tier: "standard"

target:
  name: "TNF-alpha"
  pdb_id: "1TNF"
  chain_id: "A"
  uniprot_id: "P01375"

epitope:
  hotspot_residues: [75, 76, 77, 79, 81, 87, 88, 89, 90, 91, 92, 95, 96, 97]

design:
  tool: "boltzgen"
  modality: "vhh"
  scaffolds:
    - name: "caplacizumab"
      pdb: "7eow"
    - name: "ozoralizumab"
      pdb: "8z8v"
  designs_per_scaffold: 5000

screening:
  hard_filters:
    iptm_min: 0.5
    ipsae_min: 0.3
    plddt_min: 70
    rmsd_max: 5.0

compute:
  provider: "tamarind"
```

---

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run `pytest tests/` to verify Python
5. Run `npx tsc -p tsconfig.init.json --noEmit` to verify TypeScript
6. Open a pull request against `master`

Please open an issue first for major changes to discuss the approach.

---

## License

[MIT](LICENSE)

---

## Acknowledgments

- **[BoltzGen](https://github.com/jostorge/boltzgen)** (MIT) by Hannes Stark et al. -- stochastic optimal control for antibody design
- **[Protenix](https://github.com/bytedance/protenix)** by ByteDance -- AF3-class structure prediction (368M params)
- **[PXDesign](https://github.com/bytedance/pxdesign)** by ByteDance -- de novo protein binder design (17--82% hit rates)
- **[Tamarind Bio](https://tamarind.bio)** -- cloud compute platform with 200+ structural biology models
- **[Adaptyv Bio](https://www.adaptyvbio.com)** -- wet-lab antibody testing and validation
- **[DunbrackLab](https://dunbrack.fccc.edu/)** -- ipSAE formula (TM-align-inspired interface score from PAE matrices)
- **[ChromaDB](https://www.trychroma.com/)** -- vector database powering the learning system
- **[sentence-transformers](https://www.sbert.net/)** -- embedding model (all-MiniLM-L6-v2) for semantic search
- **[Claude Code SDK](https://docs.anthropic.com/en/docs/claude-code)** by Anthropic -- agent framework

## Citation

```bibtex
@software{by2026,
  title   = {BY (Blatant-Why): Protein Design Agent for Claude Code},
  author  = {Tristan Farmer},
  year    = {2026},
  url     = {https://github.com/001TMF/blatant-why},
  license = {MIT}
}
```
