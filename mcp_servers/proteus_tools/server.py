"""Proteus Tools MCP Server — wraps Phase 1 CLI wrappers for protein design."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src directory to sys.path so proteus_cli imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import httpx
from mcp.server.fastmcp import FastMCP

from proteus_cli.common import ToolResult, validate_tool_path
from proteus_cli.fold import build_protenix_json, run_fold, parse_fold_output, MODELS
from proteus_cli.protein import build_pxdesign_config, run_protein_design, parse_design_results
from proteus_cli.antibody import build_design_spec, run_antibody_design, parse_antibody_results

mcp = FastMCP("proteus-tools")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RCSB_DOWNLOAD_URL = "https://files.rcsb.org/download"
TIMEOUT = 60.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


def _result_json(result: ToolResult) -> str:
    """Serialize a ToolResult to its JSON representation."""
    return result.to_json()


# ---------------------------------------------------------------------------
# Tool 1: proteus_fold_predict
# ---------------------------------------------------------------------------


@mcp.tool()
def proteus_fold_predict(
    sequences: list[str],
    output_dir: str,
    name: str = "prediction",
    model: str = "base_default",
    seeds: list[int] | None = None,
    sample_count: int = 1,
) -> str:
    """Run Protenix v1 structure prediction on one or more protein sequences.

    Builds a Protenix JSON input file, invokes the fold pipeline, and returns
    confidence metrics (ipTM, pTM, pLDDT, ranking_score).

    Args:
        sequences: List of amino-acid sequences to predict.
        output_dir: Directory where prediction outputs will be written.
        name: Job name for the prediction (default "prediction").
        model: Model key — one of "base_default", "base_20250630", "mini".
        seeds: Random seeds for the model (default [42]).
        sample_count: Number of diffusion samples per seed.

    Returns:
        JSON ToolResult with status, output_dir, and confidence metrics.
    """
    try:
        if not sequences:
            return _error("At least one sequence is required.")

        if model not in MODELS:
            return _error(
                f"Unknown model '{model}'. Available: {list(MODELS.keys())}"
            )

        # Build the JSON input file
        input_json = build_protenix_json(
            sequences=sequences,
            output_dir=output_dir,
            name=name,
            seeds=seeds,
            sample_count=sample_count,
        )

        # Run fold prediction
        result = run_fold(
            input_json_path=input_json,
            model=model,
            output_dir=output_dir,
        )

        return _result_json(result)

    except Exception as exc:
        return _error(f"proteus_fold_predict failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 2: proteus_prot_design
# ---------------------------------------------------------------------------


@mcp.tool()
def proteus_prot_design(
    target_pdb: str,
    target_chains: list[str],
    hotspot_residues: list[str] | None = None,
    output_dir: str = "/tmp/pxdesign",
    preset: str = "extended",
    num_samples: int = 500,
    binder_length: int = 100,
) -> str:
    """Run PXDesign de novo protein binder design against a target structure.

    Builds a PXDesign YAML config, runs the design pipeline, and returns
    the result status and output directory.

    Args:
        target_pdb: Path to the target structure file (CIF or PDB).
        target_chains: Chain identifiers to target (e.g. ["A"]).
        hotspot_residues: Optional hotspot residue IDs (e.g. ["A45", "A50"]).
        output_dir: Directory for outputs (default "/tmp/pxdesign").
        preset: PXDesign preset — "preview" or "extended" (default "extended").
        num_samples: Number of design samples (default 500).
        binder_length: Length of the designed binder in residues (default 100).

    Returns:
        JSON ToolResult with status and output_dir.
    """
    try:
        target_path = Path(target_pdb)
        if not target_path.exists():
            return _error(f"Target PDB not found: {target_pdb}")

        if not target_chains:
            return _error("At least one target chain is required.")

        if preset not in ("preview", "extended"):
            return _error(
                f"Unknown preset '{preset}'. Available: ['preview', 'extended']"
            )

        # Build the config
        config_path = build_pxdesign_config(
            target_pdb=target_pdb,
            target_chains=target_chains,
            hotspot_residues=hotspot_residues,
            output_dir=output_dir,
            binder_length=binder_length,
        )

        # Run design pipeline
        result = run_protein_design(
            config_path=config_path,
            preset=preset,
            num_samples=num_samples,
            output_dir=output_dir,
        )

        return _result_json(result)

    except Exception as exc:
        return _error(f"proteus_prot_design failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 3: proteus_ab_design
# ---------------------------------------------------------------------------


@mcp.tool()
def proteus_ab_design(
    target_pdb: str,
    target_chains: list[str],
    binding_residues: dict[str, list[int]],
    protocol: str = "nanobody-anything",
    num_designs: int = 10,
    output_dir: str = "/tmp/proteus_ab",
    msa_mode: str = "none",
    budget: int = 10,
) -> str:
    """Run Proteus-AB antibody/nanobody design against a target structure.

    Builds a design spec YAML, runs the antibody design pipeline, and returns
    the result status and output directory.

    Args:
        target_pdb: Path to the target structure file (CIF or PDB).
        target_chains: Chain identifiers to target (e.g. ["A"]).
        binding_residues: Per-chain binding residue indices, e.g. {"A": [7,8,9,27,28]}.
        protocol: Design protocol — "nanobody-anything" or "antibody-anything".
        num_designs: Number of designs to generate (default 10).
        output_dir: Directory for outputs (default "/tmp/proteus_ab").
        msa_mode: MSA generation mode — "none", "precomputed", or "nim".
        budget: Computational budget for the design run.

    Returns:
        JSON ToolResult with status and output_dir.
    """
    try:
        target_path = Path(target_pdb)
        if not target_path.exists():
            return _error(f"Target PDB not found: {target_pdb}")

        if not target_chains:
            return _error("At least one target chain is required.")

        if not binding_residues:
            return _error("At least one binding residue is required.")

        if protocol not in ("nanobody-anything", "antibody-anything"):
            return _error(
                f"Unknown protocol '{protocol}'. "
                f"Available: ['nanobody-anything', 'antibody-anything']"
            )

        # Build the design spec
        spec_path = build_design_spec(
            target_pdb=target_pdb,
            target_chains=target_chains,
            binding_residues=binding_residues,
            output_dir=output_dir,
        )

        # Run antibody design
        result = run_antibody_design(
            spec_path=spec_path,
            protocol=protocol,
            num_designs=num_designs,
            output_dir=output_dir,
            msa_mode=msa_mode,
            budget=budget,
        )

        return _result_json(result)

    except Exception as exc:
        return _error(f"proteus_ab_design failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 4: proteus_check_input
# ---------------------------------------------------------------------------


@mcp.tool()
def proteus_check_input(tool_name: str) -> str:
    """Validate that a Proteus tool is installed and its directory exists.

    Args:
        tool_name: Tool identifier — "proteus-fold", "proteus-prot",
            or "proteus-ab".

    Returns:
        JSON object with tool_name, status ("ok" or "error"), path, and
        optional error message.
    """
    try:
        path = validate_tool_path(tool_name)
        return json.dumps(
            {
                "tool_name": tool_name,
                "status": "ok",
                "path": str(path),
            },
            indent=2,
        )
    except (ValueError, FileNotFoundError) as exc:
        return json.dumps(
            {
                "tool_name": tool_name,
                "status": "error",
                "path": None,
                "error": str(exc),
            },
            indent=2,
        )
    except Exception as exc:
        return _error(f"proteus_check_input failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 5: proteus_parse_results
# ---------------------------------------------------------------------------


@mcp.tool()
def proteus_parse_results(tool_name: str, output_dir: str) -> str:
    """Parse results from a completed Proteus tool run.

    Calls the appropriate parser for the specified tool and returns
    structured design/prediction results.

    Args:
        tool_name: Tool identifier — "proteus-fold", "proteus-prot",
            or "proteus-ab".
        output_dir: Directory containing the tool's output files.

    Returns:
        JSON object with tool_name, output_dir, and parsed results
        (metrics for fold, designs list for prot/ab).
    """
    try:
        out = Path(output_dir)
        if not out.exists():
            return _error(f"Output directory not found: {output_dir}")

        if tool_name == "proteus-fold":
            metrics = parse_fold_output(output_dir)
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "output_dir": str(out),
                    "metrics": metrics,
                },
                indent=2,
            )

        elif tool_name == "proteus-prot":
            designs = parse_design_results(output_dir)
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "output_dir": str(out),
                    "designs": designs,
                    "design_count": len(designs),
                },
                indent=2,
            )

        elif tool_name == "proteus-ab":
            designs = parse_antibody_results(output_dir)
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "output_dir": str(out),
                    "designs": designs,
                    "design_count": len(designs),
                },
                indent=2,
            )

        else:
            return _error(
                f"Unknown tool '{tool_name}'. "
                f"Available: ['proteus-fold', 'proteus-prot', 'proteus-ab']"
            )

    except Exception as exc:
        return _error(f"proteus_parse_results failed: {exc}")


# ---------------------------------------------------------------------------
# Tool 6: proteus_download_target
# ---------------------------------------------------------------------------


@mcp.tool()
async def proteus_download_target(
    pdb_id: str,
    output_dir: str = "/tmp",
) -> str:
    """Download a PDB structure file from the RCSB for use as a design target.

    Args:
        pdb_id: 4-character PDB identifier (e.g. "7S4S").
        output_dir: Directory to save the file (default "/tmp").

    Returns:
        JSON object with pdb_id, path, and size_bytes.
    """
    pdb_id = pdb_id.strip().upper()
    if len(pdb_id) != 4:
        return _error(f"Invalid PDB ID: '{pdb_id}'. Must be 4 characters.")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{pdb_id}.pdb"

    try:
        download_url = f"{RCSB_DOWNLOAD_URL}/{pdb_id}.pdb"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                download_url, timeout=TIMEOUT, follow_redirects=True
            )
            resp.raise_for_status()
            file_path.write_bytes(resp.content)

        size_bytes = file_path.stat().st_size
        return json.dumps(
            {
                "pdb_id": pdb_id,
                "path": str(file_path),
                "size_bytes": size_bytes,
            },
            indent=2,
        )

    except httpx.HTTPError as exc:
        return _error(f"Failed to download {pdb_id}.pdb: {exc}")
    except OSError as exc:
        return _error(f"Failed to write file {file_path}: {exc}")
    except Exception as exc:
        return _error(f"proteus_download_target failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
