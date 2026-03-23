import { userInfo } from "os";
import { theme } from "./theme.js";

const PROTEIN_ART = [
  "⠀⠀⠀⣠⡤⠤⣤⡀⠀⠀⠀⠀⠀⣠⡤⠤⣤⡀⠀⠀",
  "⠀⢤⣿⣥⠀⠀⠙⢧⣤⠀⢀⣠⠿⠁⠀⠀⣤⡝⠧⠀",
  "⠀⠈⣹⡿⠀⢀⣴⠟⠁⠀⣾⣏⡀⠀⠀⠙⢿⣷⣄⠀",
  "⠀⣠⡾⠋⠀⣿⣇⡀⠀⠀⠈⠻⣿⣦⡀⠀⠀⣸⡿⠀",
  "⠀⢿⣧⣄⠀⠈⠻⢿⣦⠀⠀⢀⣼⠟⠀⣠⡾⠋⠀⠀",
  "⠀⠙⢿⣷⠄⠀⢀⣼⠟⠀⣴⡟⠁⠀⠐⢿⣷⣄⠀⠀",
  "⠀⠀⣠⡾⠋⣴⡟⠁⠀⠀⠻⣷⣦⡀⠀⠀⠙⢻⣷⠀",
  "⠀⣾⡏⠀⠀⠻⢿⣧⣤⠀⠀⠈⢹⣿⠀⢀⣠⠿⠃⠀",
  "⠀⠙⢿⣷⣄⠀⠈⣹⡿⠀⢀⣴⠟⠁⠀⣾⣏⡀⠀⠀",
  "⠀⠀⣸⡿⠀⣠⡾⠋⠀⠀⣿⣇⡀⠀⠀⠈⠻⣿⣦⡀",
  "⠀⣠⡾⠋⠀⢿⣧⣄⠀⠀⠈⠻⢿⣦⠀⠀⢀⣼⠟⠀",
  "⠐⢿⣷⣄⠀⠀⠙⢿⣷⠄⠀⢀⣼⠟⠀⣴⡟⠁⠀⠀",
  "⠀⠙⢻⣷⠀⠀⣠⡾⠋⠀⣴⡟⠁⠀⠀⠻⣷⣦⡀⠀",
  "⠀⠀⢀⡿⠃⠚⠋⣤⡀⠀⠛⣻⡧⠀⠀⠀⠈⣽⠛⠀",
  "⠀⠀⠾⠁⠀⠀⠀⠙⠓⠒⠛⠁⠀⠀⠀⠀⠀⠹⠆⠀",
];

const TITLE_LINES = [
  "██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗",
  "██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝",
  "██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗",
  "██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║",
  "██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║",
  "╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝",
];

export function renderBanner(mode: string): string {
  // Protein art in green (left side)
  const artLines = PROTEIN_ART.map((line) => theme.primary(line));

  // Title in green (right side), vertically centered against art
  const titleLines = TITLE_LINES.map((line) => theme.primary(line));

  // Combine: art on left, title on right
  // Art is 15 lines, title is 6 lines. Center title vertically.
  const spacer = "  ";
  const combined: string[] = [];
  const titleStart = Math.floor((artLines.length - titleLines.length) / 2);

  for (let i = 0; i < artLines.length; i++) {
    const titleIdx = i - titleStart;
    if (titleIdx >= 0 && titleIdx < titleLines.length) {
      combined.push(artLines[i] + spacer + titleLines[titleIdx]);
    } else {
      combined.push(artLines[i]);
    }
  }

  const art = combined.join("\n");
  const username = userInfo().username;
  const displayName = username.charAt(0).toUpperCase() + username.slice(1);
  const greeting = theme.dim("  Welcome back, ") + theme.accent(displayName) + theme.dim(". Ready to engineer proteins.");
  const modeLine = theme.dim("  Mode: ") + theme.accent(mode) + theme.dim("  (Shift+Tab to switch)");
  const helpLine = theme.dim("  Type ") + theme.accent("/help") + theme.dim(" for commands, or describe what you want to design.");

  return art + "\n\n" + greeting + "\n" + modeLine + "\n" + helpLine;
}
