---
description: Run full screening battery on a design
arguments:
  - name: design_id
    description: The design identifier or sequence to screen
    required: true
---

Run the complete screening battery on design `$ARGUMENTS`.

Use the by-screening MCP server to run:
1. PTM liability scan (deamidation, isomerization, oxidation, glycosylation, free Cys)
2. Net charge at pH 7.4
3. Developability assessment (CDR length, hydrophobic fraction, composition)
4. ipSAE scoring (if NPZ available)
5. Composite score with pass/fail verdict

Present results with:
- Per-category breakdown with severity levels
- Overall verdict (PASS/MARGINAL/FAIL)
- Specific recommendations for addressing any issues
- Comparison to quality thresholds from by-screening skill
