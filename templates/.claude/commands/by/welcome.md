---
name: by:welcome
description: First-run orientation -- what BY can do and where to start
---

# /welcome — First-Run Orientation

Introduce BY to a new user and surface the core workflows without overwhelming
them with internal complexity.

## Instructions

### Step 1: Check if this is a first run

Read `.by/environment.json`. If it does not exist, this is likely a fresh install.
Note the result for Step 3 and Step 4.

### Step 2: Display welcome message

Present the following orientation:

---

# Welcome to BY (Blatant-Why)

BY is a protein design agent that helps you design nanobodies, antibodies, and protein binders. You describe a target, BY handles the computation.

## Getting Started (pick one)

**1. Design nanobodies against a target**
> Example: "Design VHH nanobodies against PD-L1"
>
> BY will research your target, ask a few quick questions about your preferences, then run the full design-screen-rank pipeline. You get back a ranked table of candidates ready for lab testing.

**2. Load and explore a target first**
> Example: `/by:load PD-L1` or `/by:load 5JDS`
>
> Research a protein target before committing to a design campaign. BY pulls structural data, known binders, and epitope information so you can make an informed decision.

**3. Check your environment**
> Example: `/by:setup`
>
> See what compute providers are available and which API keys are configured. Useful if you want to confirm Tamarind Bio access or check for local GPU tools.

**4. Resume an existing campaign**
> Example: `/by:status` then `/by:results`
>
> Check the state of a running campaign or view ranked designs from a completed one.

## Key Commands

| Command | What it does |
|---------|-------------|
| `/by:plan-campaign` | Quick discussion to capture your design preferences before launching |
| `/by:load` | Research a protein target (structure, known binders, epitopes) |
| `/by:status` | Check current campaign progress |
| `/by:results` | View ranked design candidates with scores |
| `/by:setup` | Configure compute providers and API keys |

## What happens behind the scenes

BY uses specialized MCP tools to search protein databases (PDB, UniProt, SAbDab), run structure predictions and design computations via Tamarind Bio cloud (free tier available), and score candidates with custom metrics (ipSAE for interface quality, ipTM for global confidence). You do not need to manage any of this -- just describe what you want.

**Tip:** Start with workflow #1 above. BY will guide you through the rest.

---

### Step 3: Environment check

If `.by/environment.json` does NOT exist:

> **Recommendation:** Run `/by:setup` first to configure your compute environment. This will detect available tools and set up API keys.

### Step 4: API key check

If `.by/environment.json` exists but `TAMARIND_API_KEY` is not configured (check the environment file for tamarind provider status):

> **Note:** Tamarind Bio API key is not configured. You can still use BY with local tools, but for cloud compute (recommended), add your API key to `.env`:
> ```
> TAMARIND_API_KEY=your_key_here
> ```
> Get a free key at https://tamarind.bio

If environment is fully configured, skip this step.
