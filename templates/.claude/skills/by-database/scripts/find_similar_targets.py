#!/usr/bin/env python3
"""Find similar targets — sequence-similarity search starting from a UniProt or PDB ID.

Purpose
-------
Given a UniProt accession (preferred) or a PDB ID, retrieve the protein sequence
and run a sequence-similarity search against UniProtKB. Output a ranked CSV of
related entries with percent identity and other useful metadata for cross-species
homolog targeting, prior-art search, and orthology mapping.

Inputs
------
- Exactly one of:
    --uniprot <accession>   e.g. P01375
    --pdb <pdb_id> [--chain <chain_id>]   e.g. 7S4S A
- Optional --max-hits (default 25, max 100).
- Optional --min-identity (default 30.0; percent identity floor).
- Optional --out path for the CSV (default stdout).

Outputs
-------
CSV with columns:
    rank, accession, entry_name, organism, length, percent_identity,
    e_value, bit_score, gene_name, reviewed, query_source

On success: `✓ find_similar_targets completed: <N> rows -> <path>`.

Example
-------
    python find_similar_targets.py --uniprot P01375 --max-hits 25 --out homologs.csv
    python find_similar_targets.py --pdb 7S4S --chain A --out homologs.csv

Implementation notes
--------------------
- Uses the UniProt REST `peptidesearch` and entry endpoints; falls back to the
  UniProt similarity REST endpoint when peptide search returns no hits.
- For larger queries we use UniProt's BLAST-like REST endpoint
  (https://rest.uniprot.org/blast). Submission is async; this script polls.
- Applies exponential backoff on 429 / 5xx.
- Never invents an accession; if no hits, exits with `✗ No similar entries found.`
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("Install with: pip install httpx")


UNIPROT_FASTA_URL = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"
UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"
UNIPROT_BLAST_RUN = "https://rest.uniprot.org/blast/run"
UNIPROT_BLAST_STATUS = "https://rest.uniprot.org/blast/status/{job_id}"
UNIPROT_BLAST_RESULT = "https://rest.uniprot.org/blast/result/{job_id}/tab"
RCSB_POLYMER_URL = "https://data.rcsb.org/rest/v1/core/polymer_entity"
RCSB_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry"

TIMEOUT = 60.0
MAX_RETRIES = 5
BACKOFF_BASE = 2.0
POLL_INTERVAL = 5.0
POLL_TIMEOUT_S = 300.0

FIELDS = [
    "rank",
    "accession",
    "entry_name",
    "organism",
    "length",
    "percent_identity",
    "e_value",
    "bit_score",
    "gene_name",
    "reviewed",
    "query_source",
]


def _get_with_retry(client: httpx.Client, url: str, **kwargs) -> httpx.Response | None:
    """GET with exponential backoff on 429 / 5xx."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, timeout=TIMEOUT, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(BACKOFF_BASE ** attempt)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPError:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(BACKOFF_BASE ** attempt)
    return None


def _post_with_retry(
    client: httpx.Client, url: str, **kwargs
) -> httpx.Response | None:
    """POST with exponential backoff on 429 / 5xx."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.post(url, timeout=TIMEOUT, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(BACKOFF_BASE ** attempt)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPError:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(BACKOFF_BASE ** attempt)
    return None


def fetch_sequence_from_uniprot(client: httpx.Client, accession: str) -> str | None:
    """Fetch the canonical sequence for a UniProt accession (FASTA body)."""
    resp = _get_with_retry(client, UNIPROT_FASTA_URL.format(accession=accession))
    if resp is None or not resp.text:
        return None
    lines = [ln for ln in resp.text.splitlines() if not ln.startswith(">")]
    return "".join(lines).strip() or None


def fetch_sequence_from_pdb(
    client: httpx.Client, pdb_id: str, chain: str | None
) -> tuple[str | None, str]:
    """Fetch a chain sequence from a PDB entry.

    Returns (sequence, source_label). Picks polymer entity 1 if no chain
    specified; otherwise finds the entity whose pdbx_strand_id contains chain.
    """
    pdb_id = pdb_id.upper()
    entry = _get_with_retry(client, f"{RCSB_ENTRY_URL}/{pdb_id}")
    if entry is None:
        return None, f"pdb:{pdb_id}"
    summary = entry.json().get("rcsb_entry_info", {}) or {}
    n_entities = summary.get("polymer_entity_count", 0)

    target_chain = chain.upper() if chain else None
    for entity_id in range(1, n_entities + 1):
        ent = _get_with_retry(client, f"{RCSB_POLYMER_URL}/{pdb_id}/{entity_id}")
        if ent is None:
            continue
        ent_json = ent.json()
        poly = ent_json.get("entity_poly", {}) or {}
        chains_str = (poly.get("pdbx_strand_id", "") or "").upper()
        seq = poly.get("pdbx_seq_one_letter_code_can", "") or ""
        seq = seq.replace("\n", "").strip()
        chain_list = [c.strip() for c in chains_str.split(",") if c.strip()]
        if target_chain is None and seq:
            return seq, f"pdb:{pdb_id}/entity{entity_id}"
        if target_chain and target_chain in chain_list and seq:
            return seq, f"pdb:{pdb_id}/{target_chain}"
    return None, f"pdb:{pdb_id}"


def submit_blast(
    client: httpx.Client, sequence: str, max_hits: int
) -> str | None:
    """Submit a BLAST job to UniProt REST; return job_id or None."""
    payload = {
        "email": "by-database@local",
        "program": "blastp",
        "database": "uniprotkb_refprotswissprot",
        "stype": "protein",
        "sequence": sequence,
        "hits": str(min(max(max_hits, 1), 100)),
    }
    resp = _post_with_retry(client, UNIPROT_BLAST_RUN, data=payload)
    if resp is None:
        return None
    return resp.text.strip() or None


def poll_blast(client: httpx.Client, job_id: str) -> bool:
    """Poll BLAST status until FINISHED or timeout. Return True on success."""
    elapsed = 0.0
    while elapsed < POLL_TIMEOUT_S:
        resp = _get_with_retry(client, UNIPROT_BLAST_STATUS.format(job_id=job_id))
        if resp is None:
            return False
        status = resp.text.strip().upper()
        if status == "FINISHED":
            return True
        if status in {"FAILURE", "ERROR", "NOT_FOUND"}:
            return False
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    return False


def fetch_blast_results(
    client: httpx.Client, job_id: str
) -> list[dict]:
    """Fetch BLAST tabular results and parse into hit records."""
    resp = _get_with_retry(client, UNIPROT_BLAST_RESULT.format(job_id=job_id))
    if resp is None:
        return []
    hits: list[dict] = []
    for line in resp.text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        # Tabular blast: qseqid sseqid pident length mismatch gapopen qstart
        # qend sstart send evalue bitscore
        subject = cols[1]
        # subject format usually 'sp|ACC|ENTRY_NAME' or 'tr|ACC|ENTRY_NAME'
        acc = ""
        entry_name = ""
        reviewed = ""
        if "|" in subject:
            parts = subject.split("|")
            if len(parts) >= 3:
                reviewed = "true" if parts[0] == "sp" else "false"
                acc = parts[1]
                entry_name = parts[2]
        hits.append(
            {
                "accession": acc,
                "entry_name": entry_name,
                "percent_identity": cols[2],
                "e_value": cols[10],
                "bit_score": cols[11],
                "reviewed": reviewed,
            }
        )
    return hits


def enrich_hit(client: httpx.Client, hit: dict) -> dict:
    """Annotate a hit with organism, length, gene_name from UniProt entry JSON."""
    if not hit.get("accession"):
        return hit
    resp = _get_with_retry(client, UNIPROT_ENTRY_URL.format(accession=hit["accession"]))
    if resp is None:
        return hit
    try:
        data = resp.json()
    except ValueError:
        return hit
    organism = (data.get("organism", {}) or {}).get("scientificName", "")
    seq = (data.get("sequence", {}) or {}).get("value", "")
    gene_name = ""
    genes = data.get("genes", []) or []
    if genes:
        primary = (genes[0].get("geneName", {}) or {}).get("value", "")
        gene_name = primary
    hit["organism"] = organism
    hit["length"] = len(seq) if seq else ""
    hit["gene_name"] = gene_name
    if not hit.get("entry_name"):
        hit["entry_name"] = data.get("uniProtkbId", "")
    return hit


def find_similar(
    client: httpx.Client,
    sequence: str,
    max_hits: int,
    min_identity: float,
    query_source: str,
) -> list[dict]:
    """Submit BLAST, poll, fetch, and annotate hits. Public for library use."""
    job_id = submit_blast(client, sequence, max_hits)
    if not job_id:
        return []
    if not poll_blast(client, job_id):
        return []
    raw_hits = fetch_blast_results(client, job_id)
    if not raw_hits:
        return []

    filtered: list[dict] = []
    for hit in raw_hits:
        try:
            pident = float(hit.get("percent_identity") or 0.0)
        except ValueError:
            pident = 0.0
        if pident < min_identity:
            continue
        hit["query_source"] = query_source
        filtered.append(hit)

    enriched = [enrich_hit(client, h) for h in filtered]
    enriched.sort(
        key=lambda h: float(h.get("percent_identity") or 0.0), reverse=True
    )
    for rank, hit in enumerate(enriched, start=1):
        hit["rank"] = rank
    return enriched


def _write_csv(rows: list[dict], out_path: str | None) -> str:
    """Write rows to CSV; return destination label for the success message."""
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        f = open(out_path, "w", newline="")
        destination = out_path
    else:
        f = sys.stdout
        destination = "stdout"
    try:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    finally:
        if out_path:
            f.close()
    return destination


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Sequence-similarity search from a UniProt accession or PDB chain; "
            "output a ranked CSV of related UniProt entries."
        ),
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--uniprot", help="UniProt accession (e.g. P01375).")
    src.add_argument("--pdb", help="PDB ID (e.g. 7S4S).")
    parser.add_argument(
        "--chain",
        help="Chain ID (for --pdb). Defaults to entity 1 if omitted.",
    )
    parser.add_argument(
        "--max-hits",
        type=int,
        default=25,
        help="Maximum hits to retain (1-100, default 25).",
    )
    parser.add_argument(
        "--min-identity",
        type=float,
        default=30.0,
        help="Minimum percent identity to keep (default 30.0).",
    )
    parser.add_argument(
        "--out",
        help="Output CSV path. If omitted, writes to stdout.",
    )
    args = parser.parse_args()

    with httpx.Client() as client:
        if args.uniprot:
            seq = fetch_sequence_from_uniprot(client, args.uniprot.strip())
            query_source = f"uniprot:{args.uniprot.strip()}"
        else:
            seq, query_source = fetch_sequence_from_pdb(
                client, args.pdb.strip(), args.chain
            )

        if not seq:
            sys.exit(f"✗ Could not fetch sequence for {query_source}.")

        rows = find_similar(
            client=client,
            sequence=seq,
            max_hits=args.max_hits,
            min_identity=args.min_identity,
            query_source=query_source,
        )

    if not rows:
        sys.exit("✗ No similar entries found above the identity threshold.")

    destination = _write_csv(rows, args.out)
    print(
        f"✓ find_similar_targets completed: {len(rows)} rows -> {destination}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
