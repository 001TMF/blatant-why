import type { AgentDefinition } from "../types.js";

export const screeningAgent: AgentDefinition = {
  name: "screening",
  role: "Score, filter, and rank designs using screening battery",
  systemPromptPath: "screening.md",
  mcpServers: ["proteus-screening", "proteus-campaign"],
  disallowedTools: ["Write", "Edit"],
  maxTurns: 20,
};
