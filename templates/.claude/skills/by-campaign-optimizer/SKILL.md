---
id: "skill_6cd1e0f4c6864ff89ff64d873441900f"
name: "by-campaign-optimizer"
display-name: "BY Campaign Optimizer (Active Learning)"
short-description: "Trains a Random Forest on scored designs from prior rounds and proposes parameter adjustments for the next round. Use when a multi-round campaign has at least 10 scored designs and you need data-driven suggestions for thresholds, design counts, and feature targets."
category: "optimization"
keywords: "active learning, random forest, optimizer, campaign, multi-round, parameter tuning, feature importance, acquisition function, scikit-learn"
version: "1.0"
last-updated: "2026-05-20"
---

# BY Campaign Optimizer (Active Learning)

Multi-round design campaigns generate scored designs at every iteration. This skill
turns that scoring history into actionable parameter changes for the next round —
training a lightweight Random Forest on the designs you already have, ranking which
features actually discriminate good from bad, and proposing thresholds and design
counts that target the most promising regions of feature space.

The optimizer is the **iteration loop**: it runs *after* the diagnosis step
(`by-failure-diagnosis`) has identified which features matter, and decides what
parameters to push or relax for the next round. Diagnosis answers "what went
wrong?"; this skill answers "what should we try next?".

---

## When to Use This Skill

✅ **Use this skill when:**
- A design round has completed and scores are written to `*_scores.json` files
- The campaign has **≥10 scored designs total** across all rounds
- You are deciding how to configure the next round of a multi-round campaign
- `by-failure-diagnosis` has identified discriminating features and you need
  concrete threshold values
- You want a feature-importance ranking to decide what to optimize for
- The user asks "what should I change for the next round?" or "tune my campaign"

❌ **Do NOT use this skill when:**
- The campaign has fewer than 10 scored designs → use rule-based defaults from
  `by-campaign-manager` instead
- This is the first round (no prior scores exist) → use `by-research` and
  `by-design-workflow` to set initial parameters
- Designs are failing for non-statistical reasons (e.g., compute errors, bad
  target structure) → run `by-failure-diagnosis` first to confirm the signal
  is real
- The campaign is a single-shot screen with no planned iterations
- You only need a "why did designs fail?" report → use `by-failure-diagnosis`
  (the diagnostic counterpart to this optimizer)

---

## Quick Start

```python
from proteus_cli.campaign.active_learning import (
    has_enough_data,
    suggest_from_campaign,
)

campaign_dir = "campaigns/tnfa/campaign_20260520_001"

if has_enough_data(campaign_dir):
    result = suggest_from_campaign(campaign_dir)
    print(f"Source: {result.source}")                  # "active_learning"
    print(f"Confidence: {result.confidence}")          # "high" if >30 designs
    print(f"Top feature: {result.feature_importances[0]}")
    print(f"Recommendations: {result.recommended_parameters}")
```

Or via the CLI scripts shipped with this skill:

```bash
# Step 1: train RF, write optimizer_output.json
python scripts/optimize_from_csv.py \
    --scores campaign/round_1/scores.csv \
    --output campaign/round_1/optimizer_output.json

# Step 2: write next-round YAML config
python scripts/propose_next_round.py \
    --optimizer-output campaign/round_1/optimizer_output.json \
    --previous-config campaign/round_1/config.yaml \
    --output campaign/round_2/config.yaml
```

---

## Installation

| Package | Version | License | Commercial Use | Install |
|---------|---------|---------|----------------|---------|
| scikit-learn | ≥1.3 | BSD-3-Clause | ✅ Permitted | `pip install scikit-learn` |
| pandas | ≥2.0 | BSD-3-Clause | ✅ Permitted | `pip install pandas` |
| numpy | ≥1.24 | BSD-3-Clause | ✅ Permitted | `pip install numpy` |
| PyYAML | ≥6.0 | MIT | ✅ Permitted | `pip install pyyaml` |

Or install the ML extras bundle:

```bash
pip install by-agent[ml]
```

**License Compliance:** All packages permit commercial use in AI applications.

---

## Inputs

**Required:**
- **Scored designs**: either
  - A campaign directory containing `*_scores.json` files (Python API), or
  - A flat CSV with one row per design (CLI scripts)
- Each scored design must contain numeric values for some subset of:
  `ipsae` (or `ipsae_min`), `iptm`, `plddt`, `rmsd`, `liabilities`,
  `cdr3_length`, `net_charge`, `hydrophobic_fraction`
- A `status` column (`PASS` / `FAIL`) is optional but improves recommendations

**Optional:**
- `min_designs` (default 10) — the active-learning threshold
- A previous-round YAML config to use as a template for the next round
- A target feature to optimize (defaults to `ipsae`)

See [references/active-learning.md](references/active-learning.md) for sample-size
guidance and [references/random-forest-approach.md](references/random-forest-approach.md)
for feature-engineering details.

---

## Outputs

**Primary results:**
- `optimizer_output.json` — feature importances, recommended thresholds,
  exploration regions, confidence level, and a human-readable explanation
- `OptimizationResult` dataclass (Python API) with the same content

**Next-round config:**
- `config_round_N+1.yaml` — design parameters with adjusted thresholds,
  updated `num_designs`, and feature targets carried over from the optimizer

**Diagnostic fields in `optimizer_output.json`:**
- `source` — `"active_learning"` if RF trained, `"rule_based"` if fallback
- `confidence` — `"low"` / `"medium"` / `"high"` based on training-set size
- `feature_importances` — sorted list of `(feature, importance)` tuples
- `recommended_parameters` — concrete values for the next round
- `exploration_regions` — feature-space regions to sample more densely
- `warnings` — any files skipped or features dropped

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST.** Always confirm the user has at least 10 scored
designs before running the optimizer. Below the threshold, the RF will not train
and you should route to rule-based defaults instead.

1. **Scored data available?** *(ASK THIS FIRST)*
   How many scored designs exist in the campaign? Where are the `*_scores.json`
   files (or the scores CSV)? If fewer than 10, stop and use rule-based defaults.

2. **Target metric to optimize.**
   ipSAE is the default. Should we optimize for composite score, ipTM, or a
   custom weighted target? Different targets produce different recommendations.

3. **Pass/fail labels.**
   Does the data include a `status` column with `PASS`/`FAIL` labels, or only
   continuous scores? With labels, the optimizer can suggest thresholds that
   match the empirical pass boundary.

4. **Has diagnosis been run?**
   If `by-failure-diagnosis` flagged a feature as a strong discriminator,
   prioritize that feature when interpreting RF importances.

5. **Compute and design-count budget for next round.**
   How many designs is the user willing to run? The optimizer can suggest
   `increase_num_designs` if the search space is under-sampled.

6. **Diversity vs exploitation.**
   Should the next round exploit the top-quartile region (narrow thresholds) or
   explore widely (lower thresholds, higher diversity weight)? See
   [references/active-learning.md#acquisition-functions](references/active-learning.md#acquisition-functions).

7. **Round number.**
   Which round number is being planned? The optimizer keeps a history file so
   later rounds can compare improvement trajectories.

---

## Standard Workflow

🚨 **MANDATORY: USE THE SHIPPED SCRIPTS — DO NOT REIMPLEMENT THE RF INLINE.** 🚨

1. **Confirm data sufficiency.**
   ```python
   from proteus_cli.campaign.active_learning import has_enough_data
   assert has_enough_data(campaign_dir, min_designs=10)
   ```
   ✅ **VERIFICATION:** `True` printed. If `False`, stop and use rule-based defaults.

2. **(Optional) Run diagnosis first.**
   If the previous-round pass rate is below 20%, invoke `by-failure-diagnosis`
   to identify discriminating features. Use those features as priors when
   interpreting the optimizer's importance ranking.

3. **Train RF and write optimizer output.**
   ```bash
   python scripts/optimize_from_csv.py \
       --scores campaign/round_N/scores.csv \
       --target ipsae \
       --output campaign/round_N/optimizer_output.json
   ```
   ✅ **VERIFICATION:** `✓ Optimizer completed: N designs, top feature: <feat>`

4. **Inspect feature importances.**
   Read `optimizer_output.json`. The top feature drives the most variance in
   ipSAE; the recommended thresholds are derived from the top-quartile mean.

5. **Propose next-round config.**
   ```bash
   python scripts/propose_next_round.py \
       --optimizer-output campaign/round_N/optimizer_output.json \
       --previous-config campaign/round_N/config.yaml \
       --output campaign/round_N+1/config.yaml
   ```
   ✅ **VERIFICATION:** `✓ Next-round config written: <path>`

6. **Review the diff.**
   Compare the new config to the previous one. Surface every parameter change
   to the user before launching the next round.

7. **Launch next round.**
   Hand off to `by-design-workflow` with the new config. The optimizer does
   not submit jobs.

❌ **DON'T:**
- ❌ Skip step 1 — running RF on <10 designs returns garbage importances
- ❌ Discard the optimizer's `warnings` list — it flags skipped files and dropped features
- ❌ Apply recommendations blindly when `confidence` is `"low"` — review with the user first

---

## When Scripts Fail

Follow the standard Script Failure Hierarchy:

1. **Fix and retry (90%)** — Install scikit-learn / pyyaml; re-run.
2. **Modify the script (5%)** — Adjust `--target` or feature list if your
   campaign uses non-standard metric names.
3. **Use as reference (4%)** — Read `optimize_from_csv.py` and adapt the
   training loop if you need a different model class.
4. **Write from scratch (1%)** — Only if the campaign requires a
   fundamentally different optimizer (e.g., Bayesian optimization with a
   Gaussian process).

For active-learning theory, see [references/active-learning.md](references/active-learning.md).
For RF hyperparameter rationale, see [references/random-forest-approach.md](references/random-forest-approach.md).

---

## Decision Points

| Decision | Options | Guidance |
|---|---|---|
| Acquisition function | Greedy exploit / uncertainty / expected improvement | Greedy when ≥30 designs; uncertainty when 10–30 |
| Threshold adjustment | Tighten / hold / loosen | Tighten if pass rate ≥40%; loosen if <20% |
| Design count | Hold / increase / decrease | Increase if `recommended_parameters.increase_num_designs` is `True` |
| Confidence floor | Accept low / medium / high only | Require ≥medium before propagating to config |

See [references/active-learning.md#acquisition-functions](references/active-learning.md#acquisition-functions)
for the full decision tree.

---

## Common Issues

| Issue | Cause | Solution | Details |
|---|---|---|---|
| `source: rule_based` returned unexpectedly | <10 scored designs OR scikit-learn missing | Check `has_enough_data`; `pip install scikit-learn` | [active-learning.md](references/active-learning.md) |
| All importances near 0 | All designs have similar scores (low variance) | Run more diverse designs first; lower thresholds | [random-forest-approach.md](references/random-forest-approach.md) |
| Recommended threshold = 0 | Feature missing from most scores | Backfill scores with `by-screening` | [active-learning.md](references/active-learning.md) |
| RF predicts same ipSAE for every input | `max_depth=5` too shallow for noisy data | Edit `optimize_from_csv.py` to raise `max_depth` to 10 | [random-forest-approach.md](references/random-forest-approach.md#hyperparameters) |
| `cdr3_length` dominates importance | Class imbalance in CDR3 lengths | Stratify training or drop the feature | [random-forest-approach.md](references/random-forest-approach.md#feature-leakage) |
| `optimizer_output.json` missing `exploration_regions` | All top-quartile designs cluster tightly | Increase round size; reduce greedy exploitation | [active-learning.md](references/active-learning.md#exploration-vs-exploitation) |
| `files_skipped` > 0 in result | Malformed JSON in `*_scores.json` | Open the offending files; fix or remove | — |
| Suggested `min_ipsae` lower than previous round | Top-quartile mean drifted down | Investigate degradation before applying; rerun diagnosis | [active-learning.md](references/active-learning.md#trajectory-monitoring) |
| YAML output has wrong key names | Previous config used non-standard keys | Edit `propose_next_round.py` key map | — |
| Importances differ wildly between rounds | RF has high variance with small N | Average importances across last 3 rounds before acting | [random-forest-approach.md](references/random-forest-approach.md#instability) |
| `confidence: low` despite >30 designs | High `files_skipped` count | Inspect `warnings`; fix data quality | — |

---

## Best Practices

1. 🚨 **CRITICAL:** Always check `has_enough_data` before training — RF on <10 points is meaningless.
2. ✅ **REQUIRED:** Run `by-failure-diagnosis` first if previous-round pass rate is below 20%.
3. ✅ Treat importance < 0.10 as noise; do not propagate those features to the next-round config.
4. ✅ Use the top-quartile mean (not the maximum) when deriving thresholds — robust to outliers.
5. ✅ Carry a constant 10% safety margin on thresholds (e.g., `min_ipsae = top_quartile_mean * 0.9`).
6. ✅ Review the diff between rounds — never auto-apply without user sign-off.
7. ✨ **Optional:** Average feature importances across the last 3 rounds for stability.
8. ❌ Never use the optimizer as a replacement for diagnosis — they answer different questions.
9. ❌ Never train on data from different targets — restrict to one campaign per fit.
10. ❌ Never push `min_ipsae` above 0.75 without manual verification — the RF will happily recommend impossible thresholds.

---

## Suggested Next Steps

After running the optimizer:

1. **`by-design-workflow`** — Launch the next round with the proposed YAML config.
   This is the normal forward path once the user approves the recommendations.
2. **`by-campaign-manager`** — Record the optimizer recommendations and round
   number in the campaign state file so later sessions can reconstruct the
   trajectory.
3. **`by-failure-diagnosis`** — Re-run after the next round completes to check
   whether the predicted discriminators held up empirically. Closed-loop
   improvement requires this pairing.
4. **`by-knowledge`** — Persist any surprising findings (e.g., `cdr3_length`
   dominating importance for a specific target family) so future campaigns
   start with stronger priors.

These chain because each skill operates on a different artifact: the optimizer
produces parameters, the workflow consumes them, the campaign manager tracks
history, and diagnosis closes the loop on whether the recommendations worked.

---

## Related Skills

**Upstream (run first):**
- `by-failure-diagnosis` — Identifies which features discriminate PASS/FAIL.
  Use its top features as priors when reading optimizer importances.
- `by-screening` — Produces the `*_scores.json` files this skill consumes.

**Downstream (run after):**
- `by-design-workflow` — Consumes the next-round YAML and launches the round.
- `by-campaign-manager` — Persists round history and reconstructs trajectories.

**Complementary:**
- `by-knowledge` — Long-term memory across campaigns; learns which features
  matter for which target families.
- `by-hypothesis-debate` — When the optimizer is uncertain (low confidence),
  use hypothesis-debate to choose between competing parameter strategies
  before committing GPU compute.

---

## References

**Detailed documentation:**
- [references/active-learning.md](references/active-learning.md) — How active
  learning applies to protein design, acquisition functions, sample-size
  minimums, exploration vs exploitation trade-offs.
- [references/random-forest-approach.md](references/random-forest-approach.md) —
  Random Forest hyperparameters, feature engineering, importance interpretation,
  fallback behaviour for sparse data.

**Scripts:**
- `scripts/optimize_from_csv.py` — CLI: reads scored designs CSV, trains the
  Random Forest, writes `optimizer_output.json` with feature importances and
  recommendations.
- `scripts/propose_next_round.py` — CLI: reads optimizer output and a previous
  config, writes the next-round YAML config with adjusted thresholds and
  design parameters.

**Key references:**
- EVOLVEpro (Science, 2024) — few-shot active learning for protein engineering
  using protein language model embeddings. This skill uses hand-crafted
  structural and developability features instead of PLM embeddings.
- Settles, B. (2009). *Active Learning Literature Survey*. University of
  Wisconsin–Madison Computer Sciences Technical Report 1648.
- Breiman, L. (2001). *Random Forests*. Machine Learning 45, 5–32.

**License:** All dependencies (scikit-learn, pandas, numpy, PyYAML) permit
commercial use.
