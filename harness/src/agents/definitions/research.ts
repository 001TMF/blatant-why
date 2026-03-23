import type { AgentDefinition } from "../types.js";

export const researchAgent: AgentDefinition = {
  name: "research",
  role: "Target analysis, literature search, prior art identification",
  systemPromptPath: "research.md",
  mcpServers: ["pdb", "uniprot", "sabdab", "research"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 15,
};
