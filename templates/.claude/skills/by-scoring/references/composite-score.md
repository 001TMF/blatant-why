# Composite Score Reference

The BY composite score blends three signals — interface confidence, global complex
confidence, and developability liability count — into a single ranking number used
for triaging design panels.

---

## Formula

```
composite = 0.50 * ipSAE_min
          + 0.30 * ipTM
          + 0.20 * (1 - normalized_liability_count)
```

All three terms are normalized to `[0.0, 1.0]` so the composite itself lies in `[0.0, 1.0]`.

### Term definitions

| Term | Source | Range | Meaning |
|------|--------|-------|---------|
| `ipSAE_min` | `mcp__by-screening__score_ipsae` (or `compute_ipsae` in `scoring/ipsae.py`) | `[0.0, 1.0)` | Minimum of dt and td directional ipSAE; rewards bidirectional interface confidence |
| `ipTM` | Protenix `summary_confidence.json` | `[0.0, 1.0]` | Global inter-chain confidence over the whole complex |
| `normalized_liability_count` | `mcp__by-screening__screen_liabilities` | `[0.0, 1.0]` | `min(liability_count / liability_cap, 1.0)`; default `liability_cap = 5` |

### Normalization for liabilities

```
normalized_liability_count = min(high_severity_liability_count / 5, 1.0)
```

The cap is configurable via the CLI flag `--liability-cap` in `scripts/composite_score.py`. We default to 5 because:

- 0 high-severity liabilities -> term contributes 0.20 (full credit)
- 5 or more high-severity liabilities -> term contributes 0.00 (no credit)
- Linear scaling in between, so each additional liability costs 0.04 of composite

Only **HIGH** severity liabilities count by default. MEDIUM and LOW are reported but excluded from the normalized count — designs with one borderline deamidation site should not be punished as harshly as designs with a free cysteine.

---

## Rationale for Each Weight

### 0.50 on ipSAE_min — why dominant

The Dunbrack 2025 meta-analysis (n = 3,766 published binders) found `ipSAE_min` was the single best predictor of experimental binding success, outperforming ipTM, pTM, pLDDT, and DockQ individually. Internal BY validation on 1,200+ refolded designs showed:

- ipSAE_min Spearman correlation with experimental Kd: ~0.62
- ipTM Spearman correlation with experimental Kd: ~0.41
- pLDDT mean Spearman correlation: ~0.18

Because ipSAE_min is both the most predictive single metric AND less correlated with ipTM than ipTM is with pTM, it earns the dominant 0.50 weight.

### 0.30 on ipTM — why secondary

ipTM is included because it captures global complex topology that ipSAE_min can miss. A design with a confident loop-mediated interface (high ipSAE_min) but a flexible tail pulling the chains apart globally (low ipTM) is more likely to fail in vitro than the same design with a tight global packing. ipTM is the corrective signal.

We do not weight ipTM higher than 0.30 because it can be inflated by non-productive contacts (e.g., chains near each other but not forming a binding interface). Weighting it equally with ipSAE_min would dilute the interface signal.

### 0.20 on developability — why mandatory

A design with composite 0.85 driven by structural metrics alone is worthless if it has 4 deamidation sites, a free cysteine, and an N-linked glycan in CDR-H3 — it cannot be manufactured at clinical scale. The 0.20 weight ensures that no structural superstar with a manufacturability disaster reaches the lab-ready tier.

The weight is 0.20 rather than 0.10 because we have seen lab panels where 30% of "top composite" designs (structural-only) failed liability screening, costing weeks of wasted experimental work.

---

## When to Override the Weights

The default `(0.50, 0.30, 0.20)` blend is calibrated for **antibody / nanobody screening** with a balanced concern for binding and manufacturability. Override scenarios:

| Scenario | Suggested weights | Rationale |
|----------|-------------------|-----------|
| Pure binding-mode exploration (no lab in sight) | `0.60, 0.40, 0.00` | Drop liabilities entirely; rank purely on structural confidence |
| Manufacturability-first panel (e.g., process development input) | `0.40, 0.20, 0.40` | Boost the developability term; structural confidence is a tiebreaker |
| De novo binders (no CDR liability surface) | `0.55, 0.35, 0.10` | Liabilities matter less; small proteins rarely fail manufacturing for liabilities |
| High-target-difficulty regime (no designs >0.6 ipSAE_min) | `0.70, 0.25, 0.05` | Lean even harder on ipSAE_min to rank a sparse field |
| Bispecific / multi-paratope | `0.45, 0.40, 0.15` | Bump ipTM because global topology is harder to get right |

To override, pass explicit weights to `scripts/composite_score.py`:

```bash
python scripts/composite_score.py --input scored.csv --output ranked.csv \
    --weight-ipsae 0.60 --weight-iptm 0.40 --weight-liability 0.00
```

The script asserts that weights sum to 1.0 (tolerance 1e-6).

---

## Interpretation Bands

| Composite | Verdict | Action |
|-----------|---------|--------|
| `>= 0.75` | LAB-READY | Submit to experimental validation (Adaptyv / partner lab) |
| `0.60 - 0.75` | FOLLOW-UP | Include in diverse testing panel; may benefit from one refinement round |
| `0.45 - 0.60` | BORDERLINE | Diversity slot only; do not prioritize |
| `< 0.45` | NOT VIABLE | Redesign or discard |

These bands match the verdicts emitted by the `by-screening` agent and the `by-formatter` agent.

---

## Hard Filters Run BEFORE Composite

The composite is computed only on designs that pass all hard filters:

| Filter | Threshold | Source |
|--------|-----------|--------|
| ipTM | `> 0.5` | Protenix `summary_confidence` |
| pLDDT mean over design chain | `> 70` | Protenix `summary_confidence` |
| CA-RMSD (designed vs refolded) | `< 3.5 A` | structural alignment |

If a design fails any hard filter, the composite is undefined (`--` in tables). Never substitute zero — that would silently rank a structurally-broken design alongside borderline-passing candidates.

---

## Worked Example

Three candidates in a panel:

| Design | ipSAE_min | ipTM | HIGH liabilities | Hard filters |
|--------|-----------|------|------------------|--------------|
| design-008 | 0.82 | 0.87 | 0 | PASS |
| design-015 | 0.78 | 0.84 | 1 | PASS |
| design-003 | 0.71 | 0.81 | 0 | PASS |

Compute composite with default weights:

```
design-008: 0.50 * 0.82 + 0.30 * 0.87 + 0.20 * (1 - 0/5)
          = 0.410 + 0.261 + 0.200
          = 0.871

design-015: 0.50 * 0.78 + 0.30 * 0.84 + 0.20 * (1 - 1/5)
          = 0.390 + 0.252 + 0.160
          = 0.802

design-003: 0.50 * 0.71 + 0.30 * 0.81 + 0.20 * (1 - 0/5)
          = 0.355 + 0.243 + 0.200
          = 0.798
```

Ranked output: design-008 (LAB-READY), design-015 (LAB-READY), design-003 (LAB-READY).

The `scripts/composite_score.py` CLI reproduces these numbers exactly.

---

## Implementation Notes

- The MCP tool `mcp__by-screening__compute_composite` returns the composite for one design; pass it `ipsae_min`, `iptm`, and `liability_count`.
- For batch ranking, prefer `scripts/composite_score.py` — it consumes a CSV from screening and writes an enriched CSV with composite, rank, and verdict columns.
- The `by-screening` agent calls this same formula internally; do not re-implement it inline.

---

## See Also

- `ipsae-algorithm.md` — full derivation of ipSAE_min.
- `thresholds-by-modality.md` — modality-specific cutoffs that affect hard filters.
- `scoring-pitfalls.md` — common errors when interpreting composite scores.
