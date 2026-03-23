---
name: proteus-research
description: Deep academic research for antibody design campaigns — target analysis, literature review, prior art search, epitope identification. Uses an 8-phase pipeline with quality gates and persistent memory. Use this skill whenever researching a protein target, starting a new design campaign, investigating prior art, analyzing epitopes, reviewing literature for design strategy, or when the user mentions target research, literature search, or prior art in the context of protein/antibody design.
---

# Proteus Research Skill

Thorough target research before design prevents wasted compute and failed campaigns.
This skill defines an 8-phase pipeline that retrieves, validates, and packages research
findings with quality gates and anti-drift checkpoints at every stage.

## When to Use

- Starting a new design campaign (target research is always step 1)
- Investigating a protein target before committing to a design modality
- Searching for prior art (existing antibodies, nanobodies, binders)
- Analyzing epitope regions and binding sites from literature + structure
- Literature review for design strategy or scaffold selection
- Resuming interrupted research (checkpoint recovery)

## Research Depth

Auto-select depth based on how well-studied the target is. If uncertain, start with
Standard and let quality gates decide whether to iterate.

| Depth | When | Phases | Time | Min Sources |
|-------|------|--------|------|-------------|
| Quick | Well-studied target (TNF-alpha, PD-L1, HER2) | 1-3-5-8 | 5 min | 5+ |
| Standard | Moderate target (some known binders) | All 8 | 15 min | 10+ |
| Deep | Novel target (no known binders) | All 8 + iteration | 30 min | 15+ |

Indicators for depth selection:
- **Quick**: >10 PDB structures, >5 SAbDab antibodies, >50 PubMed papers
- **Standard**: 2-10 PDB structures, 1-5 SAbDab antibodies, 10-50 papers
- **Deep**: 0-1 PDB structures, 0 SAbDab antibodies, <10 papers

---

## 8-Phase Research Pipeline

### Phase 1: SCOPE

Define the research boundaries before searching anything.

Write `research/scope.json` to the campaign directory:
```json
{
  "target_name": "TNF-alpha",
  "organism": "Homo sapiens",
  "uniprot_accession": null,
  "therapeutic_area": "Autoimmune / inflammation",
  "modality_preference": "VHH",
  "known_information": ["Homotrimeric cytokine", "Multiple approved antibodies"],
  "gaps_to_fill": ["Novel epitope regions", "VHH-specific binding data"],
  "research_depth": "quick",
  "started_at": "2026-03-23T10:00:00Z"
}
```

Scope comes from user input and quick heuristics. Do not search databases yet.

### Phase 2: PLAN

Create a research strategy based on the scope.

Write `research/research_plan.json`:
```json
{
  "database_queries": [
    {"database": "UniProt+PDB", "tool": "research_get_target_info", "query": "TNF-alpha"},
    {"database": "PubMed+bioRxiv", "tool": "research_search_prior_art", "query": "TNF-alpha"},
    {"database": "SAbDab", "tool": "research_analyze_known_binders", "query": "TNF-alpha"},
    {"database": "UniProt BLAST", "tool": "research_find_similar_targets", "query": "P01375"}
  ],
  "priority_order": ["structure", "literature", "antibodies", "homologs"],
  "depth_per_source": "standard",
  "estimated_time_minutes": 15
}
```

Priority: structure data first (most reliable for interface analysis), then literature,
then existing binders, then homologs with known binders.

### Phase 3: RETRIEVE

Execute all searches. Run tools in parallel where possible:

1. `research_get_target_info` — UniProt protein info + PDB structures
2. `research_search_prior_art` — PubMed + bioRxiv literature
3. `research_analyze_known_binders` — SAbDab antibody database
4. `research_find_similar_targets` — homologs with known binders

Save ALL results to `research/sources.json` with credibility scores:

| Source Type | Credibility | Examples |
|-------------|-------------|---------|
| Crystal structure (PDB) | 0.95 | X-ray, cryo-EM structures |
| Peer-reviewed paper | 0.90 | Nature, Science, PNAS, JMB |
| bioRxiv/medRxiv preprint | 0.70 | Unreviewed manuscripts |
| Computational prediction | 0.50 | AlphaFold models, docking studies |
| Blog/press release | 0.30 | Company announcements |

Each source entry in `sources.json`:
```json
{
  "id": "src_001",
  "type": "pdb_structure",
  "credibility": 0.95,
  "identifier": "7S4S",
  "title": "Crystal structure of PD-L1 in complex with VHH",
  "key_findings": ["Interface residues: Y56, R113, A121"],
  "retrieved_from": "research_get_target_info",
  "retrieved_at": "2026-03-23T10:02:00Z"
}
```

**Quality gate**: After Phase 3, check source count against depth thresholds.
If below minimum, re-run with broader queries (drop "antibody" filter, expand date range).

### Phase 4: TRIANGULATE

Cross-validate findings across sources:

- Do structural data (PDB interface residues) match literature claims about binding sites?
- Do known antibody epitopes from SAbDab agree with PubMed-reported epitopes?
- Are binding affinity values consistent across publications?

Assign confidence to each finding:
- **HIGH**: 3+ independent sources agree
- **MEDIUM**: 2 sources agree
- **LOW**: Single source only
- **CONTRADICTED**: Sources disagree (flag explicitly with both sides)

Write `research/validated_findings.json`:
```json
{
  "findings": [
    {
      "claim": "Residues Y56, R113 are critical for PD-1 binding",
      "confidence": "HIGH",
      "supporting_sources": ["src_001", "src_003", "src_007"],
      "contradicting_sources": [],
      "notes": ""
    }
  ],
  "contradictions": [],
  "summary": "12 findings: 5 HIGH, 4 MEDIUM, 3 LOW, 0 CONTRADICTED"
}
```

### Phase 5: SYNTHESIZE

Structure findings into a coherent narrative covering:

1. **Target overview** — function, structure, therapeutic relevance
2. **Known binders** — existing antibodies/nanobodies from SAbDab + literature
3. **Epitope analysis** — consensus hotspot residues, interface character
4. **Design strategy** — recommended modality, scaffolds, campaign tier
5. **Risk assessment** — target difficulty, expected hit rate, key risks

This is the first draft of the research report. Write it as structured prose with
inline citations (e.g., "[src_001]").

### Phase 6: CRITIQUE

Challenge the synthesis with adversarial questions:

- What evidence is missing? (e.g., no crystal structure of the exact epitope region)
- What assumptions are unvalidated? (e.g., assuming human TNF-alpha binds like mouse)
- Are there contradicting studies we glossed over?
- What could go wrong with the recommended design approach?
- Is the recommended modality actually the best choice given the evidence?

If the critique identifies critical gaps, return to Phase 3 for targeted retrieval.
"Critical gap" = a finding rated HIGH confidence that lacks structural validation,
or a design recommendation based only on LOW confidence findings.

### Phase 7: REFINE

Address critique findings:

- Run additional targeted searches to fill gaps
- Strengthen weak claims with additional sources
- Explicitly note remaining uncertainties (do not hide them)
- Update confidence levels in `validated_findings.json`
- Add new sources to `sources.json`

### Phase 8: PACKAGE

Write final outputs to the campaign directory:

1. **`research/research.md`** — formatted report (see Output Format below)
2. **`research/recommended_hotspots.json`** — residue list for the design agent
3. **`research/design_recommendation.json`** — modality, scaffolds, tier, parameters
4. Update campaign state with research summary

---

## Anti-Drift Checkpoints

After completing each phase, write progress to `research/research_progress.json`:

```json
{
  "campaign_id": "tnf_alpha_20260323_001",
  "current_phase": 3,
  "completed_phases": [1, 2],
  "phase_outputs": {
    "1": "scope.json",
    "2": "research_plan.json"
  },
  "sources_count": 12,
  "quality_gate_passed": true,
  "research_depth": "standard",
  "started_at": "2026-03-23T10:00:00Z",
  "last_checkpoint": "2026-03-23T10:05:00Z"
}
```

**Resuming from checkpoint**: If context is compacted mid-research, read
`research/research_progress.json` first. Load all phase outputs listed in
`phase_outputs`. Continue from the phase after the last completed one.

Short task cycles matter: each phase is a discrete, reviewable step. Do not combine
phases or skip checkpoints. The checkpoint file is the source of truth for progress.

---

## Quality Gates

| Gate | Requirement | Action if Failed |
|------|-------------|-----------------|
| After Phase 3 (RETRIEVE) | Source count >= depth minimum (5/10/15) | Re-run with broader queries |
| After Phase 4 (TRIANGULATE) | >= 1 HIGH confidence finding | Flag to user, proceed with caveats |
| After Phase 6 (CRITIQUE) | No critical gaps identified | Return to Phase 3 for targeted retrieval |
| After Phase 8 (PACKAGE) | All major claims have >= 1 citation | Add missing citations before finalizing |

For detailed credibility scoring and confidence criteria, read
`references/quality-gates.md`.

---

## Output Format

### research.md structure

```markdown
# Research Report: {Target Name}

## Executive Summary
(2-3 sentences: what the target is, what's known, what we recommend)

## Target Profile
- Name: {name}
- Organism: {organism}
- UniProt: {accession}
- PDB entries: {ids with resolution}
- Function: {brief description}
- Therapeutic relevance: {indication areas}

## Known Binders
| Source | Type | PDB | Epitope Region | Affinity | Reference |
|--------|------|-----|---------------|----------|-----------|
(Table of existing antibodies from SAbDab + literature)

## Epitope Analysis
### Consensus Hotspots
| Residue | AA | Classification | Confidence | Sources |
|---------|-----|---------------|------------|---------|
(Hotspot residues with type and evidence level)

### Interface Character
(Hydrophobic/polar balance, pocket depth, accessibility)

## Design Recommendation
- Modality: VHH / scFv / De novo
- Scaffolds: {recommended with rationale}
- Tier: {preview/standard/production with rationale}
- Estimated designs: {num}
- Hotspot residues: {list in entities YAML range notation}

## Risk Assessment
- Target difficulty: {well-studied / moderate / novel}
- Expected hit rate: {range based on campaign-manager baselines}
- Key risks: {list with mitigation strategies}

## Uncertainties
(Explicitly list what we do NOT know and what remains unvalidated)

## References
[src_001] PDB 7S4S — Crystal structure of...
[src_002] PMID 12345678 — Smith et al. (2024)...
(Numbered citations matching inline references)
```

### recommended_hotspots.json

```json
{
  "target": "TNF-alpha",
  "pdb_id": "7S4S",
  "target_chain": "A",
  "hotspots": [
    {"residue": 56, "aa": "Y", "classification": "polar_anchor", "confidence": "HIGH"},
    {"residue": 113, "aa": "R", "classification": "salt_bridge", "confidence": "HIGH"}
  ],
  "range_notation": "A56-A58,A113,A121-A125",
  "source_ids": ["src_001", "src_003"]
}
```

### design_recommendation.json

```json
{
  "target": "TNF-alpha",
  "modality": "VHH",
  "protocol": "nanobody-anything",
  "scaffolds": ["caplacizumab", "ozoralizumab"],
  "tier": "standard",
  "num_designs_per_scaffold": 5000,
  "budget": 50,
  "rationale": "Well-studied target with multiple VHH co-crystals...",
  "estimated_hit_rate": "20-40%",
  "estimated_time_hours": 2,
  "research_source_ids": ["src_001", "src_002", "src_005"]
}
```

---

## MCP Tools Available

### Research-specific (proteus-research server)
- `research_search_prior_art(target_name, max_results)` — PubMed + bioRxiv
- `research_get_target_info(target)` — UniProt + PDB combined query
- `research_analyze_known_binders(target_name, max_structures)` — SAbDab
- `research_find_similar_targets(uniprot_accession, max_results)` — UniProt homolog search

### Database tools (for deep dives)
- `pdb_search`, `pdb_fetch_structure`, `pdb_get_chains`, `pdb_interface_residues`
- `uniprot_search`, `uniprot_fetch_protein`, `uniprot_get_domains`, `uniprot_get_variants`
- `sabdab_search_antibodies`, `sabdab_get_structure`, `sabdab_cdr_sequences`, `sabdab_search_by_antigen`

For database tool usage patterns, see the `proteus-database` skill.

---

## Memory Persistence

### Session artifacts (campaign directory)

All files go under `campaigns/{target}/campaign_{date}_{id}/research/`:

| File | Purpose | Written in Phase |
|------|---------|-----------------|
| `scope.json` | Research boundaries | 1 |
| `research_plan.json` | Search strategy | 2 |
| `sources.json` | All sources with credibility scores | 3, 7 |
| `validated_findings.json` | Cross-validated findings with confidence | 4, 7 |
| `research_progress.json` | Phase tracking for resume | Every phase |
| `research.md` | Final formatted report | 8 |
| `recommended_hotspots.json` | Residue list for design agent | 8 |
| `design_recommendation.json` | Parameters for campaign orchestrator | 8 |

### Project memory (.claude/memory/)

After completing research, persist target-specific insights that may help future
conversations: novel findings about the target, successful design strategies for
similar targets, or corrections to commonly misunderstood target biology.

---

## Anti-Hallucination Rules

These are non-negotiable:
- NEVER fabricate PDB IDs, UniProt accessions, PMIDs, or DOIs
- NEVER invent binding affinity values (Kd, IC50, EC50)
- NEVER claim a crystal structure exists without PDB verification
- NEVER present computational predictions as experimental facts
- If a search returns no results, say "no data found" — do not guess
- All claims in research.md must trace to a source in sources.json
- Flag computational predictions explicitly: "predicted (AlphaFold)" vs "experimental (X-ray)"

For detailed methodology including database priority, query construction, and
cross-validation rules, read `references/methodology.md`.
