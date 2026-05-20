---
id: "skill_b7bd2add94d84922a8d7141b635a4d89"
name: "by-deploy-compute"
display-name: "BY Deploy Compute"
short-description: "Set up structure-prediction and antibody/binder design tools on user-owned compute — local GPU, RunPod, Modal, or generic SLURM/PBS HPC. Use when bootstrapping a new BY workstation, adding a tool (Protenix, BoltzGen, PXDesign, RFAntibody, etc.) to an existing environment, or migrating away from Tamarind cloud."
category: "deployment"
keywords: "deployment, local GPU, RunPod, Modal, HPC, SLURM, CUDA, Docker, Protenix, BoltzGen, PXDesign, RFAntibody, ImmuneBuilder, ThermoMPNN, Boltz-2, AlphaFold, weights, conda, env"
version: "1.0"
last-updated: "2026-05-20"
---

# BY Deploy Compute Skill

BY is a **local-first** agent. The default compute provider is `"local"` (see
`.by/config.json` → `compute.default_provider`). This skill teaches you how to
stand up each design and folding tool on hardware **the user owns or pays for
directly** — a personal GPU workstation, a RunPod pod, a Modal app, or a
generic SLURM/PBS cluster — so campaigns run without depending on a managed
cloud provider.

Tamarind remains available as a cloud fallback when local compute is
unavailable. It is never the default; users opt in explicitly via
`compute.default_provider = "tamarind"`.

## When to Use This Skill

Use this skill when you have:

- ✅ **A fresh BY workstation** that needs Protenix / BoltzGen / PXDesign installed for the first time
- ✅ **An existing local install missing a tool** (e.g., ThermoMPNN, RFAntibody, ImmuneBuilder) that an active campaign now requires
- ✅ **A RunPod account** and want a per-tool deployment recipe with pod template, persistent volumes, and a working `entry_command`
- ✅ **A Modal account** and want a `modal.Image` recipe with HuggingFace secret wiring and weight-cache volumes
- ✅ **An institutional HPC** (SLURM or PBS) and want a portable submission script that loads CUDA modules, activates a conda env, and runs the tool
- ✅ **A user migrating away from Tamarind** — concrete, copy-pasteable replacement deployments for every tool they currently call
- ✅ **A failed local invocation** that needs to be diagnosed as a deployment issue (missing weights, wrong CUDA, OOM) vs a tool-internal bug

Do NOT use this skill when:

- ❌ **You just need to run a tool that is already installed** — invoke the engine skill (`protenix`, `boltzgen`, `pxdesign`) directly.
- ❌ **You are debugging tool-internal results** (low ipSAE, high RMSD) — use `by-scoring` or `by-failure-diagnosis`. Deployment is upstream of result quality.
- ❌ **The user has explicitly chosen Tamarind** (`compute.default_provider = "tamarind"`) — call the Tamarind MCP path; don't try to deploy locally first.
- ❌ **The campaign is already running** and just needs a status check — that's `by-campaign-manager` or `/by:watch`.
- ❌ **You need to allocate a campaign directory** — that is `by-session` / `by-campaign-manager`.
- ❌ **The question is "which tool should I use"** — that is `by-design-workflow`; deployment is per-tool plumbing, not strategy.

## Quick Start

```text
User: "Set up Protenix on my workstation. I have an RTX 4090."

Agent:
  1. Run scripts/check_gpu_env.sh → confirms CUDA 12.1, 24GB free
  2. Look up Protenix in the Tool Catalog → 16-24 GB recommended, OK
  3. Render scripts/deploy_tool_template.yaml with target=local, tool=protenix
  4. Clone repo + download weights to the path in `.by/config.json` compute.local.protenix.path
  5. Create conda env per references/local-gpu-setup.md
  6. Smoke-test: predict 6OFS chain A; expect a .cif file + confidence JSON in under 5 minutes
  7. Update .by/config.json compute.local.protenix.{path,conda_env,binary}
  8. Done — campaigns now resolve Protenix locally.
```

```text
User: "Deploy BoltzGen on RunPod, I don't have a local GPU."

Agent:
  1. Confirm RUNPOD_API_KEY is set (refuse if missing — direct to references/runpod-setup.md)
  2. Choose pod template: PyTorch 2.4 + CUDA 12.4, GPU = A40 (48 GB)
  3. Mount persistent volume `/runpod-volume` for weights cache
  4. Render scripts/deploy_tool_template.yaml with target=runpod, tool=boltzgen
  5. Run scripts/runpod_deploy.py deploy_boltzgen.yaml → returns pod_id + endpoint URL
  6. Update .by/config.json compute.hpc.endpoint_url
  7. Done — design agent now resolves BoltzGen against the RunPod endpoint.
```

## Installation

This skill itself has no Python dependencies beyond stdlib. The tools it
deploys each have their own dependency graphs documented in their respective
upstream repos. The table below lists what the **scripts in this skill**
require.

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| Python | ≥ 3.10 | PSF | ✅ Permitted | system / conda |
| PyYAML | ≥ 6.0 | MIT | ✅ Permitted | `pip install pyyaml` |
| requests | ≥ 2.31 | Apache-2.0 | ✅ Permitted | `pip install requests` |
| bash | ≥ 4.0 (Linux) / 3.2 (macOS) | GPLv3 | ✅ Permitted | system |
| Docker (optional) | ≥ 24.0 | Apache-2.0 | ✅ Permitted | docker.com |
| nvidia-driver | ≥ 535 (CUDA 12.x) | NVIDIA EULA | ✅ Permitted (binary use) | nvidia.com |
| CUDA Toolkit | 12.1 or 12.4 | NVIDIA EULA | ✅ Permitted | developer.nvidia.com |

**License Compliance:** All packages and runtimes in this table permit
commercial use in AI applications. The per-tool license is documented in each
tool's upstream repository — check before commercial deployment.

**System requirements:**
- Linux x86_64 (Ubuntu 22.04 LTS recommended) for any NVIDIA-GPU workflow
- macOS (Apple Silicon) only supports a subset of tools via MPS or CPU-only fallback paths
- For RunPod: outbound HTTPS to `api.runpod.io` and a funded account
- For Modal: outbound HTTPS to `api.modal.com` and `modal token new` completed
- For HPC: ssh access, a working conda or module system, and a GPU partition

## Inputs

**Required:**
- **Target deployment surface** — exactly one of `local`, `runpod`, `modal`, `hpc`. Drives every downstream choice.
- **Tool name** — one of: `protenix`, `boltzgen`, `pxdesign`, `alphafold2`, `alphafold3`, `rfantibody`, `immunebuilder`, `thermompnn`, `boltz2`. See Tool Catalog below.
- **Working directory** — absolute path where the repo will be cloned and weights will be cached. For local, this becomes `compute.local.<tool>.path` in `.by/config.json`.

**Conditional (per target):**
- **`local`** — GPU model + free VRAM (from `nvidia-smi`); conda or Docker preference.
- **`runpod`** — `RUNPOD_API_KEY` in environment; preferred GPU type (A40 / A100-40 / A100-80 / H100); region.
- **`modal`** — `modal token new` already run; HuggingFace token if any tool needs gated weights.
- **`hpc`** — cluster scheduler (`slurm` or `pbs`); GPU partition name; module-load commands for CUDA; conda or singularity preference.

**Optional:**
- **Weights URL override** — if the user has a private mirror, pass it; otherwise default to upstream.
- **Pinned CUDA version** — defaults to 12.1; override only if the cluster forces a different version.
- **Pod/image tag** — defaults to a known-good PyTorch image; override for reproducibility-locked deployments.

See [`references/runpod-setup.md`](references/runpod-setup.md),
[`references/local-gpu-setup.md`](references/local-gpu-setup.md), and
[`references/modal-setup.md`](references/modal-setup.md) for per-surface
specifics.

## Outputs

All outputs are written next to the tool install (under the working directory)
and a single config-update is applied to `.by/config.json`.

| Output | Location | Purpose |
|--------|----------|---------|
| Cloned tool repo | `<workdir>/<tool>/` | Source code at the pinned commit |
| Downloaded weights | `<workdir>/<tool>/weights/` (or HF cache) | Model checkpoints |
| Conda env (local/HPC) | `<workdir>/envs/<tool>/` or named env | Reproducible runtime |
| Docker image (optional) | local registry tag `by/<tool>:<version>` | Portable runtime |
| `deploy.yaml` (rendered) | `<workdir>/<tool>/deploy.yaml` | Records the deployment so it can be re-applied |
| `smoke_test.log` | `<workdir>/<tool>/smoke_test.log` | Proof the tool runs end-to-end |
| Updated `.by/config.json` | repo root | `compute.local.<tool>` or `compute.hpc.endpoint_url` populated |
| RunPod endpoint URL | printed to stdout, copied to config | `https://<pod-id>-<port>.proxy.runpod.net` |
| Modal app URL | printed to stdout, copied to config | `https://<workspace>--<app>.modal.run` |
| HPC submission script | `<workdir>/<tool>/submit.sbatch` (SLURM) or `.pbs` (PBS) | Reusable batch script |

**Verification:** Every deployment produces a `smoke_test.log` showing one
successful end-to-end invocation against a tiny test input (e.g., a 50-residue
protein for folding tools, a 1-chain target for design tools). If the smoke
test fails, the deployment is not done.

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — Before downloading anything, confirm the
deployment surface and the working directory. A wrong answer here means
hundreds of GB of weights end up in the wrong place.

1. **Deployment surface (ASK THIS FIRST)** — Local GPU, RunPod, Modal, or HPC? If unsure, ask about hardware: "Do you have a local NVIDIA GPU with 24 GB or more of VRAM?" If yes → local. If no, ask about budget and queue tolerance — RunPod (pay-per-hour, no queue), Modal (free tier + scale-to-zero), or HPC (free if institutional, but queue).
2. **Tool list** — Which tools must be deployed in this session? Common combinations: `{protenix, boltzgen}` for an antibody campaign; `{protenix, pxdesign}` for de novo binders; add `{thermompnn, immunebuilder}` for downstream developability.
3. **Working directory** — Absolute path. For local: typically `~/by/tools/` or `/opt/by/`. For RunPod: pod's `/workspace/` (persistent volume). For Modal: not user-facing (Modal manages it). For HPC: a project-shared filesystem with at least 200 GB free.
4. **GPU VRAM available** — Run `scripts/check_gpu_env.sh` to confirm. Cross-reference the Tool Catalog: BoltzGen and AlphaFold3 need 24+ GB; Protenix is happiest with 24+ GB but can run smaller models on 16 GB.
5. **API key / credentials present** — For RunPod, is `RUNPOD_API_KEY` exported? For Modal, has `modal token new` been run? For HPC, do you have ssh + a GPU partition allocation?
6. **Existing installs to preserve** — Are any of these tools already partially installed? If yes, do NOT overwrite — diff against the existing install and only fill in what's missing.
7. **Weights cache location** — Should weights live inside the working directory, or in a shared cache (e.g., `~/.cache/huggingface/`)? Shared cache saves disk when multiple tools share base models (e.g., Boltz-2 ↔ BoltzGen).

## Standard Workflow

🚨 **MANDATORY: USE THE SCRIPTS IN `scripts/` — DO NOT WRITE INLINE DEPLOYMENT CODE** 🚨

The skill ships three scripts that compose into the full deployment flow.
Their job is to make every step copy-pasteable and auditable.

**Step 1 — Environment check (always):**
```bash
bash scripts/check_gpu_env.sh
```
✅ **VERIFICATION:** Expected `✓ Detected N GPU(s); free VRAM = X GB; CUDA = 12.x`. If you see `✗ No NVIDIA GPU detected`, switch to a cloud surface (`runpod` / `modal`) before continuing.

**Step 2 — Render a deploy manifest:**
Copy `scripts/deploy_tool_template.yaml` to `<workdir>/<tool>/deploy.yaml` and
fill in the six fields (see Generic Builder Pattern below). One file per tool.

**Step 3 — Apply the deployment:**
- For `target: local` — run the recipe in `references/local-gpu-setup.md` (clone → conda env → weights → smoke test).
- For `target: runpod` — `python3 scripts/runpod_deploy.py <workdir>/<tool>/deploy.yaml`.
- For `target: modal` — `modal deploy <workdir>/<tool>/modal_app.py` (template in `references/modal-setup.md`).
- For `target: hpc` — `sbatch <workdir>/<tool>/submit.sbatch`.

**Step 4 — Smoke test:**
Invoke the tool against a tiny test input and write `smoke_test.log`. The
specific invocation depends on the tool — examples in
`references/local-gpu-setup.md` §Smoke Tests.

**Step 5 — Update `.by/config.json`:**
For `local`, set `compute.local.<tool>.{path, conda_env, binary}`. For `runpod`
/ `modal` / `hpc`, set `compute.hpc.endpoint_url` (or add a per-tool override
under `compute.hpc.<tool>.endpoint_url`).

**Discipline:**
- ✅ Always run `check_gpu_env.sh` first — every deployment depends on its output
- ✅ One `deploy.yaml` per tool, committed alongside the install
- ✅ Smoke-test before declaring the deployment done
- ✅ Update `.by/config.json` in the same session — otherwise the agent can't find the tool
- ❌ Do NOT skip the smoke test ("the install completed" is not proof the tool runs)
- ❌ Do NOT hardcode paths — every script accepts the working directory as an argument
- ❌ Do NOT download weights into the repo's tracked tree — keep them under `weights/` (gitignored)
- ❌ Do NOT use `sudo pip install` — always conda env or virtualenv

## Choose a Deployment Target

| Target | Best For | VRAM Available | Cold Start | $ / hr | Setup Time | Pros | Cons |
|--------|----------|----------------|-----------|--------|-----------|------|------|
| **Local GPU** | Daily iteration; private targets; fast turnaround | Whatever you own (typically 24-80 GB) | 0 s (already on) | $0 marginal | 30-60 min one-time | Fastest iteration; full privacy; no per-call cost; works offline | Requires own hardware; you maintain drivers & weights |
| **RunPod** | Spiky workloads; >80 GB needs; no local GPU | A40 (48), A100 (40/80), H100 (80) | 30-90 s | $0.34 (A40) → $2.49 (H100) | 15-30 min | Cheap on-demand; large GPU choice; full SSH | Pay-per-second; ephemeral by default; needs persistent volume |
| **Modal** | Bursty workloads with idle gaps; free tier R&D | T4 (16), A10G (24), A100 (40/80), H100 (80) | 2-10 min (cold) to 5 s (warm) | $0.59 (T4) → $4.56 (H100) + $30/mo free credits | 20-40 min | Serverless scale-to-zero; generous free tier; weights cache in volumes; secrets manager | Slow cold start; image build is opinionated; less SSH-y |
| **Generic SLURM/PBS HPC** | Institutional users; long jobs; free compute | Whatever the cluster offers | Minutes to hours (queue) | $0 (institutional) | 1-3 h one-time (env + modules) | Free at the point of use; high concurrency; well-resourced | Queue waits; shared filesystem quirks; module-system politics; no GPU control |

**Decision rule:**
1. If `nvidia-smi` reports ≥ 24 GB free VRAM on a CUDA-12-compatible GPU → **local**.
2. Else, if `RUNPOD_API_KEY` is set or the user has a RunPod account → **RunPod**.
3. Else, if `modal token new` succeeded → **Modal**.
4. Else, if the user has institutional HPC access → **HPC**.
5. Else, set `compute.default_provider = "tamarind"` and call the Tamarind MCP path (outside the scope of this skill).

## Tool Catalog

Every tool listed here can be deployed on any of the four targets. The GPU
memory column is the **recommended minimum** for typical inputs (≤ 600
residues per chain, ≤ 4 chains, default sampling counts). Larger targets need
proportionally more.

| Tool | Function | GPU Memory | Repo URL | Weights URL | Typical Runtime per Call |
|------|----------|-----------|----------|-------------|-------------------------|
| **Protenix** | AF3-class structure prediction (368 M params); used for refolding designs and complex prediction | 16-24 GB | https://github.com/bytedance/Protenix | https://huggingface.co/ByteDance/Protenix | 1-5 min per complex (single seed) |
| **BoltzGen** | Diffusion-based antibody and nanobody binder design (paired with Protenix refold) | 24-40 GB | https://github.com/jwohlwend/boltz | https://huggingface.co/boltz-community | 30-90 min for 100 designs against a single epitope |
| **PXDesign** | De novo non-antibody binder design (RFdiffusion-style) | 24-32 GB | https://github.com/RosettaCommons/RFdiffusion | https://files.ipd.uw.edu/pub/RFdiffusion/ | 5-20 min for 50 designs |
| **AlphaFold2** | Monomer and multimer structure prediction (legacy, still useful for cross-checks) | 16-40 GB (memory-efficient mode) | https://github.com/deepmind/alphafold | https://storage.googleapis.com/alphafold/ | 5-30 min depending on MSA |
| **AlphaFold3** | Latest DeepMind folder; closed weights (research license) | 24-40 GB | https://github.com/google-deepmind/alphafold3 | request via DeepMind form | 2-10 min per complex |
| **RFAntibody** | Antibody CDR design and inverse-folding via RFdiffusion variant | 24 GB | https://github.com/RosettaCommons/RFantibody | https://files.ipd.uw.edu/pub/RFantibody/ | 10-30 min per design batch |
| **ImmuneBuilder** | Fast antibody backbone prediction (no diffusion); useful for screening 1000s of CDR sequences | 8 GB | https://github.com/oxpig/ImmuneBuilder | bundled via pip wheel | 2-10 s per antibody |
| **ThermoMPNN** | Thermal stability ΔTm prediction from sequence + structure | 8 GB | https://github.com/Kuhlman-Lab/ThermoMPNN | bundled in repo | < 5 s per variant |
| **Boltz-2** | Multi-chain folding with high accuracy; complements Protenix for ensembles | 24 GB | https://github.com/jwohlwend/boltz | https://huggingface.co/boltz-community | 1-5 min per complex |

**Notes:**
- VRAM figures are *recommended*. Smaller GPUs may work with `--low-memory` flags or batch=1 at the cost of latency.
- The "Typical runtime" assumes the GPU memory recommendation is met; running below the recommendation can be 3-10× slower or OOM.
- For tools with gated weights (AlphaFold3, some HuggingFace mirrors), the user must obtain access tokens before this skill can deploy them.

## Generic Builder Pattern

All four targets share the same six-field manifest. The generic builder
function is conceptually:

```python
from typing import Literal
from dataclasses import dataclass

Target = Literal["local", "runpod", "modal", "hpc"]

@dataclass
class Endpoint:
    target: Target
    tool: str
    url_or_path: str          # local path, RunPod URL, Modal URL, or HPC submit cmd
    config_patch: dict        # what to merge into .by/config.json

def deploy_tool(name: str, target: Target, config: dict) -> Endpoint:
    """Deploy `name` to `target` using a six-field manifest.

    The `config` dict must contain:
      - tool            : str   one of the Tool Catalog names
      - target          : str   one of: local | runpod | modal | hpc
      - image           : str   container image OR conda spec
      - weights_url     : str   upstream URL or HF model ID
      - entry_command   : str   exact CLI invocation the tool exposes
      - volumes         : list  persistent paths to mount (weights + outputs)

    Returns an Endpoint the agent records in .by/config.json.
    Implementation is split per-target across the references/*.md guides.
    """
    ...
```

**Concrete worked example — deploy Protenix to RunPod end-to-end:**

```yaml
# deploy_protenix_runpod.yaml — render of scripts/deploy_tool_template.yaml
tool: protenix
target: runpod
image: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
weights_url: "https://huggingface.co/ByteDance/Protenix"
entry_command: "python -m protenix.predict --input ${INPUT} --output ${OUTPUT} --device cuda"
volumes:
  - host: "/runpod-volume/weights"
    container: "/workspace/protenix/weights"
  - host: "/runpod-volume/outputs"
    container: "/workspace/protenix/outputs"
```

```bash
# 1. Verify the manifest parses
python3 -c "import yaml; yaml.safe_load(open('deploy_protenix_runpod.yaml'))"

# 2. Submit to RunPod
python3 scripts/runpod_deploy.py deploy_protenix_runpod.yaml
# → prints pod_id=abc123 and endpoint=https://abc123-8000.proxy.runpod.net

# 3. Update config
# (the runpod_deploy.py script writes the patch to .by/config.json automatically)

# 4. Smoke test against the endpoint
curl -X POST "https://abc123-8000.proxy.runpod.net/predict" \
  -H "Content-Type: application/json" \
  -d @smoke_input.json
```

The same manifest, with `target: local`, drives `references/local-gpu-setup.md`
to clone+install Protenix locally. With `target: modal`, it drives the
`modal.Image` builder in `references/modal-setup.md`. With `target: hpc`, it
drives the SLURM submission script template.

## Decision Points

**Local vs Cloud:** Decision rule above. Local wins if you have ≥ 24 GB VRAM
and care about iteration speed; cloud wins if you don't, or you need a bigger
GPU than you own.

**Conda vs Docker (local/HPC only):** Conda is faster to install and easier to
debug; Docker is more reproducible across machines and avoids dependency hell.
Pick Conda for one-machine setups, Docker for multi-machine or shared
environments. References include both.

**Weights cache: per-tool vs shared:** Per-tool is simpler; shared
(`~/.cache/huggingface/`) saves disk when tools share base models (Boltz-2
shares ESM with Protenix; BoltzGen shares Boltz with Boltz-2). Default to
shared; per-tool only if disk quota forces it.

**Pod lifecycle (RunPod):** "Spot" pods are 50% cheaper but can be reclaimed
mid-run. Use "on-demand" for production campaigns; spot only for
batch-resumable smoke tests.

## When Scripts Fail

If any script fails, follow the standard hierarchy. Deployment failures are
mostly environmental, not logic bugs.

1. **Fix and Retry (90%)** —
   - `check_gpu_env.sh` reports no GPU? Verify with `nvidia-smi`; reinstall drivers per `references/local-gpu-setup.md`.
   - `runpod_deploy.py` errors with `401`? `RUNPOD_API_KEY` is wrong or unset; re-export and retry.
   - YAML parse error in `deploy.yaml`? Run `python3 -c "import yaml; yaml.safe_load(open('deploy.yaml'))"` and fix the offending line.
2. **Modify Script (5%)** — Edit `deploy_tool_template.yaml` to add a field the upstream tool now requires (e.g., a new `--config` flag). Keep the 6-field core stable.
3. **Use as Reference (4%)** — If a tool's deployment is genuinely novel (e.g., a custom in-house diffusion model), read the closest existing recipe in `references/` and adapt.
4. **Write from Scratch (1%)** — Only when none of the patterns apply. Document why in `<workdir>/<tool>/deploy_notes.md` and contribute back to this skill.

If `RUNPOD_API_KEY` is missing, **never** silently fall back to Tamarind —
report the missing key, offer to switch the target to `local` or `modal`, and
let the user decide.

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `nvidia-smi: command not found` | NVIDIA driver not installed or PATH missing | Install driver ≥ 535 per distro; `which nvidia-smi` should resolve | [`references/local-gpu-setup.md`](references/local-gpu-setup.md) Driver Install |
| `CUDA out of memory` on first call | Tool default batch/length exceeds available VRAM | Lower `--batch-size 1`, enable `--low-memory`, or move to a bigger GPU | [`references/local-gpu-setup.md`](references/local-gpu-setup.md) VRAM Tuning |
| `RUNPOD_API_KEY` not set | User hasn't created or exported the key | Direct to RunPod console → Settings → API Keys; `export RUNPOD_API_KEY=...` | [`references/runpod-setup.md`](references/runpod-setup.md) API Key |
| Pod stuck in `STARTING` for > 10 min | Image still pulling or no capacity in region | Pick a different region or smaller GPU; check RunPod status page | [`references/runpod-setup.md`](references/runpod-setup.md) Pod Lifecycle |
| Modal cold start > 10 min | Image build runs on first call; weights not cached | Pre-build with `modal deploy`; mount a `modal.Volume` for weights; warm with `keep_warm=1` | [`references/modal-setup.md`](references/modal-setup.md) Cold Start Tuning |
| Weights download fails halfway | Flaky network; partial file in cache | Delete the partial `weights/` directory; retry with `--resume` or `aria2c -c` | [`references/local-gpu-setup.md`](references/local-gpu-setup.md) Weights Cache |
| HF model gated (e.g., AF3) | License acceptance required upstream | Direct user to the HF model page; accept the license; export `HF_TOKEN` | [`references/modal-setup.md`](references/modal-setup.md) HF Secrets |
| `nvcc --version` mismatches PyTorch CUDA version | Mixed CUDA toolkit and runtime versions | Reinstall PyTorch with the wheel matching the system CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu121` | [`references/local-gpu-setup.md`](references/local-gpu-setup.md) CUDA Matrix |
| Conda env solver hangs | Too many channels; conflicting pinned versions | Switch to `mamba`; use a minimal `environment.yml`; pin Python exactly | [`references/local-gpu-setup.md`](references/local-gpu-setup.md) Conda |
| SLURM job killed at runtime | Time limit too short or GPU partition wrong | Increase `--time`; verify partition with `sinfo`; request more memory with `--mem` | SKILL.md HPC notes |
| RunPod pod survives but endpoint 502s | Tool process crashed inside the pod | SSH in: `runpodctl exec <id> -- bash`; check `journalctl -u <tool>` or process logs | [`references/runpod-setup.md`](references/runpod-setup.md) Troubleshooting |
| Modal function times out at 300 s | Default function timeout too low for big folds | Set `@app.function(timeout=3600)` on the GPU function | [`references/modal-setup.md`](references/modal-setup.md) Function Config |
| macOS user runs `check_gpu_env.sh` and gets `✗ No NVIDIA GPU` | Apple Silicon — no CUDA path | Skill prints macOS notice; advise switching to RunPod / Modal target | `scripts/check_gpu_env.sh` |
| `.by/config.json` has stale `endpoint_url` after pod terminated | Pod was reclaimed (spot) or expired (auto-terminate) | Re-run `runpod_deploy.py` to get a new pod; update config | [`references/runpod-setup.md`](references/runpod-setup.md) Pod Lifecycle |
| Permission denied writing weights to `/workspace/...` | Pod volume not mounted or wrong mount path | Confirm the `volumes` block in `deploy.yaml`; check `mount` output inside the pod | SKILL.md Generic Builder |

## Best Practices

1. 🚨 **CRITICAL: Run `scripts/check_gpu_env.sh` before every deployment.** Stale driver state is the single biggest cause of deployment failures.
2. ✅ **REQUIRED: One `deploy.yaml` per tool, committed alongside the install.** It is the only artifact that captures the exact deployment shape.
3. ✅ **REQUIRED: Smoke test before declaring done.** A clean install with a failing smoke test is worse than no install — it lies to downstream skills.
4. ✅ **REQUIRED: Update `.by/config.json` in the same session as the deployment.** Otherwise the design agent can't find the tool.
5. ✅ Prefer a shared HuggingFace cache (`HF_HOME=~/.cache/huggingface`) — multiple tools share base weights.
6. ✅ Use persistent volumes on RunPod and Modal — re-downloading weights costs money and 20+ minutes.
7. ✅ Pin CUDA, PyTorch, and the tool's commit hash in `deploy.yaml` — "latest" is the enemy of reproducibility.
8. ✅ For HPC, write the `submit.sbatch` once and parameterize via env vars (`INPUT`, `OUTPUT`) — never hand-edit per run.
9. ❌ Do NOT mix conda and system pip in the same env — one or the other.
10. ❌ Do NOT silently fall back to Tamarind when local fails — surface the error, let the user choose.
11. ✨ **Optional:** Bake a Docker image of the full local install so a new workstation comes up in one `docker run`.
12. ✨ **Optional:** Add a `make smoke` target in `<workdir>/<tool>/` so re-validation is one command.

## Suggested Next Steps

After a successful deployment, chain into these skills in order:

1. **`by-session`** — re-run to confirm the updated `.by/config.json` resolves and the new tool is now discoverable. Required before any campaign can use it.
2. **The tool's engine skill** — `protenix`, `boltzgen`, or `pxdesign` — to actually invoke the freshly deployed tool against real inputs. Each engine skill assumes deployment is already complete.
3. **`by-campaign-manager`** — if the deployment was prerequisite for a planned campaign, mark the deployment task complete in the campaign plan and start the next phase.
4. **`by-failure-diagnosis`** — only if the smoke test failed and you cannot get past it after applying the Common Issues table.

The chain is intentional: deployment is plumbing. As soon as it's done, the
agent should pop back to whatever skill triggered the deployment request and
continue the campaign.

## Related Skills

**Upstream (often calls this skill):**
- `by-session` — discovers missing tools and triggers this skill to install them.
- `by-design-workflow` — when a planned campaign needs a tool not yet installed.

**Downstream (use the deployed tool):**
- `protenix` — folding via the deployed Protenix endpoint.
- `boltzgen` — antibody/nanobody design via the deployed BoltzGen endpoint.
- `pxdesign` — de novo binder design via the deployed PXDesign endpoint.
- `by-screening` — orchestrates screening tools (ImmuneBuilder, ThermoMPNN) that this skill installs.

**Alternative / complementary:**
- Tamarind cloud path — if `compute.default_provider = "tamarind"`, this skill is not needed; the agent calls Tamarind directly. Tamarind is a **fallback**, not a default.

## References

**Detailed documentation:**
- [`references/runpod-setup.md`](references/runpod-setup.md) — account creation, API key, pod templates by CUDA version, persistent volumes, networking, GPU price list, troubleshooting.
- [`references/local-gpu-setup.md`](references/local-gpu-setup.md) — VRAM requirements per tool, driver installation, CUDA/cuDNN matrix, conda env patterns, Docker alternative, smoke tests.
- [`references/modal-setup.md`](references/modal-setup.md) — `modal.Image` patterns, GPU selection, HuggingFace token wiring, cold-start optimization, persistent weight volumes, function timeouts.

**Scripts:**
- [`scripts/check_gpu_env.sh`](scripts/check_gpu_env.sh) — prints CUDA version, GPU count, free VRAM; exits non-zero with install hints if no GPU.
- [`scripts/deploy_tool_template.yaml`](scripts/deploy_tool_template.yaml) — 6-field deployment manifest with 3 worked examples (Protenix/RunPod, BoltzGen/local, ImmuneBuilder/Modal).
- [`scripts/runpod_deploy.py`](scripts/runpod_deploy.py) — CLI that reads a deploy YAML, submits to the RunPod API, prints pod ID + endpoint URL, and patches `.by/config.json`.

**Official documentation:**
- RunPod API: https://docs.runpod.io/
- Modal: https://modal.com/docs
- SLURM: https://slurm.schedmd.com/documentation.html
- NVIDIA CUDA: https://docs.nvidia.com/cuda/
- HuggingFace Hub: https://huggingface.co/docs/hub

**Key Papers:**
- Abramson et al. (2024) "AlphaFold 3" — [Nature](https://doi.org/10.1038/s41586-024-07487-w)
- Krishna et al. (2024) "Generalized biomolecular modeling and design with RoseTTAFold All-Atom" — [Science](https://doi.org/10.1126/science.adl2528)
- Watson et al. (2023) "De novo design of protein structure and function with RFdiffusion" — [Nature](https://doi.org/10.1038/s41586-023-06415-8)

**License:** All packages referenced in this skill's installation table
permit commercial use in AI applications. Per-tool licenses vary — verify
upstream before commercial deployment.
