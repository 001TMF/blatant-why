# Fallback Decisions

What to do when the debate breaks down. Three failure modes are covered here.
The orchestrator script invokes these as labeled escalations — never silently
auto-recover.

---

## 1. All Three Proposals Score Within 5% of Each Other

**Symptom:** Composite scores look like 0.7200, 0.7050, 0.6900 — three-way
near-tie.

**Diagnosis:** Either the research is too thin to differentiate strategies,
or the rubric weights are uninformative for this campaign type.

**Decision tree:**

```
START
  |
  v
[Is W_INNOVATION weight > 0.30?]
  |
  +-- Yes --> Bias toward Aggressive may be obscuring real winner.
  |          Switch to balanced preset, recompute, re-rank.
  |
  +-- No --> Check research:
                |
                v
            [Are there >= 3 HIGH confidence findings?]
                |
                +-- Yes --> Genuine ambiguity; escalate to user.
                |          Apply tie-break mode `user_decides`.
                |          Write decision_summary.md presenting all three.
                |          Pause for user pick.
                |
                +-- No --> Research is the bottleneck.
                           Recommend running `by-research` UltraDeep.
                           Pause debate; resume after fresh research.
```

**What the orchestrator does:**

1. Write `<debate_dir>/three_way_tie.flag` (empty file as signal)
2. Add a `three_way_tie: true` field to `ranking.json`
3. Set `winner: null`
4. Write `decision_summary.md` with all three proposals' summaries and the
   reflection agent's per-axis justifications
5. Print escalation message:
   ```
   ⚠ Three-way tie: scores 0.7200, 0.7050, 0.6900 (delta < 5%).
     Apply tie-break mode `user_decides` and pause for user pick.
     OR run `by-research --depth ultradeep` and rerun debate.
   ```

**Do NOT:** Pick a winner via lexicographic order, alphabetical agent name,
or coin flip. The ambiguity is real signal — surface it.

---

## 2. All Three Proposals Score Poorly (Composite < 0.5)

**Symptom:** Best composite is 0.4800. Reflection agent reports low confidence.

**Diagnosis:** Either the target is genuinely intractable with current
tooling, or the research bundle is missing critical context.

**Decision tree:**

```
START
  |
  v
[Was research run at UltraDeep depth?]
  |
  +-- No --> Research is likely incomplete.
  |          ACTION: Recommend rerunning `by-research --depth ultradeep`.
  |          Reasons: 5x more sources, cross-species homologs, patent landscape.
  |
  +-- Yes --> Research is thorough but signal is weak.
                |
                v
            [Is the target a known-hard class? (IDP, surface, glycoprotein)]
                |
                +-- Yes --> Recommend specialized tooling.
                |          E.g., conformational ensemble for IDPs.
                |          May require external collaborators or wait for tool updates.
                |
                +-- No --> Suggest preview campaign anyway.
                           Even low-confidence preview generates signal.
                           Aggressive proposal may be useful as a 5-design probe.
```

**What the orchestrator does:**

1. Write `<debate_dir>/low_confidence.flag`
2. Add `low_confidence: true` to `ranking.json`
3. Still pick a winner (rank-1 by composite) BUT mark `confidence: "low"` in `decision_summary.md`
4. Add prominent warning to `decision_summary.md`:
   ```
   ⚠ ALL PROPOSALS SCORED < 0.5. The winner is the best of a weak set.
   
   Recommended actions BEFORE executing:
   1. Run a 5-design preview campaign at the lowest tier
   2. If preview fails (zero hits), do not escalate to standard tier
   3. Consider re-running `by-research` with UltraDeep depth
   ```
5. Suggest preview-tier override in `campaign_config.yaml` regardless of
   what the winning proposal said about tier

**Do NOT:** Hide the low-confidence flag. The downstream `by-campaign-manager`
must see it to override the tier setting.

---

## 3. Reflection Agent Crashes or Returns Malformed Output

**Symptom:** `Task()` for reflection returns an error, times out, or produces
JSON that fails schema validation.

**Diagnosis:** Usually one of:
- Token limit hit (proposals are too verbose)
- Reflection agent confused itself (low-quality directive interpretation)
- Genuine transient error (rare; retry usually works)

**Decision tree:**

```
START
  |
  v
[Is the failure mode: ValidationError on ranking.json?]
  |
  +-- Yes --> Retry once with stricter directive.
  |          Append "Output MUST be valid JSON matching the schema in SKILL.md"
  |          to the reflection prompt and re-spawn.
  |          On second failure, fall through to manual ranking.
  |
  +-- No --> [Is the failure mode: timeout / no response?]
                |
                +-- Yes --> Truncate proposal rationale fields to 500 tokens.
                |          Re-spawn with truncated input.
                |          On second failure, fall through to manual ranking.
                |
                +-- No --> [Is the failure: hard error from Task() infrastructure?]
                              |
                              +-- Yes --> Wait 30 sec, retry once.
                              |          Likely transient.
                              |
                              +-- No --> Unknown failure mode.
                                         Fall through to manual ranking.
```

**Manual ranking fallback:**

If reflection has failed twice, the orchestrator:

1. Writes a `manual_ranking_required.flag` file
2. Computes per-axis scores **algorithmically** from each proposal's stated
   fields (no LLM call):
   - `scientific_rigor` = `0.3 * (HIGH_citations / 3) + 0.4 * (MEDIUM_citations / 3) + 0.3 * (1 if contradicts_HIGH else 0)`
   - `feasibility` = `1.0 if tier=='preview' else 0.85 if tier=='standard' else 0.65 if tier=='production'`
   - `innovation` = `0.3 if conventional_modality_and_scaffold else 0.7 if novel_one else 0.95 if novel_two`
   - `risk_adjusted_confidence` = `proposal.confidence * (1 - 0.15 * unmitigated_risk_count)`
3. Applies default balanced weights
4. Picks winner by composite, writes `ranking.json` with
   `"fallback_method": "algorithmic"` field
5. Adds prominent warning to `decision_summary.md`:
   ```
   ⚠ REFLECTION AGENT FAILED. Ranking was computed algorithmically from
   proposal metadata. Review the per-axis scores manually before approving.
   ```

**Do NOT:** Re-spawn the reflection agent more than twice. Persistent failure
likely indicates a deeper problem — escalate to user instead of looping.

---

## 4. A Hypothesis Agent Crashes Mid-Debate

**Symptom:** Only 2 of 3 proposals returned. Validation passes on both.

**Decision tree:**

```
[Did >= 2 proposals return validly?]
  |
  +-- Yes (2 of 3) --> Continue with reflection on 2 proposals.
  |                   Note in ranking.json: `"agents_returned": 2`.
  |                   This is acceptable; debate still has variance.
  |
  +-- No (0 or 1) --> Halt debate. Cannot meaningfully rank one proposal.
                      Re-spawn missing agents. On second failure of same
                      agent, drop it and proceed with the remaining 2.
                      Never proceed with only 1 proposal.
```

The orchestrator records dropped agents in `debate_log.jsonl` so the
audit trail is complete.

---

## 5. Winning Proposal Contradicts HIGH Research Finding

This is handled by the reflection rubric (see
[ranking-rubric.md](ranking-rubric.md) §5), not as a fallback. The reflection
agent will:

1. Set `scientific_rigor = 0.0` for the contradicting proposal
2. Set `escalate_to_user = true`
3. Refuse to mark the proposal as winner

The orchestrator pauses on `escalate_to_user = true`. No silent override.

---

## 6. User Has Strong Preference Conflicting with Winner

**Scenario:** User said *"I want VHH"* in conversation, but debate picks de
novo binder.

**Decision tree:**

```
[Is the user's preference in campaign_context.json as a hard constraint?]
  |
  +-- Yes (constraint) --> Filter proposals BEFORE reflection.
  |                       Any proposal violating the constraint is dropped.
  |                       If all proposals are dropped, halt and ask user.
  |
  +-- No (preference) --> Reflection sees the preference as a prior.
                          Winner may still differ. Present both:
                          "Debate recommends X. You preferred Y.
                           Reasons debate picked X: ... 
                           Do you want to override?"
```

This is NOT a fallback in the failure sense — it's a routine handoff back to
the user. But it deserves a section because it's the most common
"surprise" outcome of a debate.
