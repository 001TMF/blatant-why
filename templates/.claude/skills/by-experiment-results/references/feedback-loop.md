# Feedback Loop

How this skill chains into the larger BY pipeline. The wet-lab loop is the only path by which the system improves on real-world calibration, so the chaining contracts here are load-bearing.

---

## State Diagram

```
       ┌──────────────────────────────────────────────────────┐
       │                                                      │
       │   ROUND N                                            │
       │   ───────                                            │
       │   by-research → by-design-workflow → by-screening    │
       │                                          │           │
       │                                          ▼           │
       │                          screening_results.json      │
       │                                          │           │
       │                                          ▼           │
       │                          /by:approve-lab (gated)     │
       │                                          │           │
       │                                          ▼           │
       │                          adaptyv_confirm_submission  │
       │                                          │           │
       │                                          ▼           │
       │                                   LAB EXPERIMENT     │
       │                                   (real world)       │
       │                                          │           │
       │                                          ▼           │
       │                          adaptyv_get_results         │
       │                                          │           │
       │                                          ▼           │
       │                         lab_results.raw.csv          │
       │                                                      │
       └──────────────────────────────────────┬───────────────┘
                                              │
                       ┌──────────────────────┴──────────────────┐
                       │  THIS SKILL: by-experiment-results       │
                       │                                          │
                       │  1. ingest_lab_results.py                │
                       │     -> lab_results.normalized.json       │
                       │                                          │
                       │  2. diagnose_silico_vs_lab.py            │
                       │     -> enriched_dataset.csv              │
                       │     -> calibration.json                  │
                       │     -> calibration_report.md             │
                       │                                          │
                       │  3. update_knowledge_from_lab.py         │
                       │     -> knowledge_store_campaign          │
                       │     -> knowledge_store_failure (×N)      │
                       └──────────────────────┬───────────────────┘
                                              │
       ┌──────────────────────────────────────┴──────────────────────┐
       │                                                             │
       │   ROUND N+1                                                 │
       │   ─────────                                                 │
       │   by-campaign-optimizer (reads enriched_dataset.csv)        │
       │              │                                              │
       │              ▼                                              │
       │   propose_next_round.py -> config_round_N+1.yaml            │
       │              │                                              │
       │              ▼                                              │
       │   by-design-workflow (with updated parameters AND priors    │
       │                       from knowledge graph)                 │
       │                                                             │
       └─────────────────────────────────────────────────────────────┘
```

The lab loop is **the** improvement engine. Without it, the campaign optimizer is trained only on in-silico self-prediction (which is biased toward what the screener already believes).

---

## MCP Tool Calls

### Reading lab results from Adaptyv

```python
import json

raw = mcp__by_adaptyv__adaptyv_get_results(experiment_id="exp_12345")
data = json.loads(raw)

# data == {"experiment_id": "exp_12345", "results": [...]}
# Write to disk for ingest:
with open("experiments/exp_12345.adaptyv.json", "w") as fh:
    json.dump(data, fh, indent=2)
```

Then run ingest with `--format adaptyv-json --input experiments/exp_12345.adaptyv.json`.

### Writing the enriched campaign record

```python
# update_knowledge_from_lab.py wraps this call; shown here for transparency.
import json

result = mcp__by_knowledge__knowledge_store_campaign(
    target="tnf-alpha",
    modality="VHH",
    parameters={"scaffold": "caplacizumab", "seeds": 4, "round": 2},
    outcomes={
        "hit_rate": 0.23,                # in-silico pass rate
        "best_ipsae": 0.78,
        "best_iptm": 0.85,
        "screening_pass_rate": 0.18,
        # Lab-derived fields:
        "lab_tested": 18,
        "lab_passed": 12,
        "lab_pass_rate": 0.67,
        "lab_best_kd_nm": 12.5,
        "calibration": {
            "validated_features": ["ipsae_min", "iptm"],
            "contradicted_features": ["hydrophobic_fraction"],
            "auc_ipsae": 0.81,
            "precision_at_top_10": 0.7,
        },
    },
    notes="Round 2 lab data; ipSAE validated; hydrophobic_fraction contradicted",
    designs=[
        {
            "design_id": "tnf_002_001",
            "scaffold": "caplacizumab",
            "ipsae": 0.78,
            "iptm": 0.85,
            "status": "PASS",         # silico verdict
            "lab_outcome": "PASS",    # lab verdict
            "kd_nm": 12.5,
        },
        # ... top 10-20 designs
    ],
)
```

### Recording a contradicted predictor as a failure

```python
result = mcp__by_knowledge__knowledge_store_failure(
    campaign_id="campaign_20260520_001",
    description="hydrophobic_fraction predicted FAIL for lab-PASS designs",
    root_cause="Total-residue hydrophobicity used instead of surface-exposed; "
               "feature definition mis-specified for this target class",
    target="tnf-alpha",
)
```

These two writes together form the **complete** lab-feedback record. The campaign record encodes what worked; the failure record encodes what to NOT trust next time.

---

## Idempotency

`update_knowledge_from_lab.py` is safe to re-run:

1. **Campaign record** — keyed by `(target, campaign_id, batch_id)`. If a record with the same triple already exists, the script logs `already exists, skipping` and exits 0. To overwrite, pass `--force`.
2. **Failure records** — keyed by `(campaign_id, feature_name)`. Same dedup logic.

This matters because lab results often arrive in chunks (partial batch completion). You will re-run this skill 2-3 times as data trickles in, and you do not want duplicate knowledge entries.

---

## Per-Assay Calibration

Every assay has its own noise floor and its own PASS threshold. Mixing assays in one calibration call invalidates the test.

Run one diagnosis per assay:

```bash
# Affinity calibration
python3 scripts/diagnose_silico_vs_lab.py \
    --lab    lab_affinity.normalized.json \
    --silico screening_results.json \
    --output-json calibration_affinity.json \
    --output-md   calibration_affinity_report.md

# Expression calibration (separate)
python3 scripts/diagnose_silico_vs_lab.py \
    --lab    lab_expression.normalized.json \
    --silico screening_results.json \
    --output-json calibration_expression.json \
    --output-md   calibration_expression_report.md
```

Cross-reference the two reports manually. A common pattern: `ipsae` validates against affinity but is inconclusive against expression — that is the expected behavior (ipsae models interface, not folding/expression).

---

## Per-Target Calibration

Calibrations are target-specific. A predictor that validates on TNF-alpha may be contradicted on PD-L1 because:

- Different epitope topology
- Different glycosylation pattern
- Different conformational dynamics

**Never** generalize a calibration finding across targets without a separate validation. The knowledge graph records findings per target so future campaigns on related targets get warmer priors, not blanket assumptions.

---

## When the Loop Closes

The feedback loop "closes" when:

1. Lab results arrive for round N.
2. Calibration is computed.
3. Validated features are kept in the screener; contradicted features are removed or inverted.
4. Round N+1 launches with adjusted parameters AND knowledge-graph priors.
5. Round N+1 lab results arrive.
6. The round N+1 calibration shows **higher AUC** for the kept features and the contradicted features have either been fixed or removed.

If step 6 fails (AUC does not improve), the screener model needs structural changes, not just threshold tuning. Escalate to **by-hypothesis-debate**.

---

## Lab Submission Gate

This skill operates ENTIRELY on data that arrives AFTER lab submission. It does not submit anything. Lab submission is triple-gated and lives in **by-adaptyv** / `/by:approve-lab`.

The gate matters here because:

- The skill expects lab data with a `design_id` that maps onto the campaign's submitted batch.
- If lab data arrives but the campaign manifest does not record the submission, the join will fail with cryptic 0-row results.

Always confirm the campaign manifest records the lab submission before running this skill. Cross-check via `by-campaign-manager` if uncertain.

---

## Failure-Mode Handoff

When calibration shows multiple contradicted predictors, this skill emits failure records but does NOT decide what to do next. The user (or **by-failure-diagnosis**) decides:

1. **One contradicted feature** → record, remove from screener, move on.
2. **2 contradicted features** → record, run by-failure-diagnosis on the lab-FAIL subset to look for missed signal.
3. **3+ contradicted features** → the screener is mis-specified for this target. Run **by-hypothesis-debate** before more lab compute.

The handoff rule: **calibration produces facts; downstream skills produce decisions.**

---

## Storage Conventions

Files this skill writes (all under the campaign directory):

```
campaigns/<target>/<campaign_id>/
├── screening_results.json           # input, from by-screening
├── experiments/                     # raw lab files (one subdir per batch)
│   └── batch_001_adaptyv.csv
├── lab_results.normalized.json      # output from ingest_lab_results.py
├── enriched_dataset.csv             # output from diagnose_silico_vs_lab.py
├── calibration.json                 # output from diagnose_silico_vs_lab.py
└── calibration_report.md            # output from diagnose_silico_vs_lab.py
```

The knowledge graph receives entries via MCP — those live in `~/.by/knowledge/` or the project-local override.
