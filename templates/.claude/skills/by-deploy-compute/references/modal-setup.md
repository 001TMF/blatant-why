# Modal Setup Reference

How to deploy BY design tools to [Modal](https://modal.com) — a serverless
GPU runtime that scales to zero when idle and bills per-second when active.
Modal sits in the `hpc` provider slot when `compute.hpc.target = "modal"`.

Modal's sweet spot for BY:
- Bursty workloads (one campaign every few days)
- Tools you want exposed as an HTTP endpoint with no pod babysitting
- Free tier ($30/mo credits) is enough for ~50 hours of T4 or ~5 hours of H100
- Persistent volumes for weights so cold starts don't re-download model files

---

## 1. Account & CLI

1. Sign up at https://modal.com/signup.
2. Install the CLI:

   ```bash
   pip install modal
   ```

3. Authenticate (one-time, per workstation):

   ```bash
   modal token new
   # → opens a browser; approve; CLI saves token to ~/.modal.toml
   ```

4. Verify:

   ```bash
   modal token current
   # → prints workspace + token expiry
   ```

---

## 2. `modal.Image` Pattern

Every tool deployed to Modal is wrapped in a `modal.Image` that defines its
runtime. The pattern is identical across tools:

```python
import modal

# 1. Base image — pick the right CUDA version
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04",
        add_python="3.11",
    )
    # 2. System deps the tool needs
    .apt_install("git", "wget", "build-essential")
    # 3. Python deps — pin everything
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        index_url="https://download.pytorch.org/whl/cu124",
    )
    # 4. Clone the tool repo at a pinned commit
    .run_commands(
        "git clone https://github.com/bytedance/Protenix.git /opt/protenix",
        "cd /opt/protenix && git checkout v0.5.0 && pip install -e .",
    )
    # 5. Env vars
    .env({"HF_HOME": "/cache/huggingface"})
)

app = modal.App("by-protenix")
```

**Why this pattern:**
- The image is built once and cached in Modal's registry.
- Pinning the git commit + CUDA + Torch versions makes the deployment reproducible six months later.
- Splitting `apt_install` from `pip_install` from `run_commands` keeps cache layers small — editing one step doesn't invalidate the others.

---

## 3. GPU Function

A Modal "function" is a serverless invocation that runs on the GPU you ask
for. The decorator picks GPU type, mounts secrets, and timeout.

```python
@app.function(
    image=image,
    gpu="A100-40GB",                                  # see GPU table below
    timeout=3600,                                     # seconds; default is 300
    volumes={"/cache/huggingface": modal.Volume.from_name("hf-cache", create_if_missing=True)},
    secrets=[modal.Secret.from_name("huggingface-token")],
)
def predict(input_pdb_bytes: bytes) -> bytes:
    """Run Protenix prediction inside a Modal function.

    Args:
      input_pdb_bytes: Raw PDB or FASTA file contents.
    Returns:
      Raw bytes of the predicted CIF file.
    """
    import subprocess, tempfile, pathlib
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "input.fasta").write_bytes(input_pdb_bytes)
        subprocess.run(
            ["python", "-m", "protenix.predict",
             "--input", str(tmp / "input.fasta"),
             "--output", str(tmp / "out"),
             "--device", "cuda"],
            check=True,
        )
        return (tmp / "out" / "model_0.cif").read_bytes()
```

---

## 4. GPU Selection & Pricing

Modal pricing as of 2026 — always check the [Modal pricing page](https://modal.com/pricing)
for live rates.

| GPU Type Spec | VRAM | $/hr | Cold Start | Best For |
|---------------|------|------|-----------|----------|
| `T4` | 16 GB | $0.59 | 2-4 min | ImmuneBuilder, ThermoMPNN smoke tests |
| `L4` | 24 GB | $0.80 | 2-5 min | Protenix small inputs |
| `A10G` | 24 GB | $1.10 | 2-5 min | RFAntibody, PXDesign |
| `A100-40GB` | 40 GB | $2.10 | 3-7 min | BoltzGen, full Protenix, AF3 |
| `A100-80GB` | 80 GB | $2.78 | 3-7 min | Long sequences, multi-chain folding |
| `H100` | 80 GB | $4.56 | 4-10 min | Fastest; only when latency matters |

**Free tier:** $30/month credits. That buys ≈ 50 h on T4, ≈ 14 h on A100-40,
≈ 6.5 h on H100. Burns down monthly; no rollover.

---

## 5. HuggingFace Secret Wiring

Tools with gated weights (AlphaFold3, sometimes RFAntibody) need a HF token.

```bash
# Create the secret in Modal
modal secret create huggingface-token HF_TOKEN=hf_xxxxxxxxxxxxxxxx
```

Then attach to any function that needs it:

```python
@app.function(
    image=image,
    gpu="A100-40GB",
    secrets=[modal.Secret.from_name("huggingface-token")],
)
def predict(...):
    import os
    assert os.environ["HF_TOKEN"], "HF_TOKEN missing"
    ...
```

Modal injects the secret as an env var at runtime. Never commit the token to
git or paste it into the image build steps.

---

## 6. Persistent Weight Volumes

Weights are slow to download (10-30 min for Protenix; 50 GB+). Cache them in
a `modal.Volume`:

```python
hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

@app.function(
    image=image,
    gpu="A100-40GB",
    volumes={"/cache/huggingface": hf_cache},
)
def predict(...):
    # HF_HOME=/cache/huggingface from the image; first call downloads + caches.
    # Subsequent calls find the weights already on disk.
    ...
```

**Pre-warming the cache** (run once, then never again):

```python
@app.function(image=image, gpu="T4", volumes={"/cache/huggingface": hf_cache}, timeout=1800)
def prefetch_weights():
    from huggingface_hub import snapshot_download
    snapshot_download("ByteDance/Protenix", local_dir="/cache/huggingface/protenix")
    hf_cache.commit()
    print("✓ weights cached")
```

```bash
modal run app.py::prefetch_weights
```

The first prediction after pre-warming starts in 30 s instead of 25 min.

---

## 7. Cold-Start Optimization

Cold-start latency is Modal's biggest weakness for interactive use. Options:

| Strategy | Cold Start | Cost Impact |
|----------|-----------|-------------|
| Default (scale-to-zero) | 2-10 min | Cheapest |
| `keep_warm=1` on the function | < 5 s | One container always alive — billed continuously |
| Pre-warm via scheduled cron | Reduces to 30 s for next call | Modest extra hours |
| Use `modal.Volume` weight cache | -15 min from cold | Free (Volume storage is cheap) |
| Pin a minimal image | -1 to -2 min | Free |

For production endpoints, set `keep_warm=1` and accept the always-on cost.
For dev / bursty use, scale-to-zero with a Volume cache is the right balance.

```python
@app.function(
    image=image,
    gpu="A100-40GB",
    keep_warm=1,           # production: 1 warm container always
    volumes={"/cache/huggingface": hf_cache},
)
def predict(...):
    ...
```

---

## 8. Exposing as HTTP

To call the function from outside Modal (e.g., from `.by/config.json`
endpoint URL), use `modal.web_endpoint`:

```python
@app.function(image=image, gpu="A100-40GB", volumes={"/cache/huggingface": hf_cache})
@modal.web_endpoint(method="POST")
def predict_http(input_pdb_bytes: bytes) -> bytes:
    return predict.local(input_pdb_bytes)
```

Deploy:

```bash
modal deploy app.py
# → prints https://<workspace>--by-protenix-predict-http.modal.run
```

Patch `.by/config.json`:

```json
{
  "compute": {
    "hpc": {
      "target": "modal",
      "endpoint_url": "https://<workspace>--by-protenix-predict-http.modal.run"
    }
  }
}
```

---

## 9. Complete Example: Protenix on Modal

```python
# app.py — full Protenix deployment to Modal
import modal

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "wget", "build-essential")
    .pip_install(
        "torch==2.4.0", "torchvision==0.19.0",
        index_url="https://download.pytorch.org/whl/cu124",
    )
    .run_commands(
        "git clone https://github.com/bytedance/Protenix.git /opt/protenix",
        "cd /opt/protenix && git checkout v0.5.0 && pip install -e .",
    )
    .env({"HF_HOME": "/cache/huggingface"})
)

app = modal.App("by-protenix")
hf_cache = modal.Volume.from_name("by-hf-cache", create_if_missing=True)

@app.function(
    image=image,
    gpu="A100-40GB",
    timeout=3600,
    volumes={"/cache/huggingface": hf_cache},
    secrets=[modal.Secret.from_name("huggingface-token")],
    keep_warm=1,
)
@modal.web_endpoint(method="POST")
def predict(payload: dict) -> dict:
    """POST /predict — body: {fasta: '...'} → returns {cif: '...', confidence: {...}}."""
    import subprocess, tempfile, pathlib, json
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "in.fasta").write_text(payload["fasta"])
        subprocess.run(
            ["python", "-m", "protenix.predict",
             "--input", str(tmp / "in.fasta"),
             "--output", str(tmp / "out"),
             "--device", "cuda"],
            check=True,
        )
        return {
            "cif": (tmp / "out" / "model_0.cif").read_text(),
            "confidence": json.loads((tmp / "out" / "confidence.json").read_text()),
        }
```

Deploy and use:

```bash
modal deploy app.py
# → endpoint URL printed

# Smoke test
curl -X POST "<endpoint>" -H "Content-Type: application/json" \
  -d '{"fasta": ">seq\nMVLSEGEWQ..."}'
```

---

## 10. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `modal: command not found` | CLI not installed | `pip install modal` |
| `not authenticated` | Token expired | `modal token new` |
| Function timeout at 300 s | Default timeout too short | Set `timeout=3600` (or longer) on the decorator |
| Cold start every call | Volume not mounted; image pulling weights each time | Add `modal.Volume`, set `HF_HOME` |
| `OOM` on T4 but tool spec says it should fit | T4 lacks BF16; some kernels OOM that fit on A10G | Move to `A10G` or `A100-40GB` |
| Image build hangs on `pip install` | Network flake in the build image | Re-run; consider mirroring wheels to a Modal Volume |
| `keep_warm` burning credits at idle | Not needed for dev workloads | Remove `keep_warm`; let it scale to zero |
| Web endpoint returns 500 with no logs | Function-level exception | `modal logs by-protenix` shows the traceback |
| HuggingFace 403 on gated weights | Token not attached or license not accepted | Accept license at HF model page; verify secret in `modal secret list` |

---

## See Also

- Main skill: [`SKILL.md`](../SKILL.md)
- Local-GPU alternative: [`local-gpu-setup.md`](local-gpu-setup.md)
- RunPod alternative: [`runpod-setup.md`](runpod-setup.md)
- Deploy manifest: [`../scripts/deploy_tool_template.yaml`](../scripts/deploy_tool_template.yaml)
- Modal docs: https://modal.com/docs
