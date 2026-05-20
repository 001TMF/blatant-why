#!/usr/bin/env python3
"""Print a progress dashboard for an in-flight BY campaign.

Purpose
-------
Reads the latest checkpoint and run summaries from a campaign directory,
computes running pass rate / ETA / spend-to-date, and prints a compact
dashboard. Designed to be invoked from the campaign-manager skill or as
an ad-hoc shell command.

Inputs (CLI args)
-----------------
- --campaign-dir: path to campaigns/{target}/campaign_{date}_{NNN}/
- --hourly-rate: optional override of GPU $/hr for cost-so-far calc
                 (default reads from cost_estimate.json or assumes $0 local)
- --json: emit machine-readable JSON instead of the text dashboard
- --out: optional path to also write the JSON snapshot

Expected files in the campaign dir
----------------------------------
- checkpoints/NN_*.json — latest one tells us the current phase
- run_*/summary.csv — per-design metrics (optional; gracefully degrades)
- cost_estimate.json — for total budgeted cost (optional)
- campaign_log.json — top-level state (optional but preferred)

Outputs
-------
- Stdout: progress dashboard (text or JSON).
- Optional JSON file with a snapshot for downstream consumption.

Example invocation
------------------
    python scripts/track_progress.py \\
        --campaign-dir campaigns/pdl1/campaign_20260520_001
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Defaults                                                                    #
# --------------------------------------------------------------------------- #

DEFAULT_HOURLY_RATE_USD: float = 0.0  # local-first default
PASS_IPTM_MIN: float = 0.5
PASS_PLDDT_MIN: float = 70.0
PASS_RMSD_MAX: float = 3.5


# --------------------------------------------------------------------------- #
# Dataclasses                                                                 #
# --------------------------------------------------------------------------- #

@dataclass
class RunProgress:
    """Per-run summary."""
    run_id: str
    designs_requested: int = 0
    designs_generated: int = 0
    designs_scored: int = 0
    designs_passed: int = 0
    top_iptm: float = 0.0
    top_ipsae: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    status: str = "unknown"


@dataclass
class ProgressSnapshot:
    """Full dashboard snapshot."""
    campaign_dir: str
    campaign_id: str = ""
    target: str = ""
    tool: str = ""
    tier: str = ""
    phase: str = ""
    phase_index: int = -1
    provider: str = "unknown"
    submitted: int = 0
    scored: int = 0
    passed: int = 0
    pass_rate: float = 0.0
    top_iptm: float = 0.0
    top_ipsae: float = 0.0
    elapsed_hr: float = 0.0
    eta_hr: float | None = None
    spend_so_far_usd: float = 0.0
    budgeted_usd: float | None = None
    runs: list[RunProgress] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# IO helpers                                                                  #
# --------------------------------------------------------------------------- #

def _load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON file or return None if missing/malformed."""
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def find_latest_checkpoint(campaign_dir: Path) -> Path | None:
    """Return the highest-numbered checkpoint file or None."""
    cp_dir = campaign_dir / "checkpoints"
    if not cp_dir.is_dir():
        return None
    files = sorted(
        (p for p in cp_dir.iterdir() if p.suffix == ".json"),
        key=lambda p: p.name,
    )
    return files[-1] if files else None


def list_run_dirs(campaign_dir: Path) -> list[Path]:
    """Return all run_* subdirectories, sorted."""
    return sorted(
        p for p in campaign_dir.iterdir()
        if p.is_dir() and p.name.startswith("run_")
    )


# --------------------------------------------------------------------------- #
# Parsing                                                                     #
# --------------------------------------------------------------------------- #

def parse_summary_csv(path: Path) -> tuple[int, int, float, float]:
    """Return (n_scored, n_passed, top_iptm, top_ipsae) from a summary.csv.

    Gracefully returns zeros if columns are missing or file is malformed.
    """
    if not path.exists():
        return 0, 0, 0.0, 0.0
    n_scored = 0
    n_passed = 0
    top_iptm = 0.0
    top_ipsae = 0.0
    try:
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                n_scored += 1
                try:
                    iptm = float(row.get("ipTM", row.get("iptm", "0")) or 0)
                    plddt = float(row.get("pLDDT", row.get("plddt", "0")) or 0)
                    rmsd = float(row.get("RMSD", row.get("rmsd", "999")) or 999)
                    ipsae = float(row.get("ipSAE_min", row.get("ipsae_min", "0")) or 0)
                except ValueError:
                    continue
                top_iptm = max(top_iptm, iptm)
                top_ipsae = max(top_ipsae, ipsae)
                if (iptm >= PASS_IPTM_MIN and plddt >= PASS_PLDDT_MIN
                        and rmsd <= PASS_RMSD_MAX):
                    n_passed += 1
    except OSError:
        return 0, 0, 0.0, 0.0
    return n_scored, n_passed, top_iptm, top_ipsae


def collect_run_progress(campaign_dir: Path) -> list[RunProgress]:
    """Scan run_* dirs and compute per-run progress."""
    progress: list[RunProgress] = []
    for run_dir in list_run_dirs(campaign_dir):
        n_scored, n_passed, top_iptm, top_ipsae = parse_summary_csv(
            run_dir / "summary.csv"
        )
        # Count generated designs by counting design files if available
        designs_dir = run_dir / "designs"
        designs_generated = 0
        if designs_dir.is_dir():
            designs_generated = sum(1 for _ in designs_dir.iterdir())
        progress.append(RunProgress(
            run_id=run_dir.name,
            designs_generated=designs_generated,
            designs_scored=n_scored,
            designs_passed=n_passed,
            top_iptm=round(top_iptm, 3),
            top_ipsae=round(top_ipsae, 3),
        ))
    return progress


# --------------------------------------------------------------------------- #
# Aggregation                                                                 #
# --------------------------------------------------------------------------- #

def parse_iso_utc(s: str | None) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp string. Returns None on failure."""
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def compute_eta_hours(
    started_at: str | None,
    scored: int,
    submitted: int,
) -> tuple[float, float | None]:
    """Return (elapsed_hr, eta_hr) given start time and scoring progress."""
    start = parse_iso_utc(started_at)
    if start is None:
        return 0.0, None
    now = datetime.now(timezone.utc)
    elapsed_hr = (now - start).total_seconds() / 3600.0
    if scored <= 0 or submitted <= scored:
        return round(elapsed_hr, 2), None
    rate_per_hr = scored / elapsed_hr if elapsed_hr > 0 else 0
    if rate_per_hr <= 0:
        return round(elapsed_hr, 2), None
    remaining = submitted - scored
    eta_hr = remaining / rate_per_hr
    return round(elapsed_hr, 2), round(eta_hr, 2)


def aggregate(
    campaign_dir: Path,
    hourly_rate: float,
) -> ProgressSnapshot:
    """Aggregate campaign state, checkpoint, and per-run progress."""
    snapshot = ProgressSnapshot(campaign_dir=str(campaign_dir))

    if not campaign_dir.is_dir():
        snapshot.warnings.append(f"Campaign dir does not exist: {campaign_dir}")
        return snapshot

    # Top-level campaign log
    log = _load_json(campaign_dir / "campaign_log.json") or {}
    snapshot.campaign_id = log.get("campaign_id", campaign_dir.name)
    target_obj = log.get("target", {})
    snapshot.target = (
        target_obj.get("name", "")
        if isinstance(target_obj, dict) else str(target_obj)
    )
    snapshot.tool = log.get("tool", "")
    snapshot.tier = log.get("tier", "")

    # Latest checkpoint
    cp_path = find_latest_checkpoint(campaign_dir)
    if cp_path is not None:
        cp = _load_json(cp_path) or {}
        snapshot.phase = cp.get("phase", "")
        snapshot.phase_index = int(cp.get("phase_index", -1))
        ps = cp.get("phase_specific", {})
        snapshot.provider = ps.get("provider", log.get("compute_provider", "unknown"))
    else:
        snapshot.warnings.append("No checkpoint files found.")

    # Cost estimate (if present)
    cost = _load_json(campaign_dir / "cost_estimate.json") or {}
    budget = None
    if cost:
        # Pick the matching provider estimate when possible
        for est in cost.get("estimates", []):
            if isinstance(est, dict) and est.get("provider", "").startswith(snapshot.provider):
                budget = est.get("cost_usd_mid")
                break
    snapshot.budgeted_usd = budget

    # Per-run progress
    snapshot.runs = collect_run_progress(campaign_dir)
    snapshot.submitted = sum(r.designs_generated for r in snapshot.runs)
    snapshot.scored = sum(r.designs_scored for r in snapshot.runs)
    snapshot.passed = sum(r.designs_passed for r in snapshot.runs)
    snapshot.pass_rate = (
        round(snapshot.passed / snapshot.scored, 3)
        if snapshot.scored > 0 else 0.0
    )
    snapshot.top_iptm = max((r.top_iptm for r in snapshot.runs), default=0.0)
    snapshot.top_ipsae = max((r.top_ipsae for r in snapshot.runs), default=0.0)

    # Elapsed + ETA
    started_at = log.get("created_at") or log.get("started_at")
    snapshot.elapsed_hr, snapshot.eta_hr = compute_eta_hours(
        started_at, snapshot.scored, snapshot.submitted
    )

    # Spend so far = elapsed * hourly_rate
    snapshot.spend_so_far_usd = round(snapshot.elapsed_hr * hourly_rate, 2)

    return snapshot


# --------------------------------------------------------------------------- #
# Rendering                                                                   #
# --------------------------------------------------------------------------- #

def render_dashboard(snap: ProgressSnapshot) -> str:
    """Render a compact text dashboard."""
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append(f"Campaign Progress: {snap.campaign_id}")
    lines.append("=" * 64)
    lines.append(f"  Target:   {snap.target or '(unknown)'}")
    lines.append(f"  Tool:     {snap.tool or '(unknown)'}   Tier: {snap.tier or '(unknown)'}")
    lines.append(f"  Phase:    {snap.phase} (#{snap.phase_index})")
    lines.append(f"  Provider: {snap.provider}")
    lines.append("")
    lines.append(f"  Submitted: {snap.submitted:>6}")
    lines.append(f"  Scored:    {snap.scored:>6}")
    lines.append(f"  Passed:    {snap.passed:>6}   (pass rate {snap.pass_rate*100:.1f}%)")
    lines.append(f"  Top ipTM:  {snap.top_iptm:.3f}")
    lines.append(f"  Top ipSAE: {snap.top_ipsae:.3f}")
    lines.append("")
    eta_str = (
        f"~{snap.eta_hr:.1f} hr" if snap.eta_hr is not None else "n/a"
    )
    lines.append(f"  Elapsed:   {snap.elapsed_hr:.1f} hr")
    lines.append(f"  ETA:       {eta_str}")
    budget_str = (
        f" / ${snap.budgeted_usd:.2f}" if snap.budgeted_usd is not None else ""
    )
    lines.append(f"  Spend:     ${snap.spend_so_far_usd:.2f}{budget_str}")
    if snap.runs:
        lines.append("")
        lines.append("  Per-run breakdown:")
        for r in snap.runs:
            lines.append(
                f"    {r.run_id:<12} generated={r.designs_generated:>4}  "
                f"scored={r.designs_scored:>4}  passed={r.designs_passed:>4}  "
                f"top_iptm={r.top_iptm:.3f}"
            )
    if snap.warnings:
        lines.append("")
        lines.append("  Warnings:")
        for w in snap.warnings:
            lines.append(f"    - {w}")
    lines.append("=" * 64)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="track_progress.py",
        description="Print a progress dashboard for an in-flight BY campaign.",
    )
    parser.add_argument(
        "--campaign-dir", required=True,
        help="Path to campaigns/{target}/campaign_{date}_{NNN}/",
    )
    parser.add_argument(
        "--hourly-rate", type=float, default=DEFAULT_HOURLY_RATE_USD,
        help=(
            "GPU $/hr override for spend-so-far calc "
            f"(default {DEFAULT_HOURLY_RATE_USD} for local)."
        ),
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of the text dashboard.",
    )
    parser.add_argument(
        "--out", default=None,
        help="Optional path to write the JSON snapshot.",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    campaign_dir = Path(args.campaign_dir).expanduser().resolve()
    snapshot = aggregate(campaign_dir, hourly_rate=args.hourly_rate)

    if args.json:
        print(json.dumps(asdict(snapshot), indent=2))
    else:
        print(render_dashboard(snapshot))

    if args.out:
        try:
            with open(args.out, "w") as f:
                json.dump(asdict(snapshot), f, indent=2)
            print(f"\n✓ Snapshot written: {args.out}")
        except OSError as e:
            sys.exit(f"Failed to write {args.out}: {e}")
    else:
        print(f"\n✓ Progress snapshot computed: {snapshot.scored} scored, "
              f"{snapshot.passed} passed")


if __name__ == "__main__":
    main()
