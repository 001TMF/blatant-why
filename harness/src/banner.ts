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
  return art + "\n" + subtitle + "\n" + modeLine;
}
