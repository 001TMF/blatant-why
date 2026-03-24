"""Sequence diversity analysis for candidate sets."""
from __future__ import annotations


def sequence_identity(seq1: str, seq2: str) -> float:
    """Compute pairwise sequence identity (simple alignment-free).

    Compares sequences position-by-position, truncating to the shorter
    length if they differ.  Returns the fraction of matching positions
    relative to the longer original sequence.

    Args:
        seq1: First amino acid sequence.
        seq2: Second amino acid sequence.

    Returns:
        Fraction of identical residues (0.0 to 1.0).
    """
    max_len = max(len(seq1), len(seq2))
    if max_len == 0:
        return 0.0
    min_len = min(len(seq1), len(seq2))
    matches = sum(a == b for a, b in zip(seq1[:min_len], seq2[:min_len]))
    return matches / max_len


def cluster_sequences(
    sequences: list[dict],
    identity_threshold: float = 0.9,
    key: str = "sequence",
) -> list[list[dict]]:
    """Cluster sequences by identity threshold (greedy).

    Each dict must have a *key* field with the amino acid sequence.
    Returns list of clusters, each cluster is a list of sequence dicts.

    Args:
        sequences: List of dicts each containing a sequence string.
        identity_threshold: Minimum identity to join an existing cluster.
        key: Dict key that holds the amino acid sequence string.

    Returns:
        List of clusters (each cluster is a list of sequence dicts).
    """
    clusters: list[list[dict]] = []
    for seq in sequences:
        placed = False
        for cluster in clusters:
            if sequence_identity(seq[key], cluster[0][key]) >= identity_threshold:
                cluster.append(seq)
                placed = True
                break
        if not placed:
            clusters.append([seq])
    return clusters


def diversity_report(
    sequences: list[dict],
    identity_threshold: float = 0.9,
) -> dict:
    """Generate diversity analysis report.

    Args:
        sequences: List of dicts, each with a ``"sequence"`` key.
        identity_threshold: Clustering identity threshold (0.0-1.0).

    Returns:
        Dict with num_sequences, num_clusters, diversity_ratio,
        avg_pairwise_identity, largest_cluster_size, singleton_clusters,
        and redundancy_warning flag.
    """
    if not sequences:
        return {"num_sequences": 0, "num_clusters": 0, "diversity_ratio": 0.0}

    clusters = cluster_sequences(sequences, identity_threshold)

    # Pairwise identity matrix (sample if too many)
    n = len(sequences)
    sample = sequences[:50] if n > 50 else sequences
    identities = []
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            identities.append(
                sequence_identity(sample[i]["sequence"], sample[j]["sequence"])
            )

    avg_identity = sum(identities) / len(identities) if identities else 0.0

    return {
        "num_sequences": n,
        "num_clusters": len(clusters),
        "diversity_ratio": len(clusters) / n,
        "avg_pairwise_identity": round(avg_identity, 3),
        "largest_cluster_size": max(len(c) for c in clusters),
        "singleton_clusters": sum(1 for c in clusters if len(c) == 1),
        "redundancy_warning": len(clusters) < n * 0.5,
    }


def format_diversity(report: dict) -> str:
    """Format diversity report as space-aligned text.

    Args:
        report: Output from :func:`diversity_report`.

    Returns:
        Multi-line formatted string for terminal display.
    """
    if report.get("num_sequences", 0) == 0:
        return "  Diversity Analysis\n  No sequences to analyze."

    lines = [
        "  Diversity Analysis",
        f"  Sequences          {report['num_sequences']}",
        f"  Unique clusters    {report['num_clusters']} (at {report.get('threshold', 90)}% identity)",
        f"  Diversity ratio    {report['diversity_ratio']:.2f}",
        f"  Avg pairwise ID    {report['avg_pairwise_identity']:.1%}",
        f"  Largest cluster    {report['largest_cluster_size']} sequences",
        f"  Singletons         {report['singleton_clusters']}",
    ]
    if report.get("redundancy_warning"):
        lines.append(
            "  WARNING: High redundancy — consider increasing alpha or adding scaffolds"
        )
    return "\n".join(lines)
