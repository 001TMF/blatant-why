#!/usr/bin/env node

import { runInit } from "./init.js";

interface CliFlags {
  help: boolean;
  skipKeys: boolean;
  force: boolean;
}

function parseArgs(argv: string[]): CliFlags {
  const flags: CliFlags = {
    help: false,
    skipKeys: false,
    force: false,
  };

  for (const arg of argv.slice(2)) {
    switch (arg) {
      case "--help":
      case "-h":
        flags.help = true;
        break;
      case "--skip-keys":
        flags.skipKeys = true;
        break;
      case "--force":
      case "-f":
        flags.force = true;
        break;
      default:
        console.error(`Unknown flag: ${arg}`);
        process.exit(1);
    }
  }

  return flags;
}

function printHelp(): void {
  console.log(`
by - BY (Blatant-Why) protein design agent for Claude Code

Usage:
  by [options]

Options:
  --help, -h       Show this help message
  --skip-keys      Skip API key prompts during init
  --force, -f      Overwrite existing files instead of skipping

Description:
  Initializes a new BY project in the current directory.
  Copies template files (.claude/, mcp_servers/, .by/) and
  generates .claude/settings.json with MCP server registrations.
`);
}

async function main(): Promise<void> {
  const flags = parseArgs(process.argv);

  if (flags.help) {
    printHelp();
    process.exit(0);
  }

  try {
    await runInit({
      skipKeys: flags.skipKeys,
      force: flags.force,
    });
  } catch (err) {
    console.error("Init failed:", err instanceof Error ? err.message : err);
    process.exit(1);
  }
}

main();
