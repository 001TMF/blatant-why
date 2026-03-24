// Test 9: Structure Prediction Discussion
// Expected: should explain 20-seed minimum for antibodies, multi-seed workflow
import { chat } from "./stress_test.mjs";

console.log("=== TEST 9: Structure Prediction Discussion ===\n");
const r = await chat("I have a PDB file of my target. How do I validate my designs using Protenix? How many seeds should I use?", 8);

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
const mentionsProtenix = text.includes("protenix");
const mentionsSeeds = text.includes("seed");
const mentions20Seeds = text.includes("20") && text.includes("seed");
const mentionsValidation = text.includes("validat") || text.includes("refolding") || text.includes("predict");
const mentionsMetrics = text.includes("iptm") || text.includes("ipsae") || text.includes("plddt") || text.includes("rmsd");

let status = "PASS";
const issues = [];
if (!mentionsProtenix) issues.push("response does not mention Protenix");
if (!mentionsSeeds) issues.push("response does not discuss seeds");
if (!mentionsValidation) issues.push("response does not discuss validation workflow");
if (!mentionsMetrics) issues.push("response does not mention scoring metrics");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
console.log(`Protenix: ${mentionsProtenix}, Seeds: ${mentionsSeeds}, 20-seed: ${mentions20Seeds}, Metrics: ${mentionsMetrics}`);
