/**
 * index.ts — entry point for the Proteus TUI.
 *
 * Detects the user's first name, renders <App> to the normal terminal
 * buffer (no alternate screen), and handles clean shutdown on signals.
 */

import React from "react";
import { render } from "ink";
import { App } from "./app.js";
import { resolve } from "path";
import { execSync } from "child_process";
import { userInfo } from "os";
import { readFileSync, existsSync } from "fs";

// Load .env from project root so TAMARIND_API_KEY etc. are available
const envPath = resolve(process.cwd(), "..", ".env");
if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf-8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
}

// ---------------------------------------------------------------------------
// Detect user's first name from GECOS field or username
// ---------------------------------------------------------------------------

function getForename(): string {
  try {
    const gecos = execSync(`getent passwd ${userInfo().username}`, {
      encoding: "utf-8",
      timeout: 1000,
    })
      .split(":")[4]
      ?.split(",")[0]
      ?.trim();
    if (gecos?.includes(" ")) return gecos.split(" ")[0];
    if (gecos) return gecos;
  } catch {
    /* fallback to username heuristics */
  }

  const u = userInfo().username;
  if (/[._-]/.test(u)) {
    return u
      .split(/[._-]/)[0]
      .replace(/^./, (c) => c.toUpperCase());
  }
  return u.charAt(0).toUpperCase() + u.slice(1);
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

const projectDir = resolve(process.cwd(), "..");
const forename = getForename();

// NO alternate screen — render to normal terminal buffer
const { unmount, waitUntilExit } = render(
  React.createElement(App, { projectDir, forename }),
  { exitOnCtrlC: false },
);

// Signal handling — double Ctrl+C to exit (like Claude Code)
let lastCtrlCTime = 0;

process.on("SIGINT", () => {
  const now = Date.now();
  if (now - lastCtrlCTime < 2000) {
    // Second Ctrl+C within 2 seconds — exit
    unmount();
    process.exit(0);
  }

  lastCtrlCTime = now;
  // Show hint to user (use stderr to avoid breaking Ink rendering)
  process.stderr.write("\n  Press Ctrl+C again to exit\n\n");
});
process.on("SIGTERM", () => {
  unmount();
  process.exit(0);
});

waitUntilExit().then(() => process.exit(0));
