#!/usr/bin/env node
// Run all 10 stress tests sequentially and produce a summary report
import { execSync } from "child_process";
import { resolve } from "path";

const dir = import.meta.dirname;
const tests = [
  "test_01_target_research.mjs",
  "test_02_sabdab_search.mjs",
  "test_03_literature_search.mjs",
  "test_04_cost_estimation.mjs",
  "test_05_screening_explanation.mjs",
  "test_06_modality_selection.mjs",
  "test_07_campaign_planning.mjs",
  "test_08_liability_scanning.mjs",
  "test_09_structure_prediction.mjs",
  "test_10_de_novo_protein.mjs",
];

const results = [];
const totalStart = Date.now();

for (const test of tests) {
  const testPath = resolve(dir, test);
  console.log(`\n${"=".repeat(70)}`);
  console.log(`Running: ${test}`);
  console.log("=".repeat(70));

  const start = Date.now();
  let output = "";
  let exitCode = 0;

  try {
    output = execSync(`node "${testPath}"`, {
      cwd: dir,
      encoding: "utf-8",
      timeout: 300000, // 5 min per test
      env: { ...process.env },
    });
  } catch (e) {
    output = e.stdout || "";
    output += "\n" + (e.stderr || "");
    exitCode = e.status || 1;
  }

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(output);

  // Extract status from output
  const statusMatch = output.match(/Status:\s*(PASS|FAIL|PARTIAL)/);
  const status = statusMatch ? statusMatch[1] : (exitCode ? "ERROR" : "UNKNOWN");

  results.push({ test, status, elapsed, exitCode });
}

// Summary
const totalElapsed = ((Date.now() - totalStart) / 1000).toFixed(1);
console.log(`\n${"=".repeat(70)}`);
console.log("STRESS TEST SUMMARY");
console.log("=".repeat(70));
console.log(`Total time: ${totalElapsed}s\n`);

const pad = (s, n) => String(s).padEnd(n);
console.log(`${pad("Test", 40)} ${pad("Status", 10)} ${pad("Time", 10)} Exit`);
console.log("-".repeat(70));

let pass = 0, fail = 0, partial = 0, error = 0;
for (const r of results) {
  const icon = r.status === "PASS" ? "[OK]" : r.status === "FAIL" ? "[!!]" : r.status === "PARTIAL" ? "[~]" : "[??]";
  console.log(`${pad(r.test, 40)} ${pad(icon + " " + r.status, 10)} ${pad(r.elapsed + "s", 10)} ${r.exitCode}`);
  if (r.status === "PASS") pass++;
  else if (r.status === "FAIL") fail++;
  else if (r.status === "PARTIAL") partial++;
  else error++;
}

console.log("-".repeat(70));
console.log(`PASS: ${pass}  PARTIAL: ${partial}  FAIL: ${fail}  ERROR: ${error}  TOTAL: ${results.length}`);
console.log(`Overall: ${pass}/${results.length} passed (${((pass / results.length) * 100).toFixed(0)}%)`);
