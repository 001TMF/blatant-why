#!/usr/bin/env node
// BY env-loader hook — SessionStart
// Loads .env from project root, detects compute providers, discovers existing
// campaigns, and outputs rich context for Claude Code so the agent announces
// itself and has immediate situational awareness.


'use strict';
const { readFileSync, readdirSync, existsSync } = require('fs');
const { resolve, dirname, join } = require('path');

// ---------------------------------------------------------------------------
// 1. Locate the project root by walking up until we find .by/
// ---------------------------------------------------------------------------
function findProjectRoot(start) {
  let dir = resolve(start);
  while (dir !== '/') {
    if (existsSync(resolve(dir, '.by'))) return dir;
    dir = dirname(dir);
  }
  return null;
}

const root = findProjectRoot(process.cwd());

// ---------------------------------------------------------------------------
// 2. Parse .env file (KEY=VALUE, skip comments and blanks)
// ---------------------------------------------------------------------------
function parseEnv(filePath) {
  const vars = {};
  if (!existsSync(filePath)) return vars;

  const lines = readFileSync(filePath, 'utf-8').split('\n');
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;

    const eqIdx = line.indexOf('=');
    if (eqIdx === -1) continue;

    const key = line.slice(0, eqIdx).trim();
    let value = line.slice(eqIdx + 1).trim();
    // Strip surrounding quotes if present
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    vars[key] = value;
  }
  return vars;
}

const envPath = root ? resolve(root, '.env') : resolve(process.cwd(), '.env');
const envVars = parseEnv(envPath);

// Merge into process.env (does not overwrite existing)
for (const [key, value] of Object.entries(envVars)) {
  if (process.env[key] === undefined) {
    process.env[key] = value;
  }
}

// ---------------------------------------------------------------------------
// 3. Detect available compute providers
// ---------------------------------------------------------------------------
const providers = [];

// Tamarind Bio — detected via API key
const hasTamarind = !!process.env.TAMARIND_API_KEY;
if (hasTamarind) {
  const tier = process.env.TAMARIND_TIER || 'Pro';
  providers.push(`Tamarind (${tier})`);
}

// Local GPU — detected via tool directories or CUDA env
const localDirs = ['PROTEUS_FOLD_DIR', 'PROTEUS_PROT_DIR', 'PROTEUS_AB_DIR'];
const hasLocalDirs = localDirs.some((k) => process.env[k] && existsSync(process.env[k]));
const hasCuda = !!process.env.CUDA_VISIBLE_DEVICES;
const hasLocalGpu = hasLocalDirs || hasCuda;

if (hasLocalGpu) {
  const gpuLabel = process.env.PROTEUS_GPU_LABEL || 'GPU';
  providers.push(`Local GPU (${gpuLabel})`);
}

// SSH hosts — check for known config variables
const hasSsh = !!process.env.PROTEUS_SSH_HOST;
if (hasSsh) {
  providers.push(`SSH (${process.env.PROTEUS_SSH_HOST})`);
}

// Adaptyv Bio lab — detected via API key
const hasAdaptyv = !!process.env.ADAPTYV_API_KEY;

// ---------------------------------------------------------------------------
// 4. Detect existing campaigns
// ---------------------------------------------------------------------------
const campaigns = [];
if (root) {
  const campaignsDir = resolve(root, '.by', 'campaigns');
  if (existsSync(campaignsDir)) {
    try {
      const dirs = readdirSync(campaignsDir, { withFileTypes: true });
      for (const d of dirs) {
        if (!d.isDirectory()) continue;
        const logPath = join(campaignsDir, d.name, 'campaign_log.json');
        const statePath = join(campaignsDir, d.name, 'state.json');
        // A campaign is detected if it has either a campaign_log.json or state.json
        if (existsSync(logPath) || existsSync(statePath)) {
          let name = d.name;
          let status = 'unknown';
          // Try to read state.json for campaign name and status
          try {
            const state = JSON.parse(readFileSync(statePath, 'utf-8'));
            if (state.target) name = state.target;
            if (state.phase) status = state.phase;
            if (state.status) status = state.status;
          } catch { /* use directory name */ }
          campaigns.push({ id: d.name, name, status });
        }
      }
    } catch { /* campaigns dir unreadable — skip */ }
  }
}

// ---------------------------------------------------------------------------
// 5. Read config profile
// ---------------------------------------------------------------------------
let profile = 'balanced';
if (root) {
  try {
    const config = JSON.parse(readFileSync(resolve(root, '.by', 'config.json'), 'utf-8'));
    if (config.model_profile) profile = config.model_profile;
    if (config.profile) profile = config.profile;
  } catch { /* default balanced */ }
}

// ---------------------------------------------------------------------------
// 6. Build rich additionalContext for agent session start
// ---------------------------------------------------------------------------
const providerSummary = providers.length > 0
  ? providers.join(', ')
  : 'none detected — set TAMARIND_API_KEY or PROTEUS_*_DIR';

// Build environment status line (symbol format matching BY display patterns)
const envLine = `Tamarind ${hasTamarind ? '\u2713' : '\u25CB'} | Local GPU ${hasLocalGpu ? '\u2713' : '\u25CB'} | SSH ${hasSsh ? '\u2713' : '\u25CB'}`;

const parts = [];

// Identity line — tells the agent who it is
parts.push('You are BY (Blatant-Why), a protein design agent.');
parts.push(`Environment: ${envLine}.`);
parts.push(`Providers: ${providerSummary}.`);
parts.push(`Profile: ${profile}.`);

if (hasAdaptyv) parts.push('Adaptyv Bio lab integration available.');

// Campaign summary
if (campaigns.length > 0) {
  const campaignList = campaigns.map((c) => `${c.name} (${c.status})`).join(', ');
  parts.push(`Existing campaigns (${campaigns.length}): ${campaignList}.`);
  parts.push('Offer to resume an existing campaign or start a new one.');
} else {
  parts.push('No existing campaigns found. This may be a first session — show /by:welcome orientation.');
}

if (!root) parts.push('Warning: .by/ directory not found — run /by:setup to initialize.');

// Suggested first action
parts.push('On session start: display the BY banner, show environment status, and offer next steps per the "On Session Start" section in CLAUDE.md.');

const output = {
  hookSpecificOutput: {
    hookEventName: 'SessionStart',
    additionalContext: parts.join(' ')
  }
};

process.stdout.write(JSON.stringify(output) + '\n');
