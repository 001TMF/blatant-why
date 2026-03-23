import type { AgentDefinition } from "../types.js";

export const designAgent: AgentDefinition = {
  name: "design",
  role: "Generate antibody/binder designs via cloud or local tools",
  systemPromptPath: "design.md",
  mcpServers: ["pdb", "screening", "tamarind", "levitate", "campaign"],
  maxTurns: 30,
};
