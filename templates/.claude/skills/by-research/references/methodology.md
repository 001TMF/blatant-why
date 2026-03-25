# Research Methodology

## Database Priority Order

Search databases in this order. Earlier databases provide more reliable data for
protein design decisions, so prioritize them when time is limited.

1. **PDB** — structural data (most reliable for binding interfaces and epitope mapping)
2. **UniProt** — protein function, domains, variants, isoforms, subcellular location
3. **SAbDab** — existing antibody structures and sequences (critical for scaffold selection)
4. **PubMed** — peer-reviewed literature (experimental binding data, clinical results)
5. **bioRxiv** — recent preprints (cutting-edge methods, may not be peer-reviewed)

For Quick depth, search 1-3 only. For Standard, search all five. For Deep, search
all five plus run homolog analysis via `mcp__by-research__research_find_similar_targets`.

---

## Query Construction

### Target info query (research_get_target_info)

Pass the most specific identifier available:
- UniProt accession (best): `"P01375"`
- Gene name: `"TNFSF2"`
- Protein name: `"TNF-alpha"` (may match multiple species)

The tool searches both UniProt and PDB in one call.

### Prior art query (research_search_prior_art)

The tool constructs: `"{target_name}" AND (antibody OR nanobody OR binder) AND (design OR engineering)`

For broader results, try:
- Target name only: `"TNF-alpha"` — catches general biology papers
- Target + specific modality: `"TNF-alpha nanobody"` — narrows to relevant scaffolds
- Target + epitope: `"TNF-alpha epitope binding site"` — focuses on structural biology

### Known binders query (research_analyze_known_binders)

Use the canonical antigen name as it appears in SAbDab:
- `"tumor necrosis factor"` rather than `"TNF-alpha"` (SAbDab uses full names)
- Try both common name and full name if initial search returns few results
- The tool searches SAbDab's antigen_name field via substring match

### Similar targets (research_find_similar_targets)

Requires a UniProt accession. Get this from `mcp__by-research__research_get_target_info` first.
Returns sequence homologs that may have known binders even if the primary target does not.

---

## Cross-Validation Rules

Cross-validation is the core of Phase 4 (TRIANGULATE). These rules determine whether
findings from different sources agree or conflict.

### Epitope residues

A residue is considered a validated hotspot if it appears in 2+ independent sources:
- PDB interface analysis + literature claim = validated
- Two independent PDB structures showing the same contact = strongly validated
- Literature claim only = unvalidated (note as "reported but not structurally confirmed")

### Binding affinity

Affinity claims require experimental data from recognized methods:
- **Acceptable**: SPR (Biacore), BLI (Octet), ITC, ELISA (with dose-response)
- **Weak**: Single-point ELISA, pull-down (qualitative only)
- **Not acceptable**: Computational docking scores, molecular dynamics estimates

When two papers report different affinities for the same binder:
- Check assay conditions (temperature, buffer, antigen construct)
- Prefer SPR/BLI over ELISA
- Report the range rather than picking one value

### Structure quality

For interface analysis, prioritize structures by:

1. Resolution < 3.0A (side-chain positions reliable)
2. Bound state (holo) over unbound (apo) — binding may induce conformational changes
3. Complete chains over truncated constructs
4. Biological assembly over asymmetric unit
5. Recent deposition over older structures (better refinement tools)

Computational predictions (AlphaFold, homology models) are acceptable for:
- Domain boundary identification
- Overall fold verification
- Loop region estimation (with explicit LOW confidence)

Computational predictions are NOT acceptable as sole evidence for:
- Specific interface residue contacts
- Side-chain rotamer states at the binding interface
- Binding affinity predictions

---

## Anti-Hallucination Rules

These rules prevent the research agent from generating plausible but fabricated data.
Violations undermine the entire research pipeline because downstream design decisions
depend on the accuracy of the research report.

### Identifiers

- NEVER fabricate PDB IDs — every PDB ID cited must come from a tool response
- NEVER fabricate UniProt accessions — must come from `mcp__by-research__research_get_target_info` or `mcp__by-uniprot__uniprot_search`
- NEVER fabricate PMIDs or DOIs — must come from `mcp__by-research__research_search_prior_art`
- NEVER fabricate SAbDab entries — must come from `mcp__by-research__research_analyze_known_binders`

### Quantitative data

- NEVER invent binding affinity values (Kd, IC50, EC50, kon, koff)
- NEVER invent resolution values for PDB structures
- NEVER invent hit rates or success percentages for specific targets
- Use ranges from the campaign-manager skill baselines when estimating expected hit rates

### Claims and assertions

- Every claim in `research.md` must trace to a `src_XXX` entry in `sources.json`
- If a search returns no results, report "no data found" — do not fill the gap with guesses
- Distinguish clearly between "experimental" and "predicted" findings
- When uncertain, use hedging language: "suggests", "may indicate", "based on limited data"

### Common traps

- Do not confuse species orthologs (human TNF-alpha vs mouse TNF-alpha have different epitopes)
- Do not assume binding site conservation between family members without evidence
- Do not extrapolate affinity data from one antibody format to another (IgG Kd differs from scFv Kd)
- Do not conflate "therapeutic target" with "structurally tractable for binder design"

---

## Source Deduplication

Multiple tools may return overlapping information. Before adding to sources.json:

1. Check if the PDB ID or PMID already exists in sources.json
2. If yes, merge new findings into the existing entry (update key_findings array)
3. If a preprint has been published as a peer-reviewed paper, keep only the published version
   and upgrade its credibility score
4. Count unique sources (not total tool responses) when checking quality gate thresholds

---

## Time Management

Research should not block design indefinitely. Target times by depth:

| Depth | Target | Hard Limit | Action at Limit |
|-------|--------|------------|----------------|
| Quick | 5 min | 10 min | Package what you have |
| Standard | 15 min | 25 min | Skip Phase 7, package |
| Deep | 30 min | 45 min | One iteration max, package |

If approaching the hard limit, skip Phases 6-7 (CRITIQUE/REFINE) and go directly to
Phase 8 (PACKAGE). Note in the report that critique/refinement was skipped due to
time constraints and flag the report as "preliminary."
