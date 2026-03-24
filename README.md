<p align="center">
  <img src="assets/banner_compressed.png" alt="BY Design" width="700">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <a href="https://github.com/001TMF/blatant-why/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square" alt="PRs Welcome"></a>
  <img src="https://img.shields.io/badge/Claude_Code_SDK-0.2-blueviolet?style=flat-square" alt="Claude Code SDK">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=flat-square&logo=uv&logoColor=white" alt="uv">
  <img src="https://img.shields.io/badge/npm-package-CB3837?style=flat-square&logo=npm&logoColor=white" alt="npm">
</p>

<h3 align="center">Open-source protein design agent for Claude Code</h3>

<p align="center">
Some platforms charge thousands for AI-driven protein design using the same open-source tools — BoltzGen, Protenix, PXDesign. BY gives you direct access through Claude Code: a frontier AI agent designing proteins with no platform fees, no vendor lock-in, no artificial limitations.
</p>

<p align="center">
Use Tamarind Bio's free tier for cloud compute, bring your own GPU, or connect SSH remotes. Your tools, your models, your designs.
</p>

---

<p align="center">
  <img src="assets/by_timesaver.jpg" alt="Time comparison: traditional vs. agentic antibody design" width="500">
</p>
<p align="center"><sub>Source: trust us bro</sub></p>
<p align="center"><sub>(Interactive version: <a href="assets/blatant_why_time_parody_v4.html">assets/blatant_why_time_parody_v4.html</a>)</sub></p>

---

## Quick Start

```bash
npx blatant-why init
claude
> "Design VHH nanobodies against PD-L1"
```

That is it. `blatant-why init` generates everything Claude Code needs -- MCP servers, agents, skills, commands, hooks, and a CLAUDE.md personality file. Open Claude Code in the same directory and you have a protein design workstation.

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [uv](https://docs.astral.sh/uv/), Python >= 3.11, Node.js >= 18.

---

## Setup Guide

### API Keys

| Key | Required? | Where to get it | What it enables |
|-----|-----------|-----------------|-----------------|
| `ANTHROPIC_API_KEY` | Required | Via [Claude Code](https://docs.anthropic.com/en/docs/claude-code) subscription | Powers the AI agent |
| `TAMARIND_API_KEY` | Recommended | [tamarind.bio](https://tamarind.bio) (free account) | Cloud compute -- BoltzGen, Protenix, 200+ models. Free tier: 10 jobs/month |
| `ADAPTYV_API_TOKEN` | Optional | [adaptyvbio.com](https://www.adaptyvbio.com) | Lab testing submission (triple-gated) |

### Setting up your environment

After `npx blatant-why init`:

1. Copy `.env.example` to `.env`
2. Add your API keys:
   ```
   TAMARIND_API_KEY=your_key_here
   ```
3. For local GPU (optional):
   ```
   PROTEUS_FOLD_DIR=/path/to/Protenix
   PROTEUS_PROT_DIR=/path/to/PXDesign
   PROTEUS_AB_DIR=/path/to/boltzgen
   ```
4. For SSH remotes (optional):
   Add host configs to `.by/config.json`

### Compute Options

| Provider | Cost | Setup | Best for |
|----------|------|-------|----------|
| **Tamarind Bio** | Free tier: 10 jobs/month | Just add API key | Getting started, small campaigns |
| **Tamarind Paid** | Pay per job | Same API key | Production campaigns |
| **Local GPU** | Your hardware | Install tools + set env vars | Power users with GPUs |
| **SSH Remote** | Your infrastructure | Configure in `.by/config.json` | HPC clusters, Lambda.ai, RunPod |

---

## What It Does

Give it a target protein. It researches the target across PDB, UniProt, and SAbDab. It plans a design campaign. It submits compute jobs to Tamarind Bio (free tier, no GPU). It screens every design for structural quality, sequence liabilities, and developability. It ranks candidates by composite score. You get a table of lab-ready binders.

The whole pipeline runs inside Claude Code. No platform. No dashboard. No vendor lock-in.

---

## What Is Inside

- **11 MCP servers** -- biological databases, cloud compute, screening, campaign management, knowledge
- **16 agents** -- specialized sub-agents for research, design, screening, evaluation, and lab integration
- **14 skills** -- BoltzGen, Protenix, PXDesign, scoring, screening, epitope analysis, campaign management
- **11 slash commands** -- campaign control from the Claude Code prompt
- **JSON knowledge store** -- campaign memory that improves with every run
- **Tamarind Bio cloud compute** -- free tier, 200+ structural biology models (via Tamarind Bio API), no GPU required

<details>
<summary><strong>MCP Servers (11)</strong></summary>

| Server | Role |
|--------|------|
| `pdb` | Protein Data Bank queries |
| `uniprot` | UniProt protein annotation |
| `sabdab` | Structural Antibody Database |
| `by-screening` | Screening battery orchestration |
| `tamarind` | Tamarind Bio cloud compute |
| `by-cloud` | Cloud compute abstraction |
| `adaptyv` | Adaptyv Bio lab submission (gated) |
| `by-campaign` | Campaign state management |
| `by-research` | Literature and target research |
| `by-local` | Local GPU compute dispatch |
| `by-knowledge` | JSON-backed campaign knowledge store |

</details>

<details>
<summary><strong>Agents (16)</strong></summary>

| Agent | Role |
|-------|------|
| `by-research` | Target analysis, literature review, prior art |
| `by-design` | Generate designs via cloud or local pipelines |
| `by-screening` | Score, filter, rank candidates |
| `by-evaluator` | Structural evaluation and quality assessment |
| `by-visualization` | Structure and results visualization |
| `by-diversity` | Sequence and structural diversity selection |
| `by-campaign` | Campaign lifecycle orchestration |
| `by-knowledge` | Learning system and campaign memory |
| `by-verifier` | Output verification and sanity checks |
| `by-plan-checker` | Campaign plan validation |
| `by-environment` | Environment setup and dependency checks |
| `by-lab` | Adaptyv Bio lab submission (triple-gated) |
| `by-epitope` | Epitope analysis and mapping |
| `by-humanization` | Antibody humanization engineering |
| `by-liability-engineer` | Sequence liability detection and fixes |
| `by-formatter` | Output formatting and reporting |

</details>

<details>
<summary><strong>Skills (14)</strong></summary>

| Skill | Description |
|-------|-------------|
| `boltzgen` | BoltzGen antibody/nanobody generation |
| `protenix` | Protenix structure prediction |
| `pxdesign` | PXDesign de novo binder design |
| `by-scoring` | ipSAE + p_bind composite scoring |
| `by-screening` | Full screening battery |
| `by-epitope-analysis` | Epitope mapping and analysis |
| `by-campaign-manager` | Campaign state and lifecycle |
| `by-campaign-optimizer` | Active learning and iteration |
| `by-design-workflow` | End-to-end design pipeline |
| `by-research` | Target research and literature |
| `by-knowledge` | Campaign knowledge operations |
| `by-database` | Local results database |
| `by-failure-diagnosis` | Pipeline failure analysis |
| `by-hypothesis-debate` | Multi-agent hypothesis evaluation |

</details>

<details>
<summary><strong>Slash Commands (11)</strong></summary>

| Command | Action |
|---------|--------|
| `/by:load` | Load a campaign from file |
| `/by:screen` | Run screening battery on designs |
| `/by:results` | Display campaign results table |
| `/by:watch` | Live-watch running compute jobs |
| `/by:status` | Campaign status dashboard |
| `/by:approve-lab` | Approve Adaptyv Bio submission (gated) |
| `/by:set-profile` | Switch compute profile |
| `/by:setup` | Initialize environment and dependencies |
| `/by:plan-campaign` | Generate a detailed campaign plan for a loaded target |
| `/by:welcome` | Show welcome message and quick-start guide |
| `/by:resume` | Resume an interrupted or paused campaign |

</details>

<details>
<summary><strong>Repository Structure</strong></summary>

```
blatant-why/
├── assets/                  # Banner, diagrams, screenshots
├── campaigns/               # Campaign output directories
├── docs/                    # LOCAL_GPU_SETUP guide
├── examples/                # Example campaign configs
├── mcp_servers/             # -> templates/.claude/mcp_servers (symlink)
├── src/                     # Source code
│   ├── init-cli/            #   `npx blatant-why init` CLI
│   ├── proteus_cli/         #   Python CLI (scoring, screening, campaign)
├── templates/               # Templates deployed by init CLI
│   ├── .claude/             #   Agents, commands, hooks, skills, settings
│   └── mcp_servers/         #   11 MCP server implementations
├── tests/                   # Test suite
├── CLAUDE.md                # Agent personality & orchestration rules
├── package.json             # Node.js package (Claude Code SDK)
├── pyproject.toml           # Python package (uv)
└── README.md
```

</details>

---

## Architecture

```mermaid
flowchart TB
    User([User]) -->|prompt| Claude[Claude Code + CLAUDE.md]

    Claude -->|delegates| Agents[16 Specialized Agents]
    Claude -->|invokes| Skills[14 Skills]
    Claude -->|slash cmds| Commands[11 Commands]

    Agents --> MCP[11 MCP Servers]
    Skills --> MCP

    subgraph Data["Data Sources"]
        PDB[(PDB)]
        UniProt[(UniProt)]
        SAbDab[(SAbDab)]
    end

    subgraph Compute["Compute"]
        Tamarind["Tamarind Bio -- Free Cloud"]
        LocalGPU["Local GPU -- Optional"]
    end

    subgraph Models["Models"]
        BoltzGen["BoltzGen -- Ab/Nb Design"]
        Protenix["Protenix v1 -- Structure Prediction"]
        PXDesign["PXDesign -- Binder Design"]
    end

    subgraph Screening["Screening"]
        ipSAE["ipSAE Scoring"]
        Liabilities["Liability Scan"]
        Developability["Developability"]
        Diversity["Diversity Selection"]
    end

    subgraph Lab["Lab"]
        Adaptyv["Adaptyv Bio -- Triple-Gated"]
    end

    MCP --> Data
    MCP --> Compute
    Compute --> Models
    MCP --> Screening
    MCP --> Lab

    Knowledge[("Knowledge Store -- JSON")] <--> MCP
```

<details>
<summary><strong>Model Profiles</strong></summary>

| Model | Type | Parameters | What It Does |
|-------|------|-----------|--------------|
| **Protenix v1** | Structure prediction | 368M | AlphaFold3-class folding (protein, nucleic acid, ligand) |
| **PXDesign** | De novo binder design | -- | 17-82% hit rates on published benchmarks |
| **BoltzGen** | Antibody/nanobody design | -- | Boltzmann generator + Protenix confidence scoring |

</details>

<details>
<summary><strong>Learning System</strong></summary>

Every campaign writes results to a JSON knowledge store. The knowledge MCP server provides keyword search over past campaigns, so the system learns which design strategies work for which target classes.

Stored per campaign:
- Target metadata and research context
- Design parameters and compute profiles
- Screening results and composite scores
- Success/failure annotations

Over time, the agent develops institutional memory about what works.

</details>

---

## Credits

**Built by** [Tristan Farmer](https://www.linkedin.com/in/tristan-farmer-973b7a17a/)

- [Hannes Stark](https://github.com/jostorge/boltzgen) and the MIT team for BoltzGen
- [Deniz Kavi](https://tamarind.bio) and Sherry Liu at Tamarind Bio
- [Julian Englert](https://www.adaptyvbio.com) at Adaptyv Bio
- The [Claude Code](https://docs.anthropic.com/en/docs/claude-code) team

---

## License

[MIT](LICENSE)
