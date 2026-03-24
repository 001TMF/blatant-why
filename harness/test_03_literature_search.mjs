// Test 3: Literature Search
// Expected: should call research_search_prior_art or similar tool for PubMed results
import { chat } from "./stress_test.mjs";

console.log("=== TEST 3: Literature Search ===\n");
const r = await chat("Search PubMed for recent papers about nanobody design against viral targets", 5);

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
const hasResearchTool = tools.some(t => t.includes("research") || t.includes("prior_art") || t.includes("pubmed") || t.includes("PubMed") || t.includes("search_articles"));
const mentionsNanobody = r.resultText.toLowerCase().includes("nanobod") || r.resultText.toLowerCase().includes("vhh");
const mentionsViral = r.resultText.toLowerCase().includes("viral") || r.resultText.toLowerCase().includes("virus") || r.resultText.toLowerCase().includes("sars") || r.resultText.toLowerCase().includes("covid");

let status = "PASS";
const issues = [];
if (!hasResearchTool) issues.push("did NOT call research_search_prior_art or pubmed tool");
if (!mentionsNanobody) issues.push("response does not mention nanobodies");
if (!mentionsViral) issues.push("response does not discuss viral targets");
if (r.errors.length) issues.push("errors: " + r.errors.join("; "));
if (issues.length) status = issues.length >= 2 ? "FAIL" : "PARTIAL";

console.log("Status:", status);
if (issues.length) console.log("Issues:", issues.join("; "));
