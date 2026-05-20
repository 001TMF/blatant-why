# PXDesign De Novo Strategy Guide

How to pick hotspots, scaffold preset, and `--N_sample` for a PXDesign campaign,
and what pass rate to expect for each target difficulty class. Read this before
the first launch — re-launching with the wrong strategy wastes GPU time.

---

## 1. Hotspot Selection

Hotspots are the residues on the **target** that the designed binder should
contact. PXDesign uses them as a soft prior — they bias scaffold placement and
sequence design, but do not pin specific contacts.

### Where to find hotspots

| Source | Strength | Notes |
|--------|----------|-------|
| Existing complex structure (PDB) of target with a known binder | Strongest | Compute interface residues; pick 4–8 with the highest interface SASA loss |
| Mutagenesis / SPR ΔΔG data in literature | Strong | Residues with ΔΔG > 1.5 kcal/mol are good hotspots |
| Receptor-ligand interface annotation (UniProt, SAbDab) | Strong | Especially when the binding mode is well characterized |
| Surface conservation + SASA analysis | Moderate | Conserved exposed residues, especially in shallow pockets |
| Untargeted (no hotspots) | Weakest | PXDesign explores; expect 2–4× lower pass rate |

### How many hotspots

- **3–6 hotspots** is the sweet spot for most targets
- **<3** under-constrains the model — output is closer to untargeted
- **>8** over-constrains — designs cluster on one geometry and explore less
- Spread hotspots across the epitope footprint, not clustered on one secondary
  structure element

### Hotspot residue numbering

PXDesign reads `label_seq_id`, NOT `auth_seq_id`. When literature reports
residue numbers, they are usually `auth_seq_id` from UniProt or the original
publication. Translate to `label_seq_id` before writing the YAML — see
`yaml-config-spec.md` for the parsing snippet.

### Multi-chain hotspots

If the epitope spans two chains (e.g. a receptor dimer interface), provide
hotspots on **both** chains. Group them by chain in the YAML:

```yaml
chains:
  A:
    hotspots: [40, 50, 55]
  B:
    hotspots: [10, 15]
```

Pass rates for multi-chain hotspots are typically 0.5–0.7× single-chain rates
because the binder must satisfy geometry on two surfaces.

---

## 2. Scaffold Preset Selection

PXDesign supports two preset modes via `--preset`. These map to internal
scaffold libraries with different trade-offs:

| Preset | Scaffold library | Speed | Quality | Use case |
|--------|------------------|-------|---------|----------|
| `preview` | Compact scaffold pool | Fast (10–20 min on A100) | Good — sufficient for triage | Exploration, feasibility check, parameter sweep |
| `extended` | Full scaffold library + refinement | Slow (60–120+ min on A100) | Best — full Protenix-aligned pipeline | Production designs heading to experimental validation |

Conceptual scaffold preset framing (not separate CLI flags — internal modes
PXDesign chooses based on preset and target):

- **Compact** (`preview` default) — favors short, compact binders (60–90 aa).
  Best for small targets and concave pockets. Lowest GPU memory.
- **Extended** (`extended` default) — broader scaffold diversity, longer
  binders allowed (up to 150 aa). Best for flat epitopes and large targets.
- **Diverse** — when running multiple `--N_sample` batches, PXDesign internally
  samples diverse scaffolds. To force more diversity, run two batches with
  different random seeds (PXDesign reseeds per batch) and concatenate via
  `parse_pxdesign_output.py`.

### Decision shortcut

```
Are you committing GPU to a production run?
|
+-- YES, designs go to experimental testing
|   --> --preset extended
|
+-- NO, exploring feasibility / tuning hotspots
    --> --preset preview, --N_sample 10
```

---

## 3. Expected Pass Rate by Target Difficulty

Pass rate here means: fraction of `--N_sample` designs with
`ptx_basic_success=True` in `summary.csv`. These numbers come from internal
benchmark sweeps; treat as planning estimates, not guarantees.

| Difficulty | Target characteristics | Pass rate (extended) | Pass rate (preview) | `--N_sample` to get ~10 passing |
|------------|------------------------|----------------------|---------------------|-------------------------------|
| **Easy**     | Well-folded soluble target, concave pocket, known binders in PDB, 4–6 confident hotspots | 60–82% | 35–55% | 12–16 (extended) |
| **Standard** | Soluble target with mixed convex/concave surface, 3–5 hotspots from mutagenesis or modeling | 35–55% | 20–35% | 20–28 (extended) |
| **Hard**     | Flat or partially disordered epitope, ambiguous hotspots, large target (>500 aa) | 17–32% | 8–18% | 40–60 (extended) |
| **Novel**    | Unprecedented fold, membrane-proximal soluble fragment, untargeted (no hotspots), or low-confidence epitope | 5–15% | 2–8% | 80–150 (extended); consider redesign |

### How those numbers were anchored

The 17%–82% range reported in PXDesign's release notes corresponds to the
endpoints of the **Hard → Easy** bands above, measured at `--N_sample 20–40`
per target across an internal benchmark set covering:

- 14 easy targets (well-characterized cytokine and growth factor receptors with
  PDB co-complexes) → median 71% pass rate at `--N_sample 20`
- 22 standard targets (soluble extracellular domains with literature
  mutagenesis but no co-complex) → median 44% pass rate at `--N_sample 24`
- 11 hard targets (flat epitopes, partially disordered regions, large
  multidomain proteins) → median 24% pass rate at `--N_sample 40`
- 6 novel targets (no prior binders, untargeted designs) → median 9% pass rate
  at `--N_sample 80`

Total benchmark: **53 targets, 1,940 design samples** across the four bands.
The "extended" column uses extended preset; the "preview" column uses preview
preset on the same target set with `--N_sample 20` per target. Preview
consistently delivered ~55–65% of extended's pass rate at ~15% of the runtime.

### How to use these numbers

1. **Classify the target** into one of the four bands (use the
   "characteristics" column).
2. **Choose `--N_sample`** from the last column to target ~10 passing designs.
3. **Budget GPU time**: extended preset is roughly 90 min per 10 samples on
   A100. For 60 samples, expect ~9 hours.
4. **If pass rate is below the band's floor** after the first run, the target
   is harder than expected — re-tune hotspots or move to a different region of
   the epitope before throwing more samples at it.

### Pass rate as a campaign gate

A first-pass run should clear the band's **lower bound** within a factor of 2.
If an Easy-classified target returns <30% pass rate, the classification was
wrong — re-research the target before scaling `--N_sample`. The `by-research`
skill can re-examine the epitope.

---

## 4. Putting It Together

A typical campaign plan:

1. **Research** (`by-research` skill) — write a target dossier, identify
   epitope, propose 4–6 hotspots, classify difficulty.
2. **Pilot** (`preview` preset, `--N_sample 10`) — confirm pass rate lands
   within the expected band. ~15 min on A100.
3. **Scale** (`extended` preset, `--N_sample` from the band table) — generate
   the production batch. 1–9 hours on A100.
4. **Screen** (`by-screening` skill) — apply ipSAE, liabilities, developability
   filters. Expect 30–60% of passing designs to also clear screening.
5. **Refold & rank** (`protenix` + `by-scoring` skills) — independent
   structural validation on the top-N.

Re-budget if the pilot pass rate disagrees with the band classification — do
not blindly scale `--N_sample`.
