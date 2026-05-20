---
id: "skill_5166b5795e7f473d9c80c23c3cdcc903"
name: "boltzgen"
display-name: "BoltzGen — Antibody / Nanobody / Binder Design"
short-description: "Antibody, nanobody, and de novo binder design using BoltzGen (diffusion + AntiFold inverse folding + Protenix refolding). Use when the user needs to design a binder against a protein target with a known epitope or hotspot set."
category: "tool"
keywords: "antibody, nanobody, VHH, scFv, Fab, binder design, BoltzGen, diffusion, Protenix, AntiFold, ipSAE, ipTM, epitope, hotspot, scaffold, entities YAML"
version: "1.0"
last-updated: "2026-05-20"
---

# BoltzGen — Antibody / Nanobody / Binder Design

BoltzGen is an all-atom diffusion model that generates antibody, nanobody,
and de novo miniprotein backbones conditioned on a target structure and a
set of binding (hotspot) residues. Sequences are assigned by AntiFold, then
each design is independently refolded with Protenix to produce ipTM, pTM,
pLDDT, ipSAE, and CA-RMSD metrics. This skill teaches the exact
**Write → Bash → Read** pattern for invoking BoltzGen via its CLI on local
GPU (default), HPC (RunPod via `by-deploy-compute`), or Tamarind cloud.

The legacy CLI name was `proteus-ab`. It has been renamed to **BoltzGen**
throughout. If you see `proteus-ab` in older docs or scripts, treat it as
the same engine — the binary on PATH is now `boltzgen`.

---

## When to Use This Skill

Use BoltzGen when you have:

- ✅ **A cleaned target structure** (CIF or PDB) with unambiguous chain IDs
- ✅ **A defined epitope or hotspot set** expressed in `label_seq_id` numbering
- ✅ **A modality decision in hand** — VHH single-domain, full antibody Fab, or de novo miniprotein
- ✅ **GPU compute available** — local (CUDA-capable, ≥24 GB VRAM), HPC (RunPod), or Tamarind cloud
- ✅ **A design budget** — typical preview is 10–20 designs; production is 50–200

Do NOT use BoltzGen when:

- ❌ **You need to validate a known antibody sequence against a target** → use **Protenix** directly (no design needed)
- ❌ **You need to score or filter an existing batch of designs** → use **by-scoring** (ipSAE) and **by-screening**
- ❌ **No epitope is known or characterised** → run **by-research** + **by-epitope-analysis** first; designing with no `binding_types` is wasteful
- ❌ **You want a small-molecule binder** → BoltzGen designs proteins/peptides only
- ❌ **You need ranked, published results** → use **by-display** / `/by:results`

---

## Quick Start

A 20-design VHH preview against TNF-α (PDB 1TNF, epitope residues 45–52 and 78–85) on a local GPU:

```bash
# Step 1: write spec via the Write tool — see scripts/boltzgen_submit.py for a builder
# Step 2: submit (dry-run prints the command; remove --dry-run to launch)
python scripts/boltzgen_submit.py \
  --spec workspace/tnf_spec.yaml \
  --protocol nanobody-anything \
  --num-designs 20 \
  --budget 48 \
  --target local \
  --output workspace/tnf_out

# Step 3: parse results into a CSV with sequences + metrics
python scripts/parse_designs.py \
  --output-dir workspace/tnf_out \
  --csv workspace/tnf_designs.csv
```

Expected runtime: ~10–25 min on a single H100/A100 (Stage 4 Protenix refolding dominates).
Expected output: a CSV ranked by `iptm` descending, typically 60–80% of designs
with `iptm > 0.4`, 20–40% with `iptm > 0.6`.

---

## Installation

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| BoltzGen | ≥0.1.0 | MIT | ✅ Permitted | Clone https://github.com/HannesStark/boltzgen; install per repo README |
| Protenix | v1.x (368M) | Apache-2.0 | ✅ Permitted | Bundled with BoltzGen install; downloads weights on first run |
| AntiFold | ≥1.0 | MIT | ✅ Permitted | Bundled with BoltzGen install |
| CUDA toolkit | ≥11.8 | NVIDIA EULA | ✅ Permitted | Match your driver version |
| Python | ≥3.10 | PSF | ✅ Permitted | Use the conda env shipped by BoltzGen |
| pyyaml | ≥6.0 | MIT | ✅ Permitted | `pip install pyyaml` (used by the helper scripts) |

**System requirements:**

| Requirement | Details |
|-------------|---------|
| BoltzGen path env | `BOLTZGEN_DIR` (or legacy `PROTEUS_AB_DIR`) pointing at the repo clone |
| Model weights env | `PROTEUS_MODELS_DIR` — typically `~/.cache/boltzgen` |
| LayerNorm env | `LAYERNORM_TYPE=openfold` — **mandatory** for correct inference |
| GPU | CUDA-capable, ≥24 GB VRAM recommended (40 GB for `antibody-anything` with budget ≥ 128) |
| CLI binary | `boltzgen` (on PATH after env setup) |

**License Compliance:** All packages permit commercial use in AI applications.

For HPC (RunPod) deployment, see the **by-deploy-compute** skill — it handles
container image selection, secret injection, GPU type, and S3 mounting.
For Tamarind cloud, point the helper scripts at `--target tamarind`
(requires `TAMARIND_API_KEY` env var).

---

## Inputs

**Required:**

- **Target structure file** — CIF (preferred) or PDB
  - Single chain or multi-chain
  - Clean chain IDs (`A`, `B`, …) — no `0` or unusual letters
  - Resolved coordinates for the epitope region (no missing density)
- **Entities YAML spec** — see `references/entities-yaml-spec.md`
  - Lists the target file, chains to include, and `binding_types` epitope ranges
  - Optional scaffold entity (Fab framework or nanobody scaffold)
- **Protocol** — `nanobody-anything`, `antibody-anything`, `protein-anything`, `peptide-anything`, or `protein-redesign`

**Alternative inputs:**

- **Binding residue list (Python list of ints)** — converted to range notation by `boltzgen_submit.py` (see range table in `references/entities-yaml-spec.md`)
- **Pre-built scaffold YAML** — point a second entity at `$BOLTZGEN_DIR/example/fab_scaffolds/*.yaml` or `nanobody_scaffolds/*.yaml`

**Optional:**

- **MSA mode** — `none` (default), `precomputed` (A3M files), or `nim` (NVIDIA NIM API)
- **Budget** — diffusion steps; 48 preview, 96–128 production
- **`--prefilter`** — drops low-quality designs before the expensive Protenix refolding (recommended for `num_designs ≥ 50`)

⚠️ **CRITICAL:** Binding residues use `label_seq_id` (1-indexed, sequential, per-chain).
Mistakenly using `auth_seq_id` is the single most common cause of wasted campaigns.

See `references/entities-yaml-spec.md` for the full schema and conversion rules.

---

## Outputs

All outputs land under the directory passed as `--output`.

**Primary results:**

| File | Format | Description |
|------|--------|-------------|
| `final_ranked_designs/final_designs_metrics_*.csv` | CSV | Per-design metrics sorted by `iptm` descending |
| `final_ranked_designs/*.cif` | CIF | Refolded structures for each ranked design |
| `pae/*.npz` | NPZ | PAE matrices used to recompute ipSAE downstream |
| `designed_backbones/*.cif` | CIF | Stage-1 backbones (pre-refolding) |
| `run_config.json` | JSON | Reproducibility manifest — protocol, budget, seed, spec hash |

**CSV columns (in order):**

| Column | Type | Description |
|--------|------|-------------|
| `design_id` | string | Unique design identifier |
| `iptm` | float | Interface predicted TM-score (0–1) — primary ranking |
| `ptm` | float | Predicted TM-score (0–1) |
| `plddt` | float | Mean per-residue confidence (0–100) |
| `design_iptm` | float | Stage-1 ipTM before refolding |
| `ipsae_min` | float | Minimum of directional ipSAE scores (0–1) |
| `rmsd` | float | CA-RMSD between designed and refolded backbones (Å) |
| `sequence` | string | Full amino acid sequence of the designed chain(s) |

**Sorted by `iptm` descending.** Hard filters applied downstream by `by-scoring`:
`ipTM > 0.5`, `pLDDT > 70`, `RMSD < 3.5 Å`. The composite score combines
ipSAE_min (0.50), ipTM (0.30), and inverted liability count (0.20).

The helper script `scripts/parse_designs.py` flattens multi-seed ensembles
into a single CSV and adds the `seed` column.

---

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — confirm the target structure, epitope, and modality before running anything.

1. **Target structure (ASK THIS FIRST)** — Do you have a cleaned CIF/PDB for the target, with confirmed chain IDs? If only a UniProt accession, run **by-research** + **Protenix** first to obtain a structure.
2. **Epitope / hotspot residues** — Which residues should the binder target? Provide as a Python list of `label_seq_id` integers per chain. If unknown, run **by-epitope-analysis** first.
3. **Modality** — VHH single-domain, full antibody (VH/VL Fab), or de novo miniprotein? See `references/antibody-design-best-practices.md` for selection criteria.
4. **Design count** — How many designs? Preview (10–20) for quick sanity check; production (50–200) once epitope is validated.
5. **Compute target** — Local GPU (default), HPC via RunPod, or Tamarind cloud? Local is preferred when a GPU is present; HPC for batched runs > 100 designs.
6. **Scaffold preference** — Use a specific therapeutic framework (e.g., adalimumab) or let BoltzGen pick defaults? Most runs use defaults; specify a scaffold only when humanization or framework matching is required.
7. **MSA mode** — Default `none` is fine for the first pass. Switch to `precomputed` or `nim` only if pLDDT < 70 across the top designs.

See `references/antibody-design-best-practices.md` for the modality decision
tree and expected pass rates by target class.

---

## Standard Workflow

🚨 **MANDATORY: USE SCRIPTS EXACTLY AS SHOWN — DO NOT WRITE INLINE CODE** 🚨

This skill follows the Write → Bash → Read pattern. The two scripts under
`scripts/` are the canonical entry points.

### Step 1 — Write the entities YAML

Use the **Write** tool to create the spec file. The minimal form:

```yaml
# workspace/design_spec.yaml
entities:
- file:
    path: ./target.cif
    include:
    - chain:
        id: A
    binding_types:
    - chain:
        id: A
        binding: 45..52,78..85
```

Range notation rules and conversion tables: `references/entities-yaml-spec.md`.

✅ **VERIFICATION:** `yamllint workspace/design_spec.yaml` returns no errors.

### Step 2 — Submit via `boltzgen_submit.py`

```bash
python scripts/boltzgen_submit.py \
  --spec workspace/design_spec.yaml \
  --protocol nanobody-anything \
  --num-designs 20 \
  --budget 48 \
  --msa-mode none \
  --target local \
  --output workspace/output \
  --prefilter
```

Targets:

| Target | Behaviour |
|--------|-----------|
| `local` (default) | Invokes `boltzgen run` directly on the current host |
| `hpc` | Prints the deployment command and hands off to the **by-deploy-compute** skill |
| `tamarind` | Submits via Tamarind API (requires `TAMARIND_API_KEY`) |
| Add `--dry-run` to any target to print the command and exit | |

✅ **VERIFICATION:** Console shows `✓ boltzgen completed: <N> designs written to <path>` on success.

### Step 3 — Parse and rank

```bash
python scripts/parse_designs.py \
  --output-dir workspace/output \
  --csv workspace/designs.csv
```

This walks `final_ranked_designs/`, handles multi-seed ensembles by merging
all `final_designs_metrics_*.csv` files, and writes a single canonical CSV.

✅ **VERIFICATION:** Console shows `✓ parse_designs completed: <N> rows / <path>`.

### Step 4 — Hand off to `by-scoring` / `by-screening`

The CSV is the input to downstream skills. Do not re-derive metrics inline.

⚠️ **CRITICAL — DO NOT:**

- ❌ Write inline `subprocess.run(["boltzgen", ...])` calls → use `boltzgen_submit.py`
- ❌ Parse the CSV with ad-hoc `pd.read_csv` filtering → use `parse_designs.py` then `by-scoring`
- ❌ Edit the entities YAML by hand on every run → use the script's `--binding-residues` flag to generate ranges
- ❌ Use absolute `/mnt/...` paths in spec files → use paths relative to the spec file

---

## When Scripts Fail

Follow the standard script-failure hierarchy:

| Level | Frequency | Action |
|-------|-----------|--------|
| 1. Fix and Retry | 90% | Install missing package (`pip install pyyaml`), export missing env var (`LAYERNORM_TYPE=openfold`), re-run |
| 2. Modify Script | 5% | Edit `boltzgen_submit.py` or `parse_designs.py` to handle a new flag or output layout |
| 3. Use as Reference | 4% | Read the script, hand-craft a one-off `boltzgen run` invocation for unusual cases |
| 4. Write from Scratch | 1% | Only when BoltzGen's output schema has changed substantially — document why in `run_config.json` |

Common decision tree:

- Missing env var → Step 1 (`export LAYERNORM_TYPE=openfold; export PROTEUS_MODELS_DIR=~/.cache/boltzgen`)
- CUDA OOM → Step 1 (reduce `--num-designs` or `--budget`)
- New CLI flag in a BoltzGen upgrade → Step 2 (add the flag to `boltzgen_submit.py`)
- Multi-seed run with a non-standard directory layout → Step 3
- Output schema renamed columns → Step 4

---

## Decision Points

### Protocol selection

| Protocol | Format | Chains | Designs / Run | When to Choose |
|----------|--------|--------|---------------|----------------|
| `nanobody-anything` | VHH single-domain | 1 | 10–50 | Fast iteration, tissue penetration, intracellular delivery |
| `antibody-anything` | VH/VL Fab pair | 2 | 20–100 | Fc effector function, higher affinity, therapeutic format |
| `protein-anything` | De novo miniprotein | 1 | 10–100 | When PXDesign is unavailable or failing; novel binders 65–150 aa |
| `peptide-anything` | Linear peptide | 1 | 20–100 | Short binders, MHC ligands, cell-penetrating peptides |
| `protein-redesign` | Redesign existing | 1 | 10–50 | Improving an existing binder's affinity or expression |

### Compute target

| Target | When to Use | Cost Order |
|--------|-------------|-----------|
| `local` (default) | A GPU is present; ≤ 100 designs; iterating on epitope or scaffold | Cheapest |
| `hpc` (RunPod via by-deploy-compute) | Batches > 100 designs; need A100/H100 you don't own | Medium |
| `tamarind` (cloud fallback) | No GPU, no HPC access, willing to pay per run | Highest |

### MSA mode

| Mode | When |
|------|------|
| `none` | Default. Sufficient for most runs |
| `precomputed` | You have MMseqs2 / HHblits A3M files and top designs show pLDDT < 70 |
| `nim` | Remote MSA needed and NIM API key available |

See `references/antibody-design-best-practices.md` for budget × protocol × hit-rate guidance.

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `FileNotFoundError` on model weights | `PROTEUS_MODELS_DIR` not set | `export PROTEUS_MODELS_DIR=~/.cache/boltzgen` and verify weights are present | `references/entities-yaml-spec.md` |
| `LAYERNORM_TYPE` error or silent NaNs | Env var missing | `export LAYERNORM_TYPE=openfold` before every run | — |
| All designs have `iptm < 0.4` | Bad epitope (buried residues, wrong numbering) | Re-verify with `auth_seq_id`→`label_seq_id` conversion; check SASA > 0.25 for all epitope residues | `references/antibody-design-best-practices.md` |
| CUDA OOM during Stage 4 (refolding) | Target + binder too large for VRAM | Reduce `--num-designs`, drop `--budget` to 48, or move to HPC with 80 GB GPU | `references/pipeline-stages.md` |
| No CSV in `final_ranked_designs/` | Run failed silently or output dir wrong | `find <output> -name 'final_designs_metrics_*.csv'`; check `run_config.json` and stderr | — |
| Very similar sequences across all designs | Budget too low; diversity not explored | Increase `--budget` to 96–128; try a different scaffold | `references/antibody-design-best-practices.md` |
| `auth_seq_id` used in `binding:` | Wrong residues targeted | Convert to `label_seq_id`; the spec uses 1-indexed sequential numbering per chain | `references/entities-yaml-spec.md` |
| Spaces in range notation (`7..12, 27..34`) | YAML parses but BoltzGen rejects | Remove spaces: `7..12,27..34` | `references/entities-yaml-spec.md` |
| Scaffold path not found | `$BOLTZGEN_DIR` not expanded | Use an absolute path or shell-expand before writing the YAML | — |
| `antibody-anything` slower than expected | Single-chain VHH was the right choice | Switch to `nanobody-anything` unless Fc / Fab is required | `references/antibody-design-best-practices.md` |
| MSA mode `nim` very slow | NIM API latency | Use `none` for iteration; switch only when pLDDT < 70 persists | — |
| Stage-3 pre-filter discards > 80% | Bad backbones from Stage 1 (wrong epitope) | Re-examine binding residues; try a different scaffold | `references/pipeline-stages.md` |
| Multi-seed CSV columns differ across seeds | Older BoltzGen versions changed schema | `parse_designs.py` normalises columns; upgrade BoltzGen if persistent | — |
| `boltzgen: command not found` | PATH not set after env activation | Activate the BoltzGen conda env or add `$BOLTZGEN_DIR/bin` to PATH | — |
| HPC submission stalls in queue | Wrong GPU class requested | See **by-deploy-compute** for RunPod GPU selection | — |

---

## Best Practices

1. 🚨 **CRITICAL:** Always export `LAYERNORM_TYPE=openfold` and `PROTEUS_MODELS_DIR` before running — silent NaNs otherwise.
2. 🚨 **CRITICAL:** Binding residues use `label_seq_id`, not `auth_seq_id`. Verify the conversion before launching.
3. ✅ **REQUIRED:** Run a 10–20 design preview before any production run > 50 designs. Confirms epitope is reachable.
4. ✅ **REQUIRED:** Enable `--prefilter` for `num_designs ≥ 50`. Saves 20–50% GPU time.
5. ✅ Prefer **local GPU** as the default compute target. Only escalate to HPC (RunPod) for batches > 100 or when no local GPU is available. Tamarind is the last-resort cloud fallback.
6. ✅ Choose VHH (`nanobody-anything`) unless Fc effector function is required — faster, fewer designs needed.
7. ✅ Use the helper scripts (`boltzgen_submit.py`, `parse_designs.py`); do not hand-craft `boltzgen run` invocations.
8. ✅ Always pass output to **by-scoring** and **by-screening** — never rank by `iptm` alone for a final shortlist.
9. ✨ **Optional:** Pin a specific Fab scaffold when humanization is a downstream requirement (see scaffold catalog below).
10. ❌ **DON'T** rerun a campaign with a different epitope without first checking SASA — buried residues waste compute.

---

## Suggested Next Steps

After BoltzGen completes, route through the standard scoring → screening → display pipeline.

| Next skill | Why |
|------------|-----|
| **by-scoring** | Recompute ipSAE_min from PAE matrices; apply hard filters (`ipTM > 0.5`, `pLDDT > 70`, `RMSD < 3.5 Å`); produce composite score |
| **by-screening** | Run the full screening battery — liabilities, developability, MHC II, aggregation; outputs `PASS` / `FAIL` per design |
| **by-display** | Format the ranked shortlist into a human-readable table (`/by:results`) |
| **by-campaign-manager** | Update campaign state (`campaignState.designs[]`), checkpoint, and decide on next iteration |
| **by-epitope-analysis** | If all designs failed, re-examine the epitope (SASA, conservation, structural accessibility) |
| **by-failure-diagnosis** | If `pass rate` is < 5%, classify the failure mode (epitope / scaffold / numerical) |

Chain rationale: BoltzGen produces raw structural metrics; **by-scoring** normalises
and combines them; **by-screening** adds biophysical filters; **by-display** is the
user-facing artifact. The campaign manager closes the loop with state and history.

---

## Related Skills

**Upstream (run before BoltzGen):**

- **by-research** — Target dossier, prior art, scaffold suggestions
- **by-epitope-analysis** — Hotspot residues with SASA and conservation
- **by-hypothesis-debate** — Strategy selection (modality, scaffold, budget) when multiple approaches are viable
- **Protenix** — If only a sequence is available, predict the target structure first

**Downstream (run after BoltzGen):**

- **by-scoring** — ipSAE recomputation + composite score
- **by-screening** — Full developability and liability battery
- **by-display** — Format and present ranked designs
- **by-campaign-manager** — State checkpoint and next-iteration decision

**Alternative / complementary:**

- **pxdesign** — De novo miniprotein binder design (non-antibody). Use `boltzgen` `protein-anything` only as a fallback when pxdesign is unavailable.
- **by-deploy-compute** — HPC (RunPod) and Tamarind deployment details for offloading BoltzGen runs

---

## Scaffold Templates

Pre-built scaffold YAMLs ship with BoltzGen under `$BOLTZGEN_DIR/example/`.
Add a second entity in the spec to use one; omit for built-in defaults.

### Fab scaffolds (14)

| Scaffold | PDB | File |
|----------|-----|------|
| Adalimumab | 6cr1 | `fab_scaffolds/adalimumab.6cr1.yaml` |
| Belimumab | 7m3n | `fab_scaffolds/belimumab.7m3n.yaml` |
| Crenezumab | 5vzo | `fab_scaffolds/crenezumab.5vzo.yaml` |
| Dupilumab | 8d96 | `fab_scaffolds/dupilumab.8d96.yaml` |
| Golimumab | 5wuv | `fab_scaffolds/golimumab.5wuv.yaml` |
| Guselkumab | 7unp | `fab_scaffolds/guselkumab.7unp.yaml` |
| mAb1 | 7q0g | `fab_scaffolds/mab1.7q0g.yaml` |
| Necitumumab | 5stx | `fab_scaffolds/necitumumab.5stx.yaml` |
| Nirsevimab | 8hkq | `fab_scaffolds/nirsevimab.8hkq.yaml` |
| Sarilumab | 7moe | `fab_scaffolds/sarilumab.7moe.yaml` |
| Secukinumab | 5yy2 | `fab_scaffolds/secukinumab.5yy2.yaml` |
| Tezepelumab | 6oaj | `fab_scaffolds/tezepelumab.6oaj.yaml` |
| Tralokinumab | 6ux9 | `fab_scaffolds/tralokinumab.6ux9.yaml` |
| Ustekinumab | 3hn3 | `fab_scaffolds/ustekinumab.3hn3.yaml` |

### Nanobody scaffolds (4)

| Scaffold | PDB | File |
|----------|-----|------|
| Caplacizumab | 7eow | `nanobody_scaffolds/caplacizumab.7eow.yaml` |
| Vobarilizumab | 7xl0 | `nanobody_scaffolds/vobarilizumab.7xl0.yaml` |
| Gefurulimab | 8coh | `nanobody_scaffolds/gefurulimab.8coh.yaml` |
| Ozoralizumab | 8z8v | `nanobody_scaffolds/ozoralizumab.8z8v.yaml` |

Example with explicit scaffold:

```yaml
entities:
- file:
    path: ./target.cif
    include:
    - chain:
        id: A
    binding_types:
    - chain:
        id: A
        binding: 45..52,78..85
- file:
    path: $BOLTZGEN_DIR/example/fab_scaffolds/adalimumab.6cr1.yaml
```

---

## References

**Detailed documentation:**

- [`references/entities-yaml-spec.md`](references/entities-yaml-spec.md) — Full schema for the entities YAML: target entity, include blocks, binding ranges, scaffold entities, and common mistakes.
- [`references/pipeline-stages.md`](references/pipeline-stages.md) — Six-stage internal pipeline (Design → Inverse Fold → Pre-filter → Refold → Analysis → Filtering) with per-stage timing and success indicators.
- [`references/antibody-design-best-practices.md`](references/antibody-design-best-practices.md) — VHH vs scFv vs Fab selection, MSA mode choice, expected pass rates by target difficulty, hotspot count recommendations.

**Scripts:**

- [`scripts/boltzgen_submit.py`](scripts/boltzgen_submit.py) — Reads the entities YAML + flags, builds the CLI command, and invokes locally or hands off to HPC / Tamarind. Supports `--dry-run`.
- [`scripts/parse_designs.py`](scripts/parse_designs.py) — Walks a BoltzGen output directory, merges multi-seed CSVs, and writes a single canonical CSV of design IDs, scores, and sequences.

**External documentation:**

- BoltzGen repository — https://github.com/HannesStark/boltzgen
- Protenix (refolding engine) — https://github.com/bytedance/Protenix
- AntiFold (inverse folding) — https://github.com/oxpig/AntiFold

**License:** All referenced engines (BoltzGen, Protenix, AntiFold) permit commercial use.
