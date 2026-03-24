"""Pareto front extraction for multi-objective design ranking."""
from __future__ import annotations


def is_dominated(a: dict, b: dict, objectives: list[tuple[str, str]]) -> bool:
    """Check if design b dominates design a on all objectives.

    objectives: list of (metric_name, "maximize"|"minimize")
    """
    dominated = True
    strictly_better = False
    for metric, direction in objectives:
        # Skip comparisons where either design is missing the metric
        if metric not in a or metric not in b:
            continue
        va = a[metric]
        vb = b[metric]
        if direction == "maximize":
            if vb < va:
                dominated = False
            if vb > va:
                strictly_better = True
        else:
            if vb > va:
                dominated = False
            if vb < va:
                strictly_better = True
    return dominated and strictly_better


def pareto_front(
    designs: list[dict],
    objectives: list[tuple[str, str]] | None = None,
) -> list[dict]:
    """Extract Pareto-optimal designs (non-dominated front).

    Default objectives: maximize ipSAE, maximize ipTM, minimize liabilities.
    """
    if objectives is None:
        objectives = [
            ("ipsae_min", "maximize"),
            ("iptm", "maximize"),
            ("liabilities", "minimize"),
        ]

    if not designs:
        return []

    front: list[dict] = []
    for i, d in enumerate(designs):
        dominated_by_any = False
        for j, other in enumerate(designs):
            if i != j and is_dominated(d, other, objectives):
                dominated_by_any = True
                break
        if not dominated_by_any:
            d_copy = dict(d)
            d_copy["pareto_rank"] = 0
            front.append(d_copy)

    # Annotate trade-offs
    for d in front:
        annotations: list[str] = []
        for metric, direction in objectives:
            values = [f.get(metric, 0) for f in front]
            val = d.get(metric, 0)
            if direction == "maximize" and val == max(values):
                annotations.append(f"Best {metric}")
            elif direction == "minimize" and val == min(values):
                annotations.append(f"Best {metric}")
        d["tradeoff"] = "; ".join(annotations) if annotations else "Balanced"

    return front


def format_pareto(
    front: list[dict],
    objectives: list[tuple[str, str]] | None = None,
) -> str:
    """Format Pareto front as a human-readable table."""
    if objectives is None:
        objectives = [
            ("ipsae_min", "maximize"),
            ("iptm", "maximize"),
            ("liabilities", "minimize"),
        ]

    if not front:
        return "  No Pareto-optimal designs found."

    header_cols = ["Design"] + [o[0] for o in objectives] + ["Trade-off"]
    lines = ["  Pareto-Optimal Candidates", ""]

    # Header
    header = "  " + "  ".join(f"{c:<16}" for c in header_cols)
    lines.append(header)
    lines.append("  " + "\u2500" * len(header))

    for d in front:
        name = d.get("design_name", d.get("name", "?"))[:16]
        vals = [name]
        for metric, _ in objectives:
            v = d.get(metric, 0)
            vals.append(f"{v:.3f}" if isinstance(v, float) else str(v))
        vals.append(d.get("tradeoff", "")[:30])
        lines.append("  " + "  ".join(f"{v:<16}" for v in vals))

    lines.append("")
    lines.append(
        f"  {len(front)} Pareto-optimal designs from {len(front)} on front 0"
    )
    return "\n".join(lines)
