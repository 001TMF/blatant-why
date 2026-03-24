from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

"""Proteus Knowledge Graph MCP Server — persistent structured memory across campaigns."""

import json
import os
import time
import fcntl
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("proteus-knowledge")

KNOWLEDGE_DIR = Path(
    os.getenv("PROTEUS_KNOWLEDGE_DIR", os.path.expanduser("~/.proteus/knowledge"))
)

# ---------------------------------------------------------------------------
# Valid ontology types
# ---------------------------------------------------------------------------

VALID_ENTITY_TYPES = {
    "Target",
    "Epitope",
    "Scaffold",
    "Design",
    "ScreenResult",
    "FailurePattern",
}

VALID_RELATIONSHIP_TYPES = {
    "targets_epitope",
    "uses_scaffold",
    "produces_design",
    "has_result",
    "exhibits_failure",
}

VALID_QUERY_TYPES = {
    "scaffolds_for_target",
    "failure_patterns",
    "best_parameters",
}

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _ensure_dir():
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def _nodes_path() -> Path:
    _ensure_dir()
    return KNOWLEDGE_DIR / "nodes.jsonl"


def _edges_path() -> Path:
    _ensure_dir()
    return KNOWLEDGE_DIR / "edges.jsonl"


def _append_jsonl(path: Path, entry: dict):
    """Append a single JSON object as a line to a JSONL file (file-locked)."""
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)


def _read_jsonl(path: Path) -> list[dict]:
    """Read all valid JSON lines from a JSONL file."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _rewrite_jsonl(path: Path, entries: list[dict]):
    """Rewrite an entire JSONL file (file-locked, but NOT atomic)."""
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


# ---------------------------------------------------------------------------
# Tool 1: knowledge_add_entity
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_add_entity(
    entity_type: str,
    entity_id: str,
    properties_json: str = "{}",
) -> str:
    """Add or update a node in the knowledge graph.

    If an entity with the same entity_id already exists, its properties are
    merged (new properties overwrite existing keys).

    Args:
        entity_type: One of Target, Epitope, Scaffold, Design, ScreenResult,
            FailurePattern.
        entity_id: Unique identifier for this entity (e.g. "TNF-alpha",
            "caplacizumab", "design_001").
        properties_json: JSON string of key-value properties to store
            (default "{}").

    Returns:
        JSON with the stored entity including type, id, properties, and
        timestamps.
    """
    if entity_type not in VALID_ENTITY_TYPES:
        return _error(
            f"Invalid entity_type {entity_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}"
        )
    if not entity_id.strip():
        return _error("entity_id must not be empty.")

    try:
        properties = json.loads(properties_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid properties_json: {exc}")

    if not isinstance(properties, dict):
        return _error("properties_json must be a JSON object.")

    nodes_file = _nodes_path()

    # Hold an exclusive lock for the entire read-modify-write to prevent races.
    _ensure_dir()
    with open(nodes_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read()
            nodes = []
            for line in content.splitlines():
                if line.strip():
                    try:
                        nodes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            # Check for existing entity to merge.
            now = time.time()
            existing_idx = None
            for idx, node in enumerate(nodes):
                if node.get("entity_id") == entity_id:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                # Merge: update type if changed, merge properties.
                existing = nodes[existing_idx]
                existing["entity_type"] = entity_type
                existing_props = existing.get("properties", {})
                existing_props.update(properties)
                existing["properties"] = existing_props
                existing["updated_at"] = now
                nodes[existing_idx] = existing
                result = existing
            else:
                # New entity.
                entry = {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "properties": properties,
                    "created_at": now,
                    "updated_at": now,
                }
                nodes.append(entry)
                result = entry

            # Rewrite under the same lock.
            f.seek(0)
            f.truncate()
            for node in nodes:
                f.write(json.dumps(node) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: knowledge_add_relationship
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_add_relationship(
    from_id: str,
    to_id: str,
    relationship_type: str,
    properties_json: str = "{}",
) -> str:
    """Add a directed edge between two entities in the knowledge graph.

    Does NOT require entities to exist first — edges are stored independently
    to allow flexible graph construction.

    Args:
        from_id: Source entity_id.
        to_id: Target entity_id.
        relationship_type: One of targets_epitope, uses_scaffold,
            produces_design, has_result, exhibits_failure.
        properties_json: JSON string of edge properties (e.g. hit_rate,
            campaign_id). Default "{}".

    Returns:
        JSON with the stored edge including from, to, type, properties,
        and timestamp.
    """
    if relationship_type not in VALID_RELATIONSHIP_TYPES:
        return _error(
            f"Invalid relationship_type {relationship_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_RELATIONSHIP_TYPES))}"
        )
    if not from_id.strip():
        return _error("from_id must not be empty.")
    if not to_id.strip():
        return _error("to_id must not be empty.")

    try:
        properties = json.loads(properties_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid properties_json: {exc}")

    if not isinstance(properties, dict):
        return _error("properties_json must be a JSON object.")

    now = time.time()
    entry = {
        "from_id": from_id,
        "to_id": to_id,
        "relationship_type": relationship_type,
        "properties": properties,
        "created_at": now,
    }
    _append_jsonl(_edges_path(), entry)

    return json.dumps(entry, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: knowledge_query
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_query(
    query_type: str,
    filters_json: str = "{}",
) -> str:
    """Run a structured query against the knowledge graph.

    Supported query types:

    - **scaffolds_for_target**: Find scaffolds used for similar targets,
      returning hit rates and design counts. Filters: target_name (partial
      match), entity_type (default "Target").

    - **failure_patterns**: Find common failure patterns for a given scaffold
      or modality. Filters: scaffold_id, modality, entity_type.

    - **best_parameters**: Historical best parameters by target type. Filters:
      target_type (e.g. "cytokine", "receptor"), tool (e.g. "boltzgen").

    Args:
        query_type: One of scaffolds_for_target, failure_patterns,
            best_parameters.
        filters_json: JSON string of filter criteria (default "{}").

    Returns:
        JSON array of matching results, or an error if the query type is
        invalid.
    """
    if query_type not in VALID_QUERY_TYPES:
        return _error(
            f"Invalid query_type {query_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_QUERY_TYPES))}"
        )

    try:
        filters = json.loads(filters_json)
    except json.JSONDecodeError as exc:
        return _error(f"Invalid filters_json: {exc}")

    if not isinstance(filters, dict):
        return _error("filters_json must be a JSON object.")

    nodes = _read_jsonl(_nodes_path())
    edges = _read_jsonl(_edges_path())

    if query_type == "scaffolds_for_target":
        return _query_scaffolds_for_target(nodes, edges, filters)
    elif query_type == "failure_patterns":
        return _query_failure_patterns(nodes, edges, filters)
    elif query_type == "best_parameters":
        return _query_best_parameters(nodes, edges, filters)

    return _error("Unhandled query type.")


def _query_scaffolds_for_target(
    nodes: list[dict], edges: list[dict], filters: dict
) -> str:
    """Find scaffolds used for targets matching the filter."""
    target_name = filters.get("target_name", "").lower()

    # Find matching target entity IDs.
    matching_targets = set()
    for node in nodes:
        if node.get("entity_type") != "Target":
            continue
        eid = node.get("entity_id", "")
        props = node.get("properties", {})
        name = props.get("name", eid).lower()
        if target_name and target_name not in name and target_name not in eid.lower():
            continue
        matching_targets.add(eid)

    if not matching_targets and target_name:
        # Broaden: include all targets if no match.
        for node in nodes:
            if node.get("entity_type") == "Target":
                matching_targets.add(node["entity_id"])

    # Walk edges: target -> uses_scaffold -> scaffold.
    scaffold_stats: dict[str, dict] = {}
    for edge in edges:
        if edge.get("relationship_type") != "uses_scaffold":
            continue
        if edge.get("from_id") not in matching_targets:
            continue
        scaffold_id = edge.get("to_id", "")
        props = edge.get("properties", {})
        if scaffold_id not in scaffold_stats:
            scaffold_stats[scaffold_id] = {
                "scaffold_id": scaffold_id,
                "usage_count": 0,
                "hit_rates": [],
                "campaigns": [],
            }
        scaffold_stats[scaffold_id]["usage_count"] += 1
        if "hit_rate" in props:
            scaffold_stats[scaffold_id]["hit_rates"].append(props["hit_rate"])
        if "campaign_id" in props:
            scaffold_stats[scaffold_id]["campaigns"].append(props["campaign_id"])

    # Enrich with scaffold node properties.
    scaffold_nodes = {
        n["entity_id"]: n for n in nodes if n.get("entity_type") == "Scaffold"
    }
    results = []
    for sid, stats in scaffold_stats.items():
        entry = dict(stats)
        if stats["hit_rates"]:
            entry["mean_hit_rate"] = sum(stats["hit_rates"]) / len(stats["hit_rates"])
        if sid in scaffold_nodes:
            entry["properties"] = scaffold_nodes[sid].get("properties", {})
        results.append(entry)

    results.sort(key=lambda x: x.get("mean_hit_rate", 0), reverse=True)
    return json.dumps(results, indent=2)


def _query_failure_patterns(
    nodes: list[dict], edges: list[dict], filters: dict
) -> str:
    """Find failure patterns associated with a scaffold or modality."""
    scaffold_id = filters.get("scaffold_id", "").lower()
    modality = filters.get("modality", "").lower()

    # Collect FailurePattern entities.
    failure_nodes = [n for n in nodes if n.get("entity_type") == "FailurePattern"]

    # Find IDs connected via exhibits_failure edges.
    failure_sources: dict[str, set] = {}
    for edge in edges:
        if edge.get("relationship_type") != "exhibits_failure":
            continue
        fid = edge.get("to_id", "")
        src = edge.get("from_id", "")
        if fid not in failure_sources:
            failure_sources[fid] = set()
        failure_sources[fid].add(src)

    results = []
    for fnode in failure_nodes:
        fid = fnode.get("entity_id", "")
        props = fnode.get("properties", {})

        # Filter by scaffold_id if provided.
        if scaffold_id:
            sources = failure_sources.get(fid, set())
            if not any(scaffold_id in s.lower() for s in sources):
                continue

        # Filter by modality if provided.
        if modality:
            node_modality = props.get("modality", "").lower()
            if modality not in node_modality:
                continue

        entry = {
            "failure_id": fid,
            "properties": props,
            "occurrence_count": len(failure_sources.get(fid, set())),
            "sources": list(failure_sources.get(fid, set())),
        }
        results.append(entry)

    results.sort(key=lambda x: x["occurrence_count"], reverse=True)
    return json.dumps(results, indent=2)


def _query_best_parameters(
    nodes: list[dict], edges: list[dict], filters: dict
) -> str:
    """Find historical best parameters by target type or tool."""
    target_type = filters.get("target_type", "").lower()
    tool = filters.get("tool", "").lower()

    # Collect Design entities with their parameters and scores.
    designs = [n for n in nodes if n.get("entity_type") == "Design"]

    # Build design -> ScreenResult mapping via has_result edges.
    design_results: dict[str, list[dict]] = {}
    result_nodes = {
        n["entity_id"]: n for n in nodes if n.get("entity_type") == "ScreenResult"
    }
    for edge in edges:
        if edge.get("relationship_type") != "has_result":
            continue
        did = edge.get("from_id", "")
        rid = edge.get("to_id", "")
        if rid in result_nodes:
            if did not in design_results:
                design_results[did] = []
            design_results[did].append(result_nodes[rid].get("properties", {}))

    # Filter and rank designs.
    results = []
    for design in designs:
        did = design.get("entity_id", "")
        props = design.get("properties", {})

        if target_type:
            d_target_type = props.get("target_type", "").lower()
            if target_type not in d_target_type:
                continue

        if tool:
            d_tool = props.get("tool", "").lower()
            if tool not in d_tool:
                continue

        # Find best scores for this design.
        best_ipsae = 0.0
        best_iptm = 0.0
        for result in design_results.get(did, []):
            ipsae = result.get("ipsae_min", result.get("ipsae", 0.0))
            iptm = result.get("iptm", 0.0)
            if ipsae > best_ipsae:
                best_ipsae = ipsae
            if iptm > best_iptm:
                best_iptm = iptm

        entry = {
            "design_id": did,
            "parameters": props,
            "best_ipsae": best_ipsae,
            "best_iptm": best_iptm,
        }
        results.append(entry)

    results.sort(key=lambda x: x["best_ipsae"], reverse=True)
    return json.dumps(results[:20], indent=2)


# ---------------------------------------------------------------------------
# Tool 4: knowledge_get_entities
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_get_entities(
    entity_type: str = "",
    limit: int = 50,
) -> str:
    """List recent entities from the knowledge graph.

    Args:
        entity_type: Filter by entity type (e.g. "Target", "Scaffold").
            If empty, returns all types.
        limit: Maximum number of entities to return (default 50, max 500).

    Returns:
        JSON array of matching entities, sorted by most recently updated.
    """
    if entity_type and entity_type not in VALID_ENTITY_TYPES:
        return _error(
            f"Invalid entity_type {entity_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}"
        )

    limit = min(max(1, limit), 500)
    nodes = _read_jsonl(_nodes_path())

    if entity_type:
        nodes = [n for n in nodes if n.get("entity_type") == entity_type]

    # Sort by updated_at descending (most recent first).
    nodes.sort(key=lambda x: x.get("updated_at", 0), reverse=True)

    return json.dumps(nodes[:limit], indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
