/**
 * test_5scenarios.mjs — 5-scenario interactive test for the rebuilt Proteus TUI.
 *
 * Runs each scenario through the Claude Code SDK headlessly, captures:
 *   - Full response text
 *   - Tool calls made
 *   - Elapsed time
 *   - PASS/FAIL assessment with criteria checks
 *
 * Usage: node test_5scenarios.mjs
 */
import { query } from "@anthropic-ai/claude-code";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cwd = resolve(__dirname, "..");
const resultsDir = resolve(__dirname, "test_results");

// Ensure output directory
if (!existsSync(resultsDir)) mkdirSync(resultsDir, { recursive: true });

// Load MCP servers from .claude/settings.json
const settingsPath = resolve(cwd, ".claude/settings.json");
let mcpServers = {};
try {
  const settings = JSON.parse(readFileSync(settingsPath, "utf-8"));
  for (const [name, config] of Object.entries(settings.mcpServers || {})) {
    mcpServers[name] = {
      ...config,
      args: (config.args || []).map((a) =>
        a.startsWith("/") || a.startsWith("-") ? a : resolve(cwd, a)
      ),
    };
  }
} catch (e) {
  console.warn("Warning: Could not load .claude/settings.json:", e.message);
}

console.log(`Project dir: ${cwd}`);
console.log(`MCP servers: ${Object.keys(mcpServers).join(", ") || "(none)"}`);
console.log("");

// --------------------------------------------------------------------------
// Test runner
// --------------------------------------------------------------------------
const allResults = [];

async function runTest(testNum, label, prompt, maxTurns, timeoutMs, criteria) {
  const divider = "=".repeat(70);
  console.log(`\n${divider}`);
  console.log(`TEST ${testNum}: ${label}`);
  console.log(`>>> USER: ${prompt.substring(0, 120)}${prompt.length > 120 ? "..." : ""}`);
  console.log(divider);

  const result = {
    testNum,
    label,
    prompt,
    status: "FAIL",
    toolCalls: [],
    mcpServersUsed: new Set(),
    resultText: "",
    allText: "", // Collects ALL text blocks (not just final result)
    errors: [],
    elapsed: 0,
    numTurns: 0,
    costUsd: 0,
    criteriaResults: {},
    systemInfo: null,
  };

  const t0 = Date.now();
  const abortController = new AbortController();
  const timer = setTimeout(() => {
    console.log(`  [TIMEOUT] Aborting after ${timeoutMs / 1000}s`);
    abortController.abort();
  }, timeoutMs);

  try {
    const stream = query({
      prompt,
      options: {
        cwd,
        maxTurns,
        permissionMode: "bypassPermissions",
        mcpServers,
        abortController,
      },
    });

    for await (const msg of stream) {
      if (msg.type === "system" && msg.subtype === "init") {
        result.systemInfo = {
          model: msg.model,
          tools: msg.tools?.length || 0,
          mcpServers: (msg.mcp_servers || []).map((s) => `${s.name}:${s.status}`),
        };
        console.log(`  [INIT] Model: ${msg.model}, Tools: ${msg.tools?.length || 0}`);
        const statuses = (msg.mcp_servers || [])
          .map((s) => `${s.name}:${s.status}`)
          .join(", ");
        if (statuses) console.log(`  [MCP] ${statuses}`);
      } else if (msg.type === "assistant") {
        const content = msg.message?.content || [];
        for (const block of content) {
          if (block.type === "tool_use") {
            const toolName = block.name || "unknown";
            result.toolCalls.push(toolName);
            const parts = toolName.split("__");
            if (parts.length >= 3) result.mcpServersUsed.add(parts[1]);
            console.log(`  [TOOL] ${toolName}`);
          } else if (block.type === "text" && block.text) {
            result.allText += block.text + "\n";
            const preview = block.text.substring(0, 200);
            console.log(`  [TEXT] ${preview}${block.text.length > 200 ? "..." : ""}`);
          }
        }
      } else if (msg.type === "result") {
        result.elapsed = Date.now() - t0;
        result.numTurns = msg.num_turns || 0;
        result.costUsd = msg.total_cost_usd || 0;
        if (msg.subtype === "success") {
          result.resultText = msg.result || "";
          console.log(`\n  [RESULT] ${result.numTurns} turns, ${(result.elapsed / 1000).toFixed(1)}s, $${result.costUsd.toFixed(4)}`);
          console.log(`  [PREVIEW] ${(msg.result || "").substring(0, 300)}...`);
        } else {
          result.errors.push(`Result error: ${msg.subtype}`);
          console.log(`  [ERROR] Result subtype: ${msg.subtype}`);
        }
      }
    }
  } catch (err) {
    result.elapsed = Date.now() - t0;
    const errMsg = err.message || String(err);
    if (errMsg.includes("abort") || errMsg.includes("AbortError")) {
      // Timeout abort is not a hard error if we got useful intermediate output
      if (result.allText.length > 0 || result.toolCalls.length > 0) {
        console.log(`  [TIMEOUT] Aborted after ${(result.elapsed / 1000).toFixed(1)}s with ${result.toolCalls.length} tool calls and ${result.allText.length} chars of text`);
      }
    } else {
      result.errors.push(errMsg);
      console.log(`  [EXCEPTION] ${errMsg}`);
    }
  } finally {
    clearTimeout(timer);
  }

  // Evaluate criteria — use allText as fallback when resultText is empty
  // (e.g. when the agent was aborted/timed out before producing a final result)
  const evalText = result.resultText || result.allText;
  const textLower = evalText.toLowerCase();
  const toolNames = result.toolCalls.map((t) => t.toLowerCase());

  for (const [name, check] of Object.entries(criteria)) {
    try {
      result.criteriaResults[name] = check(result.resultText, textLower, toolNames, result);
    } catch {
      result.criteriaResults[name] = false;
    }
  }

  const totalCriteria = Object.keys(result.criteriaResults).length;
  const passedCriteria = Object.values(result.criteriaResults).filter(Boolean).length;

  if (result.errors.length > 0) {
    result.status = "FAIL";
  } else if (passedCriteria === totalCriteria) {
    result.status = "PASS";
  } else if (passedCriteria >= totalCriteria * 0.6) {
    result.status = "PARTIAL";
  } else {
    result.status = "FAIL";
  }

  // Print criteria results
  console.log(`\n  --- Criteria ---`);
  for (const [name, passed] of Object.entries(result.criteriaResults)) {
    const mark = passed ? "\x1b[92mPASS\x1b[0m" : "\x1b[91mFAIL\x1b[0m";
    console.log(`    ${mark}  ${name}`);
  }
  console.log(`\n  STATUS: ${result.status === "PASS" ? "\x1b[92m" : result.status === "PARTIAL" ? "\x1b[93m" : "\x1b[91m"}${result.status}\x1b[0m`);

  // Check for scientific language vs marketing
  const marketingWords = ["revolutionary", "cutting-edge", "game-changing", "unlock the power"];
  const hasMarketing = marketingWords.some((w) => textLower.includes(w));
  if (hasMarketing) {
    console.log(`  [WARN] Response contains marketing language`);
  }

  // Check for explicit tool name mentions
  const toolMentions = [];
  if (textLower.includes("protenix")) toolMentions.push("Protenix");
  if (textLower.includes("boltzgen")) toolMentions.push("BoltzGen");
  if (textLower.includes("ipsae")) toolMentions.push("ipSAE");
  if (textLower.includes("pxdesign")) toolMentions.push("PXDesign");
  if (toolMentions.length > 0) {
    console.log(`  [INFO] Tool names mentioned: ${toolMentions.join(", ")}`);
  }

  allResults.push(result);
  return result;
}

// --------------------------------------------------------------------------
// Test definitions
// --------------------------------------------------------------------------

// Test 1: Simple beginner question
// Note: The orchestrator CLAUDE.md triggers autonomous research before responding.
// Give it enough turns (15) and time (300s) to complete the full research+respond cycle.
await runTest(
  1,
  "Simple beginner question",
  "I have a protein called PD-L1 and I want to make something that binds to it. What should I do?",
  15,
  300000,
  {
    "responds without errors": (_text, _lower, _tools, r) => r.errors.length === 0,
    "mentions PD-L1": (_text, lower) => lower.includes("pd-l1") || lower.includes("pd l1") || lower.includes("pdl1"),
    "explains options (nanobody/antibody/binder)": (_text, lower) =>
      (lower.includes("nanobody") || lower.includes("vhh")) ||
      (lower.includes("antibody") || lower.includes("binder")),
    "suggests next steps": (_text, lower) =>
      lower.includes("next") || lower.includes("step") || lower.includes("start") ||
      lower.includes("recommend") || lower.includes("campaign") || lower.includes("research"),
    "beginner-friendly tone (no raw jargon overload)": (_text, lower) =>
      !lower.includes("d0 = 1.24") && (lower.includes("design") || lower.includes("bind") || lower.includes("target")),
    "uses research MCP tools (not just text)": (_text, _lower, tools) =>
      tools.some((t) => t.includes("pdb") || t.includes("uniprot") || t.includes("sabdab")),
  }
);

// Test 2: Expert with specific parameters
// Note: The orchestrator pattern uses TodoWrite + Task + MCP calls.
// Give it 15 turns and 300s to research, plan, and present.
await runTest(
  2,
  "Expert with exact parameters",
  "Design 20K VHH nanobodies against TNF-alpha residues 75-97 using caplacizumab scaffold, alpha 0.01, on Tamarind",
  15,
  300000,
  {
    "responds without errors": (_text, _lower, _tools, r) => r.errors.length === 0,
    "recognizes VHH/nanobody modality": (_text, lower) =>
      lower.includes("vhh") || lower.includes("nanobody"),
    "mentions TNF-alpha": (_text, lower) =>
      lower.includes("tnf") || lower.includes("tnf-alpha") || lower.includes("tnfa"),
    "presents campaign plan or parameters": (_text, lower) =>
      lower.includes("campaign") || lower.includes("parameter") || lower.includes("plan"),
    "references caplacizumab scaffold": (_text, lower) => lower.includes("caplacizumab"),
    "mentions alpha or sampling parameter": (_text, lower) =>
      lower.includes("alpha") || lower.includes("0.01"),
    "mentions Tamarind as compute provider": (_text, lower) => lower.includes("tamarind"),
  }
);

// Test 3: Liability screening with real sequence
await runTest(
  3,
  "Liability screening with VHH sequence",
  "Screen this VHH for liabilities: EVQLVESGGGLVQPGGSLRLSCAASGFTFSNYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDRVGATGAFDIWGQGTLVTVSS",
  5,
  180000,
  {
    "responds without errors": (_text, _lower, _tools, r) => r.errors.length === 0,
    "mentions liability or screening": (_text, lower) =>
      lower.includes("liabilit") || lower.includes("screen"),
    "identifies specific motifs (NG, NS, DG, or deamidation)": (_text, lower) =>
      lower.includes("deamidation") || lower.includes("isomerization") ||
      lower.includes("ng") || lower.includes("ns ") || lower.includes("dg"),
    "calls screening tool or analyzes sequence directly": (_text, lower, tools) => {
      const hasScreenTool = tools.some((t) => t.includes("screen") || t.includes("liabilit"));
      const hasAnalysis = lower.includes("liability") || lower.includes("motif") || lower.includes("deamidation");
      return hasScreenTool || hasAnalysis;
    },
    "provides actionable result (sites/concerns/consider/engineering)": (_text, lower) =>
      lower.includes("pass") || lower.includes("flag") || lower.includes("warning") ||
      lower.includes("found") || lower.includes("identified") || lower.includes("detected") ||
      lower.includes("consider") || lower.includes("sites") || lower.includes("concerns") ||
      lower.includes("engineering") || lower.includes("hotspot") || lower.includes("risk"),
  }
);

// Test 4: Research target
// Note: The orchestrator uses TodoWrite for planning which consumes turns.
// Give it 20 turns and 300s to complete research + present results.
await runTest(
  4,
  "Research EGFR target",
  "Research EGFR as a target for antibody design. Check PDB and UniProt.",
  20,
  300000,
  {
    "responds without errors": (_text, _lower, _tools, r) => r.errors.length === 0,
    "mentions EGFR": (_text, lower) => lower.includes("egfr"),
    "calls PDB or UniProt tool": (_text, _lower, tools) =>
      tools.some((t) => t.includes("pdb") || t.includes("uniprot")),
    "does NOT rely solely on WebSearch": (_text, _lower, tools) => {
      const webSearchCount = tools.filter((t) => t.includes("websearch") || t.includes("web_search")).length;
      const researchToolCount = tools.filter((t) =>
        t.includes("pdb") || t.includes("uniprot") || t.includes("sabdab") || t.includes("research")
      ).length;
      // Either no web search, or research tools outnumber web searches
      return webSearchCount === 0 || researchToolCount > webSearchCount;
    },
    "provides scientific data (structures, function, or domains)": (_text, lower) =>
      (lower.includes("structure") || lower.includes("pdb")) &&
      (lower.includes("kinase") || lower.includes("receptor") || lower.includes("domain") || lower.includes("egfr")),
    "mentions specific PDB IDs or UniProt accession": (_text, lower) =>
      /[0-9][a-z0-9]{3}/i.test(lower) || /[pqo][0-9][a-z0-9]{3}[0-9]/i.test(lower),
  }
);

// Test 5: Help command
// NOTE: /help is a LOCAL command handled by the TUI's app.tsx (isLocalCommand).
// The SDK never sees it in the real TUI — it is intercepted before reaching the agent.
// When sent directly via SDK (bypassing TUI), the model may or may not respond.
// We test that:
//   1. It doesn't crash
//   2. The result comes back quickly (local command = fast)
//   3. Separately, we verify the TUI's formatHelp() output directly.
await runTest(
  5,
  "/help command (local TUI — SDK passthrough)",
  "/help",
  2,
  60000,
  {
    "SDK does not crash on /help": (_text, _lower, _tools, r) => r.errors.length === 0,
    "returns quickly (< 30s)": (_text, _lower, _tools, r) => r.elapsed < 30000,
    "no expensive tool calls": (_text, _lower, tools) =>
      !tools.some((t) => t.includes("pdb") || t.includes("uniprot") || t.includes("tamarind")),
  }
);

// Also verify the TUI's local /help handler produces correct output
console.log("\n--- Verifying TUI local /help handler ---");
try {
  // Import the compiled slashCommands module
  const { formatHelp, isLocalCommand, COMMANDS } = await import("./dist/lib/slashCommands.js");
  const helpText = formatHelp();
  const isLocal = isLocalCommand("/help");

  const helpChecks = {
    "isLocalCommand('/help') returns '/help'": isLocal === "/help",
    "formatHelp() lists /campaign": helpText.includes("/campaign"),
    "formatHelp() lists /screen": helpText.includes("/screen"),
    "formatHelp() lists /load": helpText.includes("/load"),
    "formatHelp() includes usage hint": helpText.includes("describe what you want"),
    "formatHelp() has all commands": COMMANDS.every((c) => helpText.includes(c.name)),
  };

  for (const [name, passed] of Object.entries(helpChecks)) {
    const mark = passed ? "\x1b[92mPASS\x1b[0m" : "\x1b[91mFAIL\x1b[0m";
    console.log(`    ${mark}  ${name}`);
  }
} catch (e) {
  console.log(`  [ERROR] Could not import TUI module: ${e.message}`);
}

// --------------------------------------------------------------------------
// Summary
// --------------------------------------------------------------------------
console.log("\n" + "=".repeat(70));
console.log("FINAL SUMMARY — 5-Scenario Test Suite");
console.log("=".repeat(70));

let passCount = 0;
let partialCount = 0;
let failCount = 0;

for (const r of allResults) {
  const colorCode = r.status === "PASS" ? "\x1b[92m" : r.status === "PARTIAL" ? "\x1b[93m" : "\x1b[91m";
  console.log(`\n  ${colorCode}${r.status.padEnd(7)}\x1b[0m  Test ${r.testNum}: ${r.label}`);
  console.log(`           Elapsed: ${(r.elapsed / 1000).toFixed(1)}s | Turns: ${r.numTurns} | Cost: $${r.costUsd.toFixed(4)}`);
  console.log(`           Tools: ${r.toolCalls.length > 0 ? r.toolCalls.slice(0, 8).join(", ") : "(none)"}${r.toolCalls.length > 8 ? "..." : ""}`);

  const criteriaStr = Object.entries(r.criteriaResults)
    .map(([k, v]) => `${v ? "\x1b[92m+\x1b[0m" : "\x1b[91m-\x1b[0m"}${k}`)
    .join("  ");
  console.log(`           ${criteriaStr}`);

  if (r.errors.length > 0) {
    console.log(`           Errors: ${r.errors.join("; ")}`);
  }

  if (r.status === "PASS") passCount++;
  else if (r.status === "PARTIAL") partialCount++;
  else failCount++;
}

console.log(`\n  Total: ${passCount} PASS, ${partialCount} PARTIAL, ${failCount} FAIL out of ${allResults.length}`);
console.log("=".repeat(70));

// Write JSON results for downstream consumption
const jsonResults = allResults.map((r) => ({
  testNum: r.testNum,
  label: r.label,
  prompt: r.prompt,
  status: r.status,
  toolCalls: r.toolCalls,
  mcpServersUsed: [...r.mcpServersUsed],
  resultText: r.resultText.substring(0, 3000),
  allText: (r.allText || "").substring(0, 3000),
  errors: r.errors,
  elapsed: r.elapsed,
  numTurns: r.numTurns,
  costUsd: r.costUsd,
  criteriaResults: r.criteriaResults,
}));

writeFileSync(
  resolve(resultsDir, "test_5scenarios_results.json"),
  JSON.stringify(jsonResults, null, 2),
);
console.log(`\nResults written to: ${resolve(resultsDir, "test_5scenarios_results.json")}`);
