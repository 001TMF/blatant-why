---
id: "skill_927c0230b96941e0ada299a50ccee03c"
name: "by-display"
display-name: "BY Display"
short-description: "Canonical display formats and conversational patterns for BY terminal output — banners, score bars, status tables, progress, errors, and checkpoints. Use when rendering any user-facing output so every skill speaks with the same voice."
category: "display"
keywords: "display, formatting, output, terminal, banner, progress bar, score bar, status table, screening report, error message, checkpoint, conversational pattern, ANSI, unicode, box drawing"
version: "1.0"
last-updated: "2026-05-20"
---

# BY Display Patterns

Standard display formats for **all** campaign output. They use Unicode box-drawing
characters and markdown that render natively in Claude Code's terminal. **Never
use ANSI escape codes in response text** — they render as literal characters.

Every other BY skill (research, screening, scoring, campaign-manager, ...) calls
into these templates when it is time to talk to the user. This file is the
canonical source; the literal templates live in
[`references/output-format-spec.md`](references/output-format-spec.md) so other
skills can copy them verbatim.

---

## When to Use This Skill

Use this skill when you are:

- ✅ **Rendering campaign status** for `/by:status`, `/by:watch`, or phase transitions
- ✅ **Formatting screening reports** (liabilities, developability, structure scores)
- ✅ **Showing ranked results** for `/by:results` or any final campaign output
- ✅ **Displaying errors or quota warnings** that need user attention
- ✅ **Presenting a checkpoint or safety gate** that requires explicit user approval
- ✅ **Streaming progress** during long-running design/fold jobs
- ✅ **Closing a phase** — every major phase ends with a "Next Up" block

Do NOT use this skill when:

- ❌ **You need to compute scores** — that is `by-scoring`; this skill only renders them
- ❌ **You need to run a screening battery** — that is `by-screening`
- ❌ **You need to decide what to do next** — that is `by-campaign-manager` / `by-design-workflow`
- ❌ **You need raw machine-readable JSON output** for another tool — emit JSON directly, not the human-facing templates here
- ❌ **You want to invent a new visual style** — extend the templates here instead of forking them

---

## Inputs

This skill is consumed by other skills. Inputs are the data objects to be rendered:

**Required (one of):**
- **Campaign checkpoint object** — `{ campaign_id, target, phases: [{name, status, time, details}, ...], current_phase }`. Source: `by-campaign-manager` (campaign_state.json).
- **Ranked design list** — `[{ design_id, composite, ipSAE, ipTM, pLDDT, liabilities, verdict }, ...]`. Source: `by-scoring` / `by-screening`.
- **Screening report object** — `{ design_id, liabilities: {...}, developability: {...}, structure: {...}, verdict }`. Source: `by-screening`.
- **Progress event** — `{ phase, status (◆/✓/✗), message, elapsed }`. Source: any long-running skill.
- **Error object** — `{ title, details, suggested_next }`.

**Optional:**
- **Score scale overrides** — non-default thresholds for the `EXCELLENT/STRONG/...` labels on score bars (see `references/output-format-spec.md` §Score Bars).
- **Provider context** — `{ provider, tool, protocol, scaffold, budget }` shown in design-launch banners.

---

## Outputs

Markdown strings printed to the terminal. No files written by this skill itself.

| Output | When | Template ID |
|--------|------|-------------|
| Campaign status banner | `/by:status`, phase transitions | `banner.campaign-status` |
| Progress-during-design line | `/by:watch`, mid-pipeline | `progress.design` |
| Ranked results table | `/by:results`, campaign close | `table.ranked-results` |
| Screening battery report | `/by:screen`, per-design report | `report.screening` |
| Score bar | Any 0-1 metric display | `bar.score` |
| Error box | Quota / failure / warning | `box.error` |
| Checkpoint box | Lab gate, approval gate | `box.checkpoint` |
| Next-Up block | End of every major phase | `block.next-up` |
| Long-running job submission | SSH / Tamarind dispatch | `block.job-submitted` |
| Batch progress | Multi-job tracking | `block.batch-progress` |
| Pipeline summary table | Campaign complete | `table.pipeline-summary` |
| Inline progress (✓/◆/✗) | Between phases | `inline.progress` |

For the literal Unicode/ASCII templates, see
[`references/output-format-spec.md`](references/output-format-spec.md).

---

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — confirm there is something to render before invoking this skill.

1. **What are you trying to render? (ASK THIS FIRST)** — A campaign status, a ranked results table, a screening report, an error, or a checkpoint? Each maps to a different template. Without this, do not generate any output.
2. **Which data object do you have?** — Pass the campaign checkpoint, the ranked design list, or the screening report object. The skill cannot make up values; if a field is missing, leave it blank or mark `—` (em-dash).
3. **What is the audience?** — User-facing terminal output (this skill) vs. machine-readable JSON for another tool (do NOT use this skill).
4. **Is this an end-of-phase rendering?** — If yes, append the Next-Up block. If mid-phase, use the inline `◆/✓` progress format instead.
5. **Are there units to clarify?** — pLDDT is 0-100 (divide by 100 for the score bar); ipSAE and ipTM are 0-1 (use directly). RMSD is in Å, lower is better.
6. **Is a safety gate involved?** — If lab submission or any irreversible action is next, use the checkpoint box and require explicit user approval. Never auto-proceed past a checkpoint.
7. **Provider context available?** — Local GPU / HPC / Tamarind affects what shows in the design-launch banner. If unknown, fall back to "compute provider: see `.by/config.json`".

---

## Standard Workflow

🚨 **MANDATORY: COPY TEMPLATES FROM `references/output-format-spec.md` VERBATIM — DO NOT IMPROVISE LAYOUT** 🚨

1. **Identify the render type.** Match the data object to one of the templates above.
2. **Load the template** from `references/output-format-spec.md`.
3. **Fill the slots** with values from the input object. Use `—` (em-dash) for missing values; never invent numbers.
4. **Pick the right status symbol** from the table below.
5. **Render the score bars** at 10-block resolution. Round the filled count to the nearest integer; for ambiguous cases below 0.9, prefer the conservative (lower) count.
6. **Append the Next-Up block** if this is the end of a major phase.

Anti-patterns:

- ❌ Writing ANSI escape codes (`\033[...`) in response text → they render literally in Claude Code chat
- ❌ Varying the banner width — always 53 `━` characters
- ❌ Using `GSD ►` or any prefix other than `BY ►`
- ❌ Reprinting the full phase table on every progress update — use inline `◆/✓` lines, print the summary table ONCE at the end
- ❌ Showing raw JSON from MCP tools — always parse and present clean summaries
- ❌ Exposing API keys, tokens, or secrets in any rendered output

---

## Status Symbols

```
✓  Complete / Passed / Verified
✗  Failed / Missing / Blocked
◆  In Progress / Active
○  Pending
⚠  Warning
```

Use ONLY these symbols. Random emoji break skimmability.

---

## Campaign Status Banner

Use for `/by:status` and phase transitions.

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► CAMPAIGN: {campaign_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Phase    | Status     | Time   | Details              |
|----------|------------|--------|----------------------|
| Research | ✓ Complete | 45s    | 3 PDB, 12 prior art  |
| Plan     | ✓ Complete | 30s    | Preview tier, 10 VHH |
| Design   | ◆ Active   | 1m 15s | 5/10 designs         |
| Screen   | ○ Pending  | —      |                      |
| Rank     | ○ Pending  | —      |                      |
```

A drop-in CLI renderer is provided at `scripts/render_campaign_status.py`:

```bash
python3 scripts/render_campaign_status.py \
  --checkpoint campaigns/anti-HER2/campaign_20260520_001/campaign_state.json
```

---

## Progress During Design

Use for `/by:watch` and mid-pipeline updates.

```markdown
BY ► DESIGNING ████████░░ 80% (8/10 designs)

Provider: Local GPU (RTX 6000)
Tool: BoltzGen | Protocol: nanobody-anything
Scaffold: caplacizumab | Budget: 10
```

Progress bar: 10 blocks total. `█` (U+2588) for filled, `░` (U+2591) for empty.
Fill proportionally to percent complete.

---

## Ranked Results Table

Use for `/by:results` and final campaign output.

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► RESULTS: {campaign_name} — {N} candidates ranked
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 #  Design       Composite  ipSAE   ipTM   pLDDT  Liabilities   Verdict
─── ──────────── ────────── ─────── ────── ────── ───────────── ──────────
 1  design_003   0.871      0.85    0.82   91.2   0 crit        ✓ LAB-READY
 2  design_007   0.823      0.80    0.79   88.5   1 warn        ✓ LAB-READY
 3  design_001   0.756      0.72    0.75   85.1   0 crit        ◆ FOLLOW-UP
 4  design_012   0.534      0.45    0.62   78.3   2 crit        ✗ NOT VIABLE

## Score Context
ipSAE  0.85  ████████░░  EXCELLENT  (top 5% of approved therapeutics)
ipTM   0.82  ████████░░  STRONG     (confident interface prediction)
pLDDT  91.2  █████████░  VERY HIGH  (reliable fold prediction)

## Summary
✓ 2 lab-ready candidates | ◆ 1 needs follow-up | ✗ 1 not viable

## Next Steps
1. Submit top 2 to Adaptyv Bio ($119-215/design)
2. Run follow-up campaign with increased budget for design_001
3. Consider alternative epitope for design_012
```

---

## Screening Battery Display

Use for `/by:screen` and per-design screening reports.

```markdown
BY ► SCREENING {design_id}

Liabilities:
  ✓ Deamidation     0 sites
  ✓ Isomerization   0 sites
  ✓ Oxidation       0 sites (no exposed Met)
  ✓ Free Cys        0 unpaired
  ✓ Glycosylation   0 NXS/T motifs

Developability:
  Charge pH 7.4    +2.1   ✓ normal range
  Hydrophobic      34%    ✓ below 45% threshold
  CDR3 length      12 aa  ✓ within range

Structure:
  ipSAE   0.85   ████████░░   EXCELLENT
  ipTM    0.82   ████████░░   STRONG
  pLDDT   91.2   █████████░   VERY HIGH
  RMSD    1.2A   ██░░░░░░░░   GOOD

VERDICT: ✓ PASS — composite score 0.871
```

---

## Score Bar Format

For any metric on a 0-1 scale (or 0-100 normalized to 0-1):

```
{metric}  {value}  {bar}  {label}
```

Where bar = 10 blocks, filled proportionally: `████████░░` for 0.80.

Scale: each `█` represents 10%. Round to nearest block. Examples:
- 0.85 = `████████░░` (8.5 rounds to 9, but display 8 for conservatism below 0.9)
- 0.92 = `█████████░`
- 0.50 = `█████░░░░░`
- 0.12 = `█░░░░░░░░░`

For pLDDT (0-100 scale), divide by 100 first: pLDDT 91.2 = 0.912 = `█████████░`.

Canonical thresholds and labels for ipSAE / ipTM / pLDDT / RMSD live in
[`references/output-format-spec.md`](references/output-format-spec.md) §Score Bars.

---

## Error Display

Use for warnings, quota exhaustion, and failures.

```markdown
╔══════════════════════════════════════════════════════╗
║  ⚠ {Error title}                                     ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  {Details and alternatives}                          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

## Checkpoint / Safety Gate

Use for lab submission gates and user approval points.

```markdown
╔══════════════════════════════════════════════════════╗
║  CHECKPOINT: {Type}                                  ║
╚══════════════════════════════════════════════════════╝

{Content — candidates table, cost estimate, safety gate status}

──────────────────────────────────────────────────────
→ {ACTION PROMPT}
──────────────────────────────────────────────────────
```

---

## Next Up Block

Always show at the end of major phase completions.

```markdown
──────────────────────────────────────────────────────

## ▶ Next Up

**{Action}** — {description}

`/by:{command}`

<sub>`/clear` first → fresh context window</sub>

──────────────────────────────────────────────────────
```

---

## Long-Running Job Display

Use for SSH remote jobs, HPC dispatch, and Tamarind cloud jobs that take minutes to hours.

### Fire-and-Forget Pattern

For jobs submitted to remote compute:

```markdown
BY ► JOB SUBMITTED

  Job ID:    tmr_abc123
  Provider:  Local GPU (RTX 6000)
  Tool:      BoltzGen | Protocol: nanobody-anything
  Submitted: 2026-03-25 14:32 UTC
  Est. time: ~45 min

  Track: /by:watch tmr_abc123
  Check: /by:status
```

### SSH Remote Job

```markdown
BY ► REMOTE JOB

  Host:      gpu-node.example.com
  PID:       12345
  Tool:      Protenix refolding (20 seeds)
  Started:   2026-03-25 14:32 UTC

  Output:    ~/campaigns/anti-HER2/run_001/protenix_out/
  Monitor:   ssh gpu-node "tail -f ~/campaigns/.../protenix.log"
```

### Batch Progress

When monitoring a batch of jobs:

```markdown
BY ► BATCH PROGRESS

  ████████░░  80% (8/10 jobs complete)

  ✓ job_001  design_001  ipTM 0.82  ipSAE 0.79
  ✓ job_002  design_002  ipTM 0.75  ipSAE 0.71
  ✓ job_003  design_003  ipTM 0.88  ipSAE 0.85
  ...
  ◆ job_009  design_009  running (est. 5 min)
  ○ job_010  design_010  queued
```

---

## Inline Progress Updates (preferred over repeated tables)

Claude Code output is append-only — tables cannot be updated in place.
Instead, show one-line status updates as each phase completes. Print the
full summary table only ONCE at the end.

```markdown
◆ Structure: querying PDB...
✓ Structure: 10 PDB hits, best 3DPL at 2.6Å (12s)
✓ Sequence: P62877, 108 aa, RING domain (8s)
✓ Prior Art: 0 known binders in SAbDab (15s)
✓ Epitope: 2 druggable surfaces identified (18s)
◆ Synthesizer: compiling report...
✓ Synthesizer: druggability 0.89, de novo recommended (5s)
◆ Design: submitting 1,000 designs to local GPU...
```

Do NOT reprint the full phase table after every step — it clutters the chat.
Use the one-line ✓/◆/✗ format between phases.

## Live Progress from Compute Tools

BoltzGen and Protenix output their own progress bars when run via Bash.
Claude Code streams Bash output in real-time, so users see live progress:

```
[Step 1/5] design - Predicting DataLoader 0: : 50%|█████     | 5/10 [00:32<00:32, 0.15it/s]
```

**IMPORTANT:** For live progress to work, the design agent MUST run compute
tools via the **Bash tool** (not MCP). MCP tools return results only after
completion — no streaming. Bash streams output as it happens.

Pattern for the design agent:
```bash
# Run BoltzGen via conda env — output streams live
/home/user/.conda/envs/bg/bin/boltzgen run design_spec.yaml \
  --output ./campaign_output \
  --num_designs 10 \
  --protocol nanobody-anything \
  --budget 10
```

The 5-stage BoltzGen pipeline shows live progress for each step:
1. `design` — backbone generation with diffusion progress bar
2. `inverse_folding` — sequence design progress bar
3. `folding` — Protenix refolding progress bar
4. `analysis` — metrics computation
5. `filtering` — ranking and output

## Pipeline Summary Table (show ONCE at end)

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► CAMPAIGN COMPLETE: {target}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Phase       | Status     | Time   | Details                          |
|-------------|------------|--------|----------------------------------|
| Structure   | ✓ Complete | 12s    | 10 PDB hits, best 3DPL at 2.6Å  |
| Sequence    | ✓ Complete | 8s     | P62877, 108 aa, RING domain      |
| Prior Art   | ✓ Complete | 15s    | 0 known binders                  |
| Epitope     | ✓ Complete | 18s    | 2 druggable surfaces             |
| Synthesizer | ✓ Complete | 5s     | Druggability 0.89                |
| Design      | ✓ Complete | 5m 20s | 1,000 designs, local GPU         |
| Screen      | ✓ Complete | 45s    | 847 pass, 153 fail               |
| Verify      | ✓ Complete | 10s    | 10 candidates verified           |

Total: 7m 13s | Provider: Local GPU (RTX 6000)
```

---

## Conversational Patterns

### Target Lookup

Formatted table with Name, UniProt ID, PDB entries, Organism, Length, Function,
followed by a recommendation and confirmation prompt.

### Interface Analysis

Residue table with classifications (hotspot, contact, peripheral), followed by
hotspot list and numbered options for epitope selection.

### Design Launch

Parameter table (modality, scaffold, budget, provider, protocol), followed by
monitoring hints (`/by:watch`, `/by:status`).

### Results

Ranked table (Rank, Design, ipSAE, ipTM, Liabilities, Status), followed by
Score Context bars, Summary line, and Next Steps.

---

## When Scripts Fail

This skill ships one script: `scripts/render_campaign_status.py`. It only depends on
Python stdlib (`json`, `argparse`, `pathlib`). Standard failure hierarchy:

1. **Fix and Retry (90%)** — Wrong checkpoint path, malformed JSON, or missing
   `phases` array. Inspect the checkpoint, fix, re-run.
2. **Modify Script (5%)** — Add a new column or sparkline variant. Keep the
   `--checkpoint` CLI signature stable.
3. **Use as Reference (4%)** — If a campaign needs an entirely different layout,
   read the script and inline the rendering. Still copy the literal templates
   from `references/output-format-spec.md` — do not reinvent them.
4. **Write from Scratch (1%)** — Only if the checkpoint schema has changed and
   the script cannot be repaired. Document why in the campaign's `notes.md`.

If you need a template that does not yet exist (e.g., a new "kinetics report"
view), extend `references/output-format-spec.md` rather than improvising.

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| ANSI escape codes show as literal `\033[31m` | Used terminal color codes in response text | Claude Code does not interpret ANSI in chat — use status symbols (✓ ✗ ◆) and unicode bars only | SKILL.md Anti-Patterns |
| Banner width misaligned (some `━` lines longer than others) | Hand-typed banner lines drifted | Always 53 `━` characters; copy from `references/output-format-spec.md` §Banners | references/output-format-spec.md |
| Score bar shows 11 blocks instead of 10 | Off-by-one when filling proportionally | Bar is exactly 10 blocks; use `int(round(value * 10))` for fill count, capped at 10 | references/output-format-spec.md §Score Bars |
| pLDDT score bar shows 0.91 → 9 blocks → label "EXCELLENT" but pLDDT is on 0-100 scale | Forgot to divide pLDDT by 100 before rendering | Divide pLDDT by 100 for the bar; show the raw 0-100 value as the displayed number | SKILL.md Score Bar Format |
| Status table reprinted after every progress event | Treating the table as a live dashboard | Print the summary table ONCE at the end; use inline `◆/✓` lines between phases | SKILL.md Inline Progress |
| Box-drawing characters look broken (▒▓ instead of ░█) | Font does not support U+2588 / U+2591, or fallback failed | Most modern terminals render these; if user reports breakage, fall back to ASCII `#` for filled and `-` for empty | references/output-format-spec.md §Fallbacks |
| Long-running job displays no progress | Compute tool launched via MCP instead of Bash | MCP returns only on completion; launch BoltzGen/Protenix via the Bash tool so output streams live | SKILL.md Live Progress |
| `GSD ►` prefix appearing instead of `BY ►` | Carried over from another agent's display patterns | BY uses `BY ►` exclusively — search-and-replace any `GSD ►` occurrences | SKILL.md Anti-Patterns |
| Raw MCP JSON dumped into chat | Skipped the parse step | Parse the JSON object, render via the appropriate template, never `print(json.dumps(...))` to chat | CLAUDE.md Communication Style |
| API keys / tokens visible in design-launch banner | Provider config printed verbatim | Strip secrets; show only provider name (`Local GPU`, `Tamarind Bio`) and tool name | SKILL.md Anti-Patterns |
| Next-Up block missing after phase completes | Forgot the closing block | Every major phase ends with the Next-Up block (template `block.next-up`); enforce in skill exit | SKILL.md Next Up Block |
| Em-dash `—` shown as `-` or `--` | Wrong character (hyphen / double-hyphen instead of U+2014) | Use the actual em-dash U+2014 for missing values; many editors auto-replace `--` → `—` | references/output-format-spec.md §Typography |
| Checkpoint box rendered without action prompt | Used the box template but forgot the `→ {ACTION}` footer | Checkpoint boxes are gated; ALWAYS include the action prompt below the box | SKILL.md Checkpoint |

---

## Best Practices

1. 🚨 **CRITICAL: Always use `BY ►` as the banner prefix.** Never `GSD ►` or any other variant.
2. 🚨 **CRITICAL: Never emit ANSI escape codes in response text.** They render as literal characters in Claude Code chat.
3. ✅ **REQUIRED: Copy templates verbatim from `references/output-format-spec.md`.** Do not improvise widths or symbols.
4. ✅ **REQUIRED: Print the full phase summary table ONCE.** Between phases, use one-line `◆/✓/✗` updates.
5. ✅ **REQUIRED: End every major phase with a Next-Up block.** It is the user's hand-off cue.
6. ✅ Use the canonical status symbols (✓ ✗ ◆ ○ ⚠) — no random emoji.
7. ✅ Divide pLDDT by 100 before computing the score bar fill; show the raw 0-100 value alongside.
8. ✅ Stream long-running progress via Bash, not MCP (MCP returns only on completion).
9. ❌ Do NOT dump raw MCP JSON into chat — parse and render via a template.
10. ❌ Do NOT include API keys, tokens, or full file paths with secrets in any rendered output.
11. ✨ **Optional:** When a new view type emerges (e.g., kinetics, dose-response), add a new template to `references/output-format-spec.md` rather than improvising once.

---

## Suggested Next Steps

This skill is a **render layer** — every other skill calls into it. After invoking
`by-display`, the typical continuation depends on the render type:

1. **After a results table** → invoke `by-experiment-results` (lab readouts) or `by-campaign-optimizer` (active-learning round N+1) for what happens next.
2. **After a screening report** → invoke `by-failure-diagnosis` if anything failed, or `by-campaign-manager` to advance the campaign state.
3. **After a checkpoint** → wait for explicit user approval; on approval, hand back to the calling skill (e.g., `by-campaign-manager` for lab submission).
4. **After a status banner mid-pipeline** → continue the running phase; do not auto-advance.
5. **After a campaign-complete summary** → invoke `by-knowledge` to persist learnings, then `by-campaign-optimizer` if iterating.

---

## Related Skills

**Upstream (feed data into this skill):**
- `by-campaign-manager` — supplies campaign checkpoint objects.
- `by-scoring` — supplies composite / ipSAE / ipTM / pLDDT values.
- `by-screening` — supplies per-design liability and developability data.
- `by-research` — supplies target-lookup data and prior-art counts.

**Downstream (consumed by user, not other skills):**
- The user reads the rendered output and invokes the next slash command.

**Alternative / complementary:**
- None — this is the single canonical render layer. If a different style is needed, extend `references/output-format-spec.md`.

---

## References

**Detailed documentation:**
- [`references/output-format-spec.md`](references/output-format-spec.md) — canonical Unicode/ASCII templates for every render type listed in Outputs, plus typography rules, fallback policy, and score-bar threshold tables.

**Scripts:**
- [`scripts/render_campaign_status.py`](scripts/render_campaign_status.py) — CLI: reads a campaign checkpoint JSON and prints the formatted banner + phase table + score distribution sparkline + recent events.

**External references:**
- Unicode box-drawing block: https://www.unicode.org/charts/PDF/U2500.pdf
- Unicode block elements (▀ ▌ █ ░ ▒ ▓): https://www.unicode.org/charts/PDF/U2580.pdf
