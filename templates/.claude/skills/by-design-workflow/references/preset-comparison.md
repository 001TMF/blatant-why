# Preset / Tier Comparison

Compare presets and campaign tiers across BoltzGen and PXDesign. Use this reference
when sizing a campaign and choosing the wall-time / cost / diversity trade-off.

All wall-time and cost figures assume **1× 80GB GPU local** unless noted. Multiply
appropriately for multi-GPU or HPC pricing.

---

## 1. Campaign Tiers (canonical names)

| Tier | Design Count | When to Use | Wall Time (1 GPU) | Typical Local Cost | Typical HPC Cost (RunPod H100 SXM) |
|------|--------------|-------------|---------------------|--------------------|------------------------------------|
| **Preview** | 5-500 | Feasibility check, parameter tuning, hotspot validation | 15 min – 1 hr | $0 (local) | $2-5 |
| **Standard** | 5,000 | Exploratory campaigns, iterating on hotspots / scaffolds | 1-3 hr | $0 (local) | $30-60 |
| **Production** | 20,000 | Production candidate pool for experimental selection | 4-12 hr | $0 (local) | $200-400 |
| **Exploratory** | 50,000 | Novel / difficult targets, max diversity, publication-grade | 12-48 hr | $0 (local) | $500-1500 |

Tier names are canonical (`Preview` / `Standard` / `Production` / `Exploratory`) —
use the capitalized forms in `routing_decision.json` and `campaign_plan.md`.

---

## 2. BoltzGen Protocol × Tier Matrix

### `nanobody-anything` (VHH)

| Tier | Designs per Scaffold | Default Budget Token | Diversity Alpha | Wall Time (1×80GB) | Expected Pass Rate | Use Case |
|------|----------------------|----------------------|-----------------|----------------------|--------------------|----------|
| Preview | 500 | 10 | 0.001 | ~30 min | 15-40% | Feasibility |
| Standard | 5,000 | 50 | 0.001 | ~2.5 hr | 15-40% | Iteration / exploration |
| Production | 20,000 | 100 | 0.001 | ~10 hr | 15-40% | Final candidate pool |
| Exploratory | 50,000 | 200 | 0.01 | ~25 hr | 10-30% (broader space) | Novel epitopes |

Note: `diversity_alpha=0.001` is the default for production runs (max quality);
`0.01` for Exploratory tier (broader space, slightly lower per-design pass rate).

### `antibody-anything` (scFv / Fab)

| Tier | Designs per Scaffold | Default Budget Token | Diversity Alpha | Wall Time (1×80GB) | Expected Pass Rate | Use Case |
|------|----------------------|----------------------|-----------------|----------------------|--------------------|----------|
| Preview | 500 | 10 | 0.001 | ~45 min | 10-30% | Feasibility |
| Standard | 5,000 | 50 | 0.001 | ~4 hr | 10-30% | Iteration / exploration |
| Production | 20,000 | 100 | 0.001 | ~16 hr | 10-30% | Final candidate pool |
| Exploratory | 50,000 | 200 | 0.01 | ~40 hr | 8-20% (broader space) | Novel epitopes |

Wall time is roughly 1.5× the VHH protocol because Fab designs are paired (VH + VL).

### `protein-anything` (de novo fallback)

| Tier | Designs | Default Budget Token | Diversity Alpha | Wall Time (1×80GB) | Expected Pass Rate | Use Case |
|------|---------|----------------------|-----------------|----------------------|--------------------|----------|
| Preview | 500 | 10 | 0.001 | ~30 min | 10-25% | Feasibility (use PXDesign first) |
| Standard | 5,000 | 50 | 0.001 | ~2.5 hr | 10-25% | Fallback when PXDesign fails |
| Production | 20,000 | 100 | 0.001 | ~10 hr | 10-25% | Rare; usually use PXDesign instead |
| Exploratory | 50,000 | 200 | 0.01 | ~25 hr | 8-18% | Novel topology, PXDesign unsuitable |

---

## 3. PXDesign Preset × Tier Matrix

PXDesign uses **presets** rather than per-tier budget tokens. The preset selects the
internal pipeline depth and filtering aggressiveness.

| Tier | Preset | `N_sample` | Multi-GPU | Wall Time (1×40GB) | Expected Pass Rate | Use Case |
|------|--------|------------|-----------|----------------------|--------------------|----------|
| Preview | `preview` | 5-10 | single | 15-30 min | 10-30% | Sanity check, hotspot validation |
| Standard | `extended` | 20-100 | single | 1-3 hr | 30-50% | Exploratory |
| Production | `extended` | 100-200 | `--nproc 4` (4 GPUs) | 4-12 hr | 30-50% | Final candidate pool |
| Exploratory | `extended` | 500+ | `--nproc 4-8` | 12-48 hr | 17-40% (target-dependent) | Novel target / publication run |

Pass rate range (17-82% reported in the PXDesign literature) collapses on a per-target
basis. Always estimate from the canonical bucket below.

### Pass-rate buckets by target difficulty

| Target Class | Typical PXDesign Pass Rate | Typical BoltzGen `nanobody-anything` Pass Rate |
|--------------|---------------------------|----------------------------------------------|
| Well-studied (TNF-alpha, PD-L1, HER2 — many co-crystals) | 40-82% | 30-40% |
| Moderate (some prior art) | 25-45% | 20-30% |
| Novel (no co-crystals, < 10 papers) | 10-25% | 10-20% |
| Difficult (disordered, transmembrane, glycosylated) | 5-15% | 5-15% |

---

## 4. Protenix Mode × Use Case

Protenix does not have "tiers" in the same sense; instead, it has model choices and
seed counts.

| Mode | Model | Seeds | Wall Time (1×24GB, 300 aa) | Use Case |
|------|-------|-------|------------------------------|----------|
| Fast | `mini` | 1 | ~2 min | Sanity check only |
| Single-seed | `base_default` | 1 | ~5-15 min | Quick fold check |
| Multi-seed ensemble | `base_default` | 5 [42, 123, 456, 789, 1024] | ~25-75 min | Production validation |
| Latest checkpoint | `base_20250630` | 5 | ~25-75 min | When `base_default` confidence is low |
| Complex refolding | `base_default` | 1-3 | ~5-30 min | Post-design binder + target validation |

Multi-seed ensemble is the canonical production mode; single-seed is only acceptable
for preview / debugging.

---

## 5. Diversity Trade-off

Higher `diversity_alpha` (BoltzGen) or higher `N_sample` (PXDesign) gives more
diverse output but lowers per-design pass rate. Choose based on downstream goal:

| Goal | BoltzGen `diversity_alpha` | PXDesign Preset | Notes |
|------|-----------------------------|-----------------|-------|
| Maximum quality (one best design) | 0.001 | `extended` (default) | Defaults; converges on consensus paratope |
| Diversity for lab portfolio | 0.001 → 0.01 | `extended` × 4 with different hotspot subsets | Spread risk across mechanisms |
| Maximum exploration (novel target) | 0.01 | `extended` × multiple hotspot windows | Trade pass rate for coverage |
| Convergence test (sanity) | 0.0 (rarely; produces near-duplicates) | `preview` × 3 seeds | Should yield highly similar designs |

**Anti-pattern:** `diversity_alpha = 1.0`. This kills BoltzGen diversity and produces
near-duplicate outputs. Use `0.001` (default) or `0.01` (exploratory).

---

## 6. Budget Gating Heuristics

When the user provides a budget constraint, apply this gate **before** running
`route_intent.py`:

| User Budget (USD on HPC) | Maximum Tier | Notes |
|---------------------------|--------------|-------|
| ≤ $50 | Preview | Single tier; one modality |
| ≤ $200 | Standard | One modality, 1-2 scaffolds |
| ≤ $500 | Standard | Up to 3 scaffolds, full screening |
| ≤ $2,000 | Production | Full Production run, 2 scaffolds, complete screening |
| > $2,000 | Exploratory or multi-modality | Compare VHH + scFv + de novo, full screening |

Local GPU compute is free at the dollar level but costs wall time — apply the same
table treating $1 ≈ 5 GPU-hours.

---

## 7. Multi-Target Sweep Sizing

When orchestrating the same protocol against N targets:

| Total Targets | Approach | Notes |
|---------------|----------|-------|
| 2-5 | Sequential per-target Standard runs | Routing decision per target; shared scaffold pool |
| 6-20 | Parallel Preview tier per target, then Standard on top performers | Filter at Preview stage; only top 30% promote to Standard |
| 20+ | HPC array job via `by-deploy-compute`; Preview tier only | Promote winners to Standard sequentially |

Never run Production tier across > 10 targets in parallel without explicit user
sign-off on the cumulative spend.

---

## 8. Memory Footprint by Tier

| Engine | Tier | Local Memory Footprint | When Local Fails |
|--------|------|--------------------------|-------------------|
| BoltzGen `nanobody-anything` | Standard | 40-60 GB peak | Target > 1500 aa |
| BoltzGen `antibody-anything` | Standard | 60-80 GB peak | Target > 1200 aa |
| BoltzGen `protein-anything` | Standard | 40-60 GB peak | Target > 1500 aa |
| PXDesign `extended` | Standard | 30-40 GB peak | Target > 2000 aa |
| Protenix `base_default` | Single chain | 8-16 GB | Sequence > 1500 aa |
| Protenix `base_default` | Complex | 24-40 GB | Total residues > 2000 |

When the local memory budget is exceeded:
1. Crop target to binding domain + 10 Å buffer.
2. If still too large, switch compute target to HPC (RunPod A100/H100 80GB).
3. Only as a last resort: switch to Tamarind cloud.

---

## 9. Recommended Defaults — Quick Card

For a typical, well-studied target with no special constraints:

| Modality | Engine | Preset / Protocol | Tier | Compute | Wall Time | Expected Cost |
|----------|--------|-------------------|------|---------|-----------|---------------|
| VHH | BoltzGen | `nanobody-anything` | Standard | local | ~2.5 hr | $0 |
| scFv | BoltzGen | `antibody-anything` | Standard | local | ~4 hr | $0 |
| De novo | PXDesign | `extended` | Standard | local | ~2 hr | $0 |
| Structure validation | Protenix | `base_default`, 5 seeds | n/a | local | ~30 min | $0 |

When the user just says "design a binder", route to BoltzGen `nanobody-anything`
Standard tier on local. That is the highest-leverage default.
