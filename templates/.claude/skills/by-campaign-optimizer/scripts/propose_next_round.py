#!/usr/bin/env python3
"""Write the next-round YAML config from optimizer output.

Reads an ``optimizer_output.json`` produced by ``optimize_from_csv.py`` and a
previous-round YAML config, then writes a new YAML config with thresholds and
design parameters adjusted according to the optimizer's recommendations.

Inputs:
    --optimizer-output PATH   JSON from optimize_from_csv.py (required)
    --previous-config PATH    YAML config for the round that was just scored (optional)
    --output PATH             Where to write the next-round YAML (required)
    --apply-low-confidence    Apply recommendations even when confidence is 'low'

Behavior:
    - If optimizer source is 'rule_based', writes the previous config unchanged
      with a note explaining the fallback (or a minimal default if no previous
      config was provided).
    - If confidence is 'low' and --apply-low-confidence is not set, writes the
      previous config unchanged with a note.
    - Otherwise applies the recommended thresholds and design count nudges.

Example:
    python propose_next_round.py \\
        --optimizer-output campaign/round_1/optimizer_output.json \\
        --previous-config campaign/round_1/config.yaml \\
        --output campaign/round_2/config.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    sys.exit("Install with: pip install pyyaml")


# Map recommendation key -> location in the YAML config.
# This is intentionally explicit so unusual configs don't get silently mangled.
RECOMMENDATION_KEY_MAP: dict[str, tuple[str, ...]] = {
    "min_ipsae": ("screening", "thresholds", "min_ipsae"),
    "min_iptm": ("screening", "thresholds", "min_iptm"),
    "min_plddt": ("screening", "thresholds", "min_plddt"),
    "max_rmsd": ("screening", "thresholds", "max_rmsd"),
    "target_cdr3_length": ("design", "cdr3_length"),
    "suggested_alpha": ("design", "alpha"),
}


def load_optimizer_output(path: Path) -> dict:
    """Load and minimally validate the optimizer's JSON output."""
    if not path.exists():
        sys.exit(f"Optimizer output not found: {path}")
    data = json.loads(path.read_text())
    if "source" not in data:
        sys.exit(f"Invalid optimizer output (missing 'source'): {path}")
    return data


def load_previous_config(path: Optional[Path]) -> dict:
    """Load the previous-round YAML or return a minimal default."""
    if path is None:
        return {
            "design": {"num_designs": 100, "cdr3_length": 13, "alpha": 0.01},
            "screening": {
                "thresholds": {
                    "min_ipsae": 0.40,
                    "min_iptm": 0.50,
                    "min_plddt": 70.0,
                    "max_rmsd": 5.0,
                }
            },
        }
    if not path.exists():
        sys.exit(f"Previous config not found: {path}")
    return yaml.safe_load(path.read_text()) or {}


def set_nested(config: dict, keys: tuple[str, ...], value: Any) -> None:
    """Set a nested config value, creating intermediate dicts as needed."""
    cursor = config
    for key in keys[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[keys[-1]] = value


def get_nested(config: dict, keys: tuple[str, ...]) -> Any:
    """Get a nested config value, returning None if any key is missing."""
    cursor: Any = config
    for key in keys:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def adjust_num_designs(config: dict, increase: bool) -> tuple[Optional[int], Optional[int]]:
    """Bump num_designs up by 50% if the optimizer recommended it."""
    keys = ("design", "num_designs")
    current = get_nested(config, keys)
    if current is None:
        return (None, None)
    if not isinstance(current, int):
        return (current, current)
    if not increase:
        return (current, current)
    new_value = int(round(current * 1.5))
    set_nested(config, keys, new_value)
    return (current, new_value)


def apply_recommendations(
    config: dict, recommendations: dict
) -> list[dict]:
    """Apply recommendations to the config and return a diff log."""
    diff: list[dict] = []
    for rec_key, value in recommendations.items():
        if rec_key == "increase_num_designs":
            continue  # handled separately
        if rec_key not in RECOMMENDATION_KEY_MAP:
            diff.append(
                {
                    "key": rec_key,
                    "status": "skipped",
                    "reason": "no mapping defined; edit RECOMMENDATION_KEY_MAP to apply",
                }
            )
            continue
        config_keys = RECOMMENDATION_KEY_MAP[rec_key]
        old_value = get_nested(config, config_keys)
        set_nested(config, config_keys, value)
        diff.append(
            {
                "key": ".".join(config_keys),
                "old": old_value,
                "new": value,
                "status": "applied",
            }
        )
    return diff


def propose(
    optimizer_output: dict,
    previous_config: dict,
    apply_low_confidence: bool,
) -> tuple[dict, list[dict], str]:
    """Construct the next-round config. Returns (config, diff, note)."""
    config = deepcopy(previous_config)
    source = optimizer_output.get("source", "rule_based")
    confidence = optimizer_output.get("confidence", "none")

    if source == "rule_based":
        note = (
            "Optimizer fell back to rule-based defaults "
            f"({optimizer_output.get('explanation', 'no explanation')}). "
            "Next-round config is unchanged from previous round."
        )
        return config, [], note

    if confidence == "low" and not apply_low_confidence:
        note = (
            "Optimizer confidence is 'low'; recommendations were NOT applied. "
            "Re-run with --apply-low-confidence to override."
        )
        return config, [], note

    recommendations = optimizer_output.get("recommended_parameters", {})
    diff = apply_recommendations(config, recommendations)
    old, new = adjust_num_designs(
        config, increase=bool(recommendations.get("increase_num_designs", False))
    )
    if old is not None and old != new:
        diff.append(
            {
                "key": "design.num_designs",
                "old": old,
                "new": new,
                "status": "applied",
            }
        )

    # Carry the optimizer's metadata into the new config for traceability
    config.setdefault("optimizer", {})
    config["optimizer"] = {
        "source": source,
        "confidence": confidence,
        "n_designs_trained_on": optimizer_output.get("n_designs"),
        "target": optimizer_output.get("target"),
        "top_features": [
            {"feature": f, "importance": i}
            for f, i in optimizer_output.get("feature_importances", [])[:5]
        ],
        "explanation": optimizer_output.get("explanation"),
        "data_sha256": optimizer_output.get("data_sha256"),
    }

    note = (
        f"Optimizer source={source}, confidence={confidence}. "
        f"{len([d for d in diff if d['status'] == 'applied'])} parameters applied."
    )
    return config, diff, note


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Write next-round YAML config from optimizer output."
    )
    parser.add_argument(
        "--optimizer-output",
        type=Path,
        required=True,
        help="Path to optimizer_output.json from optimize_from_csv.py.",
    )
    parser.add_argument(
        "--previous-config",
        type=Path,
        default=None,
        help="Previous-round YAML config (optional; defaults used if absent).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write the next-round YAML config.",
    )
    parser.add_argument(
        "--apply-low-confidence",
        action="store_true",
        help="Apply recommendations even when confidence is 'low'.",
    )
    args = parser.parse_args()

    optimizer_output = load_optimizer_output(args.optimizer_output)
    previous_config = load_previous_config(args.previous_config)

    config, diff, note = propose(
        optimizer_output, previous_config, args.apply_low_confidence
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(config, sort_keys=False))

    applied = [d for d in diff if d["status"] == "applied"]
    skipped = [d for d in diff if d["status"] == "skipped"]

    print(f"✓ Next-round config written: {args.output}")
    print(f"  Note: {note}")
    if applied:
        print(f"  Applied changes ({len(applied)}):")
        for change in applied:
            print(f"    - {change['key']}: {change['old']} -> {change['new']}")
    if skipped:
        print(f"  Skipped recommendations ({len(skipped)}):")
        for change in skipped:
            print(f"    - {change['key']}: {change['reason']}")


if __name__ == "__main__":
    main()
