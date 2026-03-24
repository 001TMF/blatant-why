#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "chromadb>=0.5.0",
#   "sentence-transformers>=3.0.0",
# ]
# ///
"""BY Knowledge MCP Server — semantic memory with ChromaDB + sentence-transformers."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import defaultdict

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# ---------------------------------------------------------------------------
# ChromaDB setup
# ---------------------------------------------------------------------------

COLLECTION_NAMES = ("campaigns", "scaffolds", "targets", "failures", "user_preferences")

_client: chromadb.ClientAPI | None = None
_ef: embedding_functions.SentenceTransformerEmbeddingFunction | None = None


def _get_embedding_function() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    global _ef
    if _ef is None:
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
        )
    return _ef


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        db_path = os.path.join(os.getcwd(), ".by", "knowledge.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection(name: str) -> chromadb.Collection:
    client = _get_client()
    ef = _get_embedding_function()
    return client.get_or_create_collection(name, embedding_function=ef)


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


def _flatten_metadata(d: dict) -> dict:
    """Flatten a dict so all values are ChromaDB-safe (str, int, float, bool).

    Nested dicts/lists are JSON-serialised to strings.
    """
    flat: dict = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            flat[k] = v
        else:
            flat[k] = json.dumps(v)
    return flat


def _unflatten_metadata(d: dict) -> dict:
    """Attempt to JSON-parse string values that look like dicts/lists."""
    out: dict = {}
    for k, v in d.items():
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, (dict, list)):
                    out[k] = parsed
                    continue
            except (json.JSONDecodeError, ValueError):
                pass
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# MMR helper
# ---------------------------------------------------------------------------


def _mmr_rerank(
    query_embedding: list[float],
    doc_embeddings: list[list[float]],
    doc_indices: list[int],
    top_k: int,
    lambda_param: float = 0.7,
) -> list[int]:
    """Maximal Marginal Relevance re-ranking.

    score = lambda * similarity(query, doc) + (1-lambda) * max_diversity(doc, selected)
    """
    import math

    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    if not doc_indices:
        return []

    selected: list[int] = []
    remaining = list(range(len(doc_indices)))

    # Precompute query similarities.
    query_sims = [_cosine(query_embedding, doc_embeddings[i]) for i in range(len(doc_indices))]

    for _ in range(min(top_k, len(doc_indices))):
        best_score = -float("inf")
        best_idx = -1

        for idx in remaining:
            sim_query = query_sims[idx]

            if not selected:
                diversity = 0.0
            else:
                max_sim_selected = max(
                    _cosine(doc_embeddings[idx], doc_embeddings[s]) for s in selected
                )
                diversity = 1.0 - max_sim_selected

            score = lambda_param * sim_query + (1 - lambda_param) * diversity
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx < 0:
            break
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [doc_indices[i] for i in selected]


# ---------------------------------------------------------------------------
# Server definition
# ---------------------------------------------------------------------------

server = Server("by-knowledge")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="knowledge_store_campaign",
            description=(
                "Store a completed campaign outcome in the knowledge base. "
                "Embeds a text summary for semantic search and stores full data as metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target name or description"},
                    "modality": {
                        "type": "string",
                        "description": "Design modality (e.g. antibody, nanobody, binder)",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Campaign parameters (scaffold, seeds, temperature, etc.)",
                    },
                    "outcomes": {
                        "type": "object",
                        "description": (
                            "Campaign outcomes with keys: hit_rate, best_ipsae, best_iptm, "
                            "screening_pass_rate"
                        ),
                    },
                    "notes": {"type": "string", "description": "Free-text notes about the campaign"},
                },
                "required": ["target", "modality", "parameters", "outcomes"],
            },
        ),
        types.Tool(
            name="knowledge_query_similar",
            description=(
                "Find similar past campaigns using semantic search with MMR diversity re-ranking."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_description": {
                        "type": "string",
                        "description": "Description of the target to search for",
                    },
                    "modality": {
                        "type": "string",
                        "description": "Optional modality filter (e.g. antibody, nanobody)",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["target_description"],
            },
        ),
        types.Tool(
            name="knowledge_scaffold_rankings",
            description=(
                "Get best-performing scaffolds for a target class, ranked by average hit rate "
                "and average ipSAE across past campaigns."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_class": {
                        "type": "string",
                        "description": 'Target class (e.g. "immune checkpoint", "cytokine")',
                    },
                },
                "required": ["target_class"],
            },
        ),
        types.Tool(
            name="knowledge_store_failure",
            description="Store a campaign failure for future avoidance queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign identifier"},
                    "description": {"type": "string", "description": "What went wrong"},
                    "root_cause": {
                        "type": "string",
                        "description": "Root cause analysis",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target the campaign was for",
                    },
                },
                "required": ["campaign_id", "description", "root_cause", "target"],
            },
        ),
        types.Tool(
            name="knowledge_get_recommendations",
            description=(
                "Get pre-campaign parameter recommendations by querying similar campaigns, "
                "scaffold rankings, and past failures."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target name or description"},
                    "modality": {
                        "type": "string",
                        "description": "Design modality (e.g. antibody, nanobody, binder)",
                    },
                },
                "required": ["target", "modality"],
            },
        ),
        types.Tool(
            name="knowledge_consolidate",
            description=(
                "Run a maintenance cycle: deduplicate near-identical entries (>0.95 cosine "
                "similarity) and prune stale entries (>90 days old with <3 accesses)."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
    except Exception as exc:
        result = _error(f"Internal error: {exc}")
    return [types.TextContent(type="text", text=result)]


async def _dispatch(name: str, arguments: dict) -> str:
    if name == "knowledge_store_campaign":
        return await _store_campaign(arguments)
    elif name == "knowledge_query_similar":
        return await _query_similar(arguments)
    elif name == "knowledge_scaffold_rankings":
        return await _scaffold_rankings(arguments)
    elif name == "knowledge_store_failure":
        return await _store_failure(arguments)
    elif name == "knowledge_get_recommendations":
        return await _get_recommendations(arguments)
    elif name == "knowledge_consolidate":
        return await _consolidate(arguments)
    else:
        return _error(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool 1: knowledge_store_campaign
# ---------------------------------------------------------------------------


async def _store_campaign(args: dict) -> str:
    target = args.get("target", "")
    modality = args.get("modality", "")
    parameters = args.get("parameters", {})
    outcomes = args.get("outcomes", {})
    notes = args.get("notes", "")

    if not target:
        return _error("target is required")
    if not modality:
        return _error("modality is required")

    # Build a text summary for embedding.
    summary_parts = [
        f"Campaign targeting {target} using {modality} modality.",
    ]
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

    document = " ".join(summary_parts)
    doc_id = f"campaign_{uuid.uuid4().hex[:12]}"
    now = time.time()

    metadata = _flatten_metadata(
        {
            "target": target,
            "modality": modality,
            "parameters": parameters,
            "outcomes": outcomes,
            "notes": notes,
            "stored_at": now,
            "access_count": 0,
        }
    )

    collection = _get_collection("campaigns")
    collection.add(
        ids=[doc_id],
        documents=[document],
        metadatas=[metadata],
    )

    return json.dumps(
        {
            "status": "stored",
            "id": doc_id,
            "document": document,
            "metadata": _unflatten_metadata(metadata),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 2: knowledge_query_similar
# ---------------------------------------------------------------------------


async def _query_similar(args: dict) -> str:
    target_description = args.get("target_description", "")
    modality = args.get("modality")
    top_k = args.get("top_k", 5)

    if not target_description:
        return _error("target_description is required")

    collection = _get_collection("campaigns")

    # Fetch more candidates than needed for MMR re-ranking.
    fetch_k = min(top_k * 3, 20)

    where_filter = None
    if modality:
        where_filter = {"modality": modality}

    try:
        results = collection.query(
            query_texts=[target_description],
            n_results=fetch_k,
            where=where_filter,
            include=["documents", "metadatas", "distances", "embeddings"],
        )
    except Exception:
        # If collection is empty or filter yields nothing, return empty.
        return json.dumps({"results": [], "query": target_description})

    if not results["ids"] or not results["ids"][0]:
        return json.dumps({"results": [], "query": target_description})

    ids = results["ids"][0]
    documents = results["documents"][0] if results["documents"] else [""] * len(ids)
    metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
    distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)

    # MMR re-ranking if we have embeddings.
    doc_embeddings = results.get("embeddings", [[]])[0] if results.get("embeddings") else None

    if doc_embeddings and len(doc_embeddings) == len(ids):
        # Get query embedding.
        ef = _get_embedding_function()
        query_emb = ef([target_description])[0]

        reranked_indices = _mmr_rerank(
            query_embedding=query_emb,
            doc_embeddings=doc_embeddings,
            doc_indices=list(range(len(ids))),
            top_k=top_k,
            lambda_param=0.7,
        )
    else:
        reranked_indices = list(range(min(top_k, len(ids))))

    # Increment access counts for returned results.
    output = []
    for idx in reranked_indices:
        # Convert distance to similarity (ChromaDB L2 distance).
        similarity = 1.0 / (1.0 + distances[idx])
        meta = _unflatten_metadata(metadatas[idx]) if metadatas[idx] else {}

        # Bump access count.
        new_count = meta.get("access_count", 0)
        if isinstance(new_count, (int, float)):
            new_count = int(new_count) + 1
        else:
            new_count = 1
        try:
            updated_meta = dict(metadatas[idx]) if metadatas[idx] else {}
            updated_meta["access_count"] = new_count
            collection.update(ids=[ids[idx]], metadatas=[updated_meta])
        except Exception:
            pass

        output.append(
            {
                "id": ids[idx],
                "similarity": round(similarity, 4),
                "document": documents[idx],
                "metadata": meta,
            }
        )

    return json.dumps({"results": output, "query": target_description}, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: knowledge_scaffold_rankings
# ---------------------------------------------------------------------------


async def _scaffold_rankings(args: dict) -> str:
    target_class = args.get("target_class", "")
    if not target_class:
        return _error("target_class is required")

    collection = _get_collection("campaigns")

    # Semantic search for campaigns matching this target class.
    try:
        results = collection.query(
            query_texts=[target_class],
            n_results=50,
            include=["metadatas"],
        )
    except Exception:
        return json.dumps({"rankings": [], "target_class": target_class})

    if not results["ids"] or not results["ids"][0]:
        return json.dumps({"rankings": [], "target_class": target_class})

    metadatas = results["metadatas"][0] if results["metadatas"] else []

    # Aggregate scaffold performance.
    scaffold_stats: dict[str, dict] = defaultdict(
        lambda: {"hit_rates": [], "ipsae_scores": [], "campaign_count": 0}
    )

    for meta in metadatas:
        meta = _unflatten_metadata(meta) if meta else {}
        params = meta.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, ValueError):
                params = {}

        outcomes = meta.get("outcomes", {})
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


async def _store_failure(args: dict) -> str:
    campaign_id = args.get("campaign_id", "")
    description = args.get("description", "")
    root_cause = args.get("root_cause", "")
    target = args.get("target", "")

    if not campaign_id:
        return _error("campaign_id is required")
    if not description:
        return _error("description is required")
    if not root_cause:
        return _error("root_cause is required")
    if not target:
        return _error("target is required")

    document = (
        f"Failure in campaign {campaign_id} targeting {target}. "
        f"Description: {description}. Root cause: {root_cause}."
    )
    doc_id = f"failure_{uuid.uuid4().hex[:12]}"
    now = time.time()

    metadata = _flatten_metadata(
        {
            "campaign_id": campaign_id,
            "description": description,
            "root_cause": root_cause,
            "target": target,
            "stored_at": now,
            "access_count": 0,
        }
    )

    collection = _get_collection("failures")
    collection.add(
        ids=[doc_id],
        documents=[document],
        metadatas=[metadata],
    )

    return json.dumps(
        {
            "status": "stored",
            "id": doc_id,
            "document": document,
            "metadata": _unflatten_metadata(metadata),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tool 5: knowledge_get_recommendations
# ---------------------------------------------------------------------------


async def _get_recommendations(args: dict) -> str:
    target = args.get("target", "")
    modality = args.get("modality", "")

    if not target:
        return _error("target is required")
    if not modality:
        return _error("modality is required")

    query_text = f"{target} {modality}"
    recommendations: dict = {
        "target": target,
        "modality": modality,
        "similar_campaigns": [],
        "recommended_scaffolds": [],
        "warnings": [],
    }

    # 1. Query similar campaigns.
    campaigns_coll = _get_collection("campaigns")
    try:
        campaign_results = campaigns_coll.query(
            query_texts=[query_text],
            n_results=5,
            include=["documents", "metadatas", "distances"],
        )
        if campaign_results["ids"] and campaign_results["ids"][0]:
            for i, doc_id in enumerate(campaign_results["ids"][0]):
                meta = campaign_results["metadatas"][0][i] if campaign_results["metadatas"] else {}
                meta = _unflatten_metadata(meta) if meta else {}
                distance = campaign_results["distances"][0][i] if campaign_results["distances"] else 0
                similarity = 1.0 / (1.0 + distance)
                recommendations["similar_campaigns"].append(
                    {
                        "id": doc_id,
                        "similarity": round(similarity, 4),
                        "target": meta.get("target", ""),
                        "modality": meta.get("modality", ""),
                        "outcomes": meta.get("outcomes", {}),
                        "parameters": meta.get("parameters", {}),
                    }
                )
    except Exception:
        pass

    # 2. Scaffold rankings from similar campaigns.
    scaffold_stats: dict[str, dict] = defaultdict(
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
    failures_coll = _get_collection("failures")
    try:
        failure_results = failures_coll.query(
            query_texts=[query_text],
            n_results=5,
            include=["documents", "metadatas", "distances"],
        )
        if failure_results["ids"] and failure_results["ids"][0]:
            for i, doc_id in enumerate(failure_results["ids"][0]):
                meta = failure_results["metadatas"][0][i] if failure_results["metadatas"] else {}
                meta = _unflatten_metadata(meta) if meta else {}
                distance = failure_results["distances"][0][i] if failure_results["distances"] else 0
                similarity = 1.0 / (1.0 + distance)
                # Only include reasonably relevant failures.
                if similarity > 0.3:
                    recommendations["warnings"].append(
                        {
                            "id": doc_id,
                            "relevance": round(similarity, 4),
                            "campaign_id": meta.get("campaign_id", ""),
                            "description": meta.get("description", ""),
                            "root_cause": meta.get("root_cause", ""),
                        }
                    )
    except Exception:
        pass

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


async def _consolidate(args: dict) -> str:
    import math

    stats: dict = {"deduped": 0, "pruned": 0, "total_remaining": 0}
    now = time.time()
    ninety_days = 90 * 24 * 60 * 60

    ef = _get_embedding_function()

    for coll_name in COLLECTION_NAMES:
        collection = _get_collection(coll_name)

        try:
            all_data = collection.get(include=["embeddings", "metadatas", "documents"])
        except Exception:
            continue

        if not all_data["ids"]:
            continue

        ids = all_data["ids"]
        embeddings = all_data["embeddings"] if all_data.get("embeddings") else []
        metadatas = all_data["metadatas"] if all_data.get("metadatas") else [{}] * len(ids)

        # --- Deduplication: find pairs with >0.95 cosine similarity ---
        to_remove: set[str] = set()

        if embeddings and len(embeddings) == len(ids):

            def _cosine(a: list[float], b: list[float]) -> float:
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(x * x for x in b))
                if na == 0 or nb == 0:
                    return 0.0
                return dot / (na * nb)

            for i in range(len(ids)):
                if ids[i] in to_remove:
                    continue
                for j in range(i + 1, len(ids)):
                    if ids[j] in to_remove:
                        continue
                    sim = _cosine(embeddings[i], embeddings[j])
                    if sim > 0.95:
                        # Keep the one with higher access_count or more recent timestamp.
                        meta_i = metadatas[i] if metadatas[i] else {}
                        meta_j = metadatas[j] if metadatas[j] else {}
                        access_i = meta_i.get("access_count", 0)
                        access_j = meta_j.get("access_count", 0)
                        if isinstance(access_i, str):
                            try:
                                access_i = int(access_i)
                            except ValueError:
                                access_i = 0
                        if isinstance(access_j, str):
                            try:
                                access_j = int(access_j)
                            except ValueError:
                                access_j = 0

                        stored_i = meta_i.get("stored_at", 0)
                        stored_j = meta_j.get("stored_at", 0)

                        # Remove the lower-quality one.
                        if access_i > access_j or (access_i == access_j and stored_i >= stored_j):
                            to_remove.add(ids[j])
                        else:
                            to_remove.add(ids[i])

            if to_remove:
                stats["deduped"] += len(to_remove)
                collection.delete(ids=list(to_remove))

        # --- Pruning: remove entries older than 90 days with <3 accesses ---
        # Re-fetch after dedup.
        try:
            remaining = collection.get(include=["metadatas"])
        except Exception:
            continue

        if not remaining["ids"]:
            continue

        prune_ids: list[str] = []
        for idx, doc_id in enumerate(remaining["ids"]):
            meta = remaining["metadatas"][idx] if remaining["metadatas"] and remaining["metadatas"][idx] else {}
            stored_at = meta.get("stored_at", 0)
            access_count = meta.get("access_count", 0)

            if isinstance(stored_at, str):
                try:
                    stored_at = float(stored_at)
                except ValueError:
                    stored_at = 0
            if isinstance(access_count, str):
                try:
                    access_count = int(access_count)
                except ValueError:
                    access_count = 0

            age = now - stored_at
            if age > ninety_days and access_count < 3:
                prune_ids.append(doc_id)

        if prune_ids:
            stats["pruned"] += len(prune_ids)
            collection.delete(ids=prune_ids)

        # Count remaining.
        try:
            stats["total_remaining"] += collection.count()
        except Exception:
            pass

    return json.dumps(
        {"status": "consolidation_complete", **stats},
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
