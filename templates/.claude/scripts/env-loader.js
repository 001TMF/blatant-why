#!/usr/bin/env node
// Proteus env-loader hook — SessionStart
// Loads .env from project root, detects compute providers, outputs context for Claude Code.

import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';

// ---------------------------------------------------------------------------
// 1. Locate the project root by walking up until we find .proteus/
// ---------------------------------------------------------------------------
function findProjectRoot(start) {
  let dir = resolve(start);
  while (dir !== '/') {
    if (existsSync(resolve(dir, '.proteus'))) return dir;
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
if (process.env.TAMARIND_API_KEY) {
  const tier = process.env.TAMARIND_TIER || 'Pro';
  providers.push(`Tamarind (${tier})`);
}

// Levitate Bio — detected via API key
if (process.env.LEVITATE_API_KEY) {
  providers.push('Levitate');
}

// Local GPU — detected via tool directories or CUDA env
const localDirs = ['PROTEUS_FOLD_DIR', 'PROTEUS_PROT_DIR', 'PROTEUS_AB_DIR'];
const hasLocalDirs = localDirs.some((k) => process.env[k] && existsSync(process.env[k]));
const hasCuda = !!process.env.CUDA_VISIBLE_DEVICES;

if (hasLocalDirs || hasCuda) {
  const gpuLabel = process.env.PROTEUS_GPU_LABEL || 'GPU';
  providers.push(`Local GPU (${gpuLabel})`);
}

// SSH hosts — check for known config variables
if (process.env.PROTEUS_SSH_HOST) {
  providers.push(`SSH (${process.env.PROTEUS_SSH_HOST})`);
}

// Adaptyv Bio lab — detected via API key
const hasAdaptyv = !!process.env.ADAPTYV_API_KEY;

// ---------------------------------------------------------------------------
// 4. Build summary and output hook JSON
// ---------------------------------------------------------------------------
const providerSummary = providers.length > 0
  ? providers.join(', ')
  : 'none detected — set TAMARIND_API_KEY or PROTEUS_*_DIR';

const parts = [`Proteus environment loaded. Providers: ${providerSummary}.`];
if (hasAdaptyv) parts.push('Adaptyv Bio lab integration available.');
if (!root) parts.push('Warning: .proteus/ directory not found — run /proteus:init.');

const output = {
  hookSpecificOutput: {
    hookEventName: 'SessionStart',
    additionalContext: parts.join(' ')
  }
};

process.stdout.write(JSON.stringify(output) + '\n');
