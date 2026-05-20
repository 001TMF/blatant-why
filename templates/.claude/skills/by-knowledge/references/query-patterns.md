# Query Patterns Reference

Common query templates against the BY knowledge graph, with expected output
shapes and performance notes. Pair this file with
[graph-schema.md](graph-schema.md) for field-level details.

The query layer is keyword overlap, not vector search. This is intentional: it
keeps the system dependency-free and predictable. Plan queries around exact
target names + class-level descriptors.

---

## Pattern 1: Find Similar Past Campaigns

**When to use:** Starting a new campaign and want to see what worked / failed on
similar targets.

**Tool:** `mcp__by-knowledge__knowledge_query_similar`

**Query template:**
```python
mcp__by_knowledge__knowledge_query_similar(
    target_description="<target_name> <organism> <target_class> <modality_keywords>",
    modality="<VHH|antibody|nanobody|scFv|de_novo|binder>",   # optional filter
    top_k=5,
)
```

**Example:**
```python
mcp__by_knowledge__knowledge_query_similar(
    target_description="TNF-alpha homotrimer cytokine autoimmune",
    modality="VHH",
    top_k=5,
)
```

**Expected output shape:**
```json
{
  "results": [
    {
      "id": "campaign_a1b2c3d4e5f6",
      "similarity": 0.83,
      "document": "Campaign targeting TNF-alpha using VHH modality. Scaffold: caplacizumab. Hit rate: 0.23.",
      "metadata": {
        "target": "tnf-alpha",
        "modality": "VHH",
        "parameters": {...},
        "outcomes": {"hit_rate": 0.23, "best_ipsae": 0.78, "best_iptm": 0.85},
        "designs_count": 17
      }
    }
  ],
  "query": "TNF-alpha homotrimer cytokine autoimmune"
}
```

**Performance:** O(N) where N = number of campaigns. Sub-100ms for N < 1000.
For N > 5000, run `knowledge_consolidate` to dedup.

**Edge cases:**
- Empty results: graph is empty OR no shared keywords. Broaden the description.
- Low similarity scores (<0.3): query terms didn't overlap with stored notes/parameters. Add scaffold name or target class.

---

## Pattern 2: List Designs Above Threshold For Target X

**When to use:** Pulling the best designs from a target's history for
verification, lab submission, or report generation.

**Tool:** Compose `knowledge_query_similar` + client-side filter on `metadata.designs_count`.

**Query template:**
```python
# Step 1: Get campaigns for this target
result = mcp__by_knowledge__knowledge_query_similar(
    target_description="tnf-alpha",
    top_k=20,
)

# Step 2: For each campaign, the metadata.designs_count tells you how many
# top designs are stored. Fetch the full record via knowledge_get_recommendations
# (which returns full parameters/outcomes) OR pull from campaigns.json directly
# via migrate_knowledge.py --extract <campaign_id>.

# Step 3: Filter designs by threshold (e.g. ipsae > 0.7)
designs = [d for c in result["results"]
           for d in c.get("designs", [])
           if d.get("ipsae", 0) > 0.7]
```

**Expected output shape:** List of Design objects (see
[graph-schema.md#design](graph-schema.md)).

**Performance:** Sub-200ms total. Threshold filtering is client-side.

**Note:** `knowledge_query_similar` returns top-level metadata, not the embedded
`designs` array. To get the full designs list, either:
1. Query and then read the record by id from `campaigns.json`
2. Use `scripts/migrate_knowledge.py --extract <campaign_id>` for one-off pulls

---

## Pattern 3: Show Contradicted / Failed Findings For Target Y

**When to use:** Diagnosing a low pass rate; checking for known failure modes.

**Tool:** `mcp__by-knowledge__knowledge_get_recommendations` (returns warnings)

**Query template:**
```python
result = mcp__by_knowledge__knowledge_get_recommendations(
    target="tnf-alpha",
    modality="VHH",
)
warnings = result["warnings"]   # already sorted by relevance, top 5
```

**Expected output shape:**
```json
{
  "warnings": [
    {
      "id": "failure_xyz789",
      "relevance": 0.66,
      "campaign_id": "tnf_alpha_20260301_001",
      "description": "VHH+caplacizumab on glycosylated epitope misfolded",
      "root_cause": "BoltzGen does not model N-linked glycans; hotspot N78 adjacent to glycan site"
    }
  ]
}
```

**Performance:** O(N+F) where N = campaigns, F = failures. Sub-100ms.

**Threshold:** Warnings with relevance < 0.2 are filtered out by the server.
For lower-threshold scans, read `failures.json` directly or use
`scripts/knowledge_query_examples.py`.

---

## Pattern 4: Scaffold Rankings For Target Class

**When to use:** Choosing a scaffold for a new target — narrow to the target
class (e.g. cytokine, GPCR) and see which scaffolds rank highest.

**Tool:** `mcp__by-knowledge__knowledge_scaffold_rankings`

**Query template:**
```python
result = mcp__by_knowledge__knowledge_scaffold_rankings(
    target_class="cytokine",   # substring-matched against Campaign.target
)
```

**Expected output shape:**
```json
{
  "rankings": [
    {"scaffold": "caplacizumab", "campaign_count": 8, "avg_hit_rate": 0.31, "avg_ipsae": 0.74},
    {"scaffold": "ozoralizumab", "campaign_count": 3, "avg_hit_rate": 0.18, "avg_ipsae": 0.65}
  ],
  "target_class": "cytokine"
}
```

**Performance:** O(N). Sub-50ms.

**Gotchas:**
- `target_class` is a substring match against `Campaign.target`. Use broad terms ("cytokine") not specific targets ("IL-23p19").
- Campaigns without `parameters.scaffold` show up under scaffold `"unknown"`.
- Rankings are sorted by `(avg_hit_rate, avg_ipsae)` descending.

---

## Pattern 5: Pre-Campaign Recommendation Bundle

**When to use:** One-stop call at the start of a new campaign — pulls similar
campaigns, scaffold rankings, warnings, and suggested parameters in a single
request.

**Tool:** `mcp__by-knowledge__knowledge_get_recommendations`

**Query template:**
```python
result = mcp__by_knowledge__knowledge_get_recommendations(
    target="tnf-alpha",
    modality="VHH",
)
```

**Expected output shape:**
```json
{
  "target": "tnf-alpha",
  "modality": "VHH",
  "similar_campaigns": [/* top 5 similar */],
  "recommended_scaffolds": [/* sorted by avg_hit_rate */],
  "warnings": [/* top 5 relevant failures */],
  "suggested_parameters": {/* from best similar campaign */}
}
```

**Performance:** O(N+F), sub-200ms.

**This is the highest-leverage query** — use it first on every new campaign.

---

## Pattern 6: Browse Recent Entries

**When to use:** Health check on the graph; spot-check what's been recorded.

**Tool:** Direct read of `campaigns.json` via `migrate_knowledge.py --recent` or
shell:
```bash
python3 -c "
import json, pathlib
p = pathlib.Path.home() / '.by/knowledge/campaigns.json'
with open(p) as f: data = json.load(f)
data.sort(key=lambda x: x.get('stored_at', 0), reverse=True)
for c in data[:10]:
    print(c['id'], c['target'], c['modality'])
"
```

**Performance:** O(N) full scan. Use sparingly.

---

## Pattern 7: Cross-Target Scaffold Comparison

**When to use:** Investigating whether a scaffold is broadly useful or
target-specific.

**Tool:** Compose multiple `knowledge_scaffold_rankings` calls.

**Query template:**
```python
classes = ["cytokine", "receptor", "enzyme", "viral"]
results = {
    cls: mcp__by_knowledge__knowledge_scaffold_rankings(target_class=cls)
    for cls in classes
}
# Aggregate scaffold appearances across classes
scaffold_breadth = {}
for cls, r in results.items():
    for entry in r["rankings"]:
        s = entry["scaffold"]
        scaffold_breadth.setdefault(s, []).append((cls, entry["avg_hit_rate"]))
```

**Expected output:** Dict of scaffold -> list of (target_class, hit_rate).

**Performance:** O(C*N) where C = number of classes. Sub-500ms for typical
graph sizes.

---

## Pattern 8: Failure Pattern Clustering

**When to use:** Identifying recurring failure modes across multiple campaigns.

**Tool:** Direct read of `failures.json` + client-side keyword clustering.

**Query template:** See `scripts/knowledge_query_examples.py` example 8.

**Performance:** O(F^2) for naive clustering. Use `migrate_knowledge.py
--export` then run an offline clustering pass for F > 100.

---

## Performance Reference Table

| Pattern | Tool | Complexity | Typical Latency |
|---------|------|------------|----------------|
| 1. Similar campaigns | `knowledge_query_similar` | O(N) | <100ms |
| 2. Designs above threshold | composed | O(N + K) | <200ms |
| 3. Failures for target | `knowledge_get_recommendations` | O(N+F) | <100ms |
| 4. Scaffold rankings | `knowledge_scaffold_rankings` | O(N) | <50ms |
| 5. Recommendation bundle | `knowledge_get_recommendations` | O(N+F) | <200ms |
| 6. Recent entries | direct read | O(N) | <50ms |
| 7. Cross-target scaffolds | composed | O(C*N) | <500ms |
| 8. Failure clustering | offline | O(F^2) | seconds |

N = campaigns, F = failures, K = designs across queried campaigns, C = target
classes.

When N > 5000, run `mcp__by-knowledge__knowledge_consolidate` to dedup +
prune. After consolidation, query latencies return to typical ranges.

---

## Empty-Result Handling

If `knowledge_query_similar` returns `{"results": [], "message": "No prior
campaigns recorded..."}`:
1. Graph is genuinely empty — run some campaigns and store outcomes.
2. Or: storage directory is wrong. Check `KNOWLEDGE_DIR`,
   `$BY_PROJECT_ROOT/.by/knowledge/`, and `~/.by/knowledge/` in priority order.

If `knowledge_query_similar` returns results but all similarity scores are
0.0:
1. Query keywords don't overlap with stored notes/parameters.
2. Broaden the `target_description` to include scaffold name and target class.
3. Try the more lenient `knowledge_get_recommendations` which scans across
   `parameters` and `outcomes` values.
