// Test 4: Campaign Cost Estimation
// Expected: should estimate compute + lab costs for a VHH nanobody campaign
import { chat } from "./stress_test.mjs";

console.log("=== TEST 4: Campaign Cost Estimation ===\n");
const r = await chat("If I want to design 5000 VHH nanobodies against TNF-alpha using 2 scaffolds on Tamarind Bio, how much would it cost?", 5);

console.log("Prompt:", r.prompt);
console.log("Elapsed:", r.elapsedSec, "sec");
console.log("Turns:", r.numTurns);
console.log("Cost: $" + r.costUSD);
console.log("Tools called:", JSON.stringify(r.toolCalls.map(t => t.tool), null, 2));
console.log("Errors:", r.errors.length ? r.errors : "none");
console.log("\n--- Response (first 2000 chars) ---");
console.log(r.resultText);
console.log("\n--- Assessment ---");

const tools = r.toolCalls.map(t => t.tool);
const hasCostTool = tools.some(t => t.includes("cost") || t.includes("campaign") || t.includes("tamarind") || t.includes("adaptyv"));
const mentionsCost = r.resultText.includes("$") || r.resultText.toLowerCase().includes("cost") || r.resultText.toLowerCase().includes("price");
const mentionsTNF = r.resultText.toLowerCase().includes("tnf");
const mentionsVHH = r.resultText.toLowerCase().includes("vhh") || r.resultText.toLowerCase().includes("nanobod");

let status = "PASS";
const issues = [];
if (!mentionsCost) issues.push("response does not discuss costs");
if (!mentionsTNF) issues.push("response does not mention TNF-alpha");
if (!mentionsVHH) issues.push("response does not mention VHH/nanobody");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
