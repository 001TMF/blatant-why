# Evidence Grading

How `by-causal-reasoning` scores evidence retrieved from the BY knowledge
graph. This document defines the **tier system**, the **precedence table**
for combining supporting and contradicting evidence, and the **anti-confirmation
checks** that prevent the skill from rubber-stamping its inputs.

The grading is deterministic. `generate_hypotheses.py` assigns tiers
mechanically from the rules below; the agent cannot override the assigned
confidence.

---

## Tier system

Every evidence entity retrieved from `by-knowledge` is classified into one of
three tiers based on its source type and replication.

### Tier 1 — HIGH

Strong evidence. Use as a foundation for HIGH-confidence claims.

| Source pattern | Why it qualifies |
|----------------|------------------|
| Peer-reviewed publication referenced in a `campaign.notes` field | External validation |
| ≥3 distinct campaigns sharing the same mechanism in `failures.json` | Empirical multi-replicate |
| A `failure_*` entity whose `root_cause` has been confirmed by a wet-lab readout (lab-calibration flag set) | Independent confirmation |
| A scaffold ranking with ≥10 campaigns all showing the same hit-rate trend | Statistical replication |

### Tier 2 — MEDIUM

Reasonable evidence. Sufficient for MEDIUM confidence on its own; combines
with Tier 1 to keep HIGH confidence.

| Source pattern | Why it qualifies |
|----------------|------------------|
| Single campaign with ≥2 replicate rounds showing the same mechanism | Replicated but single-target |
| A `failure_*` entity with `root_cause` documented but no lab confirmation | One-off post-mortem |
| Preprint (bioRxiv/ChemRxiv) referenced in a campaign note | Pre-peer-review |
| A scaffold ranking with 3-9 campaigns | Modest replication |

### Tier 3 — SPECULATIVE

Weak evidence. Insufficient alone for HIGH or MEDIUM. Only useful as
corroboration to a Tier-1 or Tier-2 entity.

| Source pattern | Why it qualifies |
|----------------|------------------|
| Single observation in one campaign with no replication | Anecdotal |
| Simulation result from one in-silico screen with no wet-lab readout | Theoretical |
| Anecdote in a campaign `notes` field with no supporting metrics | Unstructured |
| A scaffold ranking with 1-2 campaigns | Insufficient power |

---

## Precedence table

When combining supporting and contradicting evidence, follow this table. The
final confidence is the value in the cell at (best supporting tier, best
contradicting tier).

| Best supporting → / Best contradicting ↓ | Tier 1 (HIGH) | Tier 2 (MEDIUM) | Tier 3 (SPECULATIVE) | None |
|-----------------------------------------|---------------|------------------|----------------------|------|
| **None** | HIGH | MEDIUM | SPECULATIVE | refuse to emit |
| **Tier 3 (SPECULATIVE)** | HIGH | MEDIUM | SPECULATIVE | refuse to emit |
| **Tier 2 (MEDIUM)** | MEDIUM | SPECULATIVE | SPECULATIVE | refuse to emit |
| **Tier 1 (HIGH)** | SPECULATIVE | SPECULATIVE | SPECULATIVE | refuse to emit |

Key reads of the table:

- **HIGH supporting + HIGH contradicting = SPECULATIVE.** This is not an
  inconclusive label — it is a flag that there is a real conflict in the
  literature/graph, and the hypothesis should be routed to
  `by-hypothesis-debate` for adversarial pruning rather than acted on.
- **HIGH supporting + MEDIUM contradicting = MEDIUM.** Real but qualified
  conflict — downgrade one step.
- **No supporting evidence = refuse to emit.** This is the hardest rule and
  the one that distinguishes this skill from LLM-chain "AI scientist" demos.

---

## Single-source rule

A mechanism with only one supporting entity:

- ✅ HIGH confidence allowed only if that single entity is **Tier 1**.
- ✅ MEDIUM allowed if **Tier 2**.
- ⚠️ Tier 3 → SPECULATIVE.

Best practice: when a mechanism has a single Tier 1 supporter and zero
contradictors, the skill still surfaces it as HIGH, but the
`evidence_trail.md` flags the dependency on a single source so the user
knows downstream confirmation is high-value.

---

## Anti-confirmation checks

`score_hypothesis_evidence.py` runs these checks on every generated hypothesis:

1. **Entity existence.** Every cited `entity_id` is looked up via the
   `by-knowledge` MCP server. A missing entity raises `ENTITY_NOT_FOUND` and
   the hypothesis is rejected (not just downgraded). Fabricated citations are
   the most common silent failure mode for LLM-generated hypotheses.

2. **Relation match.** Each evidence record has a `claim_relation` field
   (e.g. `supports`, `partially_supports`, `contradicts`, `contradicts_partially`).
   The script checks that the cited entity actually contains the named
   mechanism in its `description`, `root_cause`, or `outcomes` field. Mismatch
   raises `RELATION_MISMATCH` and the hypothesis is downgraded one tier.

3. **Mechanism key validity.** The `mechanism` field on the hypothesis must
   be one of the canonical keys in
   [failure-mechanisms-catalog.md](failure-mechanisms-catalog.md). Unknown
   keys are rejected.

4. **Claim-as-correlation guard.** A claim sentence that does NOT name a
   canonical mechanism (or its synonym) is flagged
   `CLAIM_IS_CORRELATION_NOT_MECHANISM` and the hypothesis is rejected. See
   [failure-mechanisms-catalog.md#mechanism-vs-correlation](failure-mechanisms-catalog.md#mechanism-vs-correlation).

5. **Falsification clause present.** The `falsifiable_prediction` field is
   checked for an assay-vocabulary token (SPR, BLI, MST, DSF, HIC, AC-SINS,
   HDX-MS, mass spec, cryo-EM, ELISA, cell binding, etc.). Empty or
   non-assay text → `FALSIFICATION_MISSING_OR_VAGUE`.

6. **Confirmation-bias detector.** If the claim sentence simply restates the
   text of the input diagnosis without independent evidence retrieval, the
   `supporting_evidence` array will contain entities whose `claim_relation`
   value is `restates_input` (set by the generator when the only "evidence"
   is the diagnosis itself). Any hypothesis with that value is downgraded to
   SPECULATIVE.

Hypotheses that fail check 1, 3, or 4 are rejected outright. Failures of
checks 2, 5, and 6 result in confidence downgrade and an annotation in
`hypotheses_scored.json`.

---

## Empty graph

When `by-knowledge` returns 0 campaigns and 0 failures, the precedence table
shows refuse-to-emit in every cell. The skill does not produce
`hypotheses.json` in this case; instead it writes a single-paragraph
`evidence_trail.md` explaining that the graph must be populated first, and
exits with status `no_evidence`.

There is no fallback "best guess" output. Best-guesses without evidence are
exactly the thing this skill exists to prevent.

---

## MCP unreachable

If the `by-knowledge` MCP server cannot be contacted,
`generate_hypotheses.py` falls back to a stub-data mode using an embedded
sample knowledge graph. Stub mode produces hypotheses for development /
testing purposes only — every hypothesis emitted in stub mode is
automatically labeled SPECULATIVE regardless of supposed evidence tier, and
the `evidence_trail.md` carries a prominent banner stating the data is
synthetic.

Do NOT pass stub-mode `hypotheses.json` to `by-campaign-optimizer`.

---

## Staleness

Entries in `by-knowledge` get a `stored_at` timestamp and an `access_count`.
Entries older than 12 months with `access_count < 3` are considered stale
for the purpose of this skill: they still contribute to supporting/
contradicting counts, but are scored at one tier lower than their nominal
classification would suggest (Tier 1 → Tier 2, Tier 2 → Tier 3). This
prevents ancient single-observation entries from dominating queries when
target biology has since been refined.

Running `mcp__by-knowledge__knowledge_consolidate` periodically removes
stale entries entirely. The skill prefers a recently-consolidated graph.

---

## Lab calibration upgrade

When `--experiment-results` is passed and a hypothesis's predicted assay
matches a lab outcome that was already observed:

- If the lab confirmed the mechanism (assay readout matched the prediction),
  upgrade the hypothesis confidence by one tier.
- If the lab refuted the mechanism, downgrade by one tier AND add a synthetic
  contradicting evidence entity with `type: lab_calibration`.

Lab calibration cannot push confidence above HIGH or below SPECULATIVE; it
is a single-step modulator only.

---

## Precedence table — quick reference

Read top-to-bottom: what does the *worst* contradicting evidence tier do to
the *best* supporting evidence tier?

- HIGH support, no contradiction → **HIGH**
- HIGH support, Tier 3 contradiction → **HIGH** (Tier 3 is weak — doesn't move the needle)
- HIGH support, Tier 2 contradiction → **MEDIUM**
- HIGH support, Tier 1 contradiction → **SPECULATIVE** (real conflict, debate it)
- MEDIUM support, no contradiction → **MEDIUM**
- MEDIUM support, Tier 1 contradiction → **SPECULATIVE**
- SPECULATIVE support, anything → **SPECULATIVE**
- No support → refuse to emit

This is the rule the script enforces. The agent contributes the
*narrative* (claim sentence, falsifiable prediction); it does NOT set the
confidence value.
