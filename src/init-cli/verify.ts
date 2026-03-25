import { execSync } from "node:child_process";

export function verifyMcpServers(): { passed: number; failed: string[] } {
  const failed: string[] = [];
  let passed = 0;

  try {
    // Use `claude mcp list` to verify servers are registered in .mcp.json
    const output = execSync("claude mcp list", {
      timeout: 15000,
      encoding: "utf-8",
      stdio: "pipe",
    });

    // Count BY servers that appear in the listing
    const lines = output.split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("by-")) {
        passed++;
      }
    }

    if (passed === 0) {
      // No BY servers found — report as a general failure
      failed.push("(no by-* servers found in claude mcp list)");
    }
  } catch {
    // claude CLI not available or mcp list failed
    failed.push("(claude mcp list failed — is Claude Code CLI installed?)");
  }

  return { passed, failed };
}
