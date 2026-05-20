#!/usr/bin/env python3
"""Summarize an 8-phase BY research checkpoint into a one-page markdown digest.

Purpose
-------
Reads the JSON outputs produced by the by-research skill's 8-phase pipeline and
emits a compact markdown summary suitable for embedding in `campaign_plan.md` or
sharing with a reviewer. The summary picks the headline target facts, top
sources, validated findings by confidence, critique status, and final design
recommendation.

Inputs
------
A campaign research directory containing any subset of:
  - scope.json
  - research_plan.json
  - sources.json
  - validated_findings.json
  - critique.json
  - design_recommendation.json
  - recommended_hotspots.json
  - research_progress.json

Outputs
-------
A markdown file (default: <research_dir>/research_summary.md) printed to stdout
if --stdout is passed.

Example invocation
------------------
  python3 summarize_research.py \\
      --research-dir campaigns/tnf_alpha/campaign_20260520_001/research \\
      --out campaigns/tnf_alpha/campaign_20260520_001/research/research_summary.md

  python3 summarize_research.py --research-dir ./research --stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PHASE_FILES: dict[str, str] = {
    "scope": "scope.json",
    "research_plan": "research_plan.json",
    "sources": "sources.json",
    "validated_findings": "validated_findings.json",
    "critique": "critique.json",
    "design_recommendation": "design_recommendation.json",
    "recommended_hotspots": "recommended_hotspots.json",
    "research_progress": "research_progress.json",
}


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning None if it does not exist."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"WARNING: could not parse {path}: {exc}", file=sys.stderr)
        return None


def load_research_dir(research_dir: Path) -> dict[str, dict[str, Any] | None]:
    """Load every known phase output from the research directory."""
    return {
        key: load_json_if_exists(research_dir / filename)
        for key, filename in PHASE_FILES.items()
    }


def fmt_scope(scope: dict[str, Any] | None) -> str:
    """Format the scope section."""
    if not scope:
        return "_(scope.json not found)_"
    lines = [
        f"- **Target:** {scope.get('target_name', 'UNKNOWN')}",
        f"- **Organism:** {scope.get('organism', 'unspecified')}",
        f"- **UniProt:** {scope.get('uniprot_accession', 'not yet retrieved')}",
        f"- **Modality preference:** {scope.get('modality_preference', 'unspecified')}",
        f"- **Research depth:** {scope.get('research_depth', 'unspecified')}",
        f"- **Therapeutic area:** {scope.get('therapeutic_area', 'unspecified')}",
    ]
    return "\n".join(lines)


def fmt_sources(sources: dict[str, Any] | None) -> str:
    """Format the sources section with credibility counts."""
    if not sources:
        return "_(sources.json not found)_"
    source_list = sources.get("sources", sources if isinstance(sources, list) else [])
    if isinstance(source_list, dict):
        source_list = list(source_list.values())
    n_total = len(source_list)
    type_counts: Counter[str] = Counter(s.get("type", "unknown") for s in source_list)
    top_types = ", ".join(f"{t}={n}" for t, n in type_counts.most_common(5))
    lines = [
        f"- **Total sources:** {n_total}",
        f"- **Type breakdown:** {top_types or 'none'}",
    ]
    # Top 5 by credibility
    ranked = sorted(
        source_list,
        key=lambda s: s.get("credibility", 0.0),
        reverse=True,
    )[:5]
    if ranked:
        lines.append("- **Top sources:**")
        for src in ranked:
            sid = src.get("id", "?")
            cred = src.get("credibility", 0.0)
            ident = src.get("identifier", "")
            title = (src.get("title", "") or "")[:80]
            lines.append(f"  - `{sid}` ({cred:.2f}) {ident} — {title}")
    return "\n".join(lines)


def fmt_findings(findings: dict[str, Any] | None) -> str:
    """Format validated findings with confidence breakdown."""
    if not findings:
        return "_(validated_findings.json not found)_"
    finding_list = findings.get("findings", [])
    conf_counts: Counter[str] = Counter(
        f.get("confidence", "UNKNOWN") for f in finding_list
    )
    lines = [
        f"- **Total findings:** {len(finding_list)}",
        f"- **HIGH:** {conf_counts.get('HIGH', 0)}",
        f"- **MEDIUM:** {conf_counts.get('MEDIUM', 0)}",
        f"- **LOW:** {conf_counts.get('LOW', 0)}",
        f"- **CONTRADICTED:** {conf_counts.get('CONTRADICTED', 0)}",
    ]
    high_findings = [f for f in finding_list if f.get("confidence") == "HIGH"]
    if high_findings:
        lines.append("- **HIGH confidence claims:**")
        for f in high_findings[:5]:
            claim = (f.get("claim", "") or "")[:120]
            srcs = ", ".join(f.get("supporting_sources", []))
            lines.append(f"  - {claim} [{srcs}]")
    return "\n".join(lines)


def fmt_critique(critique: dict[str, Any] | None) -> str:
    """Format the critique section by severity."""
    if not critique:
        return "_(critique.json not found)_"
    concerns = critique.get("concerns", [])
    severity_counts: Counter[str] = Counter(
        c.get("severity", "UNKNOWN") for c in concerns
    )
    lines = [
        f"- **Total concerns:** {len(concerns)}",
        f"- **CRITICAL:** {severity_counts.get('CRITICAL', 0)}",
        f"- **HIGH:** {severity_counts.get('HIGH', 0)}",
        f"- **MEDIUM:** {severity_counts.get('MEDIUM', 0)}",
        f"- **LOW:** {severity_counts.get('LOW', 0)}",
    ]
    critical = [c for c in concerns if c.get("severity") == "CRITICAL"]
    if critical:
        lines.append("- **CRITICAL concerns:**")
        for c in critical:
            persona = c.get("persona", "?")
            txt = (c.get("concern", "") or "")[:120]
            lines.append(f"  - [{persona}] {txt}")
    return "\n".join(lines)


def fmt_recommendation(rec: dict[str, Any] | None) -> str:
    """Format the design recommendation."""
    if not rec:
        return "_(design_recommendation.json not found)_"
    scaffolds = rec.get("scaffolds", [])
    lines = [
        f"- **Modality:** {rec.get('modality', 'unspecified')}",
        f"- **Protocol:** {rec.get('protocol', 'unspecified')}",
        f"- **Tier:** {rec.get('tier', 'unspecified')}",
        f"- **Scaffolds:** {', '.join(scaffolds) if scaffolds else 'none'}",
        f"- **Designs per scaffold:** {rec.get('num_designs_per_scaffold', '?')}",
        f"- **Budget (USD):** {rec.get('budget', '?')}",
        f"- **Estimated pass rate:** {rec.get('estimated_hit_rate', '?')}",
        f"- **Estimated time (hours):** {rec.get('estimated_time_hours', '?')}",
    ]
    rationale = rec.get("rationale", "")
    if rationale:
        lines.append(f"- **Rationale:** {rationale[:200]}")
    return "\n".join(lines)


def fmt_hotspots(hotspots: dict[str, Any] | None) -> str:
    """Format the hotspot residue list."""
    if not hotspots:
        return "_(recommended_hotspots.json not found)_"
    rng = hotspots.get("range_notation", "")
    residues = hotspots.get("hotspots", [])
    lines = [
        f"- **Range notation:** `{rng}`" if rng else "- **Range notation:** _(missing)_",
        f"- **Residue count:** {len(residues)}",
    ]
    if residues:
        sample = residues[:8]
        sample_strs = [
            f"{r.get('aa', '?')}{r.get('residue', '?')}({r.get('confidence', '?')})"
            for r in sample
        ]
        lines.append(f"- **Residues:** {', '.join(sample_strs)}")
    return "\n".join(lines)


def fmt_progress(progress: dict[str, Any] | None) -> str:
    """Format the pipeline progress / audit."""
    if not progress:
        return "_(research_progress.json not found)_"
    completed = progress.get("completed_phases", [])
    lines = [
        f"- **Completed phases:** {completed}",
        f"- **Current phase:** {progress.get('current_phase', '?')}",
        f"- **Iterations through retrieval:** {progress.get('iteration_count', 0)}",
        f"- **Started:** {progress.get('started_at', '?')}",
        f"- **Last checkpoint:** {progress.get('last_checkpoint', '?')}",
    ]
    gates = progress.get("quality_gate_status", {})
    if gates:
        gate_strs = [f"{k}={v}" for k, v in gates.items()]
        lines.append(f"- **Gate status:** {', '.join(gate_strs)}")
    return "\n".join(lines)


def build_summary(data: dict[str, dict[str, Any] | None]) -> str:
    """Build the one-page markdown summary from loaded JSON outputs."""
    scope = data["scope"] or {}
    target = scope.get("target_name", "UNKNOWN_TARGET")
    sections = [
        f"# Research Summary: {target}",
        "",
        "_Generated by `summarize_research.py` — one-page digest of the 8-phase pipeline outputs._",
        "",
        "## Scope (Phase 1)",
        fmt_scope(data["scope"]),
        "",
        "## Sources (Phase 3)",
        fmt_sources(data["sources"]),
        "",
        "## Validated Findings (Phase 4)",
        fmt_findings(data["validated_findings"]),
        "",
        "## Critique (Phase 6)",
        fmt_critique(data["critique"]),
        "",
        "## Hotspots (Phase 8)",
        fmt_hotspots(data["recommended_hotspots"]),
        "",
        "## Design Recommendation (Phase 8)",
        fmt_recommendation(data["design_recommendation"]),
        "",
        "## Pipeline Audit",
        fmt_progress(data["research_progress"]),
        "",
    ]
    return "\n".join(sections)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Summarize a BY research checkpoint into a one-page markdown digest "
            "suitable for inclusion in campaign_plan.md."
        ),
    )
    parser.add_argument(
        "--research-dir",
        required=True,
        type=Path,
        help="Path to the campaign research directory (contains scope.json etc).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output markdown file path. Defaults to "
            "<research-dir>/research_summary.md. Ignored if --stdout is set."
        ),
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print summary to stdout instead of writing to a file.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    research_dir: Path = args.research_dir.resolve()
    if not research_dir.exists() or not research_dir.is_dir():
        sys.exit(f"ERROR: research directory not found: {research_dir}")

    data = load_research_dir(research_dir)
    summary = build_summary(data)

    if args.stdout:
        print(summary)
        n_loaded = sum(1 for v in data.values() if v is not None)
        print(
            f"✓ research summary generated: {n_loaded}/{len(PHASE_FILES)} phase outputs found",
            file=sys.stderr,
        )
        return

    out_path: Path = args.out or (research_dir / "research_summary.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary, encoding="utf-8")
    n_loaded = sum(1 for v in data.values() if v is not None)
    print(
        f"✓ research summary written: {out_path} "
        f"({n_loaded}/{len(PHASE_FILES)} phase outputs found)"
    )


if __name__ == "__main__":
    main()
