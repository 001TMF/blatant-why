# Cost Model — Local, HPC, Tamarind

This reference quantifies the cost of running BY design campaigns on each of the
three supported compute targets. **Default provider is `local`** per
`templates/CLAUDE.md`; HPC RunPod is the bursty / large-memory option; Tamarind
is the managed-cloud fallback.

All numbers below are first-order estimates calibrated against typical BY runs.
They feed `scripts/estimate_campaign.py` and should be reviewed quarterly as
engines improve.

---

## Provider Selection

| Provider | Best For | Typical Constraint | Headline Cost |
|----------|----------|--------------------|---------------|
| **local** | Preview tiers, iterative work, small/medium campaigns, on-prem privacy | GPU VRAM (24–48 GB common); wall clock | **$0** (electricity not counted) |
| **hpc** (RunPod) | Antibody campaigns needing 40–80 GB cards; bursty production runs; team-shared cluster | $/hr by card class; queue time | $0.34–$2.89/hr per GPU |
| **tamarind** | No local or HPC available; managed runtime; Adaptyv handoff convenience | $/credit; per-design pricing | ~$2.50/hr GPU equivalent |

**Selection rule:**
1. Read `.by/config.json` `compute.default_provider`.
2. If `local` (the default) — try local first; never silently fall back.
3. If `hpc` — use the target in `compute.hpc.target` (RunPod by default). See `by-deploy-compute`.
4. If `tamarind` — submit via `mcp__by-cloud__cloud_submit_job`.
5. If `auto` — detect availability in priority order `local → hpc → tamarind`.

⚠️ **CRITICAL:** Never silently switch providers. If `compute.fallback_allowed` is
`false`, ask the user before switching.

---

## (a) Local GPU — Wall-Clock per Design

Local-first defaults. Times are wall-clock for a single A100 40 GB unless
otherwise noted. Other cards scale roughly linearly with FP16 TFLOPS.

| Engine | Operation | Wall-Clock per Design | VRAM Required |
|--------|-----------|-----------------------|---------------|
| **Protenix** | Single prediction | 2–5 min | 16–24 GB |
| **Protenix** | 5-seed ensemble | 10–25 min | 16–24 GB |
| **PXDesign** | Preview (5–10 designs total) | 2–4 min/design | 24–40 GB |
| **PXDesign** | Extended (20–50 designs total) | 3–6 min/design | 24–40 GB |
| **PXDesign** | Production (100+ designs total) | 4–8 min/design | 24–40 GB |
| **BoltzGen** | Nanobody (10–20 designs total) | 2–4 min/design | 24–40 GB |
| **BoltzGen** | Antibody (20–50 designs total) | 3–6 min/design | **40–80 GB** |
| **BoltzGen** | Large (50–100 designs total) | 3–6 min/design | 40–80 GB |

**Local cost = $0 USD** for the user-facing report; the actual marginal cost
(electricity, depreciation) is out of scope.

### GPU Requirements

- 24 GB cards (RTX 4090, A10): OK for Protenix and PXDesign; OK for VHH BoltzGen.
- 40 GB+ cards (A100 40GB, A6000): required for antibody BoltzGen.
- 80 GB cards (A100 80GB, H100): comfortable for any engine; speedup ~1.5× over 40 GB.

---

## (b) HPC RunPod — $/hr × Hours per Design

RunPod is the default HPC target. Prices below are spot-pool indicative rates
(May 2026) and float ±20%. The cost script reads live rates if available; it
otherwise uses these as a baseline.

| GPU Class | $/hr (spot) | $/hr (on-demand) | VRAM | Recommended For |
|-----------|-------------|-------------------|------|------------------|
| RTX 4090 | $0.34 | $0.69 | 24 GB | Protenix, VHH BoltzGen |
| A40 | $0.39 | $0.79 | 48 GB | PXDesign Extended, VHH |
| A100 40GB | $0.79 | $1.89 | 40 GB | Antibody BoltzGen baseline |
| A100 80GB | $1.49 | $2.69 | 80 GB | Antibody BoltzGen production |
| H100 PCIe | $2.49 | $4.89 | 80 GB | Throughput-bound antibody runs |

### Hours per Design (HPC)

Use the same wall-clock as local; multiply by GPU $/hr to get cost.

| Engine | Designs/hr (single A100 40GB) |
|--------|-------------------------------|
| Protenix single | 12–30 |
| PXDesign Extended | 10–20 |
| BoltzGen VHH | 15–30 |
| BoltzGen antibody | 10–20 |

**Example:** Standard antibody campaign, 50 designs, A100 40GB spot @ $0.79/hr:
- Wall clock ≈ 50 designs × 4 min = 200 min = 3.3 hr
- Cost ≈ 3.3 × $0.79 = **$2.61**

Plus screening overhead (see [Screening](#screening-overhead)).

### Queue Time

RunPod spot pools occasionally have queue times of 5–30 min. The estimator
applies a +15% wall-clock buffer for spot bookings.

---

## (c) Tamarind — Managed Cloud

Tamarind charges per-design or per-GPU-hour depending on the engine.

| Engine | Tamarind Pricing | Notes |
|--------|------------------|-------|
| BoltzGen | ~$0.009/design (3.6 sec each at $2.50/hr equivalent) | Per `src/proteus_cli/campaign/cost.py` |
| PXDesign | ~$2.50/hr GPU equivalent | Billed per GPU-hour |
| Protenix | ~$2.50/hr GPU equivalent | Billed per GPU-hour |

**Tamarind reference rate: $2.50/GPU-hr** for engines that bill on time.

### Example Tamarind Cost (matches local-first replacement story)

Standard VHH campaign, 2 scaffolds × 5000 designs = 10,000 designs:
- Design time: 10,000 × 0.001 hr = 10 GPU-hr → $25
- Screening: 100 ranked designs × 2 min = 3.3 GPU-hr → $8.25
- **Total: ~$33.25** + lab cost if applicable

The same campaign on local GPU: **$0** + ~12 hours wall clock on an A100 40GB.

---

## Per-Modality Scaling Factors

These multipliers apply on top of the base per-design times above.

| Modality | Scaling Factor | Reason |
|----------|----------------|--------|
| VHH (nanobody) | ×1.0 | Baseline |
| scFv (antibody) | ×1.5 | Two chains + paired CDR design |
| Bispecific scFv | ×2.0 | Two targeting domains + linker design |
| De novo protein binder (PXDesign) | ×1.2 | Topology search overhead |
| Long target (>500 aa) | ×1.3 | Folding context cost |
| Glycosylated target | ×1.4 | Modeling overhead + extra refold checks |

The cost script multiplies base time by the relevant factor before computing $.

---

## Screening Overhead

Screening adds modest CPU/GPU time on top of design generation:

| Step | Time per Design |
|------|-----------------|
| ipSAE (CPU) | 5–15 sec |
| Liability + developability (CPU) | <1 sec |
| Protenix refolding validation (GPU) | 2–5 min per top-N candidate |

Full screening battery for 30 designs ≈ 3–8 min CPU + 10–20 min GPU
(only for the top 5 refolded). Negligible vs design generation.

---

## Confidence Intervals

`estimate_campaign.py` reports a low/high range for each provider. Defaults:

- **Local:** ±25% on wall clock (GPU variability, contention).
- **HPC RunPod spot:** ±20% on cost (rate float), +15% buffer on time (queue).
- **HPC RunPod on-demand:** ±10% on cost.
- **Tamarind:** ±10% on cost (rate fixed by Tamarind).

Confidence is wider for novel targets due to early-failure restarts.

---

## Composite Cost Formula

```
total_cost_usd = (design_gpu_hours + screening_gpu_hours) * hourly_rate + lab_cost
design_gpu_hours = total_designs * minutes_per_design / 60 * modality_factor
screening_gpu_hours = ranked_designs * screening_minutes_per_design / 60
hourly_rate = {local: 0, hpc: <see GPU class table>, tamarind: 2.50}
lab_cost = max_candidates * cost_per_variant
```

This formula matches `src/proteus_cli/campaign/cost.py` for backward
compatibility; the script extends it with per-provider rates and modality
scaling.

---

## Cost Reporting Format

The estimator prints a comparative table:

```
Campaign: standard tier | vhh | 2 scaffold(s)
Designs: 10,000 total (5,000/scaffold) -> 100 ranked

Provider          Wall Clock     Cost USD       Notes
----------------------------------------------------------------
local             ~12 hr         $0             on-prem GPU
hpc (RunPod A100) ~10 hr         $7.90 ± $1.60  spot pool
tamarind          ~12 hr         $33.25 ± $3.32 managed

Recommendation: local (default, $0). HPC if local card <40 GB.
```

---

## When to Override Defaults

- Antibody campaign + local card has <40 GB → recommend HPC.
- Time-sensitive (need results in <2 hr) → recommend HPC on-demand or Tamarind.
- Multi-target batch (>5 targets) → recommend HPC for parallel job slots.
- Adaptyv lab handoff at end → Tamarind can simplify the bridge but is not required.

Document the override rationale in `cost_estimate.json.notes` so future audits
can trace why a non-default provider was chosen.
