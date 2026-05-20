---
id: "skill_7b1465f73e1a4c5c9cd7591d123dac91"
name: "by-database"
display-name: "BY Database Queries (PDB / UniProt / SAbDab)"
short-description: "Query the BY MCP database servers (PDB, UniProt, SAbDab) for target characterization, antibody scaffold selection, and competition analysis. Use when you need structural metadata, sequence/domain annotations, or known antibody-antigen complexes for a target."
category: "research"
keywords: "PDB, RCSB, UniProt, SAbDab, antibody database, structure lookup, interface residues, CDR sequences, hotspot, scaffold selection"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: [
  "mcp__by-pdb__pdb_search",
  "mcp__by-pdb__pdb_fetch_structure",
  "mcp__by-pdb__pdb_get_chains",
  "mcp__by-pdb__pdb_interface_residues",
  "mcp__by-pdb__pdb_download",
  "mcp__by-uniprot__uniprot_search",
  "mcp__by-uniprot__uniprot_fetch_protein",
  "mcp__by-uniprot__uniprot_get_domains",
  "mcp__by-uniprot__uniprot_get_variants",
  "mcp__by-sabdab__sabdab_search_antibodies",
  "mcp__by-sabdab__sabdab_get_structure",
  "mcp__by-sabdab__sabdab_cdr_sequences",
  "mcp__by-sabdab__sabdab_search_by_antigen"
]
---

# Skill: by-database

Use the BY MCP database tools to query PDB, UniProt, and SAbDab for target
characterization, antibody scaffold selection, and competition analysis.

---

## When to Use This Skill

Use this skill when you need:

- ✅ Structural metadata for a target (resolution, method, organism, chains)
- ✅ Interface residue lists for hotspot selection in PXDesign / BoltzGen
- ✅ Canonical UniProt sequence, domain boundaries, or known variants
- ✅ Existing antibody-antigen complexes for scaffold selection or competition analysis
- ✅ Cross-referencing PDB residue numbering with UniProt positions
- ✅ Verifying chain composition before generating a design spec

**Don't use this skill for:**

- ❌ Full target research narrative or literature review → use `by-research`
- ❌ Epitope hotspot scoring or surface analysis → use `by-epitope-analysis`
- ❌ Scoring designs (ipSAE, ipTM, liabilities) → use `by-scoring` / `by-screening`
- ❌ Web search or PubMed lookups → fall back to PubMed/bioRxiv tools then WebSearch
- ❌ Submitting compute jobs → use `boltzgen`, `pxdesign`, `protenix` skills

---

## Quick Start

Look up a target end-to-end in three calls:

```text
mcp__by-pdb__pdb_search(query="PD-L1", max_results=10)
mcp__by-uniprot__uniprot_search(query="CD274 human", max_results=5)
mcp__by-sabdab__sabdab_search_by_antigen(antigen_name="PD-L1", max_results=20)
```

For batch enrichment of a known list of PDB IDs without an MCP loop:

```bash
python scripts/batch_pdb_lookup.py --ids 7S4S 6XWG 5JDS --out enriched.csv
```

✅ **VERIFICATION:** Expect `✓ batch_pdb_lookup completed: 3 rows -> enriched.csv`.

---

## Inputs

**Required (at least one of):**

- **PDB ID** — 4-character RCSB identifier (e.g. `7S4S`). Source: `mcp__by-pdb__pdb_search`.
- **UniProt accession** — e.g. `Q9NZQ7`. Source: `mcp__by-uniprot__uniprot_search`.
- **Target name / gene symbol** — e.g. `"PD-L1"`, `"CD274"`. Used as free-text query.
- **Antigen name** — for SAbDab antibody lookups (e.g. `"HER2"`).

**Optional:**

- **Chain IDs** — author chain IDs from `mcp__by-pdb__pdb_get_chains` (e.g. `A`, `H`, `L`).
- **Distance cutoff** — Angstroms for interface analysis (default 5.0; 4.0 strict, 6.0 extended).
- **Species filter** — for SAbDab queries (e.g. `"HOMO SAPIENS"`).
- **Output directory** — for `mcp__by-pdb__pdb_download`.

See [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md) for
resolution and completeness thresholds.

---

## Outputs

All MCP tools return JSON strings. Parse before display — never show raw JSON to the user.

**PDB tool outputs:**

- `pdb_search` → list of `{pdb_id, title, method, resolution, release_date}`.
- `pdb_fetch_structure` → object with `polymer_entity_count`, `organism`, plus the search fields.
- `pdb_get_chains` → list of `{chain_id, entity_id, molecule_name, sequence, length}`.
- `pdb_interface_residues` → `{chain1_residues:[{resname,resseq}], chain2_residues:[...], contact_count}`.
- `pdb_download` → `{path, size_bytes}`. Files are CIF (preferred) or PDB.

**UniProt tool outputs:**

- `uniprot_search` → list of `{accession, name, organism, gene_name, length, reviewed}`.
- `uniprot_fetch_protein` → full record incl. `sequence`, `function_description`, `subcellular_location`.
- `uniprot_get_domains` → list of `{type, description, start, end}`.
- `uniprot_get_variants` → list of `{type, position, original, variation, description}`.

**SAbDab tool outputs:**

- `sabdab_search_antibodies` / `sabdab_search_by_antigen` → list of antibody PDB records.
- `sabdab_get_structure` → detailed record incl. `r_free`, `cdr_lengths`, `chain_pairings`.
- `sabdab_cdr_sequences` → `{H1, H2, H3, L1, L2, L3}` with `{sequence, length}` each.

**Script outputs (this skill's `scripts/`):**

- `batch_pdb_lookup.py` → CSV with one row per PDB ID (resolution, organism, chain count, ligands).
- `find_similar_targets.py` → CSV with related UniProt/PDB entries ranked by % sequence identity.

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST.** Confirm the user actually has identifiers in hand.

1. **Identifiers** (ASK THIS FIRST):
   - Do you have a PDB ID, UniProt accession, gene symbol, or just a target name?
   - If only a target name, we will start with `mcp__by-pdb__pdb_search` and
     `mcp__by-uniprot__uniprot_search` to resolve canonical IDs.

2. **Organism:**
   - Human, mouse, viral, other?
   - Determines which UniProt entry is canonical and which PDB structures are relevant.

3. **Modality intent (drives SAbDab usage):**
   - Antibody (Fab/IgG), nanobody (VHH), or non-antibody binder?
   - Nanobody designs need templates with `light_chain = ""`. Fabs need both H and L.

4. **Resolution threshold:**
   - Default ≤2.5 Å for X-ray. Cryo-EM may go to 3.0–3.5 Å.
   - Lower the bar for novel targets where nothing better exists.

5. **Bound vs apo state:**
   - For interface analysis you need holo (bound) structures.
   - Apo structures are fine for general topology but miss the binding interface.

6. **Downstream tool:**
   - PXDesign (de novo binder), BoltzGen (antibody/nanobody), or Protenix (refold only)?
   - This affects which fields you must extract (e.g. hotspot range notation vs. CDR lengths).

7. **Cross-reference need:**
   - Do you need PDB→UniProt numbering reconciliation?
   - Required when reporting hotspot positions across data sources.

---

## Standard Workflow

🚨 **MANDATORY: USE MCP TOOLS AS THE PRIMARY DATA PATH** 🚨

Do not WebSearch for data that exists in PDB, UniProt, or SAbDab. Batch your MCP
calls and present one consolidated summary — never expose raw JSON.

### Target Characterization (PDB-first)

1. `mcp__by-pdb__pdb_search(query="<target>")` — find available structures.
2. `mcp__by-pdb__pdb_fetch_structure(pdb_id="<top>")` — compare resolution + method.
3. `mcp__by-pdb__pdb_get_chains(pdb_id="<top>")` — identify target chain vs. binder vs. ligands.
4. `mcp__by-uniprot__uniprot_search(query="<gene> <organism>")` then
   `mcp__by-uniprot__uniprot_fetch_protein` — sequence, function, location.
5. `mcp__by-uniprot__uniprot_get_domains(accession=...)` — domain boundaries.
6. `mcp__by-pdb__pdb_interface_residues(pdb_id=..., chain1=..., chain2=...)` — epitope residues.
7. `mcp__by-uniprot__uniprot_get_variants(accession=...)` — flag polymorphic hotspots.
8. `mcp__by-pdb__pdb_download(pdb_id=..., format="cif")` — local file for BY design tools.

### Antibody Scaffold Selection (SAbDab-first)

1. `mcp__by-sabdab__sabdab_search_by_antigen(antigen_name="<target>")` — known antibodies.
2. `mcp__by-sabdab__sabdab_get_structure(pdb_id="<top>")` — resolution, species, subclass, CDR lengths.
3. `mcp__by-sabdab__sabdab_cdr_sequences(pdb_id="<top>")` — CDR architectures.
4. Match CDRH3 length to target depth (10–15 standard, 15–20+ deep pockets, 8–10 flat).
5. Pick a high-resolution human (or humanized) scaffold.
6. `mcp__by-pdb__pdb_fetch_structure(pdb_id="<scaffold>")` — final quality check.

### Competition Analysis

1. `mcp__by-sabdab__sabdab_search_by_antigen` — all known antibodies.
2. `mcp__by-pdb__pdb_search` — non-antibody binders too.
3. `mcp__by-pdb__pdb_interface_residues` on each competitor — map epitopes.
4. Compare interface residues across binders → conserved hotspots vs. novel epitope opportunities.
5. `mcp__by-uniprot__uniprot_get_variants` — does any escape mutation hit competitor sites?

### Batch Lookups (use scripts)

For >5 PDB IDs or >5 UniProt accessions, prefer the scripts in this skill — they
deduplicate, retry on transient errors, and emit a single CSV instead of N JSON blobs:

```bash
python scripts/batch_pdb_lookup.py --ids 7S4S 6XWG 5JDS 4HHB --out targets.csv
python scripts/find_similar_targets.py --uniprot P01375 --max-hits 25 --out homologs.csv
```

✅ **VERIFICATION:** Each script prints `✓ <name> completed: N rows -> <path>`.

---

## When Scripts Fail

Hierarchy (apply in order):

1. **Fix and retry (90%)** — Install missing dep (`pip install httpx biopython`),
   then re-run with the same args.
2. **Modify script (5%)** — Edit the local script file (e.g. tighten resolution
   filter, change e-value threshold for BLAST).
3. **Use as reference (4%)** — Read the script and call the MCP tools manually
   for one-off cases.
4. **Write from scratch (1%)** — Only if the underlying RCSB / UniProt / SAbDab
   API has changed in a way that breaks the script. Document why.

Decision tree:
- HTTP 429 / rate limit → step 1 (the script retries with backoff; re-run).
- Missing `httpx` / `biopython` → step 1 (`pip install`).
- Wrong output columns → step 2 (modify script).
- Tool unavailable in environment → step 3 (MCP fallback).
- API schema changed upstream → step 4 (rewrite + report).

---

## Decision Points

### When to prefer X-ray vs. cryo-EM

See [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md). Short
form: X-ray ≤2.5 Å for interface work; cryo-EM acceptable to ~3.0 Å for large
complexes where X-ray is impossible.

### Holo vs. apo selection

For interface residues you MUST use a holo (bound) structure. Apo can confirm
domain architecture but contact residues will be missing or rearranged.

### Reviewed vs. unreviewed UniProt

Always prefer reviewed (Swiss-Prot). Unreviewed (TrEMBL) entries may lack
domain, variant, and function annotations. See
[references/uniprot-fields.md](references/uniprot-fields.md).

### Antigen-deposited vs. validated SAbDab entries

SAbDab indexes the PDB; presence in SAbDab does NOT mean affinity has been
independently validated. See [references/sabdab-best-practices.md](references/sabdab-best-practices.md).

---

## Common Issues

| Issue | Possible Cause | Solution | Details |
|-------|----------------|----------|---------|
| `pdb_search` returns empty list | Target name doesn't match any title or keyword | Try gene symbol, organism, or UniProt accession via `uniprot_search` first | [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md) |
| `pdb_interface_residues` errors `Chain not found` | Wrong chain ID (case, label vs. auth) | Run `pdb_get_chains` first; use the exact `chain_id` field returned | [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md) |
| Interface residue count is zero | `distance_cutoff` too strict, or apo structure | Increase cutoff to 6.0 Å; switch to a holo PDB ID | [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md) |
| Resolution shows `null` | Cryo-EM entry without combined resolution, or NMR | Check `method`; for NMR resolution is not defined; report ensemble size instead | [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md) |
| `uniprot_fetch_protein` returns sparse fields | Unreviewed (TrEMBL) entry | Search with `reviewed:true` or pick the canonical Swiss-Prot accession | [references/uniprot-fields.md](references/uniprot-fields.md) |
| Wrong isoform sequence | Default canonical does not match construct | Inspect isoforms; choose the one matching your PDB chain length | [references/uniprot-fields.md](references/uniprot-fields.md) |
| PDB resseq does not match UniProt position | Construct tags, truncations, or signal peptide cleavage | Align PDB chain sequence to UniProt; offset = first matched residue | [references/uniprot-fields.md](references/uniprot-fields.md) |
| SAbDab keyword search is slow | Tool downloads full DB (~8 MB) then filters | Use PDB-code lookups when possible; cache results between calls | [references/sabdab-best-practices.md](references/sabdab-best-practices.md) |
| `sabdab_search_by_antigen` returns zero hits | No deposited antibody co-crystals | Fall back to `pdb_search` for non-antibody binders; consider homolog targets | [references/sabdab-best-practices.md](references/sabdab-best-practices.md) |
| CDRH3 length mismatch with target depth | Picked the wrong scaffold | Match CDRH3 within ±2 residues (10–15 standard, 15–20 deep pockets, 8–10 flat) | [references/sabdab-best-practices.md](references/sabdab-best-practices.md) |
| `batch_pdb_lookup.py` reports `httpx` missing | Dependency not installed | `pip install httpx` and re-run | See script header |
| `find_similar_targets.py` BLAST returns 503 | UniProt REST BLAST is rate-limited | Re-run after 30 s; script applies exponential backoff automatically | See script header |
| Antibody scaffold has light_chain but you want VHH | Picked a Fab template by mistake | Filter SAbDab results where `light_chain == ""` | [references/sabdab-best-practices.md](references/sabdab-best-practices.md) |
| Engineered / chimeric SAbDab record | Scaffold is not natively the listed species | Check `engineered` field; prefer fully natural human / camelid scaffolds for therapeutics | [references/sabdab-best-practices.md](references/sabdab-best-practices.md) |

---

## Best Practices

1. 🚨 **CRITICAL:** Always resolve identifiers via search before assuming an accession or PDB ID exists.
2. ✅ Prefer reviewed (Swiss-Prot) UniProt entries.
3. ✅ Prefer X-ray ≤2.5 Å, holo (bound) structures for interface analysis.
4. ✅ Always run `pdb_get_chains` before `pdb_interface_residues` so chain IDs are exact.
5. ✅ Cross-reference PDB residue numbers (`resseq`) with UniProt positions by sequence alignment.
6. ✅ Match CDRH3 length to target topology; do not blindly default to a popular scaffold.
7. ✅ Use mmCIF (`format="cif"`) — handles large structures and multi-character chain IDs.
8. ❌ DON'T expose raw MCP JSON to the user; summarize into tables.
9. ❌ DON'T WebSearch when an MCP database tool can answer the question.
10. ✨ Batch >5 identifier lookups through `scripts/batch_pdb_lookup.py` instead of looped MCP calls.

---

## Suggested Next Steps

After running this skill, hand off to one of:

- **`by-research`** — when you need a synthesized target dossier with literature
  triangulation, critique, and design recommendation. This skill is the data
  layer underneath `by-research` Phase 3.
- **`by-epitope-analysis`** — once you have interface residues, score epitope
  drugability and select hotspots for design.
- **`by-scoring`** / **`by-screening`** — when you already have designs and
  need to evaluate ipSAE, ipTM, and liabilities.
- **`boltzgen`** — once a target chain, hotspot range, and scaffold candidates
  are confirmed, hand off CDR templates and the holo PDB to BoltzGen.
- **`pxdesign`** — for non-antibody binders, hand off the holo CIF and hotspot
  range notation to PXDesign.

Why this chaining works: database lookups are the deterministic, citation-grade
input layer. Downstream skills assume the data is already canonical (correct
accession, correct chain IDs, correct residue numbering). Skipping this skill is
the single biggest cause of failed campaigns.

---

## Related Skills

**Upstream:**
- `by-session` — environment + config check before any database work.

**Downstream:**
- `by-research` — full research dossier with literature.
- `by-epitope-analysis` — hotspot scoring from interface residues.
- `boltzgen`, `pxdesign`, `protenix` — design and refold using the PDB/CIF you fetched.

**Alternative / Complementary:**
- `by-knowledge` — query the project knowledge graph for prior campaigns on the same target.

---

## References

**Detailed documentation:**

- [references/pdb-quality-metrics.md](references/pdb-quality-metrics.md) —
  Resolution thresholds, holo vs. apo, organism filtering, missing residues,
  structural completeness; X-ray vs. cryo-EM selection.
- [references/uniprot-fields.md](references/uniprot-fields.md) — Important
  UniProt fields for design (sequence, domains, PTMs, isoforms, species) and
  efficient query patterns.
- [references/sabdab-best-practices.md](references/sabdab-best-practices.md) —
  Antibody database queries (by target, germline, affinity) and the
  deposited-vs-validated caveat.

**Scripts:**

- [scripts/batch_pdb_lookup.py](scripts/batch_pdb_lookup.py) — CLI that reads
  a list of PDB IDs and writes an enriched CSV (resolution, method, organism,
  chain count, ligands).
- [scripts/find_similar_targets.py](scripts/find_similar_targets.py) — CLI that
  takes a UniProt accession or PDB ID and returns a ranked list of related
  entries by sequence identity.

**Official documentation:**

- RCSB Data API — https://data.rcsb.org/
- RCSB Search API — https://search.rcsb.org/
- UniProt REST — https://www.uniprot.org/help/api
- SAbDab — https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab

**Identifier quick reference:**

| Database | Identifier | Example | Source |
|----------|-----------|---------|--------|
| PDB | 4-char ID | 7S4S | `mcp__by-pdb__pdb_search` |
| UniProt | Accession | Q9NZQ7 | `mcp__by-uniprot__uniprot_search` |
| SAbDab | PDB ID | 1ahw | `mcp__by-sabdab__sabdab_search_antibodies` |
| Chain | Auth chain ID | A, B, H, L | `mcp__by-pdb__pdb_get_chains` |
| Residue | resseq (int) | 115 | `mcp__by-pdb__pdb_interface_residues` |
