# Research Quality Gates

## Source Credibility Scoring

Assign a credibility score to every source added to `sources.json`. The score reflects
how much weight the finding should carry during triangulation and synthesis.

| Source Type | Score | Examples | Notes |
|-------------|-------|---------|-------|
| Crystal structure (PDB) | 0.95 | X-ray <2.5A, cryo-EM <3.5A | Gold standard for interface residues |
| Peer-reviewed paper | 0.90 | Nature, Science, PNAS, JMB, mAbs | Experimental data with peer validation |
| bioRxiv/medRxiv preprint | 0.70 | Unreviewed manuscripts | May be revised; check for updates |
| Computational prediction | 0.50 | AlphaFold models, docking, MD sims | Always label as "predicted" |
| Blog/press release | 0.30 | Company announcements, news | Verify claims with primary sources |

### Resolution-adjusted PDB credibility

Not all PDB structures are equally reliable for interface analysis:

| Resolution | Credibility Adjustment |
|------------|----------------------|
| < 2.0 A | 0.95 (full) |
| 2.0-2.5 A | 0.90 |
| 2.5-3.0 A | 0.80 |
| 3.0-3.5 A | 0.70 |
| > 3.5 A | 0.60 (caution: side-chain positions unreliable) |

For cryo-EM, apply a 0.05 penalty relative to X-ray at the same resolution
(side-chain rotamers less certain in cryo-EM maps).

### Journal impact weighting

Not all peer-reviewed papers carry equal weight. Use these tiers for literature:

| Tier | Journals | Score |
|------|----------|-------|
| Tier 1 | Nature, Science, Cell, PNAS | 0.95 |
| Tier 2 | JMB, Structure, mAbs, Nat Struct Mol Biol | 0.90 |
| Tier 3 | Other indexed journals | 0.85 |
| Tier 4 | Conference proceedings, supplements | 0.75 |

---

## Confidence Levels

Confidence reflects how strongly the evidence supports a specific claim.

- **HIGH**: 3+ independent sources agree, at least 1 with credibility >= 0.90
- **MEDIUM**: 2 sources agree, or 1 source with credibility >= 0.90
- **LOW**: Single source only, or only sources with credibility < 0.70
- **CONTRADICTED**: Sources disagree — flag explicitly with both positions

### Promoting confidence

A finding can be promoted from MEDIUM to HIGH if:
- A structural source (PDB) confirms a literature claim
- Two independent experimental methods agree (e.g., SPR + X-ray interface)
- A mutagenesis study validates a predicted hotspot

### Demoting confidence

A finding should be demoted if:
- The only supporting source is computational (max MEDIUM even with 3+ sources)
- The source uses outdated methods or has known errors
- A later publication contradicts the finding

---

## Minimum Thresholds by Depth

### Quick research (well-studied targets)
- **Sources**: >= 5 total
- **HIGH confidence findings**: >= 1
- **Structural validation**: >= 1 PDB structure with interface data
- Acceptable to skip Phases 4, 6, 7 (go 1-3-5-8)

### Standard research (moderate targets)
- **Sources**: >= 10 total
- **HIGH confidence findings**: >= 3
- **Structural validation**: >= 1 PDB structure, preferably with bound antibody
- All 8 phases required

### Deep research (novel targets)
- **Sources**: >= 15 total
- **HIGH confidence findings**: >= 5
- **Structural validation**: >= 2 structural sources (PDB or AlphaFold + homolog)
- All 8 phases + iteration back through 3-7 at least once
- Include homolog analysis (research_find_similar_targets)

---

## Gate Failure Actions

### Phase 3 gate failure (insufficient sources)

1. Broaden search queries: drop "antibody" or "nanobody" modifiers
2. Expand date range for bioRxiv (3 years instead of 2)
3. Search with alternative names (gene name, aliases, older nomenclature)
4. Search for the target family rather than the specific target
5. If still below threshold after retry, proceed with a LOW CONFIDENCE flag on the
   entire research report and inform the user

### Phase 4 gate failure (no HIGH confidence findings)

1. Add a prominent warning to the research report header
2. Proceed with MEDIUM confidence findings but flag all as "requires validation"
3. Recommend Preview tier only (not Standard or Production)
4. Suggest the user provide additional context or references

### Phase 6 gate failure (critical gaps found)

1. Return to Phase 3 with targeted queries addressing the specific gap
2. Maximum 2 retrieval iterations to avoid infinite loops
3. After 2 iterations, if gaps persist, document them in the Uncertainties section
4. Adjust design recommendation conservatively (lower tier, more scaffolds)

### Phase 8 gate failure (uncited claims)

1. Remove any claim that cannot be traced to sources.json
2. Demote confidence level for weakly cited claims
3. Add a "Data Limitations" note to the report
