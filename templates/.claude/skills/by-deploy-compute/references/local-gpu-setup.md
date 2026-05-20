# Local GPU Setup Reference

How to install BY design tools on a workstation you own. This is the default
deployment surface (`compute.default_provider = "local"`) and the cheapest
option once you own the hardware.

---

## 1. Hardware Requirements

Per-tool **recommended** VRAM (typical inputs ≤ 600 residues / chain, ≤ 4
chains, default sampling):

| Tool | Min VRAM | Recommended VRAM | CPU RAM | Disk |
|------|----------|------------------|---------|------|
| Protenix | 16 GB | 24 GB | 32 GB | 30 GB weights |
| BoltzGen | 24 GB | 40 GB | 64 GB | 25 GB weights |
| PXDesign (RFdiffusion) | 16 GB | 24 GB | 32 GB | 5 GB weights |
| AlphaFold2 (multimer) | 16 GB (mem-eff) | 40 GB | 64 GB | 600 GB MSA DB |
| AlphaFold3 | 24 GB | 40 GB | 64 GB | 100 GB weights + MSA |
| RFAntibody | 16 GB | 24 GB | 32 GB | 5 GB weights |
| ImmuneBuilder | 4 GB | 8 GB | 16 GB | 2 GB weights |
| ThermoMPNN | 4 GB | 8 GB | 16 GB | < 1 GB weights |
| Boltz-2 | 16 GB | 24 GB | 32 GB | 15 GB weights |

**Practical sweet spots:**
- **24 GB consumer card** (RTX 3090 / 4090) — runs everything except multi-chain AF3 / BoltzGen on huge inputs
- **48 GB workstation card** (A6000 / RTX 6000 Ada) — comfortably runs the full toolchain at production sizes
- **80 GB datacenter card** (A100 80GB / H100) — overkill for single-target work; reserve for batched throughput

**Disk:** Allocate at least 200 GB on the `<workdir>` filesystem. Shared
HuggingFace cache (`HF_HOME=~/.cache/huggingface/`) keeps weights from
duplicating across tools.

---

## 2. Verify the GPU

Always start with the skill's environment check:

```bash
bash <path-to-skill>/scripts/check_gpu_env.sh
```

Expected output:

```
✓ NVIDIA driver detected (535.x or higher)
✓ CUDA runtime: 12.4
✓ Detected 1 GPU(s):
  GPU 0: NVIDIA GeForce RTX 4090, 24564 MiB free / 24564 MiB total
```

If you see `✗ No NVIDIA GPU detected`, you are on a non-NVIDIA host (Apple
Silicon, AMD GPU, CPU-only). Switch to a cloud surface (RunPod or Modal).

---

## 3. Driver Install

### Ubuntu 22.04 / 24.04

```bash
# Remove old drivers
sudo apt purge -y nvidia-* libnvidia-*
sudo apt autoremove -y

# Add NVIDIA repo
distro=ubuntu2204
wget https://developer.download.nvidia.com/compute/cuda/repos/${distro}/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update

# Install driver + CUDA toolkit (matched versions)
sudo apt install -y cuda-drivers-550 cuda-toolkit-12-4

# Reboot
sudo reboot
```

After reboot:

```bash
nvidia-smi
# → driver version, CUDA version, GPU list
nvcc --version
# → toolkit version (should match the driver's reported CUDA)
```

### Other distros

- **RHEL/Rocky**: use NVIDIA's `cuda-repo-rhel9-*.rpm` and `dnf install cuda-drivers`.
- **Arch**: `sudo pacman -S nvidia cuda cudnn`.
- **WSL2 (Windows 11)**: install the host Windows driver only; the WSL distro gets CUDA via the Microsoft kernel passthrough. Inside WSL: `sudo apt install cuda-toolkit-12-4`.

### CUDA / cuDNN / PyTorch Version Matrix

Mixing versions is the most common deployment failure. Pin all three:

| PyTorch | CUDA Toolkit | cuDNN | Driver Minimum | Wheel Tag |
|---------|--------------|-------|----------------|-----------|
| 2.4.x | 12.4 | 9.1 | 535 | `+cu124` |
| 2.4.x | 12.1 | 8.9 | 525 | `+cu121` |
| 2.2.x | 12.1 | 8.9 | 525 | `+cu121` |
| 2.0.x | 11.8 | 8.7 | 520 | `+cu118` |

Install PyTorch with the wheel that matches your system CUDA:

```bash
# Example for CUDA 12.4
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Example for CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 4. Conda Environment Conventions

One conda env per tool. Naming convention: `by-<tool>` (e.g., `by-protenix`,
`by-boltzgen`). This matches `compute.local.<tool>.conda_env` in
`.by/config.json`.

```bash
# Bootstrap a new env (use mamba if available — much faster solver)
mamba create -n by-protenix python=3.11 -y
mamba activate by-protenix

# Install PyTorch first, with the right CUDA wheel
pip install torch --index-url https://download.pytorch.org/whl/cu124

# Then install the tool's requirements
git clone https://github.com/bytedance/Protenix.git $WORKDIR/protenix
cd $WORKDIR/protenix
pip install -e .

# Verify CUDA is visible from PyTorch
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# → True NVIDIA GeForce RTX 4090
```

**Anti-patterns:**
- ❌ Installing all tools into one mega-env — version conflicts will break things weeks later
- ❌ `sudo pip install` — leaks into the system Python; impossible to clean up
- ❌ Skipping the CUDA wheel and letting pip pull the default (`+cpu` or `+cu118` for older Torch)

---

## 5. Docker Alternative

If conda is brittle on your distro, or you want a one-command reproducible
setup, use Docker.

```bash
# Pull the NVIDIA PyTorch base
docker pull nvcr.io/nvidia/pytorch:24.07-py3

# Run with GPU access (NVIDIA Container Toolkit required)
docker run --gpus all \
  -v $WORKDIR/weights:/workspace/weights \
  -v $WORKDIR/outputs:/workspace/outputs \
  -it nvcr.io/nvidia/pytorch:24.07-py3 bash

# Inside the container, install the tool
pip install -e /workspace/protenix
```

**NVIDIA Container Toolkit install (one-time):**

```bash
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/${distribution}/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 6. Weights Cache

Most BY tools pull weights from HuggingFace. Set a shared cache to avoid
duplicate downloads:

```bash
export HF_HOME=$WORKDIR/.cache/huggingface
# Or, system-wide:
echo 'export HF_HOME=$HOME/.cache/huggingface' >> ~/.zshrc
```

**Pre-downloading weights** (recommended for offline use):

```bash
huggingface-cli download ByteDance/Protenix --local-dir $WORKDIR/weights/protenix
huggingface-cli download boltz-community/boltz1 --local-dir $WORKDIR/weights/boltz
```

**Gated models:** AlphaFold3 weights require accepting DeepMind's research
license. Once accepted, set `HF_TOKEN`:

```bash
huggingface-cli login
# Or: export HF_TOKEN=hf_xxxxxxxxxxxxxxxx
```

---

## 7. Smoke Tests

After every install, run a smoke test before declaring the deployment done.

### Protenix

```bash
mamba activate by-protenix
cd $WORKDIR/protenix
python -m protenix.predict \
  --input examples/6OFS_chainA.fasta \
  --output /tmp/protenix_smoke/ \
  --device cuda 2>&1 | tee smoke_test.log
ls /tmp/protenix_smoke/
# Expect: model_0.cif, confidence.json
```

### BoltzGen

```bash
mamba activate by-boltzgen
cd $WORKDIR/boltzgen
boltz design --config examples/nanobody_small.yaml --out /tmp/boltzgen_smoke/ 2>&1 | tee smoke_test.log
ls /tmp/boltzgen_smoke/
# Expect: designs/, scores.csv
```

### PXDesign

```bash
mamba activate by-pxdesign
cd $WORKDIR/pxdesign
python scripts/run_inference.py \
  inference.input_pdb=examples/insulin.pdb \
  inference.output_prefix=/tmp/pxdesign_smoke/run \
  inference.num_designs=2 2>&1 | tee smoke_test.log
ls /tmp/pxdesign_smoke/
# Expect: run_0.pdb, run_1.pdb
```

If any smoke test fails, do not update `.by/config.json`. Diagnose using the
Common Issues table in the main SKILL.md.

---

## 8. VRAM Tuning

When a tool throws `CUDA out of memory` on your GPU:

1. **Lower batch size**: most tools have `--batch-size 1` or equivalent.
2. **Enable memory-efficient attention**: `--use-flash-attn` (where supported) or set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
3. **Reduce sampling counts**: e.g., BoltzGen `--num-samples 50` instead of 200.
4. **Trim input length**: split long chains, prune flexible tails.
5. **Move to a bigger GPU**: if none of the above help, deploy to RunPod with an A6000 or A100.

```bash
# Quick check: how much VRAM is free right now?
nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits
# → free MiB per GPU
```

---

## 9. Updating `.by/config.json`

Once smoke tests pass, patch the config:

```json
{
  "compute": {
    "default_provider": "local",
    "local": {
      "protenix": {
        "path": "/home/user/by/tools/protenix",
        "conda_env": "by-protenix",
        "binary": "python -m protenix.predict"
      },
      "boltzgen": {
        "path": "/home/user/by/tools/boltzgen",
        "conda_env": "by-boltzgen",
        "binary": "boltz design"
      }
    }
  }
}
```

The design agent reads this block to spawn sub-agents with the right env and
binary path.

---

## 10. Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `libnvidia-ml.so.1: not found` after kernel update | `sudo apt install --reinstall nvidia-driver-550`; reboot |
| `torch.cuda.is_available() == False` despite `nvidia-smi` working | PyTorch wheel doesn't match CUDA — reinstall with the correct `--index-url` |
| `OOM` immediately on a 24 GB card | A second process is holding VRAM — `nvidia-smi` to find the PID |
| Conda env solving for hours | Switch to `mamba`; pin Python; trim channels to `pytorch`, `nvidia`, `conda-forge` |
| `Permission denied` on `/dev/nvidia*` | User not in `video` group: `sudo usermod -aG video $USER`; log out and back in |
| Weights download stuck at 99% | Network flake; delete the partial file and retry with `--resume-download` |

---

## See Also

- Main skill: [`SKILL.md`](../SKILL.md)
- Cloud alternatives: [`runpod-setup.md`](runpod-setup.md), [`modal-setup.md`](modal-setup.md)
- GPU check script: [`../scripts/check_gpu_env.sh`](../scripts/check_gpu_env.sh)
- Deploy manifest: [`../scripts/deploy_tool_template.yaml`](../scripts/deploy_tool_template.yaml)
- NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
