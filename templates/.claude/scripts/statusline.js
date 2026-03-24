#!/usr/bin/env node
// BY statusline hook — PostToolUse
// Generates a compact status string for the Claude Code status bar.
// Reads config, active campaign, and provider info from .by/.


'use strict';
const { readFileSync, existsSync, readdirSync, statSync } = require('fs');
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

// Consume stdin (PostToolUse sends hook input, we read but don't need it here)
let stdinData = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => { stdinData += chunk; });
process.stdin.on('end', () => {
  try { run(); } catch { /* never crash Claude Code */ }
});

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function run() {
  const root = findProjectRoot(process.cwd());
  if (!root) {
    // No .by directory — output nothing (silent)
    return;
  }

  const byDir = resolve(root, '.by');

  // 1. Read model profile from config
  const config = readJson(resolve(byDir, 'config.json'));
  const profile = config?.model_profile || 'balanced';

  // 2. Detect provider from environment.json
  const envInfo = readJson(resolve(byDir, 'environment.json'));
  const provider = envInfo?.primary_provider || 'Tamarind';
  const providerTier = envInfo?.provider_tier || '';
  const providerLabel = providerTier ? `${provider} (${providerTier})` : provider;

  // 3. Find the most recent active campaign
  const campaignsDir = resolve(byDir, 'campaigns');
  let campaignSlug = 'none';
  let roundInfo = '';

  if (existsSync(campaignsDir)) {
    const entries = readdirSync(campaignsDir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => ({
        name: f,
        path: resolve(campaignsDir, f),
        mtime: statSync(resolve(campaignsDir, f)).mtimeMs
      }))
      .sort((a, b) => b.mtime - a.mtime);

    if (entries.length > 0) {
      const campaign = readJson(entries[0].path);
      if (campaign) {
        campaignSlug = campaign.slug || campaign.id || entries[0].name.replace('.json', '');
        const current = campaign.current_round ?? campaign.round ?? 0;
        const total = campaign.total_rounds ?? campaign.rounds ?? 0;
        const phase = campaign.phase || campaign.status || '';
        if (total > 0) {
          const dot = phase === 'running' ? ' \u25CF' : '';
          roundInfo = ` | round ${current}/${total}${dot}`;
        }
      }
    }
  }

  // 4. Format the statusline
  const statusline = `BY | ${providerLabel} | campaign: ${campaignSlug}${roundInfo} | ${profile}`;

  const output = {
    hookSpecificOutput: {
      hookEventName: 'PostToolUse',
      statusline
    }
  };

  process.stdout.write(JSON.stringify(output) + '\n');
}
