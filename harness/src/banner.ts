import { theme } from "./theme.js";

const BANNER_LINES = [
  " ██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗",
  " ██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝",
  " ██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗",
  " ██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║",
  " ██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║",
  " ╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝",
];

export function renderBanner(mode: string): string {
  const art = BANNER_LINES.map((line) => theme.primary(line)).join("\n");
  const subtitle = theme.dim("   Protein Design Agent") + "  " + theme.accent(`[${mode}]`);
  const modeLine = theme.dim(" Mode: ") + theme.accent(mode) + theme.dim("  (Shift+Tab to switch)");
  const helpLine = theme.dim(" Type ") + theme.accent("/help") + theme.dim(" for commands or describe what you want to design.");
  const hintLine = theme.dim(" \u2139 Natural language enabled. Try: ") + theme.accent("'list targets'") + theme.dim(" or ") + theme.accent("'design for PD-L1'");
  return art + "\n" + subtitle + "\n" + modeLine + "\n\n" + helpLine + "\n\n" + hintLine;
}
