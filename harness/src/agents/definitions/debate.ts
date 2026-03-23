import type { AgentDefinition } from "../types.js";

export const hypothesisEpitopeAgent: AgentDefinition = {
  name: "hypothesis-epitope",
  role: "Propose a design strategy focused on epitope region selection",
  systemPromptPath: "hypothesis.md",
  mcpServers: ["pdb", "uniprot", "sabdab", "proteus-research", "proteus-campaign"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 10,
};

export const hypothesisScaffoldAgent: AgentDefinition = {
  name: "hypothesis-scaffold",
  role: "Propose a design strategy focused on scaffold and protocol selection",
  systemPromptPath: "hypothesis.md",
  mcpServers: ["pdb", "uniprot", "sabdab", "proteus-research", "proteus-campaign"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 10,
};

export const hypothesisParameterAgent: AgentDefinition = {
  name: "hypothesis-parameter",
  role: "Propose a design strategy focused on BoltzGen parameters and campaign sizing",
  systemPromptPath: "hypothesis.md",
  mcpServers: ["pdb", "proteus-campaign"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 10,
};

export const reflectionAgent: AgentDefinition = {
  name: "reflection",
  role: "Critique and rank competing design hypotheses",
  systemPromptPath: "reflection.md",
  mcpServers: ["proteus-campaign"],
  disallowedTools: ["Write", "Edit", "Bash", "NotebookEdit"],
  maxTurns: 15,
};
