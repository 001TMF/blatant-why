# Active Learning for Protein Design Campaigns

This reference explains the active-learning principles behind the
`by-campaign-optimizer` skill: when ML actually adds value over random sampling,
which acquisition functions to use, and how to size training sets so the
optimizer's recommendations are trustworthy.

---

## What "Active Learning" Means Here

Classical supervised learning consumes a fixed labelled dataset. Active learning
chooses *which* points to label next, given the labels collected so far. In a
multi-round design campaign every round is exactly that: you have N scored
designs and need to decide what to sample in round N+1.

The optimizer does not literally pick individual sequences. It picks **regions
of feature space** — value ranges for ipSAE, ipTM, pLDDT, RMSD, liability count,
and CDR3 length — that historically produced top-quartile designs. The next-round
config narrows the design search to those regions, which is equivalent to
acquiring more labels where the model thinks the signal is strongest.

---

## When Active Learning Adds Value vs Random Sampling

| Scenario | Recommendation | Why |
|---|---|---|
| <10 scored designs | Random / rule-based defaults | RF cannot fit a meaningful model; importances are pure noise |
| 10–30 scored designs, low feature variance | Uncertainty sampling | Need to broaden the training set before exploiting |
| 10–30 scored designs, high feature variance | Mixed exploit/explore | Some signal is present; verify with cross-round consistency |
| 30–100 scored designs | Greedy exploitation OK | RF has enough data for stable importance ranking |
| >100 scored designs | Pure exploitation, narrow thresholds | Diminishing returns from exploration |
| Single-target campaign | Active learning works well | Distribution shift is minimal |
| Multi-target campaign | Train per-target models | Mixing targets adds confounding noise |

**Rule of thumb:** if the top feature's importance is <0.10, fall back to
random sampling. Importance below that threshold is statistically
indistinguishable from background on small training sets.

---

## Acquisition Functions

An acquisition function ranks candidate feature-space regions by how useful
sampling them would be. The optimizer supports three modes; the choice depends
on the campaign's stage.

### Greedy Exploitation (default for ≥30 designs)

Sample the region with the highest predicted ipSAE. This is the most aggressive
strategy and converges fastest when the model is accurate.

```
score(region) = predicted_ipsae(region)
```

**Use when:** pass rate has been climbing across rounds, model importances are
stable, and you want to push for top hits.

### Uncertainty Sampling (default for 10–30 designs)

Sample the region where the RF's prediction variance is highest. This actively
broadens the training set in the most informative direction.

```
score(region) = std(individual_tree_predictions(region))
```

The RF's per-tree predictions give a cheap proxy for prediction variance. High
variance means trees disagree, which means the region is under-sampled.

**Use when:** the campaign is still early, importances change between rounds,
or pass rate is below 20%.

### Expected Improvement (advanced)

Trade off exploitation and exploration explicitly:

```
EI(region) = E[max(0, predicted_ipsae(region) - best_observed_ipsae)]
```

Computed via the per-tree prediction distribution. Use when the user has a
specific quality target (e.g., "find at least 5 designs with ipSAE ≥ 0.70")
rather than a vague "improve the round".

---

## Sample-Size Minimums

The optimizer applies these floors when deciding whether to trust the RF:

| Designs Available | Optimizer Behavior |
|---|---|
| <10 | Returns `source: "rule_based"`; recommends defaults from `by-campaign-manager` |
| 10–19 | Returns `confidence: "low"`; surfaces importances but flags them as preliminary |
| 20–29 | Returns `confidence: "medium"`; recommendations propagate to YAML with safety margin |
| 30–99 | Returns `confidence: "high"`; recommendations propagate with normal margin |
| ≥100 | Returns `confidence: "high"`; greedy exploitation becomes viable |

These thresholds are conservative. RF can technically train on fewer points but
the importance ranking is unstable below 30 designs — different random seeds
produce different top features. The fallback path exists specifically to
prevent acting on that instability.

---

## Exploration vs Exploitation

Every round trades these off. The optimizer surfaces both signals so the user
can choose.

**Exploitation lever:** `recommended_parameters.min_ipsae` set to
`top_quartile_mean * 0.9`. Tightening this filters more aggressively for the
known-good region.

**Exploration lever:** `exploration_regions` lists feature-space cells with
high RF prediction variance. Sampling these expands the training set and
de-risks the next round.

**Default policy:** allocate 70% of next-round designs to exploitation and 30%
to exploration. This is a defensible starting point — adjust based on
campaign goals.

When pass rate is climbing, shift toward exploitation. When pass rate stalls,
shift toward exploration. When pass rate drops, run `by-failure-diagnosis`
before deciding.

---

## Trajectory Monitoring

A single round's recommendations can be noisy. Robust active learning watches
the trajectory across multiple rounds:

- **Importance drift:** if the top feature changes every round, the training
  set is still too small. Hold thresholds steady; collect more data.
- **Threshold drift:** if `min_ipsae` recommendations bounce around, average
  the last 3 rounds rather than acting on the most recent.
- **Pass-rate trajectory:** if pass rate is monotonically improving, the
  optimizer is working; continue. If it stalls or reverses, switch to
  uncertainty sampling or invoke `by-failure-diagnosis`.

The optimizer writes its full history to `campaign_state.json` (managed by
`by-campaign-manager`) so later sessions can reconstruct the trajectory
without re-reading every `*_scores.json`.

---

## Relationship to `by-failure-diagnosis`

Diagnosis and optimization solve different problems:

| Aspect | `by-failure-diagnosis` | `by-campaign-optimizer` |
|---|---|---|
| Question | "What discriminates PASS from FAIL?" | "What parameters should the next round use?" |
| Method | Mann-Whitney U on continuous metrics | Random Forest regression on continuous metrics |
| Input | PASS/FAIL labelled designs | All scored designs (labels optional) |
| Output | Significant discriminators + p-values | Feature importances + concrete thresholds |
| When to run | Pass rate below 20%, or "why are designs failing?" | Planning next round, ≥10 scored designs |

Best practice: run diagnosis first when pass rate is low. Use its top
discriminators as a sanity check on the optimizer's importance ranking. If
they disagree, the disagreement itself is a signal — investigate before
launching the next round.

---

## Limitations and Honest Caveats

1. **Hand-crafted features only.** This optimizer does not consume sequence
   embeddings or structural representations directly. PLM-based active
   learning (e.g., EVOLVEpro) would extend this, but adds dependencies.
2. **Per-campaign training only.** Cross-target generalization requires a
   different model class (likely a multi-task learner).
3. **No interaction terms.** RF captures non-linearity but importance is
   single-feature. Pairwise interactions (e.g., low RMSD only matters when
   ipSAE is high) are not surfaced explicitly.
4. **Threshold recommendations are heuristics.** The `top_quartile_mean * 0.9`
   rule is a defensible default, not an optimization. Treat the value as a
   starting point for the user, not an answer.
5. **Confidence labels are not statistical confidence intervals.** They are
   training-set-size buckets. Do not interpret `"high"` as a 95% CI.
