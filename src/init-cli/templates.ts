import * as fs from "node:fs";
import * as path from "node:path";
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
 * Scan the mcp_servers/ directory for Python scripts and generate
 * .claude/settings.json with uv run --script commands.
 *
 * @param targetDir - The project root directory
 * @param mcpServerDir - Relative path to the MCP servers directory
 * @returns Number of MCP servers registered
 */
export async function generateSettingsJson(
  targetDir: string,
  mcpServerDir: string
): Promise<number> {
  const serversPath = path.join(targetDir, mcpServerDir);
  const settingsDir = path.join(targetDir, ".claude");
  const settingsFile = path.join(settingsDir, "settings.json");

  fs.mkdirSync(settingsDir, { recursive: true });

  // Find all .py files in the MCP servers directory
  const mcpServers: Record<
    string,
    { command: string; args: string[]; type: string }
  > = {};

  if (fs.existsSync(serversPath)) {
    // Scan subdirectories for server.py (e.g. mcp_servers/pdb/server.py)
    const dirs = fs.readdirSync(serversPath, { withFileTypes: true })
      .filter((d) => d.isDirectory() && !d.name.startsWith("_"));

    for (const dir of dirs) {
      const serverPy = path.join(serversPath, dir.name, "server.py");
      if (!fs.existsSync(serverPy)) continue;

      const serverKey = `by-${dir.name.replace(/_/g, "-")}`;
      const scriptPath = path.join(mcpServerDir, dir.name, "server.py");

      mcpServers[serverKey] = {
        command: "uv",
        args: ["run", "--script", scriptPath],
        type: "stdio",
      };
    }
  }

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

  // Merge MCP servers into settings
  if (Object.keys(mcpServers).length > 0) {
    const existingMcp =
      (settings["mcpServers"] as Record<string, unknown>) ?? {};
    settings["mcpServers"] = { ...existingMcp, ...mcpServers };
  }

  fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + "\n");

  return Object.keys(mcpServers).length;
}
