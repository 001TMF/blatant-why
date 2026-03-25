---
name: by:setup
description: Discover and configure compute environment
---

# /setup — Environment Discovery and Configuration

Scan the local system and cloud endpoints to detect available tools,
GPU resources, and API keys. Write a complete environment profile.

## Instructions

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command:
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| by-environment | sonnet | sonnet | haiku |

### Step 1: Ensure config directory

```bash
mkdir -p .by
if [ ! -f .by/config.json ]; then
  echo '{"model_profile": "balanced"}' > .by/config.json
fi
```

### Step 2: Spawn by-environment agent

Delegate to a **by-environment** agent (model per profile table above):

> Scan the compute environment and produce a complete inventory.
>
> **Local tools** — check env vars and PATH for installed tools:
> - proteus-fold (Protenix): `$PROTEUS_FOLD_DIR` or `which protenix`
> - proteus-prot (PXDesign): `$PROTEUS_PROT_DIR` or `which pxdesign`
> - boltzgen: `$PROTEUS_AB_DIR` or `which boltzgen`
>
> **GPU** — run `nvidia-smi` if available. Report:
> - GPU model, VRAM, driver version, CUDA version
> - If no GPU, note "CPU-only — cloud providers required"
>
> **Python environment** — check for:
> - Python version (require 3.10+)
> - Key packages: torch, numpy, biopython, boltzgen
>
> **Cloud providers** — check API key environment variables:
> - TAMARIND_API_KEY (Tamarind Bio)
> - ADAPTYV_API_KEY (Adaptyv Bio — lab submission)
> - Report configured/missing for each (NEVER log key values)
>
> **SSH tunnels** — check for any active SSH tunnels to GPU nodes
>
> Write complete results to `.by/environment.json`.

### Step 3: Review environment report

Verify the agent produced valid environment.json with all required sections.

### Step 4: Select default provider

Based on the environment scan, recommend a compute provider:
1. **Tamarind Bio** if API key is configured (preferred — free tier)
2. **Local GPU** if NVIDIA GPU detected with sufficient VRAM (>=16GB)
3. **None** — warn that no compute provider is available

### Step 5: Report to user

Display a formatted environment summary:
- Tools found and their versions
- GPU status
- API keys status (configured/missing)
- Recommended provider
- Any warnings or setup steps needed
