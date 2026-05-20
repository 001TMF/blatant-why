# Mann-Whitney U Test Guide for Failure Diagnosis

A practical reference for the statistical machinery underneath the `screen_diagnose_failures` tool. Use this when you need to interpret edge cases, justify the methodology to a reviewer, or decide whether a different test is more appropriate.

---

## Why Mann-Whitney U (and not a t-test)

Screening features (ipSAE, ipTM, pLDDT, RMSD, liability count, CDR3 length) are **not normally distributed**. They have:

- Hard floors and ceilings (ipSAE ∈ [0, 1], pLDDT ∈ [0, 100])
- Heavy right or left tails depending on the metric
- Integer-valued or zero-inflated distributions (liability count, CDR3 length)

The two-sample t-test assumes both groups are approximately normal and have similar variances. Neither holds. Using a t-test on these features inflates Type I error (false positives) when distributions are skewed and inflates Type II error (false negatives) when there are outliers in one group.

The Mann-Whitney U test (a.k.a. Wilcoxon rank-sum test) compares **ranks** instead of values. It only requires that both samples come from continuous (or ordinal) distributions and that observations are independent. It is the standard non-parametric alternative.

---

## What the test actually computes

Given two samples (PASS values, FAIL values):

1. Pool all values and assign ranks (ties get average ranks).
2. Sum the ranks in the PASS group → R_pass.
3. Compute U_pass = R_pass − n_pass(n_pass + 1)/2.
4. By symmetry, U_fail = n_pass · n_fail − U_pass.
5. The test statistic is U = min(U_pass, U_fail).
6. Under H₀ (no difference in distributions), U is approximately normal for n ≥ 8 in each group. Convert to a z-score and look up a two-sided p-value.

`scipy.stats.mannwhitneyu(p_vals, f_vals, alternative="two-sided")` returns U and p.

**What the null hypothesis actually says:** "The probability that a random PASS value exceeds a random FAIL value equals 0.5." Rejecting H₀ means PASS designs tend to have higher (or lower) values, not that the means differ. For roughly symmetric distributions the two are equivalent; for heavy-tailed ones they diverge.

---

## Effect size

A p-value tells you whether the difference is statistically real; an effect size tells you whether it is **practically important**. With large samples (n > 1000), tiny irrelevant differences can produce p < 0.001.

This skill reports a **Cohen's d analog** computed in `proteus_cli.screening.diagnosis`:

```
effect_size = |mean(PASS) − mean(FAIL)| / std(all values)
```

This is a rough but interpretable proxy:

| Effect size | Cohen's interpretation | Practical action |
|-------------|------------------------|------------------|
| < 0.2 | Negligible | Ignore even if p < 0.05 |
| 0.2 – 0.5 | Small | Useful only as tie-breaker |
| 0.5 – 0.8 | Medium | Worth adjusting |
| > 0.8 | Large | Primary threshold target |
| > 1.5 | Very large | Cohort is bimodal — investigate |

For pure rank-based effect size, also consider the **rank-biserial correlation**:
```
r = 1 − 2U / (n_pass · n_fail)
```
where U is the smaller of U_pass, U_fail. Values close to ±1 indicate perfect separation; ~0 indicates no separation.

---

## P-value interpretation and multiple-testing correction

The skill tests up to 9 features in a single diagnosis call. With α = 0.05 per test, the family-wise false-positive rate is:

```
1 − (1 − 0.05)^9 ≈ 0.37
```

That means a ~37% chance at least one feature looks significant by chance even if none truly differ. **This is unacceptable** when you are about to spend GPU hours on a re-run.

**Solution: Benjamini-Hochberg (BH) correction.** Sort p-values ascending, then for each rank i (1-indexed):

```
q_i = p_i · m / i    where m = number of tests
```

Apply monotonic adjustment (q_i ≤ q_{i+1}). Report q-values alongside raw p-values. Consider a feature significant only if q < 0.05 (or q < 0.10 for exploratory work).

`scripts/diagnose_from_csv.py` applies BH automatically. The MCP tool does NOT apply BH — interpret its raw p-values with care when multiple features are flagged.

---

## When the test is invalid

Mann-Whitney U breaks down in the following cases:

1. **Group size < 3** — the test cannot compute a meaningful statistic. Skill skips these features.
2. **All values identical within a group** — variance is zero, ranks are degenerate. scipy raises `ValueError`; the skill catches it and skips.
3. **Massive tie-fraction** (e.g., liability count where 80% of designs have 0) — the normal approximation breaks; use `method="exact"` for small samples or use chi-squared on a binarized version.
4. **Non-independent observations** — if multiple designs share the same template (siblings from one diffusion seed), they are not independent. This usually does NOT invalidate the test for population-level inference but means within-cluster variance is underestimated.
5. **Mixed cohorts** (e.g., round 1 and round 2 thresholds differ) — the PASS/FAIL labels mean different things; the test answers a meaningless question. Filter to one round.

See [failure-patterns.md](failure-patterns.md) for failure modes that produce these edge cases.

---

## Power (sample size needed to detect an effect)

Rough power table for two-sided test at α = 0.05, 80% power:

| Effect size (Cohen's d analog) | Minimum n per group | Minimum total designs |
|-------------------------------|---------------------|-----------------------|
| 0.8 (large) | ~15 | 30 |
| 0.5 (medium) | ~30 | 60 |
| 0.3 (small) | ~85 | 170 |
| 0.2 (negligible) | ~190 | 380 |

In practice: **30 designs is a floor, 100+ is comfortable, 500+ detects subtle effects.** Below 30, expect noise.

---

## Ties

When values repeat across groups (common for `cdr3_length`, `liabilities`), ranks are averaged. scipy applies a tie correction to the U statistic variance, but extreme tie fractions still distort results.

If more than 50% of observations are tied at a single value, consider:
- Treating the feature as categorical (chi-squared on PASS rate by bucket)
- Binarizing (e.g., `liabilities == 0` vs `liabilities > 0`) and using Fisher's exact test

The skill currently does NOT auto-detect tie-heavy features. If you suspect a feature is tie-dominated, eyeball the distribution with `plot_distributions.py` first.

---

## Null result handling

If diagnosis returns no features with q < 0.05:

1. **Check sample size first.** With n < 30, a null result is uninformative.
2. **Check feature coverage.** If only 1-2 features had enough non-null values, you are under-powered.
3. **Check distributions visually.** Maybe a feature is bimodal and the test misses it (Mann-Whitney compares stochastic dominance, not multimodality).
4. **Consider feature engineering.** Add shape complementarity, paratope SASA, hydrophobic moment, or other features outside the canonical set.
5. **Consider strategy change.** If the failure mode is not in any continuous feature, the cause may be categorical (wrong scaffold family, wrong epitope) — escalate to **by-hypothesis-debate**.

---

## Dependencies

The MCP tool imports `scipy.stats.mannwhitneyu` and `numpy`. If these are missing from the by-screening server's Python environment, the tool returns a summary string explaining the install command (`pip install scipy numpy`).

The standalone scripts also use `pandas` for CSV I/O and `matplotlib` for plotting. Install with:
```bash
pip install scipy numpy pandas matplotlib
```

All packages are BSD or PSF licensed and permit commercial use.

---

## Validation references

- [scipy mannwhitneyu docs](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)
- Conover, W.J. (1999) *Practical Nonparametric Statistics*, 3rd ed., Wiley — chapter 5 covers the rank-sum test in detail
- Sullivan & Feinn 2012, "Using effect size — or why the P value is not enough" — explains why effect size belongs in every report
