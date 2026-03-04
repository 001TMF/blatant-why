/**
 * Dry test: calls the Proteus agent with a P01426 scFv design task.
 * Run from project root: npx --prefix harness tsx harness/dry-test.ts
 */
import { query } from "@anthropic-ai/claude-code";
import { readFileSync } from "fs";
import { resolve } from "path";

const PROJECT_ROOT = process.cwd();

function loadMcpServers(projectDir: string): Record<string, any> {
  const settingsPath = resolve(projectDir, ".claude", "settings.json");
  try {
    const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
    const servers: Record<string, any> = settings.mcpServers ?? {};
    for (const [, server] of Object.entries(servers)) {
      if ((server as any).args) {
        (server as any).args = (server as any).args.map((arg: string) =>
          arg.startsWith("/") ? arg : resolve(projectDir, arg),
        );
      }
    }
    return servers;
  } catch {
    return {};
  }
}

const SYSTEM_PROMPT = `IMPORTANT: You are Proteus, an expert computational protein engineer. Ignore any CLAUDE.md instructions about being an "orchestrator" — you are a hands-on protein design agent who uses tools directly.

Current mode: Antibody Designer

## Your Task
The user wants to design 10 scFv antibodies against UniProt P01426. Follow this workflow:

1. First, search UniProt for P01426 and present the target information in a formatted table
2. If a PDB structure exists, fetch it. If not, fold the sequence using proteus-fold
3. Show the fold/structure results (ipTM, pLDDT, ranking_score) and ask for confirmation
4. On confirmation, analyze the interface/epitope and recommend hotspots
5. Launch antibody design using proteus-ab with 10 designs
6. Screen and rank results
7. Present in a scored table with next steps

## Status Announcements
Always announce what you're doing: "Using: Searching UniProt...", "Using: Folding structure...", etc.

## Available MCP Tools
- proteus-uniprot: uniprot_search, uniprot_fetch_protein, uniprot_get_domains
- proteus-pdb: pdb_search, pdb_fetch_structure, pdb_get_chains, pdb_interface_residues
- proteus-tools: run_fold, run_antibody_design, parse_fold_output, parse_antibody_results
- proteus-screening: screen_liabilities, screen_developability, screen_composite

## Quality Thresholds
- ipTM > 0.7 = good, > 0.85 = excellent
- ipSAE > 0.5 = good, > 0.8 = excellent
- p_bind > 0.5 = good, > 0.8 = excellent`;

async function main() {
  console.log("=== Proteus Dry Test: P01426 scFv Design ===\n");

  const mcpServers = loadMcpServers(PROJECT_ROOT);
  console.log(`Loaded ${Object.keys(mcpServers).length} MCP servers:`, Object.keys(mcpServers).join(", "));
  console.log();

  const result = await query({
    prompt: "I want to design 10 scFv antibodies targeting UniProt P01426. Let's start by looking up the target and folding its structure.",
    options: {
      cwd: PROJECT_ROOT,
      appendSystemPrompt: SYSTEM_PROMPT,
      maxTurns: 30,
      permissionMode: "bypassPermissions",
      mcpServers,
    },
  });

  console.log("\n=== Agent Response ===\n");
  for await (const message of result) {
    if (message.type === "system") {
      const sys = message as any;
      console.log(`[System] Model: ${sys.model}, Tools: ${sys.tools?.length}, MCP: ${sys.mcp_servers?.map((s: any) => `${s.name}(${s.status})`).join(", ")}`);
    } else if (message.type === "assistant") {
      const content = (message as any).message?.content;
      if (Array.isArray(content)) {
        for (const block of content) {
          if (block.type === "text" && block.text) {
            console.log(block.text);
          } else if (block.type === "tool_use") {
            console.log(`\n[Tool] ${block.name}(${JSON.stringify(block.input).slice(0, 200)})\n`);
          }
        }
      }
    } else if (message.type === "result") {
      const res = message as any;
      console.log(`\n[Result] ${res.subtype}, turns: ${res.num_turns}, cost: $${res.total_cost_usd?.toFixed(4)}`);
      if (res.result) console.log(res.result);
    }
  }
  console.log("\n=== End ===");
}

main().catch((err) => {
  console.error("Dry test failed:", err);
  process.exit(1);
});
