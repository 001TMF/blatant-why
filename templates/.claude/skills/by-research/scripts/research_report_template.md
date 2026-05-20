# Research Report: {TARGET_NAME}

> **How to use this template**
> Copy this file into the campaign directory at
> `campaigns/{target}/campaign_{date}_{id}/research/research.md` and replace each
> `{PLACEHOLDER}` with the corresponding value from the 8-phase JSON outputs in
> the same `research/` directory. Delete this admonition before saving.
>
> Every claim below MUST cite a `[src_XXX]` entry from `sources.json`. Uncited
> claims fail the Phase 8 quality gate.

---

## Executive Summary

- **Target:** {TARGET_NAME} ({ORGANISM}, UniProt {UNIPROT_ACCESSION})
- **Research depth:** {QUICK|STANDARD|DEEP|ULTRADEEP}
- **Sources reviewed:** {N_TOTAL} ({N_HIGH} HIGH, {N_MEDIUM} MEDIUM, {N_LOW} LOW, {N_CONTRADICTED} CONTRADICTED)
- **Recommended modality:** {VHH|scFv|Fab|de_novo}
- **Recommended tier:** {preview|standard|production}
- **Headline finding:** {ONE_SENTENCE_KEY_INSIGHT}

---

## Phase 1 — Scope

Source: `scope.json`

- **Target name:** {TARGET_NAME}
- **Organism:** {ORGANISM}
- **UniProt accession:** {UNIPROT_ACCESSION}
- **Therapeutic area:** {THERAPEUTIC_AREA}
- **Modality preference:** {MODALITY_PREFERENCE}
- **Known information seeded by user:**
  - {SEED_FACT_1}
  - {SEED_FACT_2}
- **Gaps identified for retrieval:**
  - {GAP_1}
  - {GAP_2}

---

## Phase 2 — Research Plan

Source: `research_plan.json`

- **Priority order:** {ORDERED_LIST_OF_DATABASES}
- **Time budget:** {ESTIMATED_MINUTES} min ({HARD_LIMIT_MINUTES} min hard cap)
- **Tools invoked:**
  - {TOOL_1} — query `{QUERY_1}`
  - {TOOL_2} — query `{QUERY_2}`
  - {TOOL_3} — query `{QUERY_3}`
  - {TOOL_4} — query `{QUERY_4}`

---

## Phase 3 — Retrieved Sources

Source: `sources.json`

### Source counts by type

| Type | Count | Avg credibility |
|------|-------|-----------------|
| Crystal structure (PDB) | {N_PDB} | {AVG_PDB_CRED} |
| Peer-reviewed paper | {N_PEER} | {AVG_PEER_CRED} |
| bioRxiv preprint | {N_BIORXIV} | {AVG_BIORXIV_CRED} |
| Computational prediction | {N_COMP} | {AVG_COMP_CRED} |
| Other | {N_OTHER} | {AVG_OTHER_CRED} |

### Quality gate

- **Threshold:** {MIN_SOURCES_FOR_DEPTH}
- **Actual:** {N_TOTAL}
- **Status:** {PASS|FAIL}

### Top sources (highest credibility, max 10)

| ID | Type | Identifier | Credibility | Key finding |
|----|------|-----------|-------------|-------------|
| {src_001} | {TYPE} | {PDB_OR_PMID} | {SCORE} | {ONE_LINE_FINDING} |

---

## Phase 4 — Validated Findings

Source: `validated_findings.json`

### Findings by confidence

| Confidence | Count | Examples |
|------------|-------|----------|
| HIGH | {N_HIGH} | {EXAMPLE_FINDING_HIGH} |
| MEDIUM | {N_MEDIUM} | {EXAMPLE_FINDING_MEDIUM} |
| LOW | {N_LOW} | {EXAMPLE_FINDING_LOW} |
| CONTRADICTED | {N_CONTRADICTED} | {EXAMPLE_CONTRADICTION} |

### Contradictions to flag

- {CONTRADICTION_1}: Source A says {A_POSITION} [src_XXX]; Source B says {B_POSITION} [src_YYY]
- {CONTRADICTION_2}: ...

### Quality gate

- **Threshold:** >= 1 HIGH confidence finding
- **Actual:** {N_HIGH}
- **Status:** {PASS|FAIL}

---

## Phase 5 — Synthesis

### Target Profile

- **Name:** {TARGET_NAME} [src_XXX]
- **Organism:** {ORGANISM}
- **UniProt:** {UNIPROT_ACCESSION}
- **PDB entries:** {PDB_ID_LIST_WITH_RESOLUTION}
- **Function:** {ONE_PARAGRAPH_FUNCTION_DESCRIPTION} [src_XXX]
- **Therapeutic relevance:** {INDICATION_AREAS} [src_XXX]

### Known Binders

| Source | Modality | PDB | Epitope region | Affinity (Kd) | Reference |
|--------|----------|-----|----------------|---------------|-----------|
| {BINDER_1} | {VHH|scFv|Fab} | {PDB_ID} | {RESIDUE_RANGE} | {KD_VALUE} | [src_XXX] |

### Epitope Analysis

#### Consensus Hotspots

| Residue | AA | Classification | Confidence | Sources |
|---------|-----|----------------|------------|---------|
| {RES_NUM} | {AA} | {polar_anchor|hydrophobic|salt_bridge|backbone} | {HIGH|MEDIUM|LOW} | [src_XXX, src_YYY] |

#### Interface Character

{PARAGRAPH_DESCRIBING_INTERFACE: hydrophobic/polar balance, pocket depth, accessibility,
glycosylation proximity, disordered regions, etc.} [src_XXX]

### Design Recommendation Narrative

{PARAGRAPH_EXPLAINING_THE_MODALITY_AND_SCAFFOLD_RATIONALE} [src_XXX]

---

## Phase 6 — Critique

Source: `critique.json`

### Concerns raised by persona

#### Skeptical Practitioner

- {CONCERN_1} — severity {LOW|MEDIUM|HIGH|CRITICAL} → {RESOLUTION}
- {CONCERN_2} — ...

#### Adversarial Reviewer

- {CONCERN_1} — severity {LOW|MEDIUM|HIGH|CRITICAL} → {RESOLUTION}

#### Implementation Engineer

- {CONCERN_1} — severity {LOW|MEDIUM|HIGH|CRITICAL} → {RESOLUTION}

### Critique gate

- **Threshold:** Zero CRITICAL concerns
- **Actual:** {N_CRITICAL}
- **Status:** {PASS|FAIL}
- **Action taken if FAIL:** {RETURN_TO_PHASE_3_OR_DOCUMENT}

---

## Phase 7 — Refinement

Source: updated `sources.json` and `validated_findings.json`

- **Targeted retrievals run:** {N_RETRIEVALS}
- **New sources added:** {N_NEW_SOURCES}
- **Findings promoted (MEDIUM → HIGH):** {N_PROMOTED}
- **Findings demoted:** {N_DEMOTED}
- **Remaining uncertainties documented:** {N_UNCERTAINTIES}

---

## Phase 8 — Package: Final Recommendation

### Design Recommendation

(From `design_recommendation.json`)

- **Modality:** {VHH|scFv|Fab|de_novo}
- **Protocol:** {nanobody-anything|antibody-anything|custom}
- **Scaffolds:** {SCAFFOLD_LIST}
- **Tier:** {preview|standard|production}
- **Designs per scaffold:** {N_DESIGNS}
- **Budget:** ${BUDGET_USD}
- **Hotspot residues (range notation):** `{HOTSPOT_RANGE_STRING}`
- **Estimated pass rate:** {RANGE_PERCENT}
- **Estimated time:** {RANGE_HOURS} hours

### Risk Assessment

- **Target difficulty:** {WELL_STUDIED|MODERATE|NOVEL|EXTREMELY_NOVEL}
- **Key risks:**
  1. {RISK_1} — mitigation: {MITIGATION_1}
  2. {RISK_2} — mitigation: {MITIGATION_2}
  3. {RISK_3} — mitigation: {MITIGATION_3}
- **Fallback plan:** {WHAT_TO_DO_IF_PRIMARY_FAILS}

### Uncertainties

Explicitly document what was NOT validated:

- {UNCERTAINTY_1}
- {UNCERTAINTY_2}
- {UNCERTAINTY_3}

---

## References

Numbered citations matching inline `[src_XXX]` references. Pull each entry from
`sources.json`.

- **[src_001]** {SOURCE_TYPE} — {IDENTIFIER} — {TITLE}
- **[src_002]** {SOURCE_TYPE} — {IDENTIFIER} — {TITLE}
- **[src_003]** {SOURCE_TYPE} — {IDENTIFIER} — {TITLE}

---

## Appendix: Pipeline Audit

- **Pipeline started:** {STARTED_AT}
- **Pipeline completed:** {COMPLETED_AT}
- **Total wall time:** {DURATION_MINUTES} min
- **Iterations through Phases 3-7:** {N_ITERATIONS}
- **Checkpoint file:** `research_progress.json`
- **All claims cited:** {YES|NO}
- **Preliminary flag:** {NONE|PHASES_SKIPPED|TIME_LIMITED}
