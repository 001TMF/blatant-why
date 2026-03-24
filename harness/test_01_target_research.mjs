// Test 1: Target Research (PDB + UniProt)
// Expected: should call pdb_search and uniprot_search, return structure info for EGFR
import { chat } from "./stress_test.mjs";

console.log("=== TEST 1: Target Research (PDB + UniProt) ===\n");
const r = await chat("Search PDB and UniProt for EGFR. What structures exist?", 8);

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
const hasPDB = tools.some(t => t.includes("pdb"));
const hasUniProt = tools.some(t => t.includes("uniprot"));
const mentionsEGFR = r.resultText.toLowerCase().includes("egfr");
const mentionsStructure = r.resultText.toLowerCase().includes("structure") || r.resultText.toLowerCase().includes("pdb");

let status = "PASS";
const issues = [];
if (!hasPDB) issues.push("did NOT call any pdb tool");
if (!hasUniProt) issues.push("did NOT call any uniprot tool");
if (!mentionsEGFR) issues.push("response does not mention EGFR");
if (!mentionsStructure) issues.push("response does not discuss structures");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
