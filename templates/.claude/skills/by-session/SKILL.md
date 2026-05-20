---
id: "skill_c83b4ac84baf4c5e8810cdd0f53a5153"
name: "by-session"
display-name: "BY Session"
short-description: "Session initialization, environment discovery, and first-run configuration for BY projects. Use when opening a new session, running first-time setup, refreshing environment.json, or auditing the active compute provider."
category: "session"
keywords: "session start, config questionnaire, environment.json, config.json, compute provider, local GPU, RunPod, HPC, Tamarind, resume, campaign detection, banner"
version: "1.0"
last-updated: "2026-05-20"
---

# BY Session Skill

Session initialization and configuration for BY projects. This skill defines the full
session-start sequence (banner, environment check, status display) and the first-run
configuration questionnaire that writes `.by/config.json`. It is **not optional** — it
runs every time a new session opens in a BY project directory.

The session skill is the single source of truth for **which compute provider BY will
use this session**. Every downstream skill (by-design-workflow, by-screening, the
design engines) reads `.by/config.json` written here.

---

## When to Use This Skill

Use this skill when you have:

- ✅ **A new session opening** in a BY project directory — the SessionStart hook fires this skill automatically
- ✅ **No `.by/config.json` yet** — run the first-run questionnaire to capture compute provider, model profile, campaign defaults
- ✅ **A request to refresh environment discovery** — re-scan local tools, conda envs, GPU, API keys
- ✅ **A request to switch compute provider** — update `compute.default_provider` cleanly without overwriting unrelated fields
- ✅ **An in-progress campaign** to detect and surface (`campaigns/*/campaign_log.json` with status not `complete`)
- ✅ **Staleness checks** — `.by/environment.json` older than 24h should prompt a refresh

Do NOT use this skill when:

- ❌ **You are mid-campaign and just want status** → use the `status` skill (it reads but does not re-questionnaire)
- ❌ **You need to deploy compute on RunPod / HPC** → use `by-deploy-compute` (this skill only records the *choice* of HPC)
- ❌ **You are scoring designs or running design engines** → use `by-scoring`, `boltzgen`, `pxdesign`, or `protenix`
- ❌ **You want to inspect a specific campaign's state** → use `by-campaign-manager`
- ❌ **The user is editing `.by/config.json` by hand** → read it back with `validate_config.py`, do not re-run the questionnaire

---

## Quick Start

```text
User opens a new terminal in a BY project directory.

Agent (by-session):
  1. Banner    → BY ► Protein Design Agent
  2. Check     → .by/config.json exists?
  3a. NO       → run init_questionnaire.py (or its inline AskUserQuestion equivalent)
                 → writes .by/config.json with local-first defaults
  3b. YES      → read config + environment, no questions asked
  4. Resume    → check campaigns/*/campaign_log.json for in-progress work
  5. Status    → print compute + profile + campaign count
  6. Done      → "Ready" prompt with suggested actions
```

Total time: ~1 second when config exists; ~30 seconds for first-run questionnaire.

---

## Inputs

**Required:**
- **Working directory** — the BY project root (current directory by default).
- **User input** (first run only) — answers to the 3-round questionnaire (compute provider, model profile, campaign defaults).

**Optional (auto-detected):**
- **`.by/config.json`** — if present, skip questionnaire entirely.
- **`.by/environment.json`** — written by `/by:setup`; used to confirm tools and GPU.
- **Environment variables** — `RUNPOD_API_KEY`, `TAMARIND_API_KEY`, etc. for provider detection.
- **`campaigns/*/campaign_log.json`** — used to surface in-progress campaigns.

See `references/config-schema.md` for the full schema of both JSON files.

---

## Outputs

All outputs land under `.by/` in the project root.

| File | Type | When written | Purpose |
|------|------|--------------|---------|
| `.by/config.json` | JSON | First run, or on user-driven update | User preferences: compute provider, providers_priority, model_profile, campaign defaults |
| `.by/environment.json` | JSON | First run + `/by:setup` refresh | Auto-detected hardware/tools snapshot (GPU model, VRAM, conda envs, tool paths, API keys present) |
| Terminal banner | Text | Every session | Branded session header |
| Status block | Text | Every session | Compute provider in use, profile, campaign count, next-step prompts |

The `.by/config.json` schema is canonical and downstream-critical: every BY skill that
selects a compute provider reads this file. See `references/config-schema.md`.

---

## Clarification Questions

⚠️ **CRITICAL: ASK THIS FIRST** — Confirm `.by/config.json` does not already exist
before running the questionnaire. Re-running the questionnaire would overwrite the
user's saved preferences.

1. **Config file presence (ASK THIS FIRST)** — Does `.by/config.json` already exist? If yes, skip the questionnaire and go straight to the session banner. If no, proceed to Q2. (You can check this silently — only ask the user if there's ambiguity, e.g., the file exists but is corrupted.)
2. **Compute provider** — Where should BY run design computations? Options: `local` (recommended default — uses local GPU), `hpc` (RunPod or other HPC target deployed via `by-deploy-compute`), `tamarind` (Tamarind Bio cloud), `auto` (detect best available in priority order). **The default is `local`.**
3. **Local GPU tool paths** (only if provider is `local` or `auto`) — Where are BoltzGen, Protenix, and PXDesign installed? Auto-detect from `PATH` and common locations, or accept a custom path per tool. Validate each path exists.
4. **HPC target** (only if provider is `hpc`) — Which HPC target? Default `runpod`. The actual deployment is handled by `by-deploy-compute`; this skill only records the choice and the `api_key_env` variable name.
5. **Tamarind API key** (only if provider is `tamarind`) — Is `TAMARIND_API_KEY` set in `.env` or the shell environment? If missing, point the user to https://tamarind.bio for a free key before continuing.
6. **Model profile** — Which AI model profile for sub-agents? `balanced` (Sonnet, recommended), `quality` (Opus for research/design agents), `budget` (Haiku where possible).
7. **Default campaign tier** — Default designs per campaign? `preview` (~500, fast feasibility checks), `standard` (~5,000, recommended), `production` (~20,000, thorough coverage).

See `references/config-schema.md` for the exact field names each answer maps to.

---

## Standard Workflow

🚨 **MANDATORY: USE THE TWO PROVIDED SCRIPTS — DO NOT WRITE INLINE PYTHON** 🚨

This skill ships two scripts that codify the questionnaire and validation logic:

- `scripts/init_questionnaire.py` — interactive or `--defaults` first-run setup; writes `.by/config.json`.
- `scripts/validate_config.py` — reads `.by/config.json`, validates against the documented schema, prints issues.

When a script does not fit (e.g., the user wants to flip a single field), edit the
JSON directly and re-run `validate_config.py` to confirm correctness. Do not invent a
new questionnaire flow inline.

### Step 1 — Detect first-run vs returning session

```bash
test -f .by/config.json && echo "returning" || echo "first-run"
```

✅ **VERIFICATION:** Output is exactly `returning` or `first-run`.

### Step 2a — First-run: run the questionnaire

```bash
python3 .claude/skills/by-session/scripts/init_questionnaire.py
```

Or for a non-interactive default install (CI, automated scaffolding):

```bash
python3 .claude/skills/by-session/scripts/init_questionnaire.py --defaults
```

✅ **VERIFICATION:** Expect `✓ Wrote .by/config.json with provider=local` (or whichever provider the user selected).

The questionnaire collects answers in three rounds (compute, profile, campaign
defaults) and writes `.by/config.json`. The **default provider is `local`** and
`providers_priority` is `["local", "hpc", "tamarind"]`. If the user picks `hpc`, the
skill records the HPC target (default `runpod`) and the env var name for the API key,
but does NOT deploy anything — deployment lives in `by-deploy-compute`.

### Step 2b — Returning session: read config + environment

```bash
python3 .claude/skills/by-session/scripts/validate_config.py .by/config.json
```

✅ **VERIFICATION:** Expect `✓ Config valid: provider=<name>, profile=<name>`.

If validation fails, surface the specific field error to the user and ask before
overwriting anything. Do NOT silently re-run the questionnaire.

### Step 3 — Show banner

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► Protein Design Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 4 — Check for in-progress campaigns

```bash
ls campaigns/*/campaign_log.json 2>/dev/null
```

Count campaigns and inspect each `status` field. See `references/resume-protocol.md`
for the exact rules on what counts as "in progress" and what gets restored.

### Step 5 — Display status

Build the compute line from `compute.default_provider` and any populated provider
blocks. Examples:

- `Compute: Local GPU ✓ (BoltzGen, Protenix, PXDesign)`
- `Compute: HPC ✓ (target=runpod, key=RUNPOD_API_KEY)`
- `Compute: Tamarind ✓ (free tier)`

Full display:

```text
Compute: Local GPU ✓ (BoltzGen, Protenix, PXDesign)
Profile: balanced | Default: standard (5,000/scaffold)
Campaigns: 3 previous, 1 active (anti-HER2 — designing 80%)

Ready:
  "Design [modality] against [target]"
  /by:plan-campaign — guided setup
  /by:status — existing campaigns
```

### Anti-patterns

⚠️ **CRITICAL — DO NOT:**
- ❌ Re-run the questionnaire if `.by/config.json` already exists → STOP: read it instead
- ❌ Default to `tamarind` → the new default is `local`; respect `providers_priority`
- ❌ Silently overwrite unrelated fields in `config.json` → load, mutate only target field, save
- ❌ Block the session on a single failed tool check → mark `✗` with reason, continue
- ❌ Deploy HPC infrastructure here → that is `by-deploy-compute`'s job

---

## When Scripts Fail

Script-failure hierarchy (per the BY quality bar):

1. **Fix and Retry (90%)** — `python3 -m pip install -e .` may be needed if the project venv is stale; or set `PYTHONPATH` to include the templates dir. Re-run the script.
2. **Modify Script (5%)** — If the questionnaire flow is missing a new option (e.g., a new HPC target), add a branch to `init_questionnaire.py`. Keep validation in `validate_config.py` in sync.
3. **Use as Reference (4%)** — If the script's behavior is wrong for this user's edge case (e.g., heterogeneous multi-node setup), read the script and adapt the writes manually with `python -c "import json; ..."`.
4. **Write from Scratch (1%)** — Only if `config.json` semantics have changed enough that the script is misleading; in that case, update `references/config-schema.md` first, then the script.

| Decision | Action |
|---|---|
| Missing `python3` | Step 1 — install Python 3.10+ |
| Missing `argparse` (impossible: stdlib) | Step 1 — Python is broken; reinstall |
| User wants to keep current config but switch one field | Step 3 — `python3 -c "import json,pathlib; p=pathlib.Path('.by/config.json'); c=json.loads(p.read_text()); c['compute']['default_provider']='hpc'; p.write_text(json.dumps(c, indent=2))"` |
| Script crashes on malformed config | Step 2 — patch `validate_config.py` to surface a friendlier error |

---

## Decision Points

### Default provider selection

| Situation | Recommended provider | Why |
|---|---|---|
| User has a local NVIDIA GPU with ≥ 24 GB VRAM | `local` | Fastest, no cloud cost; matches new default |
| User has a local GPU but with < 24 GB VRAM | `local` for inference, `hpc` for design | BoltzGen design is memory-heavy |
| User has no local GPU, has RunPod credits | `hpc` (target=runpod) | Predictable cost, full GPU control via `by-deploy-compute` |
| User has no local GPU, no HPC credits | `tamarind` | Free tier covers small campaigns |
| User is unsure | `auto` | Probes in order `local → hpc → tamarind` |

### Model profile selection

| Profile | Sub-agent models | When to choose |
|---|---|---|
| `balanced` | Sonnet for most agents | Default — good quality/cost ratio |
| `quality` | Opus for research + design | Novel target, high-stakes campaign |
| `budget` | Haiku where possible | Cost-constrained, well-studied target |

### Campaign tier default

| Tier | Designs/scaffold | When to default to it |
|---|---|---|
| `preview` | ~500 | Tutorials, feasibility checks |
| `standard` | ~5,000 | Recommended; most campaigns |
| `production` | ~20,000 | Hard targets, last-mile screening |

---

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `.by/config.json` exists but `default_provider` is `tamarind` | Pre-2026-05 config — Tamarind used to be the default | Run `validate_config.py --suggest-fix` to surface; offer to flip to `local` |
| Questionnaire re-runs every session | `.by/config.json` is being deleted by a hook or `.gitignore` exclusion | Confirm `.by/` is committed (or at least persisted between sessions); inspect `.git/info/exclude` and `.gitignore` |
| `validate_config.py` reports `providers_priority` missing | Config predates the local-first migration | Run `init_questionnaire.py --defaults --keep-existing` to merge in the new field without nuking other settings |
| `compute.hpc.target` is empty after picking `hpc` | User skipped Q4 | Re-ask Q4; default is `runpod` |
| `RUNPOD_API_KEY` env var unset but provider is `hpc` | API key not exported in `.env` | Point user to `by-deploy-compute` for setup; do NOT block the session |
| `TAMARIND_API_KEY` env var unset but provider is `tamarind` | Same as above for Tamarind | Show the signup URL; mark provider `✗` in status until set |
| Local GPU tool paths point to nonexistent dirs | Tools moved or were never installed | Mark each tool `✗ <reason>` in the status block; do NOT change config without asking |
| Banner prints garbled box-drawing characters | Terminal not UTF-8 | Document the limitation; suggest `export LANG=en_US.UTF-8` |
| `environment.json` is older than 24h | User ran `/by:setup` long ago; tools may have changed | Suggest `/by:setup` to refresh; do NOT auto-refresh without consent |
| Multiple `.by/` dirs in nested project roots | Monorepo with sub-projects | Use the closest `.by/` walking up from `cwd`; document the choice in the status block |
| In-progress campaign was force-killed and `campaign_log.json` says `running` | Stale lock | See `references/resume-protocol.md` — surface to user, ask whether to resume or mark complete |
| Sub-agent receives the wrong compute provider | Sub-agent did not read `.by/config.json` | Always include the compute config explicitly in `Task()` prompts; this skill cannot enforce that downstream |

---

## Best Practices

1. 🚨 **CRITICAL:** Always check `.by/config.json` existence BEFORE running the questionnaire — re-running silently overwrites user preferences.
2. ✅ **REQUIRED:** Use `scripts/init_questionnaire.py` and `scripts/validate_config.py` — do not write inline Python for these flows.
3. ✅ Honor `providers_priority` (`["local", "hpc", "tamarind"]`) when `default_provider` is `auto`.
4. ✅ When updating config, read-modify-write — never replace the file wholesale unless the user opts in.
5. ✅ Surface compute-provider issues but do NOT block the session — the user may want to fix them mid-session.
6. ✅ Treat `.by/environment.json` as advisory; the config is canonical for "which provider to use".
7. ❌ Never expose API key VALUES in the banner or logs — only `present/missing`.
8. ❌ Never silently fall back from `local` to `tamarind` — respect the user's explicit choice.
9. ✨ **Optional:** Cache the questionnaire answers in `.by/.questionnaire-history.json` if the user re-runs setup, so we can suggest their previous choices as defaults.

---

## Suggested Next Steps

After the session is initialized, common next moves:

- **`by-design-workflow`** — when the user describes a target, this is the master orchestration skill that decides which design engine to invoke (it reads the compute provider from `.by/config.json` written here).
- **`by-research`** — if the user is starting a new campaign against an unfamiliar target, research is always step 1.
- **`by-campaign-manager`** — if the session detected an in-progress campaign, hand off to this skill for resume.
- **`by-deploy-compute`** — if the user selected `hpc` but the actual deployment is not yet active.
- **`/by:status`** — if the user just wants a campaign-status summary without starting work.

The chaining matters: by-session's job is to *prepare the environment*; downstream
skills consume `.by/config.json` and trust it. Keep that contract clean.

---

## Related Skills

**Upstream (run before by-session):** None — this skill is the entry point.

**Downstream (run after by-session):**
- `by-design-workflow` — master orchestration; reads provider from config
- `by-research` — first step of any new campaign
- `by-campaign-manager` — for resume of in-progress campaigns

**Alternative / Complementary:**
- `by-deploy-compute` — handles the *deployment* side of HPC; by-session only records the *choice*
- `status` (slash command skill) — read-only campaign status; does not modify config

---

## References

**Detailed documentation (`references/`):**
- [`references/config-schema.md`](references/config-schema.md) — Full JSON Schema for `.by/config.json` and `.by/environment.json`, including the post-2026-05 fields (`providers_priority`, `compute.hpc.target`, `compute.hpc.api_key_env`).
- [`references/resume-protocol.md`](references/resume-protocol.md) — Detection rules for in-progress campaigns, checkpoint loading, and what is restored vs re-asked when a session reopens mid-campaign.

**Scripts (`scripts/`):**
- `scripts/init_questionnaire.py` — Interactive (or `--defaults`) first-run config flow. Asks: local GPU available? RunPod API key? Tamarind key? Writes `.by/config.json` with local-first defaults.
- `scripts/validate_config.py` — Reads `.by/config.json`, validates against the schema documented in `references/config-schema.md`, prints actionable issues.

**Project context:**
- `templates/CLAUDE.md` — the "Compute Provider Selection" section is the authoritative prose explanation of the local-first ordering this skill enforces.
- `templates/.by/config.json` — the canonical default config shipped with new projects.
