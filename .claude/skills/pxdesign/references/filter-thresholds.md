# PXDesign Filter Thresholds

PXDesign applies multiple validation filters during the design pipeline. Each
design is tested against these filters and the results are recorded as boolean
columns in `summary.csv`. Understanding these filters is essential for
interpreting results and deciding which designs to advance.

---

## Filter Summary

| Filter | Column in CSV | Confidence Thresholds | Geometry Threshold | Stringency |
|--------|--------------|----------------------|-------------------|------------|
| AF2-IG easy | `af2_easy_success` | ipAE < 10.85, ipTM > 0.5, pLDDT > 0.8 | RMSD < 3.5 A | Standard |
| AF2-IG strict | `af2_opt_success` | ipAE < 7.0, pLDDT > 0.9 | RMSD < 1.5 A | High |
| Protenix basic | `ptx_basic_success` | ipTM > 0.8, pTM > 0.8 | RMSD < 2.5 A | Standard |
| Protenix strict | `ptx_success` | ipTM > 0.85, pTM > 0.88 | RMSD < 2.5 A | High |

---

## AF2-IG Easy Filter

**Column**: `af2_easy_success`

**Purpose**: Broad initial screen using AlphaFold2 initial guess (AF2-IG)
predictions. Catches obviously poor designs while keeping borderline candidates
for further evaluation.

**Thresholds**:

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| ipAE | < 10.85 | Interface predicted aligned error below 10.85 Angstroms |
| ipTM | > 0.5 | Interface predicted TM-score above 0.5 |
| pLDDT | > 0.8 | Per-residue confidence above 80% |
| RMSD | < 3.5 A | Backbone RMSD between designed and predicted complex below 3.5 Angstroms |

**When to use**: As a first-pass filter. Designs failing AF2-IG easy are very
unlikely to be viable binders. Designs passing this filter warrant further
evaluation with Protenix filters.

---

## AF2-IG Strict Filter

**Column**: `af2_opt_success`

**Purpose**: Stringent AF2-based validation for high-confidence designs.
Requires tight structural agreement and high per-residue confidence.

**Thresholds**:

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| ipAE | < 7.0 | Very low interface error -- high confidence in contact geometry |
| pLDDT | > 0.9 | Excellent per-residue confidence (>90%) |
| RMSD | < 1.5 A | Near-perfect structural agreement with design model |

**When to use**: For selecting the highest-confidence designs. Passing AF2-IG
strict is a strong signal but not required -- many good binders pass easy but
not strict. Do not reject designs solely for failing strict if they pass basic
Protenix filters.

---

## Protenix Basic Filter

**Column**: `ptx_basic_success`

**Purpose**: Standard Protenix-based validation using the Protenix v1
structure predictor. More reliable than AF2-IG filters for novel binder
scaffolds because Protenix handles de novo designs better.

**Thresholds**:

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| ipTM | > 0.8 | Strong interface confidence from Protenix |
| pTM | > 0.8 | Strong global fold confidence |
| RMSD | < 2.5 A | Good structural agreement |

**When to use**: As the primary acceptance criterion for designs. Designs
passing Protenix basic are good candidates for experimental testing, especially
when combined with downstream screening (proteus-screening skill).

---

## Protenix Strict Filter

**Column**: `ptx_success`

**Purpose**: Highest-confidence Protenix validation. Designs passing this
filter have excellent predicted binding quality.

**Thresholds**:

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| ipTM | > 0.85 | Very strong interface prediction |
| pTM | > 0.88 | Very strong global fold prediction |
| RMSD | < 2.5 A | Good structural agreement |

**When to use**: For selecting top-tier candidates when you have many designs
to choose from. Prioritize `ptx_success=True` designs over those that only
pass `ptx_basic_success`.

---

## Interpreting Filter Results

### Decision Tree

```
Design passes ptx_success (Protenix strict)?
|
+-- YES --> Top-tier candidate. Advance to screening.
|
+-- NO --> Passes ptx_basic_success (Protenix basic)?
    |
    +-- YES --> Good candidate. Advance to screening with moderate confidence.
    |
    +-- NO --> Passes af2_easy_success (AF2-IG easy)?
        |
        +-- YES --> Marginal. Consider only if few other candidates available.
        |           Re-run with extended preset or more samples.
        |
        +-- NO --> Reject. Design is unlikely to fold or bind as intended.
```

### Common Patterns

| ptx_success | ptx_basic | af2_easy | af2_opt | Interpretation |
|-------------|-----------|----------|---------|----------------|
| True | True | True | True | Excellent -- all filters agree |
| True | True | True | False | Strong -- Protenix confident, AF2 strict is conservative |
| True | True | False | False | Good -- Protenix trusts it, AF2 does not. Trust Protenix for de novo binders |
| False | True | True | True | Solid -- basic Protenix but not strict. Still a viable candidate |
| False | True | True | False | Moderate -- passes basic filters only |
| False | False | True | False | Weak -- only passes easiest filter. Likely needs redesign |
| False | False | False | False | Reject -- no validation support |

### Protenix vs AF2 Disagreements

When Protenix and AF2 filters disagree, **trust Protenix** for de novo binder
designs. PXDesign uses Protenix internally, so its validation is more aligned
with the design model. AF2 may underperform on novel scaffolds that lack
homologs in its training data.

---

## Using Filters in Practice

1. **Sort by `ptx_iptm` descending** -- this is the primary ranking metric
2. **Filter by `ptx_basic_success=True`** as minimum acceptance
3. **Highlight `ptx_success=True`** designs as top candidates
4. **Note `af2_easy_success` and `af2_opt_success`** as supplementary evidence
5. **Run passing designs through proteus-screening** for liability and
   developability checks before final selection
