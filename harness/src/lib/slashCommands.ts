/**
 * slashCommands.ts — command definitions and local handlers.
 *
 * Local commands are handled in app.tsx without sending to the agent.
 * Non-local commands are forwarded to the agent as regular prompts.
 */

export interface SlashCommand {
  name: string;
  description: string;
  local: boolean; // true = handled locally, false = sent to agent
}

export const COMMANDS: SlashCommand[] = [
  { name: "/help", description: "Show available commands", local: true },
  { name: "/campaign", description: "Show campaign status", local: true },
  { name: "/resume", description: "Resume a previous campaign", local: true },
  { name: "/compare", description: "Compare campaign rounds", local: true },
  { name: "/costs", description: "Show cost breakdown", local: true },
  { name: "/export", description: "Export conversation or designs", local: true },
  { name: "/view", description: "View structure in ProteinView", local: true },
  { name: "/approve-lab", description: "Approve lab submission", local: true },
  { name: "/jobs", description: "Show active cloud jobs", local: true },
  { name: "/plan", description: "Show campaign plan", local: false },
  { name: "/pareto", description: "Show Pareto-optimal designs", local: false },
  { name: "/screen", description: "Run screening on a design", local: false },
  { name: "/results", description: "Show ranked results", local: false },
  { name: "/status", description: "Show current status", local: false },
  { name: "/load", description: "Load a target protein", local: false },
];

/**
 * Return command names matching a partial prefix (for tab completion).
 */
export function getCompletions(partial: string): string[] {
  return COMMANDS.filter((c) => c.name.startsWith(partial)).map((c) => c.name);
}

/**
 * Format the help text shown by /help.
 */
export function formatHelp(): string {
  const lines = ["  Available Commands", ""];
  for (const cmd of COMMANDS) {
    lines.push(`  ${cmd.name.padEnd(16)} ${cmd.description}`);
  }
  lines.push("");
  lines.push("  Or just describe what you want to design.");
  return lines.join("\n");
}

/**
 * Check whether `input` matches a local command.
 * Returns the command name if local, null otherwise.
 */
export function isLocalCommand(input: string): string | null {
  const trimmed = input.trim();
  const cmd = COMMANDS.find(
    (c) => c.local && (trimmed === c.name || trimmed.startsWith(c.name + " ")),
  );
  return cmd ? cmd.name : null;
}
