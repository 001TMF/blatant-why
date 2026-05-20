#!/usr/bin/env bash
#
# check_gpu_env.sh — verify the local environment can host BY design tools.
#
# Purpose:
#   Reports CUDA version, GPU count, and free VRAM per GPU. Exits 0 on success,
#   non-zero with install hints on failure. Handles Linux (NVIDIA) and macOS
#   (Apple Silicon — no NVIDIA available).
#
# Inputs:
#   none (no CLI args)
#
# Outputs:
#   stdout summary; exit code 0 (GPU OK), 1 (no GPU), 2 (driver issue), 3 (mac)
#
# Example:
#   bash scripts/check_gpu_env.sh
#

set -u  # treat unset vars as errors; do NOT set -e — we want to handle failures

# ----- color helpers (no-op if stdout is not a TTY) ---------------------------
if [ -t 1 ]; then
  GREEN="\033[0;32m"
  YELLOW="\033[0;33m"
  RED="\033[0;31m"
  NC="\033[0m"
else
  GREEN=""
  YELLOW=""
  RED=""
  NC=""
fi

ok()    { printf "${GREEN}✓${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}!${NC} %s\n" "$1"; }
fail()  { printf "${RED}✗${NC} %s\n" "$1"; }

# ----- macOS (Apple Silicon) special case ------------------------------------
OS="$(uname -s)"
ARCH="$(uname -m)"

if [ "$OS" = "Darwin" ]; then
  if [ "$ARCH" = "arm64" ]; then
    fail "macOS Apple Silicon detected — NVIDIA GPUs are not available."
    echo ""
    echo "  BY design tools need CUDA. On macOS you have three options:"
    echo "    1. Use RunPod (cloud GPU)         — see references/runpod-setup.md"
    echo "    2. Use Modal (serverless GPU)     — see references/modal-setup.md"
    echo "    3. Use Tamarind (managed cloud)   — set compute.default_provider = 'tamarind'"
    echo ""
    echo "  Some tools (ImmuneBuilder, ThermoMPNN) have a CPU-only fallback that runs on Mac."
    echo "  Set compute.local.<tool>.device = 'cpu' in .by/config.json if you want to try."
    exit 3
  else
    warn "macOS Intel — no NVIDIA GPU. CUDA not supported."
    exit 3
  fi
fi

# ----- Linux: check for nvidia-smi -------------------------------------------
if ! command -v nvidia-smi >/dev/null 2>&1; then
  fail "nvidia-smi not found on PATH."
  echo ""
  echo "  This usually means the NVIDIA driver is not installed. To fix:"
  echo "    Ubuntu/Debian:  sudo apt install nvidia-driver-550 cuda-toolkit-12-4"
  echo "    RHEL/Rocky:     sudo dnf install cuda-drivers cuda-toolkit-12-4"
  echo "    Arch:           sudo pacman -S nvidia cuda cudnn"
  echo ""
  echo "  After install, reboot and re-run this script."
  echo "  See references/local-gpu-setup.md for the full driver install guide."
  exit 1
fi

# ----- run nvidia-smi to get driver + CUDA -----------------------------------
NVIDIA_SMI_OUT="$(nvidia-smi 2>&1)"
NVIDIA_SMI_EXIT=$?

if [ $NVIDIA_SMI_EXIT -ne 0 ]; then
  fail "nvidia-smi ran but errored out (exit $NVIDIA_SMI_EXIT)."
  echo ""
  echo "$NVIDIA_SMI_OUT" | head -5
  echo ""
  echo "  Common causes:"
  echo "    - Kernel module not loaded:  sudo modprobe nvidia"
  echo "    - Driver / kernel mismatch:  sudo apt install --reinstall nvidia-driver-550 && reboot"
  echo "    - User not in 'video' group: sudo usermod -aG video \$USER  (then log out / log in)"
  exit 2
fi

# Extract driver and CUDA versions from nvidia-smi header
DRIVER_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)"
CUDA_VERSION="$(nvidia-smi 2>/dev/null | awk -F'CUDA Version: ' '/CUDA Version/ {print $2}' | awk '{print $1}' | head -1)"

if [ -z "$DRIVER_VERSION" ]; then
  fail "Could not parse driver version from nvidia-smi."
  exit 2
fi

ok "NVIDIA driver detected (version $DRIVER_VERSION)"
if [ -n "$CUDA_VERSION" ]; then
  ok "CUDA runtime: $CUDA_VERSION"
else
  warn "CUDA runtime version could not be parsed; check 'nvidia-smi' output manually."
fi

# ----- GPU count and per-GPU memory ------------------------------------------
GPU_LIST="$(nvidia-smi --query-gpu=index,name,memory.free,memory.total --format=csv,noheader,nounits 2>/dev/null)"
GPU_COUNT="$(echo "$GPU_LIST" | wc -l | tr -d ' ')"

if [ "$GPU_COUNT" -lt 1 ] || [ -z "$GPU_LIST" ]; then
  fail "nvidia-smi reports 0 GPUs visible to the system."
  echo ""
  echo "  Driver loaded but no devices. Check:"
  echo "    lspci | grep -i nvidia       # is the card detected by PCI?"
  echo "    dmesg | grep -i nvidia       # any kernel-level errors?"
  exit 1
fi

ok "Detected $GPU_COUNT GPU(s):"
echo "$GPU_LIST" | while IFS=, read -r idx name free total; do
  # Trim whitespace
  idx="${idx// /}"
  name="$(echo "$name" | sed 's/^ *//;s/ *$//')"
  free="${free// /}"
  total="${total// /}"
  # Decide on a status hint based on free VRAM
  if [ "$free" -ge 24000 ]; then
    hint="(plenty for any BY tool)"
  elif [ "$free" -ge 16000 ]; then
    hint="(OK for Protenix / PXDesign; BoltzGen tight)"
  elif [ "$free" -ge 8000 ]; then
    hint="(small models only: ImmuneBuilder, ThermoMPNN)"
  else
    hint="(too low for BY tools — close other GPU processes)"
  fi
  printf "  GPU %s: %s — %s MiB free / %s MiB total %s\n" "$idx" "$name" "$free" "$total" "$hint"
done

# ----- nvcc check (optional but useful) ---------------------------------------
if command -v nvcc >/dev/null 2>&1; then
  NVCC_VERSION="$(nvcc --version 2>/dev/null | grep release | awk '{print $5}' | tr -d ',')"
  ok "nvcc toolkit version: $NVCC_VERSION"
  if [ -n "$CUDA_VERSION" ] && [ -n "$NVCC_VERSION" ]; then
    # Compare major.minor only
    DRV_MAJOR="${CUDA_VERSION%%.*}"
    NVCC_MAJOR="${NVCC_VERSION%%.*}"
    if [ "$DRV_MAJOR" != "$NVCC_MAJOR" ]; then
      warn "Driver CUDA ($CUDA_VERSION) and nvcc ($NVCC_VERSION) major versions differ."
      warn "Pin PyTorch wheel to the driver's CUDA: --index-url https://download.pytorch.org/whl/cu${DRV_MAJOR}x"
    fi
  fi
else
  warn "nvcc not on PATH. Tool builds that compile CUDA kernels (rare) may fail."
  warn "Install with: sudo apt install cuda-toolkit-${DRIVER_VERSION%%.*}-${DRIVER_VERSION#*.}"
fi

# ----- PyTorch quick check (only if python3 is available) --------------------
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import torch" 2>/dev/null; then
    PT_CUDA="$(python3 -c 'import torch; print(torch.cuda.is_available(), torch.version.cuda)' 2>/dev/null)"
    ok "PyTorch importable; torch.cuda: $PT_CUDA"
  else
    warn "PyTorch not installed in this python3. Install per-env later — not a blocker."
  fi
fi

echo ""
ok "Environment looks ready for BY tool deployment."
echo "  Next: render scripts/deploy_tool_template.yaml for the tool you want, then follow"
echo "  references/local-gpu-setup.md (or runpod-setup.md / modal-setup.md for cloud)."

exit 0
