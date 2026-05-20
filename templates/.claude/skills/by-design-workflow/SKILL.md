---
id: "skill_30755445e07649dbb29c836632a0417a"
name: "by-design-workflow"
display-name: "BY Design Workflow — Master Orchestrator"
short-description: "Master orchestration skill that decides which design engine (Protenix, PXDesign, BoltzGen) runs, with which preset, on which compute target, and how to evaluate the result. Use when starting any new design project, deciding between modalities, planning a campaign end-to-end, setting quality thresholds, or deciding accept vs re-run."
category: "orchestration"
keywords: "orchestration, routing, decision tree, modality, antibody, nanobody, VHH, scFv, de novo, binder, Protenix, PXDesign, BoltzGen, preset, tier, compute target, pass rate, quality threshold"
version: "1.0"
last-updated: "2026-05-20"
---

# BY Design Workflow — Master Orchestration Skill

`by-design-workflow` is the **routing brain** of BY. It does not run any engine itself.
Instead, it answers four questions before any GPU compute is committed:

1. **Which engine?** — Protenix (fold), PXDesign (de novo binder), or BoltzGen (antibody / nanobody / fallback binder).
2. **Which preset / protocol / tier?** — Preview vs Standard vs Production vs Exploratory; `nanobody-anything` vs `antibody-anything` vs `protein-anything`; PXDesign `preview` vs `extended`.
3. **Which compute target?** — `local` (default), `hpc` (RunPod / Modal / SLURM via `by-deploy-compute`), or `tamarind` (cloud fallback).
4. **Accept or re-run?** — given the screening output, do the designs clear the quality bar, or does the campaign need a second pass with new hotspots, a new modality, or a different scaffold?

This skill encodes the canonical decision tree, the modality → tool mapping, the preset
comparison, the quality thresholds, and the accept-vs-re-run heuristics that other
skills depend on. It is the connective tissue between `by-research` / `by-campaign-manager`
(upstream) and the three tool wrappers `protenix`, `pxdesign`, `boltzgen` (downstream).

---

## When to Use This Skill

Use this skill when you have:

- ✅ **A new design project starting** — research is done, but the tool / preset / compute target has not been chosen yet
- ✅ **An ambiguous modality** — user said "I want a binder against X" without specifying antibody vs nanobody vs de novo
- ✅ **A target description but no plan** — PDB ID or sequence in hand, need a campaign sized end-to-end
- ✅ **A screening result and a decision to make** — designs are scored, should we lab-submit, re-run with new hotspots, or escalate?
- ✅ **A compute-target conflict** — local GPU OOMs on a 1500-residue target, decide HPC vs Tamarind vs target cropping
- ✅ **A novel target with no clear preset** — need to pick between Standard and Exploratory tiers based on prior-art density
- ✅ **A multi-target sweep request** — orchestrate the same protocol over N targets and decide whether to batch or serialize

Do NOT use this skill when:

- ❌ **You only need to run one engine right now** — invoke the engine's skill directly (`protenix`, `pxdesign`, or `boltzgen`). This skill is the planner, not a substitute for invoking the tool.
- ❌ **You are scoring or filtering existing designs** — that is `by-scoring` + `by-screening`.
- ❌ **You are managing campaign state / checkpoints / budget** — that is `by-campaign-manager`.
- ❌ **You need a PDB lookup, UniProt entry, or SAbDab query** — call the database MCP server directly or use `by-database`.
- ❌ **You are diagnosing a failed campaign in detail** — that is `by-failure-diagnosis` → `by-causal-reasoning`.
- ❌ **You want to skip the modality clarification step** — never trust a guessed modality. Always ask if the user has not specified.

🚨 **CRITICAL:** Never trust the routing decision without checking `.by/config.json` for the compute target. If `compute.fallback_allowed` is `false`, the choice between local / HPC / Tamarind is the **user's**, not yours. See `references/tool-selection-matrix.md` and the by-deploy-compute skill.

---

## Inputs

**Required:**
- **Target description** — exactly one of:
  - PDB ID (e.g., `"7S4S"`) — most preferred; gives structure + chains + residue numbering
  - UniProt accession (e.g., `"P01375"`) — sequence + features; structure inferred via Protenix if no PDB exists
  - Bare sequence (FASTA) — least preferred; cannot resolve isoforms or residue numbering, requires Protenix fold first
- **Modality preference** (if known): `VHH` / `scFv` / `Fab` / `de_novo_binder` / `unknown`. If `unknown`, the skill ASKS — never guesses.

**Optional:**
- **Hotspot residues** (`label_seq_id` integers, per-chain) — if `by-research` or `by-epitope-analysis` already produced them, pass them through unchanged
- **Budget / timeline constraint** — e.g., `"under $500 cloud spend"`, `"results by Friday"`. Drives tier and compute-target choice.
- **Compute target preference** — `local` / `hpc` / `tamarind` / `auto`. Default `local`. Read `.by/config.json` first; explicit user override only on this turn.
- **Existing campaign plan** — `campaign_plan.md` from `by-campaign-manager`. If present, use it instead of re-deciding from scratch.
- **Prior-art context** — `design_recommendation.json` from `by-research`. If present, modality, scaffolds, and tier are already chosen; this skill validates and dispatches.
- **Acceptance criteria override** — non-default thresholds for ipSAE / ipTM / pLDDT / CA-RMSD (rarely used; default thresholds live in `references/quality-thresholds.md`).

See `references/tool-selection-matrix.md` for how each input combination maps to a routing decision.

---

## Outputs

This skill writes **routing artifacts**, not design data. Place them under the active
campaign directory at `campaigns/{target}/campaign_{date}_{id}/routing/`.

| File | Format | Purpose | Consumer |
|------|--------|---------|----------|
| `routing_decision.json` | JSON | Engine + preset + compute target + rationale | by-campaign-manager, the engine skill |
| `handoff_package.json` | JSON | Bundle of inputs the engine skill needs (target file, hotspots, YAML config skeleton) | protenix / pxdesign / boltzgen skill |
| `pass_rate_forecast.json` | JSON | Expected pass rate range + minimum-viable design count | by-campaign-manager (budgeting) |
| `accept_or_rerun.json` | JSON | After a campaign round: verdict (`ACCEPT` / `RERUN` / `SWITCH_TOOL` / `ESCALATE`) + reasoning | by-campaign-manager, the user |

**Key shape — `routing_decision.json`:**

```json
{
  "campaign_id": "tnf_alpha_20260520_001",
  "engine": "boltzgen",
  "protocol": "nanobody-anything",
  "tier": "Standard",
  "num_designs_per_scaffold": 5000,
  "scaffolds": ["caplacizumab", "ozoralizumab"],
  "compute_target": "local",
  "compute_provider_source": ".by/config.json",
  "estimated_wall_time_hours": 2.5,
  "estimated_pass_rate_range": "20-40%",
  "expected_passing_designs": 1500,
  "rationale": "VHH modality (user-specified); 2 PDB co-crystals exist; pass rate is target-bucket median for well-studied antigens; local 1xH100 sufficient at this tier.",
  "rerouting_triggers": ["local OOM (>1500 aa)", "<10% pass rate at 500 designs"],
  "fallback_chain": ["local", "hpc(runpod)", "tamarind"],
  "created_at": "2026-05-20T10:00:00Z"
}
```

**Key shape — `accept_or_rerun.json`:**

```json
{
  "campaign_id": "tnf_alpha_20260520_001",
  "verdict": "RERUN",
  "round_index": 1,
  "metrics_summary": {
    "designs_total": 500,
    "ipsae_min_p50": 0.28,
    "iptm_p50": 0.61,
    "pass_rate": 0.08
  },
  "verdict_reasoning": "ipSAE p50 below 0.30 pass threshold; iptm acceptable. Hotspots likely too dispersed; shrink window from 8 to 4 residues centered on highest-conservation cluster.",
  "next_action": "Re-run BoltzGen nanobody-anything with narrowed hotspots; same scaffolds; budget unchanged.",
  "escalation_path": "If second round also fails, switch to PXDesign de novo (different paratope topology) before escalating to wet-lab epitope mapping."
}
```

---

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — never proceed without an unambiguous target + modality. Guessing burns compute.

1. **Target + modality (ASK THIS FIRST)** — What is the target (PDB ID or sequence), and what modality do you want — antibody (scFv / Fab), nanobody (VHH), de novo protein binder, or structure-only (no design, just folding)? If the user says "binder" without qualifier, ask the modality question explicitly.
2. **Compute target** — Local GPU (default), HPC (RunPod / Modal / SLURM), or Tamarind cloud? Read `.by/config.json` first; only ask if the file is missing or `compute.fallback_allowed` is `true` and the user has not specified.
3. **Tier and budget** — Preview (feasibility, ~5–500 designs), Standard (~5K designs), Production (~20K), or Exploratory (~50K, novel targets)? If the user gave a dollar budget or deadline, derive the tier from `references/preset-comparison.md`.
4. **Hotspots / epitope** — Already known (from `by-research` or `by-epitope-analysis`)? Or do we need to do epitope analysis first? For de novo binders without hotspots, PXDesign will run a hotspot-free preview but pass rates drop ~3×.
5. **Scaffold preference** — For antibody / nanobody runs: caplacizumab default for VHH, adalimumab default for scFv. Multiple scaffolds increase diversity but multiply design count. See `references/tool-selection-matrix.md` for the full list.
6. **Acceptance criteria** — Default thresholds (`ipSAE > 0.3`, `ipTM > 0.5`, `pLDDT > 70`, `CA-RMSD < 3.5 Å`)? Or stricter (`ipSAE > 0.5`, etc.) for high-stakes targets? Defaults live in `references/quality-thresholds.md`.
7. **Re-run policy** — If first-round pass rate is below 10%, what is the user's tolerance for re-running with adjusted hotspots vs switching tools vs escalating to wet lab? Default is **two re-runs, then switch tool, then escalate**.

---

## Decision Tree

This is the canonical routing logic. Walk it top-to-bottom; the first matching branch
wins. Full matrix (with rationale per cell) is in `references/tool-selection-matrix.md`.

```
User intent
│
├─ "Design a binder against <target>"
│   │
│   ├─ Antibody / nanobody?
│   │   ├─ Nanobody / VHH / single-domain / sdAb
│   │   │     → engine: boltzgen
│   │   │       protocol: nanobody-anything
│   │   │       default scaffolds: caplacizumab, ozoralizumab
│   │   │       typical pass rate: 15-40%
│   │   │
│   │   └─ Full antibody / scFv / Fab / IgG / mAb
│   │         → engine: boltzgen
│   │           protocol: antibody-anything
│   │           default scaffolds: adalimumab, tezepelumab
│   │           typical pass rate: 10-30%
│   │           note: post-design VH-(G4S)3-VL conversion for scFv
│   │
│   └─ De novo protein binder (non-antibody, non-nanobody)?
│       ├─ Standard target (PDB exists, hotspots known)
│       │     → engine: pxdesign
│       │       preset: extended (production) | preview (feasibility)
│       │       typical pass rate: 17-82% (target-dependent)
│       │
│       └─ PXDesign env/CUDA issue OR novel topology
│             → engine: boltzgen
│               protocol: protein-anything
│               typical pass rate: 10-25%
│
├─ "Predict / validate a structure" (no design)
│       → engine: protenix
│         model: base_default (recommended) | base_20250630 (latest) | mini (fast)
│         seeds: [42] single, [42,123,456,789,1024] ensemble
│         note: ALWAYS run before designing to validate target fold
│
├─ "Score / re-rank existing designs"
│       → NOT this skill. Dispatch to by-scoring + by-screening.
│
└─ "Analyze a target / find hotspots"
        → NOT this skill. Dispatch to by-research + by-epitope-analysis.
```

### Resolved routing — quick lookup

| Modality | Engine | Protocol / Preset | Default Tier | Pass Rate (median) | Default Compute |
|----------|--------|-------------------|--------------|--------------------|-----------------|
| VHH (nanobody) | BoltzGen | `nanobody-anything` | Standard | 25% | local GPU |
| scFv / Fab / IgG | BoltzGen | `antibody-anything` | Standard | 20% | local GPU |
| De novo binder (well-studied) | PXDesign | `extended` | Standard | 30-50% | local GPU |
| De novo binder (feasibility) | PXDesign | `preview` | Preview | 10-30% | local GPU |
| De novo binder (fallback) | BoltzGen | `protein-anything` | Standard | 15% | local GPU |
| Structure prediction | Protenix | `base_default` | n/a | n/a | local GPU |
| Multi-seed ensemble fold | Protenix | `base_default`, 5 seeds | n/a | n/a | local GPU |

For full matrix (rows: VHH / scFv / Fab / de novo / ligand-binding / structure-only;
columns: tool / preset / hotspot guidance / pass rate / compute), see
`references/tool-selection-matrix.md`.

---

## Quick Start

A typical "design a binder against TNF-alpha" request, end-to-end:

```text
User: "I want a nanobody against TNF-alpha. Use local GPU. Standard tier."

Agent (this skill):
  1. Read .by/config.json → compute.default_provider="local", local engine paths.
  2. Load research/design_recommendation.json (if exists) → modality=VHH, scaffolds=[caplacizumab, ozoralizumab].
  3. python3 scripts/route_intent.py --mode route \
         --intent-json intent.json --config-json .by/config.json \
         --out-dir campaigns/tnf_alpha/.../routing/
     ✓ Routing decision written: routing/routing_decision.json
       (engine=boltzgen, protocol=nanobody-anything, tier=Standard, compute=local)
     ✓ Handoff package written: routing/handoff_package.json
       (scaffolds=2, designs_per_scaffold=5000)
  4. python3 scripts/estimate_design_space.py \
         --modality VHH --tier Standard --num-scaffolds 2 \
         --target-class well_studied --compute-target local \
         --out-dir campaigns/tnf_alpha/.../routing/
     ✓ Forecast written: routing/pass_rate_forecast.json
       (total_designs=10000, expected_passing=3500, wall_hours=5.0, cost=$0.00)
  5. Hand off to by-campaign-manager → writes campaign_plan.md
  6. Hand off to boltzgen skill → runs the actual design
  7. (Later) After by-screening completes:
     python3 scripts/route_intent.py --mode accept-or-rerun \
         --screening-summary screening_summary.json \
         --routing-decision routing/routing_decision.json \
         --out-dir campaigns/tnf_alpha/.../routing/
     ✓ Accept-or-rerun verdict written: routing/accept_or_rerun.json
       (verdict=ACCEPT, pass_rate=24.0%)
```

Expected total time for the routing step (this skill): under 30 seconds. The
actual design compute is handled by the engine skill that follows.

---

## Residue Numbering Convention

All BY tools use **`label_seq_id`**: 1-indexed, sequential, per-chain, no gaps. This
differs from `auth_seq_id` (the PDB author numbering with gaps and insertion codes)
and from 0-indexed array positions.

| Identifier | Format | Used By |
|------------|--------|---------|
| `label_seq_id` | 1-indexed, sequential, per-chain integer | every BY engine (canonical) |
| `auth_seq_id` | PDB author numbering, may have gaps / insertion codes | external publications, PyMOL |
| Array index | 0-indexed Python position | internal scripts only |

**Tool-specific encoding:**
- PXDesign `hotspot_residues`: list of `"<chain><label_seq_id>"` strings, e.g. `["A45", "A50"]`.
- BoltzGen `epitope_residues`: list of `label_seq_id` integers per chain, e.g. `[45, 50, 52]`.
- Protenix: full sequences in JSON; no residue-level specification needed.

**Common pitfall:** users frequently paste residue numbers from a publication or
PyMOL session (`auth_seq_id`). Wrong hotspot numbering wastes the entire campaign.
This skill's handoff package stores the mapping `auth_seq_id_map` so the engine
skill can validate against the target structure before launching.

---

## Compute Target Selection

The compute target is read from `.by/config.json` → `compute.default_provider`. The
skill never silently overrides this — even if the requested target appears
unavailable, it ASKS the user before switching.

| Provider | Cost | Latency | When to Use | When NOT to Use |
|----------|------|---------|-------------|------------------|
| `local` | $0 | None (instant) | Default — user owns the hardware | Target > local memory budget |
| `hpc` (RunPod / Modal / SLURM) | $3-5 / GPU-hr | minutes (cold start) | Local OOM, multi-GPU production runs | When local has capacity |
| `tamarind` | $5+ / GPU-hr | minutes-hours (cold-start queue) | No local GPU, no HPC account | If local or HPC is available |

When `compute.fallback_allowed=true` in config, the skill may auto-promote
local → hpc → tamarind in the order specified by `compute.providers_priority`. When
`fallback_allowed=false`, ANY switch requires the user's explicit approval — this
is a budget-protection property and must not be bypassed.

See `by-deploy-compute/SKILL.md` for the canonical HPC dispatch logic. This skill
does NOT re-document compute setup — it only decides which provider to use.

---

## Campaign Cost Quick Reference

Rough budget envelopes (HPC pricing; local is $0 cash but consumes wall time):

| Campaign Profile | Total Designs | HPC Cost (approx) | Local Wall Time | When |
|------------------|---------------|--------------------|--------------------|------|
| Preview only | 500-1000 | $5-15 | ~1 hr | Feasibility |
| Standard, 1 modality | 5K-10K | $50-100 | 3-5 hr | Exploration |
| Standard, 2 modalities | 10K-20K | $100-200 | 6-10 hr | Modality comparison |
| Production, 1 modality | 20K-40K | $250-500 | 10-20 hr | Final candidate pool |
| Exploratory, multi-modality | 50K-100K | $1000-2000 | 25-50 hr | Novel target, publication-grade |

Adaptyv Bio lab follow-up adds $119-$215 per design; budget 5-20 lab tests for a
Standard campaign, 30-50 for Production. Turnaround 2-4 weeks.

---

## Standard Workflow

🚨 **MANDATORY: USE THE SCRIPTS BELOW TO PRODUCE ROUTING ARTIFACTS — DO NOT IMPROVISE INLINE DECISIONS** 🚨

Every routing decision must produce a `routing_decision.json` written by the script,
not free-text. Every accept-vs-re-run verdict must produce an `accept_or_rerun.json`.

1. **Read `.by/config.json`** — Pull `compute.default_provider`, `compute.fallback_allowed`, `compute.providers_priority`, and the local engine paths. If the file is missing, prompt for `by-session` first.
2. **Load upstream artifacts** — `campaigns/{target}/.../research/design_recommendation.json` (from `by-research`) and `campaigns/{target}/.../research/recommended_hotspots.json` (from `by-epitope-analysis`). If present, modality and scaffolds are already chosen.
3. **Resolve the routing decision** — Run `scripts/route_intent.py` with the merged inputs:
   ```bash
   python3 scripts/route_intent.py \
       --intent-json /path/to/intent.json \
       --config-json /path/to/.by/config.json \
       --out-dir campaigns/{target}/.../routing/
   ```
   Writes `routing_decision.json`. Verification: `✓ Routing decision written: routing/routing_decision.json (engine=boltzgen, protocol=nanobody-anything)`.
4. **Forecast pass rate and design count** — Before launching compute, estimate budget:
   ```bash
   python3 scripts/estimate_design_space.py \
       --modality VHH \
       --tier Standard \
       --num-scaffolds 2 \
       --out-dir campaigns/{target}/.../routing/
   ```
   Writes `pass_rate_forecast.json`. Verification: `✓ Forecast written: routing/pass_rate_forecast.json (expected_passing=1500, wall_hours=2.5)`.
5. **Hand off to the engine skill** — The engine skill (`protenix`, `pxdesign`, or `boltzgen`) reads `routing_decision.json` + `handoff_package.json` and produces the actual designs. This skill does NOT invoke the engine directly.
6. **After screening, compute accept-or-rerun** — Once `by-screening` writes the per-round summary, run:
   ```bash
   python3 scripts/route_intent.py \
       --mode accept-or-rerun \
       --screening-summary /path/to/screening_summary.json \
       --routing-decision /path/to/routing_decision.json \
       --out-dir campaigns/{target}/.../routing/
   ```
   Writes `accept_or_rerun.json` with verdict ∈ {`ACCEPT`, `RERUN`, `SWITCH_TOOL`, `ESCALATE`}.

**Discipline:**
- ✅ Always write `routing_decision.json` before any compute is submitted
- ✅ Always re-read `.by/config.json` at the start — provider can change between sessions
- ✅ Always pass the resolved `compute_target` to the engine skill in the handoff package (do not let the engine guess)
- ❌ Do NOT silently switch compute providers when `compute.fallback_allowed=false`
- ❌ Do NOT skip the pass-rate forecast — it is what `by-campaign-manager` uses for budget gating
- ❌ Do NOT make the accept-vs-rerun call from memory — run the script so the verdict is auditable

---

## When Scripts Fail

Both scripts are stdlib-only Python (`json`, `argparse`, `pathlib`). Failure modes:

1. **Fix and Retry (90%)** — Almost always a missing input file or wrong path. Re-check the `--config-json` and `--intent-json` paths. Confirm `.by/config.json` exists by running `by-session`.
2. **Modify Script (5%)** — If the engine catalog changes (new protocol, new preset), edit the lookup tables at the top of `scripts/route_intent.py` and `references/tool-selection-matrix.md` together. Keep CLI signatures stable.
3. **Use as Reference (4%)** — If the routing decision needs custom logic (e.g., multi-target sweep), read the script for the canonical heuristics, then write the JSON by hand following the schema in `routing_decision.json`. Cite the source script in `rationale`.
4. **Write from Scratch (1%)** — Only if the inputs cannot be reconciled with the existing schema (rare). Document why in `routing/notes.md` and submit the new schema for review.

If the upstream artifacts (`design_recommendation.json`, `recommended_hotspots.json`) are
missing, the correct response is to invoke `by-research` first — not to invent values.

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| User says "design a binder" without modality | Ambiguous request; could be VHH, scFv, or de novo | Ask Q1 explicitly. Do NOT default to VHH silently — confirm before routing. | `references/tool-selection-matrix.md` |
| Target has no PDB structure | Sequence-only target; no experimental fold | Run Protenix fold first (single seed for preview, 5-seed ensemble for production). Crop high-pLDDT domain if full-length is disordered. | `references/quality-thresholds.md` Fold-Validation |
| Target > 1500 residues, local OOMs | BoltzGen / PXDesign exceeds 80 GB at full target | Crop to binding domain + 10 Å buffer; if still OOM, switch compute target to HPC (RunPod A100/H100 80GB) via by-deploy-compute. | `references/preset-comparison.md` Memory-by-Tier |
| Multi-chain complex target (e.g., trimer) | Hotspots span multiple chains; tools default to one target chain | Set target as the assembled complex; specify hotspots with chain prefix (`A45,B112`); pre-validate fold with Protenix multimer prediction. | `references/tool-selection-matrix.md` Multi-Chain |
| Multi-target screening request | User wants the same protocol against N targets | Sequential: one routing decision per target; share scaffold pool. Parallel: batch via by-deploy-compute HPC array job. Choose by total design count: < 5K total → sequential; ≥ 5K → batch. | `references/preset-comparison.md` Multi-Target |
| Off-target / polyspecificity concern | Therapeutic candidate must avoid binding human paralogs | Add post-design polyspecificity screen via by-screening (`screen_cross_validate`); reduce composite weight on `ipSAE_min` and add explicit cross-reactivity penalty. | `references/quality-thresholds.md` Polyspecificity |
| Low compute budget, large design space | Tier mismatch: user wants Production but budget covers Preview | Run Preview tier first, gate Production on Preview pass rate ≥ 15%; if not, escalate to user. Never silently shrink Production to Preview. | `references/preset-comparison.md` Budget-Gating |
| `compute.default_provider="local"` but local GPU absent | `.by/config.json` stale or wrong machine | Run `by-session` to re-detect compute; if no local GPU, prompt user to switch to `hpc` or `tamarind`. Never silently route to cloud. | by-deploy-compute SKILL.md |
| PXDesign fails twice in a row | CUDA / env mismatch on local install | Switch to BoltzGen `protein-anything` (de novo fallback) after 1 failed launch. Do NOT spend multiple cycles fixing PXDesign env mid-campaign. | `references/tool-selection-matrix.md` De-Novo-Fallback |
| Designs have good ipTM but low ipSAE | Interface confident but partial; ipSAE asymmetry > 0.3 | Re-run with tightened hotspots (drop 1-2 residues at the edges); if asymmetric ipSAE persists, switch modality (de novo → VHH may engage differently). | `references/quality-thresholds.md` ipSAE-Asymmetry |
| Pass rate < 10% on Preview | Hotspots too dispersed or wrong epitope | Re-run epitope analysis (`by-epitope-analysis`); narrow hotspot window to 3-5 spatially clustered residues. If second Preview also fails, escalate. | `references/quality-thresholds.md` Re-Run-Criteria |
| Modality unclear, user wants "best chance" | No modality preference, novel target | Default order: VHH (highest pass rate, simplest), then scFv, then de novo. Justify the choice in `routing_decision.json.rationale`. | `references/tool-selection-matrix.md` Modality-Selection |
| Target is a ligand / small molecule, not protein | Wrong tool family — BY engines are protein-protein interfaces | Refuse the campaign politely. Suggest small-molecule docking tools (out of scope for BY). Document refusal in `routing/notes.md`. | `references/tool-selection-matrix.md` Out-Of-Scope |
| Glycosylated surface near hotspots | BoltzGen does not model glycans by default | Implementation-engineer persona in `by-research` Phase 6 should have flagged this. Shift hotspot window or accept reduced confidence. | by-research SKILL.md Phase 6 |

---

## Best Practices

1. 🚨 **CRITICAL: Always read `.by/config.json` first.** The compute provider is the user's choice, not yours.
2. 🚨 **CRITICAL: Never silently default a modality.** Ask Q1 if the user said "binder" without qualifier.
3. ✅ **REQUIRED: Write `routing_decision.json` before any compute is submitted.** It is the audit trail.
4. ✅ **REQUIRED: Pass `compute_target` explicitly to the engine skill.** Do not let `boltzgen` / `pxdesign` / `protenix` guess from environment.
5. ✅ Run Preview before Production for any novel target. Cheaper to fail at 500 designs than 20,000.
6. ✅ Validate target fold with Protenix before any design run on a target with no experimental structure.
7. ✅ Use `label_seq_id` (1-indexed, sequential, per-chain) for hotspot residues. Convert from `auth_seq_id` if user provides PDB numbering.
8. ✅ Prefer `local` compute when available — fastest, free, and the user already paid for the hardware.
9. ✨ **Optional:** Run a hypothesis-debate (`by-hypothesis-debate`) when multiple modalities are viable. A few minutes of reasoning saves hours of compute.
10. ❌ Do NOT skip the pass-rate forecast even on "obvious" campaigns — it is the budget gate.
11. ❌ Do NOT bypass `by-campaign-manager` for the actual campaign plan. This skill makes the routing decision; `by-campaign-manager` owns the plan and state machine.
12. ❌ Do NOT improvise new presets / protocols / scaffolds. If the catalog needs an addition, update `references/tool-selection-matrix.md` and `scripts/route_intent.py` together.

---

## Suggested Next Steps

After this skill produces `routing_decision.json` and `handoff_package.json`, chain into:

1. **`by-campaign-manager`** — write the canonical `campaign_plan.md` from the routing decision and the pass-rate forecast. Required before any compute is committed; manages state machine + budget + checkpoints.
2. **The engine skill** — one of:
   - **`protenix`** — for structure prediction / fold validation. Always run this first if the target has no experimental structure.
   - **`pxdesign`** — for de novo protein binder design. Write YAML → `pxdesign pipeline` → read `summary.csv`.
   - **`boltzgen`** — for antibody / nanobody design (or de novo fallback). Write entities YAML → `boltzgen run` → read `final_designs_metrics_*.csv`.
3. **`by-deploy-compute`** (if compute target is `hpc`) — packages the engine container, syncs target data, dispatches the job. Handles RunPod / Modal / SLURM.
4. **`by-screening`** — runs the full screening battery (ipSAE, ipTM, pLDDT, RMSD, liabilities, developability) on the design output. Writes `screening_summary.json`.
5. **`by-scoring`** — applies canonical formulas (composite, multi-seed aggregation, asymmetry checks) on top of screening output.
6. **Back to `by-design-workflow`** (this skill) in `accept-or-rerun` mode — after screening, compute the verdict (`ACCEPT` / `RERUN` / `SWITCH_TOOL` / `ESCALATE`).
7. **`by-failure-diagnosis`** (conditional) — invoked when the verdict is `RERUN` or `SWITCH_TOOL`; identifies the specific failure mode driving low pass rate.

This chain works because every downstream skill expects exactly the JSON shapes this skill writes. The handoff package is the contract; bypassing it forces the next skill to re-derive routing context from scratch.

---

## Related Skills

**Upstream (run before this):**
- `by-session` — initializes config, ensures `.by/config.json` exists with compute provider.
- `by-research` — produces `design_recommendation.json` (modality, scaffolds, tier).
- `by-epitope-analysis` — produces `recommended_hotspots.json` (residue list with confidence).
- `by-hypothesis-debate` — produces adversarial-ranked strategy when multiple modalities are viable.

**Downstream (run after this):**
- `by-campaign-manager` — writes `campaign_plan.md` from routing decision + forecast.
- `protenix`, `pxdesign`, `boltzgen` — the three engine wrappers that actually run the design.
- `by-deploy-compute` — HPC dispatch for `hpc` compute target.
- `by-screening` + `by-scoring` — evaluate the design output.
- `by-failure-diagnosis` — diagnose RERUN / SWITCH_TOOL verdicts.

**Alternative / complementary:**
- `by-database` — direct PDB / UniProt / SAbDab lookups without the campaign overhead.
- `by-display` — render the routing decision + forecast as a user-facing table.

---

## References

**Detailed documentation (this skill):**
- [`references/tool-selection-matrix.md`](references/tool-selection-matrix.md) — full modality × tool × preset × hotspot × pass rate × compute matrix with per-cell rationale.
- [`references/preset-comparison.md`](references/preset-comparison.md) — Preview vs Standard vs Production vs Exploratory comparison across BoltzGen + PXDesign; cost, time, diversity, recommended use case for each.
- [`references/quality-thresholds.md`](references/quality-thresholds.md) — acceptance criteria by modality (ipSAE / ipTM / pLDDT / CA-RMSD); when to ACCEPT, RERUN, SWITCH_TOOL, ESCALATE.

**Scripts:**
- [`scripts/route_intent.py`](scripts/route_intent.py) — CLI: input intent JSON (target, modality, budget, compute pref) → output `routing_decision.json` + `handoff_package.json`; also handles `accept-or-rerun` mode after screening.
- [`scripts/estimate_design_space.py`](scripts/estimate_design_space.py) — CLI: input modality + tier + scaffold count → estimate total design count, wall time hours, expected passing designs based on canonical pass-rate buckets.

**Cross-skill canonical sources:**
- [`templates/.claude/skills/README.md`](../README.md) — canonical terminology, skill linkage map, end-to-end workflow.
- [`templates/CLAUDE.md`](../../../CLAUDE.md) — BY agent identity, compute provider selection, campaign workflow overview.
- [`by-research/SKILL.md`](../by-research/SKILL.md) — produces upstream `design_recommendation.json`.
- [`by-campaign-manager/SKILL.md`](../by-campaign-manager/SKILL.md) — consumes downstream `routing_decision.json`.
- [`by-deploy-compute/SKILL.md`](../by-deploy-compute/SKILL.md) — HPC dispatch details (do not re-document here).
- [`by-scoring/SKILL.md`](../by-scoring/SKILL.md) — canonical ipSAE / ipTM / composite formulas.
- [`by-screening/SKILL.md`](../by-screening/SKILL.md) — full screening battery + PASS / FAIL gates.

**External documentation:**
- BoltzGen: project README in the local install (see `compute.local.boltzgen.path` in `.by/config.json`).
- PXDesign: project README in the local install (see `compute.local.pxdesign.path`).
- Protenix: https://github.com/bytedance/Protenix
