import type { AgentDefinition } from "../types.js";

export const screeningAgent: AgentDefinition = {
  name: "screening",
  role: "Score, filter, and rank designs using screening battery",
  systemPromptPath: "screening.md",
  mcpServers: ["screening", "campaign"],
  disallowedTools: ["Write", "Edit"],
  maxTurns: 20,
};
