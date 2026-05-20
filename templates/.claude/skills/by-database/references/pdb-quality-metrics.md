# PDB Quality Metrics — Reference

Detailed guidance for evaluating PDB entries before using them in BY design or
analysis workflows. Use alongside `mcp__by-pdb__pdb_search`,
`mcp__by-pdb__pdb_fetch_structure`, and `mcp__by-pdb__pdb_get_chains`.

---

## 1. Resolution Thresholds

Resolution measures how reliably individual atoms are placed. Lower is better
(X-ray) — but the threshold depends on what you plan to do with the structure.

| Use case | X-ray ceiling | Cryo-EM ceiling | Notes |
|----------|---------------|-----------------|-------|
| Hotspot residue identification (`pdb_interface_residues`) | ≤2.5 Å | ≤3.0 Å | Side-chain rotamers must be reliable |
| BoltzGen template / CDR conformation | ≤2.5 Å | ≤3.0 Å | CDRH3 backbone accuracy matters |
| PXDesign target scaffold | ≤3.0 Å | ≤3.5 Å | Backbone + Cβ sufficient |
| Topology / fold reference only | ≤3.5 Å | ≤4.0 Å | Domain architecture only |
| Sequence reference | any | any | Sequence is independent of resolution |

**NMR entries** (`method = "SOLUTION NMR"`) have no resolution. Use the ensemble
size and look-up of constraint violations as proxies; prefer X-ray or cryo-EM
when both exist.

**Multiple methods on one entry** (e.g. neutron + X-ray): the
`resolution_combined` field returned by the data API is the best single number.

---

## 2. Holo vs. Apo

| State | Definition | When to use |
|-------|-----------|-------------|
| Holo | Bound to ligand, antibody, or partner | Interface residues, hotspots, CDR conformations |
| Apo | Unbound | Topology, fold confirmation, baseline conformation |

Quick check after `pdb_get_chains`:

- If `polymer_entity_count == 1` and no `non_polymer` ligands → likely apo.
- If multiple polymer chains AND `pdb_interface_residues` returns non-zero
  `contact_count` between them → holo.
- For antibody complexes, holo means an antigen chain is present and listed in
  SAbDab's `antigen_chain` field.

**Do not** report interface residues from an apo structure — the side chains
will be in unbound rotamers and contacts will be missing or misleading.

---

## 3. Organism Filtering

Match organism to your design goal:

- **Therapeutic antibody** → human antigen (Homo sapiens). Mouse / rat
  structures are useful as references but the final design must hit the human
  ortholog.
- **Tool / research reagent** → any organism, but document the species in the
  final report.
- **Cross-species programs** (e.g. HCMV across primates) → run
  `find_similar_targets.py` to map orthologs explicitly.

The organism field comes from
`rcsb_entity_source_organism.scientific_name` on polymer entity 1. For
multi-entity complexes (antibody + antigen), check the polymer entity that
corresponds to the **target** chain, not the antibody chain.

---

## 4. Missing Residues and Structural Completeness

Crystal structures rarely model 100% of the construct. Missing residues fall
into three categories:

| Category | Why it matters |
|----------|---------------|
| Disordered loops (no density) | Cannot use as hotspots; may indicate flexibility |
| N-/C-terminal truncations | Construct boundaries; the canonical sequence is longer |
| Tags removed for clarity | Sequence in PDB ≠ sequence used in expression |

Detect these by:

1. Comparing the PDB chain sequence (`pdbx_seq_one_letter_code_can`) to the
   UniProt canonical sequence.
2. Looking for `pdbx_unobs_or_zero_occ_residues` in the entry data (advanced
   queries) — these residues exist in the construct but were not modeled.
3. Comparing `length` from `pdb_get_chains` to the expected UniProt length.

**Rule of thumb:** structural completeness >85% (modeled length / expected
length) is good. <70% likely means a domain or large loop is missing and the
entry should not be used for interface analysis.

---

## 5. When to Prefer Cryo-EM over X-ray

Pick cryo-EM when:

- The complex is large (>200 kDa) — typically beyond easy X-ray crystallization.
- Multiple conformational states are biologically meaningful (cryo-EM resolves
  ensembles via 3D classification).
- The target is membrane-bound and X-ray would require detergents that distort
  the interface.
- The best available X-ray entry is >3.0 Å — at that point cryo-EM at ~3.0 Å is
  comparable.

Pick X-ray when:

- You need <2.5 Å for reliable side-chain rotamers (most hotspot work).
- The complex is small (<150 kDa).
- The interface is buried and you need accurate water positions.

If both exist at comparable resolution, prefer the entry that is **holo to your
modality of interest** (e.g. a Fab co-crystal for antibody work).

---

## 6. Practical Checklist for `pdb_search` Results

When `pdb_search` returns multiple candidates, rank them by:

1. **Method** — X-ray first, then cryo-EM, then NMR, then EM single particle.
2. **Resolution** — ascending (lowest number first).
3. **Holo state** — co-crystal with a relevant binder beats apo.
4. **Organism** — matches your intended design species.
5. **Completeness** — full ectodomain / full construct preferred.
6. **Release date** — newer is usually better refined, but a classic
   high-resolution structure beats a recent low-resolution one.

Then run `pdb_fetch_structure` on the top 3–5 to compare side-by-side before
committing to one for design.

---

## 7. Common Pitfalls

- **Combining residue numbering from two different PDB entries** — author
  numbering is entry-specific. Always normalize to UniProt before comparing.
- **Treating cryo-EM "global resolution" as uniform** — local resolution at the
  interface may be worse than the reported global value.
- **Ignoring engineered mutations** — many therapeutic Fab co-crystals carry
  surface engineering (e.g. crystallization-friendly mutations). Check the
  entry title and the `entity.pdbx_mutation` field.
- **Using a fusion construct as your target** — some entries are chimeras
  (e.g. PD-L1 fused to a stabilizing partner). The fusion residues are not
  part of the real target and should be excluded from hotspot lists.
