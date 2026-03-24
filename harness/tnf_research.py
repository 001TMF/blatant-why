#!/usr/bin/env python3
"""Comprehensive TNF-alpha research using MCP servers."""

import asyncio
import importlib.util
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_server(name: str, server_dir: str):
    """Load a server.py from a specific directory as a unique module."""
    spec = importlib.util.spec_from_file_location(
        f"mcp_server_{name}",
        os.path.join(server_dir, "server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    old_path = sys.path.copy()
    sys.path.insert(0, server_dir)
    sys.path.insert(0, PROJECT_ROOT)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path = old_path
    return mod

async def comprehensive_tnf_research():
    """Conduct comprehensive TNF-alpha research."""
    print("="*80)
    print("COMPREHENSIVE TNF-ALPHA DRUG TARGET RESEARCH REPORT")
    print("="*80)

    # Load working servers (avoiding research server due to syntax error)
    try:
        pdb_mod = load_server("pdb", os.path.join(PROJECT_ROOT, "mcp_servers", "pdb"))
        uniprot_mod = load_server("uniprot", os.path.join(PROJECT_ROOT, "mcp_servers", "uniprot"))
        sabdab_mod = load_server("sabdab", os.path.join(PROJECT_ROOT, "mcp_servers", "sabdab"))
        print("MCP servers loaded successfully")
    except Exception as e:
        print(f"Error loading servers: {e}")
        return

    # Section 1: UniProt Analysis
    print("\n" + "="*60)
    print("1. TNF-ALPHA PROTEIN INFORMATION")
    print("="*60)

    try:
        # Search for TNF-alpha variants
        search_result = await uniprot_mod.uniprot_search("TNF-alpha human", max_results=5)
        search_data = json.loads(search_result)

        print("UniProt Search Results:")
        if isinstance(search_data, list):
            for i, entry in enumerate(search_data):
                print(f"  {i+1}. {entry.get('accession', '?')} - {entry.get('name', '?')}")
                print(f"     Gene: {entry.get('gene_name', '?')} | Length: {entry.get('length', '?')} aa")
                print(f"     Reviewed: {entry.get('reviewed', '?')}")

        # Get detailed info for main TNF-alpha (P01375)
        print(f"\nDetailed Information for Human TNF-alpha (P01375):")
        detail_result = await uniprot_mod.uniprot_fetch_protein("P01375")
        detail_data = json.loads(detail_result)

        if 'error' not in detail_data:
            print(f"  Accession: {detail_data.get('accession', '?')}")
            print(f"  Full Name: {detail_data.get('name', '?')}")
            print(f"  Gene Symbol: {detail_data.get('gene_name', '?')}")
            print(f"  Length: {detail_data.get('length', '?')} amino acids")
            print(f"  Organism: {detail_data.get('organism', '?')}")

            # Function description
            func = detail_data.get('function_description', '')
            if func:
                print(f"  Function: {func}")

            # Domains
            domains = detail_data.get('domains', [])
            if domains:
                print(f"  Protein Domains ({len(domains)}):")
                for domain in domains:
                    print(f"    - {domain.get('name', '?')} (residues {domain.get('start', '?')}-{domain.get('end', '?')})")

            # Sequence
            seq = detail_data.get('sequence', '')
            if seq:
                print(f"  Sequence: {seq}")
                print(f"  Sequence Length: {len(seq)} amino acids")

    except Exception as e:
        print(f"Error in UniProt analysis: {e}")

    # Section 2: PDB Structure Analysis
    print("\n" + "="*60)
    print("2. TNF-ALPHA CRYSTAL STRUCTURES")
    print("="*60)

    try:
        pdb_result = await pdb_mod.pdb_search("TNF-alpha tumor necrosis factor", max_results=10)
        pdb_data = json.loads(pdb_result)

        if isinstance(pdb_data, list):
            print(f"Found {len(pdb_data)} PDB structures:")
            print("  PDB ID | Title | Method | Resolution")
            print("  " + "-"*58)

            for entry in pdb_data:
                pdb_id = entry.get('pdb_id', '?')
                title = entry.get('title', '')[:40] + '...' if len(entry.get('title', '')) > 40 else entry.get('title', '')
                method = entry.get('method', '?')
                resolution = entry.get('resolution', '?')
                print(f"  {pdb_id:<6} | {title:<40} | {method:<12} | {resolution}")

        # Get detailed structure info for a key TNF structure
        if isinstance(pdb_data, list) and pdb_data:
            key_structure = None
            for entry in pdb_data:
                if 'tumor necrosis factor' in entry.get('title', '').lower():
                    key_structure = entry.get('pdb_id')
                    break

            if not key_structure and pdb_data:
                key_structure = pdb_data[0].get('pdb_id')

            if key_structure:
                print(f"\nDetailed Analysis of {key_structure}:")
                struct_result = await pdb_mod.pdb_fetch_structure(key_structure)
                struct_data = json.loads(struct_result)

                if 'error' not in struct_data:
                    print(f"  Title: {struct_data.get('title', '?')}")
                    print(f"  Method: {struct_data.get('method', '?')}")
                    print(f"  Resolution: {struct_data.get('resolution', '?')}")
                    print(f"  Release Date: {struct_data.get('release_date', '?')}")

                    authors = struct_data.get('authors', [])
                    if authors:
                        print(f"  Authors: {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''}")

    except Exception as e:
        print(f"Error in PDB analysis: {e}")

    # Section 3: SAbDab Antibody Analysis
    print("\n" + "="*60)
    print("3. EXISTING TNF-ALPHA ANTIBODIES")
    print("="*60)

    try:
        sabdab_result = await sabdab_mod.sabdab_search_by_antigen("Tumor necrosis factor", max_results=10)
        sabdab_data = json.loads(sabdab_result)

        if isinstance(sabdab_data, dict):
            total = sabdab_data.get("total_results", 0)
            results = sabdab_data.get("results", [])

            print(f"Found {total} anti-TNF-alpha antibodies in SAbDab:")
            print("  PDB ID | Heavy | Light | Antigen | Species | Resolution")
            print("  " + "-"*62)

            for ab in results:
                pdb_id = ab.get('pdb_id', '?')
                heavy = ab.get('heavy_chain', '?')
                light = ab.get('light_chain', '?')
                antigen = ab.get('antigen_name', '')[:15] + '...' if len(ab.get('antigen_name', '')) > 15 else ab.get('antigen_name', '')
                species = ab.get('species', '?')
                resolution = ab.get('resolution', '?')

                print(f"  {pdb_id:<6} | {heavy:<5} | {light:<5} | {antigen:<15} | {species:<7} | {resolution}")

    except Exception as e:
        print(f"Error in SAbDab analysis: {e}")

    # Section 4: Summary and Recommendations
    print("\n" + "="*60)
    print("4. THERAPEUTIC LANDSCAPE & DESIGN OPPORTUNITIES")
    print("="*60)

    print("Known TNF-alpha Therapeutic Antibodies:")
    therapeutic_abs = [
        ("Adalimumab", "Humira", "Human IgG1", "Fully human", "Approved 2002"),
        ("Infliximab", "Remicade", "Chimeric IgG1", "Mouse/Human", "Approved 1998"),
        ("Etanercept", "Enbrel", "Fusion protein", "TNFR2-Fc", "Approved 1998"),
        ("Golimumab", "Simponi", "Human IgG1", "Fully human", "Approved 2009"),
        ("Certolizumab", "Cimzia", "Humanized Fab'", "PEGylated", "Approved 2008")
    ]

    print("  Drug Name    | Brand    | Type         | Format      | Status")
    print("  " + "-"*57)
    for name, brand, ab_type, format_type, status in therapeutic_abs:
        print(f"  {name:<12} | {brand:<8} | {ab_type:<12} | {format_type:<11} | {status}")

    print("\nMechanism of Action:")
    print("  • TNF-alpha is a pro-inflammatory cytokine")
    print("  • Primarily produced by activated macrophages")
    print("  • Binds to TNFR1 (p55) and TNFR2 (p75) receptors")
    print("  • Triggers inflammatory cascade and apoptosis")
    print("  • Key target in autoimmune diseases")

    print("\nClinical Applications:")
    print("  • Rheumatoid arthritis")
    print("  • Psoriasis and psoriatic arthritis")
    print("  • Ankylosing spondylitis")
    print("  • Inflammatory bowel disease (Crohn's, UC)")
    print("  • Juvenile idiopathic arthritis")

    print("\nDesign Opportunities:")
    print("  • Improved pharmacokinetics (longer half-life)")
    print("  • Enhanced tissue penetration")
    print("  • Reduced immunogenicity")
    print("  • Alternative epitope targeting")
    print("  • Nanobody/single-domain formats")
    print("  • Bispecific approaches")
    print("  • Subcutaneous formulations")

    print("\nKey Structural Considerations:")
    print("  • TNF-alpha exists as homotrimer")
    print("  • Each monomer ~17 kDa, trimer ~51 kDa")
    print("  • β-sheet sandwich fold")
    print("  • Multiple epitopes available")
    print("  • Conformational flexibility important")

if __name__ == "__main__":
    asyncio.run(comprehensive_tnf_research())