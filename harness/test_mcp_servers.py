#!/usr/bin/env python3
"""Test MCP servers individually by importing and calling their tool functions directly."""
import asyncio
import importlib.util
import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"


def load_server(name: str, server_dir: str):
    """Load a server.py from a specific directory as a unique module."""
    spec = importlib.util.spec_from_file_location(
        f"mcp_server_{name}",
        os.path.join(server_dir, "server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Ensure the server dir is on sys.path for relative imports
    old_path = sys.path.copy()
    sys.path.insert(0, server_dir)
    sys.path.insert(0, PROJECT_ROOT)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path = old_path
    return mod


async def test_pdb_server():
    """Test pdb MCP server tools."""
    print("\n" + "=" * 60)
    print("TEST: pdb MCP server")
    print("=" * 60)

    mod = load_server("pdb", os.path.join(PROJECT_ROOT, "mcp_servers", "pdb"))

    # Test 1: pdb_search
    print("\n--- Test 1: pdb_search('TNF-alpha', max_results=5) ---")
    t0 = time.time()
    try:
        result = await mod.pdb_search("TNF-alpha", max_results=5)
        elapsed = time.time() - t0
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        elif isinstance(data, list):
            print(f"  {PASS if len(data) > 0 else WARN} Results: {len(data)}")
            for e in data[:3]:
                print(f"         - {e['pdb_id']}: {e.get('title','')[:60]}")
                print(f"           Method: {e.get('method','?')}, Resolution: {e.get('resolution','?')}")
        else:
            print(f"  {WARN} Unexpected type: {type(data)}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")

    # Test 2: pdb_fetch_structure
    print("\n--- Test 2: pdb_fetch_structure('7S4S') ---")
    t0 = time.time()
    try:
        result = await mod.pdb_fetch_structure("7S4S")
        elapsed = time.time() - t0
        data = json.loads(result)
        if "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        else:
            print(f"  {PASS} PDB ID: {data.get('pdb_id','?')}")
            print(f"         Title: {data.get('title','')[:60]}")
            print(f"         Method: {data.get('method','?')}")
            print(f"         Resolution: {data.get('resolution','?')}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")


async def test_uniprot_server():
    """Test uniprot MCP server tools."""
    print("\n" + "=" * 60)
    print("TEST: uniprot MCP server")
    print("=" * 60)

    mod = load_server("uniprot", os.path.join(PROJECT_ROOT, "mcp_servers", "uniprot"))

    # Test 1: uniprot_search
    print("\n--- Test 1: uniprot_search('TNF-alpha human', max_results=3) ---")
    t0 = time.time()
    try:
        result = await mod.uniprot_search("TNF-alpha human", max_results=3)
        elapsed = time.time() - t0
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        elif isinstance(data, list):
            print(f"  {PASS if len(data) > 0 else WARN} Results: {len(data)}")
            for e in data[:3]:
                print(f"         - {e.get('accession','?')}: {e.get('name','?')}")
                print(f"           Organism: {e.get('organism','?')}, Gene: {e.get('gene_name','?')}")
                print(f"           Length: {e.get('length','?')}, Reviewed: {e.get('reviewed','?')}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")

    # Test 2: uniprot_fetch_protein (TNF-alpha is P01375)
    print("\n--- Test 2: uniprot_fetch_protein('P01375') ---")
    t0 = time.time()
    try:
        result = await mod.uniprot_fetch_protein("P01375")
        elapsed = time.time() - t0
        data = json.loads(result)
        if "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        else:
            print(f"  {PASS} Accession: {data.get('accession','?')}")
            print(f"         Name: {data.get('name','?')}")
            print(f"         Gene: {data.get('gene_name','?')}")
            print(f"         Organism: {data.get('organism','?')}")
            print(f"         Length: {data.get('length','?')}")
            func_desc = data.get("function_description", "")
            if func_desc:
                print(f"         Function: {func_desc[:100]}...")
            seq = data.get("sequence", "")
            if seq:
                print(f"         Sequence: {seq[:40]}... ({len(seq)} aa)")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")


async def test_research_server():
    """Test proteus-research MCP server tools."""
    print("\n" + "=" * 60)
    print("TEST: proteus-research MCP server")
    print("=" * 60)

    mod = load_server("research", os.path.join(PROJECT_ROOT, "mcp_servers", "research"))

    # Test 1: research_get_target_info
    print("\n--- Test 1: research_get_target_info('TNF-alpha') ---")
    t0 = time.time()
    try:
        result = await mod.research_get_target_info("TNF-alpha")
        elapsed = time.time() - t0
        data = json.loads(result)
        if "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        elif data.get("uniprot", {}).get("accession"):
            uni = data["uniprot"]
            print(f"  {PASS} UniProt accession: {uni['accession']}")
            print(f"         Name: {uni.get('name', 'N/A')}")
            print(f"         Organism: {uni.get('organism', 'N/A')}")
            print(f"         Length: {uni.get('sequence_length', 'N/A')}")
            print(f"         Gene names: {uni.get('gene_names', [])}")
            print(f"         PDB entries: {data.get('num_known_structures', 0)}")
            if data.get("pdb_entries"):
                for e in data["pdb_entries"][:3]:
                    print(f"           - {e['pdb_id']}: {e.get('title', '')[:60]}")
            print(f"         Function: {uni.get('function','')[:100]}...")
        else:
            print(f"  {WARN} No UniProt data returned")
        if data.get("warnings"):
            for w in data["warnings"]:
                print(f"  {WARN} {w}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")

    # Test 2: research_search_prior_art
    print("\n--- Test 2: research_search_prior_art('TNF-alpha', max_results=3) ---")
    t0 = time.time()
    try:
        result = await mod.research_search_prior_art("TNF-alpha", max_results=3)
        elapsed = time.time() - t0
        data = json.loads(result)
        if "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        else:
            pm_count = len(data.get("pubmed_results", []))
            br_count = len(data.get("biorxiv_results", []))
            print(f"  {PASS if pm_count > 0 else WARN} PubMed results: {pm_count}")
            for p in data.get("pubmed_results", [])[:2]:
                print(f"         - [{p.get('pmid','')}] {p.get('title','')[:60]}")
                print(f"           Authors: {p.get('authors','?')}, Year: {p.get('year','?')}")
            print(f"  {PASS if br_count > 0 else WARN} bioRxiv results: {br_count}")
            for b in data.get("biorxiv_results", [])[:2]:
                print(f"         - {b.get('title','')[:60]}")
        if data.get("warnings"):
            for w in data["warnings"]:
                print(f"  {WARN} {w}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")

    # Test 3: research_analyze_known_binders (SAbDab via research server)
    print("\n--- Test 3: research_analyze_known_binders('TNF-alpha', max_structures=5) ---")
    t0 = time.time()
    try:
        result = await mod.research_analyze_known_binders("TNF-alpha", max_structures=5)
        elapsed = time.time() - t0
        data = json.loads(result)
        if "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        else:
            n = data.get("num_known_binders", 0)
            print(f"  {PASS if n > 0 else WARN} Known binders: {n}")
            for b in data.get("binders", [])[:3]:
                print(f"         - {b['pdb_id']}: H={b.get('heavy_chain','?')}, "
                      f"L={b.get('light_chain','?')}, "
                      f"Ag={b.get('antigen_name','')[:30]}, "
                      f"Res={b.get('resolution','?')}")
            if data.get("consensus_info"):
                ci = data["consensus_info"]
                print(f"         Nanobody fraction: {ci.get('nanobody_fraction', 'N/A')}")
                print(f"         Has light chain fraction: {ci.get('has_light_chain_fraction', 'N/A')}")
        if data.get("warnings"):
            for w in data["warnings"]:
                print(f"  {WARN} {w}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")


async def test_sabdab_server():
    """Test sabdab MCP server tools."""
    print("\n" + "=" * 60)
    print("TEST: sabdab MCP server")
    print("=" * 60)

    mod = load_server("sabdab", os.path.join(PROJECT_ROOT, "mcp_servers", "sabdab"))

    # Test: sabdab_search_by_antigen
    print("\n--- Test: sabdab_search_by_antigen('Tumor necrosis factor', max_results=5) ---")
    t0 = time.time()
    try:
        result = await mod.sabdab_search_by_antigen("Tumor necrosis factor", max_results=5)
        elapsed = time.time() - t0
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            print(f"  {FAIL} Error: {data['error']}")
        elif isinstance(data, dict):
            total = data.get("total_results", 0)
            showing = data.get("showing", 0)
            results = data.get("results", [])
            print(f"  {PASS if total > 0 else WARN} Total matches: {total}, showing: {showing}")
            for r in results[:3]:
                print(f"         - {r.get('pdb_id','?')}: "
                      f"H={r.get('heavy_chain','?')}, "
                      f"L={r.get('light_chain','?')}, "
                      f"Ag={r.get('antigen_name','?')[:40]}, "
                      f"Species={r.get('species','?')}")
        print(f"  Elapsed: {elapsed:.1f}s")
    except Exception as e:
        print(f"  {FAIL} Exception: {type(e).__name__}: {e}")


async def test_campaign_server():
    """Test campaign MCP server — import check only."""
    print("\n" + "=" * 60)
    print("TEST: proteus-campaign MCP server (import check)")
    print("=" * 60)

    try:
        mod = load_server("campaign", os.path.join(PROJECT_ROOT, "mcp_servers", "campaign"))
        tools = [
            "campaign_create", "campaign_get", "campaign_update_status",
            "campaign_add_round", "campaign_update_round", "campaign_record_scores",
            "campaign_get_summary", "campaign_get_cost_estimate",
            "campaign_export_fasta", "campaign_export_csv",
            "campaign_log_decision", "campaign_get_decisions",
            "campaign_generate_visualization", "campaign_suggest_next_round",
        ]
        found = []
        missing = []
        for t in tools:
            if hasattr(mod, t):
                found.append(t)
            else:
                missing.append(t)
        print(f"  {PASS} Imported successfully, {len(found)}/{len(tools)} tools found")
        if missing:
            print(f"  {WARN} Missing tools: {', '.join(missing)}")
    except ImportError as e:
        print(f"  {FAIL} Import error: {e}")
    except Exception as e:
        print(f"  {FAIL} Unexpected error: {type(e).__name__}: {e}")


async def main():
    print("=" * 60)
    print("PROTEUS MCP SERVER DIRECT TEST SUITE")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")

    await test_pdb_server()
    await test_uniprot_server()
    await test_research_server()
    await test_sabdab_server()
    await test_campaign_server()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
