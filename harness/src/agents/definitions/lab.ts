import type { AgentDefinition } from "../types.js";

export const labAgent: AgentDefinition = {
  name: "lab",
  role: "Prepare and submit designs to Adaptyv Bio for experimental testing",
  systemPromptPath: "lab.md",
  mcpServers: ["adaptyv"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 10,
};
