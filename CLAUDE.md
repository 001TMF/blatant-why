# CLAUDE.md — BY (Blatant-Why) Dev Context

## About This File

This file provides development-time context for working ON the BY codebase itself. The canonical agent identity is defined in `templates/CLAUDE.md`. During development, Claude works hands-on — editing code, running tests, managing git. For campaign-related behavior, see the template.

**Canonical identity:** `templates/CLAUDE.md` defines BY as a hands-on protein design agent who uses MCP tools directly. This root file must never contradict that identity.

## Dev Guidelines

Before making changes:
1. Analyze the existing codebase for relevant files, services, and patterns
2. Include specific file paths when scoping work
3. Default to **extending existing files** over creating new ones
4. If a new file is proposed, require justification for why existing code cannot be extended

## Git Workflow

- Create feature branches before starting work
- Review all output before staging
- Write clear commit messages summarizing what was done and why
- Never commit code that has not been reviewed

## Review Checklist

Before accepting any changes:
- [ ] Follows existing codebase patterns and architecture
- [ ] Reuses existing code where possible (no unnecessary new files)
- [ ] Meets the acceptance criteria
- [ ] No regressions or broken imports
- [ ] Clean, consistent with project style

## Reference: Campaign Agent Teams

These agent teams are defined in `templates/.claude/agents/`. See `templates/CLAUDE.md` for the canonical campaign workflow.

| Agent | Role | MCP Servers |
|-------|------|-------------|
| Research | Target analysis, literature, prior art | pdb, uniprot, sabdab, research |
| Design | Generate designs via cloud or local | pdb, screening, tamarind, campaign |
| Screening | Score, filter, rank designs | screening, campaign |
| Lab Integration | Submit to Adaptyv Bio (GATED) | adaptyv |

### Campaign Workflow
1. RESEARCH — spawn Research Agent for target analysis
2. COST ESTIMATE — compute costs (seeds x designs x scaffolds)
3. DESIGN — spawn Design Agent + start Monitor
4. SCREENING — spawn Screening Agent
5. RANKING — composite score, diversity selection
6. LAB (GATED) — only with explicit /approve-lab

## Reference: Compute Providers

1. **Tamarind Bio** (DEFAULT) — free tier, 200+ models, no GPU required
2. **Local GPU** — set PROTEUS_FOLD_DIR / PROTEUS_PROT_DIR / PROTEUS_AB_DIR (power users)

## Reference: Lab Safety Gate

Adaptyv Bio submissions require TRIPLE approval:
- Layer 1: MCP tool confirmation code (5-min TTL)
- Layer 2: Orchestrator checks campaignState.labApproved
- Layer 3: lab/approval.json file from TUI /approve-lab
NEVER bypass these gates, even with bypassPermissions.
