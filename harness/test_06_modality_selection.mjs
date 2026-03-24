// Test 6: Modality Selection
// Expected: should recommend scFv modality with adalimumab/tezepelumab scaffolds for HER2
import { chat } from "./stress_test.mjs";

console.log("=== TEST 6: Modality Selection ===\n");
const r = await chat("I want to design antibodies against HER2. What modality and scaffolds would you recommend?", 12);

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
const mentionsHER2 = text.includes("her2") || text.includes("erbb2");
const mentionsScFv = text.includes("scfv") || text.includes("fab") || text.includes("antibody");
const mentionsScaffolds = text.includes("adalimumab") || text.includes("tezepelumab") || text.includes("scaffold");
const mentionsModality = text.includes("modality") || text.includes("format");

let status = "PASS";
const issues = [];
if (!mentionsHER2) issues.push("response does not mention HER2");
if (!mentionsScFv) issues.push("response does not mention scFv/Fab/antibody format");
if (!mentionsScaffolds) issues.push("response does not recommend specific scaffolds");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
