#!/usr/bin/env python3
"""Render a BY campaign status display from a checkpoint JSON file.

Reads a campaign_state.json checkpoint produced by by-campaign-manager and
prints the canonical BY status display: banner + phase table + score
distribution sparkline + recent events. Output follows the templates in
``references/output-format-spec.md``.

Inputs
------
--checkpoint PATH   Path to a campaign_state.json file.
--max-events N      Maximum number of recent events to show (default: 5).
--no-sparkline      Suppress the score distribution sparkline.

Outputs
-------
Markdown printed to stdout. No files are written.

Example
-------
    python3 render_campaign_status.py \\
      --checkpoint campaigns/anti-HER2/campaign_20260520_001/campaign_state.json

Expected checkpoint shape (minimum):
    {
      "campaign_id": "anti-HER2-20260520-001",
      "target": "HER2",
      "campaign_name": "anti-HER2",
      "phases": [
        {"name": "Research", "status": "complete", "time_seconds": 45,
         "details": "3 PDB, 12 prior art"},
        ...
      ],
      "scores": {"composite": [0.21, 0.35, ..., 0.87]},   # optional
      "events": [
        {"ts": "2026-05-20T14:32:00Z", "msg": "Design phase started"},
        ...
      ]                                                    # optional
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BANNER_WIDTH = 53
SCORE_BAR_BLOCKS = 10
SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"

STATUS_SYMBOL = {
    "complete": "✓ Complete",
    "active": "◆ Active  ",
    "in_progress": "◆ Active  ",
    "pending": "○ Pending ",
    "failed": "✗ Failed  ",
    "blocked": "✗ Blocked ",
}


def _format_time(seconds: float | int | None) -> str:
    """Render a duration as `45s`, `1m 15s`, `2h 03m`, or `—` if None."""
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"


def _status_cell(status: str | None) -> str:
    """Map a status string to the canonical symbol+label cell."""
    if not status:
        return "○ Pending "
    return STATUS_SYMBOL.get(status.lower(), f"? {status:<8}")


def _pad(text: str, width: int) -> str:
    """Left-aligned pad to width, truncate with ellipsis if too long."""
    if len(text) > width:
        return text[: max(0, width - 1)] + "…"
    return text.ljust(width)


def render_banner(campaign_name: str) -> str:
    """Render the campaign status banner."""
    rule = "━" * BANNER_WIDTH
    return f"{rule}\n BY ► CAMPAIGN: {campaign_name}\n{rule}"


def render_phase_table(phases: list[dict[str, Any]]) -> str:
    """Render the 4-column phase status table."""
    header = "| Phase       | Status     | Time   | Details                          |"
    sep = "|-------------|------------|--------|----------------------------------|"
    lines = [header, sep]
    for p in phases:
        name = _pad(str(p.get("name", "?")), 11)
        status = _status_cell(p.get("status"))
        time_cell = _pad(_format_time(p.get("time_seconds")), 6)
        details = _pad(str(p.get("details", "")), 32)
        lines.append(f"| {name} | {status} | {time_cell} | {details} |")
    return "\n".join(lines)


def render_sparkline(values: list[float]) -> str:
    """Render a score distribution as an 8-bucket sparkline."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        # All the same value — single block centered.
        bucket_counts = [0] * 8
        bucket_counts[4] = len(values)
    else:
        bucket_counts = [0] * 8
        for v in values:
            idx = int((v - lo) / (hi - lo) * 8)
            if idx == 8:
                idx = 7
            bucket_counts[idx] += 1
    peak = max(bucket_counts) or 1
    line = "".join(
        SPARKLINE_CHARS[int(c / peak * (len(SPARKLINE_CHARS) - 1))] if c else " "
        for c in bucket_counts
    )
    median = sorted(values)[len(values) // 2]
    return f"Composite distribution: {line}   (range {lo:.2f} - {hi:.2f}, median {median:.2f})"


def render_events(events: list[dict[str, Any]], limit: int) -> str:
    """Render the recent-events tail."""
    if not events:
        return ""
    recent = events[-limit:]
    lines = ["Recent events:"]
    for e in recent:
        ts = str(e.get("ts", "—"))
        msg = str(e.get("msg", ""))
        lines.append(f"  · {ts}  {msg}")
    return "\n".join(lines)


def render_status(
    checkpoint: dict[str, Any],
    max_events: int = 5,
    show_sparkline: bool = True,
) -> str:
    """Compose the full status display from a parsed checkpoint dict."""
    campaign_name = checkpoint.get("campaign_name") or checkpoint.get("campaign_id") or "?"
    phases = checkpoint.get("phases") or []
    parts = [render_banner(str(campaign_name)), "", render_phase_table(phases)]

    if show_sparkline:
        scores = ((checkpoint.get("scores") or {}).get("composite")) or []
        if scores:
            parts.append("")
            parts.append(render_sparkline(list(scores)))

    events = checkpoint.get("events") or []
    if events:
        parts.append("")
        parts.append(render_events(events, max_events))

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a BY campaign status display from a checkpoint JSON."
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        type=Path,
        help="Path to campaign_state.json checkpoint file.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum number of recent events to show (default: 5).",
    )
    parser.add_argument(
        "--no-sparkline",
        action="store_true",
        help="Suppress the score distribution sparkline.",
    )
    args = parser.parse_args()

    if not args.checkpoint.exists():
        print(
            f"✗ checkpoint not found: {args.checkpoint}",
            file=sys.stderr,
        )
        return 2

    try:
        checkpoint = json.loads(args.checkpoint.read_text())
    except json.JSONDecodeError as exc:
        print(f"✗ checkpoint is not valid JSON: {exc}", file=sys.stderr)
        return 3

    out = render_status(
        checkpoint,
        max_events=args.max_events,
        show_sparkline=not args.no_sparkline,
    )
    print(out)
    print()
    n_phases = len(checkpoint.get("phases") or [])
    print(
        f"✓ campaign status rendered: {n_phases} phases from {args.checkpoint}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
