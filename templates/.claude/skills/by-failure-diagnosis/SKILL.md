# Failure Diagnosis Skill

## When to Trigger
Activate this skill when a design campaign's screening pass rate drops below 20%, or when the user asks "why are my designs failing?" / "diagnose failures".

## What It Does
Runs Mann-Whitney U tests comparing passed vs failed designs across continuous metrics (ipSAE, ipTM, pLDDT, RMSD, liabilities, net charge, hydrophobic fraction, CDR3 length) to identify which features most strongly discriminate between successful and unsuccessful designs.

## How to Use
1. Collect all design score dicts from the campaign (each must have a status field and numeric feature columns).
2. Call the `screen_diagnose_failures` MCP tool with the scores as a JSON array.
3. Review the output: features are sorted by p-value; those with p < 0.05 are statistically significant discriminators.
4. Follow the recommendations to adjust thresholds or design parameters for the next round.

## Interpreting Results
- **Effect size > 1.0**: Strong discriminator -- this feature reliably separates passes from failures.
- **Effect size 0.5-1.0**: Moderate discriminator -- worth adjusting thresholds.
- **Effect size < 0.5**: Weak discriminator -- unlikely to help on its own.
- **Recommendations** are generated for the top 3 significant features and suggest concrete threshold or parameter changes.

## Python API
```python
from proteus_cli.screening.diagnosis import diagnose_failures, format_diagnosis

diag = diagnose_failures(design_dicts, pass_key="status", pass_value="PASS")
print(format_diagnosis(diag))
```
