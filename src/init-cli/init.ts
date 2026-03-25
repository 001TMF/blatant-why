import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { copyTemplates, generateSettingsJson, registerMcpServers } from "./templates.js";
import { promptApiKeys } from "./api-keys.js";
import { verifyMcpServers } from "./verify.js";

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
 * Read the .gitignore-append template and append its contents to .gitignore.
 * Creates .gitignore if it doesn't exist. Skips lines already present.
 */
function appendGitignore(targetDir: string, templatesDir: string): void {
  const appendFile = join(templatesDir, ".gitignore-append");
  if (!existsSync(appendFile)) return;

  const appendContent = readFileSync(appendFile, "utf-8").trim();
  if (!appendContent) return;

  const gitignorePath = join(targetDir, ".gitignore");
  let existing = "";

  if (existsSync(gitignorePath)) {
    existing = readFileSync(gitignorePath, "utf-8");
  }

  // Collect lines that are not already present
  const existingLines = new Set(
    existing.split("\n").map(l => l.trim())
  );
  const newLines = appendContent
    .split("\n")
    .filter(line => !existingLines.has(line.trim()));

  if (newLines.length === 0) {
    console.log("  .gitignore already up to date");
    return;
  }

  // Ensure trailing newline before appending
  const separator = existing.endsWith("\n") ? "\n" : "\n\n";
  writeFileSync(gitignorePath, existing + separator + newLines.join("\n") + "\n");
  console.log(`  Appended ${newLines.length} line(s) to .gitignore`);
}

/**
 * Resolve the templates/ directory by walking up from this file to package.json.
 */
function findTemplatesDir(): string {
  // Walk up from the built file to find the package root
  const thisFile = fileURLToPath(import.meta.url);
  let dir = dirname(thisFile);
  while (dir !== resolve(dir, "..")) {
    if (existsSync(join(dir, "package.json"))) {
      return join(dir, "templates");
    }
    dir = resolve(dir, "..");
  }
  throw new Error("Could not find package root (no package.json found)");
}

/**
 * Main init orchestrator.
 */
export async function runInit(options: InitOptions): Promise<void> {
  const targetDir = process.cwd();

  console.log("");
  console.log("  BY INIT");
  console.log("  BY (Blatant-Why) protein design agent for Claude Code");
  console.log("");

  // Step 1: Check prerequisites
  checkPrereqs();
  console.log("");

  // Step 2: Copy templates
  console.log("Copying template files...");
  const copied = await copyTemplates(targetDir, options.force);
  console.log(`  ${copied} file(s) copied`);
  console.log("");

  // Step 3: Generate settings.json (non-MCP settings only)
  console.log("Generating .claude/settings.json...");
  await generateSettingsJson(targetDir);
  console.log("  Settings written (mcpServers removed — now in .mcp.json)");
  console.log("");

  // Step 3b: Register MCP servers via `claude mcp add -s project`
  console.log("Registering MCP servers...");
  const serverCount = await registerMcpServers(targetDir, ".claude/mcp_servers");
  console.log(`  ${serverCount} MCP server(s) registered via claude mcp add`);
  console.log("");

  // Step 4: Prompt for API keys
  await promptApiKeys(targetDir, options.skipKeys);
  console.log("");

  // Step 5: Append to .gitignore
  console.log("Updating .gitignore...");
  const templatesDir = findTemplatesDir();
  appendGitignore(targetDir, templatesDir);
  console.log("");

  // Step 6: Ensure .by/ directory exists
  mkdirSync(join(targetDir, ".by", "campaigns"), { recursive: true });

  // Step 7: Verify MCP servers via `claude mcp list`
  {
    console.log("Verifying MCP servers...");
    const { passed, failed } = verifyMcpServers();
    console.log(`  ${passed} server(s) OK`);
    if (failed.length > 0) {
      console.log(`  ${failed.length} server(s) failed: ${failed.join(", ")}`);
    }
    console.log("");
  }

  // Summary
  console.log("Initialization complete!");
  console.log("");
  console.log("Project structure created:");
  console.log("  .claude/agents/       Agent definitions");
  console.log("  .claude/skills/       Skill definitions");
  console.log("  .claude/commands/     Slash commands");
  console.log("  .claude/hooks/        Hook scripts");
  console.log("  .claude/scripts/      Hook shell scripts");
  console.log("  .claude/mcp_servers/  MCP server scripts");
  console.log("  .by/campaigns/        Campaign data");
  console.log("");
  console.log("Next steps:");
  console.log("  1. Verify MCP servers: claude mcp list");
  console.log("  2. Set API keys if skipped: edit .claude/settings.local.json");
  console.log("  3. Open Claude Code in this directory");
  console.log("  4. Try: /by:status or /by:load <PDB_ID>");
  console.log("");
}
