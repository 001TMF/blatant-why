// Shared stress test harness — each test function simulates a user session
import { query } from "@anthropic-ai/claude-code";
import { readFileSync } from "fs";
import { resolve } from "path";

const cwd = resolve(import.meta.dirname, "..");
const settings = JSON.parse(readFileSync(resolve(cwd, ".claude/settings.json"), "utf-8"));
const mcpServers = {};
for (const [name, config] of Object.entries(settings.mcpServers || {})) {
  mcpServers[name] = { ...config, args: (config.args || []).map(a => a.startsWith("/") ? a : resolve(cwd, a)) };
}

export async function chat(prompt, maxTurns = 10) {
  const startTime = Date.now();
  let resultText = "";
  let toolCalls = [];
  let errors = [];
  let numTurns = 0;
  let costUSD = 0;

  try {
    const result = await query({
      prompt,
      options: { cwd, maxTurns, permissionMode: "bypassPermissions", mcpServers },
    });
    for await (const msg of result) {
      if (msg.type === "assistant" && msg.message && msg.message.content) {
        for (const block of msg.message.content) {
          if (block.type === "tool_use") {
            toolCalls.push({ tool: block.name, inputKeys: Object.keys(block.input || {}) });
          }
        }
      }
      if (msg.type === "result") {
        resultText = msg.result || "";
        numTurns = msg.num_turns || 0;
        costUSD = msg.total_cost_usd || 0;
      }
    }
  } catch (e) {
    errors.push(e.message);
  }

  return {
    prompt,
    resultText: resultText.substring(0, 2000),
    toolCalls,
    numTurns,
    costUSD: costUSD.toFixed(4),
    elapsed: Date.now() - startTime,
    elapsedSec: ((Date.now() - startTime) / 1000).toFixed(1),
    errors,
  };
}
