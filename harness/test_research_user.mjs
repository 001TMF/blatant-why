/**
 * Stress test: Simulate a research-heavy user via Claude Code SDK.
 *
 * Tests:
 * 1. Research query (TNF-alpha, PDB + UniProt)
 * 2. SAbDab nanobody lookup
 * 3. /help command
 * 4. /campaign command
 */
import { query } from "@anthropic-ai/claude-code";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cwd = resolve(__dirname, "..");

// Load settings
const settingsPath = resolve(cwd, ".claude/settings.json");
const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));

// Build MCP servers config with resolved paths
const mcpServers = {};
for (const [name, config] of Object.entries(settings.mcpServers || {})) {
  mcpServers[name] = {
    ...config,
    args: (config.args || []).map((a) =>
      a.startsWith("/") ? a : resolve(cwd, a)
    ),
  };
}

console.log(`\nProject dir: ${cwd}`);
console.log(`MCP servers configured: ${Object.keys(mcpServers).join(", ")}\n`);

// Test results collector
const testResults = [];

async function chat(label, prompt, maxTurns = 5, timeout = 120000) {
  const divider = "=".repeat(60);
  console.log(`\n${divider}`);
  console.log(`TEST: ${label}`);
  console.log(`>>> USER: ${prompt}`);
  console.log(divider);

  const testResult = {
    label,
    prompt,
    success: false,
    toolCalls: [],
    mcpServersUsed: new Set(),
    resultText: "",
    errors: [],
    elapsed: 0,
    systemInfo: null,
  };

  const t0 = Date.now();
  const abortController = new AbortController();
  const timer = setTimeout(() => {
    console.log(`  [TIMEOUT] Aborting after ${timeout / 1000}s`);
    abortController.abort();
  }, timeout);

  try {
    const result = query({
      prompt,
      options: {
        cwd,
        maxTurns,
        permissionMode: "bypassPermissions",
        mcpServers,
        abortController,
      },
    });

    for await (const msg of result) {
      if (msg.type === "system" && msg.subtype === "init") {
        testResult.systemInfo = {
          model: msg.model,
          tools: msg.tools?.length || 0,
          mcpServers: msg.mcp_servers || [],
          slashCommands: msg.slash_commands || [],
        };
        const serverStatuses = (msg.mcp_servers || [])
          .map((s) => `${s.name}:${s.status}`)
          .join(", ");
        console.log(`  [INIT] Model: ${msg.model}`);
        console.log(`  [INIT] Tools: ${msg.tools?.length || 0}`);
        console.log(`  [INIT] MCP servers: ${serverStatuses}`);
        console.log(
          `  [INIT] Slash commands: ${(msg.slash_commands || []).join(", ")}`
        );
      } else if (msg.type === "assistant") {
        // Full assistant message — check for tool_use content blocks
        const content = msg.message?.content || [];
        for (const block of content) {
          if (block.type === "tool_use") {
            const toolName = block.name || "unknown";
            testResult.toolCalls.push(toolName);
            // Track which MCP server was used
            const parts = toolName.split("__");
            if (parts.length >= 3) {
              testResult.mcpServersUsed.add(parts[1]);
            }
            console.log(`  [TOOL] ${toolName}`);
          } else if (block.type === "text" && block.text) {
            // Show first 300 chars of each text block
            const preview = block.text.substring(0, 300);
            console.log(`  [TEXT] ${preview}${block.text.length > 300 ? "..." : ""}`);
          }
        }
      } else if (msg.type === "result") {
        const elapsed = Date.now() - t0;
        testResult.elapsed = elapsed;
        testResult.success = !msg.is_error;

        if (msg.subtype === "success") {
          testResult.resultText = msg.result || "";
          const preview = (msg.result || "").substring(0, 500);
          console.log(`\n<<< RESULT (${elapsed / 1000}s, ${msg.num_turns} turns):`);
          console.log(`    ${preview}${(msg.result || "").length > 500 ? "..." : ""}`);
          console.log(`    Cost: $${msg.total_cost_usd?.toFixed(4) || "?"}`);
        } else {
          testResult.errors.push(`Result error: ${msg.subtype}`);
          console.log(`\n<<< ERROR (${msg.subtype}): ${elapsed / 1000}s`);
        }
      }
    }
  } catch (err) {
    const elapsed = Date.now() - t0;
    testResult.elapsed = elapsed;
    testResult.errors.push(err.message || String(err));
    console.log(`\n<<< EXCEPTION (${elapsed / 1000}s): ${err.message || err}`);
  } finally {
    clearTimeout(timer);
  }

  testResults.push(testResult);
  return testResult;
}

// ---- Run tests ----

console.log("PROTEUS TUI STRESS TEST — Research-Heavy User");
console.log("=".repeat(60));

// Test 1: Research query
await chat(
  "TNF-alpha Research (PDB + UniProt)",
  "What do you know about TNF-alpha as a drug target? Search PDB and UniProt.",
  5,
  120000
);

// Test 2: SAbDab nanobody lookup
await chat(
  "TNF-alpha SAbDab Nanobodies",
  "How many known nanobodies exist against TNF-alpha? Check SAbDab.",
  5,
  120000
);

// Test 3: /help command
await chat("/help Command", "/help", 2, 30000);

// Test 4: /campaign command
await chat("/campaign Command", "/campaign", 2, 30000);

// ---- Summary ----
console.log("\n" + "=".repeat(60));
console.log("TEST SUMMARY");
console.log("=".repeat(60));

for (const t of testResults) {
  const status = t.success ? "\x1b[92mPASS\x1b[0m" : "\x1b[91mFAIL\x1b[0m";
  console.log(`\n  ${status} ${t.label}`);
  console.log(`    Elapsed: ${(t.elapsed / 1000).toFixed(1)}s`);
  console.log(`    Tool calls: ${t.toolCalls.length > 0 ? t.toolCalls.join(", ") : "(none)"}`);
  console.log(`    MCP servers used: ${t.mcpServersUsed.size > 0 ? [...t.mcpServersUsed].join(", ") : "(none)"}`);
  if (t.errors.length > 0) {
    for (const e of t.errors) {
      console.log(`    Error: ${e}`);
    }
  }
  if (t.systemInfo) {
    const failedMcp = (t.systemInfo.mcpServers || []).filter(
      (s) => s.status !== "connected"
    );
    if (failedMcp.length > 0) {
      console.log(
        `    MCP connection failures: ${failedMcp.map((s) => `${s.name}:${s.status}`).join(", ")}`
      );
    }
  }
}

console.log("\n" + "=".repeat(60));
console.log("DONE");
console.log("=".repeat(60));
