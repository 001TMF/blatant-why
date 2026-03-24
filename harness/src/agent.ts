/**
 * agent.ts — SDK wrapper + system prompt builder
 *
 * Bridge between the TUI and the Claude Code SDK.
 * Exports loadMcpServers, buildSystemPrompt, streamQuery, and types
 * consumed by agents/orchestrator.ts and hooks/useAgent.ts.
 */

import { query } from "@anthropic-ai/claude-code";
import type {
  McpServerConfig,
  McpStdioServerConfig,
  Options,
  SDKMessage,
  SDKAssistantMessage,
  SDKPartialAssistantMessage,
  SDKResultMessage,
  SDKSystemMessage,
} from "@anthropic-ai/claude-code";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentConfig {
  projectDir: string;
  cwd?: string;
  model?: string;
  maxTurns?: number;
  permissionMode?: Options["permissionMode"];
  /** Extra MCP servers to merge (e.g. campaign-specific) */
  extraMcpServers?: Record<string, McpServerConfig>;
  /** Append to system prompt */
  appendSystemPrompt?: string;
  /** Abort handle */
  abortController?: AbortController;
  /** Session ID to resume multi-turn conversation */
  resume?: string;
}

/** Discriminated union of events yielded by streamQuery */
export type StreamEvent =
  | { type: "system_init"; data: SDKSystemMessage }
  | { type: "text_delta"; text: string }
  | { type: "tool_start"; toolName: string; toolUseId: string }
  | { type: "tool_end"; toolUseId: string }
  | { type: "assistant_message"; data: SDKAssistantMessage }
  | { type: "result"; text: string; costUsd: number; durationMs: number }
  | { type: "error"; message: string };

// ---------------------------------------------------------------------------
// loadMcpServers — reads .claude/settings.json, resolves command paths
// ---------------------------------------------------------------------------

export function loadMcpServers(
  projectDir: string,
): Record<string, McpServerConfig> {
  const settingsPath = resolve(projectDir, ".claude", "settings.json");
  if (!existsSync(settingsPath)) {
    return {};
  }

  let raw: Record<string, unknown>;
  try {
    raw = JSON.parse(readFileSync(settingsPath, "utf-8"));
  } catch {
    return {};
  }

  const mcpRaw = raw.mcpServers as
    | Record<string, Record<string, unknown>>
    | undefined;
  if (!mcpRaw || typeof mcpRaw !== "object") return {};

  const servers: Record<string, McpServerConfig> = {};

  for (const [name, config] of Object.entries(mcpRaw)) {
    if (!config || typeof config !== "object") continue;

    const command = config.command as string | undefined;
    if (!command) continue;

    // Resolve relative arg paths against projectDir
    const args = (config.args as string[] | undefined) ?? [];
    const resolvedArgs = args.map((a) =>
      a.startsWith("/") || a.startsWith("-") ? a : resolve(projectDir, a),
    );

    const env = (config.env as Record<string, string> | undefined) ?? {};

    const serverConfig: McpStdioServerConfig = {
      type: "stdio",
      command,
      args: resolvedArgs,
      env,
    };

    servers[name] = serverConfig;
  }

  return servers;
}

// ---------------------------------------------------------------------------
// buildSystemPrompt — the long system prompt for the TUI agent
// ---------------------------------------------------------------------------

export function buildSystemPrompt(): string {
  return `You are Proteus, an expert computational protein engineer and biologics design agent.

## Communication Style

By default, communicate as a knowledgeable colleague speaking to a biologist:
- Use plain language with standard biological terminology
- Explain computational concepts when relevant (e.g. "ipSAE measures how well the predicted interface aligns structurally")
- When the user demonstrates computational expertise, match their level

When presenting results or plans, use structured formats:
- Tables for scores, parameters, comparisons
- Numbered lists for action steps
- Bold for key findings or warnings

## Tool Priority

When researching a target, use MCP research tools FIRST:
1. PDB (pdb_search, pdb_fetch_structure) for structural data
2. UniProt (uniprot_search, uniprot_fetch_protein) for sequence and function
3. SAbDab (sabdab_search) for existing antibody/nanobody binders
4. PubMed / bioRxiv for recent literature
5. WebSearch only as a last resort

Always name tools explicitly: say "Protenix" not "structure prediction tool",
"BoltzGen" not "antibody design tool", "PXDesign" not "binder design tool".

## Scoring & Metrics

Primary metric: **ipSAE** (interface Predicted Structural Accuracy Error)
- Open-source TM-align metric from DunbrackLab
- d0 = 1.24 * (clamp(n0, 19) - 15)^(1/3) - 1.8
- Range: 0-1, higher is better. >0.5 good, >0.8 excellent
- Always rank by ipSAE first, then ipTM as tiebreaker

Secondary: ipTM (>0.7 good, >0.85 excellent), pLDDT (>70 good, >90 excellent)

Composite: 0.50*ipSAE_min + 0.30*ipTM + 0.20*(1 - normalized_liability_count)

## Campaign Planning

Before any compute-intensive work:
1. Research the target autonomously (no approval needed for database lookups)
2. Present a structured campaign plan with:
   - Target summary, epitope analysis, modality choice
   - Parameter table (tool, scaffolds, N designs, budget, alpha, provider)
   - Cost estimate
   - Success criteria / go-no-go gates
3. Wait for user approval before submitting compute jobs
4. Never bypass the plan-then-execute pattern

## Fold Validation (required before design)

Before designing binders against a target, verify computational fold quality:
1. Run Protenix on the target structure to check it folds correctly in silico
2. If using a cropped epitope region, verify the crop maintains its fold (ipTM > 0.7, pLDDT > 70)
3. If fold quality is poor, warn the user and suggest using the full structure or a different epitope region
4. Include fold validation results in the campaign plan

## Modality Detection (automatic)

Detect from user language:
- "nanobody", "VHH", "sdAb" -> BoltzGen nanobody-anything protocol
- "antibody", "scFv", "Fab", "mAb" -> BoltzGen antibody-anything protocol
- "binder", "miniprotein", "de novo" -> PXDesign or BoltzGen protein-anything
- Ambiguous -> default to VHH (simplest, most robust)

## Safety Gates

- Research tools: freely available, no gates
- Compute tools: require an approved campaign plan
- Lab submission (Adaptyv Bio): requires explicit /approve-lab command
  - NEVER attempt to bypass the triple-layer confirmation system
  - adaptyv_estimate_cost is always safe to call

## Screening Battery (always before presenting final candidates)

- Liabilities: NG/NS deamidation, DG isomerization, Met oxidation, free Cys, glycosylation
- Developability: net charge pH 7.4, CDR length, hydrophobic fraction
- Structure: ipTM>0.5, pLDDT>70, RMSD<3.5A
- Never present unscreened designs as final candidates`;
}

// ---------------------------------------------------------------------------
// streamQuery — async generator wrapping the SDK, yields StreamEvents
// ---------------------------------------------------------------------------

export async function* streamQuery(
  prompt: string,
  config: AgentConfig,
): AsyncGenerator<StreamEvent, void, undefined> {
  const mcpServers = {
    ...loadMcpServers(config.projectDir),
    ...(config.extraMcpServers ?? {}),
  };

  const systemPrompt = buildSystemPrompt() + (config.appendSystemPrompt ? "\n\n" + config.appendSystemPrompt : "");

  const options: Options = {
    cwd: config.cwd ?? config.projectDir,
    appendSystemPrompt: systemPrompt,
    maxTurns: config.maxTurns ?? 30,
    permissionMode: config.permissionMode ?? "bypassPermissions",
    mcpServers,
    abortController: config.abortController,
    model: config.model,
    includePartialMessages: true,
    resume: config.resume,
  };

  const stream = query({ prompt, options });

  try {
    for await (const message of stream) {
      const events = processSDKMessage(message);
      for (const event of events) {
        yield event;
      }
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    // Suppress clean cancellations
    if (!msg.includes("abort") && !msg.includes("AbortError")) {
      yield { type: "error", message: msg };
    }
  }
}

// ---------------------------------------------------------------------------
// Internal: convert SDK messages to StreamEvents
// ---------------------------------------------------------------------------

function processSDKMessage(message: SDKMessage): StreamEvent[] {
  const events: StreamEvent[] = [];

  switch (message.type) {
    case "system": {
      const sys = message as SDKSystemMessage;
      if (sys.subtype === "init") {
        events.push({ type: "system_init", data: sys });
      }
      break;
    }

    case "assistant": {
      const asst = message as SDKAssistantMessage;
      events.push({ type: "assistant_message", data: asst });
      break;
    }

    case "stream_event": {
      const partial = message as SDKPartialAssistantMessage;
      const rawEvent = partial.event as Record<string, unknown>;

      if (rawEvent.type === "content_block_start") {
        const block = rawEvent.content_block as Record<string, unknown> | undefined;
        if (block?.type === "tool_use") {
          events.push({
            type: "tool_start",
            toolName: block.name as string,
            toolUseId: block.id as string,
          });
        }
      }

      if (rawEvent.type === "content_block_delta") {
        const delta = rawEvent.delta as Record<string, unknown> | undefined;
        if (delta?.type === "text_delta" && typeof delta.text === "string") {
          events.push({ type: "text_delta", text: delta.text });
        }
      }

      if (rawEvent.type === "content_block_stop") {
        // We don't have the tool_use_id in the stop event easily,
        // but downstream consumers track active tools by start events
        const idx = rawEvent.index;
        if (typeof idx === "number") {
          events.push({ type: "tool_end", toolUseId: String(idx) });
        }
      }
      break;
    }

    case "result": {
      const res = message as SDKResultMessage;
      const text = res.subtype === "success" ? (res as { result: string }).result : "";
      events.push({
        type: "result",
        text,
        costUsd: res.total_cost_usd,
        durationMs: res.duration_ms,
      });
      break;
    }

    default:
      // user messages, replay messages, compact boundaries — ignored by TUI
      break;
  }

  return events;
}
