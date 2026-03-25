import * as fs from "node:fs";
import * as path from "node:path";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

/**
 * Resolve the templates/ directory relative to this package's root.
 * Works both when running from src (dev) and from dist (installed).
 */
function getTemplatesDir(): string {
  const thisFile = fileURLToPath(import.meta.url);
  // In dist: dist/templates.js -> project root -> templates/
  // In dev:  src/init-cli/templates.ts -> project root -> templates/
  let root = path.dirname(thisFile);
  // Walk up until we find package.json
  while (root !== path.dirname(root)) {
    if (fs.existsSync(path.join(root, "package.json"))) {
      break;
    }
    root = path.dirname(root);
  }
  return path.join(root, "templates");
}

/**
 * Recursively copy all files from srcDir to destDir.
 * Skips existing files unless force is true.
 * Returns number of files copied.
 */
function copyDirRecursive(
  srcDir: string,
  destDir: string,
  force: boolean
): number {
  let count = 0;

  if (!fs.existsSync(srcDir)) {
    return count;
  }

  // Ensure destination directory exists
  fs.mkdirSync(destDir, { recursive: true });

  const entries = fs.readdirSync(srcDir, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(srcDir, entry.name);
    const destPath = path.join(destDir, entry.name);

    if (entry.isDirectory()) {
      count += copyDirRecursive(srcPath, destPath, force);
    } else if (entry.isFile()) {
      if (fs.existsSync(destPath) && !force) {
        // Skip existing files
        continue;
      }
      fs.copyFileSync(srcPath, destPath);
      count++;
    }
  }

  return count;
}

/**
 * Ensure a directory structure exists, creating empty dirs as needed.
 * Used to create placeholder directories even if there are no template files.
 */
function ensureDirs(targetDir: string, dirs: string[]): void {
  for (const dir of dirs) {
    fs.mkdirSync(path.join(targetDir, dir), { recursive: true });
  }
}

/**
 * Copy template files to the target directory.
 * Creates the full directory skeleton and copies any template files.
 *
 * @param targetDir - The target directory (usually cwd)
 * @param force - Overwrite existing files if true
 * @returns Number of files copied
 */
export async function copyTemplates(
  targetDir: string,
  force: boolean
): Promise<number> {
  const templatesDir = getTemplatesDir();

  // Ensure the full directory skeleton exists regardless of template contents
  ensureDirs(targetDir, [
    ".claude/agents",
    ".claude/skills",
    ".claude/commands/by",
    ".claude/hooks",
    ".claude/scripts",
    "mcp_servers",
    ".by/campaigns",
  ]);

  // Copy template files
  const count = copyDirRecursive(templatesDir, targetDir, force);

  return count;
}

/**
 * Generate .claude/settings.json for non-MCP settings (hooks, permissions, env).
 * MCP servers are registered separately via `claude mcp add` (see registerMcpServers).
 *
 * If an existing settings.json contains an `mcpServers` key, it is removed
 * since MCP servers now live in .mcp.json (managed by `claude mcp add -s project`).
 *
 * @param targetDir - The project root directory
 */
export async function generateSettingsJson(
  targetDir: string
): Promise<void> {
  const settingsDir = path.join(targetDir, ".claude");
  const settingsFile = path.join(settingsDir, "settings.json");

  fs.mkdirSync(settingsDir, { recursive: true });

  const settings: Record<string, unknown> = {};

  // Read existing settings if present
  if (fs.existsSync(settingsFile)) {
    try {
      const existing = JSON.parse(fs.readFileSync(settingsFile, "utf-8"));
      Object.assign(settings, existing);
    } catch {
      // Ignore parse errors; we will overwrite
    }
  }

  // Remove mcpServers — they now live in .mcp.json via `claude mcp add`
  delete settings["mcpServers"];

  fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + "\n");
}

/**
 * Scan the mcp_servers/ directory for Python server scripts and register
 * each one with Claude Code via `claude mcp add -s project`.
 *
 * This writes to .mcp.json (the file Claude Code actually reads for MCP servers),
 * instead of .claude/settings.json which Claude Code ignores for MCP config.
 *
 * @param targetDir - The project root directory
 * @param mcpServerDir - Relative path to the MCP servers directory
 * @returns Number of MCP servers successfully registered
 */
export async function registerMcpServers(
  targetDir: string,
  mcpServerDir: string
): Promise<number> {
  const serversPath = path.join(targetDir, mcpServerDir);
  let registered = 0;

  if (!fs.existsSync(serversPath)) {
    return registered;
  }

  // Read .env if it exists — MCP servers need env vars to connect to services
  const envFile = path.join(targetDir, ".env");
  const envVars: Record<string, string> = {};
  if (fs.existsSync(envFile)) {
    const envContent = fs.readFileSync(envFile, "utf-8");
    for (const line of envContent.split("\n")) {
      const match = line.match(/^([A-Z_]+)=(.+)$/);
      if (match && !match[2].startsWith("#")) {
        envVars[match[1]] = match[2];
      }
    }
  }

  // Map which servers need which env vars
  const serverEnvMap: Record<string, string[]> = {
    cloud: [
      "TAMARIND_API_KEY",
      "PROTEUS_FOLD_DIR",
      "PROTEUS_PROT_DIR",
      "PROTEUS_AB_DIR",
    ],
    tamarind: ["TAMARIND_API_KEY"],
    local_compute: ["PROTEUS_FOLD_DIR", "PROTEUS_PROT_DIR", "PROTEUS_AB_DIR"],
  };

  // Scan subdirectories for server.py (e.g. mcp_servers/pdb/server.py)
  const dirs = fs.readdirSync(serversPath, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith("_"));

  for (const dir of dirs) {
    const serverPy = path.join(serversPath, dir.name, "server.py");
    if (!fs.existsSync(serverPy)) continue;

    const serverName = `by-${dir.name.replace(/_/g, "-")}`;
    const scriptPath = path.join(mcpServerDir, dir.name, "server.py");

    // Build -e flags for env vars this server needs
    const neededVars = serverEnvMap[dir.name] || [];
    const envFlags = neededVars
      .filter((key) => envVars[key])
      .map((key) => `-e ${key}="${envVars[key]}"`)
      .join(" ");

    try {
      execSync(
        `claude mcp add -s project ${envFlags} "${serverName}" -- uv run --script "${scriptPath}"`,
        { stdio: "pipe", cwd: targetDir }
      );
      console.log(`  ✓ Registered ${serverName}`);
      registered++;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.log(`  ⚠ Failed to register ${serverName}: ${msg}`);
    }
  }

  return registered;
}
