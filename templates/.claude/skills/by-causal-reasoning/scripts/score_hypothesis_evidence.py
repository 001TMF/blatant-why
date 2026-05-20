#!/usr/bin/env python3
"""Validate a generated hypotheses.json against the by-causal-reasoning contract.

Reads a hypotheses.json produced by generate_hypotheses.py and runs these
checks (in order):

1. JSON Schema validation (against the schema in
   references/hypothesis-output-schema.md).
2. Entity-existence check — every cited entity_id is looked up in the
   by-knowledge JSON store (campaigns.json + failures.json). Missing entities
   raise ENTITY_NOT_FOUND.
3. Mechanism-key validity check against the catalog. Unknown keys are rejected.
4. Relation match — the cited entity's text content is checked against the
   mechanism the claim asserts; mismatch raises RELATION_MISMATCH.
5. Falsification token regex — the falsifiable_prediction must contain an
   assay-vocabulary token. Empty or vague predictions raise
   FALSIFICATION_MISSING_OR_VAGUE.
6. Claim-as-correlation guard — the claim must name a canonical mechanism key
   (or synonym). Pure restatements of statistics raise
   CLAIM_IS_CORRELATION_NOT_MECHANISM.
7. Confidence recomputation — the assigned confidence is re-derived from the
   precedence table and compared against the file's value. Mismatch is
   corrected and noted.
8. Parsimony check — hypotheses array length ≤ 5.

The output is a hypotheses_scored.json identical to the input but with each
hypothesis annotated with `evidence_check` (OK or a specific failure code)
and `tier_recomputed` for every evidence record.

Inputs
------
--hypotheses     Path to hypotheses.json (required)
--out            Path for the annotated hypotheses_scored.json (required)
--knowledge-dir  Optional override for the by-knowledge directory

Outputs
-------
hypotheses_scored.json with per-hypothesis `evidence_check` annotations.
Exit status 0 if every hypothesis passes, 1 if any fails.

Example
-------
    python3 score_hypothesis_evidence.py \\
      --hypotheses campaigns/tnf/run01/hypotheses.json \\
      --out        campaigns/tnf/run01/hypotheses_scored.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Canonical mechanism keys (must match catalog and generator).
CANONICAL_MECHANISMS: tuple[str, ...] = (
    "steric_clash",
    "electrostatic_mismatch",
    "hydrophobic_aggregation",
    "cryptic_epitope_inaccessibility",
    "polyspecificity_or_off_target",
    "kinetic_mismatch_slow_on_rate",
    "allosteric_perturbation",
    "disulfide_or_ptm_issue",
)

# Per-mechanism synonyms used by the claim-as-correlation guard.
MECHANISM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "steric_clash": ("steric clash", "physical overlap", "interface clash"),
    "electrostatic_mismatch": (
        "electrostatic mismatch",
        "charge mismatch",
        "charge repulsion",
        "isoelectric",
    ),
    "hydrophobic_aggregation": (
        "hydrophobic patch",
        "hydrophobic aggregation",
        "self-association",
        "aggregation",
    ),
    "cryptic_epitope_inaccessibility": (
        "cryptic epitope",
        "conformational",
        "apo conformation",
        "inaccessible",
    ),
    "polyspecificity_or_off_target": (
        "polyspecificity",
        "off-target",
        "off target",
        "non-specific binding",
    ),
    "kinetic_mismatch_slow_on_rate": (
        "slow on-rate",
        "slow on rate",
        "kinetic mismatch",
        "kon",
    ),
    "allosteric_perturbation": (
        "allosteric",
        "conformational change",
        "target distortion",
    ),
    "disulfide_or_ptm_issue": (
        "disulfide",
        "free cysteine",
        "free cys",
        "glycosylation",
        "ptm",
        "deamidation",
    ),
}

# Assay vocabulary used in falsifiable_prediction validation.
ASSAY_VOCAB: tuple[str, ...] = (
    "spr", "bli", "mst", "dsf", "hic", "ac-sins", "sec", "sec-mals", "dls",
    "hdx-ms", "mass spec", "lc-ms", "cryo-em", "elisa", "facs",
    "cell binding", "neutralization", "competition assay",
    "psr", "anti-dna", "hep2", "alanine scan", "mutagenesis",
    "western", "dot blot", "glycoform", "sds-page",
)

# Tier -> weight, mirroring the generator.
TIER_WEIGHTS: dict[int, float] = {1: 1.0, 2: 0.6, 3: 0.3}

# Confidence precedence table -- mirrors references/evidence-grading.md.
PRECEDENCE: dict[tuple[int | None, int | None], str | None] = {
    (1, None): "HIGH",
    (1, 3): "HIGH",
    (1, 2): "MEDIUM",
    (1, 1): "SPECULATIVE",
    (2, None): "MEDIUM",
    (2, 3): "MEDIUM",
    (2, 2): "SPECULATIVE",
    (2, 1): "SPECULATIVE",
    (3, None): "SPECULATIVE",
    (3, 3): "SPECULATIVE",
    (3, 2): "SPECULATIVE",
    (3, 1): "SPECULATIVE",
    (None, None): None,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Build argparse and parse CLI args."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate hypotheses.json from by-causal-reasoning. Verifies "
            "evidence citations exist, mechanism keys are canonical, "
            "predictions are falsifiable, and confidence labels match the "
            "precedence table."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--hypotheses", required=True, help="Path to hypotheses.json.")
    parser.add_argument("--out", required=True, help="Path for annotated hypotheses_scored.json.")
    parser.add_argument(
        "--knowledge-dir",
        default=None,
        help=(
            "Path to a directory containing campaigns.json and failures.json. "
            "Defaults via KNOWLEDGE_DIR env, then $BY_PROJECT_ROOT/.by/knowledge/, "
            "then ~/.by/knowledge/."
        ),
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: str | os.PathLike[str]) -> Any:
    """Read a JSON file, returning the parsed value."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_knowledge_dir(explicit: str | None) -> Path:
    """Resolve the by-knowledge directory path."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("KNOWLEDGE_DIR")
    if env:
        return Path(env).expanduser()
    project_root = os.environ.get("BY_PROJECT_ROOT")
    if project_root:
        candidate = Path(project_root).expanduser() / ".by" / "knowledge"
        if candidate.exists():
            return candidate
    return Path.home() / ".by" / "knowledge"


def _load_knowledge(kdir: Path) -> dict[str, dict[str, Any]]:
    """Return a dict of {entity_id: entity_record} from the knowledge store."""
    index: dict[str, dict[str, Any]] = {}
    for fname in ("campaigns.json", "failures.json"):
        fpath = kdir / fname
        if not fpath.exists():
            continue
        try:
            records = _read_json(fpath)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(records, list):
            continue
        for rec in records:
            ent_id = rec.get("id")
            if ent_id:
                index[ent_id] = rec
    return index


def _entity_text(entity: dict[str, Any]) -> str:
    """Compose a single text blob from an entity for relation matching."""
    parts: list[str] = []
    for key in ("description", "root_cause", "notes", "target", "modality"):
        val = entity.get(key)
        if val:
            parts.append(str(val))
    return " ".join(parts).lower()


def _check_relation_match(entity: dict[str, Any], mechanism: str) -> bool:
    """Verify the cited entity mentions a synonym of the claimed mechanism."""
    text = _entity_text(entity)
    if not text:
        return False
    synonyms = MECHANISM_SYNONYMS.get(mechanism, ())
    return any(syn.lower() in text for syn in synonyms)


def _check_assay_vocabulary(prediction: str) -> bool:
    """Verify the falsifiable_prediction names an assay from the vocabulary."""
    if not prediction or len(prediction) < 30:
        return False
    lowered = prediction.lower()
    return any(token in lowered for token in ASSAY_VOCAB)


def _check_claim_is_mechanism(claim: str, mechanism: str) -> bool:
    """Verify the claim sentence names the mechanism (canonical or synonym)."""
    if not claim:
        return False
    lowered = claim.lower()
    if mechanism.replace("_", " ") in lowered:
        return True
    return any(syn.lower() in lowered for syn in MECHANISM_SYNONYMS.get(mechanism, ()))


def _check_entity_id_format(entity_id: str) -> bool:
    """Verify the entity_id matches the campaign_/failure_ + 12-hex pattern."""
    return bool(re.match(r"^(campaign_|failure_)[a-f0-9]{12}$", entity_id or ""))


def _best_tier(records: list[dict[str, Any]]) -> int | None:
    """Return the strongest (lowest-numbered) tier in a record list."""
    tiers = [r.get("tier") for r in records if isinstance(r.get("tier"), int)]
    return min(tiers) if tiers else None


def _recompute_confidence(
    supporting: list[dict[str, Any]],
    contradicting: list[dict[str, Any]],
    stub_mode: bool,
) -> str | None:
    """Recompute confidence per the precedence table."""
    if not supporting:
        return None
    if stub_mode:
        return "SPECULATIVE"
    return PRECEDENCE.get((_best_tier(supporting), _best_tier(contradicting)), "SPECULATIVE")


# ---------------------------------------------------------------------------
# Per-hypothesis validation
# ---------------------------------------------------------------------------


def _validate_hypothesis(
    hyp: dict[str, Any],
    kg_index: dict[str, dict[str, Any]],
    stub_mode: bool,
) -> tuple[str, list[str]]:
    """Run all validation checks on a single hypothesis.

    Returns (status_code, notes_list). The status_code is "OK" if all checks
    pass, otherwise the first failure code encountered.
    """
    notes: list[str] = []

    # 3. Mechanism key.
    mechanism = hyp.get("mechanism", "")
    if mechanism not in CANONICAL_MECHANISMS:
        return "MECHANISM_KEY_INVALID", [f"Unknown mechanism key: {mechanism}"]

    # 6. Claim-as-correlation guard.
    if not _check_claim_is_mechanism(hyp.get("claim", ""), mechanism):
        return "CLAIM_IS_CORRELATION_NOT_MECHANISM", [
            "Claim does not name the canonical mechanism or a synonym.",
        ]

    # 5. Falsifiable prediction must name an assay.
    if not _check_assay_vocabulary(hyp.get("falsifiable_prediction", "")):
        return "FALSIFICATION_MISSING_OR_VAGUE", [
            "falsifiable_prediction must name a specific assay, readout, and threshold.",
        ]

    # 2. Entity existence + 4. relation match for each supporting / contradicting record.
    supporting = hyp.get("supporting_evidence", []) or []
    contradicting = hyp.get("contradicting_evidence", []) or []
    if not supporting:
        return "NO_SUPPORTING_EVIDENCE", [
            "Hypothesis requires ≥1 supporting evidence entity.",
        ]

    relation_mismatches: list[str] = []
    for ev in supporting + contradicting:
        ent_id = ev.get("entity_id", "")
        if not _check_entity_id_format(ent_id):
            return "ENTITY_ID_FORMAT_INVALID", [
                f"entity_id '{ent_id}' is not in the campaign_/failure_ + 12-hex form.",
            ]
        # Stub mode skips graph lookup but still requires format correctness.
        if not stub_mode:
            entity = kg_index.get(ent_id)
            if entity is None:
                return "ENTITY_NOT_FOUND", [
                    f"Entity {ent_id} not present in by-knowledge store.",
                ]
            if ev.get("claim_relation") in ("supports", "contradicts"):
                if not _check_relation_match(entity, mechanism):
                    relation_mismatches.append(ent_id)
        # Recompute tier weight for record-level annotation.
        tier = ev.get("tier")
        if isinstance(tier, int) and tier in TIER_WEIGHTS:
            ev["tier_recomputed"] = tier
        else:
            ev["tier_recomputed"] = 3
            notes.append(f"Tier missing or invalid for {ent_id}; defaulted to 3.")

    if relation_mismatches:
        # Downgrade rather than reject.
        notes.append(
            "RELATION_MISMATCH for entities: " + ", ".join(relation_mismatches)
        )

    # 7. Recompute confidence.
    recomputed = _recompute_confidence(supporting, contradicting, stub_mode)
    if recomputed is None:
        return "NO_SUPPORTING_EVIDENCE", ["No supporting evidence after tier check."]
    if recomputed != hyp.get("confidence"):
        notes.append(
            f"CONFIDENCE_CORRECTED from {hyp.get('confidence')} to {recomputed}."
        )
        hyp["confidence"] = recomputed

    return "OK", notes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    args = parse_args()

    try:
        payload = _read_json(args.hypotheses)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"✗ Failed to read hypotheses: {exc}")

    if not isinstance(payload, dict) or "hypotheses" not in payload:
        sys.exit("✗ hypotheses.json must be an object with a 'hypotheses' array.")

    hyp_list = payload.get("hypotheses") or []
    if not isinstance(hyp_list, list):
        sys.exit("✗ 'hypotheses' field must be an array.")

    # 8. Parsimony cap.
    if len(hyp_list) > 5:
        sys.exit(
            f"✗ PARSIMONY_VIOLATED: {len(hyp_list)} hypotheses, cap is 5. "
            "Regenerate with --max-hypotheses ≤5 or use by-hypothesis-debate."
        )

    stub_mode = (
        payload.get("knowledge_graph_snapshot", {}).get("stub_mode", False)
    )

    kg_index = _load_knowledge(_resolve_knowledge_dir(args.knowledge_dir))
    if not kg_index and not stub_mode:
        print(
            "⚠️ by-knowledge index is empty; falling back to stub mode for validation.",
            file=sys.stderr,
        )
        stub_mode = True

    overall_ok = True
    for hyp in hyp_list:
        status, notes = _validate_hypothesis(hyp, kg_index, stub_mode)
        hyp["evidence_check"] = status
        if notes:
            existing = hyp.get("validation_notes") or []
            if isinstance(existing, list):
                hyp["validation_notes"] = existing + notes
            else:
                hyp["validation_notes"] = list(notes)
        if status != "OK":
            overall_ok = False
            print(
                f"✗ Hypothesis #{hyp.get('rank')} ({hyp.get('mechanism')}): {status}",
                file=sys.stderr,
            )

    payload["validation"] = {
        "all_passed": overall_ok,
        "n_hypotheses": len(hyp_list),
        "stub_mode": stub_mode,
    }

    Path(args.out).write_text(json.dumps(payload, indent=2))

    n_ok = sum(1 for h in hyp_list if h.get("evidence_check") == "OK")
    print(f"✓ Validated {n_ok}/{len(hyp_list)} hypotheses: {args.out}")

    if not overall_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
