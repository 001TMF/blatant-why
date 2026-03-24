# Skill: Proteus Campaign Optimizer (Active Learning)

Suggest optimised parameters for the next design round using data-driven active
learning.  Trains a lightweight random-forest regressor on all scored designs
in a campaign and returns feature importances, threshold refinements, and
diversity/alpha suggestions.

---

## When to Use

- After a design round completes and scores are recorded.
- When deciding how to configure the next round of a multi-round campaign.
- When the campaign has **10 or more** scored designs (the ML threshold).

## How It Works

1. **Data collection** -- Gathers all `*_scores.json` files under the campaign
   directory.
2. **Feature extraction** -- Extracts ipSAE, ipTM, pLDDT, RMSD, liabilities,
   and CDR3 length from each scored design.
3. **Random forest** -- Fits a `RandomForestRegressor` (100 trees, max depth 5)
   predicting ipSAE as the optimisation target.
4. **Top-quartile analysis** -- Identifies feature ranges shared by the best 25%
   of designs and derives threshold recommendations.
5. **Output** -- Returns an `OptimizationResult` with source, recommended
   parameters, feature importances, confidence level, and a human-readable
   explanation.

## Fallback Behaviour

When fewer than 10 scored designs exist, or scikit-learn is not installed, the
optimizer falls back to rule-based recommendations (source: `"rule_based"`).
Install the ML extras to enable active learning:

```
pip install proteus-agent[ml]
```

## MCP Tool

**`campaign_suggest_next_round`** -- call via the `proteus-campaign` MCP server.

| Argument | Default | Description |
|----------|---------|-------------|
| `campaign_dir` | (required) | Path to campaign directory |
| `min_designs` | `10` | Minimum scored designs for ML |

## Python API

```python
from proteus_cli.campaign.active_learning import (
    has_enough_data,
    suggest_from_campaign,
    OptimizationResult,
)

if has_enough_data("campaigns/tnfa/campaign_20260323_001"):
    result = suggest_from_campaign("campaigns/tnfa/campaign_20260323_001")
    print(result.source)                   # "active_learning"
    print(result.recommended_parameters)   # {"min_ipsae": 0.42, ...}
    print(result.feature_importances)      # [("ipsae", 0.35), ...]
```

## Reference

Inspired by **EVOLVEpro** (Science, 2024) -- few-shot active learning using
protein language model embeddings.  This implementation uses hand-crafted
structural and developability features instead of PLM embeddings, making it
lightweight and dependency-free (apart from scikit-learn).
