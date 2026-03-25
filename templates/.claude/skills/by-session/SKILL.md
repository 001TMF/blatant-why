---
name: by-session
description: >
  Session initialization and configuration for BY projects.
  Use this skill when: (1) Opening a new session in a BY project directory,
  (2) Running first-time setup (config questionnaire),
  (3) Checking environment and compute availability,
  (4) Reading or updating .by/config.json or .by/environment.json.
category: session
tags: [session, config, environment, setup, initialization]
---

# BY Session & Config Skill

This skill defines the full session start sequence and the first-run configuration
questionnaire for BY projects. It is NOT optional -- it runs every time a new
session opens in a BY project directory.

---

## 1. First-Run Setup (when .by/config.json does NOT exist)

When `.by/config.json` is missing, run the full setup questionnaire before anything
else. Use `AskUserQuestion` for all structured choices.

### Round 1 -- Compute Provider

```
AskUserQuestion(
  header: "Compute Provider",
  question: "Where should BY run design computations?",
  options: [
    "Auto-detect (Recommended)" -- Check what's available and pick the best,
    "Local GPU" -- NVIDIA GPU with tools installed (fastest, no cost),
    "Tamarind Bio" -- Cloud compute, free tier available (no GPU needed),
    "SSH Remote" -- Cloud GPU instances (Lambda.ai, RunPod, HPC)
  ]
)
```

#### If user selects "Auto-detect"

Run the same checks as "Local GPU" silently. If local tools are found, use them.
If not, check for Tamarind API key. Report what was found and which provider was
selected.

#### If user selects "Local GPU" -- follow-up questions

**BoltzGen path:**
```
AskUserQuestion(
  header: "BoltzGen Path",
  question: "Where is BoltzGen installed?",
  options: [
    "Auto-detect" -- Search PATH and common locations,
    "Custom path" -- I'll provide the path
  ]
)
```
If "Custom path" is selected, ask inline for the path. Validate the path exists.

**Protenix path:**
```
AskUserQuestion(
  header: "Protenix Path",
  question: "Where is Protenix installed?",
  options: [
    "Auto-detect" -- Search PATH and common locations,
    "Custom path" -- I'll provide the path
  ]
)
```
Same flow -- if "Custom path", ask inline and validate.

**PXDesign path:**
```
AskUserQuestion(
  header: "PXDesign Path",
  question: "Where is PXDesign installed?",
  options: [
    "Auto-detect" -- Search PATH and common locations,
    "Custom path" -- I'll provide the path
  ]
)
```
Same flow -- if "Custom path", ask inline and validate.

**After collecting paths, run environment checks:**

1. Which conda envs exist?
   ```bash
   conda env list 2>/dev/null | grep -E 'bg|protenix|pxdesign'
   ```

2. Are the tools actually runnable? Quick `--help` check for each:
   ```bash
   conda run -n bg boltzgen --help 2>/dev/null | head -1
   conda run -n protenix protenix --help 2>/dev/null | head -1
   conda run -n pxdesign pxdesign --help 2>/dev/null | head -1
   ```

3. Are model weights downloaded? Check for expected weight directories:
   - BoltzGen: `{path}/weights/` or `{path}/models/`
   - Protenix: `{path}/model_data/` or `{path}/release/`
   - PXDesign: `{path}/weights/`

4. GPU detection:
   ```bash
   nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
   ```

**Report findings in this format:**
```
Local GPU Setup:
  BoltzGen  ✓ /data/proteus/proteus-design (conda: bg, weights: ✓)
  Protenix  ✓ /data/proteus/Protenix (conda: protenix, model: 2025 base)
  PXDesign  ✓ /data/proteus/PXDesign (conda: pxdesign, weights: ✓)
  GPU       NVIDIA RTX PRO 6000 (98GB VRAM)
```

Use `✗` and a reason for any tool that fails validation:
```
  PXDesign  ✗ not found (conda env 'pxdesign' does not exist)
```

#### If user selects "Tamarind Bio"

1. Check if `TAMARIND_API_KEY` is set in environment or `.env` file:
   ```bash
   grep -q TAMARIND_API_KEY .env 2>/dev/null && echo "found" || echo "missing"
   ```

2. If not found, guide the user:
   ```
   Tamarind Bio API key not found.

   To get a free key:
   1. Go to https://tamarind.bio
   2. Sign up / log in
   3. Copy your API key from the dashboard
   4. Add to .env: TAMARIND_API_KEY=your_key_here
   ```

3. If found, check quota via `mcp__by-cloud__cloud_list_providers` and report:
   ```
   Tamarind Bio: ✓ connected
     Tier: free | GPU-hours remaining: 87
     Models: BoltzGen, Protenix, PXDesign available
   ```

#### If user selects "SSH Remote"

Ask for connection details inline:
- Host: hostname or IP
- User: SSH username
- Key path: path to SSH private key (default: `~/.ssh/id_rsa`)
- GPU type: what GPU is on the remote (for VRAM estimation)

Test the SSH connection:
```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes user@host echo "ok" 2>/dev/null
```

Report success or failure. Write connection details to config.

### Round 2 -- Model Profile

```
AskUserQuestion(
  header: "AI Model Profile",
  question: "Which AI models for sub-agents?",
  options: [
    "Balanced (Recommended)" -- Sonnet for most agents, good quality/cost ratio,
    "Quality" -- Opus for research/design agents, deeper analysis,
    "Budget" -- Haiku where possible, fastest and lowest cost
  ]
)
```

### Round 3 -- Campaign Defaults

```
AskUserQuestion(
  header: "Default Campaign Size",
  question: "Default designs per campaign?",
  options: [
    "Preview (~500)" -- Fast testing, feasibility checks,
    "Standard (~5,000)" -- Good sampling per scaffold (Recommended),
    "Production (~20,000)" -- Thorough coverage, difficult targets
  ]
)
```

### Write config.json

After all rounds, write `.by/config.json` with the collected settings:

```json
{
  "model_profile": "balanced",
  "compute": {
    "preferred_provider": "local",
    "local": {
      "boltzgen": {
        "path": "/data/proteus/proteus-design",
        "conda_env": "bg",
        "weights": true
      },
      "protenix": {
        "path": "/data/proteus/Protenix",
        "conda_env": "protenix",
        "model": "protenix_base_20250630_v1.0.0"
      },
      "pxdesign": {
        "path": "/data/proteus/PXDesign",
        "conda_env": "pxdesign",
        "weights": true
      }
    },
    "tamarind": {
      "tier": "free",
      "api_key_configured": true
    },
    "ssh": {
      "host": null,
      "user": null,
      "key_path": null,
      "gpu_type": null
    },
    "gpu": {
      "name": "NVIDIA RTX PRO 6000",
      "vram_gb": 98
    }
  },
  "campaign_defaults": {
    "tier": "standard",
    "fold_validation": true
  }
}
```

Only include sections that apply. For example, if the user selected "Tamarind Bio",
omit the `local` block (or set paths to null). If no SSH was configured, omit the
`ssh` block.

Then show: "Configuration saved to .by/config.json. Ready."

---

## 2. Session Start (when .by/config.json EXISTS)

When `.by/config.json` already exists, skip the questionnaire and go straight to
the session banner and status.

### Step 1: Show banner

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► Protein Design Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 2: Read config and environment

Read `.by/config.json` for user preferences. Read `.by/environment.json` if it
exists (written by the SessionStart hook). Determine:

- Which compute providers are available and configured
- Current model profile
- Default campaign tier
- API keys present (without exposing values)

### Step 3: Check for existing campaigns

```bash
ls .by/campaigns/*/campaign_log.json 2>/dev/null
```

Count campaigns, check for any in active (non-complete) state.

### Step 4: Display status

Build the compute status line from config:

- **Local GPU**: show tool names if local tools are configured
  `Compute: Local GPU ✓ (BoltzGen, Protenix, PXDesign)`
- **Tamarind Bio**: show tier
  `Compute: Tamarind Bio ✓ (free tier)`
- **SSH Remote**: show host
  `Compute: SSH Remote ✓ (gpu-node.example.com)`
- **Multiple**: list all with preferred marked
  `Compute: Local GPU ✓ (preferred) | Tamarind Bio ✓`

Full display:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► Protein Design Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Compute: Local GPU ✓ (BoltzGen, Protenix, PXDesign)
Profile: balanced | Default: standard (5,000/scaffold)
Campaigns: [N] previous

Ready:
  "Design [modality] against [target]"
  /by:plan-campaign -- guided setup
  /by:status -- existing campaigns
```

If there are campaigns in active state, highlight them:

```
Campaigns: 3 previous, 1 active (anti-HER2 -- designing 80%)
```

If there are zero campaigns:

```
Campaigns: none yet

Ready:
  "Design nanobodies against [target]" -- start your first campaign
  /by:welcome -- first-time walkthrough
  /by:plan-campaign -- guided setup
```

---

## 3. Environment Awareness

On every session start, read `.by/environment.json` for available tools and compute:

- Which compute providers are configured (Tamarind, SSH hosts, local GPU)
- Remaining quota / tier for cloud providers
- Available local tools (Protenix, PXDesign, BoltzGen) with paths
- API keys present (without exposing values)
- GPU hardware details (model, VRAM)

Read `.by/config.json` for user preferences:

- Model profile (quality / balanced / budget)
- Default compute provider
- Campaign defaults (tier, fold_validation)

If `.by/environment.json` is stale (>24h), suggest running `/by:setup` to refresh.

---

## 4. Config Update

When the user wants to change settings after initial setup:

- `/by:set-profile` changes model_profile in config.json
- `/by:setup` re-runs environment discovery and updates environment.json
- Direct requests like "switch to Tamarind" update compute.preferred_provider

Always read the existing config, modify only the changed fields, and write back.
Never overwrite unrelated settings.
