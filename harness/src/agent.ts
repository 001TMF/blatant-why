import { query } from "@anthropic-ai/claude-code";
import { resolve } from "path";

export interface AgentConfig {
  projectDir: string;
  mode: string;
  mcpServers: Record<string, { command: string; args: string[] }>;
}

export function buildSystemPrompt(mode: string): string {
  return [
    "You are Proteus, an expert computational protein engineer.",
    `Current mode: ${mode}.`,
    "Use the Proteus tool suite for protein and antibody design.",
    "Always run screening before presenting final candidates.",
    "Present results with scores, interpretation, and numbered next steps.",
  ].join(" ");
}

export async function* streamQuery(
  userMessage: string,
  config: AgentConfig,
): AsyncGenerator<string> {
  const abortController = new AbortController();

  const result = await query({
    prompt: userMessage,
    systemPrompt: buildSystemPrompt(config.mode),
    options: {
      maxTurns: 10,
    },
    abortController,
  });

  // Yield the final text result
  for (const message of result) {
    if (message.type === "text") {
      yield message.text;
    }
  }
}
