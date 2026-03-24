#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx",
# ]
# ///
"""Research MCP Server — public API queries for target research in BY agent."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
import re
from urllib.parse import quote, urlencode

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("by-research")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIMEOUT = 30.0

# PubMed E-utilities
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# bioRxiv
BIORXIV_API_URL = "https://api.biorxiv.org/details/biorxiv"

# UniProt REST
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_BLAST_URL = "https://rest.uniprot.org/idmapping/run"
UNIPROT_BLAST_STATUS_URL = "https://rest.uniprot.org/idmapping/status"
UNIPROT_BLAST_RESULTS_URL = "https://rest.uniprot.org/idmapping/uniprotkb/results"

# PDB / RCSB
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA_URL = "https://data.rcsb.org/rest/v1/core/entry"

# SAbDab
SABDAB_SUMMARY_URL = "http://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab/summary/all/"

# RCSB FASTA (for fetching chain sequences by PDB ID)
RCSB_FASTA_URL = "https://www.rcsb.org/fasta/entry"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any] | None = None,
    timeout: float = TIMEOUT,
) -> dict | list | None:
    """GET a URL and return parsed JSON, or None on failure."""
    resp = await client.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tool 1: research_search_prior_art
# ---------------------------------------------------------------------------


@mcp.tool()
async def research_search_prior_art(
    target_name: str,
    max_results: int = 10,
) -> str:
    """Search PubMed and bioRxiv for prior art on a target.

    Queries for published papers and preprints about antibody/nanobody
    design or engineering against the specified target.

    Args:
        target_name: Target protein name (e.g. "TNF-alpha", "PD-L1").
        max_results: Maximum results per source (default 10, max 50).

    Returns:
        JSON with pubmed_results, biorxiv_results, and total count.
    """
    if not target_name.strip():
        return _error("target_name must not be empty.")

    max_results = min(max(1, max_results), 50)
    query = f'"{target_name}" AND (antibody OR nanobody OR binder) AND (design OR engineering)'

    pubmed_results: list[dict[str, Any]] = []
    biorxiv_results: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient() as client:
        # --- PubMed search ---
        try:
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
            }
            search_data = await _get_json(client, PUBMED_ESEARCH_URL, params=search_params)
            if search_data:
                id_list = search_data.get("esearchresult", {}).get("idlist", [])

                if id_list:
                    # Fetch summaries for all IDs at once.
                    summary_params = {
                        "db": "pubmed",
                        "id": ",".join(id_list),
                        "retmode": "json",
                    }
                    summary_data = await _get_json(
                        client, PUBMED_ESUMMARY_URL, params=summary_params
                    )
                    if summary_data:
                        results_map = summary_data.get("result", {})
                        for pmid in id_list:
                            article = results_map.get(pmid, {})
                            if not isinstance(article, dict):
                                continue

                            authors_list = article.get("authors", [])
                            author_names = [
                                a.get("name", "") for a in authors_list[:3]
                            ]
                            if len(authors_list) > 3:
                                author_names.append("et al.")

                            # Extract DOI from articleids
                            doi = ""
                            for aid in article.get("articleids", []):
                                if aid.get("idtype") == "doi":
                                    doi = aid.get("value", "")
                                    break

                            pubmed_results.append({
                                "pmid": pmid,
                                "title": article.get("title", ""),
                                "authors": ", ".join(author_names),
                                "year": article.get("pubdate", "")[:4],
                                "doi": doi,
                                "source": article.get("source", ""),
                            })
        except Exception as exc:
            errors.append(f"PubMed search failed: {exc}")

        # --- bioRxiv / preprint search via EuropePMC ---
        try:
            # The bioRxiv /details API only returns the N most recent
            # preprints from a date window with no query filtering,
            # making it nearly useless for target-specific search.
            # Instead, query EuropePMC which indexes bioRxiv and medRxiv
            # preprints and supports proper relevance-ranked search.
            epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            epmc_params = {
                "query": (
                    f'(TITLE:"{target_name}" OR ABSTRACT:"{target_name}") '
                    f"AND (antibody OR nanobody OR binder OR design OR engineering) "
                    f'AND SRC:"PPR"'
                ),
                "format": "json",
                "pageSize": max_results,
                "sort": "RELEVANCE",
            }
            resp = await client.get(epmc_url, params=epmc_params, timeout=TIMEOUT)
            resp.raise_for_status()
            epmc_data = resp.json()

            for paper in epmc_data.get("resultList", {}).get("result", []):
                title = paper.get("title", "")
                authors = paper.get("authorString", "")
                if len(authors) > 80:
                    authors = authors[:80] + "..."

                biorxiv_results.append({
                    "title": title,
                    "authors": authors,
                    "doi": paper.get("doi", ""),
                    "date": paper.get("firstPublicationDate", ""),
                    "category": paper.get("journalTitle", ""),
                    "source": paper.get("source", ""),
                })

                if len(biorxiv_results) >= max_results:
                    break

        except Exception as exc:
            errors.append(f"bioRxiv/EuropePMC search failed: {exc}")

    result: dict[str, Any] = {
        "query": query,
        "pubmed_results": pubmed_results,
        "biorxiv_results": biorxiv_results,
        "total": len(pubmed_results) + len(biorxiv_results),
    }
    if errors:
        result["warnings"] = errors
        result["degraded"] = True
        result["sources_failed"] = len(errors)

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: research_get_target_info
# ---------------------------------------------------------------------------


@mcp.tool()
async def research_get_target_info(target: str) -> str:
    """Get combined UniProt and PDB information for a target protein.

    Args:
        target: Target name, UniProt accession, or gene name (e.g. "P01375",
            "TNF-alpha", "TNFSF2").

    Returns:
        JSON with uniprot info (accession, name, function, sequence_length,
        organism) and pdb_entries list.
    """
    if not target.strip():
        return _error("target must not be empty.")

    uniprot_info: dict[str, Any] = {}
    pdb_entries: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient() as client:
        # --- UniProt search ---
        try:
            params = {
                "query": target.strip(),
                "format": "json",
                "size": "1",
                "fields": "accession,protein_name,organism_name,length,cc_function,gene_names",
            }
            resp = await client.get(UNIPROT_SEARCH_URL, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            results_list = data.get("results", [])
            if results_list:
                entry = results_list[0]
                accession = entry.get("primaryAccession", "")

                # Extract protein name
                protein_desc = entry.get("proteinDescription", {})
                rec_name = protein_desc.get("recommendedName", {})
                full_name = rec_name.get("fullName", {}).get("value", "")
                if not full_name:
                    sub_names = protein_desc.get("submissionNames", [])
                    if sub_names:
                        full_name = sub_names[0].get("fullName", {}).get("value", "")

                # Extract function from comments
                function_text = ""
                comments = entry.get("comments", [])
                for comment in comments:
                    if comment.get("commentType") == "FUNCTION":
                        texts = comment.get("texts", [])
                        if texts:
                            function_text = texts[0].get("value", "")
                            break

                # Extract organism
                organism = entry.get("organism", {}).get("scientificName", "")

                # Sequence length
                seq_length = entry.get("sequence", {}).get("length", 0)

                # Gene names
                genes = entry.get("genes", [])
                gene_names = []
                for gene in genes:
                    gn = gene.get("geneName", {}).get("value")
                    if gn:
                        gene_names.append(gn)

                uniprot_info = {
                    "accession": accession,
                    "name": full_name,
                    "gene_names": gene_names,
                    "function": function_text[:500] if function_text else "",
                    "sequence_length": seq_length,
                    "organism": organism,
                }

        except Exception as exc:
            errors.append(f"UniProt search failed: {exc}")

        # --- PDB search ---
        try:
            search_payload = {
                "query": {
                    "type": "terminal",
                    "service": "full_text",
                    "parameters": {"value": target.strip()},
                },
                "return_type": "entry",
                "request_options": {
                    "paginate": {"start": 0, "rows": 10},
                    "results_content_type": ["experimental"],
                    "sort": [{"sort_by": "score", "direction": "desc"}],
                },
            }

            resp = await client.post(
                RCSB_SEARCH_URL, json=search_payload, timeout=TIMEOUT
            )
            if resp.status_code != 204:
                resp.raise_for_status()
                data = resp.json()

                pdb_ids = [
                    hit["identifier"] for hit in data.get("result_set", [])
                ]

                for pdb_id in pdb_ids:
                    try:
                        entry_url = f"{RCSB_DATA_URL}/{pdb_id}"
                        entry_data = await _get_json(client, entry_url)
                        if entry_data is None:
                            continue

                        struct = entry_data.get("struct", {}) or {}
                        title = struct.get("title", "")

                        exptl = entry_data.get("exptl", [{}])
                        method = (
                            exptl[0].get("method", "unknown") if exptl else "unknown"
                        )

                        rcsb_info = entry_data.get("rcsb_entry_info", {}) or {}
                        resolution = rcsb_info.get("resolution_combined")
                        if isinstance(resolution, list) and resolution:
                            resolution = resolution[0]

                        pdb_entries.append({
                            "pdb_id": pdb_id,
                            "title": title,
                            "method": method,
                            "resolution": resolution,
                        })
                    except httpx.HTTPError:
                        pdb_entries.append({
                            "pdb_id": pdb_id,
                            "title": "",
                            "method": "",
                            "resolution": None,
                        })

        except Exception as exc:
            errors.append(f"PDB search failed: {exc}")

    result: dict[str, Any] = {
        "uniprot": uniprot_info,
        "pdb_entries": pdb_entries,
        "num_known_structures": len(pdb_entries),
    }
    if errors:
        result["warnings"] = errors

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: research_analyze_known_binders
# ---------------------------------------------------------------------------


@mcp.tool()
async def research_analyze_known_binders(
    target_name: str,
    max_structures: int = 5,
) -> str:
    """Search SAbDab for known antibodies against a target.

    Queries the Structural Antibody Database for experimentally determined
    antibody-antigen complexes involving the target protein.

    Args:
        target_name: Target protein name (e.g. "TNF-alpha").
        max_structures: Maximum number of structures to return (default 5, max 20).

    Returns:
        JSON with target, num_known_binders, and binders list (pdb_id,
        heavy_chain, light_chain, antigen_chains, resolution, method).
    """
    if not target_name.strip():
        return _error("target_name must not be empty.")

    max_structures = min(max(1, max_structures), 20)
    binders: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # SAbDab summary endpoint returns TSV with all structures.
        # We download the summary and filter by antigen name.
        try:
            params = {"all": "true"}
            resp = await client.get(
                SABDAB_SUMMARY_URL,
                params=params,
                timeout=60.0,
                headers={"Accept": "text/tab-separated-values"},
            )
            resp.raise_for_status()
            tsv_text = resp.text

            # Parse TSV: first line is headers, rest are data rows.
            lines = tsv_text.strip().split("\n")
            if len(lines) < 2:
                return json.dumps({
                    "target": target_name,
                    "num_known_binders": 0,
                    "binders": [],
                    "warnings": ["SAbDab returned no data rows."],
                }, indent=2)

            headers = lines[0].split("\t")

            # Find relevant column indices.
            def _col(name: str) -> int:
                """Find column index by partial header match (case-insensitive)."""
                name_lower = name.lower()
                for i, h in enumerate(headers):
                    if name_lower in h.lower():
                        return i
                return -1

            col_pdb = _col("pdb")
            col_hchain = _col("hchain")
            col_lchain = _col("lchain")
            col_antigen_chain = _col("antigen_chain")
            col_antigen_name = _col("antigen_name")
            col_resolution = _col("resolution")
            col_method = _col("method")

            target_lower = target_name.strip().lower()
            seen_pdbs: set[str] = set()

            for line in lines[1:]:
                fields = line.split("\t")
                if len(fields) <= max(
                    col_pdb, col_antigen_name, col_hchain, col_lchain
                ):
                    continue

                antigen_name = (
                    fields[col_antigen_name] if col_antigen_name >= 0 else ""
                )
                if target_lower not in antigen_name.lower():
                    continue

                pdb_id = fields[col_pdb] if col_pdb >= 0 else ""
                if not pdb_id or pdb_id in seen_pdbs:
                    continue
                seen_pdbs.add(pdb_id)

                heavy_chain = fields[col_hchain] if col_hchain >= 0 else ""
                light_chain = fields[col_lchain] if col_lchain >= 0 else ""
                antigen_chains = (
                    fields[col_antigen_chain] if col_antigen_chain >= 0 else ""
                )
                resolution = fields[col_resolution] if col_resolution >= 0 else ""
                method = fields[col_method] if col_method >= 0 else ""

                # Try to parse resolution as float.
                try:
                    resolution_val = float(resolution) if resolution.strip() else None
                except (ValueError, AttributeError):
                    resolution_val = None

                binders.append({
                    "pdb_id": pdb_id.upper(),
                    "heavy_chain": heavy_chain.strip(),
                    "light_chain": light_chain.strip(),
                    "antigen_chains": antigen_chains.strip(),
                    "antigen_name": antigen_name.strip(),
                    "resolution": resolution_val,
                    "method": method.strip(),
                })

                if len(binders) >= max_structures:
                    break

        except Exception as exc:
            errors.append(f"SAbDab query failed: {exc}")

    # Build consensus info if we have results.
    consensus_info: dict[str, Any] = {}
    if binders:
        has_light = sum(1 for b in binders if b.get("light_chain"))
        consensus_info = {
            "total_found": len(binders),
            "nanobody_fraction": round(
                (len(binders) - has_light) / len(binders), 2
            )
            if binders
            else 0,
            "has_light_chain_fraction": round(has_light / len(binders), 2)
            if binders
            else 0,
        }

    result: dict[str, Any] = {
        "target": target_name,
        "num_known_binders": len(binders),
        "binders": binders,
        "consensus_info": consensus_info,
    }
    if errors:
        result["warnings"] = errors

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 4: research_find_similar_targets
# ---------------------------------------------------------------------------


@mcp.tool()
async def research_find_similar_targets(
    uniprot_accession: str,
    max_results: int = 5,
) -> str:
    """Find proteins similar to a given UniProt accession.

    Uses the UniProt ID mapping / BLAST service to identify sequence
    homologs of the query protein.

    Args:
        uniprot_accession: UniProt accession (e.g. "P01375").
        max_results: Maximum number of similar proteins to return (default 5, max 20).

    Returns:
        JSON with query_accession and list of similar proteins with
        accession, name, identity_pct (None — sequence alignment not
            available via REST search; length_similarity_pct is provided
            as a proxy), length_similarity_pct, and organism.
    """
    if not uniprot_accession.strip():
        return _error("uniprot_accession must not be empty.")

    max_results = min(max(1, max_results), 20)
    accession = uniprot_accession.strip().upper()
    errors: list[str] = []
    similar: list[dict[str, Any]] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Strategy: search UniProt for proteins in the same family by
        # querying with the accession to get the protein family, then
        # searching for related entries.
        try:
            # First, get info about the query protein.
            params = {
                "query": f"accession:{accession}",
                "format": "json",
                "size": "1",
                "fields": "accession,protein_name,organism_name,length,cc_similarity,keyword",
            }
            resp = await client.get(UNIPROT_SEARCH_URL, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            results_list = data.get("results", [])
            if not results_list:
                return _error(f"UniProt accession {accession} not found.")

            entry = results_list[0]

            # Extract protein family keywords for similarity search.
            keywords = entry.get("keywords", [])
            family_keywords = [
                kw.get("name", "")
                for kw in keywords
                if kw.get("category") == "Molecular function"
                or kw.get("category") == "Biological process"
            ]

            # Get protein name for searching.
            protein_desc = entry.get("proteinDescription", {})
            rec_name = protein_desc.get("recommendedName", {})
            full_name = rec_name.get("fullName", {}).get("value", "")

            # Search for similar proteins using the protein name as query.
            search_query = full_name if full_name else accession
            sim_params = {
                "query": f"({search_query}) NOT accession:{accession}",
                "format": "json",
                "size": str(max_results),
                "fields": "accession,protein_name,organism_name,length,sequence",
            }
            sim_resp = await client.get(
                UNIPROT_SEARCH_URL, params=sim_params, timeout=TIMEOUT
            )
            sim_resp.raise_for_status()
            sim_data = sim_resp.json()

            for sim_entry in sim_data.get("results", []):
                sim_acc = sim_entry.get("primaryAccession", "")
                sim_desc = sim_entry.get("proteinDescription", {})
                sim_rec = sim_desc.get("recommendedName", {})
                sim_name = sim_rec.get("fullName", {}).get("value", "")
                if not sim_name:
                    sub_names = sim_desc.get("submissionNames", [])
                    if sub_names:
                        sim_name = sub_names[0].get("fullName", {}).get("value", "")

                sim_organism = (
                    sim_entry.get("organism", {}).get("scientificName", "")
                )
                sim_length = sim_entry.get("sequence", {}).get("length", 0)

                # We cannot compute true sequence identity without alignment,
                # but we can note the length similarity as a rough proxy.
                query_length = entry.get("sequence", {}).get("length", 0)
                length_similarity = (
                    round(min(sim_length, query_length) / max(sim_length, query_length, 1) * 100, 1)
                )

                similar.append({
                    "accession": sim_acc,
                    "name": sim_name,
                    "identity_pct": None,  # True BLAST identity not available via REST search
                    "length_similarity_pct": length_similarity,
                    "sequence_length": sim_length,
                    "organism": sim_organism,
                })

        except Exception as exc:
            errors.append(f"UniProt similarity search failed: {exc}")

    result: dict[str, Any] = {
        "query_accession": accession,
        "similar": similar,
    }
    if errors:
        result["warnings"] = errors

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 5: research_check_novelty
# ---------------------------------------------------------------------------


def _sequence_identity(seq1: str, seq2: str) -> float:
    """Compute pairwise sequence identity (alignment-free).

    Mirrors ``proteus_cli.screening.diversity.sequence_identity`` so that
    the MCP server stays self-contained and does not import from the CLI
    package (which may not be installed in the server's venv).
    """
    max_len = max(len(seq1), len(seq2))
    if max_len == 0:
        return 0.0
    min_len = min(len(seq1), len(seq2))
    matches = sum(a == b for a, b in zip(seq1[:min_len], seq2[:min_len]))
    return matches / max_len


def _parse_fasta_sequences(fasta_text: str) -> dict[str, str]:
    """Parse a FASTA string into {header: sequence} dict.

    Returns a mapping from the *full* header line (minus '>') to the
    concatenated sequence lines.
    """
    sequences: dict[str, str] = {}
    current_header: str | None = None
    current_seq: list[str] = []

    for line in fasta_text.splitlines():
        line = line.strip()
        if line.startswith(">"):
            if current_header is not None:
                sequences[current_header] = "".join(current_seq)
            current_header = line[1:]
            current_seq = []
        elif current_header is not None:
            current_seq.append(line)

    if current_header is not None:
        sequences[current_header] = "".join(current_seq)

    return sequences


async def _fetch_chain_sequence(
    client: httpx.AsyncClient,
    pdb_id: str,
    chain_id: str,
    warnings: list[str] | None = None,
) -> str | None:
    """Fetch the amino-acid sequence for a specific chain from RCSB.

    Downloads the FASTA for the PDB entry and returns the sequence
    whose header matches the requested chain.  Returns *None* when the
    chain is not found in the entry.  Network errors are distinguished
    from missing chains: if *warnings* is provided, network failures
    are appended to it rather than silently swallowed.
    """
    try:
        url = f"{RCSB_FASTA_URL}/{pdb_id.upper()}"
        resp = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()

        sequences = _parse_fasta_sequences(resp.text)

        # RCSB FASTA headers look like:
        #   >1ABC_1|Chain A|...
        #   >1ABC_2|Chain B|...
        # Match by chain letter (case-insensitive).
        chain_upper = chain_id.strip().upper()
        for header, seq in sequences.items():
            # Match "|Chain X|" pattern
            if re.search(rf'\|Chain\s+{re.escape(chain_upper)}\b', header, re.IGNORECASE):
                return seq
            # Also match "{PDB}_{N}|Chains {X},{Y}|" for multi-chain entries
            if re.search(rf'\|Chains?\s+[^|]*\b{re.escape(chain_upper)}\b', header, re.IGNORECASE):
                return seq

        # Chain not found in the entry — this is not an error
        return None
    except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
        # Network / HTTP error — not "sequence unavailable"
        if warnings is not None:
            warnings.append(f"Network error fetching {pdb_id} chain {chain_id}: {exc}")
        return None
    except Exception as exc:
        if warnings is not None:
            warnings.append(f"Unexpected error fetching {pdb_id} chain {chain_id}: {exc}")
        return None


@mcp.tool()
async def research_check_novelty(
    design_sequence: str,
    target_name: str,
    identity_threshold: float = 0.9,
) -> str:
    """Check a design sequence for novelty against known SAbDab antibodies.

    Queries SAbDab for known antibodies against the target, fetches their
    heavy-chain sequences from RCSB PDB, and computes pairwise sequence
    identity against the design.

    Use this to screen candidate designs for potential IP overlap with
    existing antibodies before advancing to experimental validation.

    Args:
        design_sequence: Amino-acid sequence of the designed antibody /
            nanobody (heavy chain).
        target_name: Target protein name to filter SAbDab entries
            (e.g. "TNF-alpha", "PD-L1").
        identity_threshold: Maximum tolerated sequence identity (0.0-1.0).
            Designs sharing identity above this value with any known binder
            are flagged as non-novel.  Default 0.9 (90%).

    Returns:
        JSON with: novel (bool), closest_match_pdb, closest_identity,
        matches_above_threshold (count), ip_warning (str), and details list.
    """
    design_seq = design_sequence.strip().upper()
    if not design_seq:
        return _error("design_sequence must not be empty.")
    if not target_name.strip():
        return _error("target_name must not be empty.")

    identity_threshold = max(0.0, min(1.0, identity_threshold))

    # ---- Step 1: Query SAbDab for known binders (reuse existing logic) ----
    binders: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            params = {"all": "true"}
            resp = await client.get(
                SABDAB_SUMMARY_URL,
                params=params,
                timeout=60.0,
                headers={"Accept": "text/tab-separated-values"},
            )
            resp.raise_for_status()
            tsv_text = resp.text

            lines = tsv_text.strip().split("\n")
            if len(lines) < 2:
                return json.dumps({
                    "novel": True,
                    "closest_match_pdb": "",
                    "closest_identity": 0.0,
                    "matches_above_threshold": 0,
                    "ip_warning": "",
                    "details": [],
                    "warnings": ["SAbDab returned no data rows."],
                }, indent=2)

            headers = lines[0].split("\t")

            def _col(name: str) -> int:
                name_lower = name.lower()
                for i, h in enumerate(headers):
                    if name_lower in h.lower():
                        return i
                return -1

            col_pdb = _col("pdb")
            col_hchain = _col("hchain")
            col_antigen_name = _col("antigen_name")

            target_lower = target_name.strip().lower()
            seen_pdbs: set[str] = set()

            for line in lines[1:]:
                fields = line.split("\t")
                if len(fields) <= max(col_pdb, col_antigen_name, col_hchain):
                    continue

                antigen_name = fields[col_antigen_name] if col_antigen_name >= 0 else ""
                if target_lower not in antigen_name.lower():
                    continue

                pdb_id = fields[col_pdb] if col_pdb >= 0 else ""
                heavy_chain = fields[col_hchain] if col_hchain >= 0 else ""
                if not pdb_id or pdb_id in seen_pdbs:
                    continue
                seen_pdbs.add(pdb_id)

                binders.append({
                    "pdb_id": pdb_id.upper(),
                    "heavy_chain": heavy_chain.strip(),
                })

                # Cap at 50 to avoid excessive RCSB requests
                if len(binders) >= 50:
                    break

        except Exception as exc:
            errors.append(f"SAbDab query failed: {exc}")

        # ---- Step 2: Fetch sequences and compute identity ----
        comparisons: list[dict[str, Any]] = []
        closest_pdb = ""
        closest_identity = 0.0
        matches_above = 0

        for binder in binders:
            pdb_id = binder["pdb_id"]
            chain_id = binder["heavy_chain"]

            if not chain_id:
                continue

            seq = await _fetch_chain_sequence(client, pdb_id, chain_id, warnings=errors)
            if not seq:
                comparisons.append({
                    "pdb_id": pdb_id,
                    "chain": chain_id,
                    "identity": None,
                    "note": "sequence unavailable",
                })
                continue

            identity = _sequence_identity(design_seq, seq.upper())

            comparisons.append({
                "pdb_id": pdb_id,
                "chain": chain_id,
                "identity": round(identity, 4),
            })

            if identity > closest_identity:
                closest_identity = identity
                closest_pdb = pdb_id

            if identity > identity_threshold:
                matches_above += 1

    novel = matches_above == 0
    ip_warning = ""
    if not novel:
        ip_warning = (
            f"Design shares >{identity_threshold:.0%} identity with {closest_pdb}"
        )

    result: dict[str, Any] = {
        "novel": novel,
        "closest_match_pdb": closest_pdb,
        "closest_identity": round(closest_identity, 4),
        "matches_above_threshold": matches_above,
        "ip_warning": ip_warning,
        "num_known_binders_checked": len(binders),
        "details": comparisons,
    }
    if errors:
        result["warnings"] = errors

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
