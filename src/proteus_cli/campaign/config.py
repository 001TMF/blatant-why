"""Campaign configuration models and YAML I/O."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TargetConfig:
    """Target protein definition."""
    name: str
    pdb_id: str
    chain_id: str
    uniprot_id: str | None = None


@dataclass
class EpitopeConfig:
    """Epitope specification for antibody design."""
    hotspot_residues: list[int] = field(default_factory=list)
    region_notation: str = ""


@dataclass
class ScaffoldConfig:
    """Scaffold template for design."""
    name: str
    pdb: str | None = None
    path: str | None = None
    description: str = ""


@dataclass
class BoltzGenConfig:
    """BoltzGen-specific parameters (replaces seed config)."""
    num_designs: int = 5000        # designs per scaffold (500-60000)
    budget: int = 50               # final ranked designs to keep
    alpha: float = 0.001           # diversity vs quality (0.0-1.0)
    step_scale: float = 1.8        # diffusion step scaling
    inverse_fold_num_sequences: int = 1  # sequences per backbone
    tier: str = "standard"         # preview/standard/production/exploratory


@dataclass
class DesignConfig:
    """Design generation parameters."""
    tool: str = "boltzgen"         # boltzgen (default) | pxdesign (de novo fallback)
    modality: str = "vhh"          # vhh | scfv | de_novo_protein
    protocol: str = "nanobody-anything"  # nanobody-anything | antibody-anything | protein-anything
    scaffolds: list[ScaffoldConfig] = field(default_factory=list)
    designs_per_scaffold: int = 5000  # alias for boltzgen.num_designs
    budget: int = 50


@dataclass
class ScreeningConfig:
    """Screening filter and ranking configuration."""
    hard_filters: dict[str, Any] = field(default_factory=lambda: {
        "iptm_min": 0.5,
        "ipsae_min": 0.3,
        "plddt_min": 70.0,
        "rmsd_max": 3.5,
    })
    ranking_weights: dict[str, float] = field(default_factory=lambda: {
        "ipsae_min": 0.50,
        "iptm": 0.30,
        "liability_penalty": 0.20,
    })


@dataclass
class LabConfig:
    """Lab testing parameters."""
    max_candidates: int = 20
    cost_per_variant_usd: float = 175.0
    provider: str = "adaptyv_bio"


@dataclass
class ComputeConfig:
    """Compute backend configuration."""
    provider: str = "tamarind"      # tamarind | local | ssh
    gpu_type: str = "A100"
    gpu_ids: str = ""               # for local: "0,1" for specific GPUs
    # SSH options
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_port: int = 22
    ssh_key_path: str = ""
    ssh_tools_path: str = "/opt/proteus"


@dataclass
class CampaignConfig:
    """Top-level campaign configuration."""
    name: str = "untitled-campaign"
    tier: str = "standard"
    target_difficulty: str = "moderate"
    target: TargetConfig = field(default_factory=lambda: TargetConfig(
        name="", pdb_id="", chain_id="",
    ))
    epitope: EpitopeConfig = field(default_factory=EpitopeConfig)
    design: DesignConfig = field(default_factory=DesignConfig)
    boltzgen: BoltzGenConfig = field(default_factory=BoltzGenConfig)
    screening: ScreeningConfig = field(default_factory=ScreeningConfig)
    lab: LabConfig = field(default_factory=LabConfig)
    compute: ComputeConfig = field(default_factory=ComputeConfig)


def _dict_to_scaffold(d: dict[str, Any]) -> ScaffoldConfig:
    return ScaffoldConfig(
        name=d.get("name", ""),
        pdb=d.get("pdb"),
        path=d.get("path"),
        description=d.get("description", ""),
    )


def _dict_to_config(raw: dict[str, Any]) -> CampaignConfig:
    """Recursively build a CampaignConfig from a plain dict."""
    target_raw = raw.get("target", {})
    target = TargetConfig(
        name=target_raw.get("name", ""),
        pdb_id=target_raw.get("pdb_id", ""),
        chain_id=target_raw.get("chain_id", ""),
        uniprot_id=target_raw.get("uniprot_id"),
    )

    epitope_raw = raw.get("epitope", {})
    epitope = EpitopeConfig(
        hotspot_residues=epitope_raw.get("hotspot_residues", []),
        region_notation=epitope_raw.get("region_notation", ""),
    )

    design_raw = raw.get("design", {})
    scaffolds = [_dict_to_scaffold(s) for s in design_raw.get("scaffolds", [])]
    design = DesignConfig(
        tool=design_raw.get("tool", "boltzgen"),
        modality=design_raw.get("modality", "vhh"),
        protocol=design_raw.get("protocol", "nanobody-anything"),
        scaffolds=scaffolds,
        designs_per_scaffold=design_raw.get("designs_per_scaffold", 5000),
        budget=design_raw.get("budget", 50),
    )

    boltzgen_raw = raw.get("boltzgen", {})
    boltzgen = BoltzGenConfig(
        num_designs=boltzgen_raw.get("num_designs", design.designs_per_scaffold),
        budget=boltzgen_raw.get("budget", design.budget),
        alpha=boltzgen_raw.get("alpha", 0.001),
        step_scale=boltzgen_raw.get("step_scale", 1.8),
        inverse_fold_num_sequences=boltzgen_raw.get("inverse_fold_num_sequences", 1),
        tier=boltzgen_raw.get("tier", raw.get("tier", "standard")),
    )

    # Backward compat: if legacy 'seeds' key exists, just ignore it
    # (BoltzGen doesn't use seeds)

    screening_raw = raw.get("screening", {})
    screening = ScreeningConfig(
        hard_filters=screening_raw.get("hard_filters", ScreeningConfig().hard_filters),
        ranking_weights=screening_raw.get("ranking_weights", ScreeningConfig().ranking_weights),
    )

    lab_raw = raw.get("lab", {})
    lab = LabConfig(
        max_candidates=lab_raw.get("max_candidates", 20),
        cost_per_variant_usd=lab_raw.get("cost_per_variant_usd", 175.0),
        provider=lab_raw.get("provider", "adaptyv_bio"),
    )

    compute_raw = raw.get("compute", {})
    compute = ComputeConfig(
        provider=compute_raw.get("provider", "tamarind"),
        gpu_type=compute_raw.get("gpu_type", "A100"),
        gpu_ids=compute_raw.get("gpu_ids", ""),
        ssh_host=compute_raw.get("ssh_host", ""),
        ssh_user=compute_raw.get("ssh_user", ""),
        ssh_port=int(compute_raw.get("ssh_port", 22)),
        ssh_key_path=compute_raw.get("ssh_key_path", ""),
        ssh_tools_path=compute_raw.get("ssh_tools_path", "/opt/proteus"),
    )

    return CampaignConfig(
        name=raw.get("name", "untitled-campaign"),
        tier=raw.get("tier", "standard"),
        target_difficulty=raw.get("target_difficulty", "moderate"),
        target=target,
        epitope=epitope,
        design=design,
        boltzgen=boltzgen,
        screening=screening,
        lab=lab,
        compute=compute,
    )


def load_config(path: str) -> CampaignConfig:
    """Read a YAML file and return a CampaignConfig."""
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping at top level, got {type(raw).__name__}")
    return _dict_to_config(raw)


def save_config(config: CampaignConfig, path: str) -> None:
    """Write a CampaignConfig to a YAML file."""
    data = asdict(config)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
