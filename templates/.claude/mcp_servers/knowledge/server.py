#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///
"""BY Knowledge MCP Server — campaign learning with lightweight JSON storage.

Stores campaign outcomes, failures, and scaffold rankings as JSON files in
the knowledge directory. Uses keyword matching for similarity queries. Zero
heavy dependencies — starts in under 1 second.

Knowledge directory resolution (in priority order):
1. KNOWLEDGE_DIR environment variable
2. .by/knowledge/ relative to BY_PROJECT_ROOT env var
3. ~/.by/knowledge/ (home directory fallback)
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("by-knowledge")

# ---------------------------------------------------------------------------
# Knowledge directory resolution
# ---------------------------------------------------------------------------


def _resolve_knowledge_dir() -> Path:
    """Resolve the knowledge directory path.

    Priority:
    1. KNOWLEDGE_DIR env var (explicit override)
    2. BY_PROJECT_ROOT/.by/knowledge/ (project-local)
    3. ~/.by/knowledge/ (home directory fallback)
    """
    env_dir = os.environ.get("KNOWLEDGE_DIR")
    if env_dir:
        return Path(env_dir)

    project_root = os.environ.get("BY_PROJECT_ROOT")
    if project_root:
        return Path(project_root) / ".by" / "knowledge"

    return Path(os.path.expanduser("~")) / ".by" / "knowledge"


KNOWLEDGE_DIR = _resolve_knowledge_dir()

CAMPAIGNS_FILE = KNOWLEDGE_DIR / "campaigns.json"
FAILURES_FILE = KNOWLEDGE_DIR / "failures.json"


# ---------------------------------------------------------------------------
# JSON-backed storage layer
# ---------------------------------------------------------------------------


def _ensure_dir() -> None:
    """Create the knowledge directory if it doesn't exist."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> list[dict]:
    """Load a JSON list from disk. Returns [] if file doesn't exist or is empty."""
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_json(path: Path, data: list[dict]) -> None:
    """Atomically write JSON data to disk (write to .tmp, then rename)."""
    _ensure_dir()
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    tmp_path.rename(path)


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


# ---------------------------------------------------------------------------
# Keyword matching (replaces vector search)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Extract lowercase keyword tokens from text."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _keyword_score(query_tokens: set[str], doc_tokens: set[str]) -> float:
    """Score = count of matching keywords / total query keywords."""
    if not query_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    return len(overlap) / len(query_tokens)


def _campaign_text(campaign: dict) -> str:
    """Build searchable text from a campaign record."""
    parts = [
        campaign.get("target", ""),
        campaign.get("modality", ""),
        campaign.get("notes", ""),
    ]
    params = campaign.get("parameters", {})
    if isinstance(params, dict):
        parts.append(params.get("scaffold", ""))
        parts.extend(str(v) for v in params.values())
    outcomes = campaign.get("outcomes", {})
    if isinstance(outcomes, dict):
        parts.extend(str(v) for v in outcomes.values())
    return " ".join(str(p) for p in parts if p)


# ---------------------------------------------------------------------------
# Tool 1: knowledge_store_campaign
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_store_campaign(
    target: str,
    modality: str,
    parameters: dict[str, Any],
    outcomes: dict[str, Any],
    notes: str = "",
    designs: list[dict[str, Any]] | None = None,
) -> str:
    """Store a completed campaign outcome in the knowledge base.

    Embeds a text summary for semantic search and stores full data as metadata.

    Args:
        target: Target name or description.
        modality: Design modality (e.g. antibody, nanobody, binder).
        parameters: Campaign parameters (scaffold, seeds, temperature, etc.).
        outcomes: Campaign outcomes with keys: hit_rate, best_ipsae, best_iptm,
            screening_pass_rate.
        notes: Free-text notes about the campaign.
        designs: Optional per-design provenance array. Each entry should include:
            design_id, job_id, scaffold, epitope, tool, ipsae, iptm, status.

    Returns:
        JSON with status, id, document summary, and metadata.
    """
    if not target:
        return _error("target is required")
    if not modality:
        return _error("modality is required")

    doc_id = f"campaign_{uuid.uuid4().hex[:12]}"
    now = time.time()

    record: dict[str, Any] = {
        "id": doc_id,
        "target": target,
        "modality": modality,
        "parameters": parameters,
        "outcomes": outcomes,
        "notes": notes,
        "stored_at": now,
        "access_count": 0,
    }

    # Store per-design provenance if provided
    if designs is not None:
        record["designs"] = designs

    campaigns = _load_json(CAMPAIGNS_FILE)
    campaigns.append(record)
    _save_json(CAMPAIGNS_FILE, campaigns)

    # Build summary text for the response.
    summary_parts = [f"Campaign targeting {target} using {modality} modality."]
    if parameters.get("scaffold"):
        summary_parts.append(f"Scaffold: {parameters['scaffold']}.")
    if outcomes.get("hit_rate") is not None:
        summary_parts.append(f"Hit rate: {outcomes['hit_rate']}.")
    if outcomes.get("best_ipsae") is not None:
        summary_parts.append(f"Best ipSAE: {outcomes['best_ipsae']}.")
    if outcomes.get("best_iptm") is not None:
        summary_parts.append(f"Best ipTM: {outcomes['best_iptm']}.")
    if notes:
        summary_parts.append(notes)
    if designs:
        summary_parts.append(f"{len(designs)} designs with provenance recorded.")

    return json.dumps(
        {
            "status": "stored",
            "id": doc_id,
            "document": " ".join(summary_parts),
            "metadata": {
                "target": target,
                "modality": modality,
                "parameters": parameters,
                "outcomes": outcomes,
                "notes": notes,
                "designs_count": len(designs) if designs else 0,
                "stored_at": now,
                "access_count": 0,
            },
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 2: knowledge_query_similar
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_query_similar(
    target_description: str,
    modality: str | None = None,
    top_k: int = 5,
) -> str:
    """Find similar past campaigns using keyword search with MMR diversity re-ranking.

    Args:
        target_description: Description of the target to search for.
        modality: Optional modality filter (e.g. antibody, nanobody).
        top_k: Number of results to return (default 5).

    Returns:
        JSON with results list and query string.
    """
    if not target_description:
        return _error("target_description is required")

    campaigns = _load_json(CAMPAIGNS_FILE)

    if not campaigns:
        return json.dumps({
            "results": [],
            "query": target_description,
            "message": "No prior campaigns recorded. Run campaigns and store outcomes to build knowledge.",
        })

    query_tokens = _tokenize(target_description)

    scored: list[tuple[float, dict]] = []
    for campaign in campaigns:
        # Optional modality filter.
        if modality and campaign.get("modality", "").lower() != modality.lower():
            continue
        doc_text = _campaign_text(campaign)
        doc_tokens = _tokenize(doc_text)
        score = _keyword_score(query_tokens, doc_tokens)
        scored.append((score, campaign))

    # Sort by score descending.
    scored.sort(key=lambda x: x[0], reverse=True)

    # Take top_k results.
    results = []
    for score, campaign in scored[:top_k]:
        # Increment access count.
        campaign["access_count"] = campaign.get("access_count", 0) + 1

        results.append({
            "id": campaign.get("id", ""),
            "similarity": round(score, 4),
            "document": _campaign_text(campaign),
            "metadata": {
                "target": campaign.get("target", ""),
                "modality": campaign.get("modality", ""),
                "parameters": campaign.get("parameters", {}),
                "outcomes": campaign.get("outcomes", {}),
                "notes": campaign.get("notes", ""),
                "designs_count": len(campaign.get("designs", [])),
                "stored_at": campaign.get("stored_at", 0),
                "access_count": campaign.get("access_count", 0),
            },
        })

    # Persist updated access counts.
    if results:
        _save_json(CAMPAIGNS_FILE, campaigns)

    return json.dumps({"results": results, "query": target_description}, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: knowledge_scaffold_rankings
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_scaffold_rankings(target_class: str) -> str:
    """Get best-performing scaffolds for a target class.

    Ranked by average hit rate and average ipSAE across past campaigns.

    Args:
        target_class: Target class (e.g. "immune checkpoint", "cytokine").

    Returns:
        JSON with rankings list and target_class.
    """
    if not target_class:
        return _error("target_class is required")

    campaigns = _load_json(CAMPAIGNS_FILE)

    if not campaigns:
        return json.dumps({
            "rankings": [],
            "target_class": target_class,
            "message": "No scaffold data available yet.",
        })

    target_lower = target_class.lower()

    # Filter campaigns whose target field contains the target_class substring.
    scaffold_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"hit_rates": [], "ipsae_scores": [], "campaign_count": 0}
    )

    for campaign in campaigns:
        if target_lower not in campaign.get("target", "").lower():
            continue

        params = campaign.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, ValueError):
                params = {}

        outcomes = campaign.get("outcomes", {})
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, ValueError):
                outcomes = {}

        scaffold = params.get("scaffold", "unknown")
        scaffold_stats[scaffold]["campaign_count"] += 1

        hit_rate = outcomes.get("hit_rate")
        if hit_rate is not None:
            try:
                scaffold_stats[scaffold]["hit_rates"].append(float(hit_rate))
            except (ValueError, TypeError):
                pass

        best_ipsae = outcomes.get("best_ipsae")
        if best_ipsae is not None:
            try:
                scaffold_stats[scaffold]["ipsae_scores"].append(float(best_ipsae))
            except (ValueError, TypeError):
                pass

    # Build ranked output.
    rankings = []
    for scaffold, stats in scaffold_stats.items():
        entry: dict = {"scaffold": scaffold, "campaign_count": stats["campaign_count"]}
        if stats["hit_rates"]:
            entry["avg_hit_rate"] = round(
                sum(stats["hit_rates"]) / len(stats["hit_rates"]), 4
            )
        if stats["ipsae_scores"]:
            entry["avg_ipsae"] = round(
                sum(stats["ipsae_scores"]) / len(stats["ipsae_scores"]), 4
            )
        rankings.append(entry)

    # Sort by avg hit rate descending, then avg ipSAE descending.
    rankings.sort(
        key=lambda x: (x.get("avg_hit_rate", 0), x.get("avg_ipsae", 0)),
        reverse=True,
    )

    return json.dumps({"rankings": rankings, "target_class": target_class}, indent=2)


# ---------------------------------------------------------------------------
# Tool 4: knowledge_store_failure
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_store_failure(
    campaign_id: str,
    description: str,
    root_cause: str,
    target: str,
) -> str:
    """Store a campaign failure for future avoidance queries.

    Args:
        campaign_id: Campaign identifier.
        description: What went wrong.
        root_cause: Root cause analysis.
        target: Target the campaign was for.

    Returns:
        JSON with status, id, document summary, and metadata.
    """
    if not campaign_id:
        return _error("campaign_id is required")
    if not description:
        return _error("description is required")
    if not root_cause:
        return _error("root_cause is required")
    if not target:
        return _error("target is required")

    doc_id = f"failure_{uuid.uuid4().hex[:12]}"
    now = time.time()

    record = {
        "id": doc_id,
        "campaign_id": campaign_id,
        "description": description,
        "root_cause": root_cause,
        "target": target,
        "stored_at": now,
        "access_count": 0,
    }

    failures = _load_json(FAILURES_FILE)
    failures.append(record)
    _save_json(FAILURES_FILE, failures)

    document = (
        f"Failure in campaign {campaign_id} targeting {target}. "
        f"Description: {description}. Root cause: {root_cause}."
    )

    return json.dumps(
        {
            "status": "stored",
            "id": doc_id,
            "document": document,
            "metadata": {
                "campaign_id": campaign_id,
                "description": description,
                "root_cause": root_cause,
                "target": target,
                "stored_at": now,
                "access_count": 0,
            },
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 5: knowledge_get_recommendations
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_get_recommendations(
    target: str,
    modality: str,
) -> str:
    """Get pre-campaign parameter recommendations.

    Queries similar campaigns, scaffold rankings, and past failures to suggest
    parameters for a new campaign.

    Args:
        target: Target name or description.
        modality: Design modality (e.g. antibody, nanobody, binder).

    Returns:
        JSON with similar_campaigns, recommended_scaffolds, warnings, and
        suggested_parameters.
    """
    if not target:
        return _error("target is required")
    if not modality:
        return _error("modality is required")

    campaigns = _load_json(CAMPAIGNS_FILE)
    failures = _load_json(FAILURES_FILE)

    recommendations: dict = {
        "target": target,
        "modality": modality,
        "similar_campaigns": [],
        "recommended_scaffolds": [],
        "warnings": [],
    }

    if not campaigns and not failures:
        recommendations["message"] = "No prior campaign data. Using default parameters."
        recommendations["suggested_parameters"] = {}
        return json.dumps(recommendations, indent=2)

    # 1. Query similar campaigns using keyword matching.
    query_text = f"{target} {modality}"
    query_tokens = _tokenize(query_text)

    scored_campaigns: list[tuple[float, dict]] = []
    for campaign in campaigns:
        doc_text = _campaign_text(campaign)
        doc_tokens = _tokenize(doc_text)
        score = _keyword_score(query_tokens, doc_tokens)
        scored_campaigns.append((score, campaign))

    scored_campaigns.sort(key=lambda x: x[0], reverse=True)

    for score, campaign in scored_campaigns[:5]:
        recommendations["similar_campaigns"].append({
            "id": campaign.get("id", ""),
            "similarity": round(score, 4),
            "target": campaign.get("target", ""),
            "modality": campaign.get("modality", ""),
            "outcomes": campaign.get("outcomes", {}),
            "parameters": campaign.get("parameters", {}),
        })

    # 2. Scaffold rankings from similar campaigns.
    scaffold_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"hit_rates": [], "ipsae_scores": [], "count": 0}
    )
    for camp in recommendations["similar_campaigns"]:
        params = camp.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, ValueError):
                params = {}
        outcomes = camp.get("outcomes", {})
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, ValueError):
                outcomes = {}

        scaffold = params.get("scaffold", "unknown")
        scaffold_stats[scaffold]["count"] += 1
        hit_rate = outcomes.get("hit_rate")
        if hit_rate is not None:
            try:
                scaffold_stats[scaffold]["hit_rates"].append(float(hit_rate))
            except (ValueError, TypeError):
                pass
        best_ipsae = outcomes.get("best_ipsae")
        if best_ipsae is not None:
            try:
                scaffold_stats[scaffold]["ipsae_scores"].append(float(best_ipsae))
            except (ValueError, TypeError):
                pass

    for scaffold, stats in scaffold_stats.items():
        entry: dict = {"scaffold": scaffold, "usage_count": stats["count"]}
        if stats["hit_rates"]:
            entry["avg_hit_rate"] = round(
                sum(stats["hit_rates"]) / len(stats["hit_rates"]), 4
            )
        if stats["ipsae_scores"]:
            entry["avg_ipsae"] = round(
                sum(stats["ipsae_scores"]) / len(stats["ipsae_scores"]), 4
            )
        recommendations["recommended_scaffolds"].append(entry)

    recommendations["recommended_scaffolds"].sort(
        key=lambda x: x.get("avg_hit_rate", 0), reverse=True
    )

    # 3. Query failures for warnings.
    for failure in failures:
        fail_text = f"{failure.get('target', '')} {failure.get('description', '')} {failure.get('root_cause', '')}"
        fail_tokens = _tokenize(fail_text)
        score = _keyword_score(query_tokens, fail_tokens)
        if score > 0.2:
            recommendations["warnings"].append({
                "id": failure.get("id", ""),
                "relevance": round(score, 4),
                "campaign_id": failure.get("campaign_id", ""),
                "description": failure.get("description", ""),
                "root_cause": failure.get("root_cause", ""),
            })

    # Sort warnings by relevance.
    recommendations["warnings"].sort(
        key=lambda x: x.get("relevance", 0), reverse=True
    )
    recommendations["warnings"] = recommendations["warnings"][:5]

    # 4. Suggest parameters from the best similar campaign.
    suggested_params: dict = {}
    if recommendations["similar_campaigns"]:
        best = recommendations["similar_campaigns"][0]
        params = best.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, ValueError):
                params = {}
        if params:
            suggested_params = params
    recommendations["suggested_parameters"] = suggested_params

    return json.dumps(recommendations, indent=2)


# ---------------------------------------------------------------------------
# Tool 6: knowledge_consolidate
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_consolidate() -> str:
    """Run a maintenance cycle on the knowledge base.

    Deduplicates near-identical entries (same target+modality+scaffold) and
    prunes stale entries (>90 days old with <3 accesses).

    Returns:
        JSON with deduped, pruned, and total_remaining counts.
    """
    stats: dict = {"deduped": 0, "pruned": 0, "total_remaining": 0}
    now = time.time()
    ninety_days = 90 * 24 * 60 * 60

    # Process campaigns.
    campaigns = _load_json(CAMPAIGNS_FILE)

    if campaigns:
        # Deduplication: find campaigns with identical target+modality+scaffold.
        seen: dict[str, int] = {}  # key -> index of best
        to_remove: set[int] = set()

        for i, campaign in enumerate(campaigns):
            params = campaign.get("parameters", {})
            scaffold = params.get("scaffold", "") if isinstance(params, dict) else ""
            key = f"{campaign.get('target', '').lower()}|{campaign.get('modality', '').lower()}|{scaffold.lower()}"

            if key in seen:
                j = seen[key]
                existing = campaigns[j]
                # Keep the one with higher access_count or more recent stored_at.
                access_i = campaign.get("access_count", 0)
                access_j = existing.get("access_count", 0)
                stored_i = campaign.get("stored_at", 0)
                stored_j = existing.get("stored_at", 0)

                if access_i > access_j or (access_i == access_j and stored_i > stored_j):
                    to_remove.add(j)
                    seen[key] = i
                else:
                    to_remove.add(i)
            else:
                seen[key] = i

        stats["deduped"] += len(to_remove)
        if to_remove:
            campaigns = [c for i, c in enumerate(campaigns) if i not in to_remove]

        # Pruning: remove entries older than 90 days with <3 accesses.
        before_count = len(campaigns)
        campaigns = [
            c for c in campaigns
            if not (
                (now - c.get("stored_at", 0)) > ninety_days
                and c.get("access_count", 0) < 3
            )
        ]
        stats["pruned"] += before_count - len(campaigns)
        stats["total_remaining"] += len(campaigns)

        _save_json(CAMPAIGNS_FILE, campaigns)

    # Process failures.
    failures = _load_json(FAILURES_FILE)

    if failures:
        # Prune old failures with low access.
        before_count = len(failures)
        failures = [
            f for f in failures
            if not (
                (now - f.get("stored_at", 0)) > ninety_days
                and f.get("access_count", 0) < 3
            )
        ]
        stats["pruned"] += before_count - len(failures)
        stats["total_remaining"] += len(failures)

        _save_json(FAILURES_FILE, failures)

    return json.dumps(
        {"status": "consolidation_complete", **stats},
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
