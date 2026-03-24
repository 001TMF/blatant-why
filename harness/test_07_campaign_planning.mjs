// Test 7: Campaign Planning
// Expected: should present a structured campaign plan with cost estimate and screening gates
import { chat } from "./stress_test.mjs";

console.log("=== TEST 7: Campaign Planning ===\n");
const r = await chat("Plan a VHH nanobody campaign against SARS-CoV-2 RBD. Show me the full plan with cost estimate and screening gates.", 15);

console.log("Prompt:", r.prompt);
console.log("Elapsed:", r.elapsedSec, "sec");
console.log("Turns:", r.numTurns);
console.log("Cost: $" + r.costUSD);
console.log("Tools called:", JSON.stringify(r.toolCalls.map(t => t.tool), null, 2));
console.log("Errors:", r.errors.length ? r.errors : "none");
console.log("\n--- Response (first 2000 chars) ---");
console.log(r.resultText);
console.log("\n--- Assessment ---");

const text = r.resultText.toLowerCase();
const tools = r.toolCalls.map(t => t.tool);
const hasResearch = tools.some(t => t.includes("pdb") || t.includes("uniprot") || t.includes("research") || t.includes("sabdab"));
const mentionsSARS = text.includes("sars") || text.includes("rbd") || text.includes("covid") || text.includes("spike");
const mentionsVHH = text.includes("vhh") || text.includes("nanobod") || text.includes("caplacizumab");
const mentionsCost = text.includes("$") || text.includes("cost") || text.includes("estimate");
const mentionsScreening = text.includes("screen") || text.includes("gate") || text.includes("filter") || text.includes("ipsae") || text.includes("iptm");
const mentionsPlan = text.includes("plan") || text.includes("phase") || text.includes("stage") || text.includes("step") || text.includes("round");

let status = "PASS";
const issues = [];
if (!mentionsSARS) issues.push("response does not mention SARS/RBD");
if (!mentionsVHH) issues.push("response does not mention VHH/nanobody/scaffolds");
if (!mentionsCost) issues.push("response does not include cost estimate");
if (!mentionsScreening) issues.push("response does not describe screening gates");
if (!mentionsPlan) issues.push("response does not present structured plan");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));

const critical = [!mentionsPlan, !mentionsScreening, !mentionsCost].filter(Boolean).length;
if (critical >= 2) status = "FAIL";
else if (issues.length) status = "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
console.log(`Research tools used: ${hasResearch}`);
