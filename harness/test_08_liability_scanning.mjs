// Test 8: Liability Scanning
// Expected: should call screen_liabilities, return deamidation/oxidation findings
import { chat } from "./stress_test.mjs";

console.log("=== TEST 8: Liability Scanning ===\n");
const r = await chat("Screen this sequence for liabilities: EVQLVESGGGLVQPGGSLRLSCAASGFTFSNYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDRVGATGAFDIWGQGTLVTVSS", 5);

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
const text = r.resultText.toLowerCase();
const hasScreenTool = tools.some(t => t.includes("screen") || t.includes("liabilit"));
const mentionsDeamidation = text.includes("deamidation") || text.includes("ng") || text.includes("ns");
const mentionsOxidation = text.includes("oxidation") || text.includes("met");
const mentionsLiabilities = text.includes("liabilit") || text.includes("hotspot") || text.includes("risk");
const mentionsPosition = /position|pos\s|residue\s*\d|at\s+\d/i.test(r.resultText);

let status = "PASS";
const issues = [];
if (!hasScreenTool) issues.push("did NOT call screen_liabilities tool");
if (!mentionsLiabilities) issues.push("response does not discuss liabilities");
if (!mentionsDeamidation && !mentionsOxidation) issues.push("response does not mention specific liability types (deamidation/oxidation)");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
console.log(`Tool called: ${hasScreenTool}, Deamidation: ${mentionsDeamidation}, Oxidation: ${mentionsOxidation}, Positions: ${mentionsPosition}`);
