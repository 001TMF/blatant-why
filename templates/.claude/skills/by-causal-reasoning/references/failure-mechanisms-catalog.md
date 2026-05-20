# Failure Mechanisms Catalog

The canonical list of biologic-design failure mechanisms recognized by
`by-causal-reasoning`. Each row is a **mechanism key** (used in
`hypotheses.json` as `mechanism`), the **telltale in-silico features** that
flag it, **recommended diagnostic assays** for the falsifiable prediction,
and **parameter levers** that `by-campaign-optimizer` can adjust.

This is the only file that defines mechanism keys. Adding a new mechanism
elsewhere without updating this file breaks the contract.

---

## Mechanism rows

### `steric_clash`

- **Description:** The designed binder physically overlaps with the target
  surface — the modeled complex resolves the clash by distorting the binder
  geometry or producing low-confidence regions at the interface.
- **Diagnostic signature (in-silico):**
  - High RMSD in CDR-H3 (>2.0 Å vs scaffold reference)
  - Low pLDDT (<60) localized to the clash region
  - Low ipSAE despite acceptable ipTM (interface is structurally bad but global fold is OK)
  - `discriminating_features` from `by-failure-diagnosis`: `rmsd` up, `plddt` down
- **Recommended assays:**
  - SPR or BLI to measure actual on-rate (kon)
  - DSF to assess thermostability of the designed binder alone
  - Mass spec / SEC to detect misfolding aggregates
- **Parameter levers:**
  - Shorten CDR-H3 or relax binding constraints
  - Increase BoltzGen sampling temperature
  - Add explicit hotspot avoid set near the clashing target residues

### `electrostatic_mismatch`

- **Description:** Net charge or charge distribution of the designed binder
  is incompatible with the target patch — repels productive docking even
  when shape complementarity is fine.
- **Diagnostic signature:**
  - Net charge distribution of PASS vs FAIL designs shifted by >3 units
  - pI of FAIL designs clustered far from target patch pI
  - Hotspot residue list dominated by like-charge target residues
  - `discriminating_features`: `net_charge` is highest-effect
- **Recommended assays:**
  - SPR at varying ionic strength to detect salt-dependent binding
  - Western or dot blot against charge variants of the target
  - AC-SINS for self-association tendency (orthogonal check)
- **Parameter levers:**
  - Bias scaffold selection toward complementary-charged frameworks
  - Add charge-pair constraints to PXDesign target YAML
  - Drop scaffolds with confounding surface charge

### `hydrophobic_aggregation`

- **Description:** A hydrophobic patch — often centered on a few exposed
  aromatic or aliphatic residues — drives self-association and aggregation,
  which presents downstream as low yield or polyspecificity.
- **Diagnostic signature:**
  - Aggregation-propensity region (APR) hits on the designed binder
  - Hydrophobic-surface-area fraction elevated in FAIL designs
  - `discriminating_features`: `hydrophobic_fraction` and `liabilities` both significant
  - Free Cys or exposed Trp in the CDR-H3 region
- **Recommended assays:**
  - HIC (hydrophobic interaction chromatography) to score retention
  - DLS or SEC-MALS for aggregate detection
  - AC-SINS for self-association
- **Parameter levers:**
  - Mask hydrophobic positions in design constraints
  - Lower BoltzGen temperature
  - Switch scaffold to one with a less hydrophobic framework

### `cryptic_epitope_inaccessibility`

- **Description:** The epitope used for design exists only in a low-occupancy
  conformation of the target; the dominant solution-state conformation buries
  the binding site. Designs look great in silico but cannot find the epitope
  in the wet experiment.
- **Diagnostic signature:**
  - Rare conformation in the source PDB (low occupancy or apo/holo conflict)
  - High B-factor / disorder in the target loop near the hotspots
  - In-silico ipSAE high but lab pass rate disconnected from in-silico ranking
  - Lab calibration (when available): high-ipSAE designs failing at the bench
- **Recommended assays:**
  - HDX-MS on the target to map solution-state dynamics
  - Conformation-selective antibody binding studies
  - Cryo-EM of the apo target to confirm dominant conformation
- **Parameter levers:**
  - Re-run `by-epitope-analysis` on an alternative target PDB
  - Switch to a conformation-stabilizing co-crystal as the design template
  - Consider trapped/locked target constructs

### `polyspecificity_or_off_target`

- **Description:** The designed binder has low specificity — binds
  non-cognate proteins, BSA, or polyclonal antigen mixtures. Often co-occurs
  with hydrophobic patches and high CDR charge variance.
- **Diagnostic signature:**
  - BSA-binding signal in screening assays
  - Elevated CDR hydrophobicity and net charge
  - Multiple in-silico screens show acceptable scores but biology rejects
  - `discriminating_features`: combination of `hydrophobic_fraction` AND `net_charge` both significant
- **Recommended assays:**
  - PSR (polyspecificity reagent) panel
  - Anti-DNA, anti-Hep2 cross-reactivity panels
  - SCM (surface charge map) and AC-SINS
- **Parameter levers:**
  - Apply developability filter pre-screen (skin CDR liabilities)
  - Add negative-design constraints (BSA, off-target)
  - Lower temperature, raise scaffold-fit weighting

### `kinetic_mismatch_slow_on_rate`

- **Description:** The binder reaches the bound state via a high barrier;
  the equilibrium affinity may be acceptable but on-rate is too slow for
  the intended use (e.g. acute neutralization).
- **Diagnostic signature:**
  - Shallow funnel in interaction energy landscape (when energy decomp computed)
  - Bound-state ipSAE high but transition-state metrics weak
  - In-silico pass but lab fails at kinetic readouts (SPR kon)
- **Recommended assays:**
  - SPR kon/koff partitioning
  - Stopped-flow fluorescence for fast-kinetic regimes
  - Competition assays at sub-saturating concentrations
- **Parameter levers:**
  - Bias scaffold to ones with longer CDR-H3 (entropy-driven approach)
  - Relax binding constraints to allow more conformational paths
  - Consider rigidification mutations to lower entropic penalty

### `allosteric_perturbation`

- **Description:** Binding induces a conformational change in the target
  greater than ~1 Å from the apo state, which may activate, inhibit, or
  destabilize the target unintentionally — and may invalidate the in-silico
  ipSAE/ipTM ranking entirely.
- **Diagnostic signature:**
  - Target backbone RMSD between predicted complex and apo structure >1 Å
  - pLDDT drops in target regions distal to the interface
  - In-silico screening pass but functional assays show off-effect
- **Recommended assays:**
  - HDX-MS comparing apo vs binder-bound target
  - Functional cell assay (does the target still do its job?)
  - Cryo-EM of the bound complex if possible
- **Parameter levers:**
  - Add target-rigidity constraints to PXDesign
  - Switch to an epitope distal to known allosteric sites
  - Consider intrabody / nanobody (smaller perturbation) over Fab

### `disulfide_or_ptm_issue`

- **Description:** Free cysteine residues, unintended disulfide pairings, or
  N-glycosylation sites at the interface compromise expression, folding, or
  function. Sometimes presents as low yield rather than low affinity.
- **Diagnostic signature:**
  - Free Cys count in designed binder >0
  - NxS/T glycosylation motif present in CDR region or at interface
  - Pyroglutamate or deamidation hotspots flagged by developability scan
  - `discriminating_features`: `liabilities` is the top discriminator
- **Recommended assays:**
  - Mass spec on expressed protein for PTMs
  - Reducing vs non-reducing SDS-PAGE for disulfide diagnosis
  - Glycoform analysis (LC-MS or lectin blot)
- **Parameter levers:**
  - Apply liability filter pre-design
  - Mutate problem positions in CDR or framework
  - Avoid scaffolds with known free Cys positions

---

## Diagnostic-feature to mechanism mapping

`generate_hypotheses.py` parses this table to map `discriminating_features`
from `by-failure-diagnosis` to candidate mechanisms. Each row in the diagnosis
contributes votes to one or more mechanisms.

| Feature (from diagnosis.json) | Primary mechanism | Secondary mechanism(s) |
|------------------------------|-------------------|------------------------|
| `rmsd` (FAIL > PASS) | `steric_clash` | `cryptic_epitope_inaccessibility` |
| `plddt` (FAIL < PASS) | `steric_clash` | — |
| `ipsae` / `ipsae_min` (FAIL < PASS) | (non-specific signal — too broad) | — |
| `iptm` (FAIL < PASS, ipSAE OK) | `cryptic_epitope_inaccessibility` | `allosteric_perturbation` |
| `net_charge` | `electrostatic_mismatch` | `polyspecificity_or_off_target` |
| `hydrophobic_fraction` | `hydrophobic_aggregation` | `polyspecificity_or_off_target` |
| `liabilities` | `disulfide_or_ptm_issue` | `hydrophobic_aggregation` |
| `cdr3_length` | `steric_clash` (if too long) / `kinetic_mismatch_slow_on_rate` (if too short) | — |

A feature with adjusted p-value < 0.05 contributes one vote to its primary
mechanism and 0.5 vote to each secondary. Mechanisms with score ≥1.0 become
candidate hypotheses; the script then queries `by-knowledge` for evidence.

---

## Mechanism vs correlation

**A hypothesis is a mechanism. A discriminating feature is a correlation.**

❌ Bad (correlation): *"Designs with low ipSAE failed."*
✅ Good (mechanism): *"Designs failed due to a hydrophobic patch at hotspot
residues 47-52 that drives self-aggregation, manifesting as low ipSAE."*

The catalog above provides the bridge: every claim sentence emitted by this
skill must name one of the mechanism keys defined here. Without that, the
claim is restating statistics, not explaining biology.

---

## Parsimony rule

The skill never emits more than 5 hypotheses. When the diagnosis surfaces
≥3 strongly significant features, the script combines compatible mechanisms
into a single composite hypothesis (e.g. `polyspecificity_or_off_target`
naturally subsumes `hydrophobic_aggregation` when both signal together).

When ≥6 mechanisms have score ≥1.0 after voting, the script writes the top
5 to `hypotheses.json` and notes the remaining mechanisms in
`evidence_trail.md` as deferred candidates — these become input to
`by-hypothesis-debate` if invoked.

---

## Empty graph

If `by-knowledge` is empty (no campaigns, no failures), the catalog still
defines candidate mechanisms — but with zero supporting evidence entities,
every candidate is rejected by the precedence table. The skill exits with
a `no_evidence` status and routes the user to populate `by-knowledge` from
prior campaigns first.

---

## Single-source rule

A mechanism must have ≥1 supporting evidence entity from `by-knowledge`. A
single Tier-1 (peer-reviewed or multi-campaign) entity is sufficient; a
single Tier-2 or Tier-3 entity yields SPECULATIVE confidence at best. See
[evidence-grading.md](evidence-grading.md#single-source-rule).

---

## Target normalization

Different campaigns may have used different spellings of the same target
(`TNF-alpha`, `TNFα`, `TNF_alpha`). The script's keyword search tries the
canonical form first, then a small set of common variants. If apparent
duplicates are detected (multiple distinct target names with overlapping
mechanism patterns), a warning is appended to `evidence_trail.md`.

---

## Extending the catalog

To add a mechanism:

1. Add a row in the **Mechanism rows** section above with the same field set.
2. Add a mapping row in **Diagnostic-feature to mechanism mapping**.
3. Add the mechanism key to the `CANONICAL_MECHANISMS` tuple at the top of
   `scripts/generate_hypotheses.py`.
4. Re-run `score_hypothesis_evidence.py` against any pre-existing
   `hypotheses.json` to ensure no orphan keys remain.

The catalog is the source of truth; the script imports from it.
