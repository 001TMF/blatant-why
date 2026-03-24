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
      // Parse the Python file to verify syntax without running the server.
      // Running with --help starts the stdio transport and hangs until timeout.
      execSync(`python3 -c "import ast; ast.parse(open('${serverPy}').read())"`, {
        timeout: 10000,
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
