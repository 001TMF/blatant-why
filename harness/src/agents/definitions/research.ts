import type { AgentDefinition } from "../types.js";

export const researchAgent: AgentDefinition = {
  name: "research",
  role: "Target analysis, literature search, prior art identification",
  systemPromptPath: "research.md",
  mcpServers: ["pdb", "uniprot", "sabdab", "proteus-research", "proteus-knowledge"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 15,
};
