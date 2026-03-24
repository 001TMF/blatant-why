// Test 10: De Novo Protein Discussion
// Expected: should explain BoltzGen vs PXDesign tradeoffs, note PXDesign availability on Tamarind
import { chat } from "./stress_test.mjs";

console.log("=== TEST 10: De Novo Protein Discussion ===\n");
const r = await chat("I want to design a miniprotein binder against IL-6. Should I use BoltzGen or PXDesign? What are the tradeoffs?", 5);

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
const mentionsBoltzGen = text.includes("boltzgen") || text.includes("boltz");
const mentionsPXDesign = text.includes("pxdesign");
const mentionsTradeoffs = text.includes("tradeoff") || text.includes("trade-off") || text.includes("advantage") || text.includes("disadvantage") || text.includes("pros") || text.includes("cons") || text.includes("compared") || text.includes("versus") || text.includes("vs");
const mentionsIL6 = text.includes("il-6") || text.includes("il6") || text.includes("interleukin");
const mentionsTamarind = text.includes("tamarind");
const mentionsHitRate = text.includes("hit rate") || text.includes("17") || text.includes("82%");

let status = "PASS";
const issues = [];
if (!mentionsBoltzGen) issues.push("response does not mention BoltzGen");
if (!mentionsPXDesign) issues.push("response does not mention PXDesign");
if (!mentionsTradeoffs) issues.push("response does not discuss tradeoffs");
if (!mentionsIL6) issues.push("response does not mention IL-6");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));

const missing = [!mentionsBoltzGen, !mentionsPXDesign, !mentionsTradeoffs].filter(Boolean).length;
if (missing >= 2) status = "FAIL";
else if (issues.length) status = "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
console.log(`BoltzGen: ${mentionsBoltzGen}, PXDesign: ${mentionsPXDesign}, Tamarind: ${mentionsTamarind}, Hit rates: ${mentionsHitRate}`);
