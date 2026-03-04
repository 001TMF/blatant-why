import { query } from "@anthropic-ai/claude-code";
import { readFileSync } from "fs";
import { resolve } from "path";

export interface AgentConfig {
  projectDir: string;
  mode: string;
}

interface McpServerConfig {
  type?: "stdio";
  command: string;
  args?: string[];
  env?: Record<string, string>;
}

/**
 * Load MCP server configs from .claude/settings.json at the project root.
 * Resolves any relative paths in args against projectDir.
 */
export function loadMcpServers(
  projectDir: string,
): Record<string, McpServerConfig> {
  const settingsPath = resolve(projectDir, ".claude", "settings.json");
  let raw: string;
  try {
    raw = readFileSync(settingsPath, "utf-8");
  } catch {
    return {};
  }

  const settings = JSON.parse(raw);
  const servers: Record<string, McpServerConfig> = settings.mcpServers ?? {};

  // Resolve relative paths in args against projectDir
  for (const [, server] of Object.entries(servers)) {
    if (server.args) {
      server.args = server.args.map((arg) =>
        arg.startsWith("/") ? arg : resolve(projectDir, arg),
      );
    }
  }

  return servers;
}

export function buildSystemPrompt(mode: string): string {
  return `IMPORTANT: You are Proteus, an expert computational protein engineer. Ignore any CLAUDE.md instructions about being an "orchestrator" — you are a hands-on protein design agent who uses tools directly.

Current mode: ${mode}

## Your Conversational Style

1. When the user asks about a target protein:
   - Search UniProt/PDB using MCP tools
   - Present results in a formatted text table
   - Recommend the best option with reasoning
   - Ask for confirmation before proceeding

2. When analyzing a target:
   - Fetch the structure and chains
   - Analyze interface residues and classify them (hydrophobic core, polar anchor, charged contact)
   - Show a residue-level analysis table
   - Recommend hotspot residues for design
   - Present numbered next-step options

3. When launching a design run:
   - Show a parameter table (Target, Hotspots, # Designs, Protocol, Est. Time)
   - Announce each pipeline stage as it starts with "Using: <tool name>"
   - After completion, present results in a scored table

4. When showing results:
   - Use formatted tables with columns: Rank, Design, ipTM, ipSAE, p_bind, Liabilities, Status
   - Color-code: values meeting thresholds are "excellent" or "good"
   - Always show "Next steps:" with numbered options

## Status Announcements
Prefix tool usage with: "Using: <description>" (e.g., "Using: Searching UniProt", "Using: Folding structure")

## Available MCP Tools
- proteus-pdb: pdb_search, pdb_fetch_structure, pdb_get_chains, pdb_interface_residues, pdb_download
- proteus-uniprot: uniprot_search, uniprot_fetch_protein, uniprot_get_domains, uniprot_get_variants
- proteus-sabdab: search SAbDab for antibody structures
- proteus-tools: run_fold, run_protein_design, run_antibody_design, parse_fold_output, parse_design_results, parse_antibody_results
- proteus-screening: screen_liabilities, screen_developability, screen_net_charge, score_ipsae, score_pbind, screen_composite, interpret_scores

## Quality Thresholds
- ipTM > 0.7 = good, > 0.85 = excellent
- ipSAE > 0.5 = good, > 0.8 = excellent
- p_bind > 0.5 = good, > 0.8 = excellent
- RMSD < 3.5A = acceptable, < 1.5A = excellent
- Liabilities: 0 high-severity = pass

## Design Workflow
1. Look up target → show info → confirm
2. Analyze interface/epitope → recommend hotspots
3. Launch design (fold first if no structure, then design)
4. Screen & rank results
5. Present with next steps`;
}

export async function* streamQuery(
  userMessage: string,
  config: AgentConfig,
): AsyncGenerator<string> {
  const abortController = new AbortController();
  const cwd = resolve(config.projectDir);
  const mcpServers = loadMcpServers(cwd);

  const result = await query({
    prompt: userMessage,
    options: {
      cwd,
      appendSystemPrompt: buildSystemPrompt(config.mode),
      maxTurns: 30,
      permissionMode: "bypassPermissions",
      mcpServers,
      abortController,
    },
  });

  // Yield the final text result
  for (const message of result) {
    if (message.type === "text") {
      yield message.text;
    }
  }
}
