#!/usr/bin/env python3
"""Generate a campaign-ready markdown screening report.

Reads a screened CSV (output of `screen_batch.py`) and produces a
markdown report suitable for inclusion in the campaign summary. The report
includes PASS rate, distribution statistics for each metric, the top failed
criteria (reason-code counts), and the top-N PASS candidates ranked by
composite score.

Inputs:
  - --screened: path to the CSV produced by screen_batch.py
  - --output: path to the markdown report to write
  - --top-n: how many top PASS designs to include in the table (default 10)

Outputs:
  - Markdown report file at the requested path

Example:
  python generate_screening_report.py \\
    --screened screened.csv \\
    --output screening_report.md \\
    --top-n 10
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Row:
    """Parsed screened-CSV row with typed fields."""

    name: str
    verdict: str
    reason_codes: list[str]
    iptm: float
    plddt: float
    rmsd_ca: float
    ipsae_min: float
    liability_count: int
    weighted_liability_count: int
    net_charge: float
    hydrophobic_fraction: float
    total_cdr_length: int
    composite_score: float


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_screened(path: Path) -> list[Row]:
    """Read the screened CSV into typed Row records."""
    rows: list[Row] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            codes = r.get("reason_codes", "") or ""
            rows.append(
                Row(
                    name=r.get("name", ""),
                    verdict=r.get("verdict", ""),
                    reason_codes=[c for c in codes.split(";") if c],
                    iptm=_to_float(r.get("iptm")),
                    plddt=_to_float(r.get("plddt")),
                    rmsd_ca=_to_float(r.get("rmsd_ca")),
                    ipsae_min=_to_float(r.get("ipsae_min")),
                    liability_count=_to_int(r.get("liability_count")),
                    weighted_liability_count=_to_int(r.get("weighted_liability_count")),
                    net_charge=_to_float(r.get("net_charge")),
                    hydrophobic_fraction=_to_float(r.get("hydrophobic_fraction")),
                    total_cdr_length=_to_int(r.get("total_cdr_length")),
                    composite_score=_to_float(r.get("composite_score")),
                )
            )
    return rows


def _summarize(values: list[float]) -> tuple[float, float, float, float, float]:
    """Return min, p25, median, p75, max."""
    if not values:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    sorted_values = sorted(values)
    n = len(sorted_values)
    return (
        sorted_values[0],
        sorted_values[max(0, n // 4 - 1)],
        statistics.median(sorted_values),
        sorted_values[min(n - 1, (3 * n) // 4)],
        sorted_values[-1],
    )


def _distribution_table(rows: list[Row]) -> str:
    """Build the markdown distribution-summary table."""
    headers = ["Metric", "min", "p25", "median", "p75", "max"]
    metrics = [
        ("ipTM", [r.iptm for r in rows]),
        ("pLDDT", [r.plddt for r in rows]),
        ("CA-RMSD", [r.rmsd_ca for r in rows]),
        ("ipSAE_min", [r.ipsae_min for r in rows]),
        ("net_charge", [r.net_charge for r in rows]),
        ("hydro_frac", [r.hydrophobic_fraction for r in rows]),
        ("composite", [r.composite_score for r in rows]),
    ]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for name, vals in metrics:
        mn, p25, med, p75, mx = _summarize(vals)
        lines.append(
            f"| {name} | {mn:.3f} | {p25:.3f} | {med:.3f} | {p75:.3f} | {mx:.3f} |"
        )
    return "\n".join(lines)


def _reason_table(rows: list[Row]) -> str:
    """Counts of each reason code across FAIL designs."""
    counter: Counter[str] = Counter()
    for r in rows:
        for c in r.reason_codes:
            counter[c] += 1
    if not counter:
        return "_No failure reason codes recorded._"
    lines = ["| Reason Code | Count | % of FAIL |"]
    lines.append("|---|---|---|")
    n_fail = sum(1 for r in rows if r.verdict == "FAIL") or 1
    for code, count in counter.most_common():
        pct = 100.0 * count / n_fail
        lines.append(f"| `{code}` | {count} | {pct:.1f}% |")
    return "\n".join(lines)


def _top_n_table(rows: list[Row], top_n: int) -> str:
    """Top-N PASS designs ranked by composite_score."""
    passing = [r for r in rows if r.verdict == "PASS"]
    passing.sort(key=lambda r: r.composite_score, reverse=True)
    selected = passing[:top_n]
    if not selected:
        return "_No PASS designs to report._"
    lines = [
        "| Rank | Name | composite | ipSAE_min | ipTM | pLDDT | RMSD | liab | charge | hydro |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(selected, start=1):
        lines.append(
            f"| {i} | {r.name} | {r.composite_score:.3f} | {r.ipsae_min:.3f} | "
            f"{r.iptm:.3f} | {r.plddt:.1f} | {r.rmsd_ca:.2f} | "
            f"{r.weighted_liability_count} | {r.net_charge:+.2f} | "
            f"{r.hydrophobic_fraction:.2f} |"
        )
    return "\n".join(lines)


def build_report(rows: list[Row], top_n: int, screened_path: Path) -> str:
    """Assemble the full markdown report."""
    n = len(rows)
    n_pass = sum(1 for r in rows if r.verdict == "PASS")
    n_marg = sum(1 for r in rows if r.verdict == "MARGINAL")
    n_fail = sum(1 for r in rows if r.verdict == "FAIL")
    pct_pass = (n_pass / n * 100) if n else 0.0

    parts: list[str] = []
    parts.append("# Screening Report\n")
    parts.append(f"Source: `{screened_path}`\n")
    parts.append("## Summary\n")
    parts.append(
        f"- Total designs: **{n}**\n"
        f"- PASS: **{n_pass}** ({pct_pass:.1f}%)\n"
        f"- MARGINAL: **{n_marg}**\n"
        f"- FAIL: **{n_fail}**\n"
    )
    parts.append("## Metric Distributions\n")
    parts.append(_distribution_table(rows))
    parts.append("\n## Top Failure Reasons\n")
    parts.append(_reason_table(rows))
    parts.append(f"\n## Top {top_n} PASS Candidates (by composite score)\n")
    parts.append(_top_n_table(rows, top_n))
    parts.append("\n---\n")
    parts.append(
        "_Report generated by `by-screening` skill. "
        "For interpretation of thresholds, see `references/filter-thresholds.md`._\n"
    )
    return "\n".join(parts)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--screened", required=True, type=Path, help="Screened CSV input")
    parser.add_argument("--output", required=True, type=Path, help="Markdown report path")
    parser.add_argument("--top-n", type=int, default=10, help="Top-N PASS designs to include")
    args = parser.parse_args()

    if not args.screened.exists():
        sys.exit(f"Input file not found: {args.screened}")

    rows = load_screened(args.screened)
    report = build_report(rows, args.top_n, args.screened)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)

    n_pass = sum(1 for r in rows if r.verdict == "PASS")
    pct = (n_pass / len(rows) * 100) if rows else 0.0
    top_reason = ""
    counter: Counter[str] = Counter()
    for r in rows:
        for c in r.reason_codes:
            counter[c] += 1
    if counter:
        top_reason = f", top reason: {counter.most_common(1)[0][0]}"
    print(
        f"✓ report written: {args.output} (PASS rate {pct:.1f}%{top_reason})"
    )


if __name__ == "__main__":
    main()
