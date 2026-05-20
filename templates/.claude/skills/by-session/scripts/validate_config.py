#!/usr/bin/env python3
"""Validate ``.by/config.json`` against the documented schema.

Purpose
-------
Read a BY config file, check it against the schema documented in
``references/config-schema.md``, and report ERROR / WARN / INFO issues to stdout.
Designed to be called from the by-session skill on every session start (returning
sessions) and after any direct edit to ``.by/config.json``.

Inputs
------
- A path to a config JSON file (default: ``.by/config.json``).
- Optional ``--suggest-fix`` flag to print remediation commands.

Outputs
-------
- Stdout: ``✓ Config valid: provider=<name>, profile=<name>`` on success.
- Stderr: one line per issue, prefixed ``[ERROR]``, ``[WARN]``, or ``[INFO]``.

Example
-------
    python3 validate_config.py
    python3 validate_config.py .by/config.json --suggest-fix

Exit codes
----------
- 0 on success (no ERROR-level issues; WARNs allowed)
- 1 if any ERROR-level issue is present
- 2 on filesystem / parse failure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal

Severity = Literal["ERROR", "WARN", "INFO"]

VALID_PROVIDERS = ("local", "hpc", "tamarind", "auto")
VALID_PROFILES = ("quality", "balanced", "budget")
VALID_TIERS = ("preview", "standard", "production")
VALID_HPC_TARGETS = ("runpod", "modal", "lambda", "local_hpc")
ALLOWED_PRIORITY_MEMBERS = {"local", "hpc", "tamarind"}


class Issue:
    """Represents one validation finding with severity, path, message, and a fix hint."""

    def __init__(self, severity: Severity, path: str, message: str, fix: str | None = None):
        self.severity = severity
        self.path = path
        self.message = message
        self.fix = fix

    def render(self, include_fix: bool = False) -> str:
        base = f"[{self.severity}] {self.path}: {self.message}"
        if include_fix and self.fix:
            base += f"\n        → fix: {self.fix}"
        return base


def _get(config: dict[str, Any], dotted: str, default: Any = None) -> Any:
    """Get a nested value via dotted path. Returns `default` if any key is missing."""
    cur: Any = config
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def validate_top_level(config: dict[str, Any], issues: list[Issue]) -> None:
    """Check that the four top-level keys exist."""
    for key in ("model_profile", "compute", "workflow", "safety"):
        if key not in config:
            issues.append(
                Issue(
                    "ERROR",
                    key,
                    f"missing top-level key '{key}'",
                    fix=f"Run init_questionnaire.py --defaults --keep-existing",
                )
            )


def validate_model_profile(config: dict[str, Any], issues: list[Issue]) -> None:
    profile = config.get("model_profile")
    if profile is None:
        return  # caught by top-level check
    if profile not in VALID_PROFILES:
        issues.append(
            Issue(
                "ERROR",
                "model_profile",
                f"got '{profile}', expected one of {VALID_PROFILES}",
                fix="Set model_profile to 'balanced' (recommended).",
            )
        )


def validate_compute(config: dict[str, Any], issues: list[Issue]) -> None:
    compute = config.get("compute")
    if not isinstance(compute, dict):
        return

    # Legacy field name check.
    if "preferred_provider" in compute and "default_provider" not in compute:
        issues.append(
            Issue(
                "WARN",
                "compute.preferred_provider",
                "deprecated field; rename to 'default_provider'",
                fix="python3 init_questionnaire.py --defaults --keep-existing",
            )
        )

    default_provider = compute.get("default_provider") or compute.get("preferred_provider")
    if default_provider is None:
        issues.append(
            Issue(
                "ERROR",
                "compute.default_provider",
                "missing; required field",
                fix="Set compute.default_provider to 'local'.",
            )
        )
    elif default_provider not in VALID_PROVIDERS:
        issues.append(
            Issue(
                "ERROR",
                "compute.default_provider",
                f"got '{default_provider}', expected one of {VALID_PROVIDERS}",
                fix="Set compute.default_provider to 'local'.",
            )
        )

    # Pre-2026-05 default-was-tamarind hint.
    if default_provider == "tamarind" and "providers_priority" not in compute:
        issues.append(
            Issue(
                "INFO",
                "compute.default_provider",
                "set to 'tamarind' but no providers_priority — pre-2026-05 default; new default is 'local'",
                fix="Re-run init_questionnaire.py to switch to local-first (or keep current if intentional).",
            )
        )

    # providers_priority
    priority = compute.get("providers_priority")
    if priority is None:
        issues.append(
            Issue(
                "WARN",
                "compute.providers_priority",
                "missing; defaults to ['local', 'hpc', 'tamarind']",
                fix="Add providers_priority to compute block.",
            )
        )
    elif not isinstance(priority, list) or not priority:
        issues.append(
            Issue(
                "ERROR",
                "compute.providers_priority",
                "must be a non-empty list",
                fix="Set to ['local', 'hpc', 'tamarind'].",
            )
        )
    else:
        bad = [p for p in priority if p not in ALLOWED_PRIORITY_MEMBERS]
        if bad:
            issues.append(
                Issue(
                    "ERROR",
                    "compute.providers_priority",
                    f"unknown providers: {bad}; allowed: {sorted(ALLOWED_PRIORITY_MEMBERS)}",
                    fix="Set to ['local', 'hpc', 'tamarind'].",
                )
            )
        if len(priority) != len(set(priority)):
            issues.append(
                Issue(
                    "ERROR",
                    "compute.providers_priority",
                    "contains duplicates",
                    fix="Deduplicate; canonical order is ['local', 'hpc', 'tamarind'].",
                )
            )

    # HPC-specific checks
    hpc = compute.get("hpc", {})
    if default_provider == "hpc":
        target = hpc.get("target")
        if not target:
            issues.append(
                Issue(
                    "ERROR",
                    "compute.hpc.target",
                    "required when default_provider is 'hpc'",
                    fix="Set to 'runpod' (or another supported target).",
                )
            )
        elif target not in VALID_HPC_TARGETS:
            issues.append(
                Issue(
                    "ERROR",
                    "compute.hpc.target",
                    f"got '{target}', expected one of {VALID_HPC_TARGETS}",
                )
            )
        if not hpc.get("api_key_env"):
            issues.append(
                Issue(
                    "ERROR",
                    "compute.hpc.api_key_env",
                    "required when default_provider is 'hpc'",
                    fix="Set to the env var name holding your HPC API key (e.g., 'RUNPOD_API_KEY').",
                )
            )

    # Tamarind-specific checks
    tamarind = compute.get("tamarind", {})
    if default_provider == "tamarind":
        if not tamarind.get("api_key_env"):
            issues.append(
                Issue(
                    "WARN",
                    "compute.tamarind.api_key_env",
                    "missing; defaults to 'TAMARIND_API_KEY'",
                )
            )


def validate_workflow(config: dict[str, Any], issues: list[Issue]) -> None:
    workflow = config.get("workflow")
    if not isinstance(workflow, dict):
        return
    tier = workflow.get("default_campaign_tier")
    if tier is not None and tier not in VALID_TIERS:
        issues.append(
            Issue(
                "ERROR",
                "workflow.default_campaign_tier",
                f"got '{tier}', expected one of {VALID_TIERS}",
            )
        )


def validate_safety(config: dict[str, Any], issues: list[Issue]) -> None:
    safety = config.get("safety")
    if not isinstance(safety, dict):
        return
    if safety.get("require_plan_approval") is False:
        issues.append(
            Issue(
                "WARN",
                "safety.require_plan_approval",
                "set to false — compute submission will not be gated by plan approval",
                fix="Set to true unless you explicitly want unattended runs.",
            )
        )
    if safety.get("require_lab_approval") is False:
        issues.append(
            Issue(
                "WARN",
                "safety.require_lab_approval",
                "set to false — lab submission triple-gate is disabled",
                fix="Set to true; lab submission should always be triple-gated.",
            )
        )


def validate_config(config: dict[str, Any]) -> list[Issue]:
    """Run all validation passes; return a flat list of Issue objects."""
    issues: list[Issue] = []
    validate_top_level(config, issues)
    validate_model_profile(config, issues)
    validate_compute(config, issues)
    validate_workflow(config, issues)
    validate_safety(config, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate .by/config.json against the documented schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path(".by/config.json"),
        help="Path to config.json (default: .by/config.json)",
    )
    parser.add_argument(
        "--suggest-fix",
        action="store_true",
        help="Print remediation hints alongside each issue.",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"✗ {args.path} does not exist", file=sys.stderr)
        return 2
    try:
        config = json.loads(args.path.read_text())
    except json.JSONDecodeError as e:
        print(f"✗ {args.path} is not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(config, dict):
        print(f"✗ {args.path} top level must be a JSON object", file=sys.stderr)
        return 2

    issues = validate_config(config)
    errors = [i for i in issues if i.severity == "ERROR"]
    warns = [i for i in issues if i.severity == "WARN"]
    infos = [i for i in issues if i.severity == "INFO"]

    for issue in issues:
        print(issue.render(include_fix=args.suggest_fix), file=sys.stderr)

    if errors:
        print(
            f"✗ Config invalid: {len(errors)} error(s), {len(warns)} warning(s)",
            file=sys.stderr,
        )
        return 1

    provider = _get(config, "compute.default_provider", "unknown")
    profile = _get(config, "model_profile", "unknown")
    suffix = ""
    if warns or infos:
        suffix = f" ({len(warns)} warn, {len(infos)} info)"
    print(f"✓ Config valid: provider={provider}, profile={profile}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
