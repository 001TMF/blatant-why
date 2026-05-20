# Reflection Ranking Rubric

How the reflection agent scores hypothesis proposals. This is the canonical
rubric — do not duplicate it in the orchestrator script. The orchestrator
reads weights from the front-matter table below.

---

## 1. Scoring Axes

Each proposal is scored on four axes, each in `[0.0, 1.0]`.

### 1.1 Scientific Rigor

How well does the proposal align with the experimental evidence in
`validated_findings.json`?

| Score | Criterion |
|-------|-----------|
| 0.90–1.00 | Proposal cites ≥ 3 HIGH-confidence findings; every design decision traces to experimental evidence |
| 0.70–0.89 | Proposal cites ≥ 2 HIGH or 3 MEDIUM findings; one decision relies on inference but is stated explicitly |
| 0.50–0.69 | Mix of MEDIUM and LOW confidence sources; some design choices are unsupported but reasonable |
| 0.30–0.49 | Mostly LOW-confidence sources; key decisions are speculation |
| 0.00–0.29 | Proposal contradicts a HIGH-confidence finding OR cites no sources |

**Automatic 0.0 on this axis if:** The proposal contradicts a HIGH-confidence
research finding. Flag this in `dissenting_notes` and escalate to the user.

### 1.2 Feasibility

Can the BY toolchain actually execute this strategy with the available compute?

| Score | Criterion |
|-------|-----------|
| 0.90–1.00 | Standard BoltzGen / PXDesign protocols; default scaffolds; fits within stated compute budget |
| 0.70–0.89 | Standard tools but requires non-default parameters; budget is tight but achievable |
| 0.50–0.69 | Requires specialized scaffolds, custom protocols, or pushes compute budget |
| 0.30–0.49 | Needs tooling that BY does not currently support (e.g., glycan-aware design); may require workarounds |
| 0.00–0.29 | Proposal requires tooling that does not exist; not executable as written |

**Considerations:**
- Local GPU available? Penalize proposals exceeding the available VRAM
- HPC budget set? Penalize proposals exceeding the time budget
- Tamarind cost? Penalize proposals exceeding the credit budget

### 1.3 Innovation

Does the proposal explore design space, or replay a known good answer?

| Score | Criterion |
|-------|-----------|
| 0.90–1.00 | Novel modality OR novel epitope OR novel scaffold combo; first-in-class potential |
| 0.70–0.89 | Established modality but novel epitope OR scaffold combination |
| 0.50–0.69 | Standard approach with one novel parameter (e.g., higher diversity, alt-MSA) |
| 0.30–0.49 | Largely conventional; minor variation from defaults |
| 0.00–0.29 | Identical to a previously-failed campaign OR pure replay of a published result |

**Note:** Innovation is not always good. The rubric weight (§2) determines how
much it matters for a given campaign.

### 1.4 Risk-Adjusted Confidence

Probability of meaningful campaign success, weighted by stated `key_risks`.

```
risk_adjusted_confidence = stated_confidence * (1 - normalized_risk_penalty)

stated_confidence       = proposal.confidence (the agent's self-report, in [0,1])
normalized_risk_penalty = min(1.0, 0.15 * num_unmitigated_risks)
```

Where `num_unmitigated_risks` counts entries in `key_risks` that do NOT have
a corresponding entry in `mitigation`.

| Score | Interpretation |
|-------|----------------|
| 0.80–1.00 | High confidence with all risks mitigated |
| 0.60–0.79 | Confident with most risks addressed |
| 0.40–0.59 | Moderate confidence; some unmitigated risks |
| 0.20–0.39 | Low confidence OR many unmitigated risks |
| 0.00–0.19 | Very low confidence OR severe unmitigated risk |

---

## 2. Composite Score Formula

```
composite_score = (
    W_RIGOR        * scientific_rigor
  + W_FEASIBILITY  * feasibility
  + W_INNOVATION   * innovation
  + W_RISK         * risk_adjusted_confidence
)
```

Default weights:

| Weight | Default | When to Adjust |
|--------|---------|----------------|
| `W_RIGOR` | 0.30 | Raise to 0.40 for therapeutic targets; lower to 0.20 for pure-exploration campaigns |
| `W_FEASIBILITY` | 0.25 | Raise to 0.35 when compute budget is tight; lower to 0.15 when budget is generous |
| `W_INNOVATION` | 0.20 | Raise to 0.35 when user asks for "first-in-class" or novel modality; lower to 0.10 for replication campaigns |
| `W_RISK` | 0.25 | Raise to 0.35 for high-stakes campaigns (lab submission planned); lower for exploration |

Weights MUST sum to 1.0. The orchestrator validates this on load.

### Goal-Specific Weight Presets

The `campaign_context.json` `success_criteria` field selects a preset:

| Preset | W_RIGOR | W_FEASIBILITY | W_INNOVATION | W_RISK |
|--------|---------|---------------|--------------|--------|
| `hit_rate` | 0.30 | 0.30 | 0.10 | 0.30 |
| `diversity` | 0.20 | 0.20 | 0.35 | 0.25 |
| `novelty` | 0.20 | 0.15 | 0.45 | 0.20 |
| `balanced` (default) | 0.30 | 0.25 | 0.20 | 0.25 |

---

## 3. Calibration Examples

### Example A: Well-Studied Target (PD-L1, balanced preset)

Conservative proposal (VHH + caplacizumab):
- scientific_rigor = 0.90 (3 HIGH findings cited)
- feasibility = 0.95 (standard BoltzGen protocol, default scaffolds)
- innovation = 0.30 (well-trodden)
- risk_adjusted_confidence = 0.85 (high confidence, all risks mitigated)
- **composite** = 0.30×0.90 + 0.25×0.95 + 0.20×0.30 + 0.25×0.85 = **0.7800**

Aggressive proposal (de novo bispecific):
- scientific_rigor = 0.55
- feasibility = 0.45 (bispecifics not in BoltzGen library)
- innovation = 0.95
- risk_adjusted_confidence = 0.40
- **composite** = 0.30×0.55 + 0.25×0.45 + 0.20×0.95 + 0.25×0.40 = **0.5675**

Conservative wins by 0.21 — solid margin, no tie-break needed.

### Example B: Novel IDP Target (novelty preset)

Same proposals, novelty weights (0.20 / 0.15 / 0.45 / 0.20):

Conservative composite:
- 0.20×0.90 + 0.15×0.95 + 0.45×0.30 + 0.20×0.85 = **0.6275**

Aggressive composite:
- 0.20×0.55 + 0.15×0.45 + 0.45×0.95 + 0.20×0.40 = **0.6850**

Aggressive wins under novelty preset — same proposals, different rubric weights.

### Example C: Triggers Tie-Break

Diverse: composite 0.7300
Conservative: composite 0.7100

Delta = 0.0200 < 0.0500 → tie-break applies.

Under `merge` mode (default): Diverse wins, but Conservative's strongest single
recommendation (e.g., "validate top 10 with Protenix 5-seed ensemble") is
appended to Diverse's `merged_recommendations`.

---

## 4. Per-Axis Justification Requirement

For every axis score, the reflection agent MUST emit a one-sentence
justification in the `ranking.json` output. Example:

```json
{
  "agent": "conservative",
  "scientific_rigor": 0.85,
  "scientific_rigor_justification": "Cites src_001, src_003, src_007 (3 HIGH findings); design decisions trace to validated epitope.",
  "feasibility": 0.90,
  "feasibility_justification": "Standard nanobody-anything protocol with default scaffolds; well within local GPU budget.",
  "innovation": 0.40,
  "innovation_justification": "Conventional VHH approach; epitope is well-mapped from prior work.",
  "risk_adjusted_confidence": 0.72,
  "risk_adjusted_confidence_justification": "0.78 stated confidence × (1 - 0.15×0.4 unmitigated risks) = 0.72",
  "composite_score": 0.7625,
  "rank": 1
}
```

This is non-optional. Justifications are how `by-failure-diagnosis` later
audits whether a debate was sound.

---

## 5. Conflict with Research Findings

If a proposal contradicts a HIGH-confidence finding in
`validated_findings.json`, the reflection agent MUST:

1. Set `scientific_rigor = 0.0` for that proposal
2. Add a `research_conflict` entry to `dissenting_notes`:
   ```json
   "dissenting_notes": "Proposal X recommends scFv modality, but validated_findings.json finding_005 (HIGH confidence) states the target lacks the surface area for an Fab footprint. This conflict should be resolved with the user before proceeding."
   ```
3. Set `escalate_to_user = true` in the ranking output
4. Refuse to mark this proposal as winner regardless of other scores

The orchestrator handles `escalate_to_user = true` by pausing and writing a
prominent note in `decision_summary.md`.

---

## 6. Reflection Agent Temperature

Default reflection temperature: **0.2** (favors stable, repeatable rankings).

Raise to 0.4–0.5 when:
- Target is genuinely novel (research has 0 HIGH findings)
- The user wants exploration over precedent (novelty preset)
- A prior debate produced the same winner three times and a fresh ranking is needed

Lower to 0.1 when:
- Stakes are high (lab submission imminent)
- The user has explicitly asked for the most conservative call
- A previous reflection run produced uncalibrated (all-high or all-low) scores

The orchestrator exposes `--reflection-temperature` for this control.

---

## 7. Rubric Update Protocol

If you change weights or add axes:

1. Update the table in §1.X with new axis description and scoring bands
2. Update §2 with new weights; ensure they sum to 1.0
3. Add a new entry to §3 (Calibration Examples) demonstrating the new behavior
4. Bump the `version` field in `strategy_proposal.json` and `ranking.json` schemas
5. Update `scripts/validate_proposal.py` accept-list for new fields
6. Update the directive in `references/agent-profiles.md` §2.1 to mention any new axis

Do not silently change weights. The audit trail must show the rubric in
effect at each debate.
