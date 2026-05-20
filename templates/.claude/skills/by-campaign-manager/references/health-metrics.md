# Campaign Health Metrics

This reference defines how to assess a campaign's health while it is running and
when to abort vs continue. The manager skill consults this guide whenever
`track_progress.py` surfaces an anomaly, and at the post-campaign review.

Health assessment has three pillars:
1. **Pass-rate trajectory** — are designs PASSing fast enough?
2. **Score distribution** — are scores stable, drifting, or collapsing?
3. **Compute failure rate** — is the engine itself in trouble?

---

## 1. Pass-Rate Trajectory

The most important single signal. Compute it as:

```
running_pass_rate = passed_designs / scored_designs
```

Re-compute after every 5–10 newly-scored designs.

### Expected Trajectories

| Target Class | Early (first 10%) | Mid (50%) | Final |
|--------------|-------------------|-----------|-------|
| Well-studied | 30–60% PASS | 30–60% PASS | 30–60% PASS |
| Moderate | 10–25% PASS | 15–35% PASS | 15–35% PASS |
| Novel | 0–10% PASS | 5–15% PASS | 5–20% PASS |

### Trajectory Patterns

| Pattern | Interpretation | Action |
|---------|----------------|--------|
| Flat at expected rate | Healthy | Continue |
| Rising trajectory | Engine warming up / topology exploration | Continue |
| Falling trajectory | Drift into bad region; over-fitting on early hits | Continue if final rate still ≥ alarm threshold; otherwise consider abort |
| Step-function collapse | Engine error or upstream input corrupted | Abort; investigate |
| Stuck at 0% past 50% of run | Hotspot or scaffold mismatch | **Abort** ([see below](#abort-criteria)) |

### Low Pass Rate

If pass rate falls below the alarm threshold:

| Engine | Target | Expected | Alarm |
|--------|--------|----------|-------|
| PXDesign | Well-studied | 30–60% | <15% |
| PXDesign | Novel | 10–30% | <5% |
| BoltzGen nanobody | Standard | 20–40% | <10% |
| BoltzGen antibody | Standard | 15–35% | <8% |

PASS criteria: `ipTM > 0.5, pLDDT > 70, RMSD < 3.5Å, no high-severity CDR liabilities`.

Below-alarm action: surface to user; offer follow-up run with varied hotspots or scaffold.

---

## 2. Score Distribution Shifts

Beyond pass/fail counts, watch the score distribution. Compute on each batch:

- `mean(ipTM)`, `median(ipTM)`
- `mean(ipSAE_min)`, `max(ipSAE_min)`
- `mean(pLDDT_passing)` (only over PASSed designs)
- Composite score: `0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 - normalized_liability_count)`

### Distribution Shift Patterns

| Pattern | Likely Cause | Action |
|---------|--------------|--------|
| Stable mean and tail | Healthy | Continue |
| Mean rising, tail rising | Engine improving (good) | Continue; expect more PASSes |
| Mean stable, tail collapsing (no high-scorers) | Mode collapse; engine stuck on one topology | Continue but plan diverse-parameter run next |
| Mean falling | Engine drift into low-quality region | If pass rate still OK, continue; else abort |
| High variance, scattered | Healthy exploration | Continue |
| Bimodal | Engine oscillates between two topologies | Continue; cluster downstream |

### Historical Baselines

| Metric | Good | Acceptable | Concerning |
|--------|------|------------|------------|
| Best ipTM | >0.8 | 0.6–0.8 | <0.6 |
| Best ipSAE_min | >0.7 | 0.4–0.7 | <0.4 |
| Mean pLDDT (passing) | >80 | 70–80 | <70 |
| Pass rate | >30% | 15–30% | <15% |
| Diversity (clusters) | >5 | 3–5 | <3 |

---

## 3. Compute Failure Rate

For batch jobs (HPC RunPod, Tamarind), track:

```
compute_failure_rate = failed_jobs / submitted_jobs
```

| Failure Rate | Status | Action |
|--------------|--------|--------|
| 0% | Healthy | Continue |
| 1–5% | Normal noise (retries handled) | Continue |
| 5–20% | Provider degraded | Continue but log; offer to switch provider on next round |
| 20–50% | Significant problem | Halt; check provider status; resubmit failed |
| >50% | Pipeline failure | **Abort.** Diagnose before re-launching |

For local GPU runs:
- OOM errors: reduce batch size or switch to larger card.
- Timeout (no design output for >15 min): kill the run; check stderr.
- GPU utilization dropping to 0% mid-run: likely crash; abort.

---

## Abort Criteria

Abort the run if **any** of:

- Zero PASS designs after 50% of the run completed.
- Engine unresponsive >15 min, no new output.
- GPU OOM repeated (≥3 occurrences on the same batch).
- Compute failure rate exceeds 50%.
- Score distribution collapsed: max ipTM <0.3 across last 20 designs.
- User requests abort.

Do NOT abort if:

- Pass rate is low but nonzero (2–3 good candidates remain valuable).
- Early scores are poor but trending upward (engine is exploring).
- Compute failures are isolated retries (<5%).

Always write a final checkpoint when aborting:

```json
{
  "phase": "failed",
  "abort_reason": "zero_pass_rate_at_50pct",
  "designs_scored_at_abort": 25,
  "best_iptm": 0.42,
  "recovery_options": [
    "Vary hotspots; relaunch as Run 2",
    "Switch scaffold (caplacizumab -> ozoralizumab)",
    "Drop to Preview tier and re-validate hotspot selection"
  ]
}
```

---

## Mid-Run Decision Matrix

When `track_progress.py` flags a concerning signal, consult this matrix:

| Signal | Pass Rate | Top Score | Compute | Decision |
|--------|-----------|-----------|---------|----------|
| All good | ≥ expected | ipTM > 0.6 | <5% fail | Continue |
| Low pass, scores ok | < alarm | ipTM > 0.6 | OK | Continue; flag for follow-up run |
| OK pass, poor scores | OK | ipTM < 0.4 | OK | Continue; expect weak final candidates |
| Both poor | < alarm | ipTM < 0.4 | OK | **Abort** (50% rule); diagnose |
| Compute degraded | OK | OK | 20–50% fail | Continue; switch provider next round |
| Compute failing | — | — | >50% fail | **Abort** |
| Score collapse | < alarm | ipTM dropping fast | OK | **Abort**; investigate input quality |

---

## Post-Campaign Health Categories

| Category | Pass Rate | Best Scores | Action |
|----------|-----------|-------------|--------|
| **Healthy** | >30% | ipTM >0.8, ipSAE >0.7 | Present top 3–5 candidates. Offer Protenix ensemble validation. Suggest lab ordering. |
| **Marginal** | 15–30% | ipTM 0.6–0.8 | Present with caveats. Recommend follow-up run with varied parameters. Consider production tier. |
| **Poor** | <15% | ipTM <0.6 | Do not present as viable. Re-examine target prep, try different hotspots, or switch engine. Evaluate target tractability. |
| **Failed** | 0% or aborted | — | Diagnose pipeline; store failure via `mcp__by-knowledge__knowledge_store_failure`. |

---

## Diagnostic Questions When Pass Rate Is Low

Before concluding the engine failed, work through:

1. Were the hotspots verified by `by-research` with HIGH confidence?
2. Is the input PDB structure resolution adequate (<2.5 Å)?
3. Does the modality match the target (e.g., flat surface → VHH may struggle)?
4. Were prior campaigns on similar targets successful with this scaffold? (Query `by-knowledge`.)
5. Is the GPU sufficient (40 GB+ for antibody)?
6. Did the engine see a fold-validation failure upstream?

A "no" to any of these often explains low pass rate without engine fault.

---

## Anti-Patterns

- ❌ Aborting on first low pass-rate signal — wait for 50% of run.
- ❌ Continuing when compute failure rate >50% — diagnose first.
- ❌ Re-launching with same parameters after a poor result — vary one axis.
- ❌ Storing only successful outcomes — failures are equally valuable to `by-knowledge`.
- ❌ Conflating "low pass" with "engine broken" — investigate input quality first.
