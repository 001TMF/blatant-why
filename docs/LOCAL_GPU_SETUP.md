# Local GPU Setup Guide

## Prerequisites
- NVIDIA GPU with >=24GB VRAM (A100/H100 recommended, RTX 4090 minimum)
- CUDA 12.1+
- Python 3.10+
- ~50GB disk space for model weights

## Installing Tools

### BoltzGen (Antibody/Nanobody/Protein Design)
```bash
git clone https://github.com/HannesStark/boltzgen.git
cd boltzgen
pip install -e .
# Download weights (automatic on first run)
```

### PXDesign (De Novo Protein Binder Design)
```bash
git clone https://github.com/bytedance/PXDesign.git
cd PXDesign
pip install -e .

# Download model weights (required before first run)
bash download_tool_weights.sh

# CUTLASS dependency — required for PXDesign kernels
export CUTLASS_PATH=/path/to/cutlass
# See https://protenix.github.io/pxdesign/ for detailed setup
```

> **Note:** PXDesign is also available as a cloud option via Tamarind Bio
> (`tamarind_submit_job` with type `"pxdesign"`), which avoids local dependency
> management entirely.

### Protenix (Structure Prediction)
```bash
git clone https://github.com/bytedance/Protenix.git
cd Protenix
pip install -e .
```

## Configuration

### Option A: Environment Variables
```bash
# Add to ~/.bashrc or .env
export PROTEUS_AB_DIR=/path/to/boltzgen
export PROTEUS_PROT_DIR=/path/to/PXDesign
export PROTEUS_FOLD_DIR=/path/to/Protenix
```

### Option B: Default Paths
The default paths are configurable via environment variables. Example layout:
```
/opt/by/   # or any directory you choose
  boltzgen/      # BoltzGen (git clone https://github.com/HannesStark/boltzgen)
  PXDesign/         # PXDesign
  Protenix/         # Protenix
```

### Option C: Campaign Config
Set `compute.provider: "local"` in your campaign YAML.

## Verifying Installation

```bash
# Check tool detection (should show True only for configured tools)
python -c "from proteus_cli.common import detect_local_tools; print(detect_local_tools())"

# Check GPU
nvidia-smi

# Verify individual tools
by-ab --help    # BoltzGen (antibody/nanobody design)
pxdesign --help      # PXDesign (de novo protein binders)
protenix --help      # Protenix (structure prediction)
```

## Important Notes

### Conflicting Python Dependencies
BoltzGen, PXDesign, and Protenix may have conflicting Python dependency versions
(e.g., different PyTorch or NumPy requirements). Two recommended approaches:

1. **Separate conda environments** (recommended for local GPU):
   ```bash
   conda create -n boltzgen python=3.10 && conda activate boltzgen && pip install -e /path/to/boltzgen
   conda create -n pxdesign python=3.10 && conda activate pxdesign && pip install -e /path/to/PXDesign
   conda create -n protenix python=3.10 && conda activate protenix && pip install -e /path/to/Protenix
   ```

2. **Use Tamarind cloud** (no local dependencies needed):
   Set `TAMARIND_API_KEY` and run all tools via the cloud API. Free tier gives
   10 jobs/month — enough for preview campaigns.

### The `by-design` Package
The `by-design` PyPI package is the unified BoltzGen + Protenix pipeline
(also called BY-AB). It bundles BoltzGen diffusion with Protenix refolding
into a single `by-ab` CLI. If you install `by-design`, you get both
BoltzGen and Protenix in one environment.

## SSH Remote Setup

### On Your Local Machine
```bash
# Set SSH credentials
export PROTEUS_SSH_HOST=gpu-server.example.com
export PROTEUS_SSH_USER=researcher
export PROTEUS_SSH_KEY=~/.ssh/id_rsa

# Test connection
ssh -i ~/.ssh/id_rsa researcher@gpu-server.example.com "nvidia-smi"
```

### On the GPU Server
Install BoltzGen/PXDesign/Protenix at `/opt/by/` (or set PROTEUS_SSH_TOOLS_PATH).

## GPU Memory Requirements

| Tool | Minimum VRAM | Recommended | Notes |
|------|-------------|-------------|-------|
| BoltzGen | 16 GB | 40 GB+ | Scales with target size |
| PXDesign | 24 GB | 40 GB+ | Extended preset needs more |
| Protenix | 16 GB | 40 GB+ | Multi-seed needs more |

## Cost Comparison

| Provider | Cost | Latency | Best For |
|----------|------|---------|----------|
| Local GPU | $0/hr | Instant | Large campaigns, iteration |
| SSH Remote | $0/hr* | ~5s overhead | GPU clusters |
| Tamarind Bio | $2.50/hr | ~30s overhead | No GPU, getting started |

*Assumes user owns the server
