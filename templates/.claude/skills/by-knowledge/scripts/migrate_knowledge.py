#!/usr/bin/env python3
"""Migration utility for the BY knowledge graph.

Purpose:
    Read NDJSON entity dumps, validate against the schema documented in
    references/graph-schema.md, normalize to the canonical on-disk format
    (campaigns.json + failures.json), and handle schema-version upgrades
    (currently 1.0 -> 2.0).

Inputs:
    --import <path.ndjson>   Ingest an NDJSON dump into the JSON-array store
    --export <path.ndjson>   Dump the current store as NDJSON
    --validate               Validate the current store against the schema
    --upgrade                Apply schema-version transforms (1.0 -> 2.0)
    --recent N               Print the N most-recent campaigns (utility mode)
    --extract <id>           Print the full record for a single campaign id

Outputs:
    Validated NDJSON file (export mode), updated JSON-array store
    (import / upgrade mode), or stdout listing (recent / extract mode).

Example invocation:
    python3 migrate_knowledge.py --validate
    python3 migrate_knowledge.py --export /tmp/dump.ndjson
    python3 migrate_knowledge.py --import /tmp/restored.ndjson
    python3 migrate_knowledge.py --upgrade
    python3 migrate_knowledge.py --recent 10
    python3 migrate_knowledge.py --extract campaign_a1b2c3d4e5f6
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = "2.0"

VALID_MODALITIES = {"antibody", "nanobody", "VHH", "scFv", "de_novo", "binder"}
VALID_STATUS = {"PASS", "FAIL"}

CAMPAIGN_ID_RE = re.compile(r"^campaign_[a-f0-9]{12}$")
FAILURE_ID_RE = re.compile(r"^failure_[a-f0-9]{12}$")
TARGET_NORMALIZED_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


# ---------------------------------------------------------------------------
# Storage resolution (mirrors templates/.claude/mcp_servers/knowledge/server.py)
# ---------------------------------------------------------------------------


def resolve_knowledge_dir() -> Path:
    env_dir = os.environ.get("KNOWLEDGE_DIR")
    if env_dir:
        return Path(env_dir)
    project_root = os.environ.get("BY_PROJECT_ROOT")
    if project_root:
        return Path(project_root) / ".by" / "knowledge"
    return Path(os.path.expanduser("~")) / ".by" / "knowledge"


def load_json_array(path: Path) -> list[dict]:
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"warning: could not load {path}: {exc}", file=sys.stderr)
    return []


def save_json_array(path: Path, data: list[dict]) -> None:
    """Atomic write: write to .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.rename(path)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_campaign(c: dict, strict: bool = False) -> list[str]:
    """Return a list of validation messages. Empty list = valid."""
    issues: list[str] = []

    cid = c.get("id", "")
    if not CAMPAIGN_ID_RE.match(cid):
        issues.append(f"id {cid!r} does not match ^campaign_[a-f0-9]{{12}}$")

    target = c.get("target", "")
    if not target:
        issues.append("target is required")
    elif not TARGET_NORMALIZED_RE.match(target):
        issues.append(
            f"target {target!r} not normalized (use lowercase-hyphenated form)"
        )

    modality = c.get("modality", "")
    if modality not in VALID_MODALITIES:
        issues.append(f"modality {modality!r} not in {sorted(VALID_MODALITIES)}")

    outcomes = c.get("outcomes", {})
    if not isinstance(outcomes, dict):
        issues.append("outcomes must be a dict")
    else:
        for key in ("hit_rate", "best_ipsae", "best_iptm", "screening_pass_rate"):
            v = outcomes.get(key)
            if v is not None:
                try:
                    vf = float(v)
                    if not (0.0 <= vf <= 1.0):
                        issues.append(f"outcomes.{key}={v} out of range [0, 1]")
                except (ValueError, TypeError):
                    issues.append(f"outcomes.{key}={v!r} not numeric")

    stored_at = c.get("stored_at", 0)
    try:
        if float(stored_at) < 1.6e9:
            issues.append(f"stored_at={stored_at} suspicious (pre-2020)")
    except (ValueError, TypeError):
        issues.append(f"stored_at={stored_at!r} not numeric")

    designs = c.get("designs", [])
    if designs:
        if not isinstance(designs, list):
            issues.append("designs must be a list")
        else:
            if len(designs) > 25:
                issues.append(f"designs has {len(designs)} entries (limit 25)")
            elif len(designs) > 15:
                # warning, not error
                if strict:
                    issues.append(
                        f"designs has {len(designs)} entries (>15, soft warning)"
                    )
            for i, d in enumerate(designs):
                if not isinstance(d, dict):
                    issues.append(f"designs[{i}] not a dict")
                    continue
                if not d.get("design_id"):
                    issues.append(f"designs[{i}] missing design_id")
                if d.get("status") and d["status"] not in VALID_STATUS:
                    issues.append(f"designs[{i}].status {d['status']!r} invalid")

    return issues


def validate_failure(f: dict) -> list[str]:
    issues: list[str] = []
    fid = f.get("id", "")
    if not FAILURE_ID_RE.match(fid):
        issues.append(f"id {fid!r} does not match ^failure_[a-f0-9]{{12}}$")
    for required in ("campaign_id", "description", "root_cause", "target"):
        if not f.get(required):
            issues.append(f"{required} is required and non-empty")
    return issues


def cmd_validate(strict: bool) -> int:
    knowledge_dir = resolve_knowledge_dir()
    campaigns = load_json_array(knowledge_dir / "campaigns.json")
    failures = load_json_array(knowledge_dir / "failures.json")

    total_issues = 0
    print(f"Validating {knowledge_dir}")
    print(f"  {len(campaigns)} campaigns, {len(failures)} failures")

    for i, c in enumerate(campaigns):
        issues = validate_campaign(c, strict=strict)
        if issues:
            total_issues += len(issues)
            print(f"\ncampaigns[{i}] (id={c.get('id', '?')[:24]}):")
            for issue in issues:
                print(f"  - {issue}")

    for i, f in enumerate(failures):
        issues = validate_failure(f)
        if issues:
            total_issues += len(issues)
            print(f"\nfailures[{i}] (id={f.get('id', '?')[:24]}):")
            for issue in issues:
                print(f"  - {issue}")

    if total_issues == 0:
        print(f"✓ Validation passed: 0 issues across {len(campaigns) + len(failures)} records")
        return 0
    else:
        print(f"\n✗ Validation found {total_issues} issue(s)")
        return 1 if strict else 0


# ---------------------------------------------------------------------------
# Export (JSON-arrays -> NDJSON)
# ---------------------------------------------------------------------------


def cmd_export(output_path: Path) -> int:
    knowledge_dir = resolve_knowledge_dir()
    campaigns = load_json_array(knowledge_dir / "campaigns.json")
    failures = load_json_array(knowledge_dir / "failures.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(output_path, "w") as f:
        for c in campaigns:
            record = {"_entity_type": "campaign", "_schema_version": CURRENT_SCHEMA_VERSION, **c}
            f.write(json.dumps(record) + "\n")
            n += 1
        for fl in failures:
            record = {"_entity_type": "failure", "_schema_version": CURRENT_SCHEMA_VERSION, **fl}
            f.write(json.dumps(record) + "\n")
            n += 1

    print(f"✓ Export completed: {n} records written to {output_path}")
    return 0


# ---------------------------------------------------------------------------
# Import (NDJSON -> JSON-arrays)
# ---------------------------------------------------------------------------


def cmd_import(input_path: Path, strict: bool) -> int:
    if not input_path.exists():
        print(f"✗ Input file not found: {input_path}", file=sys.stderr)
        return 1

    campaigns_in: list[dict] = []
    failures_in: list[dict] = []
    parse_errors = 0
    validation_errors = 0

    with open(input_path) as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                parse_errors += 1
                print(f"line {line_no}: JSON parse error: {exc}", file=sys.stderr)
                continue

            entity_type = rec.pop("_entity_type", None)
            version = rec.pop("_schema_version", "1.0")

            # Upgrade old records if needed
            if version != CURRENT_SCHEMA_VERSION and entity_type == "campaign":
                rec = upgrade_campaign_record(rec, from_version=version)

            if entity_type == "campaign":
                issues = validate_campaign(rec, strict=strict)
                if issues:
                    validation_errors += len(issues)
                    if strict:
                        print(f"line {line_no}: validation failed: {issues}", file=sys.stderr)
                        continue
                campaigns_in.append(rec)
            elif entity_type == "failure":
                issues = validate_failure(rec)
                if issues:
                    validation_errors += len(issues)
                    if strict:
                        print(f"line {line_no}: validation failed: {issues}", file=sys.stderr)
                        continue
                failures_in.append(rec)
            else:
                print(
                    f"line {line_no}: unknown _entity_type {entity_type!r}; skipping",
                    file=sys.stderr,
                )

    knowledge_dir = resolve_knowledge_dir()
    save_json_array(knowledge_dir / "campaigns.json", campaigns_in)
    save_json_array(knowledge_dir / "failures.json", failures_in)

    print(
        f"✓ Import completed: {len(campaigns_in)} campaigns + "
        f"{len(failures_in)} failures written to {knowledge_dir}"
    )
    if parse_errors:
        print(f"  ({parse_errors} parse errors, {validation_errors} validation issues)")
    return 0


# ---------------------------------------------------------------------------
# Upgrade (1.0 -> 2.0 schema transforms)
# ---------------------------------------------------------------------------


def upgrade_campaign_record(c: dict, from_version: str) -> dict:
    """Apply schema-version transforms in-place. Currently handles 1.0 -> 2.0."""
    if from_version == "1.0":
        # v1.0 -> v2.0: ensure designs array exists, compute composite_score if missing
        c.setdefault("designs", [])
        for d in c.get("designs", []):
            if isinstance(d, dict) and "composite_score" not in d:
                ipsae = float(d.get("ipsae", 0) or 0)
                iptm = float(d.get("iptm", 0) or 0)
                liabilities = d.get("liabilities", []) or []
                # Normalize liability count to [0, 1] via 1 - count/10 (clamped)
                liab_norm = max(0.0, 1.0 - (len(liabilities) / 10.0))
                d["composite_score"] = round(
                    0.50 * ipsae + 0.30 * iptm + 0.20 * liab_norm, 4
                )
    return c


def cmd_upgrade() -> int:
    knowledge_dir = resolve_knowledge_dir()
    campaigns_path = knowledge_dir / "campaigns.json"
    campaigns = load_json_array(campaigns_path)

    n_upgraded = 0
    for c in campaigns:
        # If any design lacks composite_score, treat as v1.0 record
        designs = c.get("designs", [])
        needs_upgrade = "designs" not in c or any(
            isinstance(d, dict) and "composite_score" not in d for d in designs
        )
        if needs_upgrade:
            upgrade_campaign_record(c, from_version="1.0")
            n_upgraded += 1

    save_json_array(campaigns_path, campaigns)
    print(f"✓ Upgrade completed: {n_upgraded} campaign(s) migrated to v{CURRENT_SCHEMA_VERSION}")
    return 0


# ---------------------------------------------------------------------------
# Utility: recent / extract
# ---------------------------------------------------------------------------


def cmd_recent(n: int) -> int:
    knowledge_dir = resolve_knowledge_dir()
    campaigns = load_json_array(knowledge_dir / "campaigns.json")
    campaigns.sort(key=lambda x: x.get("stored_at", 0), reverse=True)
    print(f"Most recent {n} campaign(s) (of {len(campaigns)}):")
    for c in campaigns[:n]:
        print(
            f"  {c.get('id', '?')[:24]:<24} target={c.get('target', '?'):<20} "
            f"modality={c.get('modality', '?'):<10} stored_at={c.get('stored_at', 0):.0f}"
        )
    print(f"✓ Recent listing completed: {min(n, len(campaigns))} rows")
    return 0


def cmd_extract(campaign_id: str) -> int:
    knowledge_dir = resolve_knowledge_dir()
    campaigns = load_json_array(knowledge_dir / "campaigns.json")
    matches = [c for c in campaigns if c.get("id") == campaign_id]
    if not matches:
        print(f"✗ No campaign found with id={campaign_id}", file=sys.stderr)
        return 1
    print(json.dumps(matches[0], indent=2))
    print(f"\n✓ Extract completed: {campaign_id}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migration utility for the BY knowledge graph.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--import", dest="import_path", type=Path,
                       help="Ingest an NDJSON dump into the JSON-array store")
    group.add_argument("--export", dest="export_path", type=Path,
                       help="Dump the current store as NDJSON")
    group.add_argument("--validate", action="store_true",
                       help="Validate the current store against the schema")
    group.add_argument("--upgrade", action="store_true",
                       help="Apply schema-version transforms (1.0 -> 2.0)")
    group.add_argument("--recent", type=int, metavar="N",
                       help="Print the N most-recent campaigns")
    group.add_argument("--extract", type=str, metavar="ID",
                       help="Print the full record for a single campaign id")
    parser.add_argument("--strict", action="store_true",
                        help="Treat validation issues as errors (exits non-zero)")

    args = parser.parse_args()

    if args.import_path is not None:
        sys.exit(cmd_import(args.import_path, strict=args.strict))
    if args.export_path is not None:
        sys.exit(cmd_export(args.export_path))
    if args.validate:
        sys.exit(cmd_validate(strict=args.strict))
    if args.upgrade:
        sys.exit(cmd_upgrade())
    if args.recent is not None:
        sys.exit(cmd_recent(args.recent))
    if args.extract is not None:
        sys.exit(cmd_extract(args.extract))


if __name__ == "__main__":
    main()
