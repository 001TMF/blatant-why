#!/usr/bin/env node
// BY safety-gate hook — PreToolUse
// Blocks Adaptyv Bio lab submissions unless a fresh lab-approval.json exists.
// This enforces the triple-layer safety gate for wet-lab submissions.

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function findProjectRoot(start) {
  let dir = resolve(start);
  while (dir !== '/') {
    if (existsSync(resolve(dir, '.by'))) return dir;
    dir = dirname(dir);
  }
  return null;
}

function readJson(filePath) {
  try {
    return JSON.parse(readFileSync(filePath, 'utf-8'));
  } catch {
    return null;
  }
}

// Maximum age for a lab approval (5 minutes)
const APPROVAL_TTL_MS = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// Main — read stdin, evaluate gate, output decision
// ---------------------------------------------------------------------------
let stdinData = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => { stdinData += chunk; });
process.stdin.on('end', () => {
  run();
});

function run() {
  // Parse hook input (contains tool_name, tool_input, etc.)
  let hookInput = null;
  try {
    hookInput = JSON.parse(stdinData);
  } catch {
    // If stdin is empty or invalid, block by default
  }

  const root = findProjectRoot(process.cwd());

  // Gate 1: .by/ directory must exist
  if (!root) {
    block('No .by/ directory found. Initialize with /by:init first.');
    return;
  }

  const approvalPath = resolve(root, '.by', 'lab-approval.json');

  // Gate 2: lab-approval.json must exist
  if (!existsSync(approvalPath)) {
    block('Lab submission requires /by:approve-lab first. No approval file found.');
    return;
  }

  // Gate 3: approval must be fresh (within TTL)
  const approval = readJson(approvalPath);
  if (!approval || !approval.timestamp) {
    block('Lab approval file is malformed. Run /by:approve-lab again.');
    return;
  }

  const approvedAt = new Date(approval.timestamp).getTime();
  const now = Date.now();
  const age = now - approvedAt;

  if (isNaN(approvedAt) || age > APPROVAL_TTL_MS) {
    const minutesAgo = Math.round(age / 60000);
    block(
      `Lab approval expired (approved ${minutesAgo} min ago, TTL is 5 min). ` +
      'Run /by:approve-lab again.'
    );
    return;
  }

  // All gates passed — approve the submission
  const output = { decision: 'approve' };
  process.stdout.write(JSON.stringify(output) + '\n');
}

function block(reason) {
  const output = {
    decision: 'block',
    reason: reason || 'Lab submission requires /by:approve-lab first. Approval expires after 5 minutes.'
  };
  process.stdout.write(JSON.stringify(output) + '\n');
}
