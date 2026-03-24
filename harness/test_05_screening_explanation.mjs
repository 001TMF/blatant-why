// Test 5: Screening Explanation
// Expected: should explain ipSAE, ipTM, pLDDT, RMSD, liabilities, etc.
import { chat } from "./stress_test.mjs";

console.log("=== TEST 5: Screening Explanation ===\n");
const r = await chat("Explain the screening pipeline. What metrics do you use and in what order?", 5);

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
const mentionsIpSAE = text.includes("ipsae");
const mentionsIpTM = text.includes("iptm");
const mentionsPLDDT = text.includes("plddt");
const mentionsLiabilities = text.includes("liabilit") || text.includes("deamidation") || text.includes("oxidation");
const mentionsOrder = text.includes("order") || text.includes("first") || text.includes("then") || text.includes("stage") || text.includes("step") || text.includes("pipeline");

let status = "PASS";
const issues = [];
const metricsFound = [mentionsIpSAE, mentionsIpTM, mentionsPLDDT, mentionsLiabilities].filter(Boolean).length;
if (metricsFound < 2) issues.push(`only ${metricsFound}/4 key metrics mentioned (ipSAE, ipTM, pLDDT, liabilities)`);
if (!mentionsOrder) issues.push("does not describe pipeline order/stages");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
console.log(`Metrics coverage: ipSAE=${mentionsIpSAE}, ipTM=${mentionsIpTM}, pLDDT=${mentionsPLDDT}, liabilities=${mentionsLiabilities}`);
