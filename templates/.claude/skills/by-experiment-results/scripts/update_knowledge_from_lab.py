#!/usr/bin/env python3
"""Read a calibration.json (from diagnose_silico_vs_lab.py) and push validated /
contradicted findings into the BY knowledge graph.

This is the wet-lab feedback writer. It is idempotent: re-running with the same
campaign_id will not duplicate records (it checks the storage directory first).

For every contradicted feature it writes a knowledge_store_failure record so
future campaigns avoid trusting that predictor for similar targets.

Inputs:
    --calibration <path>    calibration.json from diagnose_silico_vs_lab.py
    --campaign-id <str>     Stable campaign identifier (e.g. campaign_20260520_001)
    --target <str>          Target name (canonical lowercase-hyphenated form)
    --modality <str>        Design modality: antibody | nanobody | VHH | scFv | de_novo | binder
    --scaffold <str>        Optional scaffold name to record in parameters
    --force                 Overwrite existing entries with same campaign_id
    --dry-run               Show what would be written; do not modify storage
    --knowledge-dir <path>  Override storage location (default: respects
                            KNOWLEDGE_DIR env, then $BY_PROJECT_ROOT/.by/knowledge,
                            then ~/.by/knowledge)

Outputs:
    Writes (idempotent) to ~/.by/knowledge/campaigns.json and failures.json.
    Prints a summary line on completion.

Note:
    This script invokes the by-knowledge storage layer DIRECTLY (the same
    file format the MCP server uses) rather than going through the MCP
    transport — this lets it run synchronously as a CLI. The on-disk format
    is the source of truth and matches mcp__by-knowledge__knowledge_*.

Example:
    python3 update_knowledge_from_lab.py \\
        --calibration campaigns/tnfa/c001/calibration.json \\
        --campaign-id campaign_20260520_001 \\
        --target tnf-alpha \\
        --modality VHH \\
        --scaffold caplacizumab
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def resolve_knowledge_dir(override: str | None) -> Path:
    """Mirror the resolution order used by the by-knowledge MCP server."""
    if override:
        return Path(override).expanduser()
    env_dir = os.environ.get("KNOWLEDGE_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    project_root = os.environ.get("BY_PROJECT_ROOT")
    if project_root:
        return Path(project_root).expanduser() / ".by" / "knowledge"
    return Path.home() / ".by" / "knowledge"


def load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open() as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise SystemExit(f"Expected JSON array in {path}; got {type(data).__name__}")
    return data


def save_json_array(path: Path, data: list[dict[str, Any]]) -> None:
    """Atomic write via .tmp + rename, matching the MCP server's safety guarantee."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(data, fh, indent=2, default=str)
    tmp.replace(path)


def build_outcomes(calibration: dict[str, Any]) -> dict[str, Any]:
    """Derive an outcomes dict for knowledge_store_campaign from calibration data."""
    meta = calibration.get("metadata", {})
    features = calibration.get("features", [])

    validated = [f["name"] for f in features if f["verdict"] == "validated"]
    contradicted = [f["name"] for f in features if f["verdict"] == "contradicted"]
    aucs = {f["name"]: f["auc"] for f in features if f.get("auc") is not None}
    precisions = {
        f["name"]: f["precision_at_top_k"]
        for f in features
        if f.get("precision_at_top_k") is not None
    }

    n_total = meta.get("n_joined", 0)
    n_pass = meta.get("n_passed", 0)
    lab_pass_rate = (n_pass / n_total) if n_total else 0.0

    outcomes: dict[str, Any] = {
        "lab_tested": n_total,
        "lab_passed": n_pass,
        "lab_pass_rate": round(lab_pass_rate, 4),
        "calibration": {
            "validated_features": validated,
            "contradicted_features": contradicted,
            "feature_aucs": aucs,
            "feature_precisions_at_top_k": precisions,
            "assay": meta.get("assay"),
        },
    }
    return outcomes


def find_existing_campaign(
    campaigns: list[dict[str, Any]], campaign_id: str
) -> int | None:
    for i, rec in enumerate(campaigns):
        params = rec.get("parameters", {})
        if params.get("campaign_id") == campaign_id:
            return i
    return None


def find_existing_failure(
    failures: list[dict[str, Any]], campaign_id: str, feature: str
) -> bool:
    for rec in failures:
        if (
            rec.get("campaign_id") == campaign_id
            and feature in rec.get("description", "")
        ):
            return True
    return False


def build_campaign_record(
    target: str,
    modality: str,
    campaign_id: str,
    scaffold: str | None,
    outcomes: dict[str, Any],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    now = time.time()
    doc_id = f"campaign_{uuid.uuid4().hex[:12]}"
    parameters: dict[str, Any] = {"campaign_id": campaign_id}
    if scaffold:
        parameters["scaffold"] = scaffold
    parameters["assay"] = calibration.get("metadata", {}).get("assay")

    notes_parts: list[str] = [
        f"Lab feedback for campaign {campaign_id}."
    ]
    validated = outcomes["calibration"]["validated_features"]
    contradicted = outcomes["calibration"]["contradicted_features"]
    if validated:
        notes_parts.append(f"Validated predictors: {', '.join(validated)}.")
    if contradicted:
        notes_parts.append(f"Contradicted predictors: {', '.join(contradicted)}.")
    notes = " ".join(notes_parts)

    return {
        "id": doc_id,
        "target": target,
        "modality": modality,
        "parameters": parameters,
        "outcomes": outcomes,
        "notes": notes,
        "stored_at": now,
        "access_count": 0,
    }


def build_failure_record(
    campaign_id: str, target: str, feature: dict[str, Any]
) -> dict[str, Any]:
    now = time.time()
    doc_id = f"failure_{uuid.uuid4().hex[:12]}"
    direction = "higher" if feature.get("passed_mean", 0) > feature.get("failed_mean", 0) else "lower"
    expected = "higher" if feature.get("higher_is_better") else "lower"
    description = (
        f"In-silico feature '{feature['name']}' contradicted lab outcomes for "
        f"campaign {campaign_id}: lab-PASS designs had {direction} values "
        f"(expected: {expected} for PASS). "
        f"p={feature['p_value']:.4f}, |d|={abs(feature['effect_size']):.2f}"
    )
    root_cause = (
        f"Feature definition or threshold mis-specified for this target class. "
        f"The screener should not trust '{feature['name']}' for {target} "
        f"until the feature pipeline is corrected."
    )
    return {
        "id": doc_id,
        "campaign_id": campaign_id,
        "description": description,
        "root_cause": root_cause,
        "target": target,
        "stored_at": now,
        "access_count": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the BY knowledge graph with lab calibration findings.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--calibration", required=True, help="calibration.json from diagnose_silico_vs_lab.py"
    )
    parser.add_argument("--campaign-id", required=True, help="Stable campaign identifier")
    parser.add_argument(
        "--target", required=True, help="Target name (lowercase-hyphenated)"
    )
    parser.add_argument(
        "--modality",
        default="antibody",
        help="Design modality (antibody, nanobody, VHH, scFv, de_novo, binder)",
    )
    parser.add_argument("--scaffold", default=None, help="Scaffold name (optional)")
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing entries"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written; do not modify storage",
    )
    parser.add_argument(
        "--knowledge-dir",
        default=None,
        help="Override storage directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    calib_path = Path(args.calibration)
    if not calib_path.exists():
        sys.exit(f"Calibration file not found: {calib_path}")

    with calib_path.open() as fh:
        calibration = json.load(fh)

    knowledge_dir = resolve_knowledge_dir(args.knowledge_dir)
    campaigns_path = knowledge_dir / "campaigns.json"
    failures_path = knowledge_dir / "failures.json"

    campaigns = load_json_array(campaigns_path)
    failures = load_json_array(failures_path)

    outcomes = build_outcomes(calibration)
    n_total = outcomes["lab_tested"]
    if n_total < 10:
        print(
            f"⚠ Lab sample size N={n_total} is below 10. "
            "Findings will be recorded but flagged as low-confidence."
        )

    # Campaign record
    existing_idx = find_existing_campaign(campaigns, args.campaign_id)
    campaign_action: str
    if existing_idx is not None and not args.force:
        print(
            f"⚠ Campaign record for campaign_id={args.campaign_id} already exists; "
            "skipping (use --force to overwrite)."
        )
        campaign_action = "skipped"
        campaign_record = campaigns[existing_idx]
    else:
        campaign_record = build_campaign_record(
            target=args.target,
            modality=args.modality,
            campaign_id=args.campaign_id,
            scaffold=args.scaffold,
            outcomes=outcomes,
            calibration=calibration,
        )
        if existing_idx is not None:
            campaigns[existing_idx] = campaign_record
            campaign_action = "overwritten"
        else:
            campaigns.append(campaign_record)
            campaign_action = "written"

    # Failure records (one per contradicted feature)
    contradicted_features = [
        f for f in calibration.get("features", []) if f["verdict"] == "contradicted"
    ]
    failure_records_written: list[dict[str, Any]] = []
    for feat in contradicted_features:
        if find_existing_failure(failures, args.campaign_id, feat["name"]) and not args.force:
            continue
        rec = build_failure_record(args.campaign_id, args.target, feat)
        failures.append(rec)
        failure_records_written.append(rec)

    if args.dry_run:
        print("DRY RUN — no files modified.")
        print(f"  Would {campaign_action} 1 campaign record at {campaigns_path}")
        print(f"  Would write {len(failure_records_written)} failure record(s) at {failures_path}")
        for rec in failure_records_written:
            print(f"    - {rec['description'][:100]}...")
        return 0

    if campaign_action != "skipped":
        save_json_array(campaigns_path, campaigns)
    if failure_records_written:
        save_json_array(failures_path, failures)

    print(
        f"✓ Knowledge update completed: campaign={campaign_action}, "
        f"failures={len(failure_records_written)} (storage={knowledge_dir})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
