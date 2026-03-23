---
description: Show ranked design results
arguments:
  - name: run_id
    description: Optional run ID (uses latest if omitted)
    required: false
---

Display the ranked results table for the specified run (or the most recent run).

Show the full results table with columns:
- Rank, Design name, ipSAE, ipTM, pLDDT, RMSD, Liabilities, Status

Include:
- Summary statistics (total designs, pass rate, best scores)
- Quality tier breakdown (excellent/good/marginal/fail)
- Numbered next-step options

