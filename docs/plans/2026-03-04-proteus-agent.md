# Proteus Agent — Full Implementation Plan (v2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a green-themed Claude Code harness + skill system ("Proteus") that wraps three local protein design tools (proteus-fold, proteus-prot, proteus-ab) into a conversational, expert-guided CLI agent for de novo protein and antibody design — with deep integration of ipSAE/p_bind custom scoring and comprehensive screening tools.

**Architecture:** A TypeScript harness app launches a custom green-themed terminal UI (inspired by Adaptyv's protein designer screenshots) via Ink/React, wrapping Claude Code through the Agent SDK. MCP servers expose biological databases (PDB, UniProt, SAbDab) and the Proteus tool suite. Claude Code skills encode expert domain workflows. Python wrapper scripts provide unified CLI interfaces to tools at `/data/proteus/`. A dedicated screening MCP server integrates ipSAE, p_bind, developability scoring, PTM liability scanning, and ESM2 pseudo-log-likelihood scoring.

**Tech Stack:** TypeScript (harness, MCP servers), Python (tool wrappers, scoring, screening), Claude Agent SDK, MCP protocol, Ink/React + ink-ui for terminal UI, chalk for green theming.

---

## Table of Contents

1. [Phase 1: Python Tool Wrappers & Scoring](#phase-1) — CLI wrappers + ipSAE/p_bind integration
2. [Phase 2: MCP Servers](#phase-2) — Database access + tool execution + screening
3. [Phase 3: Claude Code Skills](#phase-3) — Domain workflow skills
4. [Phase 4: Harness & Custom UI](#phase-4) — Green-themed terminal frontend matching inspo screenshots
5. [Phase 5: Integration & Polish](#phase-5) — E2E testing, campaign management, slash commands

---

## Research Summary

### Tool Suite (3 tools, no ODesign)

| Proteus Name | Internal Tool | Directory | CLI Entry | Purpose |
|-------------|---------------|-----------|-----------|---------|
| **proteus-fold** | Protenix v1 | `/data/proteus/Protenix/` | `protenix pred -i input.json` | AF3-class structure prediction & validation |
| **proteus-prot** | PXDesign | `/data/proteus/PXDesign/` | `pxdesign pipeline --preset extended` | De novo protein binder design (17-82% hit rates) |
| **proteus-ab** | Proteus-AB | `/data/proteus/proteus-design/` | `proteus-ab run spec.yaml` | Antibody/nanobody design (BoltzGen + Protenix refolding) |

### Custom Scoring Metrics (ipSAE + p_bind)

**ipSAE (Interfacial Predicted Structural Accuracy Error):**
- TM-align-inspired score computed from Protenix PAE matrices
- Core function: `compute_ipsae_score()` in `deps/BoltzGen/src/boltzgen/model/layers/confidence_utils.py`
- Directional: `design_to_target_ipsae`, `target_to_design_ipsae`, `design_ipsae_min`
- PAE cutoff: 15.0 A, d0 formula: `1.24 * (clamp(n0, 19) - 15)^(1/3) - 1.8`
- Wrapper: `compute_ipsae_from_protenix()` in `src/proteus_ab/pipeline/scoring.py`

**p_bind (Binding Probability Prediction):**
- 3-layer MLP: Input(1024) → Hidden(512, 256, 128) → Output(1)
- Features: `v_ab`(384) + `v_ag`(384) + `v_if`(256) = 1024-dim from Protenix trunk
- Extracted via: `extract_pbind_features()` from BoltzGen binding_utils
- Critical fix: chain_design_mask must cover FULL VH/VL chains (not CDR-only) — ROC 0.60 → 0.906
- 5 training configs: mlp_sam, adaptive_focal_sam, poly1_sam, focal_gamma1, focal_mega
- Status: Code complete, awaiting GPU featurization + training (Phase 04-02 paused)

### Screening Tools (to integrate)

| Category | Metric | Source | Implementation |
|----------|--------|--------|----------------|
| **Structure confidence** | ipTM, pTM, pLDDT | Protenix | Already in scoring.py |
| **Interface geometry** | ipSAE (directional) | Protenix PAE | Already in scoring.py |
| **Binding prediction** | p_bind probability | Custom MLP | Phase 4 integration pending |
| **Refolding quality** | CA-RMSD, all-atom RMSD | BoltzGen analyze | Already in pipeline |
| **Interface contacts** | H-bonds, salt bridges, SASA | biotite/hydride | Already in pipeline |
| **Composition** | AA fractions, hydrophobic patches | BoltzGen analyze | Already in pipeline |
| **PTM liabilities** | Deamidation (NG/NS), oxidation (Met), free Cys | Regex scan | NEW — add to screening MCP |
| **Sequence quality** | ESM2 pseudo-log-likelihood | ESM2 (in Protenix deps) | NEW — add to screening MCP |
| **Humanness** | BioPhi/OASis score | External API | NEW — add to screening MCP |
| **Solubility** | CamSol prediction | Sequence-based | NEW — add to screening MCP |
| **Developability** | TAP 5 guidelines | CDR length + surface patches | NEW — add to screening MCP |
| **Aggregation** | Largest hydrophobic patch | DBSCAN on SASA atoms | Already in pipeline |

### Design Direction (from inspo screenshots)

- **Green ink theme**: Primary accent `#4CAF50` / `#66BB6A` on charcoal `#1A1A2E`
- **ASCII art banner**: Large pixel-font "PROTEUS" in green
- **Mode indicator**: "Binder Designer mode" / "Antibody Designer mode" / "Structure Predictor mode"
- **Natural language input**: "let's load pd-l1 as a target"
- **Proactive recommendations**: Agent suggests best target, explains rationale
- **Pipeline stages**: `○ Generating backbones → ● Designing sequences → ○ Evaluating quality → ○ Design complete`
- **Ranked results tables**: Scores, shape complementarity, MPNN score, ipSAE, p_bind
- **Warning notes**: Yellow triangle for unvalidated metrics
- **Next-step menus**: Numbered options (1. Rank, 2. Approve, 3. Predict structures)
- **Slash commands**: `/watch`, `/status`, `/results`, `/screen`

---

## Phase 1: Python Tool Wrappers & Scoring {#phase-1}

### Task 1.1: Project Scaffolding

**Files:**
- Create: `src/proteus_cli/__init__.py`
- Create: `src/proteus_cli/common.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/test_common.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "proteus-agent"
version = "0.1.0"
description = "Proteus protein design agent - CLI wrappers, scoring, and screening"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pydantic>=2.0",
    "rich>=13.0",
    "pyyaml>=6.0",
    "numpy>=2.0",
    "biopython>=1.80",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov", "pytest-asyncio"]
screening = ["fair-esm>=2.0"]

[project.scripts]
proteus = "proteus_cli.main:cli"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2: Create common utilities**

```python
# src/proteus_cli/common.py
"""Shared utilities for Proteus CLI wrappers."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    """Standardized result from any Proteus tool invocation."""
    tool: str
    status: str  # "success", "error", "running"
    output_dir: Path | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    designs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "tool": self.tool,
                "status": self.status,
                "output_dir": str(self.output_dir) if self.output_dir else None,
                "metrics": self.metrics,
                "designs": self.designs,
                "error": self.error,
            },
            indent=2,
        )


TOOL_PATHS = {
    "proteus-fold": Path("/data/proteus/Protenix"),
    "proteus-prot": Path("/data/proteus/PXDesign"),
    "proteus-ab": Path("/data/proteus/proteus-design"),
}


def validate_tool_path(tool_name: str) -> Path:
    path = TOOL_PATHS.get(tool_name)
    if path is None:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_PATHS)}")
    if not path.exists():
        raise FileNotFoundError(f"Tool directory not found: {path}")
    return path


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
```

**Step 3: Tests + commit**

Run: `pytest tests/test_common.py -v`

```bash
git init && git add src/ tests/ pyproject.toml && git commit -m "feat: project scaffolding with common utilities"
```

---

### Task 1.2: proteus-fold Wrapper (Protenix)

**Files:** `src/proteus_cli/fold.py`, `tests/test_fold.py`

Wraps `protenix pred` with standardized JSON input builder (`build_protenix_json()`), model selection (base_default, base_20250630, mini), and `ToolResult` output. Supports seed/sample count configuration for single prediction vs ensemble validation.

---

### Task 1.3: proteus-prot Wrapper (PXDesign)

**Files:** `src/proteus_cli/protein.py`, `tests/test_protein.py`

Wraps `pxdesign pipeline` with YAML config builder, preset selection (preview/extended), output parser for `summary.csv`, and dual-scoring bucket extraction (AF2-IG + Protenix thresholds). Handles multi-GPU via `--nproc_per_node`.

---

### Task 1.4: proteus-ab Wrapper (Antibody Design)

**Files:** `src/proteus_cli/antibody.py`, `tests/test_antibody.py`

Wraps `proteus-ab run` with design spec builder, protocol selection (nanobody-anything/antibody-anything), prefilter toggle, MSA mode selection, budget/diversity alpha configuration. Parses `final_designs_metrics_*.csv` and `results_overview.pdf`.

---

### Task 1.5: ipSAE Scoring Module

**Files:** `src/proteus_cli/scoring/ipsae.py`, `tests/test_ipsae_scoring.py`

**Step 1: Write standalone ipSAE computation**

This module re-exports the core ipSAE functions from BoltzGen and provides a high-level API for scoring arbitrary PAE matrices:

```python
# src/proteus_cli/scoring/ipsae.py
"""ipSAE scoring — standalone interface to BoltzGen's compute_ipsae_score.

Provides both the raw scoring function and a high-level API that works
with Protenix NPZ output files directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

# Re-export from BoltzGen for direct use
from boltzgen.model.layers.confidence_utils import compute_ipsae_score


def score_npz(npz_path: Path, design_chain_ids: list[int], target_chain_ids: list[int]) -> dict[str, float]:
    """Score a Protenix output NPZ file for ipSAE metrics.

    Args:
        npz_path: Path to NPZ with 'pae' key [N_sample, N_token, N_token]
        design_chain_ids: asym_id integers for design chains
        target_chain_ids: asym_id integers for target chains

    Returns:
        Dict with best-sample ipSAE metrics.
    """
    import torch

    data = np.load(npz_path, allow_pickle=True)
    pae = torch.from_numpy(data["pae"]).float()  # [N_sample, N_token, N_token]

    # Build masks from mol_type or asym_id if available
    if "token_asym_id" in data:
        asym_id = torch.from_numpy(data["token_asym_id"])
    else:
        # Fallback: use design/target chain IDs directly
        n_tokens = pae.shape[1]
        asym_id = torch.zeros(n_tokens, dtype=torch.long)

    design_ids_t = torch.tensor(design_chain_ids)
    target_ids_t = torch.tensor(target_chain_ids)

    design_mask = torch.isin(asym_id, design_ids_t).unsqueeze(0).float()
    target_mask = torch.isin(asym_id, target_ids_t).unsqueeze(0).float()
    frame_mask = torch.ones_like(design_mask)
    pad_mask = torch.ones_like(design_mask)

    best_dt = -1.0
    best_td = -1.0
    best_min = -1.0

    for i in range(pae.shape[0]):
        pae_i = pae[i].unsqueeze(0)
        dt = compute_ipsae_score(design_mask, target_mask, pae_i, frame_mask, pad_mask).item()
        td = compute_ipsae_score(target_mask, design_mask, pae_i, frame_mask, pad_mask).item()
        mn = min(dt, td)
        if mn > best_min:
            best_dt, best_td, best_min = dt, td, mn

    return {
        "design_to_target_ipsae": best_dt,
        "target_to_design_ipsae": best_td,
        "design_ipsae_min": best_min,
    }


def interpret_ipsae(score: float) -> str:
    """Human-readable interpretation of ipSAE score."""
    if score > 0.8:
        return "Excellent interface — high confidence binding"
    elif score > 0.5:
        return "Good interface — likely binder"
    elif score > 0.3:
        return "Moderate interface — possible binder, consider redesign"
    else:
        return "Poor interface — unlikely to bind"
```

**Step 2: Test**

```python
# tests/test_ipsae_scoring.py
from proteus_cli.scoring.ipsae import interpret_ipsae

def test_interpret_excellent():
    assert "Excellent" in interpret_ipsae(0.9)

def test_interpret_poor():
    assert "Poor" in interpret_ipsae(0.1)
```

**Step 3: Commit**

```bash
git add src/proteus_cli/scoring/ tests/test_ipsae_scoring.py
git commit -m "feat: ipSAE scoring module with NPZ support"
```

---

### Task 1.6: p_bind Inference Module

**Files:** `src/proteus_cli/scoring/pbind.py`, `tests/test_pbind_inference.py`

```python
# src/proteus_cli/scoring/pbind.py
"""p_bind inference — binding probability prediction from Protenix features.

Wraps BoltzGen's PBindHead model for inference on new designs.
Uses Protenix trunk features (s_trunk, z_trunk) extracted during refolding.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_pbind_model(checkpoint_path: Path, device: str = "cpu"):
    """Load a trained p_bind checkpoint."""
    from boltzgen.pbind.model import PBindHead
    return PBindHead.from_checkpoint(str(checkpoint_path), device=device)


def predict_binding(
    model: Any,
    v_ab,  # [1, 384] antibody representation
    v_ag,  # [1, 384] antigen representation
    v_if,  # [1, 256] interface representation
) -> float:
    """Predict binding probability for a single design."""
    import torch
    with torch.no_grad():
        output = model(v_ab, v_ag, v_if)
        return output["binding_prob"][0].item()


def extract_features_from_trunk(
    s_trunk,     # [1, N, 384]
    z_trunk,     # [1, N, N, 128]
    asym_id,     # [N] or [1, N]
) -> dict:
    """Extract p_bind features from Protenix trunk outputs.

    Uses the v2 chain_design_mask (full VH/VL chains, NOT CDR-only).
    """
    import torch
    from boltzgen.model.layers.binding_utils import extract_pbind_features
    from proteus_ab.pbind.trunk import build_chain_design_mask

    chain_mask = build_chain_design_mask(asym_id)
    token_pad_mask = torch.ones(1, s_trunk.shape[1], device=s_trunk.device)

    feats = extract_pbind_features(
        s_trunk=s_trunk,
        z_trunk=z_trunk,
        design_mask=chain_mask,
        chain_design_mask=chain_mask,
        token_pad_mask=token_pad_mask,
    )
    return feats


def interpret_pbind(prob: float) -> str:
    """Human-readable interpretation of binding probability."""
    if prob > 0.8:
        return "High confidence binder"
    elif prob > 0.5:
        return "Likely binder"
    elif prob > 0.3:
        return "Marginal — consider redesign"
    else:
        return "Unlikely to bind"
```

**Step 2: Test + commit**

```bash
git add src/proteus_cli/scoring/pbind.py tests/test_pbind_inference.py
git commit -m "feat: p_bind inference module for binding probability prediction"
```

---

### Task 1.7: Screening Module

**Files:** `src/proteus_cli/screening/__init__.py`, `src/proteus_cli/screening/liabilities.py`, `src/proteus_cli/screening/developability.py`

```python
# src/proteus_cli/screening/liabilities.py
"""PTM liability and sequence quality scanning."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Liability:
    type: str
    position: int
    motif: str
    severity: str  # "high", "medium", "low"
    description: str


# Deamidation hotspots
DEAMIDATION_PATTERNS = [
    (re.compile(r"NG"), "high", "Asparagine deamidation (NG)"),
    (re.compile(r"NS"), "medium", "Asparagine deamidation (NS)"),
    (re.compile(r"NT"), "medium", "Asparagine deamidation (NT)"),
    (re.compile(r"NA"), "low", "Asparagine deamidation (NA)"),
]

# Isomerization
ISOMERIZATION_PATTERNS = [
    (re.compile(r"DG"), "high", "Aspartate isomerization (DG)"),
    (re.compile(r"DS"), "medium", "Aspartate isomerization (DS)"),
]

# Oxidation
OXIDATION_PATTERNS = [
    (re.compile(r"M"), "medium", "Methionine oxidation"),
    (re.compile(r"W"), "low", "Tryptophan oxidation"),
]

# Glycosylation
GLYCOSYLATION_PATTERN = re.compile(r"N[^P][ST]")


def scan_liabilities(sequence: str) -> list[Liability]:
    """Scan a protein sequence for PTM liabilities."""
    liabilities = []

    for pattern, severity, desc in DEAMIDATION_PATTERNS:
        for match in pattern.finditer(sequence):
            liabilities.append(Liability("deamidation", match.start(), match.group(), severity, desc))

    for pattern, severity, desc in ISOMERIZATION_PATTERNS:
        for match in pattern.finditer(sequence):
            liabilities.append(Liability("isomerization", match.start(), match.group(), severity, desc))

    # Free cysteines (odd count = unpaired)
    cys_count = sequence.count("C")
    if cys_count % 2 != 0:
        liabilities.append(Liability("free_cysteine", -1, f"{cys_count} Cys", "high", "Odd number of cysteines — likely unpaired"))

    # N-linked glycosylation
    for match in GLYCOSYLATION_PATTERN.finditer(sequence):
        liabilities.append(Liability("glycosylation", match.start(), match.group(), "medium", "N-linked glycosylation motif (NXS/T)"))

    return liabilities


def compute_net_charge(sequence: str, ph: float = 7.4) -> float:
    """Estimate net charge at given pH using Henderson-Hasselbalch."""
    pka = {"D": 3.65, "E": 4.25, "H": 6.00, "C": 8.18, "Y": 10.07, "K": 10.53, "R": 12.48}
    charge = 0.0
    for aa in sequence:
        if aa in ("D", "E", "C", "Y"):
            charge -= 1.0 / (1.0 + 10 ** (pka.get(aa, 7.0) - ph))
        elif aa in ("K", "R", "H"):
            charge += 1.0 / (1.0 + 10 ** (ph - pka.get(aa, 7.0)))
    # N-terminus and C-terminus
    charge += 1.0 / (1.0 + 10 ** (ph - 9.69))  # N-term
    charge -= 1.0 / (1.0 + 10 ** (2.34 - ph))   # C-term
    return charge
```

```python
# src/proteus_cli/screening/developability.py
"""Developability assessment for antibody designs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DevelopabilityReport:
    total_cdr_length: int
    net_charge: float
    liability_count: int
    hydrophobic_fraction: float
    proline_fraction: float
    glycine_fraction: float
    overall_risk: str  # "low", "medium", "high"
    flags: list[str]


HYDROPHOBIC_AAS = set("AILMFWVP")


def assess_developability(
    sequence: str,
    cdr_regions: list[tuple[int, int]] | None = None,
    liabilities: list | None = None,
) -> DevelopabilityReport:
    """Run TAP-inspired developability assessment."""
    from proteus_cli.screening.liabilities import scan_liabilities, compute_net_charge

    if liabilities is None:
        liabilities = scan_liabilities(sequence)

    charge = compute_net_charge(sequence)
    hydro_frac = sum(1 for aa in sequence if aa in HYDROPHOBIC_AAS) / len(sequence)
    pro_frac = sequence.count("P") / len(sequence)
    gly_frac = sequence.count("G") / len(sequence)

    total_cdr_len = 0
    if cdr_regions:
        total_cdr_len = sum(end - start for start, end in cdr_regions)

    flags = []
    if len([l for l in liabilities if l.severity == "high"]) > 2:
        flags.append("Multiple high-severity PTM liabilities")
    if abs(charge) > 10:
        flags.append(f"Extreme net charge: {charge:.1f}")
    if hydro_frac > 0.45:
        flags.append(f"High hydrophobic content: {hydro_frac:.1%}")
    if gly_frac > 0.15:
        flags.append(f"High glycine content: {gly_frac:.1%}")
    if total_cdr_len > 70:
        flags.append(f"Long total CDR length: {total_cdr_len}")

    risk = "low"
    if len(flags) >= 3:
        risk = "high"
    elif len(flags) >= 1:
        risk = "medium"

    return DevelopabilityReport(
        total_cdr_length=total_cdr_len,
        net_charge=charge,
        liability_count=len(liabilities),
        hydrophobic_fraction=hydro_frac,
        proline_fraction=pro_frac,
        glycine_fraction=gly_frac,
        overall_risk=risk,
        flags=flags,
    )
```

**Step: Commit**

```bash
git add src/proteus_cli/screening/ tests/test_screening.py
git commit -m "feat: screening module — PTM liabilities, net charge, developability"
```

---

### Task 1.8: Unified CLI Entry Point

**Files:** `src/proteus_cli/main.py`

Click group with commands: `fold`, `protein`, `ab`, `check`, `screen`, `score`.

- `proteus fold` — structure prediction
- `proteus protein` — de novo binder design
- `proteus ab` — antibody/nanobody design
- `proteus check <tool>` — verify tool installation
- `proteus screen <sequence>` — run liability + developability screening
- `proteus score <npz_path>` — compute ipSAE from NPZ

```bash
git add src/proteus_cli/main.py
git commit -m "feat: unified proteus CLI with fold/protein/ab/check/screen/score"
```

---

## Phase 2: MCP Servers {#phase-2}

### Task 2.1: PDB MCP Server

**Files:** `mcp_servers/pdb/server.py`

Tools: `pdb_search`, `pdb_fetch_structure`, `pdb_get_chains`, `pdb_interface_residues`, `pdb_download`

Uses RCSB REST API (`https://data.rcsb.org/rest/v1` + `https://search.rcsb.org/rcsbsearch/v2/query`).

---

### Task 2.2: UniProt MCP Server

**Files:** `mcp_servers/uniprot/server.py`

Tools: `uniprot_search`, `uniprot_fetch_protein`, `uniprot_get_domains`, `uniprot_get_variants`

Uses UniProt REST API (`https://rest.uniprot.org`).

---

### Task 2.3: SAbDab MCP Server

**Files:** `mcp_servers/sabdab/server.py`

Tools: `sabdab_search_antibodies`, `sabdab_get_structure`, `sabdab_cdr_sequences`, `sabdab_search_by_antigen`

Uses SAbDab API (`https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab/`). Critical for antibody scaffold selection in proteus-ab workflows.

---

### Task 2.4: Proteus Tools MCP Server

**Files:** `mcp_servers/proteus_tools/server.py`

Tools:
- `proteus_fold_predict` — Run Protenix structure prediction
- `proteus_prot_design` — Run PXDesign binder design pipeline
- `proteus_ab_design` — Run antibody/nanobody design pipeline
- `proteus_check_input` — Validate design spec YAML
- `proteus_parse_results` — Parse and rank design campaign results
- `proteus_download_target` — Download and prepare target from PDB

Each tool calls the Python wrappers from Phase 1 and returns structured JSON.

---

### Task 2.5: Screening MCP Server

**Files:** `mcp_servers/screening/server.py`

This is a key differentiator from the Adaptyv skill. Tools:

- `screen_liabilities` — Scan sequence for PTM liabilities (deamidation, isomerization, oxidation, glycosylation, free Cys)
- `screen_developability` — TAP-inspired developability assessment (CDR length, charge, hydrophobicity, composition)
- `screen_net_charge` — Net charge at pH 7.4
- `score_ipsae` — Compute ipSAE from PAE matrix or NPZ file
- `score_pbind` — Run p_bind inference on Protenix trunk features (when checkpoint available)
- `screen_composite` — Run full screening battery and return ranked summary
- `interpret_scores` — Human-readable interpretation of all scoring metrics

---

### Task 2.6: MCP Server Configuration

**Files:** `.claude/settings.json`

```json
{
  "mcpServers": {
    "proteus-pdb": {
      "command": "python",
      "args": ["mcp_servers/pdb/server.py"]
    },
    "proteus-uniprot": {
      "command": "python",
      "args": ["mcp_servers/uniprot/server.py"]
    },
    "proteus-sabdab": {
      "command": "python",
      "args": ["mcp_servers/sabdab/server.py"]
    },
    "proteus-tools": {
      "command": "python",
      "args": ["mcp_servers/proteus_tools/server.py"]
    },
    "proteus-screening": {
      "command": "python",
      "args": ["mcp_servers/screening/server.py"]
    }
  }
}
```

---

## Phase 3: Claude Code Skills {#phase-3}

### Task 3.1: Skill — proteus-design-workflow

**Files:** `.claude/skills/proteus-design-workflow/SKILL.md`

Master orchestration skill with decision tree:
```
Want to design a binder?
├── Antibody/nanobody? → proteus-ab (nanobody-anything | antibody-anything)
├── Protein binder? → proteus-prot (preview | extended)
└── Validate a structure? → proteus-fold
```

Standard pipeline: Target Prep → Hotspot Analysis → Design Generation → Screening → Ranking → Review.

Quality thresholds table. Campaign sizing guide. Residue numbering convention (label_seq_id).

---

### Task 3.2: Skill — proteus-scoring

**Files:** `.claude/skills/proteus-scoring/SKILL.md`

**Deep scoring skill** covering ipSAE and p_bind:

```markdown
## ipSAE Scoring

ipSAE is a TM-align-inspired metric computed from Protenix PAE matrices.
It captures directional interface quality:

- **design_to_target_ipsae**: How well design aligns to target
- **target_to_design_ipsae**: How well target aligns to design
- **design_ipsae_min**: min(dt, td) — most stringent assessment

### Algorithm
1. Extract PAE matrix from Protenix output
2. Build chain masks from asym_id
3. Threshold PAE at 15.0 A cutoff
4. Compute TM-align d0 reference distance
5. Score: 1 / (1 + (pae/d0)^2), averaged over valid pairs
6. Return maximum across source residues

### Interpretation
| ipSAE | Interpretation |
|-------|---------------|
| > 0.8 | Excellent interface — high confidence |
| 0.5-0.8 | Good — likely binder |
| 0.3-0.5 | Moderate — possible binder |
| < 0.3 | Poor — unlikely to bind |

## p_bind Scoring

p_bind predicts binding probability from Protenix trunk features.

### Architecture
Input: v_ab(384) + v_ag(384) + v_if(256) = 1024-dim
Network: MLP [512, 256, 128] → sigmoid
Output: probability 0-1

### Critical: chain_design_mask
Must use FULL VH/VL chains (not CDR-only).
v1 (CDR-only) gave ROC 0.60 → v2 (full chains) gave ROC 0.906.

### When to use
- After proteus-ab designs are refolded
- Before final candidate selection
- As additional ranking signal alongside ipTM and ipSAE
```

---

### Task 3.3: Skill — proteus-epitope-analysis

**Files:** `.claude/skills/proteus-epitope-analysis/SKILL.md`

Teaches Claude to:
1. Use `pdb_interface_residues` to identify binding interface
2. Classify residues: buried contact, core packing, polar anchor, hydrophobic core
3. Score hotspot quality using contact analysis
4. Recommend hotspot residues for design input
5. Assess shape complementarity

---

### Task 3.4: Skill — proteus-screening

**Files:** `.claude/skills/proteus-screening/SKILL.md`

Comprehensive screening skill encoding ALL screening metrics:

- **Structural**: ipTM thresholds, pLDDT interpretation, RMSD limits
- **Custom scores**: ipSAE ranges, p_bind thresholds
- **Liabilities**: PTM scan interpretation, severity triage
- **Developability**: TAP guidelines, charge limits, composition flags
- **Composite filtering**: Hard filters → soft ranking → diversity selection
- **Failure recovery**: What to do when designs fail each filter

---

### Task 3.5: Skill — proteus-campaign-manager

**Files:** `.claude/skills/proteus-campaign-manager/SKILL.md`

Campaign planning, state tracking, multi-run coordination, cost/time estimation, progress monitoring, health assessment.

---

### Task 3.6: Skill — proteus-database

**Files:** `.claude/skills/proteus-database/SKILL.md`

How to use MCP tools for PDB, UniProt, SAbDab queries. Template selection guidance for proteus-ab scaffolds.

---

## Phase 4: Harness & Custom UI {#phase-4}

### Task 4.1: Harness Project Setup

**Files:** `harness/package.json`, `harness/tsconfig.json`

Dependencies: `@anthropic-ai/claude-agent-sdk`, `chalk`, `ink`, `ink-ui`, `ink-text-input`, `react`.

---

### Task 4.2: Green Theme & ASCII Banner

**Files:** `harness/src/theme.ts`, `harness/src/banner.ts`

```typescript
// harness/src/theme.ts
import chalk from "chalk";

export const theme = {
  primary: chalk.hex("#4CAF50"),        // Green primary
  primaryBold: chalk.hex("#4CAF50").bold,
  accent: chalk.hex("#66BB6A"),         // Light green
  heading: chalk.white.bold,
  body: chalk.hex("#A0A0A0"),
  dim: chalk.hex("#606060"),
  success: chalk.hex("#4CAF50"),        // Green
  warning: chalk.hex("#FFC107"),        // Yellow
  error: chalk.hex("#FF5252"),          // Red
  running: chalk.hex("#4CAF50"),        // Green
  id: chalk.hex("#4CAF50"),             // IDs in green (matching inspo cyan→green)
  prompt: chalk.hex("#4CAF50")("◆ "),
  bullet: chalk.hex("#4CAF50")("● "),
  warnBullet: chalk.hex("#FFC107")("▲ "),
};
```

```typescript
// harness/src/banner.ts
const BANNER = `
██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗
██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝
██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗
██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║
██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝
`;
// Rendered in theme.primary (green)
```

---

### Task 4.3: Mode System

**Files:** `harness/src/modes.ts`

Three modes (Shift-Tab to cycle, matching inspo):
1. **Binder Designer** — proteus-prot focused (de novo protein binders)
2. **Antibody Designer** — proteus-ab focused (VHH/Fab design)
3. **Structure Predictor** — proteus-fold focused (validation)

Each mode sets active skills and default tool parameters.

---

### Task 4.4: Pipeline Progress Display

**Files:** `harness/src/progress.ts`

Multi-stage pipeline with dot indicators matching inspo screenshot 7:

```
Design Run: {run_id}

  ○ Generating backbones     PXDesign-d / BoltzGen
  ● Designing sequences      ProteinMPNN / AntiFold     ← active (green dot)
  ○ Screening quality        ipSAE + p_bind + liabilities
  ○ Evaluating structures    Protenix refolding
  ○ Filtering & ranking      Composite score
  ○ Design complete          Ready for review

Progress: 19/30 designs
Status: running
```

---

### Task 4.5: Results Table Display

**Files:** `harness/src/results.ts`

Renders ranked results matching inspo screenshots 5 and 9:

```
Rank  Design      ipTM    ipSAE   p_bind  RMSD   Liabilities  Status
1     design-8    0.87    0.82    0.91    1.2A   0 high       PASS
2     design-9    0.84    0.78    0.88    1.5A   1 medium     PASS
3     design-20   0.81    0.71    0.85    1.8A   0 high       PASS
...

▲ Note: p_bind scores require trained checkpoint.

Next steps:
1 Visualize the structure with hotspots highlighted?
2 Run full screening battery on top designs?
3 Approve top designs for experimental validation?
```

---

### Task 4.6: Slash Commands

**Files:** `.claude/commands/watch.md`, `.claude/commands/status.md`, `.claude/commands/results.md`, `.claude/commands/screen.md`

Matching inspo:
- `/watch <run_id>` — Live pipeline progress
- `/status` — Current campaign status
- `/results` — Show ranked designs
- `/screen <design_id>` — Full screening on a specific design

---

### Task 4.7: Main App Component

**Files:** `harness/src/app.tsx`

Ink React app composing: Banner → Mode indicator → Conversation area → Progress tracker → Results table → Prompt input. Wire to Agent SDK.

---

### Task 4.8: Agent SDK Integration

**Files:** `harness/src/agent.ts`

Connects harness UI to Claude:
- Loads CLAUDE.md and skills
- Registers all 5 MCP servers
- Manages conversation state via Agent SDK `query()` streaming
- PostToolUse hooks update progress display
- Handles slash command dispatch
- Session persistence for multi-session campaigns

---

## Phase 5: Integration & Polish {#phase-5}

### Task 5.1: CLAUDE.md for Proteus Agent

```markdown
# CLAUDE.md — Proteus Protein Design Agent

## Identity
You are Proteus, an expert computational protein engineer. You design protein
binders and antibodies using the Proteus tool suite.

## Tools (3 core)
- **proteus-fold**: Structure prediction & validation (Protenix v1)
- **proteus-prot**: De novo protein binder design (PXDesign, 17-82% hit rates)
- **proteus-ab**: Antibody/nanobody design (BoltzGen + Protenix refolding)

## Scoring (custom metrics — use these proactively)
- **ipSAE**: TM-align-inspired interface score from PAE matrices. Higher = better.
  Directional: design→target, target→design, min(both).
- **p_bind**: ML binding probability from Protenix trunk features (0-1).
  v2 chain mask (full VH/VL chains) — critical for accuracy.

## Screening (always run before presenting final candidates)
- PTM liability scan (deamidation NG/NS, isomerization DG, oxidation Met, free Cys)
- Net charge at pH 7.4
- Developability: CDR length, hydrophobic fraction, composition flags
- Composite: ipTM + ipSAE + p_bind + liability count → ranked output

## Conventions
- Residue indices: label_seq_id (1-indexed, sequential)
- Structure format: CIF preferred
- Metrics format: CSV for tables, NPZ for tensors, JSON for state
- Start with preview/small runs before production campaigns
- Present results with scores, interpretation, and numbered next steps
```

---

### Task 5.2: Plugin Manifest

**Files:** `plugin-manifest.json`

---

### Task 5.3: End-to-End Test

**Files:** `tests/test_e2e.py`

Full pipeline: PDB search → download → interface analysis → hotspot selection → design spec → tool invocation (mock) → scoring → screening → result presentation.

---

### Task 5.4: Launch Script

**Files:** `launch.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check dependencies
command -v node >/dev/null || { echo "Error: Node.js required"; exit 1; }
command -v python3 >/dev/null || { echo "Error: Python 3.11+ required"; exit 1; }

# Install if needed
[ -d "$SCRIPT_DIR/harness/node_modules" ] || (cd "$SCRIPT_DIR/harness" && npm install)
[ -d "$SCRIPT_DIR/.venv" ] || (python3 -m venv "$SCRIPT_DIR/.venv" && source "$SCRIPT_DIR/.venv/bin/activate" && pip install -e ".[dev,screening]")

cd "$SCRIPT_DIR/harness"
exec npx tsx src/index.ts "$@"
```

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    PROTEUS HARNESS (Green UI)                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Ink/React Terminal UI                                  │  │
│  │  ┌────────┐ ┌─────────────┐ ┌───────────────────────┐ │  │
│  │  │ GREEN  │ │  Mode:      │ │  Pipeline Progress    │ │  │
│  │  │ BANNER │ │  Ab Designer│ │  ● Step 3/6 running   │ │  │
│  │  └────────┘ └─────────────┘ └───────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │  Results Table: Rank | ipTM | ipSAE | p_bind   │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │                                     │
│              ┌──────────┴──────────┐                         │
│              │  Claude Agent SDK   │                         │
│              │  + Hooks + Sessions │                         │
│              └──────────┬──────────┘                         │
└─────────────────────────┼────────────────────────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
┌───┴───────┐  ┌──────────┴──────────┐  ┌──────┴───────┐
│  Skills   │  │    MCP Servers      │  │   Python     │
│           │  │                     │  │   Wrappers   │
│ workflow  │  │ PDB      UniProt    │  │              │
│ scoring   │  │ SAbDab   Tools      │  │ fold.py      │
│ epitope   │  │ Screening           │  │ protein.py   │
│ screening │  │                     │  │ antibody.py  │
│ campaign  │  │ (ipSAE, p_bind,     │  │              │
│ database  │  │  liabilities,       │  │ scoring/     │
│           │  │  developability)    │  │  ipsae.py    │
└───────────┘  └──────────┬──────────┘  │  pbind.py    │
                          │             │              │
                   ┌──────┴─────────────┤ screening/   │
                   │                    │  liabilities  │
                   │  /data/proteus/    │  developab.   │
                   │                    └──────────────┘
                   │  Protenix (fold)
                   │  PXDesign (prot)
                   │  Proteus-AB (ab)
                   └────────────────────
```

## File Tree

```
protein_design_agent/
├── CLAUDE.md
├── plugin-manifest.json
├── pyproject.toml
├── launch.sh
├── src/
│   └── proteus_cli/
│       ├── __init__.py
│       ├── main.py                     # CLI: proteus {fold,protein,ab,check,screen,score}
│       ├── common.py                   # ToolResult, TOOL_PATHS
│       ├── fold.py                     # proteus-fold (Protenix)
│       ├── protein.py                  # proteus-prot (PXDesign)
│       ├── antibody.py                 # proteus-ab
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── ipsae.py               # ipSAE from PAE matrices
│       │   └── pbind.py               # p_bind inference
│       └── screening/
│           ├── __init__.py
│           ├── liabilities.py          # PTM scan, net charge
│           └── developability.py       # TAP assessment
├── mcp_servers/
│   ├── pdb/server.py
│   ├── uniprot/server.py
│   ├── sabdab/server.py
│   ├── proteus_tools/server.py
│   └── screening/server.py            # ipSAE + p_bind + liabilities + developability
├── harness/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts
│       ├── app.tsx                     # Main Ink app
│       ├── agent.ts                    # Agent SDK integration
│       ├── banner.ts                   # GREEN ASCII PROTEUS banner
│       ├── theme.ts                    # Green color palette
│       ├── modes.ts                    # Binder/Antibody/Structure modes
│       ├── progress.ts                 # Pipeline stage display
│       └── results.ts                  # Ranked design tables
├── .claude/
│   ├── settings.json                   # 5 MCP servers
│   ├── commands/
│   │   ├── watch.md
│   │   ├── status.md
│   │   ├── results.md
│   │   └── screen.md
│   └── skills/
│       ├── proteus-design-workflow/SKILL.md
│       ├── proteus-scoring/SKILL.md    # ipSAE + p_bind deep guide
│       ├── proteus-epitope-analysis/SKILL.md
│       ├── proteus-screening/SKILL.md  # Full screening battery
│       ├── proteus-campaign-manager/SKILL.md
│       └── proteus-database/SKILL.md
├── tests/
│   ├── test_common.py
│   ├── test_fold.py
│   ├── test_protein.py
│   ├── test_antibody.py
│   ├── test_ipsae_scoring.py
│   ├── test_pbind_inference.py
│   ├── test_screening.py
│   └── test_e2e.py
└── docs/
    └── plans/
        └── 2026-03-04-proteus-agent.md
```

## Task Count: 30 tasks across 5 phases

| Phase | Tasks | Key Additions vs v1 |
|-------|-------|---------------------|
| 1. Python Wrappers & Scoring | 8 | ipSAE module, p_bind inference, screening module |
| 2. MCP Servers | 6 | Screening MCP server (ipSAE + p_bind + liabilities) |
| 3. Skills | 6 | proteus-scoring skill (ipSAE/p_bind deep guide), screening skill |
| 4. Harness UI | 8 | Green theme, slash commands, results with scoring columns |
| 5. Integration | 4 | Updated CLAUDE.md with scoring conventions |
