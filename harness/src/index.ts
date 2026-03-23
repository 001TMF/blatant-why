#!/usr/bin/env node

// Force true-color support for the TUI
process.env.FORCE_COLOR = '3';  // Level 3 = 16 million colors (TrueColor)

import { render } from "ink";
import React from "react";
import ansiEscapes from "ansi-escapes";
import { App } from "./app.js";
import { streamQuery, AgentConfig, StreamEvent } from "./agent.js";

async function main() {
  const config: AgentConfig = {
    projectDir: process.cwd(),
    mode: "vhh",
  };

  async function* queryFn(
    input: string,
    sessionId?: string,
    abortController?: AbortController,
  ): AsyncGenerator<StreamEvent> {
    yield* streamQuery(input, config, sessionId, abortController);
  }

  // Detect if we're in a real terminal (not piped)
  const isTTY = process.stdout.isTTY ?? false;

  if (isTTY) {
    // Enter alternate screen buffer for full-screen TUI
    process.stdout.write(ansiEscapes.enterAlternativeScreen);
    process.stdout.write(ansiEscapes.cursorHide);
  }

  if (!isTTY) {
    console.log("Proteus v0.1.0 — protein design agent");
  }

  let cleanedUp = false;
  const cleanup = () => {
    if (cleanedUp) return;
    cleanedUp = true;
    if (isTTY) {
      process.stdout.write(ansiEscapes.cursorShow);
      process.stdout.write(ansiEscapes.exitAlternativeScreen);
    }
  };

  const { unmount, waitUntilExit } = render(
    React.createElement(App, {
      queryFn,
      initialMode: "vhh",
      configRef: config,
    }),
    {
      exitOnCtrlC: false, // We handle Ctrl+C ourselves
    },
  );

  // SIGINT (Ctrl+C) is handled by the app component
  // Double Ctrl+C calls process.exit(0) which triggers the cleanup below

  // Clean exit on SIGTERM
  process.on("SIGTERM", () => {
    unmount();
    cleanup();
    process.exit(0);
  });

  // Ensure cleanup on normal exit
  process.on("exit", cleanup);

  // Handle uncaught errors gracefully
  process.on("uncaughtException", (err) => {
    unmount();
    cleanup();
    console.error("Fatal error:", err.message);
    process.exit(1);
  });

  await waitUntilExit();
  cleanup();
}

main().catch((err) => {
  // Restore terminal even on startup errors
  if (process.stdout.isTTY) {
    process.stdout.write(ansiEscapes.cursorShow);
    process.stdout.write(ansiEscapes.exitAlternativeScreen);
  }
  console.error(err);
  process.exit(1);
});
