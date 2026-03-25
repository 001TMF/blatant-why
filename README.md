<p align="center">
  <img src="assets/banner.png" alt="Blatant-Why" width="700">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/v0.1.0--beta-Live_Beta-orange?style=flat-square" alt="v0.1.0-beta">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <a href="https://github.com/001TMF/blatant-why/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square" alt="PRs Welcome"></a>
  <img src="https://img.shields.io/badge/Claude_Code-Agent-blueviolet?style=flat-square" alt="Claude Code Agent">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=node.js&logoColor=white" alt="Node.js 18+">
</p>

<h3 align="center">Open-source protein design agent for Claude Code</h3>

<p align="center">
Commercial platforms wrap open-source tools behind paywalls and call it a revolution.<br>
BY gives you direct access through Claude Code. No platform fees. Your tools, your compute, your designs.
</p>

---

<p align="center">
  <img src="assets/by_timesaver.png" alt="Time comparison: traditional vs. agentic antibody design" width="400">
</p>
<p align="center"><sub>Source: trust us bro</sub></p>

---

## Quick Start (5 minutes)

You don't need to be a developer. If you can open a terminal and paste commands, you can run BY.

### 1. Install prerequisites

| Tool | Install | Check |
|------|---------|-------|
| **Node.js 18+** | [nodejs.org](https://nodejs.org/) | `node --version` |
| **Python 3.11+** | [python.org](https://www.python.org/) | `python3 --version` |
| **uv** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| **Claude Code** | `npm install -g @anthropic-ai/claude-code` | `claude --version` |

### 2. Create your project

```bash
mkdir my-campaign && cd my-campaign
npx blatant-why init
```

This scaffolds everything: 11 MCP servers, 16 agents, 14 skills, 11 slash commands, and a CLAUDE.md orchestration file. Takes about 30 seconds.

### 3. Add your API key

```bash
cp .env.example .env
# Open .env and add your Tamarind key (see Compute Setup below)
```

### 4. Start designing

```bash
claude
```

Then just tell it what you want:

```
> "Design VHH nanobodies against PD-L1"
```

Or use the guided workflow:

```
> /by:plan-campaign
```

Or if it's your first time:

```
> /by:welcome
```

That's it. Claude Code handles the rest -- research, design, screening, and ranking.

---

## What It Does

Give it a target protein. It researches across PDB, UniProt, and SAbDab. It plans a design campaign. It submits compute jobs to Tamarind Bio (free tier, no GPU required). It screens every design for structural quality, sequence liabilities, and developability. It ranks candidates by composite score. You get a table of lab-ready binders.

The whole pipeline runs inside Claude Code. No platform. No dashboard. No vendor lock-in.

---

## What's Inside

| Component | Count | Description |
|-----------|-------|-------------|
| MCP Servers | 11 | Biological databases, cloud compute, screening, campaign state, knowledge store |
| Agents | 16 | Research, design, screening, evaluation, lab integration, and more |
| Skills | 14 | BoltzGen, Protenix, PXDesign, scoring, epitope analysis, campaign management |
| Slash Commands | 11 | Campaign control from the Claude Code prompt |

<details>
<summary><strong>MCP Servers (11)</strong></summary>

| Server | Role |
|--------|------|
| `pdb` | Protein Data Bank queries |
| `uniprot` | UniProt protein annotation |
| `sabdab` | Structural Antibody Database |
| `screening` | Screening battery orchestration |
| `tamarind` | Tamarind Bio cloud compute |
| `cloud` | Cloud compute abstraction |
| `adaptyv` | Adaptyv Bio lab submission (gated) |
| `campaign` | Campaign state management |
| `research` | Literature and target research |
| `local_compute` | Local GPU compute dispatch |
| `knowledge` | JSON-backed campaign knowledge store |

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
| `/by:plan-campaign` | Generate a detailed campaign plan |
| `/by:welcome` | Show welcome message and quick-start guide |
| `/by:resume` | Resume an interrupted or paused campaign |

</details>

---

## Setup

### API Keys

| Key | Required? | Where to get it | What it enables |
|-----|-----------|-----------------|-----------------|
| `TAMARIND_API_KEY` | Recommended | [tamarind.bio](https://tamarind.bio) (free account) | Cloud compute -- BoltzGen, Protenix, 200+ models. Free tier: 10 jobs/month |
| `ADAPTYV_API_TOKEN` | Optional | [adaptyvbio.com](https://www.adaptyvbio.com) | Lab testing submission (triple-gated) |

Claude Code handles its own authentication. No separate Anthropic API key needed.

### Configure your environment

After `npx blatant-why init`:

1. Copy `.env.example` to `.env`
2. Add your Tamarind key:
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
| **SSH Remote** | Your infrastructure | Configure in `.by/config.json` | HPC clusters, cloud GPUs |

<details>
<summary><strong>Setting up Tamarind Bio (recommended -- no GPU needed)</strong></summary>

1. Create a free account at [tamarind.bio](https://tamarind.bio)
2. Go to Settings → API Keys → Generate new key
3. Copy the key and add to `.env`:
   ```
   TAMARIND_API_KEY=your-key-here
   ```
4. That's it. BY will use Tamarind for all compute jobs.

**Free tier:** 10 jobs/month. Enough for a preview campaign (~5-10 designs).
**Paid tiers:** Contact Tamarind for production pricing.

Tamarind provides access to 200+ structural biology tools including:
- **BoltzGen** -- antibody/nanobody design (Boltzmann generator diffusion)
- **Protenix v1** -- AlphaFold3-class structure prediction (368M params)
- **PXDesign** -- de novo protein binder design (17-82% hit rates)
- **TAP/TNP** -- developability profiling
- **AbLang2** -- humanness scoring

</details>

<details>
<summary><strong>Setting up local GPU compute</strong></summary>

Requires an NVIDIA GPU with CUDA support. Install the tools you need:

**Protenix (structure prediction):**
```bash
git clone https://github.com/bytedance/protenix
cd protenix && pip install -e .
```
Add to `.env`:
```
PROTEUS_FOLD_DIR=/path/to/protenix
```

**PXDesign (de novo binder design):**
```bash
# Follow PXDesign installation guide
```
Add to `.env`:
```
PROTEUS_PROT_DIR=/path/to/pxdesign
```

**BoltzGen (antibody/nanobody design):**
```bash
git clone https://github.com/jostorge/boltzgen
cd boltzgen && pip install -e .
```
Add to `.env`:
```
PROTEUS_AB_DIR=/path/to/boltzgen
```

BY will detect these automatically and offer local compute as an option.

</details>

<details>
<summary><strong>Setting up SSH remote compute (Lambda.ai, RunPod, HPC)</strong></summary>

For cloud GPU instances or HPC clusters:

1. Ensure SSH key-based authentication is set up
2. Add host configuration to `.by/config.json`:
   ```json
   {
     "compute": {
       "ssh_hosts": [
         {
           "name": "lambda-gpu",
           "host": "your-instance.cloud.lambdalabs.com",
           "user": "ubuntu",
           "key": "~/.ssh/lambda_key",
           "gpu": "A100",
           "tools": ["protenix", "boltzgen"]
         }
       ]
     }
   }
   ```
3. BY will detect SSH hosts and offer them as compute options.

</details>

---

## Your First Campaign

After setup, here's what to expect when you run your first design campaign.

**Start Claude Code:**
```bash
claude
```

**Tell it what you want:**
```
> "Design VHH nanobodies against PD-L1"
```

**What happens next:**

1. **Research** (~1-2 min) -- BY searches PDB, UniProt, and SAbDab for your target. It pulls crystal structures, known binders, epitope data, and literature context.
2. **Campaign plan** (~30 sec) -- You get a plan showing how many designs will be generated, which models will be used, and estimated compute cost. You approve before anything runs.
3. **Design generation** (~5-15 min) -- Compute jobs run on Tamarind Bio (or your local GPU). BY monitors progress and reports back.
4. **Screening** (~2-5 min) -- Every design is scored for structural quality (ipSAE), binding confidence (ipTM), and sequence liabilities. Problem candidates are flagged.
5. **Ranking** -- You get a ranked table of candidates with composite scores, ready for lab ordering.

**Typical first campaign:** 5-10 nanobody designs, ~20 minutes end-to-end, zero GPU required (Tamarind free tier).

You can also use slash commands for more control:

| Command | What it does |
|---------|--------------|
| `/by:welcome` | Guided walkthrough for first-time users |
| `/by:plan-campaign` | Generate and review a campaign plan before running |
| `/by:status` | Check progress on a running campaign |
| `/by:results` | View ranked results table |

---

## Architecture

```mermaid
flowchart TB
    User([User]) -->|prompt| Claude[Claude Code + CLAUDE.md]

    Claude -->|delegates| Agents[16 Agents]
    Claude -->|invokes| Skills[14 Skills]
    Claude -->|slash cmds| Commands[11 Commands]

    Agents --> MCP[11 MCP Servers]
    Skills --> MCP

    subgraph Data["Biological Databases"]
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

    subgraph Lab["Lab Integration"]
        Adaptyv["Adaptyv Bio -- Triple-Gated"]
    end

    MCP --> Data
    MCP --> Compute
    Compute --> Models
    MCP --> Screening
    MCP --> Lab

    Knowledge[("Knowledge Store")] <--> MCP
```

<details>
<summary><strong>Model Profiles</strong></summary>

| Model | Type | What It Does |
|-------|------|--------------|
| **Protenix v1** | Structure prediction (368M params) | AlphaFold3-class folding -- protein, nucleic acid, ligand |
| **PXDesign** | De novo binder design | 17-82% hit rates on published benchmarks |
| **BoltzGen** | Antibody/nanobody design | Boltzmann generator + Protenix confidence scoring |

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

<details>
<summary><strong>Repository Structure</strong></summary>

```
blatant-why/
├── assets/                  # Banner and diagrams
├── src/
│   ├── init-cli/            # npx blatant-why init CLI
│   └── proteus_cli/         # Python CLI (scoring, screening, campaign)
├── templates/               # Deployed by init CLI
│   └── .claude/
│       ├── agents/          # 16 specialized agents
│       ├── commands/by/     # 11 slash commands
│       ├── skills/          # 14 skills
│       └── mcp_servers/     # 11 MCP server implementations
├── tests/                   # Test suite
├── CLAUDE.md                # Agent orchestration rules
├── package.json             # npm package
├── pyproject.toml           # Python package (uv)
└── README.md
```

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
