---
id: "skill_bf649c6b31b64e9797f3b685b50f0b77"
name: "by-research"
display-name: "BY Research"
short-description: "Deep academic research for antibody/binder design campaigns with an 8-phase pipeline, quality gates, and persistent memory. Use when starting a new design campaign, investigating a target, searching prior art, or analyzing epitopes."
category: "research"
keywords: "target research, literature review, prior art, epitope analysis, PDB, UniProt, SAbDab, PubMed, bioRxiv, design strategy, scaffold selection, hotspot identification"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools:
  - "mcp__by-research__research_get_target_info"
  - "mcp__by-research__research_search_prior_art"
  - "mcp__by-research__research_analyze_known_binders"
  - "mcp__by-research__research_find_similar_targets"
  - "mcp__by-pdb__pdb_search"
  - "mcp__by-pdb__pdb_fetch_structure"
  - "mcp__by-pdb__pdb_get_chains"
  - "mcp__by-pdb__pdb_interface_residues"
  - "mcp__by-uniprot__uniprot_search"
  - "mcp__by-uniprot__uniprot_fetch_protein"
  - "mcp__by-uniprot__uniprot_get_domains"
  - "mcp__by-uniprot__uniprot_get_variants"
  - "mcp__by-sabdab__sabdab_search_antibodies"
  - "mcp__by-sabdab__sabdab_get_structure"
  - "mcp__by-sabdab__sabdab_cdr_sequences"
  - "mcp__by-sabdab__sabdab_search_by_antigen"
---

# BY Research Skill

Thorough target research before design prevents wasted compute and failed campaigns.
This skill defines an 8-phase pipeline that retrieves, validates, and packages research
findings with quality gates and anti-drift checkpoints at every stage.

## When to Use This Skill

Use this skill when you have:

- ✅ **A protein target name or identifier** (UniProt accession, gene name, PDB ID, or common name)
- ✅ **A new design campaign starting** — research is always step 1 before planning
- ✅ **A need to characterize prior art** — existing antibodies, nanobodies, or designed binders
- ✅ **A target with unknown or partially characterized epitopes** — needs hotspot identification from literature + structure
- ✅ **A need to choose modality or scaffold** — research informs VHH vs scFv vs de novo
- ✅ **An interrupted research session** — resume from `research_progress.json` checkpoint

Do NOT use this skill when:

- ❌ **You already have a validated target report** in the campaign directory → load it instead of re-researching
- ❌ **You are scoring or filtering existing designs** → use `by-scoring` or `by-screening`
- ❌ **You are predicting structure of a known sequence** → use Protenix directly (no literature needed)
- ❌ **You need lab submission logistics** → use `by-deploy-compute` or the lab-submission flow
- ❌ **The user wants ranked design results** → use `by-display` / `results` skill
- ❌ **You need a one-off database lookup** (single PDB fetch) → call the MCP tool directly, no 8-phase overhead

## Quick Start

```text
User: "Research TNF-alpha for a nanobody design campaign."

Agent:
  1. Phase 1 SCOPE  → writes research/scope.json (target=TNF-alpha, modality=VHH, depth=quick)
  2. Phase 2 PLAN   → writes research/research_plan.json
  3. Phase 3 RETRIEVE → calls 4 research_* MCP tools in parallel, writes sources.json
  4. Phase 4 TRIANGULATE → writes validated_findings.json
  5. Phase 5 SYNTHESIZE → drafts research.md
  6. Phase 6 CRITIQUE  → 3 personas, writes critique.json
  7. Phase 7 REFINE   → closes gaps, updates sources.json + validated_findings.json
  8. Phase 8 PACKAGE  → writes research.md + recommended_hotspots.json + design_recommendation.json

Expected: 10-15 sources, 3+ HIGH confidence findings, 5-10 hotspot residues,
         design_recommendation.json with modality/protocol/tier ready for campaign-manager.
```

## Inputs

**Required:**
- **Target identifier** (one of):
  - Common name (e.g., `"TNF-alpha"`, `"PD-L1"`, `"HER2"`)
  - UniProt accession (e.g., `"P01375"`) — most specific, preferred
  - Gene name (e.g., `"TNFSF2"`)
  - PDB ID (e.g., `"7S4S"`) — auto-derives UniProt
- **Campaign directory** — path under `campaigns/{target}/campaign_{date}_{id}/` where outputs land

**Optional:**
- **Organism** — defaults to `Homo sapiens`. Specify for non-human orthologs.
- **Modality preference** — `VHH` / `scFv` / `Fab` / `de_novo`. Influences scaffold search.
- **Research depth** — `quick` / `standard` / `deep` / `ultradeep`. Auto-selected from indicator heuristics if absent (see depth table).
- **Therapeutic area** — narrows literature search.
- **Known information** — prior facts the user already has; skip redundant retrieval.
- **Existing checkpoint** — `research/research_progress.json` from a paused session.

See `references/literature-search-strategy.md` for query construction by organism/protein class.

## Outputs

All outputs go to the campaign directory at `campaigns/{target}/campaign_{date}_{id}/research/`:

| File | Type | Phase | Purpose |
|------|------|-------|---------|
| `scope.json` | JSON | 1 | Research boundaries (target, organism, modality, depth) |
| `research_plan.json` | JSON | 2 | Search strategy, priority order, time budget |
| `sources.json` | JSON | 3, 7 | All retrieved sources with credibility scores |
| `validated_findings.json` | JSON | 4, 7 | Cross-validated findings with confidence (HIGH/MEDIUM/LOW/CONTRADICTED) |
| `critique.json` | JSON | 6 | Multi-persona red team concerns with severity |
| `research_progress.json` | JSON | Every | Checkpoint for resume (current phase, completed phases, phase outputs) |
| `research.md` | Markdown | 8 | Final formatted report — feeds campaign_plan.md |
| `recommended_hotspots.json` | JSON | 8 | Residue list with range notation for design agent |
| `design_recommendation.json` | JSON | 8 | Modality, protocol, scaffolds, tier, budget for campaign-manager |

The two **downstream-critical** outputs are `recommended_hotspots.json` (consumed by `by-epitope-analysis`) and `design_recommendation.json` (consumed by `by-campaign-manager`).

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — confirm you have a usable target identifier and campaign directory before doing any retrieval.

1. **Target identifier (ASK THIS FIRST)** — What is the target? Provide a UniProt accession if available, otherwise common name + organism. Without this, no retrieval is possible.
2. **Campaign directory** — Where should research outputs land? Default is `campaigns/{target}/campaign_{YYYYMMDD}_{nnn}/research/`. Confirm the path or let the campaign-manager skill allocate one.
3. **Modality preference** — VHH / scFv / Fab / de novo? Influences SAbDab scaffold filtering and the design recommendation. If unknown, the skill suggests based on target class.
4. **Research depth** — Quick / Standard / Deep / UltraDeep? If unspecified, auto-select using the indicator heuristics (PDB/SAbDab/PubMed counts).
5. **Therapeutic area or use case** — Autoimmune? Oncology? Diagnostics? Narrows the PubMed search and risk assessment.
6. **Known prior art to include** — Has the user already identified key papers or structures? Add them as seed sources to avoid re-discovery.
7. **Time budget** — Hard deadline? Sets which phases can be skipped if time runs low (see `references/methodology.md` Time Management).

## Standard Workflow

🚨 **MANDATORY: USE THE 8-PHASE PIPELINE EXACTLY AS DEFINED — DO NOT COMBINE OR SKIP PHASES** 🚨

The 8-phase pipeline (SCOPE → PLAN → RETRIEVE → TRIANGULATE → SYNTHESIZE → CRITIQUE → REFINE → PACKAGE) is defined in the next section. Each phase has a discrete output written to the campaign directory. After every phase, update `research_progress.json` before moving on.

**Discipline:**
- ✅ Write the phase's JSON output before claiming the phase is complete
- ✅ Update `research_progress.json` after every phase (it is the source of truth for resume)
- ✅ Run RETRIEVE-stage tool calls in parallel where possible (single message, multiple tool calls)
- ❌ Do NOT skip Phase 4 (TRIANGULATE) — without it, downstream confidence values are invented
- ❌ Do NOT skip Phase 6 (CRITIQUE) for non-Quick depths — it catches the failure modes that waste compute
- ❌ Do NOT write `research.md` from memory after phases finish — it must cite `sources.json` entries

## Research Depth

Auto-select depth based on how well-studied the target is. If uncertain, start with
Standard and let quality gates decide whether to iterate.

| Depth | When | Phases | Time | Min Sources |
|-------|------|--------|------|-------------|
| Quick | Well-studied target (TNF-alpha, PD-L1, HER2) | 1-3-5-8 | 5 min | 5+ |
| Standard | Moderate target (some known binders) | All 8 | 15 min | 10+ |
| Deep | Novel target (no known binders) | All 8 + iteration | 30 min | 15+ |
| **UltraDeep** | **Extremely novel (0 PDB, 0 SAbDab, novel organism/modality)** | **All 8 + 2-3 iterations of 3-7 + cross-species homolog search** | **45+ min** | **20+** |

Indicators for depth selection:
- **Quick**: >10 PDB structures, >5 SAbDab antibodies, >50 PubMed papers
- **Standard**: 2-10 PDB structures, 1-5 SAbDab antibodies, 10-50 papers
- **Deep**: 0-1 PDB structures, 0 SAbDab antibodies, <10 papers
- **UltraDeep**: 0 PDB structures, 0 SAbDab entries, AND any of: novel organism (not human/mouse), novel modality (bispecific, peptide-protein hybrid), or user explicitly requests "deep dive" / "thorough research"

### UltraDeep Mode

UltraDeep triggers when:
- Zero PDB structures for the target
- Zero SAbDab entries
- Novel organism (not human/mouse)
- Novel modality request (e.g., bispecific, peptide-protein hybrid)
- User explicitly requests "deep dive" or "thorough research"

UltraDeep adds the following on top of Deep:
- **Cross-species homolog search**: Find similar proteins in other organisms with known binders via `mcp__by-research__research_find_similar_targets`, expanding to orthologs across species
- **Molecular docking literature review**: Targeted PubMed/bioRxiv search for docking studies on the target or homologs
- **Patent landscape scan**: PubMed patent filter search to identify prior IP and freedom-to-operate considerations
- **2-3 iterations of Phase 3-7**: Retrieve-critique loop runs 2-3 times (vs 1 for Deep) to maximize coverage
- **Minimum 20 sources, 5+ HIGH confidence findings** required to pass quality gates

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

1. `mcp__by-research__research_get_target_info` — UniProt protein info + PDB structures
2. `mcp__by-research__research_search_prior_art` — PubMed + bioRxiv literature
3. `mcp__by-research__research_analyze_known_binders` — SAbDab antibody database
4. `mcp__by-research__research_find_similar_targets` — homologs with known binders

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

Challenge the synthesis using three distinct review personas. Each persona applies a
different lens to the research. The critique output must label every concern with the
persona that raised it (e.g., `[Skeptical Practitioner]`, `[Adversarial Reviewer]`,
`[Implementation Engineer]`).

#### Persona 1: Skeptical Practitioner
Challenges evidence quality and reproducibility:
- Would this replicate? Are the key binding studies based on single experiments or independent replication?
- Is the crystal structure resolution good enough? (>3.0 A structures may have unreliable interface contacts)
- Are we extrapolating from too few data points? (e.g., one mutagenesis study defining the entire epitope)
- Has this epitope actually been validated experimentally, or is it only computationally predicted?
- Are the reported affinity values (Kd, IC50) from comparable assay formats?

#### Persona 2: Adversarial Reviewer
Attacks logical coherence and reasoning gaps:
- Do the SAbDab results contradict the literature claims? (e.g., known antibodies binding different epitopes than claimed consensus)
- Is the recommended scaffold justified by evidence or just popular? (e.g., defaulting to caplacizumab without target-specific rationale)
- Are there alternative interpretations of the structural data? (e.g., crystal packing artifacts vs true biological interfaces)
- What is the weakest link in the reasoning chain from evidence to design recommendation?
- Have we cherry-picked supportive studies while ignoring contradictory ones?

#### Persona 3: Implementation Engineer
Questions practical feasibility within the BY toolchain:
- Can BoltzGen actually handle this epitope topology? (e.g., concave pockets, disordered loops, glycosylated surfaces)
- Is the compute budget sufficient for the target difficulty? (novel targets may need Exploratory tier, not Standard)
- Are the recommended scaffolds available in the BoltzGen template library? (check against known VHH/Fab scaffold sets)
- What is the fallback if this approach fails? (alternative modality, different scaffolds, or relaxed hotspot constraints)
- Are there known failure modes for similar targets in the literature?

#### Critique Output

Write `research/critique.json`:
```json
{
  "concerns": [
    {
      "persona": "Skeptical Practitioner",
      "concern": "Primary epitope mapping based on single mutagenesis study (src_004)",
      "severity": "HIGH",
      "affected_findings": ["finding_003"],
      "resolution": "Search for independent validation of residues Y56, R113"
    },
    {
      "persona": "Adversarial Reviewer",
      "concern": "SAbDab antibodies bind loop region, contradicting our beta-sheet epitope recommendation",
      "severity": "CRITICAL",
      "affected_findings": ["finding_001", "finding_005"],
      "resolution": "Re-examine epitope consensus, consider both regions"
    },
    {
      "persona": "Implementation Engineer",
      "concern": "Target has N-linked glycosylation at N78 adjacent to proposed hotspots",
      "severity": "MEDIUM",
      "affected_findings": ["finding_002"],
      "resolution": "Check if BoltzGen models glycans; if not, shift hotspots away from N78"
    }
  ],
  "critical_gaps": [],
  "summary": "3 concerns raised: 0 CRITICAL, 1 HIGH, 1 MEDIUM, 1 LOW"
}
```

Severity levels:
- **CRITICAL**: Fundamental flaw that could invalidate the design strategy. Requires return to Phase 3.
- **HIGH**: Significant gap that weakens confidence. Should be addressed in Phase 7.
- **MEDIUM**: Notable concern worth documenting. Address if feasible in Phase 7.
- **LOW**: Minor issue for awareness. Document in the final report's Uncertainties section.

If the critique identifies any CRITICAL concerns, return to Phase 3 for targeted retrieval.
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
| After Phase 3 (RETRIEVE) | Source count >= depth minimum (5/10/15/20) | Re-run with broader queries |
| After Phase 4 (TRIANGULATE) | >= 1 HIGH confidence finding | Flag to user, proceed with caveats |
| After Phase 6 (CRITIQUE) | No CRITICAL concerns from any persona | Return to Phase 3 for targeted retrieval |
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

### Research-specific (by-research server)
- `research_search_prior_art(target_name, max_results)` — PubMed + bioRxiv
- `research_get_target_info(target)` — UniProt + PDB combined query
- `research_analyze_known_binders(target_name, max_structures)` — SAbDab
- `research_find_similar_targets(uniprot_accession, max_results)` — UniProt homolog search

### Database tools (for deep dives)
- `mcp__by-pdb__pdb_search`, `mcp__by-pdb__pdb_fetch_structure`, `mcp__by-pdb__pdb_get_chains`, `mcp__by-pdb__pdb_interface_residues`
- `mcp__by-uniprot__uniprot_search`, `mcp__by-uniprot__uniprot_fetch_protein`, `mcp__by-uniprot__uniprot_get_domains`, `mcp__by-uniprot__uniprot_get_variants`
- `mcp__by-sabdab__sabdab_search_antibodies`, `mcp__by-sabdab__sabdab_get_structure`, `mcp__by-sabdab__sabdab_cdr_sequences`, `mcp__by-sabdab__sabdab_search_by_antigen`

For database tool usage patterns, see the `by-database` skill.

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
| `critique.json` | Multi-persona red team concerns | 6 |
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

---

## When Scripts Fail

This skill ships two scripts (`scripts/research_report_template.md` and
`scripts/summarize_research.py`). If they fail, follow the standard hierarchy:

1. **Fix and Retry (90%)** — Most failures are a missing dependency or wrong path.
   - `summarize_research.py` only depends on Python stdlib (`json`, `argparse`, `pathlib`).
     If it errors, check the input JSON path and run again.
   - The template is a static markdown file — copy it, fill it, save.
2. **Modify Script (5%)** — Edit the script in place if the report layout needs an
   extra section or the summary needs a new field. Keep the CLI signature stable.
3. **Use as Reference (4%)** — If the campaign needs a substantially different
   report format, read the template, adapt the structure inline, but still cite
   `sources.json` entries.
4. **Write from Scratch (1%)** — Only if the 8-phase outputs cannot be reconciled
   with the template (rare). Document why in `research/notes.md`.

If the MCP retrieval tools fail (Phase 3), fall back per the database fallback chain
in `CLAUDE.md`: research_* MCP → by-pdb/by-uniprot/by-sabdab MCP → PubMed/bioRxiv → WebSearch.
Never silently substitute web search for structured databases.

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| `research_get_target_info` returns no UniProt hit | Common name matches multiple species or is ambiguous (e.g., "TNF") | Disambiguate with organism + canonical name (`"TNF-alpha"` + `"Homo sapiens"`) or pass UniProt accession directly | `references/literature-search-strategy.md` |
| Fewer than 5 sources after Phase 3 | Query too narrow; "antibody" filter excludes general biology | Drop modality modifier, expand date range, search by gene family | `references/methodology.md` Query Construction |
| `validated_findings.json` has 0 HIGH confidence findings | Single-source evidence only; no cross-validation possible | Phase 4 gate failure — proceed with caveat banner; recommend Preview tier only | `references/quality-gates.md` Phase 4 gate |
| Conflicting affinity values across papers | Different assay formats (SPR vs ELISA vs computational) | Report as range; prefer SPR/BLI; flag CONTRADICTED if assay formats are equivalent | `references/methodology.md` Cross-Validation |
| SAbDab returns 0 antibodies for known therapeutic target | SAbDab antigen_name uses long-form names | Retry with full name (`"tumor necrosis factor"` not `"TNF-alpha"`) | `references/methodology.md` Known Binders Query |
| Context compacted mid-research | Long retrieval phases exhaust context window | Read `research/research_progress.json` first, then load only the JSON outputs you need to continue | `references/checkpoint-recovery.md` |
| Phase 6 critique surfaces a CRITICAL concern | Adversarial Reviewer found a contradicting source set | Return to Phase 3 with targeted query addressing the contradiction; max 2 iterations | `references/checkpoint-recovery.md` Invalidating Downstream Phases |
| Hotspots include glycosylation site (e.g., N-linked NXS/T) | BoltzGen does not model glycans by default | Implementation Engineer persona flags it in Phase 6 — shift hotspot window or document as a risk | SKILL.md Phase 6 |
| PDB structure resolution > 3.5 A used for interface residues | Low-resolution structure has unreliable side-chain rotamers | Demote to MEDIUM confidence; require corroboration from mutagenesis or higher-resolution homolog | `references/quality-gates.md` Resolution-adjusted |
| `research.md` contains a claim with no `[src_XXX]` citation | Phase 5 synthesis drifted from sources | Phase 8 gate — remove or demote claim; if claim is critical, re-retrieve to back it | `references/quality-gates.md` Phase 8 gate |
| Computational prediction cited as experimental fact | Failed to label AlphaFold / docking output | Edit `sources.json` to set `type: "computational_prediction"` and credibility 0.50; relabel in prose as "predicted" | SKILL.md Anti-Hallucination Rules |
| Resume from checkpoint loads wrong phase | `research_progress.json` not updated after last completed phase | Recompute `current_phase` from the largest key in `phase_outputs` + 1; rewrite the checkpoint | `references/checkpoint-recovery.md` Checkpoint Format |
| UltraDeep mode times out before Phase 8 | 2-3 iterations of 3-7 exceed time budget | Cap iterations at 2; if still under-supported, package with explicit "preliminary" flag and Uncertainties section | `references/methodology.md` Time Management |

---

## Best Practices

1. 🚨 **CRITICAL: Always run Phase 1 (SCOPE) before any retrieval.** Skipping scope leads to scope creep and wasted MCP calls.
2. ✅ **REQUIRED: Update `research_progress.json` after every phase.** It is the only resilient resume mechanism.
3. ✅ **REQUIRED: Cite every claim in `research.md` with a `[src_XXX]` reference.** Phase 8 gate enforces this; do not bypass.
4. ✅ Run Phase 3 retrieval tools in parallel (single message, multiple MCP calls) — saves 60-80% wall time.
5. ✅ Prefer UniProt accession over common name when calling `research_get_target_info` — disambiguates species.
6. ✅ Label every computational source explicitly (`"predicted (AlphaFold)"`) — never present as experimental.
7. ✅ Use the Implementation Engineer persona in Phase 6 to catch BoltzGen-specific topology issues (glycans, disordered loops).
8. ❌ Do NOT skip Phase 4 even when you "already know" the findings agree — write them down explicitly.
9. ❌ Do NOT fabricate PDB IDs, UniProt accessions, PMIDs, or affinity values. If a search returns no results, say "no data found."
10. ✨ **Optional:** After Phase 8, persist novel target insights to `.claude/memory/` for reuse in future campaigns on the same target family.

---

## Suggested Next Steps

After completing this skill, chain into these skills in order:

1. **`by-epitope-analysis`** — consumes `recommended_hotspots.json` and runs deeper structural analysis on the proposed hotspot window (SASA, conservation, druggability). Use this whenever the design will target a specific epitope region.
2. **`by-campaign-manager`** — consumes `design_recommendation.json` and writes `campaign_plan.md` with budget, scaffolds, fold validation criteria, and submission plan. Required before any compute is committed.
3. **`by-hypothesis-debate`** (optional) — if the research yielded multiple viable design strategies, run a hypothesis debate before locking in the modality.
4. **`by-design-workflow`** — orchestrates the full Research → Plan → Approve → Design → Screen → Rank pipeline; this skill is its Research stage.

The chain works because each downstream skill expects exactly the JSON shapes this skill writes. Bypassing this skill and writing the JSON files by hand is permitted only when a validated target report already exists.

---

## Related Skills

**Upstream (run before this):**
- `by-session` — initializes the BY project, ensures campaign directory exists.

**Downstream (run after this):**
- `by-epitope-analysis` — deeper structural hotspot characterization.
- `by-campaign-manager` — converts research into a budgeted campaign plan.
- `by-design-workflow` — orchestrates the full design pipeline.

**Alternative / complementary:**
- `by-database` — direct database queries for one-off lookups without the 8-phase overhead.
- `by-knowledge` — project knowledge graph for cross-campaign learnings on similar targets.
- `by-hypothesis-debate` — adversarial strategy selection when multiple design paths are viable.

---

## References

**Detailed documentation:**
- [`references/methodology.md`](references/methodology.md) — database priority, query construction, cross-validation rules, anti-hallucination details, time management.
- [`references/quality-gates.md`](references/quality-gates.md) — credibility scoring, confidence levels, minimum thresholds by depth, gate failure actions.
- [`references/literature-search-strategy.md`](references/literature-search-strategy.md) — search strategy by organism/protein class, database-first decisions, query patterns, confidence tiering.
- [`references/checkpoint-recovery.md`](references/checkpoint-recovery.md) — checkpoint format, resume protocol, invalidating downstream phases when upstream findings change.

**Scripts:**
- [`scripts/research_report_template.md`](scripts/research_report_template.md) — fillable markdown template covering all 8 phases.
- [`scripts/summarize_research.py`](scripts/summarize_research.py) — CLI that reads 8-phase checkpoint outputs and writes a one-page markdown summary for inclusion in `campaign_plan.md`.

**External documentation:**
- PDB: https://www.rcsb.org/
- UniProt: https://www.uniprot.org/
- SAbDab: https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/
- PubMed: https://pubmed.ncbi.nlm.nih.gov/
- bioRxiv: https://www.biorxiv.org/
