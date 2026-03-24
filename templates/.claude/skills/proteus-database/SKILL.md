# Skill: proteus-database

Use the Proteus MCP database tools to query PDB, UniProt, and SAbDab for target characterization, antibody scaffold selection, and competition analysis.

---

## 1. PDB Queries (proteus-pdb server)

### pdb_search

Search RCSB by free-text query. Returns `pdb_id`, `title`, `method`, `resolution`, `release_date`.

```
pdb_search(query="PD-L1", max_results=10)
```

- `query`: protein name, organism, keyword. `max_results`: 1-100, default 10.
- **When to use:** Starting a new target — find all available structures.

### pdb_fetch_structure

Retrieve metadata for a single PDB entry. Returns `pdb_id`, `title`, `method`, `resolution`, `release_date`, `polymer_entity_count`, `organism`.

```
pdb_fetch_structure(pdb_id="7S4S")
```

**When to use:** After identifying a candidate PDB ID — assess quality by checking resolution (lower is better for X-ray), method, and organism.

### pdb_get_chains

List all polymer chains with sequences. Returns per chain: `chain_id`, `entity_id`, `molecule_name`, `sequence`, `length`.

```
pdb_get_chains(pdb_id="7S4S")
```

**When to use:** Before interface analysis — you need chain IDs to specify which chains form the binding interface. Also identifies which chain is antigen vs. binder.

### pdb_interface_residues

Find binding interface residues between two chains. Returns `chain1_residues`, `chain2_residues` (each with `resname`, `resseq`), and `contact_count`.

```
pdb_interface_residues(pdb_id="7S4S", chain1="A", chain2="B", distance_cutoff=5.0)
```

- `chain1`, `chain2`: author chain IDs from `pdb_get_chains`.
- `distance_cutoff`: Angstroms, default 5.0. Use 4.0 for strict contacts, 6.0 for extended interface.
- **When to use:** Identifying hotspot residues for proteus-prot or proteus-ab design specs.

### pdb_download

Download a structure file to disk. Returns `path` and `size_bytes`.

```
pdb_download(pdb_id="7S4S", format="cif", output_dir="/tmp")
```

- `format`: `"cif"` (preferred) or `"pdb"`. All three Proteus tools require a local structure file.

### PDB Best Practices

- Prefer X-ray structures with resolution below 2.5 A.
- Use `pdb_get_chains` to verify chain completeness and sequences before design.
- Use mmCIF format — handles large structures and multi-character chain IDs.
- When multiple entries exist, prefer best resolution, most complete chains, and bound state (holo over apo).
- Verify organism matches your intended species.

---

## 2. UniProt Queries (proteus-uniprot server)

### uniprot_search

Search by text, gene name, or organism. Returns `accession`, `name`, `organism`, `gene_name`, `length`, `reviewed`.

```
uniprot_search(query="CD274 human", max_results=10)
```

**When to use:** Finding the canonical UniProt entry for a target. Always search before assuming an accession code.

### uniprot_fetch_protein

Fetch full protein record. Returns `accession`, `name`, `organism`, `gene_name`, `sequence`, `length`, `function_description`, `subcellular_location`.

```
uniprot_fetch_protein(accession="Q9NZQ7")
```

**When to use:** Get full sequence, function, and subcellular location for target biology context.

### uniprot_get_domains

Get domain and region annotations. Returns array of: `type` (Domain, Region, Binding site), `description`, `start`, `end`.

```
uniprot_get_domains(accession="Q9NZQ7")
```

**When to use:** Understanding target architecture — identify extracellular domains for binding, active sites to target or avoid, and domain boundaries for construct design.

### uniprot_get_variants

Get known variants and mutagenesis data. Returns array of: `type` (Natural variant or Mutagenesis), `position`, `original`, `variation`, `description`.

```
uniprot_get_variants(accession="Q9NZQ7")
```

**When to use:** Before finalizing hotspot residues — check if key interface positions have polymorphisms or known functional mutations.

### UniProt Best Practices

- Prefer reviewed entries (Swiss-Prot): the `reviewed` field indicates curated data. Unreviewed (TrEMBL) entries may lack annotations.
- Use gene names for search (e.g. "CD274", "EGFR") — more specific than protein names.
- Cross-reference with PDB to match sequence annotations to 3D positions.
- Check isoforms: some targets have multiple isoforms with different domain compositions.

---

## 3. SAbDab Queries (proteus-sabdab server)

### sabdab_search_antibodies

Search for antibody structures. Returns `pdb_id`, `heavy_chain`, `light_chain`, `antigen_name`, `antigen_chain`, `resolution`, `species`, `method`.

```
sabdab_search_antibodies(query="7S4S")               # by PDB code (fast)
sabdab_search_antibodies(query="PD-L1")              # by antigen keyword (slow, full DB)
sabdab_search_antibodies(species="HOMO SAPIENS")     # by species
```

- `query`: 4-char PDB code for direct lookup, or keyword for antigen name search.
- `antigen`: filter by type (protein, peptide, hapten). `species`: filter by source.
- Keyword searches download full SAbDab (~8MB) and filter client-side.

### sabdab_get_structure

Detailed antibody structure summary. Returns all search fields plus `antigen_type`, `antigen_species`, `r_free`, `r_factor`, `scfv`, `engineered`, `heavy_subclass`, `light_subclass`, `light_ctype`, `date`, `cdr_lengths`.

```
sabdab_get_structure(pdb_id="1ahw")
```

**When to use:** Evaluating a specific antibody as scaffold or template. Subclass and CDR lengths assess proteus-ab compatibility. PDBs with multiple chain pairings return a `chain_pairings` array.

### sabdab_cdr_sequences

Extract CDR sequences (Chothia numbering). Returns per CDR (H1-H3, L1-L3): `sequence` and `length`. Absent CDRs return null.

```
sabdab_cdr_sequences(pdb_id="1ahw")
```

**When to use:** Template selection for proteus-ab. Compare CDRH3 length and composition across candidates — this is the primary specificity determinant.

### sabdab_search_by_antigen

Find all antibodies targeting a specific antigen. Returns `query`, `total_results`, `showing`, `results`.

```
sabdab_search_by_antigen(antigen_name="HER2", max_results=20)
```

**When to use:** Competition analysis — find all known antibody-antigen complexes. Reveals targeted epitopes and successful CDR architectures.

### SAbDab Best Practices and Template Selection

- **CDR length matching**: prefer templates with CDRH3 length within 2 residues of your target.
- **Species preference**: for therapeutics, prefer human/humanized scaffolds.
- **Resolution**: below 2.5 A for reliable CDR conformations.
- **Nanobody scaffolds**: for VHH design, look for `light_chain = ""` (no light chain).
- **Bound state**: ensure `antigen_chain` is populated so CDR conformations reflect binding.

---

## 4. Common Workflows

### Target Characterization

1. `pdb_search(query="<target>")` — find available structures.
2. `pdb_fetch_structure` on top candidates — compare resolution and completeness.
3. `pdb_get_chains` — identify target chain, binder, ligands.
4. `uniprot_search(query="<gene> <organism>")` then `uniprot_fetch_protein` — function and sequence.
5. `uniprot_get_domains` — map domain boundaries onto the PDB structure.
6. `pdb_interface_residues` — identify binding epitope residues.
7. `uniprot_get_variants` — flag polymorphic positions in the interface.
8. `pdb_download(format="cif")` — prepare input for Proteus tools.

### Antibody Scaffold Selection

1. `sabdab_search_by_antigen(antigen_name="<target>")` — find existing antibodies.
2. `sabdab_get_structure` on promising hits — assess resolution, species, subclass.
3. `sabdab_cdr_sequences` on top candidates — compare CDR architectures.
4. Compare CDRH3: 10-15 residues for standard binding, 15-20+ for deep pockets, 8-10 for flat epitopes.
5. Select a high-resolution human scaffold with appropriate CDR lengths.
6. `pdb_fetch_structure` on chosen scaffold — verify structure quality.

### Competition Analysis

1. `sabdab_search_by_antigen` — find all known antibodies against the target.
2. `pdb_search` — find non-antibody binders too.
3. `pdb_interface_residues` on key competitors — map their epitopes.
4. Compare interface residues across binders — identify conserved hotspots vs. novel epitope opportunities.
5. `uniprot_get_variants` — check if escape mutations affect competitor binding sites.

---

## 5. Data Integration

### Cross-Referencing PDB and UniProt

- **PDB residue numbering** (`resseq`) uses author-assigned numbers from the structure file.
- **UniProt positions** use canonical sequence numbering.
- To map between them: align PDB chain sequence (`pdb_get_chains`) against UniProt sequence (`uniprot_fetch_protein`). Account for tags, missing residues, and construct boundaries.
- Shortcut: for well-annotated structures, PDB label_seq_id often matches UniProt numbering. Always verify with sequence comparison.

### Using Domains to Identify Binding Regions

1. `uniprot_get_domains` returns domain start/end positions.
2. Map interface residues from `pdb_interface_residues` onto domain boundaries.
3. This identifies which functional domain the binder targets (e.g. "IgV domain" for PD-L1).
4. Use this to select or avoid specific domains in proteus-prot or proteus-ab design specs.

### Mapping SAbDab CDRs to Design Templates

1. `sabdab_cdr_sequences` for your chosen template — note CDRH3 length especially.
2. CDRH3 is the primary specificity region; proteus-ab redesigns it most aggressively.
3. Framework regions are largely preserved — choose scaffolds with good humanness.
4. For nanobody (VHH) design, verify no light chain in the template.
5. For Fab designs, confirm both H-chain and L-chain CDR sequences are available.

### Identifier Quick Reference

| Database | Identifier | Example | Source |
|----------|-----------|---------|--------|
| PDB | PDB ID (4-char) | 7S4S | `pdb_search` |
| UniProt | Accession | Q9NZQ7 | `uniprot_search` |
| SAbDab | PDB ID | 1ahw | `sabdab_search_antibodies` |
| Chain | Auth chain ID | A, B, H, L | `pdb_get_chains` |
| Residue | resseq (int) | 115 | `pdb_interface_residues` |

### Error Handling

- Empty `pdb_search`: try alternative names or gene symbols.
- "Chain not found" in `pdb_interface_residues`: verify IDs with `pdb_get_chains` first.
- Zero `sabdab_search_by_antigen` results: target may lack antibody co-crystals; fall back to `pdb_search`.
- UniProt `reviewed: false`: may lack annotations; prefer Swiss-Prot entries.
- SAbDab keyword searches are slow (full DB download); use PDB code lookups when possible.
