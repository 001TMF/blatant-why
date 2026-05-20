# SAbDab Best Practices — Reference

Practical guidance for querying SAbDab (Structural Antibody Database) for
scaffold selection, competition analysis, and template ranking. Pairs with
`mcp__by-sabdab__sabdab_search_antibodies`,
`mcp__by-sabdab__sabdab_get_structure`,
`mcp__by-sabdab__sabdab_cdr_sequences`, and
`mcp__by-sabdab__sabdab_search_by_antigen`.

---

## 1. What SAbDab Is (and Isn't)

SAbDab is a structural index over the PDB filtered to entries that contain at
least one antibody chain. It:

- **Provides:** PDB ID, H-chain, L-chain, antigen chain + name + type, species,
  CDR lengths, resolution, R-free, subclass, light-chain type, engineered
  status, deposit date.
- **Does NOT provide:** binding affinity (Kd, IC50), assay data, cell-based
  activity, in vivo efficacy.

**Critical caveat:** presence in SAbDab means the antibody has a deposited
structure — it does NOT mean the affinity in literature has been independently
validated, or that the depositor's claimed epitope is correct.

---

## 2. Search Strategies

### By PDB code (fastest)

```text
sabdab_search_antibodies(query="1ahw")
```

Direct lookup, no DB scan. Use when you already have the PDB ID.

### By antigen keyword (slower)

```text
sabdab_search_antibodies(query="PD-L1")
sabdab_search_by_antigen(antigen_name="HER2", max_results=20)
```

Both download the full SAbDab summary file (~8 MB) and filter client-side.
Slower but the only way to find new candidates. Cache results when possible.

### By species

```text
sabdab_search_antibodies(species="HOMO SAPIENS")
sabdab_search_antibodies(species="LAMA GLAMA")   # for nanobodies
```

Useful for filtering scaffold candidates by therapeutic suitability.

### Combined filters

The MCP layer supports `antigen`, `species`, and `query` simultaneously. Use
this to narrow to "all human Fabs against HER2" in a single call.

---

## 3. By Target — Competition Analysis

To enumerate all known antibodies against a target:

1. `sabdab_search_by_antigen(antigen_name="<target>", max_results=50)`.
2. For each hit, `sabdab_get_structure(pdb_id=...)` — capture resolution,
   species, subclass, engineering status.
3. For each top candidate, `sabdab_cdr_sequences(pdb_id=...)` — capture CDRH3.
4. For each top candidate, `mcp__by-pdb__pdb_interface_residues(...)` — capture
   epitope footprint.

Output a table comparing epitopes. Conserved hotspots across multiple
antibodies = high-confidence binding site. Sparse epitopes (1 antibody only) =
either novel opportunity or unvalidated.

---

## 4. By Germline / Subclass

The `heavy_subclass` and `light_subclass` fields encode the chain class. Useful
for filtering:

- **`IGHG1`, `IGHG4`** — common therapeutic IgG subclasses.
- **`IGHM`** — primary response; rarely used as scaffold.
- **`IGHE`** — IgE; specialized use only.

For nanobodies (VHH), look for entries with `light_chain = ""` (empty string)
and species `LAMA GLAMA` or `CAMELUS DROMEDARIUS`.

The germline V/D/J gene is NOT directly indexed in the SAbDab summary; obtain
it by running CDR sequences through an external germline assigner if needed.

---

## 5. By Binding Affinity (Indirect)

SAbDab does not store affinity. To get affinity for a SAbDab entry:

1. Fetch the PDB entry's primary citation (PMID) via the PDB data API.
2. Search PubMed for the paper and extract affinity from the abstract or
   methods. (Outside the scope of this skill — use the literature MCP fallback.)
3. **Never invent affinity values.** If unknown, mark as "not reported".

Therapeutic antibodies in development typically have Kd in the 0.1–10 nM range;
research-grade antibodies often have Kd in the 10–100 nM range. Use these as
priors when the exact value is unavailable.

---

## 6. Template Selection for BoltzGen

Selecting a scaffold for BoltzGen redesign:

| Criterion | Recommendation |
|-----------|---------------|
| Resolution | ≤2.5 Å (≤3.0 Å acceptable if no better template exists) |
| Species (therapeutic) | Human or fully humanized; camelid for VHH |
| Subclass | IgG1 or IgG4 for Fab; not relevant for VHH |
| `engineered` flag | Prefer `false`; if `true`, verify mutations don't affect framework |
| CDR lengths | Match target topology (see below) |
| `antigen_chain` | Must be populated (holo) |

### CDRH3 length matching

CDRH3 is the dominant specificity determinant. Match within ±2 residues:

| Target topology | CDRH3 length |
|-----------------|--------------|
| Flat surface (cytokines, MHC) | 8–10 |
| Standard groove | 10–15 |
| Deep pocket / cleft | 15–20+ |

For nanobody (VHH) design, CDRH3 is often longer than in conventional
antibodies — match accordingly.

### Other CDRs

- **CDRH1, CDRH2** — framework-driven, less variable. Slight length mismatches
  are tolerated by BoltzGen.
- **CDRL1, CDRL2, CDRL3** — important for Fab specificity but BoltzGen
  redesigns them. Exact length match is preferred but not critical.

---

## 7. Deposited vs. Validated — The Single Biggest Trap

Many SAbDab entries come from structural studies that solved the antibody
crystal but never validated the antibody in a biological assay. Signals that
an entry may not be "validated":

- **No primary citation in a peer-reviewed paper** (deposit-only PDB entry).
- **Engineered or chimeric** — `engineered = true` may indicate a designed
  variant, not a natural antibody.
- **`scfv = true`** — single-chain Fv constructs are often experimental
  reagents, not therapeutic antibodies.
- **Older entries (pre-2000)** — affinity assay methods differed and many
  numbers are not comparable to modern SPR / BLI measurements.

**Mitigation:** when picking a scaffold for therapeutic design, prefer entries
with a published characterization paper (find via PubMed by PDB ID), an IgG1
or IgG4 subclass, `scfv = false`, and `engineered = false` (or carefully
documented engineering).

---

## 8. Multi-Chain Pairings

Some PDB entries contain multiple antibody-antigen pairings in the asymmetric
unit. `sabdab_get_structure` returns these as a `chain_pairings` array. Each
pairing is independent — they may have different antigens or different
CDR conformations.

Decide which pairing to use by:

1. Resolution (same across the entry, but local resolution may differ).
2. Completeness of the antigen chain (longest is usually most informative).
3. Crystal contacts — pairings on the surface of the asymmetric unit may have
   artifactual contacts from neighboring molecules.

---

## 9. Cross-Linking with PDB and UniProt

After selecting a SAbDab entry:

- `mcp__by-pdb__pdb_fetch_structure(pdb_id=<sabdab_pdb>)` — confirm method,
  release date, polymer entity count.
- `mcp__by-pdb__pdb_get_chains(pdb_id=<sabdab_pdb>)` — confirm H, L, and
  antigen chain IDs and sequences match what SAbDab reports.
- `mcp__by-uniprot__uniprot_search(query="<antigen_name>")` — link the antigen
  chain to a canonical UniProt entry for numbering reconciliation.

---

## 10. Common Pitfalls

- **Picking the highest-resolution entry without checking the species.** A
  1.5 Å mouse Fab is a bad therapeutic scaffold.
- **Confusing antigen chain with antibody chain.** Always check
  `antigen_chain` — it is the target chain, not the binder.
- **Forgetting that nanobody entries have empty `light_chain`.** Filter on
  this explicitly when picking VHH templates.
- **Trusting `cdr_lengths` blindly.** They are Chothia-numbered. Other numbering
  schemes (Kabat, IMGT) give different lengths for the same CDR.
- **Treating SAbDab keyword search as instant.** It downloads the full DB; cache
  results across calls in the same session.
- **Assuming SAbDab is exhaustive.** Patents and unpublished structures are not
  indexed. Cross-check with `mcp__by-pdb__pdb_search` to catch antibody
  structures that may not have been classified as such in SAbDab yet.
