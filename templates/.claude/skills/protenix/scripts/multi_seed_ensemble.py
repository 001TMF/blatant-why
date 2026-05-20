"""multi_seed_ensemble.py — Aggregate Protenix outputs across multiple seeds.

Purpose
-------
Given a Protenix output tree for a single prediction name (containing one or
more `seed_<int>/` subdirectories, each with one or more
`*_summary_confidence_sample_*.json` files), compute:

- Per-metric summary statistics (mean, std, min, max) across every
  (seed, sample) record.
- An agreement metric — fraction of records in the median ipTM bin
  (low / mid / high).
- A pointer to the best (seed, sample) by `ranking_score`.

Two artefacts are written:

- `ensemble_summary.json` — the aggregated metrics + best pointer.
- `ensemble_ranked.csv` — one row per (seed, sample), sorted by
  `ranking_score` desc.

Inputs
------
- Output directory of a single Protenix prediction, e.g.
  `<output-root>/<name>/`. The script auto-discovers all
  `seed_*/` subdirectories below it.

Outputs
-------
- JSON summary at `--summary-json`.
- Ranked CSV at `--ranked-csv`.

Example
-------
    python multi_seed_ensemble.py \\
        --output-dir /tmp/fold_run/output/binder_target_complex \\
        --summary-json /tmp/fold_run/output/binder_target_complex/ensemble_summary.json \\
        --ranked-csv  /tmp/fold_run/output/binder_target_complex/ensemble_ranked.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:
    sys.exit("Install with: pip install numpy")

METRICS: tuple[str, ...] = ("iptm", "ptm", "plddt", "ranking_score")
SEED_DIR_RE = re.compile(r"^seed_(\d+)$")
SAMPLE_FILE_RE = re.compile(r"_summary_confidence_sample_(\d+)\.json$")


def _fail(message: str) -> None:
    """Print a single error line and exit non-zero."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def _unwrap(value: Any) -> float | None:
    """Coerce a Protenix metric value to a float.

    Protenix may emit metrics as either a bare float or a single-element list
    (e.g. `0.83` vs `[0.83]`). Returns `None` if the value is missing or
    not convertible.
    """
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def discover_records(output_dir: Path) -> list[dict[str, Any]]:
    """Scan an `<output-dir>/<name>/` tree and return one record per sample.

    Each record has keys: `seed`, `sample`, `path`, plus one float per metric
    in `METRICS` (may be None if the metric was absent or unparseable).
    """
    if not output_dir.is_dir():
        _fail(f"output directory not found: {output_dir}")

    records: list[dict[str, Any]] = []
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir():
            continue
        m = SEED_DIR_RE.match(child.name)
        if not m:
            continue
        seed = int(m.group(1))
        for json_path in sorted(child.glob("*_summary_confidence_sample_*.json")):
            sm = SAMPLE_FILE_RE.search(json_path.name)
            if not sm:
                continue
            sample = int(sm.group(1))
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"WARN: skipping unreadable {json_path}: {exc}", file=sys.stderr)
                continue
            rec: dict[str, Any] = {
                "seed": seed,
                "sample": sample,
                "path": str(json_path),
            }
            for metric in METRICS:
                rec[metric] = _unwrap(payload.get(metric))
            records.append(rec)
    return records


def summarise_metric(values: list[float]) -> dict[str, float | int]:
    """Return mean / std / min / max / n for a list of floats."""
    if not values:
        return {"n": 0, "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "max": float("nan")}
    arr = np.array(values, dtype=float)
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=0)),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def agreement_score(iptm_values: list[float]) -> float:
    """Fraction of ipTM values falling in the same low/mid/high bin as the median.

    Bins: low < 0.5, mid in [0.5, 0.7), high >= 0.7. Returns 1.0 for n <= 1.
    """
    if len(iptm_values) <= 1:
        return 1.0

    def bin_of(v: float) -> str:
        if v < 0.5:
            return "low"
        if v < 0.7:
            return "mid"
        return "high"

    median = float(np.median(iptm_values))
    target = bin_of(median)
    matches = sum(1 for v in iptm_values if bin_of(v) == target)
    return matches / len(iptm_values)


def pick_best(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the record with the highest `ranking_score` (None if all missing)."""
    scored = [r for r in records if r.get("ranking_score") is not None]
    if not scored:
        return None
    return max(scored, key=lambda r: r["ranking_score"])


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Construct the full ensemble summary payload."""
    per_metric: dict[str, dict[str, float | int]] = {}
    for metric in METRICS:
        vals = [r[metric] for r in records if r.get(metric) is not None]
        per_metric[metric] = summarise_metric(vals)

    iptm_vals = [r["iptm"] for r in records if r.get("iptm") is not None]
    summary: dict[str, Any] = {
        "n_records": len(records),
        "seeds": sorted({r["seed"] for r in records}),
        "metrics": per_metric,
        "agreement_iptm": agreement_score(iptm_vals),
    }
    best = pick_best(records)
    if best is not None:
        summary["best"] = {
            "seed": best["seed"],
            "sample": best["sample"],
            "ranking_score": best["ranking_score"],
            "iptm": best["iptm"],
            "ptm": best["ptm"],
            "plddt": best["plddt"],
            "path": best["path"],
        }
    return summary


def write_summary(summary: dict[str, Any], path: Path) -> None:
    """Write the summary payload as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def write_ranked_csv(records: list[dict[str, Any]], path: Path) -> None:
    """Write one row per (seed, sample), sorted by ranking_score desc."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def sort_key(r: dict[str, Any]) -> float:
        rs = r.get("ranking_score")
        # Records with no ranking_score sink to the bottom.
        return rs if rs is not None else -math.inf

    rows_sorted = sorted(records, key=sort_key, reverse=True)
    fieldnames = ["seed", "sample", "iptm", "ptm", "plddt", "ranking_score", "path"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows_sorted:
            writer.writerow({k: r.get(k) for k in fieldnames})


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate Protenix confidence outputs across multiple seeds / samples "
            "and emit a JSON summary + ranked CSV."
        ),
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Path to <output-root>/<name>/ containing one or more seed_<int>/ subdirs.",
    )
    parser.add_argument(
        "--summary-json",
        required=True,
        type=Path,
        help="Where to write the ensemble summary JSON.",
    )
    parser.add_argument(
        "--ranked-csv",
        required=True,
        type=Path,
        help="Where to write the ranked CSV (one row per (seed, sample)).",
    )
    args = parser.parse_args()

    records = discover_records(args.output_dir)
    if not records:
        _fail(
            f"no Protenix confidence JSONs found under {args.output_dir} "
            "(expected seed_<int>/*_summary_confidence_sample_*.json)"
        )

    summary = build_summary(records)
    write_summary(summary, args.summary_json)
    write_ranked_csv(records, args.ranked_csv)

    print(
        f"✓ Ensemble aggregated: {len(records)} (seed,sample) records "
        f"→ {args.summary_json}"
    )
    print(f"✓ Ranked CSV written: {args.ranked_csv}")


if __name__ == "__main__":
    main()
