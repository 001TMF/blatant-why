# BY Init Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the buggy Ink TUI with `npx by init` — a Ruflo-pattern npm package that generates the complete protein design environment for Claude Code.

**Architecture:** npm CLI package generates files into the project directory: 10 PEP 723 MCP servers, 9 agents, 15 skills, 8 commands, 4 hooks, ChromaDB knowledge system, CLAUDE.md. Claude Code is the native frontend. Model routing via GSD-pattern config profiles.

**Tech Stack:** TypeScript (init CLI), Python + uv (MCP servers), ChromaDB + sentence-transformers (knowledge), Claude Code plugin conventions (agents/skills/commands/hooks).

**Spec:** `docs/superpowers/specs/2026-03-24-by-init-redesign.md`

---

## Phase 1: npm Package Skeleton

### Task 1: Initialize npm package

**Files:**
- Create: `package.json`
- Create: `src/index.ts`
- Create: `src/init.ts`
- Create: `tsconfig.json`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "by-design",
  "version": "0.1.0",
  "description": "Protein design agent for Claude Code — MCP servers, skills, agents, and learning system",
  "type": "module",
  "bin": {
    "by": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsx src/index.ts"
  },
  "files": ["dist/", "templates/"],
  "dependencies": {
    "chalk": "^5.3.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "tsx": "^4.0.0",
    "@types/node": "^20.0.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "declaration": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create src/index.ts (CLI entry)**

```typescript
#!/usr/bin/env node
import { runInit } from "./init.js";

const args = process.argv.slice(2);
const flags = {
  help: args.includes("--help") || args.includes("-h"),
  skipKeys: args.includes("--skip-keys"),
  force: args.includes("--force"),
};

if (flags.help) {
  console.log(`
  by init — Generate protein design environment for Claude Code

  Usage: npx by-design init [options]

  Options:
    --skip-keys   Skip API key prompts
    --force       Overwrite existing files
    --help        Show this help
  `);
  process.exit(0);
}

await runInit({ skipKeys: flags.skipKeys, force: flags.force });
```

- [ ] **Step 4: Create src/init.ts (init orchestrator stub)**

```typescript
import { resolve } from "path";
import chalk from "chalk";

export interface InitOptions {
  skipKeys: boolean;
  force: boolean;
}

export async function runInit(options: InitOptions): Promise<void> {
  const cwd = process.cwd();
  console.log(chalk.bold("\n  BY — Protein Design Agent\n"));

  // Step 1: Check prereqs
  console.log("  Checking prerequisites...");
  await checkPrereqs();

  // Step 2: Copy templates
  console.log("  Generating files...");
  // TODO: implement in Task 2

  // Step 3: API keys
  if (!options.skipKeys) {
    // TODO: implement in Task 3
  }

  // Step 4: Verify
  console.log("  Verifying MCP servers...");
  // TODO: implement in Task 4

  console.log(chalk.green("\n  BY initialized. Run:\n"));
  console.log("    claude\n");
  console.log("  Then try:");
  console.log('    "Research PD-L1 as a target for nanobody design"\n');
}

async function checkPrereqs(): Promise<void> {
  const { execSync } = await import("child_process");

  // Check uv
  try {
    execSync("uv --version", { stdio: "pipe" });
  } catch {
    console.error(chalk.red("  Error: uv not found. Install from https://docs.astral.sh/uv/"));
    process.exit(1);
  }

  // Check Python
  try {
    const pyVer = execSync("python3 --version", { encoding: "utf-8" }).trim();
    const [major, minor] = pyVer.replace("Python ", "").split(".").map(Number);
    if (major < 3 || (major === 3 && minor < 11)) {
      console.error(chalk.red(`  Error: Python >= 3.11 required (found ${pyVer})`));
      process.exit(1);
    }
  } catch {
    console.error(chalk.red("  Error: Python 3 not found"));
    process.exit(1);
  }
}
```

- [ ] **Step 5: Build and verify**

Run: `npm install && npm run build`
Expected: Compiles to `dist/index.js`

- [ ] **Step 6: Commit**

```bash
git add package.json tsconfig.json src/
git commit -m "feat: by init CLI skeleton with prereq checks"
```

---

### Task 2: Template copy system

**Files:**
- Create: `src/templates.ts`
- Create: `templates/` directory structure (empty marker files for now)

- [ ] **Step 1: Create src/templates.ts**

```typescript
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import {
  mkdirSync, copyFileSync, existsSync, readFileSync, writeFileSync, readdirSync, statSync
} from "fs";
import chalk from "chalk";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEMPLATE_ROOT = resolve(__dirname, "..", "templates");

interface CopyResult {
  created: string[];
  skipped: string[];
}

export function copyTemplates(targetDir: string, force: boolean): CopyResult {
  const result: CopyResult = { created: [], skipped: [] };
  copyDirRecursive(TEMPLATE_ROOT, targetDir, force, result);
  return result;
}

function copyDirRecursive(
  src: string, dest: string, force: boolean, result: CopyResult
): void {
  mkdirSync(dest, { recursive: true });

  for (const entry of readdirSync(src)) {
    const srcPath = resolve(src, entry);
    const destPath = resolve(dest, entry);
    const stat = statSync(srcPath);

    if (stat.isDirectory()) {
      copyDirRecursive(srcPath, destPath, force, result);
    } else {
      if (existsSync(destPath) && !force) {
        result.skipped.push(destPath);
      } else {
        mkdirSync(dirname(destPath), { recursive: true });
        copyFileSync(srcPath, destPath);
        result.created.push(destPath);
      }
    }
  }
}

export function generateSettingsJson(
  targetDir: string,
  mcpServerDir: string,
): string {
  const servers: Record<string, unknown> = {};

  const serverFiles = readdirSync(mcpServerDir).filter(f => f.endsWith(".py"));
  for (const file of serverFiles) {
    const name = file.replace(".py", "").replace("_", "-");
    servers[`by-${name}`] = {
      command: "uv",
      args: ["run", "--script", resolve(mcpServerDir, file)],
    };
  }

  const settings = {
    permissions: {
      allow: [
        "mcp__by-*",
        "Bash(uv run *)",
      ],
    },
    mcpServers: servers,
  };

  const path = resolve(targetDir, ".claude", "settings.json");
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(settings, null, 2) + "\n");
  return path;
}
```

- [ ] **Step 2: Create templates directory skeleton**

```bash
mkdir -p templates/.claude/{agents,skills,commands/by,hooks,scripts}
mkdir -p templates/mcp_servers
mkdir -p templates/.by/{campaigns}
touch templates/.claude/agents/.gitkeep
touch templates/.claude/skills/.gitkeep
touch templates/mcp_servers/.gitkeep
```

- [ ] **Step 3: Wire into init.ts**

Add to `runInit()` after prereq check:

```typescript
import { copyTemplates, generateSettingsJson } from "./templates.js";

// In runInit():
const result = copyTemplates(cwd, options.force);
console.log(`  Created ${result.created.length} files, skipped ${result.skipped.length}`);

const mcpDir = resolve(cwd, "mcp_servers");
generateSettingsJson(cwd, mcpDir);
```

- [ ] **Step 4: Build and test**

Run: `npm run build && node dist/index.js --help`
Expected: Shows help text

- [ ] **Step 5: Commit**

```bash
git add src/templates.ts templates/
git commit -m "feat: template copy system for by init"
```

---

## Phase 2: MCP Server Migration

### Task 3: Add PEP 723 headers to all MCP servers

**Files:**
- Modify: `mcp_servers/pdb/server.py` (add header)
- Modify: `mcp_servers/uniprot/server.py`
- Modify: `mcp_servers/sabdab/server.py`
- Modify: `mcp_servers/screening/server.py`
- Modify: `mcp_servers/campaign/server.py`
- Modify: `mcp_servers/research/server.py`
- Modify: `mcp_servers/tamarind/server.py`
- Modify: `mcp_servers/adaptyv/server.py`
- Modify: `mcp_servers/local_compute/server.py`
- Modify: `mcp_servers/knowledge/server.py`

For each server:

- [ ] **Step 1: Read each server.py, identify its imports/deps**

Run: `head -30 mcp_servers/*/server.py` to see current imports.

- [ ] **Step 2: Add PEP 723 header to each server**

Pattern (adapt deps per server):
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "mcp>=1.0.0",
#   "httpx>=0.27",
# ]
# ///
```


- [ ] **Step 3: Test each server starts with uv**

Run: `for srv in mcp_servers/*/server.py; do echo "=== $srv ===" && timeout 5 uv run --script "$srv" 2>&1 | head -3; done`
Expected: Each server starts without import errors (may hang waiting for stdin — that's correct MCP behavior).

- [ ] **Step 4: Commit**

```bash
git add mcp_servers/
git commit -m "feat: add PEP 723 headers to all MCP servers — uv run ready"
```

### Task 4: Create unified cloud MCP server

**Files:**
- Create: `mcp_servers/cloud/server.py`

- [ ] **Step 1: Create cloud server with Tamarind + SSH backends**

`mcp_servers/cloud/server.py` — unified cloud compute server:
- `cloud_list_providers` — list available compute (Tamarind tier, SSH hosts, local GPU)
- `cloud_submit_job` — route to Tamarind API or SSH based on provider
- `cloud_submit_batch` — submit multiple jobs, respect concurrent limits
- `cloud_get_status` / `cloud_get_batch_status` — poll job status
- `cloud_wait_batch` — block until batch completes
- `cloud_get_results` — download results

Tamarind backend: migrate from existing `mcp_servers/tamarind/server.py`.
SSH backend: wrap `paramiko` for SSH command execution (upload → run → download).

- [ ] **Step 2: Test cloud server**

Run: `uv run --script mcp_servers/cloud/server.py 2>&1 | head -3`
Expected: Starts without error.


```bash
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: unified cloud MCP server (Tamarind + SSH)"
```

### Task 5: Rewrite knowledge MCP server with ChromaDB

**Files:**
- Rewrite: `mcp_servers/knowledge/server.py`

- [ ] **Step 1: Rewrite knowledge server with ChromaDB + sentence-transformers**

PEP 723 deps:
```python
# dependencies = [
#   "mcp>=1.0.0",
#   "chromadb>=0.5.0",
#   "sentence-transformers>=3.0.0",
# ]
```

Collections: campaigns, scaffolds, targets, failures, user_preferences.

MCP tools:
- `knowledge_store_campaign(target, modality, params, outcomes, scores)` — embed campaign outcome
- `knowledge_query_similar(target_description, modality, top_k)` — semantic search for similar campaigns
- `knowledge_scaffold_rankings(target_class)` — best scaffolds for target type
- `knowledge_store_failure(campaign_id, failure_description, root_cause)` — embed failure
- `knowledge_get_recommendations(target, modality)` — pre-campaign parameter suggestions
- `knowledge_consolidate()` — run distill/prune/merge cycle

ReasoningBank pipeline:
- Retrieve: ChromaDB semantic search with MMR (lambda=0.7)
- Judge: filter by quality score >= 0.6
- Distill: extract reusable patterns
- Consolidate: dedup (>0.95 similarity), prune (>30 days, <5 uses)

Knowledge graph: simple adjacency dict stored in ChromaDB metadata. PageRank via power iteration.

- [ ] **Step 2: Test knowledge server starts**

Run: `uv run --script mcp_servers/knowledge/server.py 2>&1 | head -3`
Expected: Starts (first run downloads 80MB embedding model, cached after).

- [ ] **Step 3: Commit**

```bash
git add mcp_servers/knowledge/server.py
git commit -m "feat: ChromaDB knowledge server with semantic search and ReasoningBank"
```

---

## Phase 3: Agents

### Task 6: Create 9 agent markdown files

**Files:**
- Create: `templates/.claude/agents/by-research.md`
- Create: `templates/.claude/agents/by-design.md`
- Create: `templates/.claude/agents/by-screening.md`
- Create: `templates/.claude/agents/by-campaign.md`
- Create: `templates/.claude/agents/by-knowledge.md`
- Create: `templates/.claude/agents/by-verifier.md`
- Create: `templates/.claude/agents/by-plan-checker.md`
- Create: `templates/.claude/agents/by-environment.md`
- Create: `templates/.claude/agents/by-lab.md`

- [ ] **Step 1: Create by-research agent**

```markdown
---
name: by-research
description: Target analysis, literature review, prior art search, epitope identification. Uses PDB, UniProt, SAbDab, and research MCP tools directly.
tools: Read, Bash, Grep, Glob, WebSearch, WebFetch, mcp__by-pdb__*, mcp__by-uniprot__*, mcp__by-sabdab__*, mcp__by-research__*, mcp__by-knowledge__*
disallowedTools: mcp__by-cloud__cloud_submit_job, mcp__by-adaptyv__*
---

You are the BY Research Agent. Your job is to thoroughly analyze a protein target for binder design.

## Workflow

1. Search UniProt for the target protein (sequence, function, domains, variants)
2. Search PDB for crystal structures (resolution, chains, ligands)
3. Search SAbDab for existing antibody/nanobody binders
4. Search prior art via by-research tools
5. Identify the best structure for design (highest resolution, relevant complex)
6. Analyze interface residues and classify hotspots
7. Query knowledge base for similar past campaigns
8. Present structured findings with recommendations

## Output Format

Return a structured research report with:
- Target summary table (name, UniProt ID, length, organism, function)
- Best PDB structures table (PDB ID, resolution, chains, method)
- Existing binders table (source, type, affinity if known)
- Interface analysis (hotspot residues with classifications)
- Prior campaign learnings (from knowledge base)
- Recommended epitope and modality

## Quality Gates

- Must call at least 3 different MCP servers (PDB + UniProt + one more)
- Must identify at least one PDB structure
- Must present hotspot residues if interface data available
- Must check knowledge base for prior campaigns against similar targets
```

- [ ] **Step 2: Create remaining 8 agents (by-design, by-screening, by-campaign, by-knowledge, by-verifier, by-plan-checker, by-environment, by-lab)**

Each follows the same YAML frontmatter pattern with:
- `name`, `description`, `tools`, `disallowedTools`
- Role description
- Workflow steps
- Output format
- Quality gates

Key constraints per agent:
- **by-design**: Can call cloud/local compute. Cannot call adaptyv.
- **by-screening**: Fast, bulk work. Cannot submit compute or lab.
- **by-campaign**: Planning agent. Can create campaigns, estimate costs. Cannot confirm lab.
- **by-knowledge**: Retrieval only. Cannot submit anything.
- **by-verifier**: Checks quality gates independently. Cannot modify campaign state.
- **by-plan-checker**: Reviews plans for completeness. Cannot modify campaign.
- **by-environment**: Discovers tools, GPU, SSH. Writes environment.json. Runs on /by:setup.
- **by-lab**: Triple-gated Adaptyv submission. Requires lab-approval.json.

- [ ] **Step 3: Commit**

```bash
git add templates/.claude/agents/
git commit -m "feat: 9 agent definitions with roles, tools, and quality gates"
```

---

## Phase 4: Commands

### Task 7: Create 4 new slash commands

**Files:**
- Create: `templates/.claude/commands/by/load.md`
- Create: `templates/.claude/commands/by/approve-lab.md`
- Create: `templates/.claude/commands/by/set-profile.md`
- Create: `templates/.claude/commands/by/setup.md`
- Copy existing: `watch.md`, `status.md`, `screen.md`, `results.md`

- [ ] **Step 1: Create /by:load command**

```markdown
---
name: by:load
description: Load a protein target from PDB or UniProt and analyze it for design
argument-hint: "<target name or ID>"
---

## Instructions

You are running the /by:load command. Spawn the by-research agent to analyze the target.

### Step 0: Read model profile

```bash
MODEL_PROFILE=$(cat .by/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "balanced")
```

Model lookup for this command:
| Agent | quality | balanced | budget |
|-------|---------|----------|--------|
| by-research | opus | sonnet | sonnet |

### Step 1: Spawn research agent

Spawn by-research agent with the target from the user's argument. Pass the resolved model.

### Step 2: Review output

Present the research report to the user. Suggest next steps:
1. Start a design campaign
2. Analyze a different epitope
3. Load a different target
```

- [ ] **Step 2: Create /by:approve-lab, /by:set-profile, /by:setup**

Each command follows the same pattern:
- YAML frontmatter with name, description, argument-hint
- Step 0: read model profile from config
- Model lookup table for agents used by this command
- Step-by-step instructions

- [ ] **Step 3: Copy existing commands**

```bash
cp .claude/commands/watch.md templates/.claude/commands/by/watch.md
cp .claude/commands/screen.md templates/.claude/commands/by/screen.md
cp .claude/commands/status.md templates/.claude/commands/by/status.md
cp .claude/commands/results.md templates/.claude/commands/by/results.md
```

Update frontmatter to use `by:` prefix.

- [ ] **Step 4: Commit**

```bash
git add templates/.claude/commands/
git commit -m "feat: 8 slash commands with GSD-pattern model profile lookup"
```

---

## Phase 5: Hooks

### Task 8: Create 4 compiled hook scripts

**Files:**
- Create: `templates/.claude/hooks/hooks.json`
- Create: `templates/.claude/scripts/env-loader.js`
- Create: `templates/.claude/scripts/statusline.js`
- Create: `templates/.claude/scripts/safety-gate.js`
- Create: `templates/.claude/scripts/campaign-tracker.js`

- [ ] **Step 1: Create hooks.json**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ${CLAUDE_PROJECT_DIR}/.claude/scripts/env-loader.js"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ${CLAUDE_PROJECT_DIR}/.claude/scripts/statusline.js"
          },
          {
            "type": "command",
            "command": "node ${CLAUDE_PROJECT_DIR}/.claude/scripts/campaign-tracker.js"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "adaptyv_confirm_submission",
        "hooks": [
          {
            "type": "command",
            "command": "node ${CLAUDE_PROJECT_DIR}/.claude/scripts/safety-gate.js"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Create env-loader.js**

Reads `.env` from project root, sets `process.env`, detects compute providers, outputs JSON for Claude Code statusline.

- [ ] **Step 3: Create statusline.js**

Reads `.by/config.json` and campaign state. Outputs statusline:
`BY | Tamarind (Pro, 477 left) | campaign: pd-l1-abc | round 2/3`

- [ ] **Step 4: Create safety-gate.js**

Checks `.by/lab-approval.json` exists and timestamp < 5 minutes. Blocks `adaptyv_confirm_submission` if not.

- [ ] **Step 5: Create campaign-tracker.js**

Detects campaign completion from PostToolUse context. Calls knowledge MCP server to embed campaign outcome.

- [ ] **Step 6: Commit**

```bash
git add templates/.claude/hooks/ templates/.claude/scripts/
git commit -m "feat: 4 hooks — env loader, statusline, safety gate, campaign tracker"
```

---

## Phase 6: CLAUDE.md + Config

### Task 9: Create CLAUDE.md template and config

**Files:**
- Create: `templates/CLAUDE.md`
- Create: `templates/.by/config.json`
- Create: `templates/.gitignore-append`

- [ ] **Step 1: Create CLAUDE.md template**

Consolidate from existing `harness/CLAUDE.md` + `harness/src/agent.ts` `buildSystemPrompt()`. Sections:
- Identity (BY, hands-on protein design agent)
- Tool priority (MCP first, exact tool names listed)
- Scoring hierarchy (ipSAE primary, composite formula)
- Campaign workflow
- Fold validation requirement
- Environment awareness (read environment.json)
- Learning (read knowledge before planning)
- Safety gates
- Modality auto-detection
- Model profile reference (lookup tables per command)

- [ ] **Step 2: Create default config**

```json
{
  "model_profile": "balanced",
  "compute": {
    "default_provider": "tamarind",
    "ssh_hosts": [],
    "local_gpu": false
  },
  "workflow": {
    "auto_research": true,
    "auto_screen": true,
    "fold_validation": true
  },
  "safety": {
    "require_plan_approval": true,
    "require_lab_approval": true
  }
}
```

- [ ] **Step 3: Create gitignore append**

```
# BY
.claude/settings.local.json
.by/knowledge.db
.by/environment.json
```

- [ ] **Step 4: Commit**

```bash
git add templates/CLAUDE.md templates/.by/ templates/.gitignore-append
git commit -m "feat: CLAUDE.md template and default config"
```

---

## Phase 7: Copy skills into templates

### Task 10: Copy existing skills into template directory

**Files:**
- Copy: `.claude/skills/*` → `templates/.claude/skills/`

- [ ] **Step 1: Copy all 15 skills**

```bash
cp -r .claude/skills/* templates/.claude/skills/
```

- [ ] **Step 2: Verify all SKILL.md files present**

Run: `find templates/.claude/skills -name "SKILL.md" | wc -l`
Expected: 15 (or 14 if skill-creator is excluded)

- [ ] **Step 3: Commit**

```bash
git add templates/.claude/skills/
git commit -m "feat: copy 15 skills into init templates"
```

---

## Phase 8: Wire init orchestrator

### Task 11: Complete the init flow

**Files:**
- Modify: `src/init.ts`
- Create: `src/api-keys.ts`
- Create: `src/verify.ts`

- [ ] **Step 1: Create API key prompter**

`src/api-keys.ts` — reads stdin for TAMARIND_API_KEY and ADAPTYV_API_KEY. Writes to `settings.local.json` (gitignored).

- [ ] **Step 2: Create verifier**

`src/verify.ts` — runs `uv run --script mcp_servers/pdb.py --help` (or similar health check) to verify deps resolve.

- [ ] **Step 3: Complete init.ts orchestrator**

Wire together: checkPrereqs → copyTemplates → generateSettingsJson → promptApiKeys → appendGitignore → verify → print summary.

- [ ] **Step 4: Build and test end-to-end**

Run: `npm run build && mkdir /tmp/test-by && cd /tmp/test-by && node /path/to/dist/index.js`
Expected: Files generated, settings.json has MCP servers, CLAUDE.md exists.

- [ ] **Step 5: Commit**

```bash
git add src/
git commit -m "feat: complete init orchestrator with API keys and verification"
```

---

## Phase 9: Migration — Delete old harness

### Task 12: Remove Ink TUI harness

**Files:**
- Delete: `harness/` (entire directory)

- [ ] **Step 1: Delete harness directory**

```bash
rm -rf harness/
```

- [ ] **Step 2: Update root .gitignore if needed**

Remove any harness-specific entries.

- [ ] **Step 3: Commit**

```bash
git rm -r harness/
git commit -m "chore: remove old Ink TUI harness — replaced by npx by init"
```

---

## Phase 10: Integration testing

### Task 13: Create integration test suite

**Files:**
- Create: `tests/test_init.sh`
- Create: `tests/test_mcp_servers.sh`
- Create: `tests/test_claude_integration.mjs`

- [ ] **Step 1: Create init test**

`tests/test_init.sh` — runs `npx by-design init --skip-keys` in a temp dir, verifies all expected files exist.

- [ ] **Step 2: Create MCP server test**

`tests/test_mcp_servers.sh` — runs each MCP server with `uv run --script` and verifies it starts.

- [ ] **Step 3: Create Claude Code integration test**

`tests/test_claude_integration.mjs` — adapted from the existing test_5scenarios.mjs. Runs 5 scenarios through the Claude Code SDK with the generated environment.

- [ ] **Step 4: Run all tests**

```bash
bash tests/test_init.sh && bash tests/test_mcp_servers.sh && node tests/test_claude_integration.mjs
```

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: init, MCP server, and Claude Code integration tests"
```

---

## Task Dependency Graph

```
Task 1 (npm skeleton)
  └→ Task 2 (template system)
       └→ Task 3 (PEP 723 headers) ─────┐
       └→ Task 4 (cloud MCP server) ─────┤
       └→ Task 5 (knowledge MCP server) ─┤
       └→ Task 6 (9 agents) ─────────────┤
       └→ Task 7 (8 commands) ────────────┤
       └→ Task 8 (4 hooks) ──────────────┤
       └→ Task 9 (CLAUDE.md + config) ───┤
       └→ Task 10 (copy skills) ─────────┤
                                          ▼
                                    Task 11 (wire init)
                                          ▼
                                    Task 12 (delete harness)
                                          ▼
                                    Task 13 (integration tests)
```

Tasks 3-10 are **parallelizable** — they produce independent template files.
