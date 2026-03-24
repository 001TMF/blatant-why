# Skill: BY Knowledge Graph

Persistent structured memory across campaigns. Use this to record and recall
targets, scaffolds, designs, screening results, and failure patterns so that
future campaigns benefit from past experience.

---

## 1. Ontology

### 1.1 Entity Types

| Type | Description | Key Properties |
|------|-------------|---------------|
| **Target** | Protein target for binder design | name, pdb_id, uniprot_id, organism, target_type (cytokine, receptor, enzyme, etc.), difficulty |
| **Epitope** | Specific binding site on a target | residues (array), chain_id, epitope_type (pocket, flat, groove), area_A2 |
| **Scaffold** | Template or framework for design | name, modality (VHH, scFv, de_novo), source (caplacizumab, etc.), framework |
| **Design** | A generated binder design | design_name, campaign_id, tool, protocol, parameters (JSON), sequence |
| **ScreenResult** | Scoring output for a design | iptm, ipsae_min, plddt, rmsd, liabilities (array), pass (bool), composite_score |
| **FailurePattern** | Recurring design failure mode | pattern_name, modality, description, severity, mitigation |

### 1.2 Relationship Types

| Relationship | From -> To | Properties |
|-------------|-----------|-----------|
| **targets_epitope** | Target -> Epitope | campaign_id, confidence |
| **uses_scaffold** | Target -> Scaffold | campaign_id, hit_rate, num_designs, pass_rate |
| **produces_design** | Scaffold -> Design | campaign_id, round_id |
| **has_result** | Design -> ScreenResult | campaign_id, round_id |
| **exhibits_failure** | Design or Scaffold -> FailurePattern | campaign_id, count, severity |

---

## 2. When to Write

Record entities and relationships at these campaign milestones:

### 2.1 Campaign Start (Research Phase)
- Add **Target** entity with UniProt/PDB metadata and difficulty classification.
- Add **Epitope** entities for each identified binding site.
- Add **targets_epitope** relationships.
- Query existing knowledge for prior campaigns on same or similar targets.

### 2.2 Design Phase Start
- Add **Scaffold** entities for each template being used (if not already present).
- Add **uses_scaffold** relationships from target to each scaffold.

### 2.3 Screening Complete
- Add **Design** entities for top candidates (top 10-20, not all thousands).
- Add **ScreenResult** entities for those designs.
- Add **has_result** and **produces_design** relationships.
- Update **uses_scaffold** edge properties with hit_rate and pass_rate.

### 2.4 Campaign Review
- Add **FailurePattern** entities for any recurring issues discovered.
- Add **exhibits_failure** relationships from affected designs/scaffolds.
- Update **Target** entity with difficulty re-assessment if needed.

---

## 3. When to Query

### 3.1 New Campaign Planning
Query **scaffolds_for_target** to find which scaffolds worked well for similar
targets. Use this to prioritize scaffold selection and set expectations.

```
knowledge_query(
    query_type="scaffolds_for_target",
    filters_json='{"target_name": "TNF"}'
)
```

### 3.2 Failure Diagnosis
Query **failure_patterns** when pass rates are low or unexpected issues arise.

```
knowledge_query(
    query_type="failure_patterns",
    filters_json='{"scaffold_id": "caplacizumab", "modality": "VHH"}'
)
```

### 3.3 Parameter Optimization
Query **best_parameters** to find historically successful design parameters.

```
knowledge_query(
    query_type="best_parameters",
    filters_json='{"target_type": "cytokine", "tool": "boltzgen"}'
)
```

### 3.4 Browsing History
Use **knowledge_get_entities** to list recent targets, designs, or patterns.

```
knowledge_get_entities(entity_type="Target", limit=10)
```

---

## 4. Best Practices

1. **Be selective**: Record top candidates, not every design. 10-20 designs per
   campaign keeps the graph manageable.
2. **Use consistent IDs**: entity_id should be human-readable and stable
   (e.g. "TNF-alpha" not "target_001"). Use lowercase-hyphenated format.
3. **Record failures**: FailurePattern entities are the most valuable long-term
   data. Always record recurring issues.
4. **Merge, don't duplicate**: knowledge_add_entity auto-merges if entity_id
   matches. Use the same ID to update existing entities.
5. **Cross-reference campaigns**: Always include campaign_id in relationship
   properties for traceability.
6. **Query before designing**: At campaign start, always query the knowledge
   graph for prior art on similar targets.

---

## 5. Storage

Data is stored as NDJSON (newline-delimited JSON) in `~/.by/knowledge/`:

```
~/.by/knowledge/
  nodes.jsonl    # All entities
  edges.jsonl    # All relationships
```

Override the storage directory with the `PROTEUS_KNOWLEDGE_DIR` environment
variable. Files are append-only with file locking for concurrent access safety.
