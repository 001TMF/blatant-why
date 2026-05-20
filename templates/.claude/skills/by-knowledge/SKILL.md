---
id: "skill_1074c69b6e034130bea9cd82aa22cfe2"
name: "by-knowledge"
display-name: "BY Knowledge Graph"
short-description: "Persistent structured memory across campaigns — record and recall targets, scaffolds, designs, screening results, and failure patterns. Use when starting a new campaign, recording outcomes after screening, diagnosing repeated failures, or recommending parameters based on prior art."
category: "persistence"
keywords: "knowledge graph, persistent memory, campaign history, scaffold rankings, failure patterns, cross-campaign learning, NDJSON, entity, relationship"
version: "1.0"
last-updated: "2026-05-20"
mcp_tools: ["mcp__by-knowledge__knowledge_store_campaign", "mcp__by-knowledge__knowledge_query_similar", "mcp__by-knowledge__knowledge_scaffold_rankings", "mcp__by-knowledge__knowledge_store_failure", "mcp__by-knowledge__knowledge_get_recommendations", "mcp__by-knowledge__knowledge_consolidate"]
---

# BY Knowledge Graph

Persistent structured memory that turns isolated campaigns into a learning system.
Each campaign writes outcomes, top designs, and failure modes into a JSON-backed
graph so the next campaign benefits from prior art without re-running compute.

The store is intentionally minimal: append-only JSON files, no server process, no
embeddings — keyword overlap is enough for the scale we operate at (hundreds to
low thousands of campaigns). Six MCP tools wrap the storage layer so every agent
in the BY suite reads and writes through the same contract.

---

## When to Use This Skill

Use this skill when:
- ✅ Starting a new campaign — query prior campaigns and scaffold rankings before committing compute
- ✅ Finishing a campaign — record outcomes, top designs, and any failure patterns
- ✅ Diagnosing low pass rates — search for matching failure patterns from prior campaigns
- ✅ Pre-flight parameter selection — call `knowledge_get_recommendations` to seed defaults
- ✅ Periodic maintenance — run `knowledge_consolidate` after every 20-30 campaigns
- ✅ Cross-target analysis — compare hit rates of a scaffold across target classes

Don't use this skill for:
- ❌ Storing raw design files — those live in the campaign directory (FASTA, PDB, CIF)
- ❌ Storing every design from a campaign — record the top 10-20 only (selectivity matters)
- ❌ Replacing the research dossier — `by-research` writes `research/research.md`; this skill stores the summary
- ❌ Per-job telemetry or compute logs — use `by-campaign-manager` checkpoints instead
- ❌ Free-form notes that have no entity to attach to — write them to `.claude/memory/` directly

The graph is a long-lived asset. Be selective on writes; aggressive on queries.

---

## Quick Start

```python
# 1. Query prior art at campaign start
result = mcp__by_knowledge__knowledge_query_similar(
    target_description="TNF-alpha cytokine homotrimer autoimmune",
    modality="VHH",
    top_k=5,
)

# 2. Record outcomes at campaign end (top 10-20 designs, not all of them)
mcp__by_knowledge__knowledge_store_campaign(
    target="TNF-alpha",
    modality="VHH",
    parameters={"scaffold": "caplacizumab", "seeds": 4, "temperature": 0.7},
    outcomes={
        "hit_rate": 0.23,
        "best_ipsae": 0.78,
        "best_iptm": 0.85,
        "screening_pass_rate": 0.18,
    },
    notes="Iter-2 hotspot refinement converged on Y56/R113",
    designs=[
        {"design_id": "tnf_001", "scaffold": "caplacizumab", "ipsae": 0.78, "iptm": 0.85, "status": "PASS"},
        # ... up to ~20 top designs
    ],
)
```

Expected runtime: <100 ms per call (no network, no DB engine). Storage is local
JSON; first call seeds `~/.by/knowledge/` if missing.

---

## Installation

| Software | Version | License | Commercial Use | Installation |
|----------|---------|---------|----------------|--------------|
| Python | >= 3.11 | PSF | ✅ Permitted | Pre-installed in BY env |
| `mcp` SDK | >= 1.0.0 | MIT | ✅ Permitted | `pip install mcp` |
| `jsonschema` (optional, for migration) | >= 4.0 | MIT | ✅ Permitted | `pip install jsonschema` |

No database, no server process, no compute. The MCP server starts cold in under
one second. License Compliance: All packages permit commercial use.

**Storage directory resolution** (priority order):
1. `KNOWLEDGE_DIR` environment variable (explicit override)
2. `$BY_PROJECT_ROOT/.by/knowledge/` (project-local)
3. `~/.by/knowledge/` (home directory fallback)

---

## Inputs

**Required for `knowledge_store_campaign`:**
- `target` (str): Target name. Use lowercase-hyphenated form for stability (e.g. `"tnf-alpha"`, `"pd-l1"`).
- `modality` (str): One of `"antibody"`, `"nanobody"`, `"VHH"`, `"scFv"`, `"de_novo"`, `"binder"`.
- `parameters` (dict): Scaffold, seeds, temperature, MSA mode, etc.
- `outcomes` (dict): Must include `hit_rate`, `best_ipsae`, `best_iptm`, `screening_pass_rate` where available.

**Optional:**
- `notes` (str): Free-text, indexed for keyword search.
- `designs` (list[dict]): Top 10-20 designs with `design_id`, `scaffold`, `ipsae`, `iptm`, `status` (`PASS`/`FAIL`).

**Required for `knowledge_store_failure`:**
- `campaign_id` (str): Stable identifier (use the campaign directory name).
- `description` (str): What broke.
- `root_cause` (str): Underlying cause from post-mortem.
- `target` (str): Target the campaign was for.

See [references/graph-schema.md](references/graph-schema.md) for the full JSON
Schema of every entity and relationship type.

---

## Outputs

All write tools return a JSON envelope:
```json
{
  "status": "stored",
  "id": "campaign_a1b2c3d4e5f6",
  "document": "Campaign targeting TNF-alpha using VHH modality. Scaffold: caplacizumab. Hit rate: 0.23. Best ipSAE: 0.78.",
  "metadata": { /* echoed back for confirmation */ }
}
```

All read tools return result lists with similarity scores:
```json
{
  "results": [
    {
      "id": "campaign_a1b2c3d4e5f6",
      "similarity": 0.83,
      "document": "Campaign targeting TNF-alpha...",
      "metadata": { "target": "...", "outcomes": {...}, "parameters": {...} }
    }
  ],
  "query": "TNF-alpha"
}
```

**Persisted files** in `~/.by/knowledge/` (or override path):
| File | Format | Contents |
|------|--------|----------|
| `campaigns.json` | JSON array | Campaign records with parameters, outcomes, notes, optional designs |
| `failures.json` | JSON array | Failure records with description, root_cause, target |

For NDJSON entity dumps (migration / external analytics), use the
`migrate_knowledge.py` script in `scripts/` — it normalizes the on-disk arrays
into the schema in [references/graph-schema.md](references/graph-schema.md).

---

## Clarification Questions

**⚠️ CRITICAL: ASK THIS FIRST** — Always confirm there is a campaign or outcome
to record before invoking write tools.

1. **Storage scope** (ASK THIS FIRST): Do we have a completed campaign with screening outcomes ready to record? Or are we querying for a new campaign that hasn't started? Writing without outcomes pollutes the graph.
2. **Target normalization**: Has the target been recorded before under a different name? (e.g. `TNF`, `TNF-alpha`, `TNF_alpha`, `tumor necrosis factor`). Decide canonical form before writing.
3. **Design selectivity**: How many designs should be recorded? Default is top 10-20 by composite score. Recording all hundreds bloats the graph and slows query.
4. **Failure boundaries**: Is this a recurring failure pattern worth recording, or a one-off bug? Only patterns that may repeat across campaigns belong in `failures.json`.
5. **Maintenance cadence**: When was `knowledge_consolidate` last run? After 20-30 new campaigns, dedup + prune keeps query speed up.
6. **Storage location**: Is `KNOWLEDGE_DIR` set, or are we using the default `~/.by/knowledge/`? Project-local stores (under `$BY_PROJECT_ROOT/.by/knowledge/`) keep teams from cross-contaminating data.
7. **Migration intent**: Are we upgrading schema version, migrating between machines, or just backing up? Different paths in `migrate_knowledge.py`.

See [references/query-patterns.md](references/query-patterns.md) for query
template selection guidance per question.

---

## Standard Workflow

🚨 **MANDATORY: USE THE MCP TOOLS — DO NOT WRITE DIRECTLY TO JSON FILES** 🚨

Direct file writes bypass the atomic-rename safety, skip validation, and break
concurrent-access guarantees.

### At campaign start (read-only)

1. Query similar past campaigns:
   ```python
   mcp__by_knowledge__knowledge_query_similar(
       target_description="<target name + organism + class>",
       modality="<VHH|antibody|de_novo>",
       top_k=5,
   )
   ```
   ✅ **VERIFICATION**: Result `results` array length matches `top_k` (or fewer if graph is small).

2. Get scaffold rankings for target class:
   ```python
   mcp__by_knowledge__knowledge_scaffold_rankings(target_class="cytokine")
   ```

3. Pull all-in-one recommendations:
   ```python
   mcp__by_knowledge__knowledge_get_recommendations(
       target="TNF-alpha",
       modality="VHH",
   )
   ```
   Returns `similar_campaigns`, `recommended_scaffolds`, `warnings` (from failures), and `suggested_parameters`.

### At campaign end (writes)

4. Record campaign outcomes:
   ```python
   mcp__by_knowledge__knowledge_store_campaign(
       target=..., modality=..., parameters={...}, outcomes={...}, designs=[...]
   )
   ```
   ✅ **VERIFICATION**: Response `status == "stored"` and `id` matches `campaign_*` pattern.

5. Record any failure patterns:
   ```python
   mcp__by_knowledge__knowledge_store_failure(
       campaign_id=..., description=..., root_cause=..., target=...,
   )
   ```

### Periodic maintenance

6. Every 20-30 campaigns, consolidate:
   ```python
   mcp__by_knowledge__knowledge_consolidate()
   ```
   Dedups (same target+modality+scaffold) and prunes (>90 days, <3 accesses).

❌ **DON'T:**
- Write to `~/.by/knowledge/campaigns.json` with `open(..., "w")` — bypasses atomic rename
- Record every design from a campaign — graph bloat slows every subsequent query
- Use varying target names (`TNF` vs `TNF-alpha`) — fragments the data
- Skip the `designs` array thinking it's optional decoration — downstream agents key off it

---

## When Scripts Fail

Script Failure Hierarchy:
1. **Fix and Retry (90%)** — `pip install mcp jsonschema`, ensure `KNOWLEDGE_DIR` exists and is writable, re-run.
2. **Modify Script (5%)** — `migrate_knowledge.py` is editable. Adjust validation rules for non-standard fields, then rerun.
3. **Use as Reference (4%)** — Read `knowledge_query_examples.py`, adapt query template for an unusual filter.
4. **Write from Scratch (1%)** — Only if the entity model has fundamentally diverged; first update [references/graph-schema.md](references/graph-schema.md).

Common failure: `Permission denied` on `~/.by/knowledge/` — set `KNOWLEDGE_DIR`
to a writable location, or `chmod -R u+w ~/.by/knowledge/`.

Common failure: JSON file corrupt mid-write — the server uses atomic rename
(write to `.tmp`, then rename), so corruption is rare. If you see a `.tmp` file
leftover, the previous write was interrupted; safe to delete after backing up.

---

## Decision Points

**When to record a design in the `designs` array:**
- ✅ Top 10-20 by composite score
- ✅ Any design with notable liability (e.g. potential glycosylation site near hotspot)
- ✅ Any design used downstream (verification, lab submission)
- ❌ Mid-tier designs without distinguishing features
- ❌ FAIL designs unless they exemplify a failure pattern

**When to record a failure:**
- ✅ Pattern repeats across 2+ designs in the same campaign
- ✅ Recurring across campaigns (e.g. "VHH+caplacizumab on glycosylated epitopes consistently misfolds")
- ❌ One-off bug in the toolchain (file in by-debug instead)
- ❌ User error (e.g. wrong PDB chain) — not a learning opportunity for the graph

**When to consolidate:**
- ✅ After every 20-30 new campaigns
- ✅ Before exporting / migrating
- ❌ During active campaigns (consolidation is non-destructive but generates noise)

See [references/query-patterns.md](references/query-patterns.md) for the full
decision tree per query type.

---

## Common Issues

| Issue | Cause | Solution | Details |
|-------|-------|----------|---------|
| Empty `results` from `knowledge_query_similar` | Graph is empty or target_description has no shared keywords | Lower threshold or broaden description; run a few campaigns first | See [query-patterns.md#empty-results](references/query-patterns.md) |
| Same target appears multiple times | Inconsistent naming (`TNF` vs `TNF-alpha`) | Normalize at write time; run `knowledge_consolidate` to dedup | [graph-schema.md#target](references/graph-schema.md) |
| `Permission denied` on storage | `~/.by/knowledge/` not writable | `chmod -R u+w ~/.by/knowledge/` or set `KNOWLEDGE_DIR` | — |
| Scaffold rankings empty for target class | Substring match too narrow | Use broader `target_class` (e.g. `cytokine` not `IL-23p19`) | [query-patterns.md#scaffold-rankings](references/query-patterns.md) |
| `knowledge_consolidate` removed entries I wanted | Pruned `>90 days + <3 accesses` | Restore from backup; raise access_count by querying before next consolidate | [graph-schema.md#access-count](references/graph-schema.md) |
| Failures not surfacing in recommendations | Keyword overlap below 0.2 threshold | Re-record failure with target name + modality in description | [graph-schema.md#failure](references/graph-schema.md) |
| `.tmp` files in storage directory | Previous write interrupted | Safe to delete after confirming `.json` file is intact | — |
| `KeyError: 'scaffold'` in scaffold rankings | Campaign stored without `parameters.scaffold` | Always include scaffold in `parameters` dict | [graph-schema.md#campaign](references/graph-schema.md) |
| Migration script rejects entries | Schema version mismatch | Run `migrate_knowledge.py --upgrade` to apply version transforms | [graph-schema.md#versioning](references/graph-schema.md) |
| Slow queries (>1s) | Graph has thousands of entries | Run `knowledge_consolidate`, then re-query | — |
| Two machines have divergent graphs | No sync layer | Export with `migrate_knowledge.py --export`, merge manually, re-import | — |
| Designs missing from query response | Top-level field, not in metadata.designs | `metadata.designs_count` shows count; query record by id for full list | [graph-schema.md#design](references/graph-schema.md) |

---

## Best Practices

1. 🚨 **CRITICAL**: Always normalize target names at write time. Use lowercase-hyphenated form (`tnf-alpha`, not `TNF-alpha` or `TNF alpha`).
2. ✅ **REQUIRED**: Record the top 10-20 designs per campaign — never all of them. Graph bloat is the #1 cause of slow queries.
3. ✅ **REQUIRED**: Include `composite_score`, `ipsae`, `iptm`, and `status` in every design entry. Downstream agents key off these fields.
4. ✅ Query before designing — `knowledge_get_recommendations` is the cheapest way to avoid repeating a failed campaign.
5. ✅ Use `notes` field for non-structured context (e.g. "iter-2 hotspot refinement"). It's indexed for keyword search.
6. ✅ Record failures as patterns, not incidents. "VHH+glycosylated epitope misfolds" is useful; "ran out of disk on day 3" is not.
7. ✅ Run `knowledge_consolidate` after every 20-30 campaigns to dedup and prune.
8. ✨ **Optional**: Set `KNOWLEDGE_DIR` to a Dropbox/iCloud path to share the graph across machines.
9. ❌ **DON'T**: Write to `campaigns.json` or `failures.json` directly. Bypasses atomic-rename safety.
10. ❌ **DON'T**: Re-query the graph mid-campaign on every screening result. Query at start, query at end, that's it.

---

## Suggested Next Steps

After storing campaign outcomes, invoke these skills:

- **by-campaign-manager** — Update the campaign state file with knowledge entries written. Closes the campaign lifecycle.
- **by-research** — On the next new campaign, `by-research` will consume `knowledge_query_similar` results as prior art context.
- **by-failure-diagnosis** — If `failures.json` grew during the campaign, run this skill to root-cause the patterns.
- **by-campaign-optimizer** — Reads scaffold rankings to recommend the next campaign's parameter sweep.

Why this chain works: every BY skill reads from and writes to the same JSON
store. Each campaign therefore improves the recommendations for the next, with
zero manual curation step.

---

## Related Skills

**Upstream** (run before this skill):
- `by-screening` — Produces the screening results that get summarized into outcomes.
- `by-campaign-manager` — Provides the campaign_id and parameters dict.

**Downstream** (run after this skill):
- `by-research` — Consumes prior campaigns as context for new target research.
- `by-failure-diagnosis` — Consumes failure entries for root-cause clustering.
- `by-campaign-optimizer` — Consumes scaffold rankings for active learning.

**Alternative / complementary**:
- `by-display` — Formats query results for human review.

---

## References

**Detailed documentation** (in `references/`):
- [references/graph-schema.md](references/graph-schema.md) — Full JSON Schema for every entity and relationship type, with field-level documentation and a property index.
- [references/query-patterns.md](references/query-patterns.md) — Common query templates, expected output shapes, and performance notes.

**Scripts** (in `scripts/`):
- [scripts/knowledge_query_examples.py](scripts/knowledge_query_examples.py) — 6-8 runnable query examples that exercise the patterns documented in `query-patterns.md`.
- [scripts/migrate_knowledge.py](scripts/migrate_knowledge.py) — Migration utility for NDJSON entity dumps; validates against schema and handles schema-version upgrades.

**MCP server source**: `templates/.claude/mcp_servers/knowledge/server.py` —
canonical implementation of the six MCP tools.

**License**: BY (Blatant-Why) project — commercial use permitted under project terms.
