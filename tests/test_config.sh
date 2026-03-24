#!/bin/bash
echo "=== Config System Test ==="
PASS=0
FAIL=0

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SCRIPT_DIR/templates/.by/config.json"

# Valid JSON
if python3 -c "import json; json.load(open('$CONFIG'))" 2>/dev/null; then
  echo "  PASS  config.json is valid JSON"
  PASS=$((PASS+1))
else
  echo "  FAIL  config.json is invalid JSON"
  FAIL=$((FAIL+1))
fi

# Has model_profile
if python3 -c "import json; d=json.load(open('$CONFIG')); assert d['model_profile'] in ('quality','balanced','budget')" 2>/dev/null; then
  echo "  PASS  model_profile is valid"
  PASS=$((PASS+1))
else
  echo "  FAIL  model_profile missing or invalid"
  FAIL=$((FAIL+1))
fi

# Has compute section
if python3 -c "import json; d=json.load(open('$CONFIG')); assert 'compute' in d" 2>/dev/null; then
  echo "  PASS  compute section exists"
  PASS=$((PASS+1))
else
  echo "  FAIL  compute section missing"
  FAIL=$((FAIL+1))
fi

# CLAUDE.md exists and is substantial
CLAUDEMD="$SCRIPT_DIR/templates/CLAUDE.md"
LINES=$(wc -l < "$CLAUDEMD" 2>/dev/null || echo 0)
if [ "$LINES" -gt 100 ]; then
  echo "  PASS  CLAUDE.md has $LINES lines"
  PASS=$((PASS+1))
else
  echo "  FAIL  CLAUDE.md too short ($LINES lines)"
  FAIL=$((FAIL+1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
