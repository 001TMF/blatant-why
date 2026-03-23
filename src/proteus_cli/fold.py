"""Wrapper for proteus-fold (Protenix v1 structure prediction)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from proteus_cli.common import ToolResult, get_tool_env, run_command, validate_tool_path


def build_protenix_json(
    sequences: list[str] | list[dict[str, Any]],
    output_dir: str | Path,
    name: str = "prediction",
    seeds: list[int] | None = None,
    sample_count: int = 1,
) -> Path:
    """Build and write a Protenix-compatible JSON input file.

    Args:
        sequences: Either a list of amino-acid strings or a list of dicts
            with keys ``"sequence"`` and optional ``"type"``
            (e.g. ``"proteinChain"``, ``"ligand"``).
        output_dir: Directory where the JSON file will be written.
        name: Prediction job name embedded in the JSON.
        seeds: Model seeds (defaults to ``[42]``).
        sample_count: Number of diffusion samples per seed.

    Returns:
        Path to the written JSON file.
    """
    if seeds is None:
        seeds = [42]

    seq_entries: list[dict[str, Any]] = []
    for seq in sequences:
        if isinstance(seq, str):
            seq_entries.append(
                {"proteinChain": {"sequence": seq, "count": 1}}
            )
        elif isinstance(seq, dict):
            seq_type = seq.get("type", "proteinChain")
            entry_inner: dict[str, Any] = {"sequence": seq["sequence"], "count": 1}
            seq_entries.append({seq_type: entry_inner})
        else:
            raise TypeError(
                f"Each sequence must be a str or dict, got {type(seq).__name__}"
            )

    payload = [
        {
            "name": name,
            "sequences": seq_entries,
            "modelSeeds": seeds,
            "sampleCount": sample_count,
        }
    ]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "input.json"
    json_path.write_text(json.dumps(payload, indent=2))
    return json_path


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODELS: dict[str, str] = {
    "base_default": "protenix_base_default_v1.0.0",
    "base_20250630": "protenix_base_20250630_v1.0.0",
    "mini": "protenix_mini_default_v0.5.0",
    "tiny": "protenix_tiny_default_v0.5.0",
    "mini_esm": "protenix_mini_esm_v0.5.0",
}


# ---------------------------------------------------------------------------
# Run fold
# ---------------------------------------------------------------------------


def run_fold(
    input_json_path: str | Path,
    model: str = "base_default",
    output_dir: str | Path | None = None,
    gpu_ids: str = "0",
) -> ToolResult:
    """Run ``protenix pred`` for structure prediction.

    Args:
        input_json_path: Path to the Protenix JSON input file.
        model: Friendly model key from :data:`MODELS`.
        output_dir: Optional override for the output directory.
        gpu_ids: CUDA visible device IDs (comma-separated string).

    Returns:
        A :class:`ToolResult` describing the outcome.
    """
    tool_dir = validate_tool_path("protenix")

    model_name = MODELS.get(model)
    if model_name is None:
        return ToolResult(
            tool="protenix",
            status="error",
            error=f"Unknown model '{model}'. Available: {list(MODELS)}",
        )

    input_path = Path(input_json_path)
    if not input_path.exists():
        return ToolResult(
            tool="protenix",
            status="error",
            error=f"Input JSON not found: {input_path}",
        )

    cmd = [
        "protenix", "pred",
        "-i", str(input_path),
        "-n", model_name,
        "--use_default_params", "true",
        "--dtype", "bf16",
    ]
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-o", str(out)])

    env = get_tool_env("protenix")
    proc = run_command(cmd, cwd=tool_dir, env=env)

    if proc.returncode != 0:
        return ToolResult(
            tool="protenix",
            status="error",
            output_dir=Path(output_dir) if output_dir else None,
            error=proc.stderr or proc.stdout,
        )

    resolved_output = Path(output_dir) if output_dir else tool_dir / "output"
    metrics = parse_fold_output(resolved_output)
    return ToolResult(
        tool="protenix",
        status="success",
        output_dir=resolved_output,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------


def parse_fold_output(output_dir: str | Path) -> dict[str, Any]:
    """Extract confidence metrics from a Protenix prediction output directory.

    Protenix writes files named
    ``<name>_summary_confidence_sample_<rank>.json`` containing keys such as
    ``iptm``, ``ptm``, ``plddt``, and ``ranking_score``.

    Args:
        output_dir: Root output directory of a Protenix prediction run.

    Returns:
        A dict with best-sample metrics (``iptm``, ``ptm``, ``plddt``,
        ``ranking_score``) or an empty dict if no scores are found.
    """
    out = Path(output_dir)
    if not out.exists():
        return {}

    # Protenix writes *_summary_confidence_sample_*.json files,
    # potentially inside nested sub-directories.
    confidence_files = sorted(out.rglob("*_summary_confidence_sample_*.json"))
    if not confidence_files:
        return {}

    best_score: float | None = None
    best_metrics: dict[str, Any] = {}

    for fpath in confidence_files:
        try:
            data = json.loads(fpath.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        metrics: dict[str, Any] = {}
        for key in ("iptm", "ptm", "plddt", "ranking_score"):
            if key in data:
                val = data[key]
                # Values may be single-element lists from tensor serialisation.
                if isinstance(val, list):
                    val = val[0] if len(val) == 1 else val
                metrics[key] = val

        score = metrics.get("ranking_score")
        if score is not None and (best_score is None or score > best_score):
            best_score = score
            best_metrics = metrics

    return best_metrics
