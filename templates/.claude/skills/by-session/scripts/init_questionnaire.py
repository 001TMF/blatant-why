#!/usr/bin/env python3
"""First-run config questionnaire for BY projects.

Purpose
-------
Interactively (or via --defaults) build a fresh ``.by/config.json`` that captures
the user's compute provider, model profile, and campaign defaults. The default
provider is ``local`` and the providers_priority is ``["local", "hpc", "tamarind"]``
(local-first); this script must NEVER write ``tamarind`` as the default provider
unless the user explicitly picks it.

Inputs
------
- Interactive: terminal stdin (3 rounds of multiple-choice prompts + optional
  follow-ups for paths and API keys).
- Non-interactive: ``--defaults`` flag — writes the local-first default config
  without asking anything.
- ``--keep-existing`` — merge new fields into an existing ``.by/config.json``
  instead of overwriting; used during the pre-2026-05 → local-first migration.

Outputs
-------
- ``.by/config.json`` in the current working directory (or ``--out`` path).
- Stdout: a one-line confirmation ``✓ Wrote .by/config.json with provider=<name>``.

Example
-------
    # Interactive first-run
    python3 init_questionnaire.py

    # CI / scaffolding default (no prompts)
    python3 init_questionnaire.py --defaults

    # Migrate an old config without nuking user fields
    python3 init_questionnaire.py --defaults --keep-existing

Exit codes
----------
- 0 on success
- 1 on user abort (Ctrl-C) or invalid input after retries
- 2 on filesystem error (e.g., cannot write .by/config.json)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Local-first defaults. These are the authoritative defaults for new installs.
DEFAULT_CONFIG: dict[str, Any] = {
    "model_profile": "balanced",
    "compute": {
        "default_provider": "local",
        "providers_priority": ["local", "hpc", "tamarind"],
        "fallback_allowed": False,
        "local_gpu": True,
        "local": {
            "boltzgen": {"path": None, "conda_env": "bg", "weights": False},
            "protenix": {"path": None, "conda_env": "protenix", "weights": False},
            "pxdesign": {"path": None, "conda_env": "pxdesign", "weights": False},
        },
        "hpc": {
            "target": "runpod",
            "endpoint_url": None,
            "api_key_env": "RUNPOD_API_KEY",
        },
        "tamarind": {
            "tier": "free",
            "api_key_env": "TAMARIND_API_KEY",
        },
        "ssh_hosts": [],
    },
    "workflow": {
        "auto_research": True,
        "auto_screen": True,
        "fold_validation": True,
        "default_campaign_tier": "standard",
    },
    "safety": {
        "require_plan_approval": True,
        "require_lab_approval": True,
    },
}

VALID_PROVIDERS = ("local", "hpc", "tamarind", "auto")
VALID_PROFILES = ("quality", "balanced", "budget")
VALID_TIERS = ("preview", "standard", "production")
VALID_HPC_TARGETS = ("runpod", "modal", "lambda", "local_hpc")


def _ask_choice(prompt: str, options: list[str], default_index: int = 0) -> str:
    """Prompt the user to pick one of `options`. Returns the selected option string.

    `default_index` is the option returned on an empty response.
    """
    while True:
        print(f"\n{prompt}")
        for i, opt in enumerate(options, start=1):
            marker = " (default)" if (i - 1) == default_index else ""
            print(f"  {i}. {opt}{marker}")
        raw = input("Choice [number]: ").strip()
        if raw == "":
            return options[default_index]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"  (please enter a number 1-{len(options)} or press Enter for default)")


def _ask_string(prompt: str, default: str | None = None, allow_empty: bool = True) -> str | None:
    """Prompt the user for a free-form string. Returns the input or `default` if empty."""
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if raw == "":
        if default is not None:
            return default
        if allow_empty:
            return None
        # Re-ask
        return _ask_string(prompt, default, allow_empty)
    return raw


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt the user for a yes/no answer."""
    suffix = " [Y/n]" if default else " [y/N]"
    raw = input(f"{prompt}{suffix}: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes", "1", "true")


def round_1_compute(config: dict[str, Any]) -> None:
    """Round 1: pick the compute provider and follow up with provider-specific questions."""
    provider = _ask_choice(
        "Round 1 / 3 — Compute Provider\n"
        "Where should BY run design computations?",
        options=[
            "local — Use a local NVIDIA GPU (fastest, no cost) [default]",
            "hpc — RunPod or other HPC target (deployed via by-deploy-compute)",
            "tamarind — Tamarind Bio cloud (free tier available)",
            "auto — Detect best available in priority order (local → hpc → tamarind)",
        ],
        default_index=0,
    )
    # Map the rendered option to the short key.
    key = provider.split(" ", 1)[0]
    config["compute"]["default_provider"] = key

    if key == "local":
        print("\nLocal GPU paths (press Enter to leave for /by:setup to auto-detect):")
        for tool in ("boltzgen", "protenix", "pxdesign"):
            path = _ask_string(f"  {tool} install path", default=None, allow_empty=True)
            if path:
                config["compute"]["local"][tool]["path"] = path
    elif key == "hpc":
        target = _ask_choice(
            "HPC target:",
            options=list(VALID_HPC_TARGETS),
            default_index=0,
        )
        config["compute"]["hpc"]["target"] = target
        api_env = _ask_string(
            "  API key env var name",
            default="RUNPOD_API_KEY" if target == "runpod" else None,
            allow_empty=False,
        )
        config["compute"]["hpc"]["api_key_env"] = api_env or "RUNPOD_API_KEY"
        if not os.environ.get(config["compute"]["hpc"]["api_key_env"]):
            print(
                f"  ⚠️  {config['compute']['hpc']['api_key_env']} is not set in this shell.\n"
                f"     by-deploy-compute will need it before submitting jobs."
            )
    elif key == "tamarind":
        api_env = "TAMARIND_API_KEY"
        config["compute"]["tamarind"]["api_key_env"] = api_env
        if not os.environ.get(api_env):
            print(
                "  ⚠️  TAMARIND_API_KEY is not set. Get a free key at https://tamarind.bio\n"
                "     and add it to .env before running campaigns."
            )
    # `auto` needs no follow-up.


def round_2_profile(config: dict[str, Any]) -> None:
    """Round 2: pick the model profile for sub-agents."""
    profile = _ask_choice(
        "Round 2 / 3 — AI Model Profile\n"
        "Which model profile for sub-agents?",
        options=[
            "balanced — Sonnet for most agents (good quality/cost) [default]",
            "quality — Opus for research and design agents (deeper analysis)",
            "budget — Haiku where possible (fastest, lowest cost)",
        ],
        default_index=0,
    )
    config["model_profile"] = profile.split(" ", 1)[0]


def round_3_campaign_defaults(config: dict[str, Any]) -> None:
    """Round 3: pick the default campaign tier."""
    tier = _ask_choice(
        "Round 3 / 3 — Default Campaign Size\n"
        "Default designs per campaign?",
        options=[
            "standard — ~5,000 designs/scaffold (recommended) [default]",
            "preview — ~500 designs (fast feasibility checks)",
            "production — ~20,000 designs (thorough coverage)",
        ],
        default_index=0,
    )
    config["workflow"]["default_campaign_tier"] = tier.split(" ", 1)[0]


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge `overlay` into `base`, recursing into dicts. Returns a new dict."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def write_config(config: dict[str, Any], out_path: Path) -> None:
    """Write `config` to `out_path`, creating parent dirs as needed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(config, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="First-run config questionnaire for BY projects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".by/config.json"),
        help="Destination path for config.json (default: .by/config.json)",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Skip interactive prompts; write the local-first default config.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Merge new fields into existing config instead of overwriting.",
    )
    args = parser.parse_args()

    # Load existing config if --keep-existing was passed.
    existing: dict[str, Any] = {}
    if args.keep_existing and args.out.exists():
        try:
            existing = json.loads(args.out.read_text())
        except json.JSONDecodeError as e:
            print(f"✗ Existing {args.out} is not valid JSON: {e}", file=sys.stderr)
            return 2

    # Migrate pre-2026-05 field names if needed.
    if existing.get("compute", {}).get("preferred_provider") and not existing.get(
        "compute", {}
    ).get("default_provider"):
        existing["compute"]["default_provider"] = existing["compute"].pop(
            "preferred_provider"
        )

    # Build new config starting from defaults.
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy

    if args.defaults:
        print("Using local-first defaults (no prompts).")
    else:
        try:
            round_1_compute(config)
            round_2_profile(config)
            round_3_campaign_defaults(config)
        except (KeyboardInterrupt, EOFError):
            print("\n✗ Aborted by user.", file=sys.stderr)
            return 1

    # If --keep-existing, merge user's old fields over the new defaults
    # (but the new local-first defaults win where the old config was silent).
    if existing:
        # Layer: defaults < existing user fields < this run's answers.
        # The interactive answers should overwrite the existing config's choices
        # where they conflict, since the user just made a fresh choice.
        merged = deep_merge(DEFAULT_CONFIG, existing)
        merged = deep_merge(merged, config)
        config = merged

    try:
        write_config(config, args.out)
    except OSError as e:
        print(f"✗ Cannot write {args.out}: {e}", file=sys.stderr)
        return 2

    provider = config["compute"]["default_provider"]
    profile = config["model_profile"]
    print(f"✓ Wrote {args.out} with provider={provider}, profile={profile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
