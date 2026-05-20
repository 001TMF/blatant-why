#!/usr/bin/env python3
"""Runnable examples exercising common BY knowledge graph query patterns.

Purpose:
    Demonstrate the query patterns documented in references/query-patterns.md.
    Each example is self-contained and prints its results. Examples read from
    a JSON-backed knowledge store at one of:
        1. $KNOWLEDGE_DIR (explicit override)
        2. $BY_PROJECT_ROOT/.by/knowledge/
        3. ~/.by/knowledge/ (default)

Inputs:
    Reads campaigns.json and failures.json from the resolved knowledge dir.
    If neither file exists, examples print empty-result messages.

Outputs:
    Plain-text summaries printed to stdout. Eight examples total.

Example invocation:
    python3 knowledge_query_examples.py
    python3 knowledge_query_examples.py --example 3
    KNOWLEDGE_DIR=/tmp/test_knowledge python3 knowledge_query_examples.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Storage resolution (mirrors templates/.claude/mcp_servers/knowledge/server.py)
# ---------------------------------------------------------------------------


def resolve_knowledge_dir() -> Path:
    """Resolve the knowledge directory path using the same priority order as
    the MCP server.
    """
    env_dir = os.environ.get("KNOWLEDGE_DIR")
    if env_dir:
        return Path(env_dir)
    project_root = os.environ.get("BY_PROJECT_ROOT")
    if project_root:
        return Path(project_root) / ".by" / "knowledge"
    return Path(os.path.expanduser("~")) / ".by" / "knowledge"


def load_json(path: Path) -> list[dict]:
    """Load a JSON array from disk. Returns [] if file missing or empty."""
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"warning: could not load {path}: {exc}", file=sys.stderr)
    return []


def tokenize(text: str) -> set[str]:
    """Lowercase alphanumeric tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def keyword_score(query_tokens: set[str], doc_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def campaign_text(c: dict) -> str:
    parts = [c.get("target", ""), c.get("modality", ""), c.get("notes", "")]
    p = c.get("parameters", {})
    if isinstance(p, dict):
        parts.append(p.get("scaffold", ""))
        parts.extend(str(v) for v in p.values())
    o = c.get("outcomes", {})
    if isinstance(o, dict):
        parts.extend(str(v) for v in o.values())
    return " ".join(str(p) for p in parts if p)


# ---------------------------------------------------------------------------
# Example 1: Find similar past campaigns
# ---------------------------------------------------------------------------


def example_1_similar_campaigns(campaigns: list[dict]) -> None:
    print("\n=== Example 1: Find similar past campaigns ===")
    query = "TNF-alpha homotrimer cytokine autoimmune"
    modality_filter = "VHH"
    top_k = 5

    qt = tokenize(query)
    scored: list[tuple[float, dict]] = []
    for c in campaigns:
        if modality_filter and c.get("modality", "").lower() != modality_filter.lower():
            continue
        score = keyword_score(qt, tokenize(campaign_text(c)))
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)

    print(f"Query: {query!r} | modality={modality_filter} | top_k={top_k}")
    print(f"Found {len(scored)} matching {modality_filter} campaigns; showing top {top_k}:")
    for score, c in scored[:top_k]:
        outcomes = c.get("outcomes", {})
        print(
            f"  [{score:.2f}] {c.get('id', '?')[:24]} target={c.get('target', '?')} "
            f"hit_rate={outcomes.get('hit_rate', '?')} best_ipsae={outcomes.get('best_ipsae', '?')}"
        )
    print(f"✓ Example 1 completed: {len(scored[:top_k])} rows printed")


# ---------------------------------------------------------------------------
# Example 2: Designs above ipSAE threshold for a target
# ---------------------------------------------------------------------------


def example_2_designs_above_threshold(campaigns: list[dict]) -> None:
    print("\n=== Example 2: Designs above ipSAE threshold for target ===")
    target = "tnf-alpha"
    threshold = 0.70

    matching = [c for c in campaigns if c.get("target", "").lower() == target.lower()]
    designs_above: list[dict] = []
    for c in matching:
        for d in c.get("designs", []):
            if isinstance(d, dict) and d.get("ipsae", 0) > threshold:
                designs_above.append({**d, "_campaign_id": c.get("id", "?")})

    print(f"Target: {target} | ipSAE > {threshold}")
    print(f"Scanned {len(matching)} campaigns; found {len(designs_above)} designs")
    for d in designs_above[:10]:
        print(
            f"  {d.get('design_id', '?'):<20} ipsae={d.get('ipsae', '?')} "
            f"iptm={d.get('iptm', '?')} status={d.get('status', '?')} "
            f"(from {d['_campaign_id'][:16]})"
        )
    print(f"✓ Example 2 completed: {len(designs_above)} designs above threshold")


# ---------------------------------------------------------------------------
# Example 3: Failures for a target (warnings)
# ---------------------------------------------------------------------------


def example_3_failures_for_target(
    campaigns: list[dict], failures: list[dict]
) -> None:
    print("\n=== Example 3: Failures relevant to target ===")
    target = "tnf-alpha"
    modality = "VHH"
    qt = tokenize(f"{target} {modality}")

    warnings = []
    for f in failures:
        ft = tokenize(
            f"{f.get('target', '')} {f.get('description', '')} {f.get('root_cause', '')}"
        )
        score = keyword_score(qt, ft)
        if score > 0.2:
            warnings.append((score, f))
    warnings.sort(key=lambda x: x[0], reverse=True)

    print(f"Target: {target} | modality: {modality}")
    print(f"Scanned {len(failures)} failures; {len(warnings)} relevant (relevance > 0.2)")
    for score, f in warnings[:5]:
        print(
            f"  [{score:.2f}] {f.get('id', '?')[:24]} "
            f"campaign={f.get('campaign_id', '?')[:20]}"
        )
        print(f"        description: {f.get('description', '?')[:80]}")
        print(f"        root_cause:  {f.get('root_cause', '?')[:80]}")
    print(f"✓ Example 3 completed: {len(warnings[:5])} warnings shown")


# ---------------------------------------------------------------------------
# Example 4: Scaffold rankings for a target class
# ---------------------------------------------------------------------------


def example_4_scaffold_rankings(campaigns: list[dict]) -> None:
    print("\n=== Example 4: Scaffold rankings for target class ===")
    target_class = "cytokine"
    tl = target_class.lower()

    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"hit_rates": [], "ipsae": [], "count": 0}
    )
    for c in campaigns:
        if tl not in c.get("target", "").lower():
            continue
        params = c.get("parameters", {}) if isinstance(c.get("parameters"), dict) else {}
        scaffold = params.get("scaffold", "unknown")
        stats[scaffold]["count"] += 1
        outcomes = c.get("outcomes", {})
        if outcomes.get("hit_rate") is not None:
            try:
                stats[scaffold]["hit_rates"].append(float(outcomes["hit_rate"]))
            except (ValueError, TypeError):
                pass
        if outcomes.get("best_ipsae") is not None:
            try:
                stats[scaffold]["ipsae"].append(float(outcomes["best_ipsae"]))
            except (ValueError, TypeError):
                pass

    rankings = []
    for s, st in stats.items():
        avg_h = sum(st["hit_rates"]) / len(st["hit_rates"]) if st["hit_rates"] else 0
        avg_i = sum(st["ipsae"]) / len(st["ipsae"]) if st["ipsae"] else 0
        rankings.append((s, st["count"], avg_h, avg_i))
    rankings.sort(key=lambda x: (x[2], x[3]), reverse=True)

    print(f"Target class: {target_class}")
    print(f"{'scaffold':<20} {'campaigns':<12} {'avg_hit':<10} {'avg_ipsae':<10}")
    for s, n, h, i in rankings[:10]:
        print(f"  {s:<18} {n:<12} {h:<10.3f} {i:<10.3f}")
    print(f"✓ Example 4 completed: {len(rankings)} scaffolds ranked")


# ---------------------------------------------------------------------------
# Example 5: Pre-campaign recommendation bundle
# ---------------------------------------------------------------------------


def example_5_recommendation_bundle(
    campaigns: list[dict], failures: list[dict]
) -> None:
    print("\n=== Example 5: Pre-campaign recommendation bundle ===")
    target = "tnf-alpha"
    modality = "VHH"
    qt = tokenize(f"{target} {modality}")

    scored = sorted(
        ((keyword_score(qt, tokenize(campaign_text(c))), c) for c in campaigns),
        key=lambda x: x[0],
        reverse=True,
    )
    similar = scored[:5]

    suggested_params: dict = {}
    if similar:
        params = similar[0][1].get("parameters", {})
        if isinstance(params, dict):
            suggested_params = params

    warn_count = 0
    for f in failures:
        ft = tokenize(
            f"{f.get('target', '')} {f.get('description', '')} {f.get('root_cause', '')}"
        )
        if keyword_score(qt, ft) > 0.2:
            warn_count += 1

    print(f"Target: {target} | modality: {modality}")
    print(f"  similar_campaigns: {len(similar)}")
    print(f"  warnings: {warn_count}")
    print(f"  suggested_parameters: {json.dumps(suggested_params, indent=2)[:200]}")
    print("✓ Example 5 completed: bundle summarized")


# ---------------------------------------------------------------------------
# Example 6: Browse recent entries
# ---------------------------------------------------------------------------


def example_6_recent_entries(campaigns: list[dict]) -> None:
    print("\n=== Example 6: Recent entries ===")
    recent = sorted(campaigns, key=lambda x: x.get("stored_at", 0), reverse=True)
    print(f"Showing 10 most recently stored campaigns (of {len(campaigns)}):")
    for c in recent[:10]:
        print(
            f"  {c.get('id', '?')[:24]:<24} "
            f"target={c.get('target', '?'):<20} "
            f"modality={c.get('modality', '?'):<10} "
            f"stored_at={c.get('stored_at', 0):.0f}"
        )
    print(f"✓ Example 6 completed: {len(recent[:10])} rows printed")


# ---------------------------------------------------------------------------
# Example 7: Cross-target scaffold comparison
# ---------------------------------------------------------------------------


def example_7_cross_target_scaffolds(campaigns: list[dict]) -> None:
    print("\n=== Example 7: Cross-target scaffold comparison ===")
    classes = ["cytokine", "receptor", "enzyme", "viral"]
    breadth: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for cls in classes:
        cl = cls.lower()
        stats: dict[str, list[float]] = defaultdict(list)
        for c in campaigns:
            if cl not in c.get("target", "").lower():
                continue
            params = c.get("parameters", {}) if isinstance(c.get("parameters"), dict) else {}
            scaffold = params.get("scaffold", "unknown")
            hr = c.get("outcomes", {}).get("hit_rate")
            if hr is not None:
                try:
                    stats[scaffold].append(float(hr))
                except (ValueError, TypeError):
                    pass
        for s, hrs in stats.items():
            if hrs:
                breadth[s].append((cls, sum(hrs) / len(hrs)))

    print(f"Classes scanned: {classes}")
    print(f"Scaffolds appearing across multiple classes:")
    for scaffold, appearances in sorted(
        breadth.items(), key=lambda x: -len(x[1])
    )[:10]:
        if len(appearances) > 1:
            summary = ", ".join(f"{cls}={hr:.2f}" for cls, hr in appearances)
            print(f"  {scaffold:<20} -> {summary}")
    print(f"✓ Example 7 completed: {len(breadth)} scaffolds analyzed")


# ---------------------------------------------------------------------------
# Example 8: Failure pattern clustering
# ---------------------------------------------------------------------------


def example_8_failure_clustering(failures: list[dict]) -> None:
    print("\n=== Example 8: Failure pattern clustering ===")
    if not failures:
        print("No failures to cluster.")
        print("✓ Example 8 completed: 0 clusters")
        return

    # Simple keyword clustering: group failures by shared keywords in description.
    keywords_per_failure = [
        (f, tokenize(f.get("description", "") + " " + f.get("root_cause", "")))
        for f in failures
    ]
    clusters: list[list[dict]] = []
    used: set[int] = set()
    for i, (fi, ki) in enumerate(keywords_per_failure):
        if i in used:
            continue
        cluster = [fi]
        used.add(i)
        for j in range(i + 1, len(keywords_per_failure)):
            if j in used:
                continue
            fj, kj = keywords_per_failure[j]
            # Cluster if Jaccard similarity > 0.3
            if ki and kj:
                jaccard = len(ki & kj) / len(ki | kj)
                if jaccard > 0.3:
                    cluster.append(fj)
                    used.add(j)
        clusters.append(cluster)

    print(f"Found {len(clusters)} clusters from {len(failures)} failures")
    for i, cluster in enumerate(clusters[:5]):
        rep = cluster[0]
        print(
            f"  cluster {i+1} ({len(cluster)} failure(s)): "
            f"{rep.get('description', '?')[:80]}"
        )
    print(f"✓ Example 8 completed: {len(clusters)} clusters identified")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Runnable examples of BY knowledge graph query patterns.",
    )
    parser.add_argument(
        "--example",
        type=int,
        help="Run only the specified example (1-8). Default: run all.",
    )
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default=None,
        help="Override knowledge directory (default: env var resolution).",
    )
    args = parser.parse_args()

    if args.knowledge_dir:
        knowledge_dir = Path(args.knowledge_dir)
    else:
        knowledge_dir = resolve_knowledge_dir()

    campaigns_path = knowledge_dir / "campaigns.json"
    failures_path = knowledge_dir / "failures.json"

    print(f"Knowledge directory: {knowledge_dir}")
    print(f"  campaigns.json exists: {campaigns_path.exists()}")
    print(f"  failures.json exists:  {failures_path.exists()}")

    campaigns = load_json(campaigns_path)
    failures = load_json(failures_path)
    print(f"  loaded {len(campaigns)} campaigns, {len(failures)} failures")

    examples = {
        1: lambda: example_1_similar_campaigns(campaigns),
        2: lambda: example_2_designs_above_threshold(campaigns),
        3: lambda: example_3_failures_for_target(campaigns, failures),
        4: lambda: example_4_scaffold_rankings(campaigns),
        5: lambda: example_5_recommendation_bundle(campaigns, failures),
        6: lambda: example_6_recent_entries(campaigns),
        7: lambda: example_7_cross_target_scaffolds(campaigns),
        8: lambda: example_8_failure_clustering(failures),
    }

    if args.example:
        if args.example not in examples:
            sys.exit(f"Unknown example: {args.example}. Choose 1-8.")
        examples[args.example]()
    else:
        for i in sorted(examples):
            examples[i]()

    print("\n✓ All examples completed.")


if __name__ == "__main__":
    main()
