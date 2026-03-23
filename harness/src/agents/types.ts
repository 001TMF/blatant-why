export interface AgentDefinition {
  name: string;
  role: string;
  systemPromptPath: string;  // path to .md file with full system prompt
  mcpServers: string[];       // names of MCP servers to include (subset of loaded servers)
  allowedTools?: string[];
  disallowedTools?: string[];
  maxTurns: number;
}

export type CampaignPhase =
  | "planning"
  | "researching"
  | "cost_estimate"
  | "debating"
  | "designing"
  | "screening"
  | "ranking"
  | "lab_pending"
  | "lab_submitted"
  | "lab_complete"
  | "iterating"
  | "complete"
  | "failed";

export interface PhaseResult {
  phase: CampaignPhase;
  success: boolean;
  output?: string;
  error?: string;
  costUsd?: number;
  durationMs?: number;
}

export interface CampaignConfig {
  campaignDir: string;
  configPath: string;
  projectDir: string;
}

export interface CampaignResult {
  campaignId: string;
  phases: PhaseResult[];
  totalCostUsd: number;
  totalDurationMs: number;
  finalStatus: CampaignPhase;
}

export interface AgentResult {
  agentName: string;
  resultText: string;
  success: boolean;
  costUsd?: number;
}

export interface MonitorEvent {
  type: "progress" | "stall" | "error" | "complete";
  runId: string;
  message: string;
  data?: Record<string, unknown>;
}

export type MonitorCallback = (event: MonitorEvent) => void;
