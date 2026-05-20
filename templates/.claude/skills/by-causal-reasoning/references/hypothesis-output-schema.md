# `hypotheses.json` Output Schema

The full JSON Schema for the `hypotheses.json` artifact produced by
`by-causal-reasoning`. This file is the contract between this skill and its
downstream consumers (`by-hypothesis-debate`, `by-campaign-optimizer`,
`by-knowledge`).

The schema is enforced by `score_hypothesis_evidence.py`. Any output that does
not validate is rejected before being passed downstream.

---

## Schema (JSON Schema Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://by/schemas/hypotheses.json",
  "title": "Ranked Mechanistic Hypotheses",
  "description": "Output of by-causal-reasoning. Ordered list of 3-5 hypotheses, each grounded in knowledge-graph evidence.",
  "type": "object",
  "required": ["campaign_id", "target", "modality", "generated_at", "hypotheses"],
  "properties": {
    "campaign_id": {
      "type": "string",
      "description": "Stable campaign identifier matching the campaign directory name."
    },
    "target": {
      "type": "string",
      "description": "Canonical target name (lowercase-hyphenated form preferred)."
    },
    "modality": {
      "type": "string",
      "enum": ["antibody", "nanobody", "VHH", "scFv", "Fab", "de_novo", "binder"]
    },
    "generated_at": {
      "type": "string",
      "format": "date-time"
    },
    "diagnosis_source": {
      "type": "string",
      "description": "Path to the diagnosis.json that fed this generation."
    },
    "epitope_source": {
      "type": ["string", "null"],
      "description": "Path to the hotspots.json if structural context was available."
    },
    "lab_calibration_source": {
      "type": ["string", "null"],
      "description": "Path to experiment_results.json if lab data was used."
    },
    "knowledge_graph_snapshot": {
      "type": "object",
      "description": "Summary of the by-knowledge state at generation time.",
      "properties": {
        "campaigns_searched": { "type": "integer", "minimum": 0 },
        "failures_searched": { "type": "integer", "minimum": 0 },
        "stub_mode": { "type": "boolean" }
      },
      "required": ["campaigns_searched", "failures_searched", "stub_mode"]
    },
    "hypotheses": {
      "type": "array",
      "minItems": 1,
      "maxItems": 5,
      "items": { "$ref": "#/$defs/hypothesis" }
    }
  },
  "$defs": {
    "hypothesis": {
      "type": "object",
      "required": [
        "rank",
        "claim",
        "mechanism",
        "confidence",
        "supporting_evidence",
        "contradicting_evidence",
        "falsifiable_prediction",
        "recommended_next_action"
      ],
      "properties": {
        "rank": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "claim": {
          "type": "string",
          "minLength": 20,
          "description": "Single-sentence mechanistic statement. Must name a canonical mechanism key."
        },
        "mechanism": {
          "type": "string",
          "enum": [
            "steric_clash",
            "electrostatic_mismatch",
            "hydrophobic_aggregation",
            "cryptic_epitope_inaccessibility",
            "polyspecificity_or_off_target",
            "kinetic_mismatch_slow_on_rate",
            "allosteric_perturbation",
            "disulfide_or_ptm_issue"
          ]
        },
        "confidence": {
          "type": "string",
          "enum": ["HIGH", "MEDIUM", "SPECULATIVE"]
        },
        "supporting_evidence": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/evidence_record" }
        },
        "contradicting_evidence": {
          "type": "array",
          "items": { "$ref": "#/$defs/evidence_record" }
        },
        "falsifiable_prediction": {
          "type": "string",
          "minLength": 30,
          "description": "Runnable assay with named readout and threshold."
        },
        "recommended_next_action": {
          "type": "string",
          "enum": [
            "by-hypothesis-debate",
            "by-campaign-optimizer",
            "by-experiment-results",
            "by-knowledge-store-failure",
            "by-research"
          ]
        },
        "notes": {
          "type": "string",
          "description": "Optional free-text annotations (e.g. REPEATED: flag)."
        }
      }
    },
    "evidence_record": {
      "type": "object",
      "required": ["entity_id", "type", "claim_relation", "weight"],
      "properties": {
        "entity_id": {
          "type": "string",
          "pattern": "^(campaign_|failure_)[a-f0-9]{12}$",
          "description": "ID from by-knowledge. Must exist in the graph."
        },
        "type": {
          "type": "string",
          "enum": ["campaign", "failure", "scaffold_ranking", "lab_calibration"]
        },
        "claim_relation": {
          "type": "string",
          "enum": [
            "supports",
            "partially_supports",
            "contradicts",
            "contradicts_partially",
            "restates_input"
          ]
        },
        "weight": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "Tier-derived weight. Tier 1 = 1.0, Tier 2 = 0.6, Tier 3 = 0.3."
        },
        "tier": {
          "type": "integer",
          "enum": [1, 2, 3]
        },
        "excerpt": {
          "type": "string",
          "description": "Short quote or summary from the entity for human review."
        }
      }
    }
  }
}
```

---

## Entity ID rules

- Format: `campaign_<12-hex>` or `failure_<12-hex>` — matches the IDs
  generated by the `by-knowledge` MCP server.
- Each cited ID must be retrievable from the live graph via
  `mcp__by-knowledge__knowledge_query_similar` or by direct scan of the
  on-disk JSON files (the `score_hypothesis_evidence.py` validator does
  both). Missing → hypothesis rejected.
- IDs must not be invented by the LLM; the generator populates them from
  the retrieval step.

---

## Evidence record shape

Each `evidence_record` entry has 4 required fields:

| Field | Required | Notes |
|-------|----------|-------|
| `entity_id` | yes | Must exist in `by-knowledge` |
| `type` | yes | `campaign`, `failure`, `scaffold_ranking`, `lab_calibration` |
| `claim_relation` | yes | Direction of the evidence (see enum) |
| `weight` | yes | Numeric tier-derived weight (1.0/0.6/0.3) |
| `tier` | optional | Integer 1/2/3, set by the grader |
| `excerpt` | optional | Short human-readable quote |

`claim_relation` values:

- `supports` — entity directly demonstrates the mechanism
- `partially_supports` — entity is consistent with the mechanism but does not prove it
- `contradicts` — entity argues the mechanism is NOT operative
- `contradicts_partially` — entity is inconsistent in some but not all aspects
- `restates_input` — reserved for the anti-confirmation guard; triggers SPECULATIVE

---

## Falsifiable prediction rules

The `falsifiable_prediction` field must:

1. Name a specific assay token (from the assay vocabulary below).
2. Name the readout (kon, Kd, Tm, % monomer, signal/background, etc.).
3. Name the threshold or outcome that would confirm or refute the claim.

### Assay vocabulary

The validator regex-matches against this list (case-insensitive):

```
SPR, BLI, MST, DSF, HIC, AC-SINS, SEC, SEC-MALS, DLS,
HDX-MS, mass spec, LC-MS, cryo-EM, ELISA, FACS, cell binding,
neutralization assay, competition assay, PSR, anti-DNA panel,
Hep2 panel, alanine scan, mutagenesis, Western, dot blot,
glycoform analysis, reducing SDS-PAGE, non-reducing SDS-PAGE
```

A prediction with no assay-vocabulary match is rejected.

### Good vs bad examples

✅ Good: *"SPR at varying ionic strength (50 mM, 150 mM, 500 mM NaCl) will
show >3-fold change in kon for FAIL designs if electrostatic mismatch is
the cause."*

✅ Good: *"HIC retention time will exceed 12 minutes for hydrophobic-patch
FAIL designs vs <8 minutes for PASS designs."*

❌ Bad: *"More research is needed to confirm."*

❌ Bad: *"The lab should test it."*

❌ Bad: *"This could be tested experimentally."*

---

## Confidence enum

Only three values are allowed: `HIGH`, `MEDIUM`, `SPECULATIVE`. These match
the BY confidence taxonomy used by `by-research`. The values are assigned
mechanically by `generate_hypotheses.py` from the precedence table in
[evidence-grading.md](evidence-grading.md). The LLM-authored claim sentence
does NOT set the confidence value.

---

## Worked example 1 — HIGH confidence

```json
{
  "campaign_id": "campaign_20260315_001",
  "target": "tnf-alpha",
  "modality": "VHH",
  "generated_at": "2026-03-22T18:42:11Z",
  "diagnosis_source": "campaigns/tnf-alpha/campaign_20260315_001/diagnosis.json",
  "epitope_source": "campaigns/tnf-alpha/campaign_20260315_001/hotspots.json",
  "lab_calibration_source": null,
  "knowledge_graph_snapshot": {
    "campaigns_searched": 47,
    "failures_searched": 12,
    "stub_mode": false
  },
  "hypotheses": [
    {
      "rank": 1,
      "claim": "Designs failed due to a hydrophobic patch centered on Trp52 and Phe54 in the CDR-H3 loop driving self-aggregation, which presents as elevated hydrophobic_fraction in the FAIL group and AC-SINS positive readouts in screening.",
      "mechanism": "hydrophobic_aggregation",
      "confidence": "HIGH",
      "supporting_evidence": [
        {
          "entity_id": "failure_a1b2c3d4e5f6",
          "type": "failure",
          "claim_relation": "supports",
          "weight": 1.0,
          "tier": 1,
          "excerpt": "Three independent VHH campaigns against cytokine targets showed aggregation correlating with exposed aromatic residues in CDR-H3."
        },
        {
          "entity_id": "campaign_f6e5d4c3b2a1",
          "type": "campaign",
          "claim_relation": "partially_supports",
          "weight": 0.6,
          "tier": 2,
          "excerpt": "Prior TNF-alpha VHH campaign with hit rate 0.08 attributed to hydrophobic surface; recovered with Trp-to-Tyr swap."
        }
      ],
      "contradicting_evidence": [],
      "falsifiable_prediction": "HIC retention time on a TSK-Butyl column will exceed 12 minutes for FAIL designs vs <8 minutes for PASS designs; AC-SINS reagent panel will show positive shifts (>10 nm) for FAIL designs only.",
      "recommended_next_action": "by-campaign-optimizer",
      "notes": "Optimizer should apply a hydrophobicity mask on positions 50-56 of CDR-H3 and lower BoltzGen temperature by 0.1."
    }
  ]
}
```

This example is HIGH because:
- One Tier-1 supporting entity (multi-campaign failure pattern)
- One Tier-2 supporting entity (single replicated campaign)
- Zero contradicting evidence
- Claim names a canonical mechanism (`hydrophobic_aggregation`)
- Falsifiable prediction names assays (HIC, AC-SINS), readouts (retention
  time, wavelength shift), and thresholds (>12 min, >10 nm)

---

## Worked example 2 — SPECULATIVE

```json
{
  "campaign_id": "campaign_20260318_002",
  "target": "novel-orphan-gpcr",
  "modality": "nanobody",
  "generated_at": "2026-03-25T09:15:00Z",
  "diagnosis_source": "campaigns/novel-orphan-gpcr/campaign_20260318_002/diagnosis.json",
  "epitope_source": null,
  "lab_calibration_source": null,
  "knowledge_graph_snapshot": {
    "campaigns_searched": 3,
    "failures_searched": 1,
    "stub_mode": false
  },
  "hypotheses": [
    {
      "rank": 1,
      "claim": "Designs failed due to cryptic epitope inaccessibility — the apo conformation of the target buries the hotspot region used as the design template, so in-silico high-ipSAE designs cannot find the binding site at the bench.",
      "mechanism": "cryptic_epitope_inaccessibility",
      "confidence": "SPECULATIVE",
      "supporting_evidence": [
        {
          "entity_id": "failure_9988aabbccdd",
          "type": "failure",
          "claim_relation": "partially_supports",
          "weight": 0.3,
          "tier": 3,
          "excerpt": "Single prior GPCR campaign noted apo vs holo conformational differences but no replication available."
        }
      ],
      "contradicting_evidence": [],
      "falsifiable_prediction": "HDX-MS on the apo target will show solvent exposure of the hotspot region in <20% of molecules; if exposure is high, this hypothesis is refuted and steric_clash should be reconsidered.",
      "recommended_next_action": "by-hypothesis-debate",
      "notes": "Single Tier-3 source. Recommend debate before committing optimizer compute."
    }
  ]
}
```

This example is SPECULATIVE because:
- Only one supporting entity, and it is Tier 3 (single observation)
- No contradicting evidence, but supporting strength is too weak to upgrade
- Per the precedence table: Tier 3 supporting + None contradicting →
  SPECULATIVE
- Next action is `by-hypothesis-debate`, not `by-campaign-optimizer`

---

## Validation pipeline

`score_hypothesis_evidence.py` runs the following passes:

1. **JSON Schema validation** against the schema above (`jsonschema` package).
2. **Entity-existence check** for every `entity_id` (via `by-knowledge`).
3. **Mechanism-key validity check** against the catalog.
4. **Falsification token regex** against the assay vocabulary.
5. **Confidence recomputation** from the precedence table — must match the
   `confidence` field. Mismatch is corrected and noted in `hypotheses_scored.json`.
6. **Parsimony check**: `hypotheses` array length ≤ 5.

A passing artifact has every hypothesis annotated with
`evidence_check: OK` in the scored output. Any other value (e.g.
`ENTITY_NOT_FOUND`, `RELATION_MISMATCH`, `FALSIFICATION_MISSING_OR_VAGUE`,
`CLAIM_IS_CORRELATION_NOT_MECHANISM`) indicates the artifact is not safe to
pass downstream.
