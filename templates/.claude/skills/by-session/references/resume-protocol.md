# Session Resume Protocol

When a user reopens a session in a BY project, the `by-session` skill must decide:

1. Are there campaigns in progress?
2. Which one (if any) should we surface to the user?
3. What state gets restored automatically vs re-asked?
4. When do we hand off to `by-campaign-manager` for full resume?

This document is the authoritative spec for that decision tree.

---

## 1. What Counts as "In Progress"

A campaign is **in progress** if both of the following are true:

- `campaigns/<target>/<campaign_id>/campaign_log.json` exists
- `campaign_log.json.status` is **not** in the terminal set `{complete, failed_abandoned, archived}`

Non-terminal statuses (treated as in-progress):

| Status | Meaning |
|---|---|
| `initialized` | Plan written, not yet approved |
| `plan_approved` | Plan approved, no compute submitted yet |
| `researching` | by-research is mid-pipeline |
| `designing` | Design engines actively running |
| `screening` | by-screening filtering designs |
| `ranking` | Final ranking step |
| `paused` | User asked to pause; explicit checkpoint exists |

Terminal statuses (NOT in-progress):

| Status | Meaning |
|---|---|
| `complete` | All phases finished, results delivered |
| `failed_abandoned` | User chose not to retry |
| `archived` | Older campaign moved to long-term storage |

---

## 2. Detection Flow

```text
session start
    │
    ▼
read .by/config.json   ─── if missing → run questionnaire (Round 1-3)
    │
    ▼
scan campaigns/*/campaign_log.json
    │
    ▼
count by status:
  ─ N_total = all campaigns
  ─ N_active = campaigns with status ∉ terminal_set
    │
    ▼
N_active == 0  ──→ show "Campaigns: N_total previous"
N_active == 1  ──→ show "Campaigns: N_total previous, 1 active (<target> — <phase> <pct>%)"
N_active >= 2  ──→ show "Campaigns: N_total previous, K active" + list them
```

The session skill does NOT auto-resume — it surfaces the in-progress campaign and
lets the user decide. Auto-resume would risk re-submitting paid compute.

---

## 3. What's Restored Automatically

When `by-session` detects in-progress campaigns, it does these things automatically
(no questions asked):

- ✅ Read each `campaign_log.json` and parse `status`, `phase`, `pct_complete`
- ✅ Read `campaigns/<id>/campaign_plan.md` if present (to display target name)
- ✅ Read `campaigns/<id>/research/research.md` summary line if present (Phase 1 of Research is enough)
- ✅ Compute the staleness of the most recent checkpoint (`last_checkpoint_at`)
- ✅ Render the status block with this info

That's it. Anything more is deferred to `by-campaign-manager`.

---

## 4. What's Re-Asked

The session skill re-asks the user for:

- ❓ **Should we resume this campaign now?** — Yes / No / Show details first
- ❓ **Compute provider has changed since pause** — If `.by/config.json.compute.default_provider` differs from `campaign_log.json.compute_provider_at_pause`, ask explicitly: "This campaign was running on `<old>`; your current provider is `<new>`. Continue on `<new>`?"

The session skill does NOT re-ask:

- ❌ Anything covered by the original campaign plan (target, modality, tier, scaffolds)
- ❌ Model profile (lives in config, not per-campaign)
- ❌ Whether to enable fold validation (lives in config)

---

## 5. Checkpoint Files

Each campaign has these checkpoints. `by-session` only *detects* them; it does not
*load* them (that's `by-campaign-manager`'s job).

| File | Written by | Used for resume? |
|---|---|---|
| `campaigns/<id>/campaign_log.json` | by-campaign-manager (every phase transition) | Yes — primary source of truth |
| `campaigns/<id>/research/research_progress.json` | by-research (every phase) | Yes — for in-progress research |
| `campaigns/<id>/design/design_jobs.json` | by-design-workflow (per job batch) | Yes — for in-progress design |
| `campaigns/<id>/screening/screening_state.json` | by-screening (per batch) | Yes — for in-progress screening |
| `campaigns/<id>/checkpoints/<phase>_<timestamp>.json` | various skills | Reference history; not loaded automatically |

The session skill checks for the presence of these files but does not parse them
beyond `campaign_log.json`. Deep parsing is `by-campaign-manager`'s job.

---

## 6. Stale Lock Handling

A "stale lock" is when `campaign_log.json.status == "designing"` (or any active
status) but no design jobs are actually running. Detect via:

- The `last_checkpoint_at` timestamp is more than 1 hour old AND status is non-terminal
- OR the user explicitly says "I killed that run yesterday"

When detected:

```text
⚠️  Campaign 'anti-HER2 vhh' shows status=designing but last activity was 3 days ago.
    The previous run may have been killed.

    Options:
      1. Mark as paused and resume cleanly (recommended)
      2. Mark as failed_abandoned (will not resume)
      3. Leave as-is (continue session without touching it)
```

Ask the user — do NOT silently flip the status.

---

## 7. Resume Handoff

When the user says "yes, resume", `by-session` hands off to `by-campaign-manager`:

```text
by-session → by-campaign-manager:
  campaign_id: <id>
  campaign_dir: campaigns/<target>/<id>
  current_status: <status from campaign_log.json>
  compute_provider: <from .by/config.json>
  user_consented_to_compute_change: <bool>
```

`by-campaign-manager` is responsible for:
- Loading the full state (research, design, screening checkpoints)
- Validating the checkpoints are mutually consistent
- Surfacing any mismatches to the user
- Continuing from the right phase

The session skill's job ends at the handoff.

---

## 8. Zero-Campaign First-Use

When `N_total == 0`, the session skill shows the welcome prompt:

```text
Campaigns: none yet

Ready:
  "Design nanobodies against [target]"  — start your first campaign
  /by:welcome                            — first-time walkthrough
  /by:plan-campaign                      — guided setup
```

No resume logic needed.

---

## 9. Multi-Project Edge Case

If the user's `cwd` is a sub-directory of a BY project (e.g., they cd'd into
`campaigns/anti-HER2/campaign_20260520_001/`), the session skill walks up looking
for `.by/config.json` and treats the first hit as the project root. This is to
avoid creating duplicate `.by/` dirs in nested paths.

Document the resolved project root in the status block:

```text
Project root: ~/work/blatant-why-projects/lab-targets-2026
```

Only print the path if it differs from `cwd`.

---

## 10. Summary: What the Session Skill Decides

| Question | Where the answer lives | by-session role |
|---|---|---|
| Should we run the questionnaire? | `.by/config.json` exists? | Decide |
| Which compute provider this session? | `config.json.compute.default_provider` | Read, render in status |
| Are there in-progress campaigns? | scan of `campaigns/*/campaign_log.json` | Detect, surface |
| Should we resume one now? | Ask the user | Ask |
| How exactly to resume? | `by-campaign-manager` | Hand off |
| Was a previous run killed? | `last_checkpoint_at` heuristic | Detect, ask user |
| Is environment.json stale? | `last_scanned_at` > 24h | Warn, don't block |
