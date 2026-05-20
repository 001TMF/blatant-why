#!/bin/bash
set -e
echo "=== BY Init Test ==="

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Run init with --skip-keys
cd "$TMPDIR"
node "$SCRIPT_DIR/dist/index.js" --skip-keys --force

# Verify core files exist
PASS=0
FAIL=0

check() {
  if [ -e "$1" ]; then
    echo "  PASS  $1"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $1"
    FAIL=$((FAIL+1))
  fi
}

echo ""
echo "Checking generated files..."
check "CLAUDE.md"
check ".by/config.json"
check ".claude/settings.json"

# Agents
for agent in research design screening campaign knowledge verifier plan-checker environment lab; do
  check ".claude/agents/by-${agent}.md"
done

# Commands
for cmd in watch status screen results load approve-lab set-profile setup; do
  check ".claude/commands/by/${cmd}.md"
done

# Hooks
check ".claude/hooks/hooks.json"
check ".claude/scripts/env-loader.js"
check ".claude/scripts/statusline.js"
check ".claude/scripts/safety-gate.js"
check ".claude/scripts/campaign-tracker.js"

# MCP servers (inside .claude/)
check ".claude/mcp_servers/pdb/server.py"
check ".claude/mcp_servers/uniprot/server.py"
check ".claude/mcp_servers/screening/server.py"
check ".claude/mcp_servers/knowledge/server.py"
check ".claude/mcp_servers/cloud/server.py"

# Skills — verify all 17 shipped skills exist
for skill in boltzgen protenix pxdesign \
             by-campaign-manager by-campaign-optimizer by-causal-reasoning \
             by-database by-deploy-compute by-design-workflow by-display \
             by-epitope-analysis by-experiment-results by-failure-diagnosis \
             by-hypothesis-debate by-knowledge by-research by-scoring \
             by-screening by-session; do
  check ".claude/skills/${skill}/SKILL.md"
done

# Settings.json has MCP servers
if grep -q "by-pdb" .claude/settings.json 2>/dev/null; then
  echo "  PASS  settings.json has MCP servers"
  PASS=$((PASS+1))
else
  echo "  FAIL  settings.json missing MCP servers"
  FAIL=$((FAIL+1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
