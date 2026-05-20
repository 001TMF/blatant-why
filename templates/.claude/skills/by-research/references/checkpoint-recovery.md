# Checkpoint Recovery

The 8-phase research pipeline is designed to survive context compaction, mid-session
crashes, and explicit pauses. Every phase writes a JSON output to the campaign
directory and updates `research_progress.json`. This reference explains how to
resume from any phase and how to correctly invalidate downstream phases when an
upstream finding changes.

---

## Checkpoint Format

`research/research_progress.json` is the single source of truth for pipeline state.
After every phase, overwrite it with the current snapshot.

### Schema

```json
{
  "campaign_id": "tnf_alpha_20260520_001",
  "target_name": "TNF-alpha",
  "research_depth": "standard",
  "current_phase": 4,
  "completed_phases": [1, 2, 3],
  "phase_outputs": {
    "1": "research/scope.json",
    "2": "research/research_plan.json",
    "3": "research/sources.json"
  },
  "sources_count": 12,
  "high_confidence_findings": 0,
  "quality_gate_status": {
    "phase_3_sources_gate": "PASS",
    "phase_4_confidence_gate": "PENDING",
    "phase_6_critique_gate": "PENDING",
    "phase_8_citation_gate": "PENDING"
  },
  "iteration_count": 0,
  "max_iterations": 2,
  "started_at": "2026-05-20T10:00:00Z",
  "last_checkpoint": "2026-05-20T10:08:30Z",
  "notes": []
}
```

### Field semantics

| Field | Meaning |
|-------|---------|
| `campaign_id` | Unique campaign directory id (target_date_seq) |
| `target_name` | Display name carried from scope.json |
| `research_depth` | quick / standard / deep / ultradeep |
| `current_phase` | The phase about to run (or in progress). Integer 1-8. |
| `completed_phases` | Sorted list of phase integers fully written |
| `phase_outputs` | Map of phase number → file path of the phase's primary output |
| `sources_count` | Count of unique entries in sources.json (for quality gate check) |
| `high_confidence_findings` | Count of HIGH confidence findings in validated_findings.json |
| `quality_gate_status` | PASS / FAIL / PENDING for each quality gate |
| `iteration_count` | How many times we've looped back from Phase 6/7 to Phase 3 |
| `max_iterations` | Cap on retrieval iterations (Deep=1, UltraDeep=2-3) |
| `started_at`, `last_checkpoint` | ISO 8601 timestamps |
| `notes` | Free-form list of any operator-visible notes (e.g., "user added seed sources") |

### Invariants

The checkpoint MUST satisfy these conditions; if it does not, treat it as corrupt
and rebuild from the JSON outputs that exist in the directory.

1. `max(completed_phases) < current_phase` (you cannot be "currently in" a completed phase)
2. Every phase listed in `phase_outputs` must also appear in `completed_phases`
3. Every file path in `phase_outputs` must exist on disk
4. `sources_count` must equal `len(sources.json["sources"])`

---

## Resume Protocol

When restarting after context compaction or explicit pause:

### Step 1: Locate the checkpoint

```text
campaigns/{target}/campaign_{date}_{id}/research/research_progress.json
```

If multiple campaign directories exist for the same target, take the most recent
`last_checkpoint` timestamp.

### Step 2: Validate invariants

Reject the checkpoint and rebuild from disk if any invariant fails:

- Iterate phase numbers 1-8, check if each `phase_outputs[N]` file exists
- Set `completed_phases` to phases whose outputs exist
- Set `current_phase` to `max(completed_phases) + 1`
- Set `sources_count` to actual count from sources.json (if present)

### Step 3: Load only the needed outputs

To continue, load:

- Always: `scope.json` (drives all phases) and `research_progress.json`
- If continuing Phase 3+: `research_plan.json`
- If continuing Phase 4+: `sources.json`
- If continuing Phase 5+: `validated_findings.json`
- If continuing Phase 6+: the synthesis draft (held in `research.md` or memory)
- If continuing Phase 7+: `critique.json`
- If continuing Phase 8: all prior outputs

Do NOT reload outputs you don't need — large `sources.json` files can blow the
context window unnecessarily.

### Step 4: Confirm with the user (optional but recommended)

For pauses longer than a few minutes, present a one-line summary:

```text
Resuming TNF-alpha research from Phase 4 (TRIANGULATE).
Completed phases: 1, 2, 3. Sources: 12. Depth: standard.
Proceed? (Y/n)
```

### Step 5: Execute the current phase

Run the phase normally. On completion, update `research_progress.json` before
moving to the next phase.

---

## Invalidating Downstream Phases

When a finding in an earlier phase changes (e.g., Phase 6 critique forces a Phase 3
re-retrieval), downstream phase outputs are no longer valid. Invalidate them
explicitly to prevent reuse of stale conclusions.

### Forward propagation rules

| If you change | Then invalidate | Reason |
|---------------|----------------|--------|
| `scope.json` (Phase 1) | ALL subsequent phases (2-8) | Scope drives everything |
| `research_plan.json` (Phase 2) | Phases 3-8 | New search strategy → new sources |
| `sources.json` (Phase 3) | Phases 4-8 | New sources change triangulation |
| `validated_findings.json` (Phase 4) | Phases 5-8 | New confidence values change synthesis |
| Phase 5 synthesis | Phases 6-8 | New narrative requires re-critique |
| `critique.json` (Phase 6) | Phase 7 only (if refinement needed) | Critique itself is informational |
| Phase 7 refinement updates to sources.json | Phases 4-8 (re-triangulate) | Refinement adds new sources |

### How to invalidate

1. Remove the affected phase numbers from `completed_phases`
2. Remove their entries from `phase_outputs`
3. Set `current_phase` to the lowest invalidated phase
4. Increment `iteration_count` (count loops back through Phase 3)
5. Check `iteration_count <= max_iterations` — if exceeded, package what you
   have with a `preliminary` flag rather than looping forever
6. Append a note to `notes`: `"Invalidated phases X-Y due to {reason}"`
7. Leave the actual JSON output files on disk (do not delete) — they remain
   useful as audit trail

### Example: Phase 6 surfaces a CRITICAL concern

Trigger: Phase 6 Adversarial Reviewer finds that SAbDab antibodies bind a different
epitope than the literature consensus.

Action:
1. Invalidate Phases 4, 5 (`completed_phases: [1, 2, 3]`)
2. Set `current_phase: 3` (return to retrieval with a targeted query)
3. `iteration_count: 1`
4. Add to `notes`: `"Iter 1: Critical critique on epitope contradiction; targeted Phase 3 retrieval"`
5. Run a focused Phase 3 query (e.g., SAbDab CDR sequences for the specific
   epitope region) and re-add sources
6. Re-run Phase 4 → 5 → 6 → 7 → 8

### Example: User adds a missed PMID after Phase 5

Trigger: User says "you missed Smith 2024, please include PMID 12345678."

Action:
1. Add the source to `sources.json` (Phase 3 output)
2. Invalidate Phases 4, 5, 6, 7 if completed
3. Set `current_phase: 4`
4. Re-triangulate. The new source may change confidence levels.

---

## Crash Recovery vs Resume

Distinguish these two cases:

| Case | Trigger | Action |
|------|---------|--------|
| **Clean resume** | User explicitly paused, or context compacted between phases | Load checkpoint, continue from `current_phase` |
| **Crash recovery** | Process died mid-phase, leaving incomplete output | Rebuild checkpoint from disk (see Step 2 above); the half-written phase output may be salvageable or may need to be redone |

For crash recovery, if a phase output exists but the next checkpoint update did not happen, the operator should re-validate the output before trusting it (open the file, check it parses, check the timestamps match the rest of the campaign).

---

## Anti-Drift Discipline

The checkpoint pattern only works if every phase obeys these rules:

- ✅ Write the phase output BEFORE updating `research_progress.json`
- ✅ Update `research_progress.json` atomically (write to temp, rename) so partial writes never leave a corrupt checkpoint
- ✅ Never edit a completed phase output without invalidating downstream phases
- ❌ Never claim a phase is complete based on memory; the file must exist on disk
- ❌ Never skip ahead — Phase 5 cannot read findings that weren't written in Phase 4

If these rules are violated, the resume protocol's invariant checks will catch the corruption and force a rebuild from disk.
