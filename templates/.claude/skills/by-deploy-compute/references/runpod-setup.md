# RunPod Setup Reference

Step-by-step deployment of BY design tools on [RunPod](https://www.runpod.io)
— a pay-per-second cloud GPU provider with no upfront commitment. This is the
primary `hpc` target when `compute.hpc.target = "runpod"` in `.by/config.json`.

---

## 1. Account & API Key

1. Create an account at https://www.runpod.io/console/signup.
2. Add a payment method or load credits (the workflows in this skill assume
   you have at least $20 in credits before the first deployment).
3. Generate an API key: **Console → User Settings → API Keys → Create API Key**.
4. Export the key in your shell:

   ```bash
   export RUNPOD_API_KEY="rpa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   # add to ~/.zshrc or ~/.bashrc to persist
   ```

5. Verify the key works:

   ```bash
   curl -H "Authorization: Bearer $RUNPOD_API_KEY" https://api.runpod.io/v2/user
   # → JSON response with your user info
   ```

❌ **DON'T:** commit `RUNPOD_API_KEY` to git, paste it into chat, or leave it
in shell history. Use a secret manager (`gpg`, `pass`, `1password`) for
long-term storage.

---

## 2. Pod Template Selection

A "template" defines the base Docker image plus default mounts. For BY tools,
choose the official PyTorch template that matches the CUDA version the tool
requires.

| CUDA Version | PyTorch Image Tag | Use For |
|--------------|-------------------|---------|
| 12.4 | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` | Protenix, BoltzGen, Boltz-2 (current default) |
| 12.1 | `runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04` | RFAntibody, PXDesign (still on Torch 2.2) |
| 11.8 | `runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04` | AlphaFold2 (legacy CUDA) |
| 12.4 (lighter) | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-runtime-ubuntu22.04` | ImmuneBuilder, ThermoMPNN (smaller models, runtime image OK) |

**Rule of thumb:** Match the tool's upstream CUDA requirement exactly. If the
repo's `requirements.txt` says `torch==2.4.0+cu124`, use the 12.4 devel image.

**Custom templates:** Once you've installed a tool on a pod, save the pod as
a template (Console → Pod → "Save as Template"). Future deployments of the
same tool start in seconds instead of 20+ minutes.

---

## 3. GPU Selection & Pricing

Prices are on-demand secure cloud (us-east) as of 2026; community cloud is
30-50% cheaper but less reliable. Always check the live price in the console
before deploying — these are subject to change.

| GPU | VRAM | $/hr (on-demand) | $/hr (spot) | Best For |
|-----|------|-----------------|-------------|----------|
| RTX A4000 | 16 GB | $0.17 | $0.10 | ImmuneBuilder, ThermoMPNN, smoke tests |
| RTX A5000 | 24 GB | $0.26 | $0.16 | Protenix small inputs, RFAntibody |
| RTX A6000 | 48 GB | $0.49 | $0.30 | BoltzGen, full Protenix, batch design |
| L40 | 48 GB | $0.69 | $0.42 | Same as A6000, faster on FP16 |
| L40S | 48 GB | $0.89 | $0.54 | Highest throughput in the 48 GB tier |
| A40 | 48 GB | $0.34 | $0.21 | Cheapest 48 GB option; great for BoltzGen |
| A100 PCIe | 40 GB | $1.19 | $0.74 | Large complexes; AF3 |
| A100 SXM | 80 GB | $1.89 | $1.13 | Multi-chain (10+) folding; long sequences |
| H100 PCIe | 80 GB | $2.49 | $1.49 | Fastest available; price-performance for production |

**Spot vs On-Demand:**
- **On-demand**: guaranteed availability, can run for days. Use for production campaigns.
- **Spot**: 40-60% cheaper, can be reclaimed with 30 s notice. Use only for batch-resumable smoke tests or quick experiments.

---

## 4. Persistent Volumes

Pods are ephemeral by default — the filesystem is wiped when the pod
terminates. To preserve downloaded weights and outputs:

1. **Create a Network Volume**: Console → Storage → Network Volumes → Create.
   - Size: 100 GB minimum (weights for BoltzGen + Protenix + Boltz-2 ≈ 50 GB).
   - Region: must match the pod region you'll deploy to.
2. **Mount it on the pod**: when creating the pod, set
   `Network Volume → /workspace` (or any mount path you prefer).
3. The pod sees the volume at `/workspace/` and writes survive pod death.

**Cost:** $0.07/GB/month. A 100 GB volume = ~$7/month — almost always worth
it vs re-downloading 50 GB of weights every time you spin up a pod.

**Mount layout convention** (used by `scripts/deploy_tool_template.yaml`):

```
/workspace/
├── weights/             # HuggingFace cache; shared across tools
│   └── ByteDance/Protenix/
├── outputs/             # Tool outputs; pulled back via rsync at end of run
└── <tool>/              # Cloned tool repo
    ├── deploy.yaml      # The manifest used to deploy this pod
    └── smoke_test.log
```

---

## 5. Networking & Security

By default, RunPod pods expose:
- **SSH** on port 22 (always; key-based)
- **HTTP proxy** at `https://<pod-id>-<port>.proxy.runpod.net` — any port the
  pod opens internally becomes reachable through this proxy

**Exposing the tool as an HTTP endpoint:**

1. In the pod environment, run the tool as a server, e.g.:

   ```bash
   uvicorn protenix.serve:app --host 0.0.0.0 --port 8000
   ```

2. Add `8000` to the pod's exposed ports (Console → Pod → Edit → Ports).
3. The proxy URL is `https://<pod-id>-8000.proxy.runpod.net`.
4. Store this URL in `.by/config.json` → `compute.hpc.endpoint_url`.

**Authentication:** The proxy is publicly reachable. Either:
- Add a shared-secret header check in the tool's server (recommended).
- Tunnel via SSH instead and bind to `127.0.0.1:8000` inside the pod, then
  `ssh -L 8000:localhost:8000 <pod>` from the client.

**Security groups:** Not exposed in the RunPod UI; the proxy is the only
external surface. To restrict by IP, use Cloudflare in front of the proxy URL.

---

## 6. Pod Lifecycle Management

```bash
# List your pods
runpodctl get pods

# Stop a pod (keeps state, saves cost; resume in minutes)
runpodctl stop pod <pod-id>

# Start a stopped pod
runpodctl start pod <pod-id>

# Terminate a pod (deletes everything not on a network volume)
runpodctl rm pod <pod-id>

# SSH into a running pod
runpodctl exec <pod-id> -- bash
```

**Auto-shutdown:** Set a pod-level idle timeout in the console to avoid
forgotten pods burning credits. Recommended: 60 min idle for dev pods, none
for production endpoints.

**Spot pod reclamation:** If a spot pod is reclaimed, the proxy URL goes
dead. The `scripts/runpod_deploy.py` script can be re-run with the same
manifest to provision a new pod and patch the config URL.

---

## 7. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `401 Unauthorized` from API | Wrong or expired API key | Regenerate at Console → User Settings; re-export `RUNPOD_API_KEY` |
| Pod stuck in `STARTING` > 10 min | Capacity issue in region | Try a different region or smaller GPU type |
| `proxy.runpod.net` returns 502 | Tool process not listening on the exposed port | SSH in, check `lsof -i :<port>`; restart the tool server |
| Pod uses GPU but `nvidia-smi` empty inside container | Image not CUDA-enabled, or `--gpus all` not passed | Pick a template with `cuda` in the name; verify GPU is attached in the pod summary |
| `Network volume not mounted` | Pod and volume in different regions | Recreate the volume in the same region as the pod, or pick a pod region that matches |
| Spot pod reclaimed mid-run | Expected; spot is preemptible | Resume from the network-volume checkpoint, or use on-demand for the next run |
| Credits exhausted, pod terminated | Auto-terminate when balance hits $0 | Top up before next run; set a low-balance alert in the console |

---

## 8. Cost Estimation Worksheet

For a typical antibody campaign on RunPod with BoltzGen + Protenix on an A40:

```
Step              | GPU runtime | $/hr | Cost
------------------|-------------|------|--------
BoltzGen design   | 1.5 h       | 0.34 | $0.51
Protenix refold   | 0.5 h       | 0.34 | $0.17
Network volume    | 100 GB·mo   | --   | ~$7/mo
Idle time         | --          | --   | $0 (auto-shutdown)
----------------------------------------------
Per-campaign     |             |      | < $1 of compute
```

A single A40 hour buys ~150 BoltzGen designs against a 1-chain epitope. Run
the math against the campaign size before deploying — if the campaign is
small (<100 designs), Modal or a local GPU is often cheaper.

---

## See Also

- Main skill: [`SKILL.md`](../SKILL.md)
- Local GPU alternative: [`local-gpu-setup.md`](local-gpu-setup.md)
- Modal alternative: [`modal-setup.md`](modal-setup.md)
- Deployment script: [`../scripts/runpod_deploy.py`](../scripts/runpod_deploy.py)
- Official RunPod docs: https://docs.runpod.io/
