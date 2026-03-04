"""Proteus CLI — unified entry point for protein design tools."""
from __future__ import annotations

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="proteus")
def cli():
    """Proteus protein design agent CLI."""
    pass


@cli.command()
@click.argument("input_json", type=click.Path(exists=True))
@click.option("--model", default="base_default", help="Model name (base_default, base_20250630, mini)")
@click.option("--output-dir", default=None, help="Output directory")
@click.option("--gpu", default="0", help="GPU device IDs")
def fold(input_json, model, output_dir, gpu):
    """Run structure prediction with Protenix."""
    from proteus_cli.fold import run_fold

    result = run_fold(input_json, model=model, output_dir=output_dir, gpu_ids=gpu)
    click.echo(result.to_json())


@cli.command()
@click.argument("config", type=click.Path(exists=True))
@click.option("--preset", default="extended", type=click.Choice(["preview", "extended"]))
@click.option("--nproc", default=1, help="Processes per node")
@click.option("--gpu", default="0", help="GPU device IDs")
def protein(config, preset, nproc, gpu):
    """Run de novo binder design with PXDesign."""
    from proteus_cli.protein import run_protein_design

    result = run_protein_design(config, preset=preset, nproc=nproc, gpu_ids=gpu)
    click.echo(result.to_json())


@cli.command()
@click.argument("spec", type=click.Path(exists=True))
@click.option("--gpu", default="0", help="GPU device IDs")
def ab(spec, gpu):
    """Run antibody/nanobody design with Proteus-AB."""
    from proteus_cli.antibody import run_antibody_design

    result = run_antibody_design(spec, gpu_ids=gpu)
    click.echo(result.to_json())


@cli.command()
@click.argument("tool_name")
def check(tool_name):
    """Verify a Proteus tool installation."""
    from proteus_cli.common import validate_tool_path

    try:
        path = validate_tool_path(tool_name)
        click.echo(f"OK: {tool_name} found at {path}")
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"ERROR: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("sequence")
def screen(sequence):
    """Run liability + developability screening on a sequence."""
    import json

    from proteus_cli.screening.developability import assess_developability
    from proteus_cli.screening.liabilities import compute_net_charge, scan_liabilities

    liabilities = scan_liabilities(sequence)
    charge = compute_net_charge(sequence)
    report = assess_developability(sequence, liabilities=liabilities)

    output = {
        "sequence_length": len(sequence),
        "net_charge": round(charge, 2),
        "liabilities": [
            {
                "type": l.type,
                "position": l.position,
                "motif": l.motif,
                "severity": l.severity,
                "description": l.description,
            }
            for l in liabilities
        ],
        "developability": {
            "overall_risk": report.overall_risk,
            "hydrophobic_fraction": round(report.hydrophobic_fraction, 4),
            "proline_fraction": round(report.proline_fraction, 4),
            "glycine_fraction": round(report.glycine_fraction, 4),
            "liability_count": report.liability_count,
            "flags": report.flags,
        },
    }
    click.echo(json.dumps(output, indent=2))


@cli.command()
@click.argument("npz_path", type=click.Path(exists=True))
@click.option("--design-chains", required=True, help="Comma-separated design chain asym_ids")
@click.option("--target-chains", required=True, help="Comma-separated target chain asym_ids")
def score(npz_path, design_chains, target_chains):
    """Compute ipSAE score from a Protenix NPZ file."""
    import json
    from pathlib import Path

    from proteus_cli.scoring.ipsae import interpret_ipsae, score_npz

    d_ids = [int(x) for x in design_chains.split(",")]
    t_ids = [int(x) for x in target_chains.split(",")]

    scores = score_npz(Path(npz_path), d_ids, t_ids)
    scores["interpretation"] = interpret_ipsae(scores["design_ipsae_min"])

    click.echo(json.dumps(scores, indent=2))
