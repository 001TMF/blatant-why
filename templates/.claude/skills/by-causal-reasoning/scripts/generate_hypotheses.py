#!/usr/bin/env python3
"""Generate ranked mechanistic hypotheses for a design-campaign failure pattern.

This script does the deterministic work of by-causal-reasoning:
- reads the statistical diagnosis (from by-failure-diagnosis)
- reads structural context (from by-epitope-analysis, optional)
- reads lab calibration (from by-experiment-results, optional)
- maps discriminating features to canonical mechanisms via the
  failure-mechanisms-catalog
- queries the by-knowledge graph for supporting and contradicting entities
- assigns confidence tiers mechanically per the precedence table
- emits a JSON skeleton for hypotheses.json plus a human-readable
  evidence_trail.md

The agent fills only the `claim` and `falsifiable_prediction` fields at
runtime, using the embedded prompt template at the bottom of the JSON. All
evidence citations and confidence tiers are set by this script and MUST NOT
be modified by the agent.

Inputs
------
--diagnosis        Path to diagnosis.json from by-failure-diagnosis (required)
--epitope          Path to hotspots.json from by-epitope-analysis (recommended)
--experiment       Path to experiment_results.json from by-experiment-results
--target           Target name string (required, used for KG keyword query)
--modality         Modality (required: antibody|nanobody|VHH|scFv|de_novo|binder)
--max-hypotheses   Hard cap, default 4, never above 5
--knowledge-dir    Optional override for by-knowledge JSON store location
--out              Output path for hypotheses.json (required)
--trail            Output path for evidence_trail.md (required)
--prior-hypotheses Optional path to a prior round's hypotheses.json
--catalog          Path to failure-mechanisms-catalog.md (defaults to ../references/)
--allow-overflow   Permit >5 hypotheses (triggers by-hypothesis-debate handoff)

Outputs
-------
- hypotheses.json   (ranked array with claim/prediction templates to fill)
- evidence_trail.md (narrative of what was queried and what came back)

Example
-------
    python3 generate_hypotheses.py \\
      --diagnosis campaigns/tnf/run01/diagnosis.json \\
      --epitope   campaigns/tnf/run01/hotspots.json \\
      --target    "TNF-alpha" \\
      --modality  "VHH" \\
      --out       campaigns/tnf/run01/hypotheses.json \\
      --trail     campaigns/tnf/run01/evidence_trail.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

# Canonical mechanism keys. Must match references/failure-mechanisms-catalog.md.
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

# Feature -> mechanism vote table (mirrors the catalog's mapping section).
# Each entry maps a discriminating feature name to a list of
# (mechanism_key, vote_weight) tuples.
FEATURE_TO_MECHANISMS: dict[str, list[tuple[str, float]]] = {
    "rmsd": [("steric_clash", 1.0), ("cryptic_epitope_inaccessibility", 0.5)],
    "plddt": [("steric_clash", 1.0)],
    "iptm": [
        ("cryptic_epitope_inaccessibility", 1.0),
        ("allosteric_perturbation", 0.5),
    ],
    "net_charge": [
        ("electrostatic_mismatch", 1.0),
        ("polyspecificity_or_off_target", 0.5),
    ],
    "hydrophobic_fraction": [
        ("hydrophobic_aggregation", 1.0),
        ("polyspecificity_or_off_target", 0.5),
    ],
    "liabilities": [
        ("disulfide_or_ptm_issue", 1.0),
        ("hydrophobic_aggregation", 0.5),
    ],
    "cdr3_length": [
        ("steric_clash", 0.5),
        ("kinetic_mismatch_slow_on_rate", 0.5),
    ],
}

# Tier weights for evidence records (Tier 1 = 1.0, Tier 2 = 0.6, Tier 3 = 0.3).
TIER_WEIGHTS: dict[int, float] = {1: 1.0, 2: 0.6, 3: 0.3}

# Significance threshold for considering a feature as a "discriminating" signal.
SIGNIFICANCE_P: float = 0.05

# Stub knowledge graph used when --knowledge-dir is unreadable or empty.
# Stub mode always yields SPECULATIVE confidence, regardless of nominal tier.
STUB_KNOWLEDGE_CAMPAIGNS: list[dict[str, Any]] = []
STUB_KNOWLEDGE_FAILURES: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Build argparse and parse CLI args."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate ranked mechanistic hypotheses from a failure-diagnosis "
            "output, querying by-knowledge for evidence."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--diagnosis", required=True, help="Path to diagnosis.json.")
    parser.add_argument("--epitope", default=None, help="Path to hotspots.json (optional).")
    parser.add_argument(
        "--experiment",
        default=None,
        help="Path to experiment_results.json (optional lab calibration).",
    )
    parser.add_argument("--target", required=True, help="Target name.")
    parser.add_argument(
        "--modality",
        required=True,
        choices=["antibody", "nanobody", "VHH", "scFv", "Fab", "de_novo", "binder"],
    )
    parser.add_argument(
        "--max-hypotheses",
        type=int,
        default=4,
        help="Hard cap on the number of hypotheses emitted (max 5).",
    )
    parser.add_argument(
        "--knowledge-dir",
        default=None,
        help=(
            "Path to a directory containing campaigns.json and failures.json. "
            "If absent, the script tries KNOWLEDGE_DIR env var, then $BY_PROJECT_ROOT/.by/knowledge/, "
            "then ~/.by/knowledge/."
        ),
    )
    parser.add_argument("--out", required=True, help="Output hypotheses.json path.")
    parser.add_argument("--trail", required=True, help="Output evidence_trail.md path.")
    parser.add_argument(
        "--prior-hypotheses",
        default=None,
        help="Optional prior round hypotheses.json for repeated-mechanism detection.",
    )
    parser.add_argument(
        "--allow-overflow",
        action="store_true",
        help="Permit >5 hypotheses (triggers by-hypothesis-debate handoff).",
    )
    return parser.parse_args()


def _read_json(path: str | os.PathLike[str]) -> Any:
    """Read a JSON file, returning the parsed value."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_knowledge_dir(explicit: str | None) -> Path:
    """Resolve the by-knowledge JSON store directory."""
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


def _load_knowledge(kdir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Load campaigns and failures from the knowledge directory.

    Returns (campaigns, failures, stub_mode). If the directory does not
    contain readable JSON, returns the stub fallback with stub_mode=True.
    """
    campaigns_path = kdir / "campaigns.json"
    failures_path = kdir / "failures.json"
    try:
        campaigns = _read_json(campaigns_path) if campaigns_path.exists() else []
        failures = _read_json(failures_path) if failures_path.exists() else []
        if not campaigns and not failures:
            return STUB_KNOWLEDGE_CAMPAIGNS, STUB_KNOWLEDGE_FAILURES, True
        return campaigns, failures, False
    except (OSError, json.JSONDecodeError):
        return STUB_KNOWLEDGE_CAMPAIGNS, STUB_KNOWLEDGE_FAILURES, True


# ---------------------------------------------------------------------------
# Diagnosis -> mechanism voting
# ---------------------------------------------------------------------------


def collect_candidate_mechanisms(
    diagnosis: dict[str, Any],
) -> list[tuple[str, float]]:
    """Vote candidate mechanisms based on significant discriminating features.

    Returns mechanisms ordered by descending total vote weight. Only
    features with adjusted p-value < SIGNIFICANCE_P contribute.
    """
    votes: dict[str, float] = {m: 0.0 for m in CANONICAL_MECHANISMS}
    features = diagnosis.get("discriminating_features", [])
    if not isinstance(features, list):
        return []
    for feat in features:
        name = (feat.get("feature_name") or feat.get("feature") or "").lower()
        # Prefer BH-corrected q-value if present; fall back to raw p-value.
        p_value = feat.get("adjusted_p_value", feat.get("q_value", feat.get("p_value")))
        if p_value is None or float(p_value) >= SIGNIFICANCE_P:
            continue
        for mechanism, weight in FEATURE_TO_MECHANISMS.get(name, []):
            votes[mechanism] += weight
    # Discard mechanisms with no vote at all.
    ranked = [(m, v) for m, v in votes.items() if v >= 1.0]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def merge_compatible_mechanisms(candidates: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Collapse pairs that are biologically subsumed by the other.

    `polyspecificity_or_off_target` subsumes `hydrophobic_aggregation` when
    both are voted, since the latter is one of several drivers of the former.
    """
    by_mech = dict(candidates)
    if (
        "polyspecificity_or_off_target" in by_mech
        and "hydrophobic_aggregation" in by_mech
    ):
        # Roll hydrophobic_aggregation vote into polyspecificity.
        by_mech["polyspecificity_or_off_target"] += by_mech.pop("hydrophobic_aggregation")
    return sorted(by_mech.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Knowledge graph queries (local JSON scan; mirrors the MCP server logic)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Lowercase + word tokenize for keyword overlap."""
    return {tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(tok) > 2}


def _entity_text_for_failure(failure: dict[str, Any]) -> str:
    """Compose the searchable text blob for a failure entity."""
    parts = [
        failure.get("description", ""),
        failure.get("root_cause", ""),
        failure.get("target", ""),
    ]
    return " ".join(p for p in parts if p)


def _entity_text_for_campaign(campaign: dict[str, Any]) -> str:
    """Compose the searchable text blob for a campaign entity."""
    parts = [
        campaign.get("target", ""),
        campaign.get("modality", ""),
        campaign.get("notes", ""),
    ]
    params = campaign.get("parameters") or {}
    if isinstance(params, dict):
        parts.append(" ".join(str(v) for v in params.values()))
    return " ".join(p for p in parts if p)


def _classify_tier_failure(failure: dict[str, Any], stub_mode: bool) -> int:
    """Heuristic tier classification for a failure entity.

    - Tier 1 if the failure references a confirmed lab readout
      (notes contains "lab confirmed", "lab calibration", or similar).
    - Tier 2 if it has a documented root_cause >40 chars and is not lab-confirmed.
    - Tier 3 otherwise.
    - Stub mode forces Tier 3.
    """
    if stub_mode:
        return 3
    notes = (failure.get("description", "") + " " + failure.get("root_cause", "")).lower()
    if any(token in notes for token in ("lab confirmed", "wet-lab", "lab calibration", "spr confirmed")):
        return 1
    if len(failure.get("root_cause", "")) >= 40:
        return 2
    return 3


def _classify_tier_campaign(campaign: dict[str, Any], stub_mode: bool) -> int:
    """Heuristic tier classification for a campaign entity.

    Campaigns with peer-reviewed publication tags in notes count Tier 1.
    Campaigns with replication info Tier 2. Others Tier 3.
    """
    if stub_mode:
        return 3
    notes = (campaign.get("notes", "") or "").lower()
    if any(tok in notes for tok in ("peer reviewed", "doi:", "published")):
        return 1
    if any(tok in notes for tok in ("replicated", "two rounds", "round 2", "round 3")):
        return 2
    return 3


def search_evidence_for_mechanism(
    mechanism: str,
    target: str,
    modality: str,
    campaigns: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    stub_mode: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Search knowledge graph for evidence relating to a mechanism.

    Returns (supporting, contradicting) evidence records.
    Each record matches the evidence_record schema in
    references/hypothesis-output-schema.md.
    """
    mech_tokens = _tokenize(mechanism.replace("_", " "))
    target_tokens = _tokenize(target)
    modality_tokens = _tokenize(modality)
    query_tokens = mech_tokens | target_tokens | modality_tokens

    supporting: list[dict[str, Any]] = []
    contradicting: list[dict[str, Any]] = []

    # Failures are most directly relevant.
    for failure in failures:
        ent_tokens = _tokenize(_entity_text_for_failure(failure))
        overlap = len(query_tokens & ent_tokens)
        if overlap < 2:
            continue
        tier = _classify_tier_failure(failure, stub_mode)
        weight = TIER_WEIGHTS[tier]
        relation = "supports" if mech_tokens & ent_tokens else "partially_supports"
        record = {
            "entity_id": failure.get("id", ""),
            "type": "failure",
            "claim_relation": relation,
            "weight": weight,
            "tier": tier,
            "excerpt": (failure.get("root_cause", "") or failure.get("description", ""))[:240],
        }
        supporting.append(record)

    # Campaigns: hit-rate-sensitive interpretation.
    for campaign in campaigns:
        ent_tokens = _tokenize(_entity_text_for_campaign(campaign))
        if len(query_tokens & ent_tokens) < 2:
            continue
        outcomes = campaign.get("outcomes") or {}
        hit_rate = outcomes.get("hit_rate")
        tier = _classify_tier_campaign(campaign, stub_mode)
        weight = TIER_WEIGHTS[tier]
        excerpt = (campaign.get("notes") or "")[:240]
        record = {
            "entity_id": campaign.get("id", ""),
            "type": "campaign",
            "claim_relation": "partially_supports",
            "weight": weight,
            "tier": tier,
            "excerpt": excerpt or f"Campaign hit_rate={hit_rate}",
        }
        if isinstance(hit_rate, (int, float)) and hit_rate >= 0.30:
            # High-pass-rate campaign at this mechanism context suggests
            # mechanism was overcome — that contradicts the hypothesis.
            record["claim_relation"] = "contradicts_partially"
            contradicting.append(record)
        else:
            supporting.append(record)

    return supporting, contradicting


# ---------------------------------------------------------------------------
# Confidence assignment per precedence table
# ---------------------------------------------------------------------------


def best_tier(records: list[dict[str, Any]]) -> int | None:
    """Return the strongest (lowest-numbered) tier in a record list, or None."""
    tiers = [r.get("tier") for r in records if isinstance(r.get("tier"), int)]
    return min(tiers) if tiers else None


def assign_confidence(
    supporting: list[dict[str, Any]],
    contradicting: list[dict[str, Any]],
    stub_mode: bool,
) -> str | None:
    """Assign final confidence per references/evidence-grading.md.

    Returns the confidence string, or None if the hypothesis must be refused.
    Stub-mode forces SPECULATIVE.
    """
    if not supporting:
        return None
    if stub_mode:
        return "SPECULATIVE"
    sup_tier = best_tier(supporting)
    con_tier = best_tier(contradicting)
    # Precedence table (see references/evidence-grading.md).
    if sup_tier == 1 and con_tier is None:
        return "HIGH"
    if sup_tier == 1 and con_tier == 3:
        return "HIGH"
    if sup_tier == 1 and con_tier == 2:
        return "MEDIUM"
    if sup_tier == 1 and con_tier == 1:
        return "SPECULATIVE"
    if sup_tier == 2 and con_tier is None:
        return "MEDIUM"
    if sup_tier == 2 and con_tier == 3:
        return "MEDIUM"
    if sup_tier == 2 and con_tier in (1, 2):
        return "SPECULATIVE"
    # Sup tier 3 (or worse) — always SPECULATIVE.
    return "SPECULATIVE"


def recommended_next_action(confidence: str, supporting_count: int) -> str:
    """Pick the downstream skill based on confidence and evidence count."""
    if confidence == "HIGH" and supporting_count >= 2:
        return "by-campaign-optimizer"
    if confidence == "SPECULATIVE":
        return "by-hypothesis-debate"
    return "by-hypothesis-debate"


# ---------------------------------------------------------------------------
# Claim / prediction templates (filled in by the agent at runtime)
# ---------------------------------------------------------------------------


CLAIM_TEMPLATE = (
    "Designs failed due to {mechanism_human}, manifesting as "
    "{primary_feature_observation}. [Agent: rewrite this sentence to name "
    "the specific residue(s) or interface region implicated, citing the "
    "epitope output if available. Single sentence, indicative tense.]"
)

PREDICTION_TEMPLATE = (
    "[Agent: name a specific assay from the assay-vocabulary list in "
    "references/hypothesis-output-schema.md, a numeric readout, and a "
    "threshold that would confirm or refute the {mechanism_human} claim. "
    "Example shape: 'SPR will show kon <X for FAIL designs vs >Y for PASS.']"
)


MECHANISM_HUMAN_NAMES: dict[str, str] = {
    "steric_clash": "steric clash at the binder-target interface",
    "electrostatic_mismatch": "electrostatic mismatch between binder and target surface",
    "hydrophobic_aggregation": "hydrophobic patch driving self-aggregation",
    "cryptic_epitope_inaccessibility": "cryptic epitope inaccessibility in the dominant target conformation",
    "polyspecificity_or_off_target": "polyspecificity producing off-target binding",
    "kinetic_mismatch_slow_on_rate": "slow on-rate kinetic mismatch",
    "allosteric_perturbation": "allosteric perturbation of the target",
    "disulfide_or_ptm_issue": "disulfide or post-translational modification liability",
}


def primary_feature_observation(
    mechanism: str, diagnosis: dict[str, Any]
) -> str:
    """Build a short observation string from the most-relevant diagnosis feature."""
    relevant_features = {
        feat: prim
        for feat, mechs in FEATURE_TO_MECHANISMS.items()
        for prim, _ in mechs
        if prim == mechanism
    }
    if not relevant_features:
        return "the observed discriminating-feature pattern"
    feature_list = diagnosis.get("discriminating_features", []) or []
    for feat in feature_list:
        name = (feat.get("feature_name") or feat.get("feature") or "").lower()
        if name in relevant_features:
            return (
                f"{name} (PASS mean={feat.get('passed_mean')}, "
                f"FAIL mean={feat.get('failed_mean')})"
            )
    return "the observed discriminating-feature pattern"


# ---------------------------------------------------------------------------
# Evidence trail rendering
# ---------------------------------------------------------------------------


def render_evidence_trail(
    target: str,
    modality: str,
    diagnosis_path: str,
    epitope_path: str | None,
    experiment_path: str | None,
    candidates: list[tuple[str, float]],
    hypotheses: list[dict[str, Any]],
    deferred_mechanisms: list[str],
    stub_mode: bool,
    campaigns_count: int,
    failures_count: int,
) -> str:
    """Render the evidence_trail.md narrative."""
    lines: list[str] = []
    lines.append("# Causal-Reasoning Evidence Trail")
    lines.append("")
    lines.append(f"- Target: `{target}`")
    lines.append(f"- Modality: `{modality}`")
    lines.append(f"- Diagnosis source: `{diagnosis_path}`")
    lines.append(f"- Epitope source: `{epitope_path or 'none — structural hypotheses downgraded'}`")
    lines.append(f"- Lab calibration source: `{experiment_path or 'none'}`")
    lines.append(f"- Generated at: {dt.datetime.utcnow().isoformat(timespec='seconds')}Z")
    lines.append("")
    if stub_mode:
        lines.append("> ⚠️ **STUB MODE** — the by-knowledge graph was unreachable or empty.")
        lines.append("> Every hypothesis below is labeled SPECULATIVE regardless of nominal tier.")
        lines.append("> Do NOT pass this artifact to by-campaign-optimizer.")
        lines.append("")
    lines.append(f"- Knowledge graph: {campaigns_count} campaigns, {failures_count} failures searched")
    lines.append("")
    lines.append("## Candidate mechanisms (after diagnosis voting)")
    lines.append("")
    if not candidates:
        lines.append("_No mechanism reached the vote threshold (≥1.0). Diagnosis may be too noisy._")
    else:
        for mech, score in candidates:
            lines.append(f"- `{mech}` — vote weight {score:.2f}")
    lines.append("")
    lines.append("## Hypotheses emitted")
    lines.append("")
    if not hypotheses:
        lines.append("_None — see Notes below._")
    for hyp in hypotheses:
        lines.append(f"### #{hyp['rank']} {hyp['mechanism']} ({hyp['confidence']})")
        lines.append(f"- Supporting evidence: {len(hyp['supporting_evidence'])}")
        lines.append(f"- Contradicting evidence: {len(hyp['contradicting_evidence'])}")
        for ev in hyp["supporting_evidence"]:
            lines.append(
                f"  - SUPPORT `{ev['entity_id']}` (tier {ev['tier']}, "
                f"{ev['claim_relation']}): {ev.get('excerpt','')}"
            )
        for ev in hyp["contradicting_evidence"]:
            lines.append(
                f"  - CONTRADICT `{ev['entity_id']}` (tier {ev['tier']}, "
                f"{ev['claim_relation']}): {ev.get('excerpt','')}"
            )
        lines.append(f"- Next action: `{hyp['recommended_next_action']}`")
        lines.append("")
    if deferred_mechanisms:
        lines.append("## Deferred mechanisms (parsimony cap)")
        lines.append("")
        for mech in deferred_mechanisms:
            lines.append(f"- `{mech}` — voted but cut at the 5-hypothesis cap; route to by-hypothesis-debate")
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Confidence values are assigned mechanically per the precedence "
        "table in `references/evidence-grading.md` and MUST NOT be modified."
    )
    lines.append(
        "- The agent fills only the `claim` and `falsifiable_prediction` "
        "fields in `hypotheses.json`. Evidence citations are populated here."
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    args = parse_args()

    # 1. Load diagnosis (required).
    try:
        diagnosis = _read_json(args.diagnosis)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"✗ Failed to read diagnosis: {exc}")
    n_features = len(diagnosis.get("discriminating_features", []) or [])
    n_sig = sum(
        1
        for f in (diagnosis.get("discriminating_features") or [])
        if (f.get("adjusted_p_value", f.get("q_value", f.get("p_value"))) or 1.0)
        < SIGNIFICANCE_P
    )
    print(f"✓ Loaded diagnosis: {n_features} features tested, {n_sig} significant")

    # 2. Load epitope (optional).
    epitope: dict[str, Any] | None = None
    if args.epitope:
        try:
            epitope = _read_json(args.epitope)
            n_hot = len(epitope.get("hotspots") or [])
            print(
                f"✓ Loaded epitope: {n_hot} hotspots, "
                f"topology={epitope.get('topology')}, "
                f"druggability={epitope.get('druggability')}"
            )
        except (OSError, json.JSONDecodeError) as exc:
            print(f"⚠️ Failed to read epitope ({exc}); structural claims will be downgraded", file=sys.stderr)
            epitope = None

    # 3. Load lab calibration (optional).
    lab: dict[str, Any] | None = None
    if args.experiment:
        try:
            lab = _read_json(args.experiment)
            print(f"✓ Loaded lab calibration with {len(lab.get('results') or [])} entries")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"⚠️ Failed to read experiment results ({exc}); lab calibration skipped", file=sys.stderr)
            lab = None

    # 4. Resolve and load knowledge graph.
    kdir = _resolve_knowledge_dir(args.knowledge_dir)
    campaigns, failures, stub_mode = _load_knowledge(kdir)
    print(
        f"✓ Queried knowledge graph: {len(campaigns)} campaigns, "
        f"{len(failures)} matching failures"
        + (" (STUB MODE)" if stub_mode else "")
    )

    # 5. Vote on candidate mechanisms.
    candidates_raw = collect_candidate_mechanisms(diagnosis)
    candidates = merge_compatible_mechanisms(candidates_raw)
    if not candidates:
        # Write an empty hypotheses file and exit cleanly.
        out_payload = {
            "campaign_id": str(Path(args.out).parent.name) or f"campaign_{uuid.uuid4().hex[:12]}",
            "target": args.target,
            "modality": args.modality,
            "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "diagnosis_source": args.diagnosis,
            "epitope_source": args.epitope,
            "lab_calibration_source": args.experiment,
            "knowledge_graph_snapshot": {
                "campaigns_searched": len(campaigns),
                "failures_searched": len(failures),
                "stub_mode": stub_mode,
            },
            "hypotheses": [],
            "status": "no_signal",
        }
        Path(args.out).write_text(json.dumps(out_payload, indent=2))
        Path(args.trail).write_text(
            render_evidence_trail(
                args.target,
                args.modality,
                args.diagnosis,
                args.epitope,
                args.experiment,
                [],
                [],
                [],
                stub_mode,
                len(campaigns),
                len(failures),
            )
        )
        print("⚠️ No mechanism reached the vote threshold; emitted empty hypotheses.json")
        return

    # 6. Apply parsimony cap.
    max_h = min(args.max_hypotheses, 5)
    if args.allow_overflow:
        max_h = min(args.max_hypotheses, len(candidates))
    chosen = candidates[:max_h]
    deferred = [m for m, _ in candidates[max_h:]]

    # 7. Build hypotheses with evidence and confidence.
    hypotheses: list[dict[str, Any]] = []
    rank = 0
    for mechanism, _vote in chosen:
        supporting, contradicting = search_evidence_for_mechanism(
            mechanism, args.target, args.modality, campaigns, failures, stub_mode,
        )
        confidence = assign_confidence(supporting, contradicting, stub_mode)
        if confidence is None:
            # No supporting evidence -> refuse to emit (per evidence-grading rules).
            continue
        rank += 1
        mech_human = MECHANISM_HUMAN_NAMES.get(mechanism, mechanism.replace("_", " "))
        hypotheses.append({
            "rank": rank,
            "claim": CLAIM_TEMPLATE.format(
                mechanism_human=mech_human,
                primary_feature_observation=primary_feature_observation(mechanism, diagnosis),
            ),
            "mechanism": mechanism,
            "confidence": confidence,
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "falsifiable_prediction": PREDICTION_TEMPLATE.format(mechanism_human=mech_human),
            "recommended_next_action": recommended_next_action(confidence, len(supporting)),
            "notes": "",
        })

    # 8. Sort by (confidence_rank, supporting_count, -contradicting_count).
    conf_order = {"HIGH": 0, "MEDIUM": 1, "SPECULATIVE": 2}
    hypotheses.sort(
        key=lambda h: (
            conf_order[h["confidence"]],
            -len(h["supporting_evidence"]),
            len(h["contradicting_evidence"]),
        )
    )
    # Re-rank after sorting.
    for i, h in enumerate(hypotheses, start=1):
        h["rank"] = i

    # 9. Emit JSON payload.
    payload = {
        "campaign_id": str(Path(args.out).parent.name) or f"campaign_{uuid.uuid4().hex[:12]}",
        "target": args.target,
        "modality": args.modality,
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "diagnosis_source": args.diagnosis,
        "epitope_source": args.epitope,
        "lab_calibration_source": args.experiment,
        "knowledge_graph_snapshot": {
            "campaigns_searched": len(campaigns),
            "failures_searched": len(failures),
            "stub_mode": stub_mode,
        },
        "hypotheses": hypotheses,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2))

    # 10. Emit evidence trail.
    Path(args.trail).write_text(
        render_evidence_trail(
            args.target,
            args.modality,
            args.diagnosis,
            args.epitope,
            args.experiment,
            candidates,
            hypotheses,
            deferred,
            stub_mode,
            len(campaigns),
            len(failures),
        )
    )

    # 11. Done.
    counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "SPECULATIVE": 0}
    for h in hypotheses:
        counts[h["confidence"]] = counts.get(h["confidence"], 0) + 1
    print(
        f"✓ Generated {len(hypotheses)} hypotheses "
        f"({counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, "
        f"{counts['SPECULATIVE']} SPECULATIVE)"
    )
    print(f"✓ Wrote {args.out}")
    print(f"✓ Wrote {args.trail}")


if __name__ == "__main__":
    main()
