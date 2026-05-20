# BY Skills Catalog and Conventions

This directory is the home of every skill BY (Blatant-Why) loads at runtime.
Each skill is a self-contained capability — a SKILL.md with optional
`references/` and `scripts/` — that the BY agent invokes when its triggers
match. This README is the **navigation map**: terminology canon, skill linkage,
end-to-end workflow, authoring rules, and a quick-reference Q&A.

**Audience:** developers extending BY, and the agent itself when picking which
skill to invoke. If a skill, term, or workflow appears here, it is canonical.
If it does not, propose adding it before improvising.

**Skill count:** 19 (17 `by-*` orchestration/analysis skills + 3 tool wrappers:
`protenix`, `pxdesign`, `boltzgen`).

---

## 1. Canonical Terminology

Every skill agrees on the spellings, casings, and phrases below. Reviews
should reject any drift.

| Term | Canonical form | Anti-patterns to avoid | Where used |
|------|----------------|------------------------|------------|
| Interface score (primary) | `ipSAE` | `ip_sae`, `IPSAE`, `ipsae`, `IpSAE` | by-scoring, by-screening, by-display |
| Secondary interface score | `ipTM` | `ipTm`, `iptm`, `IPTM` | by-scoring, by-screening |
| Fold confidence | `pLDDT` | `plddt`, `PLDDT`, `pLDdt` | by-scoring, by-screening, by-display |
| Design unit (general) | `design` | `binder` (when target is antibody/nanobody) | every skill |
| Design unit (non-Ab, non-nanobody) | `binder` | `design` (when context demands antibody distinction) | pxdesign, by-design-workflow |
| Pass/fail outcome (uppercase only) | `PASS` / `FAIL` | `pass`, `Pass`, `fail`, `Failed` | by-screening, by-experiment-results |
| Inconclusive lab readout | `INCONCLUSIVE` | `inconclusive`, `N/A`, `unknown` | by-experiment-results |
| Pass-rate metric | `pass rate` | `hit rate`, `success rate` | by-screening, by-campaign-optimizer |
| Structure prediction engine | `Protenix` | `proteus-fold`, `Protennix` | every skill referencing folding |
| De novo binder engine | `PXDesign` | `proteus-prot`, `PxDesign`, `pxdesign` (only as the skill name) | by-design-workflow, pxdesign |
| Antibody/nanobody engine | `BoltzGen` | `proteus-ab`, `Boltzgen`, `boltzgen` (only as the skill name) | by-design-workflow, boltzgen |
| MCP tool reference | `mcp__<server>__<tool>` | `mcp:<server>/<tool>`, bare tool name | every skill referencing MCP |
| Confidence levels (research) | `HIGH` / `MEDIUM` / `SPECULATIVE` | `LOW`, `low`, `tentative` | by-research, by-knowledge |
| Confidence levels (validation cross-check) | `HIGH` / `MEDIUM` / `LOW` / `CONTRADICTED` | `verified`, `unverified` | by-research (triangulation only) |
| Lab readout outcome | `PASS` / `FAIL` / `INCONCLUSIVE` | `positive`, `negative`, `null` | by-experiment-results |
| Banner prefix | `BY ►` | `GSD ►`, any other prefix, `BY:` | by-display |
| Campaign tier | `Preview` / `Standard` / `Production` | `preview`, `STANDARD`, `prod` | by-campaign-manager, by-research |
| Compute provider | `local` / `hpc` / `tamarind` | `runpod`, `cloud`, `SLURM` (those are HPC backends) | by-deploy-compute, by-session |
| Status symbols | `✓ ✗ ◆ ○ ⚠` | random emoji (🎉 🚀 🔥 etc.) | by-display |

When in doubt, search this table before writing user-facing text.

---

## 2. Skill Linkage Map

Every skill, grouped by category. **Upstream** = what produces inputs for this
skill. **Downstream** = what consumes this skill's outputs. Counts include
both files in the skill directory and files referenced from SKILL.md.

### Orchestration

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-design-workflow` | Master orchestrator — decides which design tool runs, when, on what hardware | by-research, by-campaign-manager | protenix, pxdesign, boltzgen, by-screening | yes | yes |
| `by-campaign-manager` | Campaign state machine — checkpoints, resume, budget tracking, tier selection | by-session, by-research | by-design-workflow, by-display | yes | yes |

### Research

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-research` | 8-phase target dossier pipeline with anti-drift checkpoints | by-session | by-epitope-analysis, by-campaign-manager, by-hypothesis-debate | yes | yes |
| `by-database` | Direct MCP queries to PDB / UniProt / SAbDab for one-off lookups | by-session | by-research, by-epitope-analysis | yes | yes |
| `by-epitope-analysis` | Structural epitope characterization on candidate hotspots | by-research | by-campaign-manager, by-hypothesis-debate | yes | yes |

### Strategy

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-hypothesis-debate` | Adversarial multi-strategy ranking before committing GPU compute | by-research, by-epitope-analysis | by-campaign-manager | yes | yes |

### Scoring & Filtering

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-scoring` | Canonical scoring formulas — ipSAE (min), ipTM, composite, thresholds | protenix, boltzgen, pxdesign | by-screening, by-display | yes | yes |
| `by-screening` | Liabilities + developability + structure → PASS / FAIL verdict | by-scoring | by-failure-diagnosis, by-display, by-experiment-results | yes | yes |

### Analysis

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-failure-diagnosis` | Diagnoses why a design or campaign failed quality gates | by-screening, by-experiment-results | by-causal-reasoning, by-campaign-manager | yes | yes |
| `by-experiment-results` | Ingest lab readouts (PASS/FAIL/INCONCLUSIVE) and join with design metadata | by-screening (predictions), lab submission | by-campaign-optimizer, by-knowledge | yes | yes |
| `by-causal-reasoning` | Multi-hypothesis causal inference over design failures | by-failure-diagnosis | by-knowledge, by-campaign-optimizer | yes | yes |

### Optimization

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-campaign-optimizer` | Active-learning round-N+1 planner — picks next designs from lab readouts | by-experiment-results, by-causal-reasoning | by-campaign-manager (next round) | yes | yes |

### Persistence

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-knowledge` | Cross-campaign knowledge graph — patterns, decisions, target families | every analysis skill | by-research (priors), by-hypothesis-debate (heuristics) | yes | yes |

### Session

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-session` | Session init — banner, environment check, config questionnaire, resume | (none — entry point) | every other skill | yes | yes |

### Display

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-display` | Canonical render templates — banners, score bars, status tables, errors | every skill that talks to the user | the user (terminal) | yes | yes |

### Deployment

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `by-deploy-compute` | HPC dispatch (RunPod / Modal / SLURM) for Protenix, BoltzGen, PXDesign | by-design-workflow | protenix, pxdesign, boltzgen (on remote) | yes | yes |

### Tool Wrappers

| Skill | Purpose | Upstream | Downstream | Scripts | References |
|-------|---------|----------|------------|---------|------------|
| `protenix` | AF3-class structure prediction (368M params) — refold + confidence | by-design-workflow | by-scoring, by-screening | yes | yes |
| `pxdesign` | De novo non-antibody binder design (YAML config + CLI) | by-design-workflow | protenix (refold), by-scoring | yes | yes |
| `boltzgen` | Antibody / nanobody design (BoltzGen diffusion + Protenix refolding) | by-design-workflow | by-scoring, by-screening | yes | yes |

**Row count: 19.** Cross-check against `ls templates/.claude/skills/` — they
must match the `skills` array in `plugin-manifest.json`.

---

## 3. End-to-End Workflow

The typical campaign threads through skills as follows. Solid arrows are
**always** taken; dashed arrows are **conditional** on context.

```
by-session  (init — banner, env check, config, resume)
   │
   ▼
by-research ──▶ by-epitope-analysis ──▶ by-hypothesis-debate
   │                                       │
   │                                       ▼
   └─────────────────────────────▶ by-campaign-manager
                                          │
                                          ▼
                                   by-design-workflow
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
            protenix                  pxdesign                  boltzgen
                │                         │                         │
                └─────────────┬───────────┴─────────────┬───────────┘
                              │                         │
                       (local GPU)             (HPC / Tamarind via by-deploy-compute)
                              │                         │
                              └────────────┬────────────┘
                                           ▼
                                     by-screening
                                           │
                                           ▼
                                      by-scoring
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                    by-display    by-failure-diagnosis  (lab submission)
                                           │                │
                                           ▼                ▼
                                  by-causal-reasoning  by-experiment-results
                                           │                │
                                           └────────┬───────┘
                                                    ▼
                                          by-campaign-optimizer
                                                    │
                                                    ▼
                                              by-knowledge
                                                    │
                                                    └──▶ (round N+1)
```

**Narrative walkthrough:**

A campaign begins at `by-session`, which establishes the working directory,
loads `.by/config.json` (compute provider, model profile, budget defaults),
and either creates a fresh campaign or resumes an existing one from its last
checkpoint. From there, `by-research` runs an 8-phase target-dossier pipeline
— retrieving structures, prior art, and known binders, then triangulating
findings under three adversarial review personas. The output is a
`design_recommendation.json` consumed by `by-campaign-manager`.

When multiple viable design strategies emerge (different modalities, different
scaffolds, different epitope windows), `by-hypothesis-debate` runs an
adversarial ranking pass **before** any GPU compute is committed — burning a
few minutes of LLM reasoning saves potentially hours of wasted compute.
`by-campaign-manager` then writes the campaign plan (tier, budget, scaffolds,
fold-validation criteria), and `by-design-workflow` dispatches the actual
design jobs.

The three tool wrappers (`protenix`, `pxdesign`, `boltzgen`) run on whichever
provider `.by/config.json` specifies — local GPU by default, HPC or Tamarind
when explicitly chosen. `by-deploy-compute` handles the HPC packaging (Docker
image, sync, sbatch / RunPod / Modal submission). Outputs from every engine
flow into `by-scoring` for canonical metric computation (ipSAE min, ipTM,
composite) and `by-screening` for liability + developability + structure gates
(PASS / FAIL).

`by-display` renders every user-facing artifact along the way — never
duplicated, always copied from `references/output-format-spec.md`. Failures
route through `by-failure-diagnosis` and `by-causal-reasoning` to extract
**why** a design or campaign failed. Lab submissions return as
`by-experiment-results` (PASS / FAIL / INCONCLUSIVE), which feeds
`by-campaign-optimizer` to plan round N+1 via active learning. Finally,
`by-knowledge` persists patterns and decisions to the cross-campaign graph so
the next target benefits from prior runs.

---

## 4. Authoring Conventions for New Skills

Every new skill MUST follow these rules. They are derived from the BY quality
bar and the Anthropic biology-skills reference standard.

### 4.1 YAML frontmatter

Top of `SKILL.md`, before any prose. Generate the `id` with
`python3 -c "import uuid; print('skill_' + uuid.uuid4().hex)"`.

```yaml
---
id: "skill_<32-char-hex-uuid>"
name: "<dir-name>"                         # kebab-case, matches directory
display-name: "<Human Title>"
short-description: "<1-2 sentences ending with 'Use when...'>"
category: "<orchestration|research|scoring|filtering|persistence|strategy|diagnosis|tool|display|session|deployment>"
keywords: "comma, separated, terms"
version: "1.0"
last-updated: "YYYY-MM-DD"
mcp_tools: ["mcp__<server>__<tool>", ...]   # omit if none
---
```

The canonical example is [`by-research/SKILL.md`](by-research/SKILL.md) —
imitate its structure depth.

### 4.2 Mandatory SKILL.md sections

A SKILL.md must have **at least these seven sections** (others are optional
but recommended):

1. **When to Use This Skill** — bulleted ✅ use-cases AND ❌ anti-patterns.
2. **Inputs** — required + optional, with format and source of each.
3. **Outputs** — files written, format, downstream consumers.
4. **Clarification Questions** — Q1 labeled `⚠️ CRITICAL: ASK THIS FIRST`.
5. **Common Issues** — markdown table with ≥ 10 rows: Issue / Cause / Solution / Details.
6. **Suggested Next Steps** — which skill to invoke next, with rationale.
7. **References** — links to every file in `references/` and `scripts/`.

If a section is genuinely N/A for the skill, add a one-line note explaining
why.

### 4.3 Script style (every script you ship)

1. Module docstring (purpose, inputs, outputs, example invocation).
2. Type hints on every public function.
3. `argparse` with `--help` text for CLI scripts; `main()` for library use.
4. Verification on success: `print("✓ <thing> completed: <n> rows / <path>")`.
5. Graceful ImportError: `try: import X; except ImportError: sys.exit("Install with: pip install X")`.
6. `if __name__ == "__main__": main()` guard.
7. No hardcoded absolute paths — accept I/O via CLI args.

### 4.4 References directory

Create `references/` only if the skill has at least one of:
- complex decision-making (algorithm choice, threshold tuning)
- multi-page methodology you do not want bloating SKILL.md
- canonical specifications other skills will quote (e.g.,
  `by-display/references/output-format-spec.md`)

Anti-pattern: `references/` with one 200-line file — fold it back into
SKILL.md instead.

### 4.5 Hard rules

- Do NOT mention any legacy agent names (the previous generation of agents BY descended from) anywhere — search the audit primer for the explicit blocklist.
- Use **Protenix / PXDesign / BoltzGen** as engine names in prose — the
  legacy CLI names (`proteus-fold`, `proteus-prot`, `proteus-ab`) have been
  removed.
- Default compute provider is `local`. When examples reference compute,
  prefer local GPU; HPC is the on-demand fallback; Tamarind is the cloud
  fallback. Refer to `by-deploy-compute` for HPC details — do not re-document.
- Status symbols are exactly `✓ ✗ ◆ ○ ⚠` — never substitute random emoji.
- Banner prefix is `BY ►` — never `GSD ►` or any other.

### 4.6 After authoring

1. Add the skill's directory name to the `skills` array in
   `plugin-manifest.json` (top-level repo).
2. Add a row to this README's **Skill Linkage Map** (§2) in the right category.
3. If the skill produces user-facing output, ensure it calls into `by-display`
   templates — do not invent new visual styles.
4. Commit the skill directory and the manifest update together.

---

## 5. Compute Defaults

BY defaults to **local GPU compute**. The `compute.providers_priority` field
in `.by/config.json` controls the preference order; the canonical default is
`["local", "hpc", "tamarind"]`.

- **Local** is fastest and free, but requires a workstation with a GPU and the
  three engines installed (Protenix, BoltzGen, PXDesign). Paths and conda
  environments live under `compute.local.*` in `.by/config.json`.
- **HPC** is the on-demand fallback — RunPod (default), Modal, or local-network
  SLURM. The `by-deploy-compute` skill handles packaging, sync, and dispatch;
  no other skill should reinvent that logic.
- **Tamarind** is the cloud SaaS option for users without local hardware or
  HPC accounts. It is the slowest path (cold-start queues) but requires no
  local setup.

If `compute.fallback_allowed` is `false`, BY never switches providers without
explicit user approval — a critical safety property for budget-bound campaigns.

---

## 6. Quick Reference

**Q: Which skill should I invoke first?**
A: `by-session`. It is the entry point — runs every time, never optional.
After session init, the next skill depends on intent: research → `by-research`,
resume → `by-campaign-manager`, lookup → `by-database`.

**Q: How do I add a new skill?**
A: Create `templates/.claude/skills/<name>/SKILL.md` with the YAML frontmatter
and the seven mandatory sections from §4. Add `references/` and `scripts/` if
needed. Append the skill to the `skills` array in `plugin-manifest.json` and
add a row to §2 of this README.

**Q: Which scoring metrics are canonical?**
A: `ipSAE` (the min of both directions) is the primary metric; `ipTM` is
secondary; the composite is `0.50 * ipSAE_min + 0.30 * ipTM + 0.20 * (1 -
normalized_liability_count)`. See `by-scoring/SKILL.md` for thresholds and
multi-seed handling.

**Q: Where do lab readouts go?**
A: `by-experiment-results`. It ingests PASS / FAIL / INCONCLUSIVE outcomes,
joins them with predicted scores, and writes the result file consumed by
`by-campaign-optimizer` and `by-knowledge`.

**Q: How do I diagnose a failed campaign?**
A: `by-failure-diagnosis` first — it classifies the failure mode (low ipSAE,
liability hit, fold mismatch, scaffold incompatibility, ...). For
multi-hypothesis root-cause inference, follow with `by-causal-reasoning`.
Persist the conclusion via `by-knowledge` so the next campaign avoids the
same trap.

**Q: Where do I find the canonical display templates?**
A: `by-display/references/output-format-spec.md`. Every other skill should
copy templates verbatim from there — do not improvise widths, symbols, or
labels.

**Q: How do I switch compute provider for a single campaign?**
A: Set `compute.default_provider` in `.by/config.json` (or use `/by:setup` to
edit interactively). For one-off override, pass the provider explicitly to
`by-design-workflow`. Never silently fall back across providers when
`compute.fallback_allowed` is `false`.
