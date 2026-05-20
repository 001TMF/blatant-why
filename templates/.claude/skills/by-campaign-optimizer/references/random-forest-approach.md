# Random Forest Approach

The `by-campaign-optimizer` skill uses scikit-learn's `RandomForestRegressor`
as its default model. This reference documents why RF is the right default, how
the hyperparameters were chosen, how to interpret feature importances, and what
to do when the training set is too small for ML.

---

## Why Random Forest

The optimizer needs a model that:

1. Handles small training sets (10–100 designs) without overfitting catastrophically
2. Produces stable feature importances that survive between rounds
3. Captures non-linear relationships between metrics and ipSAE
4. Requires zero hyperparameter tuning per campaign
5. Trains in <1 second on commodity laptops

Random Forest hits all five. Linear regression fails on (3). Gradient boosting
fails on (4) — it needs careful learning-rate tuning. Neural networks fail on
(1) and (4). Gaussian processes are a viable alternative but introduce a
heavier scikit-learn dependency and slower training.

Bayesian optimization with a GP would be theoretically superior for the
acquisition-function step. It is a defensible upgrade path but adds complexity
that is not warranted at the current campaign scales.

---

## Hyperparameters

The default configuration in `active_learning._ml_suggest`:

```python
RandomForestRegressor(
    n_estimators=100,
    max_depth=5,
    random_state=42,
)
```

### `n_estimators=100`

100 trees is the standard scikit-learn default. The marginal gain from 200+
trees is below noise for training sets of this size, and 100 trees train in
well under a second.

**When to change:** if you have ≥500 designs, raising to 300 trees may
stabilize importances. Edit `optimize_from_csv.py` directly.

### `max_depth=5`

Shallow trees prevent overfitting on small training sets. Depth 5 allows
~32 leaves per tree, which is roughly the number of distinct outcome
patterns a 10–100-design campaign can produce.

**When to change:** if your data is noisy and the RF predicts the same value
for every input, raise to 8 or 10. If the RF appears to be memorizing the
training set (perfect training fit, poor cross-validation), drop to 3.

### `random_state=42`

Fixed for reproducibility. The optimizer's outputs are deterministic given
the same input data. Do not change this without recording the old seed —
debugging non-deterministic recommendations is painful.

### `min_samples_split` (default: 2)

Left at scikit-learn's default. With `max_depth=5`, raising this further is
redundant.

**When to change:** if you see "splits on single design" in tree explanations,
raise to 3 or 5. Rare in practice.

---

## Feature Set

The default feature list is:

```python
_RF_FEATURE_NAMES = [
    "ipsae",
    "iptm",
    "plddt",
    "rmsd",
    "liabilities",
    "cdr3_length",
]
```

`net_charge` and `hydrophobic_fraction` are extracted but excluded from the RF
because they are sparsely populated in real scoring runs — including them
would penalize designs whose scores happen to lack those fields.

**Target variable:** `ipsae` (or `ipsae_min` if present). This is the metric
the RF tries to predict. The optimizer's recommendations are oriented around
maximizing this target.

To target composite score instead, edit the `y.append(...)` line in
`_ml_suggest` to use the composite formula.

---

## Feature Importance Interpretation

Scikit-learn's `feature_importances_` uses mean decrease in impurity (MDI)
across all trees. The values:

- Sum to 1.0 across all features
- Are normalized — `importance(ipsae) = 0.35` means 35% of the variance the
  forest can explain is attributed to ipSAE
- Are biased toward continuous features with many possible split points;
  categorical or binary features (like `cdr3_length` quantized to 1-residue
  buckets) may be underweighted

**Reading the ranking:**

| Importance | Interpretation |
|---|---|
| >0.30 | Dominant feature; threshold recommendations should reflect this |
| 0.15–0.30 | Meaningful contributor; propagate to next-round YAML |
| 0.05–0.15 | Marginal; surface in the report but do not change thresholds |
| <0.05 | Noise; ignore |

### Feature Leakage

If `cdr3_length` shows up with importance >0.40, suspect class imbalance.
If the campaign's earlier rounds happened to design only 13-residue CDR3s,
the model will learn "ipSAE is high when CDR3 = 13" — which is not a useful
finding, just a sampling artifact.

Fix: stratify the training set by CDR3 length before fitting, or drop the
feature entirely for that round.

### Instability

With 10–30 training designs, importance rankings can swing dramatically
between rounds. The recommended mitigation is to average importances across
the last 3 rounds before acting on them. The `by-campaign-manager` skill
tracks the history needed for this.

If importances are still unstable after averaging, the campaign needs more
data before active learning is meaningful. Default to rule-based parameters
and run a larger exploratory round.

---

## Threshold Derivation

Once the RF is trained, the optimizer derives recommended thresholds from the
top-quartile designs:

```python
threshold = np.percentile(y_arr, 75)
good_mask = y_arr >= threshold
good_means = X_arr[good_mask].mean(axis=0)
```

For features with importance >0.10:

- `ipsae`, `iptm`, `plddt` → `min_<feature> = top_quartile_mean * 0.9`
- `rmsd` → `max_rmsd = top_quartile_mean * 1.1`
- `cdr3_length` → `target_cdr3_length = round(top_quartile_mean)`

The 10% safety margin prevents over-aggressive threshold tightening. The
top-quartile **mean** (not max) is used because it is robust to outliers — one
unusually good design shouldn't move the threshold for the entire next round.

---

## Fallback Behavior

When the optimizer cannot train ML, it returns `source: "rule_based"` with
`recommended_parameters: {}`. The caller (typically `by-campaign-manager`)
then applies defaults documented in that skill.

Fallback triggers:

1. **<10 scored designs.** Hard floor; no exceptions.
2. **scikit-learn not installed.** `ImportError` caught explicitly.
3. **All designs have identical scores.** RF cannot fit; importances would
   all be zero.
4. **Every feature row has missing values.** No valid training set.

In all four cases, the user sees a clear explanation in `OptimizationResult.explanation`.
The `warnings` list also captures any skipped `*_scores.json` files so the
user knows the dataset was not silently truncated.

---

## When to Replace RF with Something Else

The current implementation is intentionally minimal. Upgrade paths if needed:

| Symptom | Suggested Replacement |
|---|---|
| Importances unstable across rounds with ≥100 designs | Gradient boosting (XGBoost or LightGBM) for higher signal-to-noise |
| Strong pairwise interactions known to matter | Add explicit interaction features OR switch to GBM |
| Need calibrated prediction intervals | Gaussian process regression (slower but principled) |
| Have sequence embeddings (PLM) available | Replace hand-crafted features with embedding vectors; consider EVOLVEpro-style few-shot fine-tuning |
| Cross-target transfer needed | Multi-task learner with shared backbone |

None of these are required at current campaign scale. Document the trigger
explicitly before swapping the model class, and version the optimizer output
schema so downstream code can detect the change.

---

## Reproducibility

Because `random_state=42` is fixed, every run on the same input produces the
same output. To prove this in audits:

1. Note the input data hash (the optimizer writes `data_sha256` in its output).
2. Note the scikit-learn version (also written).
3. Re-run with identical inputs; importances and recommendations should match
   to the printed precision.

If they differ, the input data changed — usually because a `*_scores.json`
file was updated between runs.
