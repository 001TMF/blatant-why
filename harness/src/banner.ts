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

export function getForename(): string {
  // Try GECOS field first (has real name: "Tristan Farmer" → "Tristan")
  try {
    const { execSync } = require("child_process");
    const gecos = execSync(`getent passwd ${userInfo().username}`, { encoding: "utf-8", timeout: 1000 })
      .split(":")[4]?.split(",")[0]?.trim();
    if (gecos && gecos.includes(" ")) {
      return gecos.split(" ")[0]; // First name from "Tristan Farmer"
    }
    if (gecos) return gecos;
  } catch { /* fallback below */ }

  const username = userInfo().username;
  // Split on dots, underscores, hyphens
  if (/[._-]/.test(username)) {
    const part = username.split(/[._-]/)[0];
    return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
  }
  // CamelCase: "tristanFarmer" → "tristan"
  const camelMatch = username.match(/^([a-z]+)[A-Z]/);
  if (camelMatch) {
    const part = camelMatch[1];
    return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
  }
  // Fallback: capitalize first letter of full username
  return username.charAt(0).toUpperCase() + username.slice(1);
}

export function renderBanner(mode: string, termWidth: number = 120): string {
  const displayName = getForename();

  // Narrow terminal: compact single-line banner
  if (termWidth < 65) {
    const compact = theme.primary("PROTEUS") + theme.dim(" \u2014 Biologics Design");
    const greeting = theme.dim("Welcome, ") + theme.accent(displayName);
    const modeLine = theme.dim("Mode: ") + theme.accent(mode);
    return compact + "\n" + greeting + "  " + modeLine;
  }

  // Standard: full ASCII art banner
  const titleLines = TITLE_LINES.map((line) => "  " + theme.primary(line));
  const title = titleLines.join("\n");

  const subtitle = theme.dim("  AI-Powered Biologics Design Campaign Agent");
  const greeting = theme.dim("  Welcome back, ") + theme.accent(displayName) + theme.dim(". Ready to engineer proteins.");
  const modeLine = theme.dim("  Mode: ") + theme.accent(mode) + theme.dim("  (Shift+Tab to switch)");
  const helpLine = theme.dim("  Type ") + theme.accent("/help") + theme.dim(" for commands, or describe what you want to design.");

  return title + "\n" + subtitle + "\n\n" + greeting + "\n" + modeLine + "\n" + helpLine;
}
