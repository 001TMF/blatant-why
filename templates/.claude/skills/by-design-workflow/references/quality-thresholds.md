# Quality Thresholds and Accept-vs-Re-Run Decision Logic

Canonical acceptance criteria for designs by modality, plus the decision rules that
drive `accept_or_rerun.json` verdicts (`ACCEPT` / `RERUN` / `SWITCH_TOOL` / `ESCALATE`).

These thresholds are the source of truth for `scripts/route_intent.py --mode
accept-or-rerun`. If a threshold changes here, change it in the script lookup
table in the same commit.

---

## 1. Per-Metric Thresholds (Canonical)

Default thresholds across all modalities (override only with explicit user request):

| Metric | Minimum (PASS) | Good | Excellent | Hard Fail |
|--------|----------------|------|-----------|-----------|
| **ipSAE (min)** | > 0.3 | > 0.5 | > 0.8 | < 0.2 |
| **ipTM** | > 0.5 | > 0.7 | > 0.85 | < 0.4 |
| **pLDDT** | > 70 | > 80 | > 90 | < 60 |
| **CA-RMSD (Å)** | < 3.5 | < 2.0 | < 1.5 | > 5.0 |
| **High-severity liabilities** | ≤ 2 | 0-1 | 0 | > 3 |
| **Net charge (abs)** | < 15 | < 10 | < 6 | > 20 |
| **Hydrophobic fraction** | < 0.45 | < 0.38 | < 0.32 | > 0.50 |

**Tier interpretation:**
- All `Excellent` → recommend for lab submission.
- All ≥ `Good`, with 1-2 only at `Minimum` → viable; note weaknesses.
- Mixed (some `Minimum`, some `Good`) → marginal; only if nothing better.
- Any `Hard Fail` → reject the individual design.

A campaign-level `ACCEPT` verdict requires **at least 3-5 designs** all reaching
the `Good` tier across the four primary metrics (ipSAE, ipTM, pLDDT, CA-RMSD).

---

## 2. Modality-Specific Overrides

Some modalities use slightly different thresholds because the engines produce
systematically different score distributions.

### VHH (nanobody)

| Metric | Minimum | Good | Excellent | Notes |
|--------|---------|------|-----------|-------|
| ipSAE (min) | > 0.3 | > 0.5 | > 0.75 | Slightly lower Excellent — VHH paratopes are smaller |
| ipTM | > 0.55 | > 0.75 | > 0.85 | Slightly higher Minimum — small interface should score confidently |
| pLDDT | > 70 | > 80 | > 90 | Same as default |
| CA-RMSD | < 3.0 | < 2.0 | < 1.5 | Tighter Minimum — VHH is rigid |

### scFv / Fab

| Metric | Minimum | Good | Excellent | Notes |
|--------|---------|------|-----------|-------|
| ipSAE (min) | > 0.3 | > 0.5 | > 0.8 | Default |
| ipTM | > 0.5 | > 0.7 | > 0.85 | Default |
| pLDDT | > 70 | > 80 | > 90 | Default |
| CA-RMSD | < 3.5 | < 2.0 | < 1.5 | Default |
| CDR-H3 length | 8-20 aa | 10-18 aa | 12-16 aa | Outside range → developability risk |

### De novo protein binder

| Metric | Minimum | Good | Excellent | Notes |
|--------|---------|------|-----------|-------|
| ipSAE (min) | > 0.35 | > 0.55 | > 0.8 | Slightly higher Minimum — de novo scaffolds need stronger interface signal |
| ipTM | > 0.55 | > 0.75 | > 0.9 | Slightly higher Minimum and Excellent |
| pLDDT | > 75 | > 85 | > 92 | De novo fold needs higher confidence than antibody framework |
| CA-RMSD | < 3.0 | < 1.8 | < 1.2 | Tighter — designed scaffold should refold consistently |
| Length | 60-150 aa | 70-130 aa | 80-120 aa | Outside range → harder to express |

---

## 3. ipSAE Asymmetry

ipSAE is directional. The skill reports both `dt_ipsae` (design → target) and
`td_ipsae` (target → design), and the min:

```
design_ipsae_min = min(dt_ipsae, td_ipsae)
asymmetry = abs(dt_ipsae - td_ipsae)
```

| Asymmetry | Interpretation | Action |
|-----------|----------------|--------|
| < 0.1 | Symmetric, balanced interface | No action; report design_ipsae_min |
| 0.1-0.3 | Mild asymmetry; one side of interface less confident | Flag to user; usually acceptable |
| > 0.3 | Significant asymmetry; partial interface | RERUN with tightened hotspots; one residue at the interface edge is likely unanchored |
| > 0.5 | Severe asymmetry; one side essentially unanchored | RERUN with completely re-derived hotspots; do not accept the design |

---

## 4. Multi-Seed Stability

When Protenix multi-seed ensemble (5 seeds) is used for refolding, compute the
seed-to-seed variance on ipTM and ipSAE:

| Variance Metric | Threshold | Action |
|-----------------|-----------|--------|
| ipTM standard deviation across 5 seeds | < 0.05 | Stable; trust the median |
| ipTM standard deviation across 5 seeds | 0.05-0.10 | Marginally stable; report range to user |
| ipTM standard deviation across 5 seeds | > 0.10 | Unstable; do not accept single-seed result |
| ipSAE standard deviation across 5 seeds | < 0.05 | Stable |
| ipSAE standard deviation across 5 seeds | > 0.10 | Unstable; consider re-running with `base_20250630` model |

The reported value in `screening_summary.json` is always the **median** across
seeds, with the variance flagged separately.

---

## 5. Polyspecificity / Cross-Reactivity Threshold

For therapeutic candidates that must avoid off-target binding:

| Cross-Reactivity Score | Interpretation | Action |
|------------------------|----------------|--------|
| < 0.1 | Specific; minimal off-target risk | ACCEPT |
| 0.1-0.3 | Possibly polyspecific; flag | Lab-submit with caveat |
| 0.3-0.5 | Likely polyspecific | RERUN with explicit polyspecificity penalty in composite |
| > 0.5 | Highly polyspecific | Reject; redesign with different hotspots |

Cross-reactivity is computed by `mcp__by-screening__screen_cross_validate` against a
canonical paralog panel (typically same-family proteins, e.g., TNF-alpha / TNF-beta /
LT-alpha for TNF-family).

---

## 6. Accept-vs-Re-Run Decision Logic (canonical)

This is the rule set encoded in `scripts/route_intent.py --mode accept-or-rerun`.
Walk top-to-bottom; first matching verdict wins.

### Step 1 — Hard reject (ESCALATE)

If **all** of the following hold across the design pool:
- p50 ipTM < 0.4
- p50 pLDDT < 60
- Pass rate < 5% (designs reaching `Minimum` tier)

→ **ESCALATE**. The epitope is likely untractable for computational design. Surface
this to the user; recommend wet-lab epitope mapping.

### Step 2 — Switch tool (SWITCH_TOOL)

If the current run is round 2+ and:
- Pass rate < 10%
- AND a different engine has not yet been tried (PXDesign → BoltzGen `protein-anything`, or vice versa; or VHH → de novo)

→ **SWITCH_TOOL**. Record the proposed alternative engine in `next_action`.

### Step 3 — Re-run (RERUN)

If pass rate is in 10-20% range, or median ipSAE is below `Good` threshold but above
`Hard Fail`:

→ **RERUN** with adjusted parameters:
- If ipSAE asymmetry > 0.3 → tighten hotspots (drop 1-2 edge residues)
- If sequence diversity is low (top designs > 80% identical) → lower diversity_alpha (BoltzGen) or increase N_sample (PXDesign)
- If pLDDT is low across the board → re-validate target fold with Protenix first; do not re-design until target is confirmed
- If CA-RMSD is high but ipTM is acceptable → adjust binder length (longer for de novo, different scaffold for antibody)
- If liability count is high → tighten the filter, request 2× more designs to compensate

Re-run budget: **at most 2 additional rounds** before escalating to SWITCH_TOOL or
ESCALATE.

### Step 4 — Accept (ACCEPT)

If:
- Pass rate ≥ 20%
- AND at least 3-5 designs reach `Good` tier on all four primary metrics
- AND no Hard Fail in the top candidates
- AND ipSAE asymmetry < 0.3 in the top candidates

→ **ACCEPT**. Recommend lab submission of top 10 (Standard) or top 50 (Production).

---

## 7. Round Limits

A single campaign is allowed **at most 3 rounds** under this skill's routing logic:

| Round | Description | Verdict Distribution (typical) |
|-------|-------------|--------------------------------|
| Round 1 (Preview or Standard) | Initial run | ACCEPT 30% / RERUN 50% / SWITCH 15% / ESCALATE 5% |
| Round 2 (RERUN with adjustments) | Second pass with narrowed hotspots / different scaffolds | ACCEPT 40% / RERUN 35% / SWITCH 20% / ESCALATE 5% |
| Round 3 (final RERUN or SWITCH) | Last chance before escalation | ACCEPT 50% / SWITCH 30% / ESCALATE 20% |

After Round 3 without ACCEPT → **ESCALATE** unconditionally. Inform the user that
the target may not be computationally tractable and recommend wet-lab follow-up.

---

## 8. Fold-Validation Threshold (Pre-Design)

Before launching design on a target without an experimental structure, Protenix
must confirm fold quality:

| Protenix Output | Action |
|-----------------|--------|
| Mean pLDDT > 80, max pLDDT > 90 | Proceed; target fold is reliable |
| Mean pLDDT 70-80 | Crop to high-confidence region (pLDDT > 80 per residue); proceed on crop |
| Mean pLDDT < 70 | Do NOT proceed with design; target is too disordered. Suggest experimental structure determination |
| ipTM < 0.7 on complex (if part of a known complex) | Inspect interface; if the predicted complex is unreliable, do not condition design on it |

---

## 9. Re-Run Criteria — Detailed

The action taken on RERUN depends on which metric is failing:

| Failing Metric | Probable Cause | Adjustment |
|----------------|----------------|------------|
| All ipTM < 0.5 | Wrong or infeasible hotspots | Re-run epitope analysis; choose a different epitope region |
| Good ipTM, low ipSAE | Partial interface; one side not anchored | Tighten hotspots; drop edge residues |
| Low pLDDT across most designs | Target fold uncertainty | Re-validate target with Protenix; consider switching to `base_20250630` checkpoint |
| Sequence converges (top designs > 80% identical) | Diversity collapse | Lower `diversity_alpha` to 0.01 (BoltzGen); or increase `N_sample` (PXDesign) |
| CA-RMSD > 3.5 Å despite good ipTM | Binder backbone not stable in refolding | Try different scaffold (antibody) or different length (de novo) |
| Many high-severity liabilities | Filter too lax or target is liability-prone (e.g., glycosylated patch) | Increase design count 2-3×, filter harder; if persistent, shift hotspots away from liability hotspots (NXS/T glycosylation, NG/NS deamidation, DG isomerization, oxidation-prone Met) |

---

## 10. Escalation to `by-failure-diagnosis`

When the verdict is RERUN with a non-obvious cause, OR when SWITCH_TOOL is chosen,
invoke `by-failure-diagnosis` to classify the failure mode and write the explicit
re-run recipe. The output of `by-failure-diagnosis` populates `next_action` in
`accept_or_rerun.json` with concrete parameter changes.

| Trigger | by-failure-diagnosis Action |
|---------|------------------------------|
| Verdict = RERUN, cause unclear | Run full failure classification (low-ipSAE / liability / fold-mismatch / scaffold-incompat / diversity-collapse) |
| Verdict = SWITCH_TOOL | Confirm the failure mode matches the new tool's strengths (e.g., switching to BoltzGen because PXDesign's MPNN stage was the failure point) |
| Verdict = ESCALATE | Produce a final causal-reasoning report (use `by-causal-reasoning`) so the user has a defensible explanation for stopping computational pursuit |

---

## 11. Defaults Summary

For the default routing decision on a well-studied target with no special
constraints:

```
Default thresholds: ipSAE > 0.3, ipTM > 0.5, pLDDT > 70, CA-RMSD < 3.5 Å
Default accept criterion: ≥ 3 designs at Good tier on all 4 metrics, pass rate ≥ 20%
Default re-run policy: 2 RERUNs allowed → SWITCH_TOOL → ESCALATE
Default tier: Preview first, then Standard if Preview pass rate ≥ 15%
```

Override only when the user explicitly requests a stricter or looser bar.
