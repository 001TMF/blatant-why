---
id: "skill_7aefc997cd234d20aa9d4045314703c9"
name: "by-hypothesis-debate"
display-name: "BY Hypothesis-Debate"
short-description: "Adversarial multi-agent strategy selection for protein/antibody design campaigns. Spawns competing hypothesis agents (conservative / aggressive / diverse), then ranks proposals with a reflection agent before committing GPU compute. Use when starting a novel-target campaign, when research findings are contradictory, or when multiple design modalities are viable."
category: "strategy"
keywords: "hypothesis debate, strategy selection, multi-agent, adversarial ranking, design strategy, novel target, BoltzGen, PXDesign, campaign planning"
version: "1.0"
last-updated: "2026-05-20"
---

# BY Hypothesis-Debate Skill

Picking the wrong design strategy on a novel target wastes a GPU day. This skill
forces an explicit, structured debate **before** any compute is spent: three
hypothesis agents propose competing strategies in parallel, then a reflection
agent ranks them against a fixed rubric. The winner becomes the campaign config.

The pattern is borrowed from adversarial ML and red-team review — it works
because three independently-constrained agents will surface failure modes that
a single planner misses, and the reflection step exposes hidden assumptions
that would otherwise propagate into the campaign plan.

---

## When to Use This Skill

✅ **Use this skill when:**
- Starting a campaign against a **novel target** (0–1 PDB structures, no SAbDab antibodies, <10 papers)
- Research findings have `CONTRADICTED` confidence (sources disagree on epitope, modality, or scaffold)
- Multiple **viable modalities** are on the table (VHH vs scFv vs de novo binder) and the user has not pinned one
- The user explicitly says *"compare approaches"*, *"explore options"*, *"which strategy would you pick"*
- Target difficulty is rated `novel` or `exploratory` by `by-research`
- A previous campaign against the same target failed with hit rate < 5% (this skill helps replan, not retry)

❌ **Do NOT use this skill when:**
- Target is well-studied with a clear precedent (e.g., TNF-alpha, PD-L1, HER2) → use `by-campaign-manager` directly
- The user has **already specified** modality, scaffolds, and tier — debating wastes turns
- Running a **preview / feasibility** campaign — overhead of 3-agent debate is not worth it for 5–10 designs
- Iterating on a previously-approved campaign (round 2, 3, … reuse the prior strategy)
- The campaign is gated on lab submission — debate occurs upstream of `/by:approve-lab`, not after

---

## Quick Start

Invoke from the orchestrator (main session) **after** `by-research` has written
`research.md` and `recommended_hotspots.json` to the campaign directory:

```bash
python3 scripts/orchestrate_debate.py \
  --research-dir campaigns/IL23R/campaign_20260520_001/research \
  --campaign-config campaigns/IL23R/campaign_20260520_001/campaign_config.yaml \
  --output-dir campaigns/IL23R/campaign_20260520_001/debate
```

Expected runtime: 4–8 minutes (3 hypothesis agents run in parallel ~3 min each,
reflection agent runs sequentially ~2 min). Expected output: `debate/proposals/`
with three `strategy_proposal.json` files, `debate/ranking.json`, and an
updated `campaign_config.yaml` reflecting the winning strategy.

---

## Inputs

**Required:**
- **Research report directory** — must contain `research.md`, `recommended_hotspots.json`, `design_recommendation.json`, and `validated_findings.json` from `by-research` (8-phase pipeline)
- **Campaign config skeleton** — a YAML file with `target`, `pdb_id`, `compute` block, but `modality`, `scaffolds`, `tier` are TBD

**Alternative inputs:**
- **`campaign_context.json`** — if present (from `/by:plan-campaign`), the user's preferences seed the agents but do NOT override the debate. Agents see the preference as a **prior**, not a constraint
- **`previous_debate.json`** — if rerunning after a failed campaign, prior debate gives historical signal to the reflection agent

**Optional:**
- **Debate budget** — number of hypothesis agents (default 3; 2 acceptable for tight token budgets, 4–5 for high-stakes campaigns)
- **Reflection temperature** — default 0.2 for ranking stability; raise to 0.5 for genuinely novel targets to encourage challenging the rubric
- **Tie-break mode** — `merge` (default), `aggressive_wins`, `user_decides`

See [references/agent-profiles.md](references/agent-profiles.md) for full input
specifications including agent-specific directive templates.

---

## Outputs

All outputs land under `<campaign_dir>/debate/`:

| File | Description | Written By |
|------|-------------|-----------|
| `proposals/conservative.json` | Strategy proposal from Conservative agent | hypothesis agent 1 |
| `proposals/aggressive.json` | Strategy proposal from Aggressive agent | hypothesis agent 2 |
| `proposals/diverse.json` | Strategy proposal from Diverse agent | hypothesis agent 3 |
| `ranking.json` | Reflection agent's scoring, winner, and rationale | reflection agent |
| `debate_log.jsonl` | Append-only audit trail of every agent dispatch | orchestrator |
| `campaign_config.yaml` | **Updated** config — modality, scaffolds, tier filled in from winner | orchestrator |
| `decision_summary.md` | Human-readable recap (target, candidates, choice, why) | reflection agent |

### `strategy_proposal.json` Schema

Every hypothesis agent writes one of these. Validation: `scripts/validate_proposal.py`.

```json
{
  "agent": "conservative",
  "version": "1.0",
  "target": "IL23R",
  "modality": "VHH",
  "protocol": "nanobody-anything",
  "scaffolds": ["caplacizumab", "ozoralizumab"],
  "tier": "standard",
  "num_designs_per_scaffold": 5000,
  "compute_provider": "local",
  "epitope": {
    "pdb_id": "6WDQ",
    "target_chain": "A",
    "residues": [78, 79, 80, 112, 113, 114, 115],
    "range_notation": "A78-A80,A112-A115"
  },
  "rationale": "Well-validated VHH scaffolds + low-novelty epitope reduces risk. Expected hit rate 20-40% based on prior IL-family campaigns.",
  "expected_hit_rate": "20-40%",
  "expected_wall_time_hours": 8,
  "key_risks": [
    "VHH may sterically clash with N-glycan at N91",
    "ipSAE may underestimate cytokine-receptor interface quality"
  ],
  "mitigation": "Run Protenix 5-seed ensemble validation on top 10 designs",
  "confidence": 0.78,
  "research_source_ids": ["src_001", "src_003", "src_007"]
}
```

### `ranking.json` Schema

The reflection agent writes one per debate.

```json
{
  "version": "1.0",
  "target": "IL23R",
  "ranked_at": "2026-05-20T14:32:00Z",
  "candidates": [
    {
      "agent": "conservative",
      "scientific_rigor": 0.85,
      "feasibility": 0.90,
      "innovation": 0.40,
      "risk_adjusted_confidence": 0.72,
      "composite_score": 0.7625,
      "rank": 1
    },
    {
      "agent": "diverse",
      "scientific_rigor": 0.70,
      "feasibility": 0.75,
      "innovation": 0.70,
      "risk_adjusted_confidence": 0.65,
      "composite_score": 0.7100,
      "rank": 2
    },
    {
      "agent": "aggressive",
      "scientific_rigor": 0.55,
      "feasibility": 0.50,
      "innovation": 0.95,
      "risk_adjusted_confidence": 0.45,
      "composite_score": 0.6125,
      "rank": 3
    }
  ],
  "winner": "conservative",
  "tie_break_applied": false,
  "rationale": "Conservative strategy wins on feasibility (0.90) and rigor (0.85); Diverse came close but lower research-source coverage.",
  "dissenting_notes": "Aggressive proposal flagged a real concern about VHH glycan clash — fold this into the conservative plan's mitigation.",
  "merged_recommendations": [
    "Add 'cross_check_glycan' flag from aggressive proposal to winning config",
    "Reserve 1500 designs from diverse proposal for alt-epitope exploration in run_002"
  ]
}
```

For the full schema with field-by-field type constraints, see
[references/ranking-rubric.md](references/ranking-rubric.md).

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST** — confirm research is complete before debating.

1. **Research output present?** (ASK THIS FIRST)
   - Does `<campaign_dir>/research/research.md` exist? If not → run `by-research` first; debate is pointless without target context
   - Are there `recommended_hotspots.json` AND `design_recommendation.json`? If not → debate has no input
   - If `validated_findings.json` shows zero HIGH confidence findings → tell user; the debate will likely produce low-confidence proposals

2. **Has the user pinned a modality?**
   - If `campaign_context.json` specifies `modality` → seed the agents but allow them to challenge it
   - If user said *"use VHH"* in conversation → still run debate; agents may surface a reason VHH is wrong here
   - If user said *"VHH only, do not consider alternatives"* → SKIP debate, go straight to `by-campaign-manager`

3. **What is the compute budget?**
   - Local GPU available? → all proposals can use `compute_provider: local`
   - HPC (RunPod) only? → agents must size designs against HPC time budget
   - Tamarind only? → agents must consider per-design cost in feasibility scoring

4. **How novel is the target really?**
   - 0 PDB, 0 SAbDab, <5 papers → use full 3-agent debate, raise reflection temperature
   - 0 PDB, 0 SAbDab, but has homologs with known binders → run debate; the Conservative agent will lean on homologs
   - Has PDB but no antibodies → likely doesn't need debate; consider skipping

5. **Tie-break preference?**
   - Default `merge` — winner gets best ideas folded in from runners-up
   - `aggressive_wins` — when user explicitly wants the highest-novelty option to break ties
   - `user_decides` — escalate to user when top 2 scores differ by < 5%

6. **Is this a replan after failure?**
   - If yes, point to `campaigns/<target>/.../previous_debate.json`. Reflection agent will downrank strategies similar to the failed one
   - Add the failure mode (e.g., "all designs had ipSAE < 0.4") to the orchestration prompt so agents avoid it

7. **What is the primary goal of this campaign?**
   - **Hit rate** → favors Conservative (well-trodden paths)
   - **Diversity** → favors Diverse (broad epitope/scaffold coverage)
   - **Novelty / first-in-class** → favors Aggressive (high-novelty hypotheses)
   - **Balanced** → reflection rubric weights all four dimensions equally

For decision detail and example transcripts, see
[references/agent-profiles.md](references/agent-profiles.md) §2.

---

## Standard Workflow

🚨 **MANDATORY: USE `scripts/orchestrate_debate.py` — DO NOT INLINE THE TASK() CALLS** 🚨

The orchestrator script wraps `Task()` dispatch, agent prompt construction, JSON
validation, and writes the debate log. Inlining the calls breaks the audit trail
and skips proposal schema validation.

### Step 1: Verify Research Inputs

```bash
ls <campaign_dir>/research/
# Must show: research.md, recommended_hotspots.json,
#            design_recommendation.json, validated_findings.json
```

✅ **VERIFICATION:** All four files exist and `validated_findings.json` has at
least 1 finding with confidence `HIGH` or `MEDIUM`.

❌ **DON'T:** Start the debate if research is incomplete — agents will hallucinate.

### Step 2: Run the Orchestrator

```bash
python3 scripts/orchestrate_debate.py \
  --research-dir <campaign_dir>/research \
  --campaign-config <campaign_dir>/campaign_config.yaml \
  --output-dir <campaign_dir>/debate \
  --num-agents 3 \
  --tie-break merge
```

Expected stdout:
```
✓ Loaded research from <campaign_dir>/research
✓ Spawned conservative agent (task_id=tsk_001)
✓ Spawned aggressive agent (task_id=tsk_002)
✓ Spawned diverse agent (task_id=tsk_003)
✓ Collected 3/3 proposals
✓ Validated all proposals against schema
✓ Spawned reflection agent (task_id=tsk_004)
✓ Ranking complete: winner=conservative, composite=0.7625
✓ Updated campaign_config.yaml
✓ Debate completed: 7 minutes 12 seconds
```

### Step 3: Validate Proposals (Automatic)

The orchestrator calls `scripts/validate_proposal.py` on each proposal before
passing to the reflection agent. If a proposal fails validation, it is dropped
and reported. **The reflection agent never sees malformed proposals.**

### Step 4: Review the Decision

Read `<campaign_dir>/debate/decision_summary.md`. Present the winner to the
user with the dissenting notes from runners-up.

### Step 5: Hand Off to `by-campaign-manager`

Once the user approves the winner, the updated `campaign_config.yaml` flows
directly into `by-campaign-manager` for execution. No re-planning needed.

### Script Failure Hierarchy

1. **Fix and Retry (90%)** — Missing Python package, stale research files → fix the underlying issue, re-run `orchestrate_debate.py`
2. **Modify Script (5%)** — Need to add an agent persona (e.g., `safety-engineer`) → edit `scripts/orchestrate_debate.py`, keep the rubric file in sync
3. **Use as Reference (4%)** — Want a one-off debate with custom prompts → read the script, run the `Task()` calls manually, write proposals by hand
4. **Write from Scratch (1%)** — Only if the entire campaign workflow is being replaced. Document the deviation in the campaign log

⚠️ **CRITICAL — DO NOT:**
- ❌ Skip JSON validation → malformed proposals corrupt the ranking
- ❌ Run agents sequentially → wastes wall-clock time; they must be parallel
- ❌ Edit a proposal after it's written → breaks the audit trail (write a follow-up note in `debate_log.jsonl`)
- ❌ Let the reflection agent score its own writeups (no recursion)

---

## When Scripts Fail

| Failure | Diagnosis | Action |
|---------|-----------|--------|
| `FileNotFoundError: research.md` | Research not run yet | Run `by-research` first; do not bypass |
| `ValidationError: missing field 'modality'` | Hypothesis agent skipped a field | Re-spawn that one agent with a more explicit directive (see [references/agent-profiles.md](references/agent-profiles.md)) |
| Reflection agent crashes / returns malformed JSON | Token limit, prompt confusion | Apply [references/fallback-decisions.md](references/fallback-decisions.md) §3 |
| All 3 proposals score < 0.5 composite | Research is too thin OR target is too hard | Apply [references/fallback-decisions.md](references/fallback-decisions.md) §2 |
| Top 2 scores within 5% | Genuine tie | Tie-break protocol (next section) |
| Agent returns identical proposals | Same prompt, no diversity injection | Check `agent-profiles.md` directive distinctness; raise temperature |

---

## Decision Points

### Tie-Break Protocol (top 2 scores within 5%)

When the composite scores of the top two proposals differ by less than **0.05**,
the orchestrator applies the configured tie-break mode:

| Mode | Behavior |
|------|----------|
| `merge` (default) | Winner is the higher-ranked, but `merged_recommendations` lifts the runner-up's strongest single recommendation into the winner's config |
| `aggressive_wins` | When tied, prefer the higher-innovation proposal (forces exploration on novel targets) |
| `user_decides` | Orchestrator pauses, presents both summaries to the user via `decision_summary.md`, awaits explicit pick |
| `risk_adjusted` | Prefer the proposal with higher `risk_adjusted_confidence` (favors low-variance outcomes) |

If three proposals are all within 5% of each other (rare, ~3% of debates), the
orchestrator escalates regardless of mode — see
[references/fallback-decisions.md](references/fallback-decisions.md) §1.

### Conservative vs Aggressive vs Diverse — When Each Wins

| Scenario | Likely Winner | Why |
|----------|---------------|-----|
| Well-studied target snuck through research filter | Conservative | High rigor + feasibility scores overwhelm Innovation |
| Truly novel target, well-funded campaign | Aggressive | Innovation weight matters; user explicitly wants first-in-class |
| Multi-modality decision (VHH vs scFv) without clear winner | Diverse | Proposes parallel-coverage panel across modalities |
| Replan after failure | Conservative or Diverse | Aggressive's prior strategy already failed — reflection downranks it |
| Target with known liability surface | Diverse | Spreads designs across non-liability epitopes |

### When the Debate Itself Is Wrong

If the winning proposal contradicts the `validated_findings.json` HIGH-confidence
findings (e.g., proposes a modality the research explicitly ruled out), the
**reflection agent must flag this** and the orchestrator must escalate to the
user. Never silently override the research.

---

## Worked Examples

### Example 1: Novel Target — IL23R Cytokine Receptor

**Setup:**
- 1 PDB (6WDQ), no SAbDab entries, 12 PubMed papers, all signaling-focused
- User asked: *"design something against IL23R"*
- Research confidence: 3 HIGH (interface residues from 6WDQ), 0 CONTRADICTED

**Debate inputs:** `validated_findings.json` flags N91 N-glycan adjacent to the
proposed epitope. `design_recommendation.json` defaults to VHH.

**Conservative proposal:**
- Modality: VHH, scaffolds: caplacizumab + ozoralizumab, tier: standard, 5000/scaffold
- Composite score: **0.7625** (rigor 0.85, feasibility 0.90, innovation 0.40, risk 0.72)

**Aggressive proposal:**
- Modality: de novo binder via PXDesign, custom hotspot ring around N91 (avoid glycan)
- Composite score: 0.6125 (rigor 0.55 — relies on AlphaFold-only model, feasibility 0.50, innovation 0.95, risk 0.45)

**Diverse proposal:**
- Two sub-runs: 3000 VHH + 1500 de novo binder, different epitope faces
- Composite score: 0.7100 (rigor 0.70, feasibility 0.75, innovation 0.70, risk 0.65)

**Winner:** Conservative. Tie-break not applied (delta 0.0525 > 0.05).

**Merged recommendation from runner-up (Diverse):** Reserve 1500 designs from
the standard budget for an alt-epitope run_002 if run_001 hit rate < 20%.

**Dissent kept:** Aggressive's glycan flag rolled into the Conservative
mitigation plan as `cross_check_glycan_clash: true`.

### Example 2: Multi-Modality Decision — Disordered Target

**Setup:**
- Intrinsically disordered protein, no PDB structure, 4 NMR papers
- User asked: *"compare approaches"* (explicit debate trigger)
- Research recommended both VHH and de novo binder, with caveats on both

**Conservative proposal:**
- VHH using AntiFold against a representative AlphaFold conformer
- Composite: 0.5450 (rigor 0.60, feasibility 0.55, innovation 0.40, risk 0.55) — **low rigor; AF model unreliable for IDPs**

**Aggressive proposal:**
- De novo cyclic peptide via PXDesign with conformational ensemble input
- Composite: 0.5800 (rigor 0.50, feasibility 0.55, innovation 0.90, risk 0.40) — **high innovation but high variance**

**Diverse proposal:**
- 1500 VHH + 1500 de novo cyclic peptide + 500 linear-binder controls
- Composite: **0.6300** (rigor 0.65, feasibility 0.65, innovation 0.65, risk 0.60)

**Tie-break check:** Top two (Diverse 0.6300, Aggressive 0.5800) differ by 0.05
exactly. Tie-break threshold is strict less-than-0.05, so NOT applied. Diverse
wins outright.

**Winner:** Diverse — appropriate for a truly novel modality decision. The
campaign config is split into three sub-runs with separate logs.

**Reflection notes:** "All three proposals scored < 0.7. Confidence is low. Run
preview tier first (5–10 designs per sub-run), escalate to standard only after
validation."

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| All 3 proposals look the same | Agent directives not differentiated enough; same temperature | Read [references/agent-profiles.md](references/agent-profiles.md) §1; ensure each agent has its "what to ignore" list | Diversity is engineered, not emergent |
| Reflection agent always picks Conservative | Rubric weights tilted toward feasibility | Adjust weights in [references/ranking-rubric.md](references/ranking-rubric.md); consider `aggressive_wins` tie-break | Default rubric favors low-variance |
| Proposal has missing fields | Agent ran out of tokens or got distracted | Re-spawn with shorter directive; check `validate_proposal.py` output | See [references/agent-profiles.md](references/agent-profiles.md) §3 |
| Composite scores all > 0.9 | Reflection agent is being too generous | Lower reflection temperature to 0.1; force per-axis justification | Calibration drift |
| Composite scores all < 0.4 | Research is too thin OR target is genuinely intractable | Run `by-research` UltraDeep; if still poor, abort campaign | [references/fallback-decisions.md](references/fallback-decisions.md) §2 |
| Aggressive proposal recommends a tool not installed | Agent didn't check environment | Pre-load `.by/environment.json` into the orchestration prompt | Always pass compute config |
| Reflection agent crashes mid-rank | Token overflow on long proposals | Truncate `rationale` field to 500 tokens before reflection | [references/fallback-decisions.md](references/fallback-decisions.md) §3 |
| Three-way tie within 5% | Genuine ambiguity OR weak research | Escalate to user via `user_decides` mode | [references/fallback-decisions.md](references/fallback-decisions.md) §1 |
| Winner contradicts `validated_findings.json` HIGH finding | Reflection rubric not weighting research alignment enough | Flag to user — do NOT auto-execute | [references/ranking-rubric.md](references/ranking-rubric.md) §5 |
| Debate produces same winner across 3 reruns | Determinism in agent dispatch | This is fine — stability is a feature when the answer is clear | Only an "issue" if you wanted exploration |
| `orchestrate_debate.py` crashes on import | Missing dependency (PyYAML, jsonschema) | `pip install pyyaml jsonschema` | Script handles ImportError gracefully |
| `validate_proposal.py` rejects valid-looking JSON | Schema version mismatch | Confirm `"version": "1.0"` field on proposal | Future-proofing |

---

## Best Practices

1. 🚨 **CRITICAL:** Always run `by-research` to completion before debating. Debate without research is fanfic
2. 🚨 **CRITICAL:** Never let the orchestrator skip the reflection agent. Three proposals without ranking is worse than one proposal
3. ✅ **REQUIRED:** Run hypothesis agents in **parallel**, never sequentially. Sequential dispatch leaks information from agent 1 into agent 3
4. ✅ **REQUIRED:** Validate every proposal against the schema before reflection. Malformed JSON breaks the ranking
5. ✅ Log every dispatch to `debate_log.jsonl`. The audit trail is how you debug post-hoc when a campaign goes sideways
6. ✅ Use `merge` tie-break by default — runners-up almost always have one or two ideas worth keeping
7. ✅ Re-run the debate after a failed campaign. Pass the failure mode in the orchestration prompt; reflection downranks repeats
8. ✅ Keep the Aggressive agent honest — its proposals are the highest-variance, so the reflection rubric must penalize unjustified novelty
9. ✨ **Optional:** Raise reflection temperature to 0.4–0.5 for truly novel targets; default 0.2 favors well-established choices
10. ❌ **DON'T:** Inline `Task()` calls in the main session. Always go through `orchestrate_debate.py` for the audit trail
11. ❌ **DON'T:** Let the user veto the debate output without recording the override in `decision_summary.md`. Decisions outside the rubric should be traceable

---

## Suggested Next Steps

After the debate produces a winning strategy:

- **Run `by-campaign-manager`** — the updated `campaign_config.yaml` is now ready for sizing, tier confirmation, and launch. The debate's `merged_recommendations` flow into the campaign plan
- **Run `by-design-workflow`** if the user wants full orchestration through to design + screening
- **Run `by-hypothesis-debate` again** (with `--reuse-research`) only if the user wants to revisit the decision; debates are not free, so this is a deliberate choice
- **Run `by-failure-diagnosis`** if a downstream campaign using this debate's winner fails — pass the debate output in so the diagnosis knows what was rejected and why

Chaining rationale: debate writes the strategy; campaign-manager executes it.
Keeping these separate means the debate output is reusable (you can switch the
executor — local vs HPC — without rerunning the debate).

---

## Related Skills

**Upstream (run before):**
- `by-research` — produces the research artifacts the debate consumes
- `by-epitope-analysis` — deeper epitope characterization if the research left gaps

**Downstream (run after):**
- `by-campaign-manager` — executes the winning strategy
- `by-design-workflow` — end-to-end orchestration including this debate
- `by-failure-diagnosis` — diagnoses why a debate-selected strategy failed

**Alternative / Complementary:**
- `by-campaign-optimizer` — active-learning loop that adjusts strategy within a campaign (not before)
- `by-knowledge` — queried by hypothesis agents for prior campaign evidence

---

## References

### Detailed Documentation
- [references/agent-profiles.md](references/agent-profiles.md) — Full directive templates for Conservative, Aggressive, and Diverse hypothesis agents. Includes what each agent is told to weight, what to ignore, and the exact system-prompt skeleton
- [references/ranking-rubric.md](references/ranking-rubric.md) — Scoring formulas, weight configuration, calibration examples, and how the reflection agent justifies each axis score
- [references/fallback-decisions.md](references/fallback-decisions.md) — Decision trees for three failure modes: three-way ties, universally low scores, and reflection agent crashes
- [references/example_debate_output.json](references/example_debate_output.json) — Complete fixture of a debate against IL23R: 3 proposals + ranking, suitable for testing and onboarding

### Scripts
- `scripts/orchestrate_debate.py` — CLI orchestrator: reads research + campaign config, spawns 3 hypothesis tasks in parallel, collects proposals, invokes reflection, writes the winner into `campaign_config.yaml`
- `scripts/validate_proposal.py` — CLI validator: checks a proposal JSON against the schema documented in this SKILL.md. Exits non-zero on schema violation with a precise error message

### Official Documentation
- Anthropic Claude Code Task() API — for the agent dispatch pattern
- `templates/CLAUDE.md` — overall BY orchestration guide (agent delegation protocol, model resolution)

### Related Methodologies
- Adversarial debate as decision procedure: Irving, Christiano, Amodei (2018) *AI safety via debate*
- Red-team review for protein design strategy selection (internal BY practice; not yet published)

**License:** All scripts in this skill are LGPL-compatible and permit
commercial use. No proprietary algorithms or datasets are embedded.
