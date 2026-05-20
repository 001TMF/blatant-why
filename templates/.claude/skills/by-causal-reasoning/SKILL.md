---
id: "skill_6f0661a7e4024d0aab430f1b236e282f"
name: "by-causal-reasoning"
display-name: "BY Causal Reasoning"
short-description: "Generate ranked mechanistic hypotheses for protein-design failure patterns, each anchored in knowledge-graph evidence with confidence tiers and falsifiable predictions. Use when a campaign has been statistically diagnosed and you need to explain WHY designs failed before committing the next round of compute."
category: "analysis"
keywords: "causal reasoning, mechanistic hypothesis, root cause analysis, evidence grading, failure mechanisms, knowledge graph, hypothesis ranking, falsifiable prediction, parsimony, post-mortem"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools:
  - "mcp__by-knowledge__knowledge_query_similar"
  - "mcp__by-knowledge__knowledge_scaffold_rankings"
  - "mcp__by-knowledge__knowledge_get_recommendations"
  - "mcp__by-knowledge__knowledge_store_failure"
---

# BY Causal Reasoning Skill

Most "AI scientist" demos fake reasoning by chaining LLM calls and calling the
chain a hypothesis. This skill does the opposite: it constrains the LLM with
**structured evidence retrieved from the BY knowledge graph** and forces every
claim to cite an existing entity with a defined evidence tier. The output is a
short, ranked list of mechanistic hypotheses — each one falsifiable, each one
traceable to a campaign, paper, or prior failure record.

It sits between **statistical diagnosis** (which says *which* features
discriminate PASS from FAIL) and **campaign optimization** (which spends new
compute). Without this step, the optimizer can only tweak thresholds; with it,
the optimizer can target the underlying mechanism.

---

## When to Use This Skill

Use this skill when:

- ✅ **`by-failure-diagnosis` has produced a discriminating-features ranking** and you need to translate statistical signals into mechanistic claims before the next round.
- ✅ **`by-epitope-analysis` is available** so structural context (topology, hotspot residues, druggability) can be merged with statistical signals.
- ✅ **You are about to call `by-campaign-optimizer`** for round N+1 — the optimizer's parameter changes should target a named mechanism, not a vibe.
- ✅ **A campaign shows an unexpected (non-trivial) pattern** — e.g. high ipSAE designs are failing at the lab stage, or pass rate dropped vs the prior round with no parameter change.
- ✅ **The user explicitly asks** "why are my designs failing at this *mechanism*?", "what's the underlying cause?", or "rank possible explanations".
- ✅ **You have access to `by-knowledge` data** — querying without a populated graph yields hypotheses with no evidence, which violates the skill contract.

Do NOT use this skill when:

- ❌ **As a substitute for actually running experiments.** Hypotheses are pointers to experiments, not conclusions. If the user asks "is this the cause?", the answer is *"the falsifiable prediction is X — run that assay to confirm"*, not *"yes"*.
- ❌ **Without evidence citations.** Every claim must reference at least one knowledge-graph entity (`campaign_<id>` or `failure_<id>`). A "hypothesis" with no evidence is a guess — flag it as SPECULATIVE or refuse to emit it.
- ❌ **To generate more than 5 hypotheses.** Parsimony is enforced: 3-5 is the cap. More than 5 means the agent is laundering uncertainty as breadth. If the diagnosis genuinely supports more candidates, that is a signal to call `by-hypothesis-debate` for adversarial pruning, not to inflate the list.
- ❌ **For per-residue redesign rationale.** That is structural, not statistical — use `by-epitope-analysis` instead.
- ❌ **When the campaign has fewer than 30 scored designs.** Statistical signals are too noisy; the hypotheses will not be reliably evidenced.
- ❌ **For pre-campaign target selection.** That is `by-research` territory; this skill explains past failures, not future opportunities.
- ❌ **When the knowledge graph is empty (0 campaigns, 0 failures recorded).** The skill cannot ground hypotheses in evidence — refuse to run, ask user to populate `by-knowledge` first.

---

## Quick Start

Typical invocation: feed the diagnosis + epitope outputs from a campaign,
let the skill query `by-knowledge` for evidence, and emit ranked hypotheses.

```bash
python3 scripts/generate_hypotheses.py \
  --diagnosis campaigns/tnf/run01/diagnosis.json \
  --epitope campaigns/tnf/run01/hotspots.json \
  --target "TNF-alpha" \
  --modality "VHH" \
  --max-hypotheses 4 \
  --out campaigns/tnf/run01/hypotheses.json \
  --trail campaigns/tnf/run01/evidence_trail.md
```

Expected console output:

```
✓ Loaded diagnosis: 9 features tested, 3 significant
✓ Loaded epitope: 6 hotspots, topology=flat, druggability=moderate
✓ Queried knowledge graph: 12 similar campaigns, 4 matching failures
✓ Generated 4 hypotheses (1 HIGH, 2 MEDIUM, 1 SPECULATIVE)
✓ Wrote campaigns/tnf/run01/hypotheses.json
✓ Wrote campaigns/tnf/run01/evidence_trail.md
```

The resulting `hypotheses.json` is a JSON array of at most 5 ordered
hypotheses; each carries claim text, supporting + contradicting evidence with
entity IDs, a confidence label, and a falsifiable prediction.

To validate hypotheses after generation (verify every cited entity exists in
the graph and the evidence tier was assigned correctly):

```bash
python3 scripts/score_hypothesis_evidence.py \
  --hypotheses campaigns/tnf/run01/hypotheses.json \
  --out campaigns/tnf/run01/hypotheses_scored.json
```

---

## Installation

| Software | Version | License | Commercial Use | Installation Command |
|----------|---------|---------|----------------|---------------------|
| Python | ≥3.10 | PSF | ✅ Permitted | preinstalled |
| `mcp` SDK | ≥1.0 | MIT | ✅ Permitted | `pip install mcp` |
| `pydantic` (optional, schema validation) | ≥2.0 | MIT | ✅ Permitted | `pip install pydantic` |
| `jsonschema` (optional, output validation) | ≥4.0 | MIT | ✅ Permitted | `pip install jsonschema` |

**License Compliance:** All packages permit commercial use in AI applications.

**System requirements:** No GPU, no internet. The skill is CPU-only and reads
from the locally persisted `by-knowledge` JSON store. Runtime is under a few
seconds for thousands of recorded campaigns.

**Dependencies on other BY services:** The `by-knowledge` MCP server must be
running for the generation script's evidence retrieval to work. If it is not,
`generate_hypotheses.py` falls back to a stub-data mode (clearly labeled in
the output) — but in stub mode the hypotheses are NOT evidence-grounded and
must be flagged SPECULATIVE before passing to any downstream skill.

---

## Inputs

**Required:**
- **Diagnosis output** (`diagnosis.json` from `by-failure-diagnosis`):
  - `total_designs`, `passed`, `failed`, `pass_rate`
  - `discriminating_features[]` — feature names sorted by adjusted p-value
  - Each feature must include `effect_size`, `passed_mean`, `failed_mean`
- **Target name** (string) — used as the keyword anchor for `by-knowledge` queries
- **Modality** — one of `antibody`, `nanobody`, `VHH`, `scFv`, `de_novo`, `binder`
- **Access to `by-knowledge`** — the MCP server must be reachable, OR a local copy of `campaigns.json` + `failures.json` must be passed via `--knowledge-dir`

**Strongly recommended:**
- **Epitope output** (`hotspots.json` from `by-epitope-analysis`):
  - Provides structural context: `topology`, `druggability`, hotspot residue list
  - Without this, structural hypotheses (steric, electrostatic, aggregation) cannot be evidenced from the interface geometry

**Optional:**
- **Lab results** (`experiment_results.json` from `by-experiment-results`, when available):
  - Real-world calibration: which designs that passed in-silico screening also passed (or failed) at the bench
  - Lets the skill distinguish "the metric is wrong" from "the metric is right but the mechanism is missed"
- **Prior hypothesis files** — earlier rounds' `hypotheses.json` to detect repeated mechanisms (the optimizer should already have addressed them)
- **`--max-hypotheses`** — hard cap, default 4, never above 5 (parsimony enforced)
- **`--include-speculative`** — include Tier 3 evidence claims (default off; require user opt-in)

See [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md)
for the canonical mechanism set and which inputs each mechanism requires.

---

## Outputs

All outputs are written to the campaign directory at
`campaigns/<target>/<campaign_id>/`:

| File | Format | Purpose |
|------|--------|---------|
| `hypotheses.json` | JSON array | Ranked hypotheses with evidence citations (downstream contract) |
| `evidence_trail.md` | Markdown | Human-readable narrative: queries run, evidence retrieved, contradictions flagged |
| `hypotheses_scored.json` | JSON array | Validation artifact from `score_hypothesis_evidence.py` (annotated evidence tiers) |

### `hypotheses.json` schema (downstream-critical)

Each entry has exactly these fields:

| Field | Type | Description |
|-------|------|-------------|
| `rank` | int | 1-indexed, sorted by confidence desc, then evidence count desc |
| `claim` | string | Single-sentence mechanistic statement (NOT a correlation) |
| `mechanism` | string | Canonical name from the catalog (e.g. `hydrophobic_aggregation`, `steric_clash`) |
| `confidence` | enum | `HIGH` / `MEDIUM` / `SPECULATIVE` (matches BY taxonomy) |
| `supporting_evidence` | array | One or more `{entity_id, type, claim_relation, weight}` records |
| `contradicting_evidence` | array | Same shape, may be empty; non-empty triggers confidence downgrade |
| `falsifiable_prediction` | string | The next experiment that would confirm or refute |
| `recommended_next_action` | string | Skill to call next (e.g. `by-hypothesis-debate`, `by-campaign-optimizer`) |

Full JSON Schema in
[references/hypothesis-output-schema.md](references/hypothesis-output-schema.md).

**Downstream consumers** of `hypotheses.json`:
- `by-hypothesis-debate` — adversarial ranking of the top candidates
- `by-campaign-optimizer` — translates the top hypothesis into round-N+1 parameter changes
- `by-knowledge` — `knowledge_store_failure` records the confirmed root cause once a prediction is run

---

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — without a concrete failure pattern to explain,
the skill cannot ground its queries and will produce vacuous hypotheses.

1. **Which failure pattern are you trying to explain? Point me at the diagnosis output file.** (ASK THIS FIRST)
   - Expected: a path to a `diagnosis.json` produced by `by-failure-diagnosis`, OR a description of the discriminating features (e.g. *"failed designs have lower pLDDT and higher hydrophobic_fraction"*).
   - If no diagnosis exists yet → route to `by-failure-diagnosis` first; this skill cannot reason from raw screening output.
2. **Do you have the matching epitope analysis output?** (`hotspots.json`)
   - Without structural context, structural hypotheses are downgraded to SPECULATIVE. Strongly preferred.
3. **Is the `by-knowledge` graph populated for this target class?**
   - If <3 prior campaigns exist for the modality+target-class combination, hypotheses will rely on the catalog only; warn the user that evidence will be thin.
4. **Has a prior round of this campaign already produced hypotheses?**
   - If yes, point the script at the prior `hypotheses.json` so repeated mechanisms can be flagged (the optimizer was supposed to address them).
5. **Are lab results available?** (`experiment_results.json`)
   - Lab calibration upgrades hypothesis confidence by one tier when in-silico signal matches bench outcome.
6. **What is the hypothesis count limit?**
   - Default 4. Hard cap 5. Never override above 5 — that signals the skill should call `by-hypothesis-debate` for pruning.
7. **What downstream action is planned?**
   - If next step is `by-campaign-optimizer`, prioritize mechanisms with concrete parameter levers. If next step is lab submission, prioritize mechanisms with cheap falsification assays.

---

## Standard Workflow

🚨 **MANDATORY: USE THE SCRIPTS EXACTLY AS SHOWN — DO NOT WRITE INLINE HYPOTHESIS NARRATIVES** 🚨

The skill is split deliberately: mechanical retrieval and scoring are handled by
the scripts; **only the per-hypothesis claim sentence and falsifiable prediction
are generated by the LLM at runtime**. That separation is what makes this skill
different from a chain-of-LLM-calls demo.

### Step 1: Verify inputs

Confirm the diagnosis file exists and has at least one significant
discriminating feature (adjusted p < 0.05). If not, the skill exits early:
without a statistical signal, mechanistic hypotheses are unfounded.

```bash
ls campaigns/<target>/<campaign_id>/diagnosis.json
jq '.discriminating_features | length' campaigns/<target>/<campaign_id>/diagnosis.json
```

✅ **VERIFICATION:** Expect ≥1 entries with `adjusted_p_value < 0.05`. If 0, route to `by-failure-diagnosis` for re-run with more designs.

### Step 2: Generate candidate hypotheses

Run `generate_hypotheses.py`. It does the following deterministic work:

1. Reads `diagnosis.json` and matches discriminating features against the
   diagnostic-signature column in
   [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md).
2. For each candidate mechanism, queries `by-knowledge` via
   `mcp__by-knowledge__knowledge_query_similar` and (when matching failures
   exist) by direct keyword scan of `failures.json`.
3. Scores each candidate via the precedence table in
   [references/evidence-grading.md](references/evidence-grading.md) to assign a
   confidence tier.
4. Ranks candidates by `(confidence_tier, supporting_evidence_count,
   contradicting_evidence_count_inverse)`.
5. Emits a JSON skeleton with all evidence citations populated and a Jinja-like
   prompt template embedded for the agent to fill in the `claim` and
   `falsifiable_prediction` fields.

```bash
python3 scripts/generate_hypotheses.py \
  --diagnosis campaigns/<target>/<campaign_id>/diagnosis.json \
  --epitope campaigns/<target>/<campaign_id>/hotspots.json \
  --target "<target>" \
  --modality "<modality>" \
  --max-hypotheses 4 \
  --out campaigns/<target>/<campaign_id>/hypotheses.json \
  --trail campaigns/<target>/<campaign_id>/evidence_trail.md
```

✅ **VERIFICATION:** Expect `✓ Generated N hypotheses` where N ≤ 5. Each hypothesis must have ≥1 supporting evidence entry.

### Step 3: Validate evidence citations

Before passing the file downstream, verify every cited entity exists in the
knowledge graph and the relation type the claim asserts is actually present in
that entity.

```bash
python3 scripts/score_hypothesis_evidence.py \
  --hypotheses campaigns/<target>/<campaign_id>/hypotheses.json \
  --out campaigns/<target>/<campaign_id>/hypotheses_scored.json
```

✅ **VERIFICATION:** Every hypothesis ends with `evidence_check: OK`. If `evidence_check: ENTITY_NOT_FOUND` appears, regenerate — a fabricated citation is worse than no citation.

### Step 4: Hand off downstream

Pipe to one of:
- `by-hypothesis-debate` — when ≥2 hypotheses tied at the top confidence tier
- `by-campaign-optimizer` — when one hypothesis dominates and has a concrete parameter lever
- `by-knowledge` (`knowledge_store_failure`) — after a falsifiable prediction has been run and confirmed

❌ **DON'T:**
- ❌ Write claim sentences inline without running `generate_hypotheses.py` — that produces unevidenced hypotheses.
- ❌ Increase `--max-hypotheses` above 5 — parsimony is the whole point.
- ❌ Skip Step 3 — fabricated entity IDs are the most common silent failure mode.
- ❌ Use this skill's output as a confirmed root cause. Confirmed means a falsifiable prediction was run AND the result matched.

---

## When Scripts Fail

Use the standard hierarchy. The most common modes for this skill:

1. **Fix and Retry (90%)** — `by-knowledge` MCP server not running → start it (`uv run mcp__by-knowledge`) and re-run. Missing `pydantic` → `pip install pydantic`.
2. **Modify Script (5%)** — Add a new mechanism to the catalog → edit `references/failure-mechanisms-catalog.md` AND the catalog parsing in `generate_hypotheses.py`. Both must agree on mechanism keys.
3. **Use as Reference (4%)** — A custom mechanism not in the catalog → read the catalog and `evidence-grading.md`, write one ad-hoc hypothesis by hand following the schema, then run `score_hypothesis_evidence.py` to validate.
4. **Write from Scratch (1%)** — Only if the entire `by-knowledge` graph is broken and cannot be repaired. In that case, output a single SPECULATIVE hypothesis and route to `by-hypothesis-debate` for human-in-the-loop ranking.

---

## Decision Points

### Confidence tier assignment

| Supporting Tier | Contradicting Tier | Final Confidence | Notes |
|-----------------|--------------------|------------------|-------|
| HIGH (≥3 campaigns OR peer-reviewed) | none | HIGH | Strong claim |
| HIGH | MEDIUM | MEDIUM | Downgrade one |
| HIGH | HIGH | SPECULATIVE | Real conflict, debate |
| MEDIUM | none | MEDIUM | Standard case |
| MEDIUM | MEDIUM | SPECULATIVE | Unclear |
| SPECULATIVE | any | SPECULATIVE | Cannot upgrade |
| none | any | refuse to emit | No evidence → no hypothesis |

Full precedence table at
[references/evidence-grading.md](references/evidence-grading.md).

### Mechanism prioritization

When multiple mechanisms have the same confidence tier, rank by:
1. **Falsifiability cost** — cheaper experiments first (in-silico re-scoring < ELISA < SPR < cell assay)
2. **Parameter actionability** — mechanisms the optimizer can directly address rank higher
3. **Evidence count** — more independent supporting entities first

### When to escalate to `by-hypothesis-debate`

- Top two hypotheses both HIGH confidence with overlapping mechanisms
- Top hypothesis SPECULATIVE because of HIGH-vs-HIGH conflict
- User asks for adversarial pressure on a single hypothesis

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| Empty knowledge graph (0 campaigns, 0 failures) | Skill called before any prior campaigns recorded | Refuse to emit hypotheses; ask user to populate via `by-knowledge` first | [references/evidence-grading.md](references/evidence-grading.md#empty-graph) |
| Single-source claim | Only one campaign in the graph matches the mechanism | Downgrade to SPECULATIVE; corroboration requires ≥2 independent entities (or 1 Tier-1 entity) | [references/evidence-grading.md](references/evidence-grading.md#single-source-rule) |
| Confirmation bias (LLM agrees with the diagnosis) | Claim sentence parrots the diagnosis input without independent evidence | Script forces evidence retrieval before claim generation; `score_hypothesis_evidence.py` flags claims without ≥1 supporting entity | [references/evidence-grading.md](references/evidence-grading.md#anti-confirmation-checks) |
| Confidence inflation | Agent labels every hypothesis HIGH | The script assigns confidence mechanically from the precedence table — agent cannot override | [references/evidence-grading.md](references/evidence-grading.md#precedence-table) |
| Hypothesis count creep | Output has 6+ hypotheses | Hard cap of 5 enforced by `generate_hypotheses.py`; emit ≥6 only with explicit `--allow-overflow` flag, which forces a `by-hypothesis-debate` handoff | [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md#parsimony-rule) |
| Missing falsification clause | `falsifiable_prediction` field is empty or aspirational ("more research needed") | Script validates the field is a runnable assay (regex match against assay-verb vocabulary); empty → fails Step 3 | [references/hypothesis-output-schema.md](references/hypothesis-output-schema.md#falsifiable-prediction-rules) |
| Claim/evidence mismatch | The claim cites entity X but X is about a different mechanism | `score_hypothesis_evidence.py` checks claim mechanism against entity `mechanism` field; mismatch flagged as `RELATION_MISMATCH` | [references/hypothesis-output-schema.md](references/hypothesis-output-schema.md#evidence-record-shape) |
| Citing non-existent KG entity IDs | LLM invented a `campaign_<random>` ID that isn't in the graph | `score_hypothesis_evidence.py` queries every cited ID via the knowledge MCP server; missing → `ENTITY_NOT_FOUND`. Hypothesis rejected outright | [references/hypothesis-output-schema.md](references/hypothesis-output-schema.md#entity-id-rules) |
| Non-mechanistic claims (correlations dressed as mechanisms) | Claim says "designs with feature X failed", but does not say WHY | Catalog uses canonical mechanism keys; claim sentence must reference one of them. The skill rejects claims that are pure restatements of statistics | [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md#mechanism-vs-correlation) |
| Missing assay context | `falsifiable_prediction` says "test it" with no assay named | Predictions must name a specific assay (SPR, BLI, MST, DSF, HIC, AC-SINS, mass spec, ELISA, cell binding, etc.) | [references/hypothesis-output-schema.md](references/hypothesis-output-schema.md#assay-vocabulary) |
| `by-knowledge` MCP server unreachable | Server crashed or not started | Restart `by-knowledge`; the script's stub-data fallback labels everything SPECULATIVE and is for development only | [references/evidence-grading.md](references/evidence-grading.md#mcp-unreachable) |
| Stale knowledge graph (old data dominates queries) | Campaigns from >12 months ago skew the keyword score | Run `mcp__by-knowledge__knowledge_consolidate` to prune stale low-access entries, then re-run hypothesis generation | [references/evidence-grading.md](references/evidence-grading.md#staleness) |
| Multiple campaigns under same target with different name spellings | Keyword match misses some (e.g. `TNF-alpha` vs `TNFα` vs `TNF_alpha`) | Pass the canonical normalized form via `--target`; the script also tries common variants and warns on apparent splits | [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md#target-normalization) |
| Diagnosis features not in the catalog | A custom feature like `disulfide_count` discriminates PASS/FAIL but no mechanism maps to it | Add a row to the catalog (or use `--catalog-overlay extra.yml`) before regenerating; emitting a hypothesis from an unmapped feature would skip mechanism grounding | [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md#extending-the-catalog) |

---

## Best Practices

- 🚨 **CRITICAL: Never emit a hypothesis without ≥1 supporting evidence entity.** This is the single rule that separates this skill from "AI scientist" hallucination demos.
- 🚨 **CRITICAL: Cap hypotheses at 5.** Parsimony is the contract. If 6+ mechanisms look plausible, that is a debate task, not a list task.
- ✅ **REQUIRED: Run `score_hypothesis_evidence.py` after every generation.** Catches fabricated entity IDs and relation mismatches before downstream consumers see them.
- ✅ **REQUIRED: Match diagnosis features to canonical mechanism keys.** Don't invent mechanisms — extend the catalog if needed.
- ✅ Prefer Tier-1 (peer-reviewed or multi-campaign) evidence; Tier-3 alone never reaches HIGH confidence.
- ✅ Write claim sentences in past or present indicative ("designs aggregate due to..."), never aspirational ("might possibly indicate...").
- ✅ Make every `falsifiable_prediction` runnable: name the assay, name the readout, name the threshold.
- ✅ Cite contradicting evidence as well as supporting — the confidence tier reflects the conflict, not the supporting count alone.
- ✨ Optional: when lab data is available, upgrade matching hypotheses by one tier per the lab-calibration rule.
- ❌ DON'T write claims like "feature X discriminates PASS/FAIL". That is a correlation, not a mechanism.
- ❌ DON'T re-emit a hypothesis the optimizer already addressed in a prior round without flagging it as `REPEATED:` in the claim.

---

## Suggested Next Steps

Pick the downstream skill based on the shape of `hypotheses.json`:

- **`by-hypothesis-debate`** — when ≥2 hypotheses share the top confidence tier OR when conflicting evidence drove a SPECULATIVE label. Debate spawns competing strategy agents and runs adversarial ranking before any GPU compute is committed.
- **`by-campaign-optimizer`** — when one hypothesis dominates AND has a clear parameter lever (e.g. lower temperature, swap scaffold, restrict CDR length). The optimizer reads `recommended_next_action` from the top hypothesis and translates it into a round-N+1 parameter delta.
- **`by-experiment-results`** — when the falsifiable prediction is cheap enough to run at the bench. Match the predicted assay to the lab queue; lab outcome closes the loop.
- **`by-knowledge` (`knowledge_store_failure`)** — once a prediction has been run and the mechanism confirmed, record it so future campaigns inherit the finding.
- **`by-research`** — only if hypothesis generation surfaced a target-biology gap (e.g. epitope conformational dynamics not characterized in literature). Re-research, then re-run this skill.

Each downstream skill expects `hypotheses.json` to validate against the schema
in [references/hypothesis-output-schema.md](references/hypothesis-output-schema.md);
that schema is the contract.

---

## Related Skills

**Upstream (run before this):**
- `by-screening` — produces PASS/FAIL labels and per-design features
- `by-failure-diagnosis` — produces `diagnosis.json` (statistical signals)
- `by-epitope-analysis` — produces `hotspots.json` (structural context)
- `by-experiment-results` — optional, produces lab calibration
- `by-knowledge` — must be populated with prior campaigns and failures

**Downstream (run after this):**
- `by-hypothesis-debate` — adversarial ranking when multiple hypotheses tie
- `by-campaign-optimizer` — round-N+1 parameter changes targeting the top mechanism
- `by-knowledge` (`knowledge_store_failure`) — record confirmed mechanisms

**Alternative / complementary:**
- `by-research` — for *target* uncertainty (literature gaps), not *design* uncertainty
- `by-failure-diagnosis` — answers "which features matter"; this skill answers "what mechanism is behind those features"

---

## References

**Detailed documentation (in `references/`):**
- [`failure-mechanisms-catalog.md`](references/failure-mechanisms-catalog.md) — Canonical list of biologic-design failure mechanisms with diagnostic signatures (steric clash, electrostatic mismatch, hydrophobic aggregation, cryptic epitope, polyspecificity, slow on-rate, allosteric perturbation, disulfide/PTM issues). For each: telltale in-silico features + recommended diagnostic assays.
- [`evidence-grading.md`](references/evidence-grading.md) — Tier system (HIGH / MEDIUM / SPECULATIVE), how to combine supporting + contradicting evidence, precedence table, anti-confirmation rules.
- [`hypothesis-output-schema.md`](references/hypothesis-output-schema.md) — Full JSON Schema for `hypotheses.json` including required fields, allowed confidence values, evidence-record shape, falsifiable-prediction rules. Two worked examples (HIGH-confidence and SPECULATIVE).

**Scripts (in `scripts/`):**
- `generate_hypotheses.py` — Mechanical query → score → rank pipeline. Emits hypotheses with evidence pre-populated; the agent fills only the claim sentence and falsifiable prediction from the embedded prompt template.
- `score_hypothesis_evidence.py` — Post-generation validator. Verifies every cited entity exists, the claim's mechanism matches the entity's mechanism field, and assigns the evidence tier per the precedence table.

**Related BY skills:**
- [`by-knowledge` SKILL.md](../by-knowledge/SKILL.md) — evidence source
- [`by-failure-diagnosis` SKILL.md](../by-failure-diagnosis/SKILL.md) — statistical input
- [`by-epitope-analysis` SKILL.md](../by-epitope-analysis/SKILL.md) — structural input
- [`by-hypothesis-debate` SKILL.md](../by-hypothesis-debate/SKILL.md) — adversarial downstream
- [`by-campaign-optimizer` SKILL.md](../by-campaign-optimizer/SKILL.md) — parameter-change downstream
- [`by-research` SKILL.md](../by-research/SKILL.md) — exemplar for confidence taxonomy

**External references** (for the catalog and grading rubrics):
- IEDB and AbDab antibody developability metadata
- Published guidance on antibody developability liabilities (e.g. hydrophobic patches, charge variants, PTM hotspots) — citations in [references/failure-mechanisms-catalog.md](references/failure-mechanisms-catalog.md)
- Falsifiability framing follows the standard scientific method literature; the skill enforces it operationally rather than philosophically.

**License:** All third-party packages permit commercial use in AI applications. Skill content is internal to BY.
