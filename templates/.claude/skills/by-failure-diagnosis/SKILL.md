---
id: "skill_21cae38a6ba64f28a898ac1c9e2cecff"
name: "by-failure-diagnosis"
display-name: "BY Failure Diagnosis"
short-description: "Statistical post-mortem for low-yield design campaigns — runs Mann-Whitney U tests across continuous features (ipSAE, ipTM, pLDDT, RMSD, liabilities, CDR3 length, hydrophobic fraction, net charge) to identify which metrics most strongly discriminate PASS from FAIL. Use when a campaign pass rate drops below 20% and at least 30 designs have been scored."
category: "diagnosis"
keywords: "failure diagnosis, mann-whitney, statistical test, pass rate, discriminating features, threshold tuning, campaign post-mortem, effect size, BH correction, design feedback loop"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: ["mcp__by-screening__screen_diagnose_failures"]
---

# BY Failure Diagnosis Skill

Closing the design feedback loop requires understanding **why** designs fail, not just **that** they fail. This skill compares the distribution of every continuous feature between PASS and FAIL designs using non-parametric statistics, ranks features by discriminating power, and translates the result into concrete threshold or campaign-parameter changes for the next iteration.

It is the bridge between **screening** (which produces PASS/FAIL labels) and **campaign optimization** (which adjusts parameters for the next round).

---

## When to Use This Skill

Use this skill when:
- ✅ **Pass rate is below 20%** in a screening round and you need to know why before re-spending compute
- ✅ **At least 30 designs have been scored** with a `status` field (`PASS` or `FAIL`)
- ✅ **You have numeric features per design** (ipSAE, ipTM, pLDDT, RMSD, liabilities, net_charge, hydrophobic_fraction, cdr3_length)
- ✅ **User explicitly asks** "why are my designs failing?", "diagnose failures", "what's going wrong?"
- ✅ **Before the active-learning step** in a multi-round campaign (route diagnosis → optimizer)
- ✅ **After a screening regression** where pass rate dropped versus a prior round

Don't use this skill when:
- ❌ **Fewer than 30 designs total** — statistical power is too low; the test will be noisy. Score more designs first.
- ❌ **No FAIL designs (100% pass rate)** — there is nothing to compare against. Either tighten thresholds or move to lab submission.
- ❌ **No PASS designs (0% pass rate)** — there is nothing to compare against. Use **by-hypothesis-debate** to pick a new strategy before spending more compute.
- ❌ **You want to redesign individual residues** — that is per-design rationale, not population statistics. Use **by-epitope-analysis** instead.
- ❌ **You want to predict structures or score new designs** — use **protenix** or **by-scoring** instead.
- ❌ **The campaign has different scoring criteria across rounds** — comparing apples to oranges; run diagnosis within a single round only.

---

## Quick Start

The most common invocation: run the MCP tool against a campaign's screening output.

```python
import json

# Load campaign screening results (one dict per design)
with open("campaigns/<target>/<campaign_id>/screening_results.json") as fh:
    designs = json.load(fh)

# Call the MCP tool with the array serialized as JSON
result = mcp__by-screening__screen_diagnose_failures(
    scores_json=json.dumps(designs),
    pass_key="status",
    pass_value="PASS",
)

# Parse and present
diag = json.loads(result)
print(diag["formatted"])           # human-readable table
print(diag["recommendations"])     # top-3 actionable suggestions
```

✅ **VERIFICATION:** Expect output like `Failure Diagnosis (12/80 passed, 15% rate)` followed by a table sorted by p-value, with effect sizes and recommendations.

For ad-hoc CSV-based diagnosis (no MCP server required), use the included scripts:
```bash
python3 scripts/diagnose_from_csv.py --input designs.csv --status-col status
python3 scripts/plot_distributions.py --input designs.csv --output diagnostics.pdf --top-n 5
```

---

## Installation

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| Python | ≥3.10 | PSF | ✅ Permitted | system |
| scipy | ≥1.11 | BSD-3 | ✅ Permitted | `pip install scipy` |
| numpy | ≥1.24 | BSD-3 | ✅ Permitted | `pip install numpy` |
| pandas | ≥2.0 | BSD-3 | ✅ Permitted | `pip install pandas` |
| matplotlib | ≥3.7 | PSF-based | ✅ Permitted | `pip install matplotlib` (only for `plot_distributions.py`) |
| proteus_cli | bundled | proprietary | internal | included with BY |

**License Compliance:** All third-party packages permit commercial use in AI applications.

**System requirements:** No GPU needed. Diagnosis runs CPU-only in seconds for up to 10,000 designs. No internet required.

---

## Inputs

**Required:**
- **Designs array (or CSV)** with one row per design:
  - A status column (default name `status`) with values `PASS` or `FAIL` (uppercase)
  - At least one numeric feature column from this set: `ipsae`, `ipsae_min`, `iptm`, `plddt`, `rmsd`, `net_charge`, `hydrophobic_fraction`, `liabilities`, `cdr3_length`
  - Minimum 3 designs in each of PASS and FAIL groups (statistical floor)
  - Recommended minimum 30 designs total (≥10 in each group) for usable power

**Alternative inputs:**
- **JSON array** (one object per design) — pass as `scores_json` to the MCP tool
- **pandas DataFrame** — convert to records with `df.to_dict(orient="records")` before passing
- **CSV file** — use `scripts/diagnose_from_csv.py` directly

**Optional:**
- **`pass_key`** — column name for status (default `status`)
- **`pass_value`** — value indicating PASS (default `PASS`)
- **Extra feature columns** — the MCP tool only tests the canonical 9 features; custom features require the CSV script (see `scripts/diagnose_from_csv.py --help`)

See [references/failure-patterns.md](references/failure-patterns.md) for which features matter for which failure modes.

---

## Outputs

**Primary results (JSON object from MCP tool):**
- `total_designs`, `passed`, `failed`, `pass_rate` — campaign-level counts
- `discriminating_features[]` — sorted by p-value ascending, each entry has:
  - `feature_name`, `test_type` (`mann_whitney`), `statistic`, `p_value`, `effect_size`
  - `passed_mean`, `failed_mean` — group means
  - `interpretation` — one-line natural language summary
- `summary` — short headline string
- `recommendations[]` — up to 3 actionable threshold/parameter suggestions
- `formatted` — human-readable text table

**Visualizations (from `plot_distributions.py`):**
- `diagnostics.pdf` — single multi-panel PDF with violin plots of PASS vs FAIL for each significant feature (300 DPI)

**Reports (from `diagnose_from_csv.py`):**
- stdout — formatted markdown-style table sorted by p-value, with BH-corrected q-values

**Analysis objects:**
- The MCP tool returns a JSON string; persist it as `campaigns/<target>/<campaign_id>/diagnosis.json` for downstream consumption by **by-campaign-optimizer** and **by-knowledge**.

---

## Clarification Questions

⚠️ **CRITICAL:** Always ask question #1 first to confirm input data exists.

1. **Input data (ASK THIS FIRST):**
   - Do you have a CSV, JSON file, or campaign directory with per-design scores plus a PASS/FAIL status column?
   - If no — run **by-screening** first to produce labels.

2. **Group sizes:**
   - How many designs are in PASS vs FAIL? If either is below 3, diagnosis cannot run. If either is below 10, results will be noisy.

3. **Status column convention:**
   - Is the column named `status`? Are values `PASS`/`FAIL` (uppercase)? If different, override with `pass_key` and `pass_value`.

4. **Features available:**
   - Which of the canonical 9 features are present? Diagnosis silently skips missing or all-null columns. Confirm at least 2 are present.

5. **Round scope:**
   - Is this a single screening round, or are you mixing rounds with different thresholds? Mixing rounds invalidates the test. Filter to one round first.

6. **Downstream intent:**
   - Will you adjust screening thresholds, change campaign parameters (scaffolds, hotspots), or both? This affects which recommendations to surface in the report.

7. **Primary objective:**
   - Are you trying to (a) understand the failure mode, (b) tune thresholds for the same model, or (c) decide whether to switch strategy entirely? See [references/threshold-tuning.md](references/threshold-tuning.md) for mapping diagnosis output to each action.

For detailed clarification flow when working with a campaign directory, read `references/failure-patterns.md`.

---

## Standard Workflow

🚨 **MANDATORY: USE THE MCP TOOL OR PROVIDED SCRIPTS - DO NOT WRITE INLINE STATISTICS** 🚨

This skill enforces a single statistical methodology (Mann-Whitney U with Benjamini-Hochberg correction). Re-implementing the test inline risks silent statistical errors (wrong tails, missing tie correction, no multiple-testing adjustment).

### Step 1: Collect designs and confirm group sizes

Load the campaign's screening output. Confirm at least 3 designs in each of PASS and FAIL.

```python
import json
designs = json.load(open("campaigns/<target>/<id>/screening_results.json"))
passed = sum(1 for d in designs if d.get("status") == "PASS")
failed = len(designs) - passed
assert passed >= 3 and failed >= 3, "Need ≥3 in each group"
```

✅ **VERIFICATION:** Print counts: `PASS=12, FAIL=68 (total=80, rate=15.0%)`. If pass rate ≥ 20%, ask the user whether diagnosis is still desired.

### Step 2: Call the MCP tool

```python
result_str = mcp__by-screening__screen_diagnose_failures(
    scores_json=json.dumps(designs),
    pass_key="status",
    pass_value="PASS",
)
diag = json.loads(result_str)
```

✅ **VERIFICATION:** `diag["summary"]` is a non-empty string. `diag["discriminating_features"]` is a list of length ≥ 0.

### Step 3: Interpret the table

Sort already done by the tool (ascending p-value). Apply the interpretation cheat-sheet:

| Effect size | Strength | Action |
|-------------|----------|--------|
| > 1.0 | **Strong** discriminator | Tighten threshold for this feature first |
| 0.5 – 1.0 | **Moderate** discriminator | Worth adjusting, but combine with other features |
| 0.2 – 0.5 | **Weak** discriminator | Only useful as a tie-breaker |
| < 0.2 | Effectively noise | Ignore even if p < 0.05 |

**p-value caveats:** With 9 features tested, expect ~0.45 false positives at α=0.05. Always check the BH-corrected q-values from `scripts/diagnose_from_csv.py` before declaring a feature significant. See [references/mann-whitney-guide.md](references/mann-whitney-guide.md) for the full math.

### Step 4: Plot distributions (optional but recommended)

For any feature with p < 0.05 and effect size > 0.5, plot the PASS vs FAIL distribution:

```bash
python3 scripts/plot_distributions.py \
    --input campaigns/<target>/<id>/screening_results.csv \
    --output campaigns/<target>/<id>/diagnostics.pdf \
    --top-n 5 \
    --status-col status
```

✅ **VERIFICATION:** `diagnostics.pdf` exists; each panel shows two violins (PASS, FAIL) with median lines.

### Step 5: Translate to action

Match the diagnosis pattern against [references/threshold-tuning.md](references/threshold-tuning.md). Common moves:
- Single feature dominates (e.g., `ipsae` effect > 1.5, others < 0.5) → raise that feature's threshold
- Multiple features moderately correlated (CDR3 length + hydrophobic fraction) → re-run BoltzGen with constrained CDR3 length
- No significant features but low pass rate → the failure mode is not in your feature set; expand features or change strategy

### Step 6: Persist and route

Write `diagnosis.json` to the campaign directory. Hand off to **by-campaign-optimizer** with the diagnosis as input. Append the diagnosis summary to **by-knowledge** for cross-campaign learning.

```python
with open("campaigns/<target>/<id>/diagnosis.json", "w") as fh:
    json.dump(diag, fh, indent=2)
```

⚠️ **CRITICAL - DO NOT:**
- ❌ Run the test with mixed rounds → STOP: filter to one round first
- ❌ Use a t-test instead of Mann-Whitney → screening features are non-normal
- ❌ Trust a single feature with p < 0.05 but effect size < 0.3 → almost certainly a false positive
- ❌ Skip the BH correction when reporting > 1 feature → inflated false-positive rate

---

## When Scripts Fail

Use the standard escalation hierarchy:

1. **Fix and Retry (90%)** — Most failures are missing scipy or numpy. Run `pip install scipy numpy pandas matplotlib`.
2. **Modify Script (5%)** — If your designs have custom feature columns not in the canonical 9, edit `scripts/diagnose_from_csv.py` to add them to the `FEATURES` list.
3. **Use as Reference (4%)** — Read `scripts/diagnose_from_csv.py` to adapt the Mann-Whitney + BH pattern for a one-off analysis.
4. **Write from Scratch (1%)** — Only if you need a different statistical framework (e.g., logistic regression, decision tree). Document why in a phase note.

| Failure | Triage |
|---------|--------|
| `ImportError: scipy` | Step 1 → `pip install scipy` |
| `ValueError: All values identical` | Feature is constant within PASS or FAIL — script skips automatically, no action |
| `KeyError: 'status'` | Step 2 → pass `--status-col` matching your column |
| `Empty diagnosis returned` | Group too small — collect more designs and retry |
| `All p-values are 1.0` | All features identical in PASS vs FAIL — your features don't discriminate, expand them |

---

## Decision Points

### Threshold tuning vs strategy change

**When:** After diagnosis returns
**Options:**
- **Tighten thresholds** — if the top feature has effect size > 1.0 and aligns with a knob you control
- **Constrain design parameters** — if CDR3 length or hydrophobicity dominates (set `--cdr3-len-range`, hotspot bias)
- **Change strategy entirely** — if no feature has effect size > 0.5 AND pass rate < 10%

See [references/threshold-tuning.md](references/threshold-tuning.md#decision-tree) for the full decision tree.

### When to escalate to hypothesis-debate

If diagnosis returns no discriminating features AND pass rate is below 10%, the failure mode is outside your feature set. Invoke **by-hypothesis-debate** to pick a new strategy (different scaffold family, different epitope, different modality) before spending more compute.

---

## Common Issues

| Issue | Possible Cause | Solution | Details |
|-------|----------------|----------|---------|
| `Cannot diagnose: need both passed and failed designs` | All designs PASS or all FAIL | Tighten/loosen thresholds in by-screening to produce a mixed cohort | [failure-patterns.md](references/failure-patterns.md#cohort-balance) |
| `Sample size too small` warning | < 30 total designs | Score more designs first; aim for ≥ 50 | [mann-whitney-guide.md](references/mann-whitney-guide.md#power) |
| Top feature has p < 0.05 but effect size 0.2 | False positive amplified by large n | Apply BH correction; ignore unless effect size > 0.5 | [mann-whitney-guide.md](references/mann-whitney-guide.md#effect-size) |
| All p-values ~ 1.0 | Features are not informative for this failure mode | Add new features (shape complementarity, paratope SASA) | [failure-patterns.md](references/failure-patterns.md#missing-features) |
| `ipsae` discriminates but threshold change has no effect next round | Threshold was already at floor of distribution | Switch from threshold tuning to design parameter change | [threshold-tuning.md](references/threshold-tuning.md#stuck-thresholds) |
| Recommendations seem contradictory (raise A, lower B) | Features are negatively correlated within failures | Pick one — usually the one with higher effect size | [threshold-tuning.md](references/threshold-tuning.md#correlated-features) |
| `cdr3_length` is top feature but is an integer | Mann-Whitney handles ordinals; small distinct values inflate ties | Result is valid but consider chi-squared as a cross-check | [mann-whitney-guide.md](references/mann-whitney-guide.md#ties) |
| Output JSON has `"discriminating_features": []` | None met `p < 0.05` threshold | Either no signal, or sample size too small | [mann-whitney-guide.md](references/mann-whitney-guide.md#null-result) |
| `ImportError: scipy` from MCP tool | scipy not installed in MCP server env | `pip install scipy` in the by-screening server's env | [mann-whitney-guide.md](references/mann-whitney-guide.md#dependencies) |
| Diagnosis disagrees with visual inspection | Visual inspection is per-design; diagnosis is per-population | Both can be right — use diagnosis for thresholds, visual for individual designs | [failure-patterns.md](references/failure-patterns.md#population-vs-individual) |
| Pass rate is 25% but user wants diagnosis anyway | Just above the 20% trigger | Run it — the trigger is a guideline, not a hard rule | n/a |
| Diagnosis flags `liabilities` as significant but all FAIL | All FAIL designs have liabilities, all PASS don't | Move liability scan earlier in the screening cascade | [threshold-tuning.md](references/threshold-tuning.md#order-of-operations) |

---

## Best Practices

1. 🚨 **CRITICAL:** Always run diagnosis **per round**, never across rounds with different thresholds.
2. 🚨 **CRITICAL:** Apply BH (Benjamini-Hochberg) correction when reporting > 1 feature as significant.
3. ✅ **REQUIRED:** Verify group sizes ≥ 3 before calling the tool.
4. ✅ Prefer effect size over p-value when ranking actionable features (effect > 0.5 matters more than p < 0.001).
5. ✅ Cross-check the top feature with `scripts/plot_distributions.py` — a feature with strong overlap in violins is rarely actionable even with low p.
6. ✅ Persist `diagnosis.json` to the campaign directory before moving on. Downstream optimizer reads it.
7. ✅ Surface the recommendations in the user-facing summary; users care about "what to change", not raw statistics.
8. ❌ Do NOT report a single significant feature without showing effect size.
9. ❌ Do NOT extrapolate diagnosis from one target to another — diagnoses are target-specific.
10. ✨ **Optional:** After 2-3 rounds, aggregate diagnoses across rounds and look for stable signals — those are reliable design-space constraints.

---

## Suggested Next Steps

After running diagnosis, route to one of:

1. **by-campaign-optimizer** — apply the recommendations as parameter updates in the next active-learning round. This is the default downstream skill; diagnosis output is directly consumed by the optimizer's policy.

2. **by-threshold-tuner** — re-run by-screening with the recommended thresholds from `diagnosis.json["recommendations"]` to confirm pass rate improves on the existing cohort before committing more compute.

3. **by-hypothesis-debate** — invoke when diagnosis finds **no** discriminating features and pass rate is < 10%. The failure mode is outside your feature set; pick a new strategy.

4. **by-knowledge** — write the diagnosis summary into the project knowledge graph so future campaigns on related targets benefit from the learning.

5. **by-epitope-analysis** — invoke when diagnosis flags `hydrophobic_fraction` or `net_charge` as dominant. The cause is likely an unsuitable epitope; reconsider hotspots.

Chaining rationale: diagnosis converts opaque "low pass rate" into concrete, statistically grounded constraints. Each downstream skill takes those constraints as inputs, keeping the campaign feedback loop fully data-driven.

---

## Related Skills

**Upstream (run before):**
- **by-screening** — produces the PASS/FAIL labels and feature columns that diagnosis consumes
- **by-scoring** — produces the per-design metrics (ipSAE, ipTM, pLDDT) that feed into screening

**Downstream (run after):**
- **by-campaign-optimizer** — applies diagnosis recommendations as parameter updates
- **by-threshold-tuner** — adjusts screening thresholds based on diagnosis
- **by-knowledge** — persists diagnosis findings to project memory

**Alternative / Complementary:**
- **by-failure-modes-catalog** — qualitative catalog of known failure modes (complement to this quantitative skill)
- **by-pareto** — multi-objective frontier analysis (use alongside when trade-offs are present)
- **by-hypothesis-debate** — when no statistical signal exists in your features

---

## References

**Detailed documentation:**
- [references/mann-whitney-guide.md](references/mann-whitney-guide.md) — Hypothesis-test math, effect sizes (Cohen's d analog), p-value interpretation, BH correction, when the test is invalid
- [references/failure-patterns.md](references/failure-patterns.md) — Catalog of common protein-design failure modes (low ipSAE cluster, CDR liability spike, hydrophobic patch bias, charge skew, doublet artifacts) with telltale signatures
- [references/threshold-tuning.md](references/threshold-tuning.md) — Pattern → action table for translating diagnosis results into next-round parameters

**Scripts:**
- `scripts/diagnose_from_csv.py` — CLI: read CSV, run Mann-Whitney per feature with BH correction, print sorted table + top-3 recommendations
- `scripts/plot_distributions.py` — CLI: read CSV, produce multi-panel violin plot PDF of PASS vs FAIL distributions for top-N features

**MCP tool:**
- `mcp__by-screening__screen_diagnose_failures` — production interface (Mann-Whitney U over canonical features, with auto-generated recommendations)

**Official documentation:**
- [scipy.stats.mannwhitneyu](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)
- [Benjamini-Hochberg FDR control](https://www.jstor.org/stable/2346101)

**Key Papers:**
- [Mann & Whitney 1947 — On a test of whether one of two random variables is stochastically larger than the other](https://doi.org/10.1214/aoms/1177730491)
- [Benjamini & Hochberg 1995 — Controlling the false discovery rate: a practical and powerful approach to multiple testing](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)
- [Sullivan & Feinn 2012 — Using effect size — or why the P value is not enough](https://doi.org/10.4300/JGME-D-12-00156.1)

**License:** All third-party packages used by this skill (scipy, numpy, pandas, matplotlib) permit commercial use in AI applications.
