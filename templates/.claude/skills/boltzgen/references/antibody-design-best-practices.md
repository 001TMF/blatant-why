# Antibody / Nanobody / Binder Design — Best Practices

Practical guidance for choosing modality, MSA mode, budget, and hotspot
strategy when running BoltzGen. Numbers reflect typical observations from
campaigns against well-characterised soluble extracellular targets unless
noted otherwise. Pass rate is defined as the fraction of designs meeting
`ipTM > 0.5`, `pLDDT > 70`, `RMSD < 3.5 Å`, and `ipSAE_min > 0.4`.

---

## Modality Selection: VHH vs scFv vs Fab vs De Novo

| Modality | Protocol | Size | Designs/Run | Use When |
|----------|----------|------|-------------|----------|
| **VHH (nanobody)** | `nanobody-anything` | ~120 aa, 1 chain | 10–50 | Default starting point; fast iteration; tissue penetration; intracellular delivery; cryo-EM tools; quick proof-of-binding |
| **Full antibody (Fab)** | `antibody-anything` | ~220 aa, 2 chains | 20–100 | Fc effector function (ADCC, CDC); therapeutic antibody pipeline; higher affinity ceiling; bispecific / multispecific formats |
| **De novo miniprotein** | `protein-anything` | 65–150 aa, 1 chain | 10–100 | Non-immunoglobulin scaffold acceptable; pxdesign unavailable; need novel topology |
| **Peptide** | `peptide-anything` | 10–40 aa, 1 chain | 20–100 | Linear binder; MHC ligand; cell-penetrating sequence; affinity ceiling acceptable |
| **Redesign** | `protein-redesign` | Variable | 10–50 | Improving an existing binder (affinity, expression, developability) |

### Decision tree

```
Need Fc effector function (ADCC, CDC, half-life via FcRn)?
├── YES → antibody-anything (Fab)
└── NO  → Is small size / tissue penetration a priority?
         ├── YES → nanobody-anything (VHH)            ← default
         └── NO  → Is an Ig scaffold required at all?
                  ├── YES → nanobody-anything
                  └── NO  → protein-anything (de novo) or peptide-anything
```

### When to escalate VHH → Fab

Start with VHH. Move to Fab only if:

- Top VHH designs plateau at `ipTM < 0.55` after 100+ designs across two epitope variants
- The therapeutic context demands an Fc (e.g., oncology ADCC, half-life extension)
- The user explicitly requires a humanized IgG product profile

---

## MSA Mode Selection

| Mode | When to Use | Cost | Notes |
|------|-------------|------|-------|
| `none` | Default. First-pass design runs. Most well-folded soluble targets. | Zero | Sufficient when target structure is high-quality and epitope is well-defined |
| `precomputed` | Top designs show pLDDT < 70 despite good ipTM | Pre-built A3M files needed | Generate once with MMseqs2 / HHblits; reuse across runs |
| `nim` | Need remote MSA, have NIM API access, no local A3M files | API latency + key | Slower per design; rarely improves outcomes vs `none` if target is monomeric |
| `templated` | Target is a multi-domain or membrane protein with poor monomer prediction | Template structures + MSA | Use only when the target itself has a known confidence problem; verify with Protenix first |

**Empirical observation:** Switching from `none` to `precomputed` improves
mean pLDDT by 2–5 points on well-folded targets but rarely changes the
ranking of top designs. Spend the iteration budget on the epitope, not on MSA,
unless pLDDT is genuinely the bottleneck.

---

## Expected Pass Rates by Target Difficulty

The numbers below are typical for a 50-design preview with `--budget 96`
and `--prefilter` enabled, scoring with the default thresholds. Pass rate
varies widely with epitope quality.

| Target Class | Difficulty | Typical Pass Rate | Notes |
|--------------|------------|-------------------|-------|
| Soluble cytokine, well-folded (TNF-α, IL-6, IL-17) | Easy | 30–60% | Good crystal structures, defined epitopes |
| Soluble receptor ectodomain (HER2 ECD, PD-L1) | Easy–Moderate | 20–40% | Epitope choice matters; multiple known antibodies |
| Cell-surface receptor (GPCR, ion channel) | Hard | 5–15% | Limited solvent-exposed surface; consider conformational state |
| Membrane-embedded epitope | Very Hard | < 5% | Often need a stabilised construct or peptide mimetic |
| Glycoprotein with sparse epitope | Hard | 5–15% | Glycan shielding limits accessible hotspots |
| Viral fusion protein (prefusion-stabilised) | Moderate | 15–30% | Prefusion mutants greatly outperform postfusion |
| Conformationally flexible / IDP target | Very Hard | < 5% | Static design is poorly matched; consider an ensemble strategy |
| Recently published target (high prior art) | Easier | +10–20% | Known epitopes accelerate hotspot selection |

**Calibrate expectations early.** If a 50-design preview returns < 5% pass
rate, do not scale to 200 designs. Re-examine the epitope or scaffold first.

---

## Hotspot / Binding Residue Recommendations

The `binding_types.binding` field is the single highest-leverage input to a
campaign. Quality of selection dominates everything else.

| Count | Use Case | Notes |
|-------|----------|-------|
| 3–5 residues | Highly focal epitope; small molecule mimicry; allosteric site | Risk of over-constraint; designs may fail to fit |
| 6–12 residues | **Recommended default** | Sweet spot for most extracellular epitopes |
| 13–20 residues | Large interface; broad neutralizing site; multi-loop interface | Use when known antibodies engage a wide surface |
| > 20 residues | Rare; whole-domain targeting | Usually means the epitope is not well-defined yet |

### Quality criteria for each hotspot residue

1. **Surface-exposed:** SASA > 0.25 (relative). Buried residues are unreachable — the most common silent failure.
2. **Conserved across orthologs / variants** (if cross-species reactivity is wanted): check UniProt variant data.
3. **Distinct conformational state** (if the target has multiple): pick residues only visible in the desired state.
4. **Not in a flexible loop with high B-factor** unless flexibility is desired (loop targeting can work but is harder to predict).
5. **Spatial clustering:** residues should form a contiguous patch on the surface, not scattered across the structure. Sanity-check by visualisation.

### Range notation reminder

Use `label_seq_id` (1-indexed, sequential, per-chain), not `auth_seq_id`.
See `entities-yaml-spec.md` for the conversion table. Mistakenly using
`auth_seq_id` is the #1 silent failure mode.

---

## Scaffold Selection

| Scenario | Recommendation |
|----------|----------------|
| First-pass design | Omit scaffold entity — use BoltzGen built-in defaults |
| Humanized therapeutic pipeline | Pick a Fab scaffold matching the target class (e.g., adalimumab for anti-cytokine) |
| Nanobody design | Defaults are excellent; only pin a scaffold (e.g., caplacizumab) if developability is the priority |
| Existing patent landscape | Choose a scaffold distant from known commercial mAbs to avoid prior art |
| Anti-viral antibody | nirsevimab (anti-RSV F) is a well-validated starting framework |

Available scaffolds are listed in the main `SKILL.md` (14 Fab + 4 nanobody).

---

## Budget × Protocol Recommendations

| Protocol | Preview Budget | Production Budget | Notes |
|----------|----------------|-------------------|-------|
| `nanobody-anything` | 48 | 96 | Diminishing returns above 128 |
| `antibody-anything` | 64 | 128 | Higher budget helps the VH/VL pairing |
| `protein-anything` | 48 | 96 | Diversity gain meaningful up to 128 |
| `peptide-anything` | 32 | 64 | Smaller search space; lower budgets fine |
| `protein-redesign` | 48 | 96 | Anchored by the starting binder; high budgets less useful |

Pair production budgets with `--prefilter` to drop low-quality designs
before the expensive Protenix refolding step. Skipping pre-filter on a
200-design run wastes ~30% of GPU time on designs that fail downstream.

---

## Iteration Loop

A typical campaign uses two passes:

1. **Preview (10–20 designs, budget 48, no scaffold)** — confirms epitope is reachable. Look at top-3 ipTM, pLDDT, and visualise the top design.
2. **Production (50–200 designs, budget 96–128, scaffold if humanization wanted, `--prefilter`)** — yields the working shortlist for `by-scoring` and `by-screening`.

If preview pass rate is < 5%, stop. Iterate on epitope or scaffold before scaling.
If preview pass rate is > 30%, the epitope is good — consider running fewer
production designs (50 instead of 200) and spending compute on multi-seed
robustness instead.

---

## Multi-Seed Robustness (Optional)

For production shortlists destined for lab synthesis, run the same spec
3–5 times with different random seeds and aggregate. The `parse_designs.py`
script handles seed merging via the `seed` column. Designs whose `ipSAE_min`
is high in only 1 of 5 seeds are likely lucky; designs robust across seeds
are the safer pick.

| Seeds | When | Cost Multiplier |
|-------|------|-----------------|
| 1 | Preview, iteration | 1× |
| 3 | Production shortlist | 3× |
| 5 | Final pre-synthesis ranking | 5× |

---

## Anti-Patterns

- ❌ Designing without an epitope (`binding_types` omitted) — pass rates collapse to < 2%
- ❌ Selecting hotspots from `auth_seq_id` numbering — wrong residues targeted
- ❌ Picking buried residues (SASA < 0.25) — geometrically unreachable
- ❌ Skipping the preview and going straight to 200 designs — wastes GPU on bad epitopes
- ❌ Using `antibody-anything` when VHH would do — 3–5× slower for no benefit
- ❌ Re-running with a different MSA mode hoping for a better ipTM — epitope dominates MSA
- ❌ Comparing pass rates across targets — they are class-specific (see table above)
