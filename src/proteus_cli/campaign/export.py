"""Export campaign designs in standard formats."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_campaign_log(campaign_dir: str) -> dict[str, Any]:
    """Load campaign_log.json from a campaign directory."""
    log_path = Path(campaign_dir).resolve() / "campaign_log.json"
    if not log_path.exists():
        raise FileNotFoundError(f"Campaign log not found: {log_path}")
    return json.loads(log_path.read_text())


def _collect_scores(campaign_dir: str) -> list[dict[str, Any]]:
    """Collect all score files from the screening directory."""
    scores_dir = Path(campaign_dir).resolve() / "screening"
    all_scores: list[dict[str, Any]] = []
    if not scores_dir.exists():
        return all_scores
    for score_file in sorted(scores_dir.glob("*_scores.json")):
        try:
            data = json.loads(score_file.read_text())
            if isinstance(data, list):
                all_scores.extend(data)
        except (json.JSONDecodeError, OSError):
            continue
    return all_scores


def _collect_design_sequences(campaign_dir: str) -> list[dict[str, Any]]:
    """Collect design sequences from the designs directory."""
    designs_dir = Path(campaign_dir).resolve() / "designs"
    sequences: list[dict[str, Any]] = []
    if not designs_dir.exists():
        return sequences
    # Look for FASTA files
    for fasta_file in sorted(designs_dir.glob("*.fasta")):
        try:
            text = fasta_file.read_text()
            current_header = ""
            current_seq: list[str] = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith(">"):
                    if current_header and current_seq:
                        sequences.append({
                            "name": current_header.lstrip(">").strip(),
                            "sequence": "".join(current_seq),
                            "source": fasta_file.name,
                        })
                    current_header = line
                    current_seq = []
                elif line:
                    current_seq.append(line)
            if current_header and current_seq:
                sequences.append({
                    "name": current_header.lstrip(">").strip(),
                    "sequence": "".join(current_seq),
                    "source": fasta_file.name,
                })
        except OSError:
            continue
    # Look for JSON design files
    for json_file in sorted(designs_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "sequence" in entry:
                        sequences.append({
                            "name": entry.get("name", entry.get("design_name", json_file.stem)),
                            "sequence": entry["sequence"],
                            "source": json_file.name,
                        })
            elif isinstance(data, dict) and "sequence" in data:
                sequences.append({
                    "name": data.get("name", data.get("design_name", json_file.stem)),
                    "sequence": data["sequence"],
                    "source": json_file.name,
                })
        except (json.JSONDecodeError, OSError):
            continue
    return sequences


def export_fasta(campaign_dir: str, output_path: str = "") -> str:
    """Export top candidates as FASTA.

    Merges sequences from the designs directory with score data from screening.
    Writes a FASTA file with score annotations in the header line.

    Args:
        campaign_dir: Path to the campaign directory.
        output_path: Optional output file path. If empty, writes to campaign_dir/exports/.

    Returns:
        The path to the written FASTA file.
    """
    campaign_path = Path(campaign_dir).resolve()
    sequences = _collect_design_sequences(campaign_dir)
    scores = _collect_scores(campaign_dir)

    # Index scores by design name for annotation
    score_map: dict[str, dict[str, Any]] = {}
    for s in scores:
        name = s.get("design_name", s.get("name", ""))
        if name:
            score_map[name] = s

    if not output_path:
        export_dir = campaign_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = str(export_dir / f"designs_{timestamp}.fasta")

    lines: list[str] = []
    for seq in sequences:
        name = seq["name"]
        score_info = score_map.get(name, {})
        # Build header with available scores
        header_parts = [name]
        if score_info.get("ipsae"):
            header_parts.append(f"ipSAE={score_info['ipsae']:.3f}")
        if score_info.get("iptm"):
            header_parts.append(f"ipTM={score_info['iptm']:.3f}")
        if score_info.get("plddt"):
            header_parts.append(f"pLDDT={score_info['plddt']:.1f}")
        if score_info.get("status"):
            header_parts.append(f"status={score_info['status']}")
        lines.append(f">{' | '.join(header_parts)}")
        # Wrap sequence at 80 characters
        sequence = seq["sequence"]
        for i in range(0, len(sequence), 80):
            lines.append(sequence[i : i + 80])

    # If no sequences found in designs dir, try to export from scores directly
    if not lines:
        for s in scores:
            seq_val = s.get("sequence", "")
            if not seq_val:
                continue
            name = s.get("design_name", s.get("name", "unknown"))
            header_parts = [name]
            if s.get("ipsae"):
                header_parts.append(f"ipSAE={s['ipsae']:.3f}")
            if s.get("iptm"):
                header_parts.append(f"ipTM={s['iptm']:.3f}")
            lines.append(f">{' | '.join(header_parts)}")
            for i in range(0, len(seq_val), 80):
                lines.append(seq_val[i : i + 80])

    if not lines:
        return json.dumps({
            "exported": None,
            "format": "fasta",
            "warning": "No design sequences found in campaign — nothing to export.",
            "sequences_found": 0,
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")

    return output_path


def export_csv(campaign_dir: str, output_path: str = "") -> str:
    """Export all scored designs as CSV.

    Columns: design_name, sequence, ipsae, iptm, plddt, rmsd, liabilities, status.

    Args:
        campaign_dir: Path to the campaign directory.
        output_path: Optional output file path. If empty, writes to campaign_dir/exports/.

    Returns:
        The path to the written CSV file.
    """
    campaign_path = Path(campaign_dir).resolve()
    scores = _collect_scores(campaign_dir)
    sequences = _collect_design_sequences(campaign_dir)

    # Index sequences by name
    seq_map: dict[str, str] = {}
    for s in sequences:
        seq_map[s["name"]] = s["sequence"]

    if not output_path:
        export_dir = campaign_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = str(export_dir / f"designs_{timestamp}.csv")

    fieldnames = [
        "design_name",
        "sequence",
        "ipsae",
        "iptm",
        "plddt",
        "rmsd",
        "liabilities",
        "status",
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for s in scores:
        name = s.get("design_name", s.get("name", "unknown"))
        row = {
            "design_name": name,
            "sequence": s.get("sequence", seq_map.get(name, "")),
            "ipsae": s.get("ipsae", ""),
            "iptm": s.get("iptm", ""),
            "plddt": s.get("plddt", ""),
            "rmsd": s.get("rmsd", ""),
            "liabilities": ";".join(s.get("liabilities", [])) if isinstance(s.get("liabilities"), list) else s.get("liabilities", ""),
            "status": s.get("status", ""),
        }
        writer.writerow(row)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(buf.getvalue())
    return output_path


def export_campaign_summary(campaign_dir: str, output_path: str = "") -> str:
    """Export campaign summary as markdown.

    Includes: target info, parameters, each round's results, cost summary.

    Args:
        campaign_dir: Path to the campaign directory.
        output_path: Optional output file path. If empty, writes to campaign_dir/exports/.

    Returns:
        The path to the written markdown file.
    """
    campaign_path = Path(campaign_dir).resolve()
    log = _load_campaign_log(campaign_dir)
    scores = _collect_scores(campaign_dir)

    if not output_path:
        export_dir = campaign_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = str(export_dir / f"campaign_summary_{timestamp}.md")

    lines: list[str] = []

    # Header
    campaign_id = log.get("campaign_id", "unknown")
    lines.append(f"# Campaign Summary: {campaign_id}\n")
    lines.append(f"**Status**: {log.get('status', 'unknown')}")
    lines.append(f"**Created**: {log.get('created_at', 'N/A')}")
    lines.append(f"**Updated**: {log.get('updated_at', 'N/A')}")
    lines.append(f"**Iteration**: {log.get('iteration', 0)}\n")

    # Target info
    target = log.get("target", {})
    if target:
        lines.append("## Target\n")
        lines.append(f"| Field | Value |")
        lines.append(f"|-------|-------|")
        lines.append(f"| Name | {target.get('name', 'N/A')} |")
        lines.append(f"| PDB ID | {target.get('pdb_id', 'N/A')} |")
        lines.append(f"| Chain | {target.get('chain_id', 'N/A')} |")
        if target.get("uniprot_id"):
            lines.append(f"| UniProt | {target['uniprot_id']} |")
        lines.append("")

    # Design parameters
    lines.append("## Design Parameters\n")
    lines.append(f"- **Tool**: {log.get('tool', 'N/A')}")
    lines.append(f"- **Protocol**: {log.get('protocol', 'N/A')}")
    lines.append("")

    # Rounds
    rounds = log.get("rounds", [])
    if rounds:
        lines.append("## Rounds\n")
        for rnd in rounds:
            round_id = rnd.get("round_id", "?")
            lines.append(f"### Round {round_id}\n")
            lines.append(f"- **Status**: {rnd.get('state', 'unknown')}")
            lines.append(f"- **Started**: {rnd.get('started_at', 'N/A')}")
            if rnd.get("completed_at"):
                lines.append(f"- **Completed**: {rnd['completed_at']}")

            params = rnd.get("parameters", {})
            if params:
                lines.append(f"- **Parameters**: {json.dumps(params)}")

            runs = rnd.get("runs", [])
            if runs:
                lines.append("\n| Run ID | Scaffold | Status | Generated | Passed | Top ipTM | Top ipSAE |")
                lines.append("|--------|----------|--------|-----------|--------|----------|-----------|")
                for run in runs:
                    lines.append(
                        f"| {run.get('run_id', '?')[:12]} "
                        f"| {run.get('scaffold', 'N/A')} "
                        f"| {run.get('status', '?')} "
                        f"| {run.get('designs_generated', 0)} "
                        f"| {run.get('designs_passed', 0)} "
                        f"| {run.get('top_iptm', 0):.3f} "
                        f"| {run.get('top_ipsae', 0):.3f} |"
                    )
            lines.append("")

    # Scores summary
    if scores:
        lines.append("## Scores Summary\n")
        lines.append(f"Total scored designs: {len(scores)}\n")

        # Top 10 by ipSAE
        sorted_scores = sorted(
            scores,
            key=lambda s: float(s.get("ipsae", 0) or 0),
            reverse=True,
        )
        top_n = sorted_scores[:10]
        if top_n:
            lines.append("### Top 10 by ipSAE\n")
            lines.append("| Rank | Design | ipSAE | ipTM | pLDDT | Status |")
            lines.append("|------|--------|-------|------|-------|--------|")
            for i, s in enumerate(top_n, 1):
                name = s.get("design_name", s.get("name", "?"))
                lines.append(
                    f"| {i} "
                    f"| {name} "
                    f"| {float(s.get('ipsae', 0) or 0):.3f} "
                    f"| {float(s.get('iptm', 0) or 0):.3f} "
                    f"| {float(s.get('plddt', 0) or 0):.1f} "
                    f"| {s.get('status', 'N/A')} |"
                )
        lines.append("")

    # Cost summary
    costs = log.get("costs", {})
    if costs:
        lines.append("## Cost Summary\n")
        for key, value in costs.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # History
    history = log.get("history", [])
    if history:
        lines.append("## Status History\n")
        lines.append("| Timestamp | From | To | Reason |")
        lines.append("|-----------|------|----|--------|")
        for h in history:
            lines.append(
                f"| {h.get('timestamp', '?')} "
                f"| {h.get('from_status', 'N/A')} "
                f"| {h.get('to_status', '?')} "
                f"| {h.get('reason', '')} |"
            )
        lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")
    return output_path
