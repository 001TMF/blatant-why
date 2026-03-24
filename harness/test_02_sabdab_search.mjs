// Test 2: SAbDab Known Binders
// Expected: should find anti-PD-L1 antibodies using sabdab or research tools
import { chat } from "./stress_test.mjs";

console.log("=== TEST 2: SAbDab Known Binders ===\n");
const r = await chat("Search SAbDab for known antibodies against PD-L1", 8);

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
const hasSAbDab = tools.some(t => t.includes("sabdab") || t.includes("known_binders") || t.includes("analyze_known"));
const mentionsPDL1 = r.resultText.toLowerCase().includes("pd-l1") || r.resultText.toLowerCase().includes("pdl1") || r.resultText.toLowerCase().includes("pd-l1");
const mentionsAntibody = r.resultText.toLowerCase().includes("antibod") || r.resultText.toLowerCase().includes("atezolizumab") || r.resultText.toLowerCase().includes("durvalumab") || r.resultText.toLowerCase().includes("avelumab");

let status = "PASS";
const issues = [];
if (!hasSAbDab) issues.push("did NOT call sabdab or research tool for known binders");
if (!mentionsPDL1) issues.push("response does not mention PD-L1");
if (!mentionsAntibody) issues.push("response does not mention any known antibodies");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
