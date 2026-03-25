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
    """Run antibody/nanobody design with BoltzGen."""
    from proteus_cli.antibody import run_antibody_design

    result = run_antibody_design(spec)
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


# ---------------------------------------------------------------------------
# Campaign management commands
# ---------------------------------------------------------------------------

@cli.group()
def campaign():
    """Manage design campaigns — plan, estimate, track, and iterate."""
    pass


@campaign.command("init")
@click.argument("config_yaml", type=click.Path(exists=True))
@click.option("--base-dir", default="campaigns", help="Base directory for campaign data")
def campaign_init(config_yaml, base_dir):
    """Create a new campaign from a YAML config file."""
    from proteus_cli.campaign.config import load_config
    from proteus_cli.campaign.cost import estimate_cost, format_cost_table
    from proteus_cli.campaign.funnel import estimate_funnel
    from proteus_cli.campaign.state import create_campaign

    config = load_config(config_yaml)
    state = create_campaign(config, base_dir=base_dir)

    cost = estimate_cost(config)
    funnel = estimate_funnel(config)

    click.echo(f"Campaign created: {state.campaign_id}")
    click.echo(f"  Target:   {config.target.name} ({config.target.pdb_id})")
    click.echo(f"  Tool:     {config.design.tool} / {config.design.protocol}")
    click.echo(f"  Status:   {state.status}")
    click.echo(f"  Est. cost: ${cost.total_cost_usd:,.2f}")
    click.echo(f"  Est. lab candidates: {funnel.lab_candidates}")
    click.echo(f"  Log: {base_dir}/{state.campaign_id}/campaign_log.json")


@campaign.command("estimate")
@click.argument("config_yaml", type=click.Path(exists=True))
def campaign_estimate(config_yaml):
    """Show cost and compute estimates for a campaign config."""
    from proteus_cli.campaign.config import load_config
    from proteus_cli.campaign.cost import estimate_cost, format_cost_table

    config = load_config(config_yaml)
    est = estimate_cost(config)

    click.echo(f"Campaign: {config.name}")
    click.echo(f"Tool: {config.design.tool} / {config.design.protocol}")
    click.echo(f"Difficulty: {config.target_difficulty}")
    click.echo()
    click.echo(format_cost_table(est))


@campaign.command("status")
@click.argument("campaign_dir", default=".", type=click.Path(exists=True))
def campaign_status(campaign_dir):
    """Show the current state of a campaign."""
    import json as _json
    from pathlib import Path

    from proteus_cli.campaign.state import load_campaign

    log_path = Path(campaign_dir)
    if log_path.is_dir():
        log_path = log_path / "campaign_log.json"

    if not log_path.exists():
        click.echo(f"No campaign_log.json found at {log_path}", err=True)
        raise SystemExit(1)

    state = load_campaign(str(log_path))

    click.echo(f"Campaign:   {state.campaign_id}")
    click.echo(f"Target:     {state.target.get('name', '—')}")
    click.echo(f"Tool:       {state.tool} / {state.protocol}")
    click.echo(f"Status:     {state.status}")
    click.echo(f"Iteration:  {state.iteration}")
    click.echo(f"Rounds:     {len(state.rounds)}")
    click.echo(f"Lab approved: {state.lab_approved}")
    click.echo(f"Created:    {state.created_at}")
    click.echo(f"Updated:    {state.updated_at}")

    if state.rounds:
        click.echo()
        click.echo("Rounds:")
        for r in state.rounds:
            total_gen = sum(run.designs_generated for run in r.runs)
            total_pass = sum(run.designs_passed for run in r.runs)
            click.echo(
                f"  Round {r.round_id}: {r.state}  "
                f"({len(r.runs)} runs, {total_gen} generated, {total_pass} passed)"
            )

    if state.history:
        click.echo()
        click.echo("Recent history:")
        for entry in state.history[-5:]:
            click.echo(
                f"  {entry.get('timestamp', '—')}  "
                f"{entry.get('from_status', '—')} -> {entry.get('to_status', '—')}  "
                f"({entry.get('reason', '')})"
            )


@campaign.command("funnel")
@click.argument("config_yaml", type=click.Path(exists=True))
def campaign_funnel(config_yaml):
    """Show the expected screening funnel for a campaign config."""
    from proteus_cli.campaign.config import load_config
    from proteus_cli.campaign.funnel import estimate_funnel, format_funnel

    config = load_config(config_yaml)
    est = estimate_funnel(config)

    num_scaffolds = max(len(config.design.scaffolds), 1)
    total_designs = num_scaffolds * config.design.designs_per_scaffold

    click.echo(f"Campaign: {config.name}")
    click.echo(f"Tool: {config.design.tool} / {config.design.protocol}")
    click.echo(f"Difficulty: {config.target_difficulty}")
    click.echo(f"Total designs: {total_designs}")
    click.echo()
    click.echo(format_funnel(est))
