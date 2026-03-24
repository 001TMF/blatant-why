import { query } from "@anthropic-ai/claude-code";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import { loadMcpServers } from "../agent.js";
import type {
  AgentDefinition,
  CampaignConfig,
  AgentResult,
} from "./types.js";
import { EventEmitter } from "events";

// Known long-running tools that should not block the TUI.
// When a subagent invokes one of these, the orchestrator emits a
// "long_running_job" event so the TUI can display status to the user.
const LONG_RUNNING_TOOLS = new Set([
  "tamarind_wait_for_job",
  "tamarind_submit_job",
  "tamarind_submit_batch",
  "levitate_run_rfantibody",
  "levitate_run_analysis",
  "local_run_boltzgen",
  "local_run_pxdesign",
  "local_run_protenix",
  "ssh_run_job",
]);

// Compute tools that require an approved campaign plan before execution.
// Research tools (PDB, UniProt, SAbDab, PubMed) are NOT gated.
const COMPUTE_TOOLS = new Set([
  "tamarind_submit_job",
  "tamarind_submit_batch",
  "tamarind_wait_for_job",
  "levitate_run_rfantibody",
  "levitate_run_analysis",
  "local_run_boltzgen",
  "local_run_pxdesign",
  "local_run_protenix",
  "ssh_run_job",
]);

export class CampaignOrchestrator extends EventEmitter {
  private campaignDir: string;
  private projectDir: string;
  private activeAgents: Map<string, AbortController> = new Map();
  private allMcpServers: Record<string, any>;

  constructor(config: CampaignConfig) {
    super();
    this.campaignDir = config.campaignDir;
    this.projectDir = config.projectDir;
    this.allMcpServers = loadMcpServers(this.projectDir);
  }

  /**
   * Spawn a single agent with scoped MCP servers and permissions.
   * Uses the Claude Code SDK query() to run an isolated agent session.
   */
  async spawnAgent(def: AgentDefinition, prompt: string): Promise<AgentResult> {
    const controller = new AbortController();
    this.activeAgents.set(def.name, controller);

    // Scope MCP servers to only what this agent needs
    const scopedServers: Record<string, any> = {};
    for (const serverName of def.mcpServers) {
      const directName = serverName;
      const prefixedName = `proteus-${serverName}`;
      const matchName = this.allMcpServers[directName] ? directName :
                        this.allMcpServers[prefixedName] ? prefixedName : null;
      if (matchName) {
        scopedServers[matchName] = this.allMcpServers[matchName];
      }
    }

    // Load system prompt from file
    const systemPrompt = this.loadPrompt(def.systemPromptPath);

    try {
      const result = await query({
        prompt,
        options: {
          cwd: this.projectDir,
          appendSystemPrompt: systemPrompt,
          maxTurns: def.maxTurns,
          permissionMode: "bypassPermissions",
          mcpServers: scopedServers,
          abortController: controller,
          ...(def.allowedTools ? { allowedTools: def.allowedTools } : {}),
          ...(def.disallowedTools ? { disallowedTools: def.disallowedTools } : {}),
        },
      });

      let resultText = "";
      for await (const message of result) {
        // Detect long-running tool invocations and emit a warning event
        if (message.type === "stream_event") {
          const event = (message as any).event;
          if (
            event?.type === "content_block_start" &&
            event.content_block?.type === "tool_use"
          ) {
            const toolName = event.content_block.name as string;

            // Gate: block compute tools until a campaign plan has been approved
            if (toolName && COMPUTE_TOOLS.has(toolName)) {
              const state = this.readCampaignState();
              if (!state || state.plan_approved !== true) {
                this.emit("plan_required", {
                  agentName: def.name,
                  toolName,
                  message:
                    "Campaign plan must be approved before submitting compute jobs. Present the plan to the user first.",
                });
              }
            }

            if (toolName && LONG_RUNNING_TOOLS.has(toolName)) {
              this.emit("long_running_job", {
                agentName: def.name,
                toolName,
                message: `${def.name} agent submitted a cloud job (${toolName}). This may take several minutes.`,
              });
            }
          }
        }

        if (message.type === "result") {
          resultText = (message as any).result ?? "";
        }
      }

      this.activeAgents.delete(def.name);
      this.emit("agent_complete", { name: def.name, success: true });
      return { agentName: def.name, resultText, success: true };
    } catch (err) {
      this.activeAgents.delete(def.name);
      const errorMsg = err instanceof Error ? err.message : "Unknown error";
      this.emit("agent_error", { name: def.name, error: errorMsg });
      return { agentName: def.name, resultText: "", success: false, costUsd: 0 };
    }
  }

  /**
   * Spawn multiple agents in parallel.
   * All agents run concurrently and results are gathered via Promise.all.
   */
  async spawnTeam(
    agents: Array<{ def: AgentDefinition; prompt: string }>,
  ): Promise<AgentResult[]> {
    return Promise.all(
      agents.map(({ def, prompt }) => this.spawnAgent(def, prompt)),
    );
  }

  /** Cancel a running agent by name. */
  cancelAgent(name: string): void {
    const controller = this.activeAgents.get(name);
    if (controller) {
      controller.abort();
      this.activeAgents.delete(name);
    }
  }

  /** Cancel all running agents. */
  cancelAll(): void {
    for (const [, controller] of this.activeAgents) {
      controller.abort();
    }
    this.activeAgents.clear();
  }

  /** Get names of currently active agents. */
  getActiveAgents(): string[] {
    return Array.from(this.activeAgents.keys());
  }

  /** Load a prompt file from the prompts directory. */
  private loadPrompt(relativePath: string): string {
    const fullPath = resolve(
      this.projectDir,
      "harness",
      "src",
      "agents",
      "prompts",
      relativePath,
    );
    try {
      return readFileSync(fullPath, "utf-8");
    } catch {
      return `You are a Proteus agent. Your role is defined by: ${relativePath}`;
    }
  }

  /** Read campaign state from the campaign_log.json file. */
  readCampaignState(): Record<string, unknown> | null {
    const statePath = resolve(this.campaignDir, "campaign_log.json");
    try {
      return JSON.parse(readFileSync(statePath, "utf-8"));
    } catch {
      return null;
    }
  }

  /**
   * Check if lab submission has been approved.
   * Approval must be recent (within 1 hour) to be valid.
   */
  isLabApproved(): boolean {
    const approvalPath = resolve(this.campaignDir, "lab", "approval.json");
    if (!existsSync(approvalPath)) return false;
    try {
      const approval = JSON.parse(readFileSync(approvalPath, "utf-8"));
      // Check timestamp is within 1 hour
      const elapsed = Date.now() - new Date(approval.timestamp).getTime();
      return approval.approved === true && elapsed < 3600000;
    } catch {
      return false;
    }
  }
}
