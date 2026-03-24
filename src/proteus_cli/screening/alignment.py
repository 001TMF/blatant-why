"""Sequence alignment utilities for candidate comparison.

Provides pairwise alignment, CDR-focused alignment matrices, and
star-based multiple alignment using BioPython's ``PairwiseAligner``.
"""
from __future__ import annotations

from Bio.Align import PairwiseAligner


# ---------------------------------------------------------------------------
# Module-level aligner (reused across calls)
# ---------------------------------------------------------------------------

def _make_aligner() -> PairwiseAligner:
    """Create a PairwiseAligner configured for global identity scoring."""
    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.match_score = 1.0
    aligner.mismatch_score = 0.0
    aligner.open_gap_score = -2.0
    aligner.extend_gap_score = -0.5
    return aligner


_ALIGNER = _make_aligner()


# ---------------------------------------------------------------------------
# 1. pairwise_align
# ---------------------------------------------------------------------------


def _extract_aligned_sequences(alignment) -> tuple[str, str]:
    """Build gapped aligned strings from a BioPython Alignment object.

    Uses the ``indices`` attribute: a 2-row numpy array where -1 marks
    gap positions.  This is reliable across BioPython versions, unlike
    parsing ``str(alignment)`` which includes labels and coordinates.
    """
    indices = alignment.indices  # shape (2, alignment_length)
    target = str(alignment.target)
    query = str(alignment.query)
    chars1: list[str] = []
    chars2: list[str] = []
    for col in range(indices.shape[1]):
        idx1 = int(indices[0][col])
        idx2 = int(indices[1][col])
        chars1.append(target[idx1] if idx1 >= 0 else "-")
        chars2.append(query[idx2] if idx2 >= 0 else "-")
    return "".join(chars1), "".join(chars2)


def pairwise_align(seq1: str, seq2: str) -> dict:
    """Align two sequences using BioPython PairwiseAligner (global).

    Args:
        seq1: First amino acid sequence.
        seq2: Second amino acid sequence.

    Returns:
        Dict with ``score``, ``identity`` (fraction), ``aligned_seq1``,
        ``aligned_seq2``, ``alignment_length``, and ``num_identical``.
    """
    if not seq1 or not seq2:
        return {
            "score": 0.0,
            "identity": 0.0,
            "aligned_seq1": seq1 or "",
            "aligned_seq2": seq2 or "",
            "alignment_length": 0,
            "num_identical": 0,
        }

    s1 = seq1.upper()
    s2 = seq2.upper()
    alignments = _ALIGNER.align(s1, s2)
    best = alignments[0]

    aligned_seq1, aligned_seq2 = _extract_aligned_sequences(best)

    aln_len = len(aligned_seq1)
    num_identical = sum(
        a == b
        for a, b in zip(aligned_seq1, aligned_seq2)
        if a != "-" and b != "-"
    )
    identity = num_identical / aln_len if aln_len > 0 else 0.0

    return {
        "score": float(best.score),
        "identity": round(identity, 4),
        "aligned_seq1": aligned_seq1,
        "aligned_seq2": aligned_seq2,
        "alignment_length": aln_len,
        "num_identical": num_identical,
    }


# ---------------------------------------------------------------------------
# 2. cdr_align
# ---------------------------------------------------------------------------


def cdr_align(
    designs: list[dict],
    cdr_key: str = "cdr3_sequence",
) -> dict:
    """Pairwise CDR3 identity matrix across a design set.

    Args:
        designs: List of dicts, each containing a CDR3 sequence under
            *cdr_key*.
        cdr_key: Dict key for the CDR3 amino acid string.

    Returns:
        Dict with ``matrix`` (list of lists, symmetric identity matrix),
        ``labels`` (list of design names or indices), and ``n``.
    """
    seqs = [d.get(cdr_key, "") for d in designs]
    labels = [d.get("name", d.get("design_name", f"design_{i}")) for i, d in enumerate(designs)]
    n = len(seqs)

    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            result = pairwise_align(seqs[i], seqs[j])
            matrix[i][j] = result["identity"]
            matrix[j][i] = result["identity"]

    return {
        "matrix": matrix,
        "labels": labels,
        "n": n,
    }


# ---------------------------------------------------------------------------
# 3. multiple_align (star alignment from centroid)
# ---------------------------------------------------------------------------


def multiple_align(
    sequences: list[dict],
    key: str = "sequence",
) -> dict:
    """Star alignment of multiple sequences using the centroid.

    Selects the sequence with the highest sum of pairwise scores as the
    centroid, then aligns all others to it and merges into a multiple
    sequence alignment (MSA).

    Args:
        sequences: List of dicts, each with an amino acid sequence under
            *key*.
        key: Dict key for the amino acid string.

    Returns:
        Dict with ``consensus``, ``msa`` (list of aligned strings),
        ``labels``, ``centroid_index``, and ``n``.
    """
    seqs = [d.get(key, "") for d in sequences]
    labels = [d.get("name", d.get("design_name", f"seq_{i}")) for i, d in enumerate(sequences)]
    n = len(seqs)

    if n == 0:
        return {"consensus": "", "msa": [], "labels": [], "centroid_index": -1, "n": 0}
    if n == 1:
        return {"consensus": seqs[0], "msa": [seqs[0]], "labels": labels, "centroid_index": 0, "n": 1}

    # Find centroid: sequence with highest total pairwise score
    score_sums = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            result = pairwise_align(seqs[i], seqs[j])
            score_sums[i] += result["score"]
            score_sums[j] += result["score"]

    centroid_idx = max(range(n), key=lambda i: score_sums[i])
    centroid_seq = seqs[centroid_idx]

    # Align each sequence to the centroid
    pairwise_results = []
    for i in range(n):
        if i == centroid_idx:
            pairwise_results.append(None)
        else:
            pairwise_results.append(pairwise_align(centroid_seq, seqs[i]))

    # Build MSA by merging gap positions from centroid alignments.
    # Collect the centroid's aligned form from each pairwise alignment
    # to determine the union of gap positions.
    centroid_aligned_forms = []
    other_aligned_forms = []
    for i in range(n):
        if i == centroid_idx:
            continue
        res = pairwise_results[i]
        assert res is not None
        centroid_aligned_forms.append(res["aligned_seq1"])
        other_aligned_forms.append((i, res["aligned_seq2"]))

    # Simple approach: use the centroid sequence itself as the reference
    # and insert gaps where the best pairwise alignment places them.
    # For a proper star alignment we re-align to the centroid and keep
    # the centroid ungapped (since it's the center star).
    msa = [""] * n
    msa[centroid_idx] = centroid_seq

    for i in range(n):
        if i == centroid_idx:
            continue
        res = pairwise_results[i]
        assert res is not None
        msa[i] = res["aligned_seq2"]

    # Pad all to same length
    max_len = max(len(s) for s in msa) if msa else 0
    msa = [s.ljust(max_len, "-") for s in msa]

    # Build consensus (most common residue at each position, '-' excluded)
    consensus_chars: list[str] = []
    for col in range(max_len):
        counts: dict[str, int] = {}
        for row in range(n):
            ch = msa[row][col] if col < len(msa[row]) else "-"
            if ch != "-":
                counts[ch] = counts.get(ch, 0) + 1
        if counts:
            consensus_chars.append(max(counts, key=lambda c: counts[c]))
        else:
            consensus_chars.append("-")

    return {
        "consensus": "".join(consensus_chars),
        "msa": msa,
        "labels": labels,
        "centroid_index": centroid_idx,
        "n": n,
    }


# ---------------------------------------------------------------------------
# 4. format_alignment
# ---------------------------------------------------------------------------


def format_alignment(result: dict) -> str:
    """Format an alignment result as space-aligned text output.

    Accepts the output from any of :func:`pairwise_align`,
    :func:`cdr_align`, or :func:`multiple_align` and returns a
    human-readable text block.

    Args:
        result: Dict returned by one of the alignment functions.

    Returns:
        Multi-line formatted string for terminal display.
    """
    lines: list[str] = []

    # Pairwise alignment result
    if "aligned_seq1" in result and "aligned_seq2" in result:
        lines.append("  Pairwise Alignment")
        lines.append(f"  Score            {result['score']:.1f}")
        lines.append(f"  Identity         {result['identity']:.1%}")
        lines.append(f"  Length           {result['alignment_length']}")
        lines.append(f"  Identical        {result['num_identical']}")
        lines.append("")
        lines.append(f"  Seq1  {result['aligned_seq1']}")
        lines.append(f"  Seq2  {result['aligned_seq2']}")
        # Match line
        match_line = "".join(
            "|" if a == b and a != "-" else " "
            for a, b in zip(result["aligned_seq1"], result["aligned_seq2"])
        )
        lines.insert(-1, f"        {match_line}")
        return "\n".join(lines)

    # CDR identity matrix
    if "matrix" in result and "labels" in result and "msa" not in result:
        lines.append("  CDR Identity Matrix")
        labels = result["labels"]
        n = result["n"]
        # Header row
        header = "  " + " " * 14 + "  ".join(f"{l[:8]:>8}" for l in labels)
        lines.append(header)
        for i in range(n):
            row = f"  {labels[i][:12]:<14}" + "  ".join(
                f"{result['matrix'][i][j]:8.1%}" for j in range(n)
            )
            lines.append(row)
        return "\n".join(lines)

    # Multiple alignment (MSA)
    if result.get("type") == "msa" and not result.get("labels"):
        return "  No sequences to align."
    if "msa" in result and "labels" in result:
        lines.append("  Multiple Sequence Alignment (Star)")
        lines.append(f"  Sequences        {result['n']}")
        lines.append(f"  Centroid         {result['labels'][result['centroid_index']]}")
        lines.append("")
        max_label = max((len(l) for l in result["labels"]), default=0)
        max_label = min(max_label, 20)
        for i, (label, seq) in enumerate(zip(result["labels"], result["msa"])):
            marker = " *" if i == result["centroid_index"] else "  "
            lines.append(f"  {label[:max_label]:<{max_label}}{marker}  {seq}")
        lines.append("")
        lines.append(f"  {'Consensus':<{max_label}}    {result['consensus']}")
        return "\n".join(lines)

    return "  (Unknown alignment result format)"
