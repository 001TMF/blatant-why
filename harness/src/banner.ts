import { userInfo } from "os";
import { theme } from "./theme.js";

// No protein art — clean banner with title only

const TITLE_LINES = [
  "██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗",
  "██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝",
  "██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗",
  "██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║",
  "██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║",
  "╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝",
];

function getForename(): string {
  const username = userInfo().username;
  // Handle common patterns: "tristanfarmer" -> "Tristan", "tristan.farmer" -> "Tristan", "tristan_farmer" -> "Tristan"
  let forename = username;
  // Split on dots, underscores, hyphens
  if (/[._-]/.test(username)) {
    forename = username.split(/[._-]/)[0];
  } else {
    // Try to detect camelCase boundary (e.g., "tristanFarmer")
    const camelMatch = username.match(/^[a-z]+/);
    if (camelMatch) {
      // Check if the remaining part starts with uppercase (camelCase) or is all lowercase (single word or concatenated)
      const rest = username.slice(camelMatch[0].length);
      if (rest && /^[A-Z]/.test(rest)) {
        forename = camelMatch[0];
      } else {
        // All lowercase concatenated — heuristic: common first names are 3-8 chars
        // Try to find a reasonable split point by checking if first 3-8 chars form a name
        forename = username; // fallback to full username
      }
    }
  }
  return forename.charAt(0).toUpperCase() + forename.slice(1).toLowerCase();
}

export function renderBanner(mode: string): string {
  const titleLines = TITLE_LINES.map((line) => "  " + theme.primary(line));
  const title = titleLines.join("\n");

  const displayName = getForename();
  const subtitle = theme.dim("  AI-Powered Biologics Design Campaign Agent");
  const greeting = theme.dim("  Welcome back, ") + theme.accent(displayName) + theme.dim(". Ready to engineer proteins.");
  const modeLine = theme.dim("  Mode: ") + theme.accent(mode) + theme.dim("  (Shift+Tab to switch)");
  const helpLine = theme.dim("  Type ") + theme.accent("/help") + theme.dim(" for commands, or describe what you want to design.");

  return title + "\n" + subtitle + "\n\n" + greeting + "\n" + modeLine + "\n" + helpLine;
}
