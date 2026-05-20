---
id: "skill_1e4ec544986d41da9964c6db5f309c53"
name: "by-epitope-analysis"
display-name: "BY Epitope Analysis"
short-description: "Interface identification, residue classification, and hotspot scoring for protein and antibody binder design. Use when selecting hotspot residues for PXDesign or BoltzGen input from a co-crystal structure."
category: "research"
keywords: "epitope, hotspot, interface, contact analysis, PDB, druggability, pocket, design input"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: ["mcp__by-pdb__pdb_search", "mcp__by-pdb__pdb_get_chains", "mcp__by-pdb__pdb_download", "mcp__by-pdb__pdb_interface_residues"]
---

# Skill: BY Epitope Analysis

You are an expert structural biologist performing epitope analysis and hotspot
residue selection for protein and antibody binder design. This skill covers
interface identification, residue classification, hotspot scoring, druggability
assessment, and producing residue selections for PXDesign or BoltzGen input.

---

## When to Use This Skill

Use this skill when you need to:
- ✅ Convert a co-crystal structure into a hotspot residue list for PXDesign / BoltzGen
- ✅ Classify and score interface residues from a target+binder PDB entry
- ✅ Decide whether an epitope is concave/convex/flat and pick a design tool accordingly
- ✅ Assess druggability of an epitope for biologics
- ✅ Refine an epitope selection produced by `by-research` before committing to design

**Don't use this skill for:**
- ❌ Sequence-only target analysis with no structure → use `by-research` to find a structure first
- ❌ Picking PDB entries from a target name → use `mcp__by-pdb__pdb_search` directly
- ❌ Predicting structures from sequence → use Protenix (see `protenix` skill)
- ❌ Liability scanning (CDR loops, developability) → use `by-screening`

---

## Quick Start

Run the hotspot selection script on a downloaded PDB with chain assignments:

```bash
python scripts/select_hotspots.py \
  --pdb /tmp/5JXE.cif \
  --target-chain A \
  --binder-chains H,L \
  --cutoff 5.0 \
  --top-n 6 \
  --out /tmp/hotspots.json
```

Expected output:
```
✓ Loaded structure 5JXE
✓ Interface residues detected: 18 (cutoff 5.0 A)
✓ Ranked 18 candidates; selected 6 hotspots
✓ Wrote /tmp/hotspots.json
```

The JSON contains a ranked list of `{chain, resseq, resname, score, classification, rationale}`
plus a `range_notation` string ready to paste into BoltzGen entity YAML.

---

## Installation

| Software | Version | License | Commercial Use | Installation Command |
|----------|---------|---------|----------------|---------------------|
| Python | ≥3.9 | PSF | ✅ Permitted | preinstalled |
| BioPython | ≥1.81 | Biopython License | ✅ Permitted | `pip install biopython` |
| NumPy | ≥1.24 | BSD-3 | ✅ Permitted | `pip install numpy` |

**License Compliance:** All packages permit commercial use in AI applications.

**System requirements:** No GPU. ~50 MB RAM per structure. Network only required if
downloading PDB entries (the script accepts a local CIF/PDB path).

---

## Inputs

**Required:**
- **Structure file** (CIF or PDB): co-crystal of target + binder
  - Resolution < 3.0 A strongly preferred; flag entries > 3.5 A
  - Single biological assembly (run `pdb_get_chains` to confirm chain labels)
- **Target chain ID** (e.g., `A`): the antigen
- **Binder chain ID(s)** (e.g., `H,L` for Fab, `H` for VHH): the existing binder

**Alternative inputs:**
- **PDB ID** (e.g., `5JXE`): fetched via `mcp__by-pdb__pdb_download` before analysis
- **Pre-computed interface JSON** from `mcp__by-pdb__pdb_interface_residues`: skips
  the structural pass and goes straight to scoring

**Optional:**
- **Distance cutoff** (default 5.0 A): see Decision Points
- **Top-N** (default 6): how many hotspots to return
- **Exclude residues**: glycosylation sites, mutation-sensitive positions

See `references/hotspot-scoring.md` for the full scoring rubric and threshold guidance.

---

## Outputs

**Primary results** (written to `--out` path):
- `hotspots.json`:
  ```json
  {
    "pdb_id": "5JXE",
    "target_chain": "A",
    "binder_chains": ["H", "L"],
    "cutoff_a": 5.0,
    "interface_size_a2": 1080.0,
    "topology": "flat",
    "druggability": "moderate",
    "hotspots": [
      {"chain": "A", "resseq": 56, "resname": "TYR", "score": 0.91,
       "classification": "polar_anchor", "rationale": "Aromatic + H-bond, buried at 4.0 A"}
    ],
    "range_notation": "A54,A56,A58,A61,A63,A68",
    "boltzgen_binding": "54,56,58,61,63,68",
    "pxdesign_hotspots": [54, 56, 58, 61, 63, 68]
  }
  ```

**Reports:**
- Console summary table (residue, score, classification, rationale)
- Topology + druggability classification with recommended design tool

**Downstream-ready formats:**
- `boltzgen_binding` string ready to drop into entity YAML `binding:` field
- `pxdesign_hotspots` int list ready for PXDesign target YAML

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST.** Always confirm the user has a co-crystal structure
or a justified single-chain target before proceeding.

1. **Structure available?** (ASK THIS FIRST)
   - Do you have a co-crystal PDB ID, a local CIF/PDB file, or only a sequence?
   - If sequence-only: route to `by-research` to find a structure first.
2. **Target identity:** Which chain is the antigen vs the binder? (We need both
   labels — `pdb_get_chains` returns chain composition.)
3. **Resolution check:** Is the structure < 3.0 A? Cryo-EM acceptable above 3.0 A
   only if the interface region is well-resolved. See `references/interface-classification.md`.
4. **Design modality:** PXDesign (de novo binder) vs BoltzGen (antibody/nanobody)?
   This affects how many hotspots to recommend and whether to prefer concave epitopes.
5. **Constraints:** Any residues to exclude (e.g., known glycosylation sites,
   essential function residues, prior mutational dead spots)?
6. **Interface scope:** Strict contacts only (4.0 A) or extended packing (6.0 A)?
   Default 5.0 A balances both. See Decision Points.
7. **Primary objective:** Maximum specificity (more polar anchors) or maximum
   binding energy (more hydrophobic core)? Defaults to 60% buried / 40% polar.

---

## Standard Workflow

🚨 **MANDATORY: USE THE PROVIDED SCRIPT — DO NOT WRITE INLINE BIOPYTHON CODE** 🚨

**This skill uses low-freedom script execution.** You must:
- ✅ Run `scripts/select_hotspots.py` for the scoring + selection
- ✅ Use `mcp__by-pdb__*` for structure fetching and chain identification
- ❌ NOT write inline BioPython parsers — they will diverge from the scoring rubric

### Step 1: Find and validate the structure

```
mcp__by-pdb__pdb_search(query="PD-L1 pembrolizumab complex", max_results=5)
```

Pick the entry with best resolution. Verify with:
```
mcp__by-pdb__pdb_get_chains(pdb_id="5JXE")
```

✅ **VERIFICATION:** Expected message lists target chain and binder chain(s) with
sequence lengths matching the expected protein.

### Step 2: Download the structure

```
mcp__by-pdb__pdb_download(pdb_id="5JXE", format="cif", output_dir="/tmp")
```

✅ **VERIFICATION:** Expect `/tmp/5JXE.cif` exists.

### Step 3: Detect the interface (two cutoffs)

```
mcp__by-pdb__pdb_interface_residues(pdb_id="5JXE", chain1="A", chain2="H", distance_cutoff=5.0)
mcp__by-pdb__pdb_interface_residues(pdb_id="5JXE", chain1="A", chain2="H", distance_cutoff=4.0)
```

Residues present at both cutoffs are the buried core.

### Step 4: Run hotspot selection

```bash
python scripts/select_hotspots.py \
  --pdb /tmp/5JXE.cif \
  --target-chain A \
  --binder-chains H,L \
  --cutoff 5.0 \
  --top-n 6 \
  --out /tmp/5JXE_hotspots.json
```

✅ **VERIFICATION:** Console prints `✓ Wrote /tmp/5JXE_hotspots.json` with the
selected residues and topology.

### Step 5: Feed hotspots into the design tool

For PXDesign (see `pxdesign` skill for full YAML):
```yaml
target:
  file: /tmp/5JXE.cif
  chains:
    A:
      hotspots: [54, 56, 58, 61, 63, 68]
```

For BoltzGen (see `boltzgen` skill for full entities spec):
```yaml
entities:
- file:
    path: /tmp/5JXE.cif
    include:
    - chain: {id: A}
    binding_types:
    - chain: {id: A, binding: "54,56,58,61,63,68"}
```

⚠️ **CRITICAL — DO NOT:**
- ❌ Pass `author_seq_id` (sometimes called `auth_seq_id`) when the design tool
  expects `label_seq_id`. The script outputs `label_seq_id` — match this.
- ❌ Skip the dual-cutoff step. Single-cutoff selection picks rim residues.
- ❌ Use cryo-EM entries > 4.0 A for hotspot selection without manual review.

---

## When Scripts Fail

Follow the **Script Failure Hierarchy** when something breaks:

1. **Fix and Retry (90%)** — Install BioPython: `pip install biopython`. Confirm
   the CIF path exists. Confirm chain IDs are present in the file.
2. **Modify Script (5%)** — If the structure has unusual chain naming
   (e.g., `AAA` instead of `A`), edit `scripts/select_hotspots.py` to relax the
   chain-label assertion.
3. **Use as Reference (4%)** — Read the script logic, replicate the scoring in
   a notebook for one-off non-standard structures (NMR ensembles, multi-model).
4. **Write from Scratch (1%)** — Only for genuinely novel formats (e.g.,
   AlphaFold Multimer JSON with no PDB output). Document why in a comment.

**Decision tree:** Missing package? → Step 1. Script raises KeyError on chain? → Step 2.
Unusual structure format? → Step 3. No PDB-like file at all? → Step 4.

---

## Decision Points

### Distance cutoff

| Cutoff | Use case |
|--------|----------|
| 4.0 A  | Strict direct contacts (H-bonds, salt bridges) |
| 5.0 A  | Standard analysis (default, recommended) |
| 6.0 A  | Extended interface with second-shell packing |
| 8.0 A  | Broad epitope mapping with solvent-mediated contacts |

Start at 5.0 A. If contact count < 20, widen to 6.0 A. If > 200, tighten to 4.0 A.
Always run at both 5.0 A and 4.0 A — residues present at both are the buried core.

### Hotspot count by interface size

| Interface size | Hotspot count | Rationale |
|---------------|---------------|-----------|
| Small (< 800 A^2, < 15 residues) | 3-4 | Most of the interface is essential |
| Medium (800-1500 A^2, 15-30 residues) | 5-6 | Focus on the energetic core |
| Large (> 1500 A^2, > 30 residues) | 6-8 | Select the dominant patch |

### Design tool by topology

| Topology | Recommended engine | Rationale |
|----------|--------------------|-----------|
| Concave (pocket/groove) | PXDesign | Diffusion fills pockets with complementary protrusions |
| Convex (dome/ridge) | BoltzGen | CDR loops wrap convex surfaces well |
| Flat | Either; prefer BoltzGen for larger interfaces | Distribute hotspots; 2+ polar anchors at edges |
| Linear (peptide-like) | BoltzGen (antibody-anything) | CDRs handle linear epitopes; PXDesign struggles |

See `references/interface-classification.md` for the full topology decision tree.

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `KeyError: chain 'A' not found` | Author chain IDs differ from label chain IDs | Inspect with `pdb_get_chains`; pass the label_asym_id | `references/interface-classification.md#chain-labels` |
| 0 interface residues detected | Wrong chain pair, or chains not in contact | Re-run with the correct binder chain; verify with `pdb_get_chains` | `references/interface-classification.md#troubleshooting` |
| Too many contacts (>200) | Crystal packing or oversized cutoff | Tighten to 4.0 A; confirm biological assembly is loaded | `references/hotspot-scoring.md#contact-density` |
| Hotspots scattered (>15 A apart) | Multiple distinct epitopes in same chain pair | Cluster residues spatially; pick the largest patch | `references/hotspot-scoring.md#spatial-contiguity` |
| All-hydrophobic selection | Polar anchors filtered out by raw contact count | Lower polar threshold; force ≥30% polar anchors via `--polar-min 2` | `references/hotspot-scoring.md#balance` |
| Druggability score low (DoGSite < 0.4) | Flat or solvent-exposed epitope | Prefer BoltzGen over PXDesign; widen hotspot set | `references/druggability-metrics.md` |
| `BioPython not installed` | Missing dependency | `pip install biopython` | Installation table above |
| Glycosylation site selected as hotspot | N-X-S/T motif near interface | Exclude with `--exclude A78`; verify with UniProt | `references/druggability-metrics.md#glycans` |
| Antibody chain treated as target | Reversed chain assignment | Swap `--target-chain` and `--binder-chains` | Clarification Q2 |
| Resolution > 3.5 A entry | Low-quality structure | Either use Protenix to refold, or accept with explicit caveat in the report | `references/interface-classification.md#resolution` |
| Multiple symmetry mates contacting | Asymmetric unit has duplicates | Use biological assembly (assembly 1); filter duplicate chains | `references/interface-classification.md#assemblies` |
| Disordered loops in interface | Missing density for key residues | Flag missing residues; consider Protenix prediction | `references/interface-classification.md#disorder` |

---

## Best Practices

1. 🚨 **CRITICAL:** Always run the script — do NOT write inline interface code.
2. ✅ **REQUIRED:** Confirm chain assignments with `pdb_get_chains` before selecting hotspots.
3. ✅ **REQUIRED:** Use dual cutoffs (4.0 A + 5.0 A) to identify the buried core.
4. ✅ Target 60-70% buried / 30-40% polar anchor balance.
5. ✅ Verify spatial contiguity — all hotspots within 12-15 A of a neighbor.
6. ✅ Classify topology (concave/convex/flat/linear) before picking a design tool.
7. ✅ Cross-check druggability score; reject if DoGSite-like score < 0.2.
8. ❌ DON'T select more than 8 hotspots — over-constrains backbone sampling.
9. ❌ DON'T use author_seq_id when the design tool wants label_seq_id.
10. ✨ **Optional:** Run analysis on 2-3 co-crystals of the same target to find
    consensus hotspots; reduces single-structure bias.

---

## Suggested Next Steps

After producing a hotspot list, route to one of:

- **`pxdesign`** — De novo binder design when topology is concave/pocket; the
  hotspot list goes into the target YAML.
- **`boltzgen`** — Antibody or nanobody design when topology is convex/flat/linear;
  the `boltzgen_binding` string goes straight into the entity YAML.
- **`by-design-workflow`** — Full campaign orchestration if this is a new target.
- **`by-research`** — If druggability is low and no good co-crystal exists, return
  to research for alternative epitopes or homolog-based hotspot transfer.
- **`by-screening`** — After designs are generated, screen against the hotspot set
  to confirm engagement at intended residues.

**Why chaining matters:** the hotspot JSON is the canonical contract between
research (where) and design (how). Skipping this step forces the design engine to
explore the entire surface — wasteful and lower hit rate.

---

## Related Skills

**Upstream (run first):**
- `by-research` — produces a research dossier including a candidate PDB ID
- `protenix` — refolds the target if the resolution is too low for direct analysis

**Downstream (run after):**
- `pxdesign`, `boltzgen` — consume the hotspot list as design input
- `by-screening` — verifies designs engage the chosen hotspots

**Alternative/Complementary:**
- `by-research` Phase 5 — produces preliminary hotspots; this skill refines them
- `by-knowledge` — retrieves prior epitope analyses for the same target

---

## References

**Detailed documentation:**
- `references/hotspot-scoring.md` — Residue importance scoring (contact frequency,
  conservation, surface accessibility, energy contribution) with thresholds.
- `references/interface-classification.md` — Pocket vs flat vs groove vs linear
  topology detection and design-tool implications.
- `references/druggability-metrics.md` — DoGSiteScorer-style metrics, FPocket
  scores, biologics druggability thresholds.

**Scripts:**
- `scripts/select_hotspots.py` — CLI hotspot selection from PDB + chain assignments
  using BioPython. Outputs ranked residues with scores and rationale, plus
  range notation for BoltzGen and PXDesign.

**Official documentation:**
- [BioPython Bio.PDB tutorial](https://biopython.org/wiki/The_Biopython_Structural_Bioinformatics_FAQ)
- [PDB label_seq_id vs auth_seq_id](https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/_atom_site.label_seq_id.html)
- [DoGSiteScorer pocket detection](https://proteins.plus/help/dogsite_help)

**Key Papers:**
- [Clackson & Wells 1995](https://doi.org/10.1126/science.7529940) — O-ring hotspot
  hypothesis; alanine-scan basis for hotspot scoring.
- [Bogan & Thorn 1998](https://doi.org/10.1006/jmbi.1998.1843) — Hot spots in
  protein-protein interfaces.
- [Volkamer et al. 2012](https://doi.org/10.1093/bioinformatics/bts310) —
  DoGSiteScorer druggability metrics.

**License:** All referenced tools and datasets permit commercial use in AI applications.
