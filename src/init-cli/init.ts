import { execSync } from "node:child_process";
import { copyTemplates, generateSettingsJson } from "./templates.js";

export interface InitOptions {
  skipKeys: boolean;
  force: boolean;
}

/**
 * Verify that `uv` is installed and available on PATH.
 */
function checkUv(): void {
  try {
    execSync("uv --version", { stdio: "pipe" });
  } catch {
    throw new Error(
      "uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    );
  }
}

/**
 * Verify Python >= 3.11 is available (via `python3 --version`).
 */
function checkPython(): void {
  try {
    const output = execSync("python3 --version", { stdio: "pipe" })
      .toString()
      .trim();
    const match = output.match(/Python (\d+)\.(\d+)/);
    if (!match) {
      throw new Error(`Could not parse Python version from: ${output}`);
    }
    const major = parseInt(match[1], 10);
    const minor = parseInt(match[2], 10);
    if (major < 3 || (major === 3 && minor < 11)) {
      throw new Error(
        `Python >= 3.11 required, found ${major}.${minor}. Install with: uv python install 3.11`
      );
    }
  } catch (err) {
    if (err instanceof Error && err.message.includes("Python >= 3.11")) {
      throw err;
    }
    throw new Error(
      "python3 is not installed. Install with: uv python install 3.11"
    );
  }
}

/**
 * Run all prerequisite checks.
 */
function checkPrereqs(): void {
  console.log("Checking prerequisites...");
  checkUv();
  console.log("  uv ......... OK");
  checkPython();
  console.log("  python3 .... OK (>= 3.11)");
}

/**
 * Main init orchestrator.
 */
export async function runInit(options: InitOptions): Promise<void> {
  const targetDir = process.cwd();

  console.log("");
  console.log("  PROTEUS INIT");
  console.log("  Protein design agent for Claude Code");
  console.log("");

  // Step 1: Check prerequisites
  checkPrereqs();
  console.log("");

  // Step 2: Copy templates
  console.log("Copying template files...");
  const copied = await copyTemplates(targetDir, options.force);
  console.log(`  ${copied} file(s) copied`);
  console.log("");

  // Step 3: Generate settings.json
  console.log("Generating .claude/settings.json...");
  const serverCount = await generateSettingsJson(targetDir, "mcp_servers");
  console.log(`  ${serverCount} MCP server(s) registered`);
  console.log("");

  // Summary
  console.log("Initialization complete!");
  console.log("");
  console.log("Project structure created:");
  console.log("  .claude/agents/       Agent definitions");
  console.log("  .claude/skills/       Skill definitions");
  console.log("  .claude/commands/     Slash commands");
  console.log("  .claude/hooks/        Hook scripts");
  console.log("  .claude/scripts/      Hook shell scripts");
  console.log("  mcp_servers/          MCP server scripts");
  console.log("  .proteus/campaigns/   Campaign data");
  console.log("");
  console.log("Next steps:");
  console.log("  1. Add MCP server scripts to mcp_servers/");
  console.log("  2. Run `proteus` again to regenerate settings.json");
  console.log("  3. Open Claude Code in this directory");
  console.log("");
}
