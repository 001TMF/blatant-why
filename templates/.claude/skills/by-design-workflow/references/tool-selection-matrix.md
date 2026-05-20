# Tool Selection Matrix

The canonical mapping from **target modality** to **engine + protocol/preset + hotspot
guidance + expected pass rate + compute requirement**. This matrix is the source of
truth for `scripts/route_intent.py`; if you change a row here, change the script's
lookup table in the same commit.

All entries assume the default compute provider is `local` (per `.by/config.json` →
`compute.default_provider`). HPC and Tamarind columns describe escalation paths when
local capacity is exceeded.

---

## 1. Primary Selection Matrix

### Antibody / nanobody modalities

| Modality | Engine | Protocol | Default Tier | Default Scaffolds | Hotspot Count | Pass Rate (median) | Local Compute | HPC Need | Notes |
|----------|--------|----------|--------------|--------------------|---------------|--------------------|---------------|----------|-------|
| **VHH (nanobody, single-domain)** | BoltzGen | `nanobody-anything` | Standard | caplacizumab, ozoralizumab | 3-6 | 25% (range 15-40%) | 1× 40GB GPU | only if > 1500 aa target | Simplest antibody modality; highest pass rate; fastest |
| **scFv** | BoltzGen | `antibody-anything` | Standard | adalimumab, tezepelumab | 3-6 | 20% (range 10-30%) | 1× 80GB GPU | preferred for production | Post-design: VH-(G4S)3-VL linker assembly |
| **Fab** | BoltzGen | `antibody-anything` | Standard | adalimumab, dupilumab | 3-6 | 20% (range 10-30%) | 1× 80GB GPU | preferred for production | Output kept as separate VH + VL chains |
| **Full IgG (mAb)** | BoltzGen | `antibody-anything` | Standard → Fab assembly downstream | adalimumab, tezepelumab | 3-6 | 18% (range 10-25%) | 1× 80GB GPU | preferred for production | Engine designs Fab; constant region appended off-pipeline |
| **Bispecific antibody** | BoltzGen | `antibody-anything` × 2 (one per target) | Standard | adalimumab + scaffold per arm | 3-6 per arm | 10-25% per arm | 2 sequential runs | HPC for parallel | Run as two independent campaigns; combine top picks downstream |

### De novo binder modalities

| Modality | Engine | Preset / Protocol | Default Tier | Hotspot Count | Pass Rate (median) | Local Compute | HPC Need | Notes |
|----------|--------|-------------------|--------------|---------------|--------------------|---------------|----------|-------|
| **De novo protein binder (60-150 aa)** | PXDesign | `extended` | Standard | 3-6 | 30-50% (range 17-82% target-dependent) | 1× 40GB GPU | rarely | Mature pipeline; AF2-IG + Protenix dual filter |
| **De novo binder, feasibility check** | PXDesign | `preview` | Preview | 3-6 | 10-30% | 1× 24GB GPU | never | 5-10 designs; ~15-30 min wall time |
| **De novo binder, large-scale** | PXDesign | `extended` × multi-GPU (`--nproc`) | Production | 3-6 | 30-50% | 4× 40GB GPU | yes for > 50K | Multi-GPU shards the diffusion stage |
| **De novo binder, PXDesign fallback** | BoltzGen | `protein-anything` | Standard | 3-6 | 15% (range 10-25%) | 1× 40GB GPU | rarely | Use after 1 failed PXDesign launch (env / CUDA issues) |
| **Ligand-binding protein** | PXDesign | `extended` (no built-in ligand support) | Standard | 3-6 spatially around binding pocket | 10-25% | 1× 40GB GPU | rarely | Ligand modeled as cofactor in target; success depends on pocket pre-formed |

### Structure-only modalities

| Modality | Engine | Model / Mode | Hotspot Count | Compute | Notes |
|----------|--------|--------------|---------------|---------|-------|
| **Single-chain fold prediction** | Protenix | `base_default`, 1 seed | n/a | 1× 24GB GPU | Fast; for sanity-check folds |
| **Multi-seed ensemble** | Protenix | `base_default`, 5 seeds [42,123,456,789,1024] | n/a | 1× 24GB GPU sequential | Use for any production validation |
| **Complex refolding** | Protenix | `base_default`, 1-3 seeds | n/a | 1× 40-80GB GPU | Used to validate designed binders post-hoc |
| **Latest-checkpoint exploration** | Protenix | `base_20250630`, 5 seeds | n/a | 1× 40GB GPU | Use only when `base_default` confidence is low |
| **Fast preview** | Protenix | `mini`, 1 seed | n/a | 1× 16GB GPU | Sanity check only; never for production |

---

## 2. Per-Cell Rationale

### Why VHH → BoltzGen `nanobody-anything`

- VHH is a single-domain antibody (~120 aa); no VH/VL pairing problem.
- BoltzGen's nanobody protocol uses a 7-scaffold library curated for stability.
- Pass rate is highest of any antibody modality because the design problem is smaller (one CDR set, no light chain).
- Recommended default for ambiguous requests if the user signals "antibody-like".

### Why scFv / Fab / IgG → BoltzGen `antibody-anything`

- Engine produces VH + VL as separate chains; post-processing assembles them.
- Fab template library (14 scaffolds) covers diverse germlines; adalimumab is the
  best-characterized default; tezepelumab is the modern-framework alternative.
- IgG full-length is not a design target — the engine designs the Fab; constant
  regions (CH1, CH2, CH3, Cκ) are appended deterministically off-pipeline.
- scFv requires the (G4S)3 linker assembly step; this is mechanical, not designed.

### Why de novo binder → PXDesign primary, BoltzGen fallback

- PXDesign is the mature, dual-filter (AF2-IG + Protenix) pipeline. Reported pass
  rate of 17-82% is target-dependent but consistently exceeds BoltzGen's
  `protein-anything` (10-25%) on well-studied targets.
- BoltzGen's `protein-anything` is reserved as a **fallback** for two cases:
  (1) PXDesign environment / CUDA issues that would take more than one retry to fix,
  (2) novel topology where PXDesign's scaffold space underperforms.
- Switch threshold: **one** failed PXDesign launch. Do not spend multiple cycles
  fixing PXDesign env mid-campaign.

### Why structure prediction → Protenix only

- Protenix v1 is the AF3-class model (368M params) shipped with BY; no alternative
  prediction engine is wired in by default.
- `base_default` is the production checkpoint; `base_20250630` is the latest
  experimental checkpoint; `mini` is for fast sanity checks only.
- Multi-seed ensemble (5 seeds) is the default for any production validation
  because single-seed confidence can be unstable on novel folds.

---

## 3. Hotspot Count Guidance

| Hotspot Count | Use Case | Risk |
|---------------|----------|------|
| 1-2 | Highly specific point interaction (rare; e.g., critical lysine) | Under-constrains paratope; low pass rate |
| **3-4** | **Default for tight, well-conserved epitopes** | None; sweet spot for most targets |
| **4-6** | **Default for diffuse / flexible epitopes** | None; sweet spot for most targets |
| 7-8 | Large or multi-region epitopes | Over-constrains; pass rate drops sharply |
| 9+ | Almost always wrong | Engine cannot satisfy all constraints; reject and re-narrow |

Always cluster hotspots spatially: residues should fit within a 10-15 Å sphere. Two
disjoint clusters means two campaigns, not one.

---

## 4. Multi-Chain Targets

When the target is a multi-chain complex (homodimer, heterotrimer, etc.):

| Target Type | Routing Adjustment |
|-------------|---------------------|
| Symmetric homodimer | Specify target as single chain; engine handles symmetry implicitly via the predicted complex |
| Heterodimeric obligate complex (e.g., TCR αβ) | Specify both chains in target spec; hotspots can span chains with chain-prefix notation (`A45, B112`) |
| Trimeric / higher-order | Pre-validate fold with Protenix multimer prediction first; if interface residues are clear, restrict design to one inter-chain interface at a time |
| Membrane-embedded receptor (GPCR, transporter) | Crop to extracellular domain + 10 Å buffer; warn user that lipid-facing surfaces are unreliable hotspots |

---

## 5. Out-of-Scope Modalities

Refuse the campaign politely (with rationale) for:

- **Small molecule binders** — BY engines are protein-protein; suggest external docking tools (out of scope).
- **Peptide-only designs (< 20 aa)** — too short for diffusion-based design space; refer to external peptide-design tools.
- **DNA / RNA-binding designs** — engines are not trained on nucleic-acid surfaces.
- **Membrane-spanning designs** — lipid context is not modeled by the engines.
- **Glycan recognition (lectin-like)** — engines do not model carbohydrates as ligands.

Document refusal in `campaigns/{target}/routing/notes.md` so future agents do not
re-attempt.

---

## 6. Modality Selection — Disambiguation Tree

When the user says only "binder against X":

1. Is X a soluble protein with a known structure (PDB)?
   - Yes → ask modality. Default suggestion order: VHH → scFv → de novo.
   - No → fold target with Protenix first; then re-ask modality.
2. Has the user worked with antibodies before?
   - Yes, wants antibody → VHH (Standard) is the highest-pass-rate default.
   - Yes, wants de novo → PXDesign.
   - No / ambiguous → recommend VHH first because (a) highest pass rate, (b) simplest validation, (c) smallest design unit.
3. Is the user's downstream workflow antibody-focused (cell binding assays, ELISA)?
   - Yes → VHH or scFv.
   - No (e.g., biophysical interrogation, miniprotein scaffolds) → de novo.

Never default silently — record the rationale in `routing_decision.json.rationale`.

---

## 7. De-Novo Fallback Trigger Matrix

| PXDesign Failure Mode | Action |
|------------------------|--------|
| CUDA out-of-memory on launch | Crop target → retry; if still OOM, switch to BoltzGen `protein-anything` |
| Conda env import error | One reinstall attempt; if still failing, switch to BoltzGen |
| Backbone diffusion produces 0 valid scaffolds | Likely hotspot infeasibility; re-run epitope analysis, then BoltzGen with same hotspots as A/B test |
| MPNN sequence design fails | Hotspots over-constrained; reduce to 3-4 residues and retry PXDesign once |
| AF2-IG filter rejects all designs | Target may be too small or too disordered; switch to BoltzGen which uses different filtering |

Single PXDesign retry, then switch. Never burn more than ~30 min of wall time on
PXDesign environment issues during an active campaign — that time costs more than
the alternate engine's compute.

---

## 8. Hand-off Package Contract

Every routing decision produces a `handoff_package.json` consumed by the engine
skill. Fields:

```json
{
  "campaign_id": "...",
  "target": {
    "pdb_id": "7S4S",
    "chains": ["A"],
    "sequence_or_path": "campaigns/.../target.cif",
    "residue_count": 154
  },
  "modality": "VHH",
  "engine": "boltzgen",
  "protocol": "nanobody-anything",
  "hotspots": {
    "chain": "A",
    "label_seq_ids": [45, 50, 52, 78],
    "auth_seq_id_map": {"45": 48, "50": 53, "52": 55, "78": 81}
  },
  "scaffolds": ["caplacizumab", "ozoralizumab"],
  "tier": "Standard",
  "num_designs_per_scaffold": 5000,
  "compute_target": "local",
  "local_paths": {
    "binary": "/opt/boltzgen/bin/boltzgen",
    "conda_env": "boltzgen"
  },
  "output_dir": "campaigns/.../designs/round_1/",
  "diversity_alpha": 0.5,
  "budget_token": 50,
  "msa_mode": "mmseqs2"
}
```

The engine skill MUST consume this verbatim. If a field is missing, fail loudly
rather than infer.
