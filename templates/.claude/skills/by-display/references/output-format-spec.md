# BY Output Format Specification

Canonical Unicode/ASCII templates for every BY render type. Other skills copy
these verbatim. Do NOT improvise widths, symbols, or labels — extend this file
when a new view emerges.

---

## §Typography

| Item | Character | Codepoint | Notes |
|------|-----------|-----------|-------|
| Em-dash for missing values | `—` | U+2014 | Never use `-` or `--` |
| Heavy horizontal (banners) | `━` | U+2501 | 53 per banner line |
| Light horizontal (separators) | `─` | U+2500 | Used in checkpoint footer, table column rules |
| Filled block (score bar) | `█` | U+2588 | Score bars and progress bars |
| Light shade (empty bar) | `░` | U+2591 | Empty cells in score / progress bars |
| Diamond (active) | `◆` | U+25C6 | In-progress phase |
| Circle (pending) | `○` | U+25CB | Pending phase |
| Check (complete) | `✓` | U+2713 | Complete / passed |
| Cross (failed) | `✗` | U+2717 | Failed / blocked |
| Warning | `⚠` | U+26A0 | Warnings, quotas |
| Right-pointing triangle | `▶` | U+25B6 | "Next Up" header |
| Arrow (action) | `→` | U+2192 | Action prompts in checkpoint boxes |
| Box double TL/TR/BL/BR | `╔ ╗ ╚ ╝` | U+2554/2557/255A/255D | Error and checkpoint boxes |
| Box double horiz / vert | `═ ║` | U+2550 / U+2551 | Error and checkpoint boxes |
| Box double T (cross-bar) | `╠ ╣` | U+2560 / U+2563 | Error box internal divider |

**Rule:** When in doubt, paste from this file. Do not retype manually — editors
sometimes auto-substitute (e.g., `--` → `—`, smart quotes).

---

## §Fallbacks

If the user's terminal cannot render block-drawing characters (rare in modern
Claude Code clients), the fallback is:

| Unicode | ASCII fallback |
|---------|----------------|
| `█` | `#` |
| `░` | `-` |
| `━` | `=` |
| `─` | `-` |
| `╔ ╗ ╚ ╝` | `+` |
| `═` | `=` |
| `║` | `|` |
| `◆` | `*` |
| `○` | `o` |
| `✓` | `[x]` |
| `✗` | `[ ]` |
| `⚠` | `!` |

Triggered only on explicit user request — default to Unicode.

---

## §Banners

53 `━` characters wide. `BY ►` prefix is mandatory.

### `banner.campaign-status`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► CAMPAIGN: {campaign_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### `banner.results`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► RESULTS: {campaign_name} — {N} candidates ranked
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### `banner.complete`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► CAMPAIGN COMPLETE: {target}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

The banner-width rule is invariant: every `━` line in a single render is the
same length.

---

## §Phase Status Tables

`table.campaign-status` — 4 columns: Phase | Status | Time | Details.

```
| Phase    | Status     | Time   | Details              |
|----------|------------|--------|----------------------|
| Research | ✓ Complete | 45s    | 3 PDB, 12 prior art  |
| Plan     | ✓ Complete | 30s    | Preview tier, 10 VHH |
| Design   | ◆ Active   | 1m 15s | 5/10 designs         |
| Screen   | ○ Pending  | —      |                      |
| Rank     | ○ Pending  | —      |                      |
```

**Rules:**
- Pad status to width: `✓ Complete`, `◆ Active  `, `○ Pending `, `✗ Failed   ` — each 10 chars after the symbol+space.
- Use em-dash `—` for missing time, not `-` or empty.
- Details column is free-form but short (≤ 30 chars).

`table.pipeline-summary` — extended 4-column variant printed ONCE at the end:

```
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

## §Ranked Results Table

`table.ranked-results` — fixed-width columns; do not switch to markdown pipes
here because the column rule line `───` is part of the visual.

```
 #  Design       Composite  ipSAE   ipTM   pLDDT  Liabilities   Verdict
─── ──────────── ────────── ─────── ────── ────── ───────────── ──────────
 1  design_003   0.871      0.85    0.82   91.2   0 crit        ✓ LAB-READY
 2  design_007   0.823      0.80    0.79   88.5   1 warn        ✓ LAB-READY
 3  design_001   0.756      0.72    0.75   85.1   0 crit        ◆ FOLLOW-UP
 4  design_012   0.534      0.45    0.62   78.3   2 crit        ✗ NOT VIABLE
```

**Verdict vocabulary** (canonical):

| Verdict | Symbol | Meaning |
|---------|--------|---------|
| `LAB-READY` | `✓` | PASS all gates; submit to lab |
| `FOLLOW-UP` | `◆` | Borderline; rerun with more budget or different scaffold |
| `NOT VIABLE` | `✗` | FAIL one or more critical gates |
| `PENDING` | `○` | Not yet scored |

---

## §Score Bars

`bar.score` — 10 blocks, filled = `int(round(value * 10))`, capped at 10.

Format:
```
{metric:6s}  {value:6.2f}  {bar}  {label}
```

### Canonical thresholds and labels

| Metric | Scale | EXCELLENT | STRONG | GOOD | MODERATE | POOR |
|--------|-------|-----------|--------|------|----------|------|
| ipSAE | 0-1 | ≥ 0.80 | 0.65-0.79 | 0.50-0.64 | 0.30-0.49 | < 0.30 |
| ipTM | 0-1 | ≥ 0.80 | 0.65-0.79 | 0.50-0.64 | 0.30-0.49 | < 0.30 |
| pLDDT | 0-100 (divide by 100 for bar) | ≥ 90 (VERY HIGH) | 70-89 (HIGH) | 50-69 (MODERATE) | 30-49 (LOW) | < 30 (VERY LOW) |
| Composite | 0-1 | ≥ 0.80 | 0.65-0.79 | 0.50-0.64 | 0.30-0.49 | < 0.30 |
| RMSD (Å, inverse) | 0-inf | ≤ 1.0 | 1.0-2.0 (GOOD) | 2.0-3.0 (MODERATE) | 3.0-5.0 (POOR) | > 5.0 (BAD) |

### Examples

```
ipSAE  0.85  ████████░░  EXCELLENT  (top 5% of approved therapeutics)
ipTM   0.82  ████████░░  STRONG     (confident interface prediction)
pLDDT  91.2  █████████░  VERY HIGH  (reliable fold prediction)
RMSD   1.2A  ██░░░░░░░░  GOOD
Comp   0.65  ██████░░░░  STRONG
```

**Block fill table (exact):**

| Value | Fill | Bar |
|-------|------|-----|
| 0.00 - 0.04 | 0 | `░░░░░░░░░░` |
| 0.05 - 0.14 | 1 | `█░░░░░░░░░` |
| 0.15 - 0.24 | 2 | `██░░░░░░░░` |
| 0.25 - 0.34 | 3 | `███░░░░░░░` |
| 0.35 - 0.44 | 4 | `████░░░░░░` |
| 0.45 - 0.54 | 5 | `█████░░░░░` |
| 0.55 - 0.64 | 6 | `██████░░░░` |
| 0.65 - 0.74 | 7 | `███████░░░` |
| 0.75 - 0.84 | 8 | `████████░░` |
| 0.85 - 0.94 | 9 | `█████████░` |
| 0.95 - 1.00 | 10 | `██████████` |

Note: this is the conservative rounding (display 8 blocks for 0.85, 9 for 0.92).
For ambiguous boundary cases below 0.90, prefer the lower count.

---

## §Progress Bars

`bar.progress` — same 10-block format as score bars but displayed inline with
percent and count.

```
BY ► DESIGNING ████████░░ 80% (8/10 designs)
```

For batches:

```
████████░░  80% (8/10 jobs complete)
```

---

## §Sparkline (score distribution)

For showing the distribution of scores across N designs (used in
`render_campaign_status.py`). 8 quantile buckets, height encoded as block
character:

```
Sparkline blocks: ▁ ▂ ▃ ▄ ▅ ▆ ▇ █
Codepoints:       U+2581 .. U+2588
```

Example for 50 designs binned into 8 buckets:

```
Composite distribution: ▂▃▅▆▇█▆▃   (range 0.21 - 0.87, median 0.62)
```

Bucket boundaries are the score range divided into 8 equal-width bins. Each
character represents the relative count in that bin (max bin = `█`, empty = blank).

---

## §Screening Report

`report.screening` — three blocks (Liabilities, Developability, Structure) plus
verdict line.

```
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

**Verdict line vocabulary:** `✓ PASS`, `✗ FAIL`, `◆ BORDERLINE`.

---

## §Error Box

`box.error` — fixed 54-char width (interior 50 chars).

```
╔══════════════════════════════════════════════════════╗
║  ⚠ {Error title}                                     ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  {Details and alternatives}                          ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

Interior content is left-padded by 2 spaces, right-padded with spaces so the
closing `║` aligns at column 54.

---

## §Checkpoint Box

`box.checkpoint` — top box only; action prompt sits OUTSIDE the box.

```
╔══════════════════════════════════════════════════════╗
║  CHECKPOINT: {Type}                                  ║
╚══════════════════════════════════════════════════════╝

{Content — candidates table, cost estimate, safety gate status}

──────────────────────────────────────────────────────
→ {ACTION PROMPT}
──────────────────────────────────────────────────────
```

The bottom `─` separator is 54 light horizontals.

**Checkpoint types** (canonical): `LAB SUBMISSION`, `PLAN APPROVAL`, `BUDGET
EXCEEDED`, `PROVIDER SWITCH`, `IRREVERSIBLE OPERATION`.

---

## §Next-Up Block

`block.next-up` — always at the end of a major phase.

```
──────────────────────────────────────────────────────

## ▶ Next Up

**{Action}** — {description}

`/by:{command}`

<sub>`/clear` first → fresh context window</sub>

──────────────────────────────────────────────────────
```

The `<sub>` tag is rendered as small text by Claude Code. The `/clear` hint is
**mandatory** before any new major phase to prevent context bleed.

---

## §Job Submission Block

`block.job-submitted` — fixed indented format.

```
BY ► JOB SUBMITTED

  Job ID:    {id}
  Provider:  {provider_name}
  Tool:      {tool} | Protocol: {protocol}
  Submitted: {timestamp}
  Est. time: {duration}

  Track: /by:watch {id}
  Check: /by:status
```

`block.remote-job` — for SSH/HPC dispatch.

```
BY ► REMOTE JOB

  Host:      {hostname}
  PID:       {pid}
  Tool:      {tool description}
  Started:   {timestamp}

  Output:    {output_path}
  Monitor:   ssh {host} "tail -f {logpath}"
```

`block.batch-progress` — for multi-job tracking.

```
BY ► BATCH PROGRESS

  {progress bar}  {pct}% ({done}/{total} jobs complete)

  ✓ job_001  design_001  ipTM 0.82  ipSAE 0.79
  ✓ job_002  design_002  ipTM 0.75  ipSAE 0.71
  ...
  ◆ job_009  design_009  running (est. 5 min)
  ○ job_010  design_010  queued
```

---

## §Inline Progress

`inline.progress` — one line per phase event. Use between major phases instead
of reprinting the table.

```
◆ Structure: querying PDB...
✓ Structure: 10 PDB hits, best 3DPL at 2.6Å (12s)
✓ Sequence: P62877, 108 aa, RING domain (8s)
✗ Prior Art: SAbDab unavailable — retrying
✓ Prior Art: 0 known binders in SAbDab (15s)
```

**Rule:** when a phase completes, REPLACE the prior `◆` line conceptually by
appending the `✓` line. Claude Code is append-only; do not attempt to overwrite.

---

## §ANSI Discipline

Never emit ANSI escape codes (`\033[31m`, `\x1b[...m`, etc.) in chat. Claude
Code renders chat as markdown, not as a TTY, so escape codes appear as literal
characters. Color emphasis must come from emoji status symbols (`✓ ✗ ◆ ○ ⚠`)
and bold markdown only.
