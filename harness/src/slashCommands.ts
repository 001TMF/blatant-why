export interface SlashCommandResult {
  handled: boolean;
  output?: string;
  local?: string;  // If set, this command is handled locally by the app (value is the command name)
}

export const SLASH_COMMANDS = [
  { name: "/help", description: "Show available commands" },
  { name: "/status", description: "Current campaign status" },
  { name: "/results", description: "Show ranked design results" },
  { name: "/screen", description: "Run screening battery" },
  { name: "/watch", description: "Watch pipeline progress" },
  { name: "/mode", description: "Show/switch current mode" },
  { name: "/load", description: "Load a target protein (PDB ID, UniProt ID, or name)" },
  { name: "/campaign", description: "Start or resume a design campaign" },
  { name: "/approve-lab", description: "Approve lab submission (requires CONFIRM)" },
  { name: "/costs", description: "Show campaign cost breakdown" },
  { name: "/team", description: "Show active agent team status" },
  { name: "/resume", description: "Resume a previous campaign" },
  { name: "/export", description: "Export conversation log (markdown or csv)" },
  { name: "/compare", description: "Compare metrics across campaign rounds" },
  { name: "/pareto", description: "Show Pareto-optimal designs (multi-objective trade-offs)" },
] as const;

export function getCompletions(input: string): typeof SLASH_COMMANDS[number][] {
  if (!input.startsWith("/") || input.includes(" ")) return [];
  return SLASH_COMMANDS.filter(c => c.name.startsWith(input));
}

export function handleSlashCommand(input: string): SlashCommandResult {
  const trimmed = input.trim();

  if (trimmed === "/help") {
    return {
      handled: true,
      output: [
        "Available commands:",
        "",
        "  /help         Show this help message",
        "  /status       Show current campaign status",
        "  /results      Show latest design results",
        "  /screen       Run screening battery on a design",
        "  /watch        Watch active pipeline progress",
        "  /mode         Show/switch current mode",
        "  /load         Load a target protein (PDB ID, UniProt ID, or name)",
        "  /campaign     Start or resume a design campaign",
        "  /approve-lab  Approve lab submission (requires CONFIRM)",
        "  /costs        Show campaign cost breakdown",
        "  /team         Show active agent team status",
        "  /resume       Resume a previous campaign",
        "  /export       Export conversation log (markdown or csv)",
        "  /compare      Compare metrics across campaign rounds",
        "  /pareto       Show Pareto-optimal designs (multi-objective trade-offs)",
        "",
        "Shift+Tab to cycle modes: Binder → Antibody → Structure",
        "",
        "Or just describe what you want to design in natural language.",
      ].join("\n"),
    };
  }

  if (trimmed === "/mode") {
    return {
      handled: true,
      output:
        "Current mode shown in prompt. Press Shift+Tab to cycle: Binder → Antibody → Structure",
    };
  }

  // /approve-lab, /costs, /team are handled locally by the app
  if (trimmed === "/approve-lab") {
    return { handled: true, local: "approve_lab" };
  }

  if (trimmed === "/costs") {
    return { handled: true, local: "show_costs" };
  }

  if (trimmed === "/team") {
    return { handled: true, local: "show_team" };
  }

  if (trimmed === "/resume") {
    return { handled: true, local: "resume_campaign" };
  }

  if (trimmed === "/compare") {
    return { handled: true, local: "compare_rounds" };
  }

  if (trimmed === "/export" || trimmed.startsWith("/export ")) {
    const arg = trimmed.slice("/export".length).trim().toLowerCase();
    if (arg === "csv") {
      return { handled: true, local: "export_csv" };
    }
    return { handled: true, local: "export_markdown" };
  }

  // /status, /results, /screen, /watch, /load, /campaign, /pareto are handled by the agent
  // Note: /watch is intercepted in app.tsx before this function is called
  return { handled: false };
}
