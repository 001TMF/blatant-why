#!/usr/bin/env python3
"""Validate a strategy_proposal.json file against the schema in SKILL.md.

The schema is defined in by-hypothesis-debate/SKILL.md (Outputs section).
This script encodes the schema as a dict of field-name to validator and
exits non-zero on any violation with a precise error message.

Inputs
------
- proposal-path : path to a strategy_proposal.json file

Outputs
-------
- stdout: "✓ Proposal valid: <agent>" on success
- stderr: list of validation errors on failure
- exit code: 0 on success, 1 on validation failure, 2 on I/O failure

Example
-------
    python3 validate_proposal.py campaigns/IL23R/debate/proposals/conservative.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


# Allowed values for enumerated fields.
ALLOWED_AGENTS = {"conservative", "aggressive", "diverse", "safety-engineer", "cost-optimizer", "replication-critic"}
ALLOWED_MODALITIES = {"VHH", "scFv", "Fab", "de_novo_binder", "cyclic_peptide", "bispecific", "mixed"}
ALLOWED_TIERS = {"preview", "standard", "production"}
ALLOWED_PROTOCOLS = {"nanobody-anything", "antibody-anything", "protein-anything", "split_run"}
ALLOWED_COMPUTE_PROVIDERS = {"local", "hpc", "tamarind"}


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and len(value) > 0


def _is_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _is_nonempty_list_of_str(value: Any) -> bool:
    return _is_list_of_str(value) and len(value) > 0


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_number_in_range(low: float, high: float) -> Callable[[Any], bool]:
    def check(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high
    return check


def _is_in_set(allowed: set[str]) -> Callable[[Any], bool]:
    def check(value: Any) -> bool:
        return value in allowed
    return check


def _is_dict_with_keys(required_keys: set[str]) -> Callable[[Any], bool]:
    def check(value: Any) -> bool:
        return isinstance(value, dict) and required_keys.issubset(value.keys())
    return check


# Schema: field name -> (required?, validator, human-readable expectation)
SCHEMA: dict[str, tuple[bool, Callable[[Any], bool], str]] = {
    "agent": (True, _is_in_set(ALLOWED_AGENTS), f"one of {sorted(ALLOWED_AGENTS)}"),
    "version": (True, lambda v: v == "1.0", "literal '1.0'"),
    "target": (True, _is_str, "non-empty string"),
    "modality": (True, _is_in_set(ALLOWED_MODALITIES), f"one of {sorted(ALLOWED_MODALITIES)}"),
    "protocol": (True, _is_in_set(ALLOWED_PROTOCOLS), f"one of {sorted(ALLOWED_PROTOCOLS)}"),
    "scaffolds": (True, _is_nonempty_list_of_str, "non-empty list of strings"),
    "tier": (True, _is_in_set(ALLOWED_TIERS), f"one of {sorted(ALLOWED_TIERS)}"),
    "compute_provider": (True, _is_in_set(ALLOWED_COMPUTE_PROVIDERS), f"one of {sorted(ALLOWED_COMPUTE_PROVIDERS)}"),
    "epitope": (True, _is_dict_with_keys({"range_notation"}), "dict with at least 'range_notation' key"),
    "rationale": (True, _is_str, "non-empty string"),
    "expected_hit_rate": (True, _is_str, "non-empty string (e.g., '20-40%')"),
    "expected_wall_time_hours": (True, lambda v: isinstance(v, (int, float)) and v > 0, "positive number"),
    "key_risks": (True, _is_list_of_str, "list of strings"),
    "mitigation": (True, lambda v: isinstance(v, list), "list (may be empty)"),
    "confidence": (True, _is_number_in_range(0.0, 1.0), "number in [0.0, 1.0]"),
    "research_source_ids": (True, _is_list_of_str, "list of strings"),
    # Optional fields:
    "num_designs_per_scaffold": (False, _is_positive_int, "positive integer (omit for split_run)"),
    "sub_runs": (False, lambda v: isinstance(v, list) and len(v) >= 2, "list of >=2 sub-run dicts (split_run only)"),
    "total_designs": (False, _is_positive_int, "positive integer (split_run only)"),
}


def validate_proposal_dict(proposal: Any) -> list[str]:
    """Return a list of validation error strings. Empty list = valid."""
    errors: list[str] = []
    if not isinstance(proposal, dict):
        return ["Proposal must be a JSON object (dict)."]

    for field, (required, validator, expectation) in SCHEMA.items():
        if field not in proposal:
            if required:
                errors.append(f"Missing required field: '{field}' (expected {expectation})")
            continue
        if not validator(proposal[field]):
            errors.append(
                f"Field '{field}' has invalid value: {proposal[field]!r} "
                f"(expected {expectation})"
            )

    # Cross-field rules:
    protocol = proposal.get("protocol")
    if protocol == "split_run":
        if "sub_runs" not in proposal:
            errors.append("protocol='split_run' requires 'sub_runs' field")
        if "total_designs" not in proposal:
            errors.append("protocol='split_run' requires 'total_designs' field")
    else:
        if "num_designs_per_scaffold" not in proposal:
            errors.append(
                f"protocol={protocol!r} requires 'num_designs_per_scaffold'"
            )

    # Rationale must be substantive (avoid one-word proposals).
    rationale = proposal.get("rationale", "")
    if isinstance(rationale, str) and len(rationale) < 50:
        errors.append("'rationale' is too short (< 50 chars); must justify the strategy")

    # Research citations must be non-empty when modality is conventional.
    sources = proposal.get("research_source_ids", [])
    if isinstance(sources, list) and len(sources) == 0:
        errors.append("'research_source_ids' must contain at least 1 source ID")

    return errors


def validate_proposal_file(path: Path) -> tuple[bool, list[str]]:
    """Load a proposal JSON file and validate it. Returns (is_valid, errors)."""
    if not path.exists():
        return False, [f"File not found: {path}"]
    try:
        with path.open() as f:
            proposal = json.load(f)
    except json.JSONDecodeError as exc:
        return False, [f"Invalid JSON in {path}: {exc}"]
    errors = validate_proposal_dict(proposal)
    return (len(errors) == 0), errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a strategy_proposal.json against the by-hypothesis-debate schema."
    )
    parser.add_argument("proposal_path", type=Path, help="Path to strategy_proposal.json")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success message; still print errors on failure.",
    )
    args = parser.parse_args()

    valid, errors = validate_proposal_file(args.proposal_path)
    if not valid:
        print(f"✗ Proposal invalid: {args.proposal_path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if not args.quiet:
        with args.proposal_path.open() as f:
            proposal = json.load(f)
        print(f"✓ Proposal valid: {proposal.get('agent', 'unknown')} agent at {args.proposal_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
