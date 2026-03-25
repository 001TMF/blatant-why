---
name: by-display
description: >
  Standard display formats and conversational patterns for BY output.
  Use this skill when: (1) Presenting campaign status, progress, or results,
  (2) Formatting screening reports,
  (3) Displaying error messages or checkpoints,
  (4) Presenting research findings or target lookups.
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

## Conversational Patterns

### Target Lookup
Formatted table with Name, UniProt ID, PDB entries, Organism, Length, Function ->
recommendation -> confirmation

### Interface Analysis
Residue table with classifications -> hotspot list -> numbered options

### Design Launch
Parameter table -> monitoring hints (/by:watch, /by:status)

### Pipeline Progress
5-stage display (complete, active, pending) with counters, elapsed time, ETA

### Results
Ranked table (Rank, Design, ipTM, ipSAE, Liabilities, Status) -> next steps

---

## Anti-Patterns

- Never use ANSI escape codes in response text (they render as literal characters)
- Never vary banner widths (always use the same `━` line length)
- Always use `BY ►` prefix in banners (not `GSD ►`)
- Never use random emoji -- stick to the status symbols above
- Never skip the Next Up block after phase completions
