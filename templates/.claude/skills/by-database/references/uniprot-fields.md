# UniProt Fields for Design — Reference

Field-by-field guide to UniProt records and how to query them efficiently for
BY design work. Pairs with `mcp__by-uniprot__uniprot_search`,
`mcp__by-uniprot__uniprot_fetch_protein`,
`mcp__by-uniprot__uniprot_get_domains`, and
`mcp__by-uniprot__uniprot_get_variants`.

---

## 1. Accession vs. Entry Name

| Field | Format | Example | Use for |
|-------|--------|---------|---------|
| `accession` | 6 or 10 alphanumeric, stable | `Q9NZQ7` | Programmatic lookups, canonical IDs |
| `entry_name` | UPPERCASE_SPECIES, can change | `PDL1_HUMAN` | Human-readable display only |
| `gene_name` | Gene symbol | `CD274` | Free-text search; concise identifier |

Always store the **accession** in campaign artifacts. Display entry name or
gene name in tables for readability.

---

## 2. Reviewed (Swiss-Prot) vs. Unreviewed (TrEMBL)

The `reviewed` field is the single most important quality signal:

- **`reviewed: true`** — Swiss-Prot. Manually curated. Domain, variant, PTM,
  isoform, and function annotations are reliable.
- **`reviewed: false`** — TrEMBL. Auto-annotated from genome sequencing.
  Sequence is usually correct, but functional annotations may be wrong or
  absent.

**Always prefer reviewed entries.** For well-studied human proteins, the
reviewed entry is the canonical one. Only use TrEMBL when:

- No reviewed entry exists for the species (common for non-model organisms).
- You explicitly need a particular strain / isolate sequence.

Filter by adding `reviewed:true` to the query string if needed.

---

## 3. Sequence Fields

The full sequence comes from `uniprot_fetch_protein` in the `sequence` field.
Key properties:

- **Single-letter amino acid codes**, no spaces or numbering.
- **Position 1 = first residue** (Met for cytoplasmic proteins, or the first
  residue after signal peptide cleavage for secreted proteins — but UniProt
  numbers from the precursor Met regardless).
- **Length** in the `length` field is canonical residue count.

**Critical for design:** signal peptides and propeptides are included in
the UniProt sequence but are cleaved off in the mature protein. The PDB
structure usually shows only the mature form. Account for this offset when
mapping PDB `resseq` to UniProt position.

---

## 4. Domains and Regions

`uniprot_get_domains` returns annotations with `type`, `description`, `start`,
`end`. Important `type` values:

| Type | What it represents | Use for |
|------|-------------------|---------|
| `Domain` | Structural / evolutionary unit | Construct boundaries; modular design |
| `Region` | Functional region (low complexity, intrinsically disordered, etc.) | Filter hotspots; flag flexible regions |
| `Binding site` | Specific cofactor / substrate residue | Hotspots to target or avoid |
| `Active site` | Catalytic residue | Often must be avoided in non-inhibitor designs |
| `Motif` | Short functional motif (NLS, glycosylation, etc.) | PTM awareness |
| `Signal` / `Propeptide` / `Transit` | Cleaved during maturation | Subtract from PDB numbering offset |
| `Topological domain` | Extracellular / cytoplasmic / TM | Extracellular = targetable; TM = avoid |

**Recipe for extracellular targeting:** filter domains where
`type == "Topological domain"` and `description == "Extracellular"`. Hotspots
must fall within these ranges for accessible binders.

---

## 5. Post-Translational Modifications (PTMs)

PTM annotations appear under `Modified residue`, `Glycosylation`,
`Disulfide bond`, and `Lipidation` types in domain queries (or via the variants
endpoint for some servers).

| PTM | Field marker | Design impact |
|-----|--------------|---------------|
| N-linked glycosylation | `Glycosylation` with description `N-linked` | Glycan may shield epitope; avoid nearby hotspots unless BoltzGen models glycans |
| O-linked glycosylation | `Glycosylation` with description `O-linked` | Similar shielding; mostly on Ser/Thr |
| Phosphorylation | `Modified residue` with `Phospho-` | Conformational impact; consider phospho-state of target |
| Disulfide bond | `Disulfide bond` | Must be preserved in expressed construct; do not mutate Cys |
| Palmitoylation / Myristoylation | `Lipidation` | Membrane anchoring; not a design surface |

**Glycan rule of thumb:** if a hotspot falls within 8 Å of an N-linked
glycosylation site, expect the glycan to interfere with binding. Choose
alternative hotspots, or confirm the glycan is removed in your expression
construct.

---

## 6. Isoforms

Many targets have multiple isoforms differing in:

- Alternative splice variants (different exons included).
- Alternative initiation (different Met start sites).
- Alternative C-termini (different last exons).

`uniprot_fetch_protein` returns the **canonical** sequence by default. To
choose a non-canonical isoform:

1. Check the PDB chain sequence length against the canonical length.
2. If they differ, fetch the isoform list (`Isoform 2`, `Isoform 3`, etc.) and
   match to the PDB sequence.
3. Use the isoform sequence for all downstream design work.

**Common gotcha:** a structure of "isoform 2" may have different residue
numbering than canonical. UniProt provides a mapping per isoform.

---

## 7. Variants and Mutagenesis

`uniprot_get_variants` returns two `type` values:

- **`Natural variant`** — population polymorphisms (often dbSNP-sourced).
  Important for therapeutic targeting: a variant at a hotspot may render the
  binder ineffective in some patients.
- **`Mutagenesis`** — published mutational studies. These are gold for hotspot
  validation: if a mutation at residue X knocks out binding to a known
  partner, X is functionally important.

For each variant: `position`, `original` (wildtype AA), `variation` (mutant AA),
`description` (PMID + effect, when available).

**Workflow tip:** before finalizing hotspots from `pdb_interface_residues`,
cross-check each position against `uniprot_get_variants`. Hotspots with
mutagenesis confirmation are HIGH-confidence; hotspots without are MEDIUM.

---

## 8. Species and Cross-Species Mapping

The `organism` field gives the scientific name. For cross-species work:

1. Fetch the canonical entry for species A.
2. Run `find_similar_targets.py` (this skill's script) to find orthologs in
   species B, C, D…
3. Compare sequence identity per residue at hotspot positions. >90% identity
   = likely cross-reactive; <70% = species-specific design needed.

---

## 9. Efficient Query Patterns

| Goal | Query pattern |
|------|---------------|
| Canonical human entry | `uniprot_search(query="<gene> human reviewed")` |
| All reviewed orthologs | `uniprot_search(query="<gene> reviewed")`, then filter by organism |
| Search by protein name | `uniprot_search(query="programmed cell death 1 ligand 1 human")` |
| Filter to membrane proteins | Add `keyword:membrane` to query |
| Filter by length range | UniProt REST `length:[300 TO 500]` (some servers expose this) |

Always start with the gene symbol — it is more specific than the protein name
and matches the official HGNC / MGI nomenclature.

---

## 10. Common Pitfalls

- **Assuming PDB position = UniProt position.** Almost never true for secreted
  proteins (signal peptide cleavage shifts the offset).
- **Using TrEMBL annotations as authoritative.** Domain boundaries are often
  predicted, not curated.
- **Ignoring isoforms.** A 290-residue PDB chain on a target with a 350-residue
  canonical isoform is almost certainly isoform 2 or a truncated construct.
- **Trusting variant descriptions without PMIDs.** The strongest mutagenesis
  data has explicit citations; orphan annotations may be auto-imported and
  unvalidated.
