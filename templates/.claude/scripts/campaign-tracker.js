#!/usr/bin/env node
// BY campaign-tracker hook — PostToolUse
// Detects campaign completion events and writes a knowledge entry to the
// campaign's JSON file for future reference.


'use strict';
const { readFileSync, writeFileSync, existsSync, mkdirSync } = require('fs');
const { resolve, dirname } = require('path');

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

// Tool names that signal campaign completion
const COMPLETION_TOOLS = new Set([
  'mcp__by-campaign__campaign_update_status',
  'mcp__by-screening__screen_composite'
]);

// ---------------------------------------------------------------------------
// Main — read stdin, detect completion, embed knowledge
// ---------------------------------------------------------------------------
let stdinData = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => { stdinData += chunk; });
process.stdin.on('end', () => {
  try { run(); } catch { /* never crash Claude Code */ }
});

function run() {
  let hookInput = null;
  try {
    hookInput = JSON.parse(stdinData);
  } catch {
    // No valid input — nothing to track
    return;
  }

  const toolName = hookInput?.tool_name || '';
  const toolInput = hookInput?.tool_input || {};
  const toolResponse = hookInput?.tool_response || {};

  // Only act on known completion tools
  if (!COMPLETION_TOOLS.has(toolName)) return;

  // Check if this is actually a completion event
  const isStatusCompletion =
    toolName.includes('campaign_update_status') &&
    toolInput.status === 'completed';

  const isScreeningFinal =
    toolName.includes('screen_composite') &&
    (toolInput.final === true || toolInput.final === 'true');

  if (!isStatusCompletion && !isScreeningFinal) return;

  // ---------------------------------------------------------------------------
  // Build knowledge entry from the campaign data
  // ---------------------------------------------------------------------------
  const root = findProjectRoot(process.cwd());
  if (!root) return;

  const campaignsDir = resolve(root, '.by', 'campaigns');
  if (!existsSync(campaignsDir)) {
    mkdirSync(campaignsDir, { recursive: true });
  }

  // Determine campaign ID from tool input or response
  const campaignId =
    toolInput.campaign_id ||
    toolResponse.campaign_id ||
    toolInput.id ||
    'unknown';

  const campaignPath = resolve(campaignsDir, `${campaignId}.json`);
  const existing = readJson(campaignPath) || {};

  // Build the knowledge entry
  const knowledgeEntry = {
    completed_at: new Date().toISOString(),
    completion_source: toolName.split('__').pop(),
    summary: buildSummary(toolInput, toolResponse),
    top_designs: extractTopDesigns(toolResponse),
    screening_stats: extractScreeningStats(toolResponse)
  };

  // Merge into existing campaign data
  const updated = {
    ...existing,
    id: campaignId,
    status: 'completed',
    knowledge: [
      ...(existing.knowledge || []),
      knowledgeEntry
    ]
  };

  writeFileSync(campaignPath, JSON.stringify(updated, null, 2) + '\n', 'utf-8');

  // Output brief context (non-silent for completions)
  const output = {
    hookSpecificOutput: {
      hookEventName: 'PostToolUse',
      additionalContext: `Campaign ${campaignId} completed. Knowledge entry saved to .by/campaigns/${campaignId}.json.`
    }
  };
  process.stdout.write(JSON.stringify(output) + '\n');
}

// ---------------------------------------------------------------------------
// Extraction helpers
// ---------------------------------------------------------------------------
function buildSummary(input, response) {
  const parts = [];
  if (input.target) parts.push(`Target: ${input.target}`);
  if (input.method) parts.push(`Method: ${input.method}`);
  if (response.total_designs) parts.push(`${response.total_designs} designs generated`);
  if (response.passing_designs) parts.push(`${response.passing_designs} passed screening`);
  return parts.join('. ') || 'Campaign completed.';
}

function extractTopDesigns(response) {
  if (!response.top_designs && !response.ranked) return [];
  const designs = response.top_designs || response.ranked || [];
  // Keep top 5 for the knowledge entry
  return designs.slice(0, 5).map((d) => ({
    id: d.id || d.name,
    ipTM: d.iptm ?? d.ipTM,
    ipSAE: d.ipsae ?? d.ipSAE,
    p_bind: d.p_bind ?? d.pbind,
    composite: d.composite ?? d.score
  }));
}

function extractScreeningStats(response) {
  if (!response.stats && !response.screening) return null;
  return response.stats || response.screening || null;
}
