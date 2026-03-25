---
name: by-display
description: >
  Standard display formats and conversational patterns for BY output.
  Use this skill when: (1) Presenting campaign status, progress, or results,
  (2) Formatting screening reports,
  (3) Displaying error messages or checkpoints,
  (4) Presenting research findings or target lookups,
  (5) Showing long-running job progress.
category: display
tags: [display, formatting, output, patterns, conversational]
---

# BY Display Patterns

Use these standard display formats for all campaign output. They use Unicode
box-drawing characters and markdown that render natively in Claude Code's terminal.
Never use ANSI escape codes in response text.

---

## Status Symbols

```
✓  Complete / Passed / Verified
✗  Failed / Missing / Blocked
◆  In Progress / Active
○  Pending
⚠  Warning
```

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

---

## Progress During Design

Use for `/by:watch` and mid-pipeline updates.

```markdown
BY ► DESIGNING ████████░░ 80% (8/10 designs)

Provider: Tamarind Bio (free tier, 7/10 jobs remaining)
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

Use for SSH remote jobs and Tamarind cloud jobs that take minutes to hours.

### Fire-and-Forget Pattern

For jobs submitted to remote compute:

```markdown
BY ► JOB SUBMITTED

  Job ID:    tmr_abc123
  Provider:  Tamarind Bio (free tier)
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

Ranked table (Rank, Design, ipTM, ipSAE, Liabilities, Status), followed by
Score Context bars, Summary line, and Next Steps.

---

## Anti-Patterns

- Never use ANSI escape codes in response text (they render as literal characters)
- Never vary banner widths (always use the same `━` line length)
- Always use `BY ►` prefix in banners (not `GSD ►` or any other prefix)
- Never use random emoji -- stick to the status symbols above (✓ ✗ ◆ ○ ⚠)
- Never skip the Next Up block after phase completions
- Never show raw JSON from MCP tool responses -- always parse and present clean summaries
- Never expose API key values in any display
