import { execSync } from "node:child_process";
import { readdirSync, existsSync } from "node:fs";
import { resolve } from "node:path";

export function verifyMcpServers(mcpDir: string): { passed: number; failed: string[] } {
  const failed: string[] = [];
  let passed = 0;

  // Find all server directories (skip _shared and other underscore-prefixed dirs)
  const dirs = readdirSync(mcpDir, { withFileTypes: true })
    .filter(d => d.isDirectory() && !d.name.startsWith("_"));

  for (const dir of dirs) {
    const serverPy = resolve(mcpDir, dir.name, "server.py");
    if (!existsSync(serverPy)) {
      continue; // Skip directories without server.py
    }
    try {
      // Check if uv can resolve deps by doing a syntax check
      execSync(`uv run --script "${serverPy}" --help`, {
        timeout: 30000,
        encoding: "utf-8",
        stdio: "pipe",
      });
      passed++;
    } catch {
      failed.push(dir.name);
    }
  }

  return { passed, failed };
}
