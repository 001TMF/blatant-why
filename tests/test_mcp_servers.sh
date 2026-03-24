#!/bin/bash
echo "=== MCP Server Startup Test ==="
PASS=0
FAIL=0
SKIP=0

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVERS_DIR="$SCRIPT_DIR/mcp_servers"

for dir in "$SERVERS_DIR"/*/; do
  name=$(basename "$dir")
  [ "$name" = "_shared" ] && continue

  server="$dir/server.py"
  [ ! -f "$server" ] && continue

  # Check if it has PEP 723 header
  if ! head -3 "$server" | grep -q "uv run"; then
    echo "  SKIP  $name (no PEP 723 header)"
    SKIP=$((SKIP+1))
    continue
  fi

  # Try to start it (will hang on stdin — kill after 5s)
  if timeout 10 uv run --script "$server" </dev/null 2>&1 | head -5 | grep -qi "error\|traceback\|modulenotfound"; then
    echo "  FAIL  $name"
    FAIL=$((FAIL+1))
  else
    echo "  PASS  $name"
    PASS=$((PASS+1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed, $SKIP skipped"
[ $FAIL -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
