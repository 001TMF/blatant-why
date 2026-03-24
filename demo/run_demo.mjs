#!/usr/bin/env node

/**
 * BY Demo Runner — VHH Nanobody Design Against RBX1
 *
 * Runs the full BY campaign pipeline headlessly via the Claude Agent SDK,
 * captures all output and tool calls, and writes them to demo/output/
 * for post-production into a 45-second video.
 *
 * Usage:
 *   node demo/run_demo.mjs
 *
 * Requires:
 *   - @anthropic-ai/claude-agent-sdk
 *   - .env with TAMARIND_API_KEY
 *   - MCP servers in .claude/settings.json
 */

import { query } from "@anthropic-ai/claude-agent-sdk";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

// ─── Paths ──────────────────────────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = resolve(__dirname, "..");
const OUTPUT_DIR = resolve(__dirname, "output");
const TRANSCRIPT_PATH = resolve(OUTPUT_DIR, "demo_transcript.md");
const TOOL_CALLS_PATH = resolve(OUTPUT_DIR, "tool_calls.json");

// ─── Load .env ──────────────────────────────────────────────────────────────

function loadEnv() {
  const envPath = resolve(PROJECT_ROOT, ".env");
  if (!existsSync(envPath)) {
    console.error("ERROR: .env file not found at", envPath);
    console.error("Copy .env.example to .env and set TAMARIND_API_KEY");
    process.exit(1);
  }

  const envContent = readFileSync(envPath, "utf-8");
  for (const line of envContent.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIndex = trimmed.indexOf("=");
    if (eqIndex === -1) continue;
    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1).trim();
    if (key && !process.env[key]) {
      process.env[key] = value;
    }
  }
}

// ─── Load MCP server config ────────────────────────────────────────────────

function loadMcpServers() {
  const settingsPath = resolve(PROJECT_ROOT, ".claude", "settings.json");
  if (!existsSync(settingsPath)) {
    console.error("ERROR: .claude/settings.json not found at", settingsPath);
    process.exit(1);
  }

  const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
  if (!settings.mcpServers) {
    console.error("ERROR: No mcpServers found in .claude/settings.json");
    process.exit(1);
  }

  // Resolve relative paths in MCP server args to absolute paths
  const servers = {};
  for (const [name, config] of Object.entries(settings.mcpServers)) {
    servers[name] = {
      ...config,
      args: (config.args || []).map((arg) => {
        // If the arg looks like a relative path to a .py file, resolve it
        if (arg.endsWith(".py") && !arg.startsWith("/")) {
          return resolve(PROJECT_ROOT, arg);
        }
        return arg;
      }),
    };
  }

  return servers;
}

// ─── Phase timing ──────────────────────────────────────────────────────────

const phaseTimings = [];
let currentPhase = null;
let phaseStart = null;

function startPhase(name) {
  if (currentPhase) {
    endPhase();
  }
  currentPhase = name;
  phaseStart = Date.now();
  console.log(`\n--- Phase: ${name} ---`);
}

function endPhase() {
  if (currentPhase && phaseStart) {
    const elapsed = ((Date.now() - phaseStart) / 1000).toFixed(1);
    phaseTimings.push({ phase: currentPhase, seconds: parseFloat(elapsed) });
    console.log(`    -> ${currentPhase}: ${elapsed}s`);
  }
  currentPhase = null;
  phaseStart = null;
}

// ─── Classify tool calls into phases ───────────────────────────────────────

function classifyPhase(toolName) {
  if (!toolName) return null;
  const name = toolName.toLowerCase();
  if (name.includes("uniprot") || name.includes("pdb") || name.includes("sabdab") || name.includes("research")) {
    return "research";
  }
  if (name.includes("campaign") && (name.includes("plan") || name.includes("create") || name.includes("cost"))) {
    return "planning";
  }
  if (name.includes("tamarind") || name.includes("levitate") || name.includes("design") || name.includes("boltzgen")) {
    return "design";
  }
  if (name.includes("screen") || name.includes("score") || name.includes("rank") || name.includes("filter")) {
    return "screening";
  }
  return null;
}

// ─── Main ──────────────────────────────────────────────────────────────────

async function main() {
  console.log("BY Demo Runner — VHH Nanobody Design Against RBX1");
  console.log("=".repeat(55));

  // Load environment and config
  loadEnv();
  const mcpServers = loadMcpServers();
  console.log(`Loaded ${Object.keys(mcpServers).length} MCP servers:`, Object.keys(mcpServers).join(", "));

  // Collectors
  const transcriptLines = [];
  const toolCalls = [];
  const runStart = Date.now();

  transcriptLines.push("# BY Demo Transcript — VHH Nanobody Design Against RBX1");
  transcriptLines.push("");
  transcriptLines.push(`Run started: ${new Date().toISOString()}`);
  transcriptLines.push("");

  // The prompt
  const prompt = [
    "Design VHH nanobodies against RBX1.",
    "Use standard campaign tier.",
    "Present results as a ranked table with ipSAE, ipTM, pLDDT, and liability columns.",
    "Include a diversity analysis of the top candidates.",
  ].join(" ");

  transcriptLines.push("## Prompt");
  transcriptLines.push("");
  transcriptLines.push(`> ${prompt}`);
  transcriptLines.push("");

  console.log(`\nPrompt: ${prompt}`);
  console.log(`\nStarting campaign (maxTurns=30, timeout=600s)...\n`);

  startPhase("research");

  let lastDetectedPhase = "research";

  try {
    // Run the query via Claude Agent SDK
    const abortController = createTimeoutController(600_000);
    const cwd = PROJECT_ROOT;
    const result = await query({
      prompt,
      options: {
        cwd,
        maxTurns: 30,
        permissionMode: "bypassPermissions",
        mcpServers,
        abortController,
        systemPrompt: { type: "preset", preset: "claude_code" },
        settingSources: ["user", "project", "local"],
        allowedTools: [
          "mcp__pdb__*",
          "mcp__uniprot__*",
          "mcp__sabdab__*",
          "mcp__by-screening__*",
          "mcp__tamarind__*",
          "mcp__levitate__*",
          "mcp__by-campaign__*",
          "mcp__by-research__*",
          "mcp__by-local__*",
          "mcp__by-knowledge__*",
        ],
      },
    });

    endPhase();

    // Process the result messages
    const messages = Array.isArray(result) ? result : [result];

    transcriptLines.push("## Conversation");
    transcriptLines.push("");

    for (const message of messages) {
      // Handle text content
      if (typeof message === "string") {
        transcriptLines.push(message);
        transcriptLines.push("");
        continue;
      }

      // Handle structured messages
      if (message.role) {
        transcriptLines.push(`### ${message.role === "assistant" ? "BY Agent" : "User"}`);
        transcriptLines.push("");
      }

      // Extract content blocks
      const contentBlocks = Array.isArray(message.content) ? message.content : [message.content];

      for (const block of contentBlocks) {
        if (!block) continue;

        // Text block
        if (typeof block === "string") {
          transcriptLines.push(block);
          transcriptLines.push("");
        } else if (block.type === "text") {
          transcriptLines.push(block.text);
          transcriptLines.push("");
        }

        // Tool use block
        if (block.type === "tool_use") {
          const toolCall = {
            id: block.id,
            name: block.name,
            input: block.input,
            timestamp: new Date().toISOString(),
          };
          toolCalls.push(toolCall);

          // Detect phase transitions
          const detectedPhase = classifyPhase(block.name);
          if (detectedPhase && detectedPhase !== lastDetectedPhase) {
            startPhase(detectedPhase);
            lastDetectedPhase = detectedPhase;
          }

          transcriptLines.push(`**Tool Call**: \`${block.name}\``);
          transcriptLines.push("```json");
          transcriptLines.push(JSON.stringify(block.input, null, 2));
          transcriptLines.push("```");
          transcriptLines.push("");
        }

        // Tool result block
        if (block.type === "tool_result") {
          const resultText =
            typeof block.content === "string"
              ? block.content
              : JSON.stringify(block.content, null, 2);

          // Attach result to the last tool call
          if (toolCalls.length > 0) {
            toolCalls[toolCalls.length - 1].result = block.content;
          }

          transcriptLines.push(`**Tool Result** (truncated):`);
          transcriptLines.push("```");
          transcriptLines.push(resultText.slice(0, 2000) + (resultText.length > 2000 ? "\n..." : ""));
          transcriptLines.push("```");
          transcriptLines.push("");
        }
      }
    }
  } catch (err) {
    endPhase();
    console.error("\nERROR during campaign:", err.message);
    transcriptLines.push("## Error");
    transcriptLines.push("");
    transcriptLines.push(`Campaign failed: ${err.message}`);
    transcriptLines.push("");
  }

  // ─── Timing summary ───────────────────────────────────────────────────

  const totalSeconds = ((Date.now() - runStart) / 1000).toFixed(1);

  transcriptLines.push("## Timing");
  transcriptLines.push("");
  transcriptLines.push("| Phase | Duration |");
  transcriptLines.push("|-------|----------|");
  for (const { phase, seconds } of phaseTimings) {
    transcriptLines.push(`| ${phase} | ${seconds}s |`);
  }
  transcriptLines.push(`| **Total** | **${totalSeconds}s** |`);
  transcriptLines.push("");

  transcriptLines.push(`Run completed: ${new Date().toISOString()}`);

  // ─── Write output files ──────────────────────────────────────────────

  writeFileSync(TRANSCRIPT_PATH, transcriptLines.join("\n"), "utf-8");
  console.log(`\nTranscript written to: ${TRANSCRIPT_PATH}`);

  const toolCallsOutput = {
    meta: {
      prompt,
      startTime: new Date(runStart).toISOString(),
      endTime: new Date().toISOString(),
      totalSeconds: parseFloat(totalSeconds),
      totalToolCalls: toolCalls.length,
      phaseTimings,
    },
    toolCalls,
  };

  writeFileSync(TOOL_CALLS_PATH, JSON.stringify(toolCallsOutput, null, 2), "utf-8");
  console.log(`Tool calls written to: ${TOOL_CALLS_PATH}`);

  // ─── Summary ─────────────────────────────────────────────────────────

  console.log("\n" + "=".repeat(55));
  console.log("Demo run complete!");
  console.log(`  Total time:       ${totalSeconds}s`);
  console.log(`  Tool calls:       ${toolCalls.length}`);
  console.log(`  Phase breakdown:`);
  for (const { phase, seconds } of phaseTimings) {
    console.log(`    ${phase.padEnd(15)} ${seconds}s`);
  }
  console.log(`\nOutput files:`);
  console.log(`  ${TRANSCRIPT_PATH}`);
  console.log(`  ${TOOL_CALLS_PATH}`);
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function createTimeoutController(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => {
    console.error(`\nTimeout: campaign exceeded ${ms / 1000}s limit`);
    controller.abort();
  }, ms);

  // Clean up timer if the signal is aborted for other reasons
  controller.signal.addEventListener("abort", () => clearTimeout(timer), { once: true });

  return controller;
}

// ─── Run ───────────────────────────────────────────────────────────────────

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
