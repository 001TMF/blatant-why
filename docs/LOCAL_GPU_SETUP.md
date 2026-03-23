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
# See https://protenix.github.io/pxdesign/ for detailed setup
```

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
Install all tools under `/data/proteus/`:
```
/data/proteus/
  proteus-design/   # BoltzGen
  PXDesign/         # PXDesign
  Protenix/         # Protenix
```

### Option C: Campaign Config
Set `compute.provider: "local"` in your campaign YAML.

## Verifying Installation
```bash
# Check tool detection
python -c "from proteus_cli.common import detect_local_tools; print(detect_local_tools())"

# Check GPU
nvidia-smi
```

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
Install BoltzGen/PXDesign/Protenix at `/opt/proteus/` (or set PROTEUS_SSH_TOOLS_PATH).

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
| Levitate Bio | $3.50-29/hr | ~30s overhead | RFAntibody pipeline |

*Assumes user owns the server
