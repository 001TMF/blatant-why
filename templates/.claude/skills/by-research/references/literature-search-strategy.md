# Literature Search Strategy

This reference covers **which database to hit first** based on the target's organism
and protein class, **how to construct queries** that maximize yield without
sacrificing precision, and **how to tier confidence** in the resulting findings.

Use this in Phase 2 (PLAN) to pick the right priority order and in Phase 3
(RETRIEVE) to construct each query.

---

## Database-First Decision Matrix

The right database to hit first depends on what you most need to know about the
target. Pick the highest-priority row that applies.

| Target situation | Hit first | Then | Rationale |
|------------------|-----------|------|-----------|
| Clinical-stage human therapeutic target (TNF-alpha, PD-L1, HER2, IL-6) | **PubMed** | SAbDab → PDB → UniProt | Mature literature trail; therapeutic context drives modality/scaffold choice |
| Solved structure exists (PDB ID known) | **PDB** | UniProt → SAbDab → PubMed | Structure is the ground truth for epitope; literature contextualizes |
| Novel target or low-PDB-coverage protein | **bioRxiv** + **PubMed** | UniProt → AlphaFold DB → homolog search | Recent preprints catch novel structural biology; experimental data still sparse |
| Non-human organism (viral, bacterial, plant) | **UniProt** | PubMed (with organism filter) → PDB → cross-species homologs | UniProt taxonomy disambiguates orthologs first |
| Antibody scaffold selection (modality already chosen) | **SAbDab** | PubMed (with "nanobody" / "scFv" modifier) → PDB | SAbDab is the canonical antibody structure database |
| Pure prior-art / IP scan | **PubMed (patent filter)** | bioRxiv → company press releases | Patent literature is in PubMed via NLM patent abstracts |
| Computational prediction needed (no structure) | **AlphaFold DB** (via UniProt accession) | PubMed → homolog search | Always flag as predicted; do not use as sole interface evidence |
| Membrane protein / GPCR | **PDB** (filter by membrane class) + **UniProt** (topology) | PubMed → SAbDab | Topology matters for accessible epitopes |
| Glycoprotein with known glycosylation | **UniProt** (PTM annotations) | PDB → PubMed | Glycan positions affect epitope choice and BoltzGen feasibility |

---

## Query Patterns by Protein Class

### Cytokines / Soluble Signaling Proteins

Common patterns: TNF family, interleukins, interferons, growth factors.

- **PubMed primary**: `"{target}" AND ("crystal structure" OR "co-crystal") AND ("antibody" OR "nanobody" OR "binder")`
- **PubMed broaden**: drop the antibody clause; add `"epitope mapping"` or `"alanine scanning"`
- **SAbDab**: query by long-form name (`"tumor necrosis factor"`, not `"TNF-alpha"`)
- **PDB**: filter by molecule class "cytokine" and chain count = 1 for monomer / 3 for homotrimers (TNF family)

### Receptors (Cell Surface, GPCR, RTK)

- **UniProt first**: confirm topology (extracellular vs intracellular domain) before designing binders
- **PubMed**: `"{target}" AND ("ectodomain" OR "extracellular domain") AND "binding"`
- **PDB**: filter for entries containing both the receptor and a partner (avoid apo structures)
- **SAbDab**: search by both receptor name and any approved drug name (e.g., `"PD-1"` and `"pembrolizumab"`)

### Viral Glycoproteins (Spike, HA, Env)

- **PDB first**: viral glycoproteins have rapid structural turnover; PDB has the freshest data
- **PubMed**: `"{virus} {protein}" AND ("neutralizing" OR "broadly neutralizing") AND "epitope"`
- **bioRxiv**: critical — most variant-specific data is preprinted before PubMed indexing
- **SAbDab**: filter for "virus" antigen class

### Intracellular Targets (Kinases, Transcription Factors)

- **Caveat first**: intracellular targets are usually NOT suitable for traditional antibody design.
  Flag to user — recommend alternative modalities (intrabodies, PROTACs) or pivot to surface partner.
- **UniProt**: confirm subcellular location is intracellular before proceeding
- If user insists, proceed but lower the expected hit rate in `design_recommendation.json`

### Disordered / Low-Complexity Targets

- **UniProt**: check for `intrinsically disordered region` annotation
- **PDB**: expect few or zero structures
- **PubMed**: `"{target}" AND ("intrinsically disordered" OR "IDR" OR "low complexity")`
- **Action**: lower depth threshold (UltraDeep often required); flag fold validation risk

---

## Query Construction Patterns

### General Boolean structure

```
"{target}" AND ({modality_clause}) AND ({evidence_clause})
```

Where:
- `{modality_clause}` = `("antibody" OR "nanobody" OR "VHH" OR "binder")`
- `{evidence_clause}` = `("crystal structure" OR "epitope" OR "binding" OR "affinity")`

Drop clauses progressively if too few hits.

### Date-range strategy

- **Default**: last 5 years for PubMed, last 2 years for bioRxiv
- **Novel target**: expand to last 10 years on PubMed
- **Foundational biology**: drop the date filter entirely (some classic papers are old)
- **Cutting-edge methods (BoltzGen, AF3 variants)**: last 12 months on bioRxiv only

### Alternative naming

Always search at least two of:
1. Common name (`"TNF-alpha"`)
2. Gene symbol (`"TNFSF2"`)
3. Full IUPHAR / UniProt recommended name (`"tumor necrosis factor"`)
4. Older nomenclature (`"cachectin"`)

SAbDab's antigen_name field uses long-form names — always try the recommended name there.

### Negative filters

Add `NOT` clauses when irrelevant noise dominates:
- `NOT "review"` — exclude reviews when you need primary data
- `NOT "{wrong_organism}"` — exclude common false-positive organisms (mouse vs human ortholog confusion)
- `NOT "knockout"` — exclude phenotype-only papers when you need molecular detail

---

## Confidence Tiering

Every finding written to `validated_findings.json` carries a confidence label. Use
these rules consistently across the pipeline.

### HIGH

- 3+ independent sources agree
- At least one source has credibility >= 0.90 (peer-reviewed paper or PDB structure)
- Structural and literature data converge on the same conclusion
- Example: "Residues Y56 and R113 are interface contacts" supported by PDB 7S4S, PDB 8XYZ, and a mutagenesis paper.

### MEDIUM

- 2 sources agree
- OR 1 source with credibility >= 0.90 stands alone (acceptable when no contradiction exists)
- Example: A single Nature paper reports an affinity Kd value that is internally consistent across replicates.

### LOW

- Single source only AND credibility < 0.70
- Computational prediction without experimental backing
- Example: An AlphaFold-predicted interface with no mutagenesis or co-crystal evidence.

### CONTRADICTED

- Two or more credible sources disagree
- Always write both positions explicitly; never silently pick one
- Example: Source A reports Kd = 10 nM by SPR; Source B reports Kd = 1 nM by SPR with same construct. Report as `"Kd reported between 1-10 nM; assay conditions vary"`.

### SPECULATIVE

- Reserve for working hypotheses generated during Phase 5 (SYNTHESIZE) that lack any source
- Must be labeled clearly in `research.md` as a hypothesis, not a finding
- Never feed into `recommended_hotspots.json` or `design_recommendation.json`

---

## Avoiding Search-Phase Pitfalls

- **Cherry-picking**: if a search returns many results, sample broadly across publication dates and journals; do not stop at the first confirming paper.
- **Single-lab bias**: if all sources come from one group, demote confidence one tier (publication bias risk).
- **Translation drift**: a paper studying mouse TNF-alpha is NOT evidence for human TNF-alpha epitopes; flag and exclude unless explicitly noting cross-species.
- **Preprint inflation**: a bioRxiv preprint reporting a new structure should be checked for subsequent peer-reviewed publication; if published, replace with the published version.
- **Stale press releases**: company announcements about clinical candidates are often outdated by the time the research runs. Always verify against current PubMed before citing.

---

## When to Escalate Search Depth

Promote depth one level (Quick → Standard, Standard → Deep, Deep → UltraDeep) when:

- Source count after Phase 3 is below the minimum for the current depth
- Phase 4 yields zero HIGH confidence findings
- Phase 6 surfaces a CRITICAL concern that requires more sources to resolve
- The user explicitly requests more thorough research

Never silently expand to UltraDeep without informing the user — it adds 30+ minutes.
