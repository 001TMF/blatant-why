#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check dependencies
command -v node >/dev/null || { echo "Error: Node.js required"; exit 1; }
command -v python3 >/dev/null || { echo "Error: Python 3.11+ required"; exit 1; }

# Install if needed
[ -d "$SCRIPT_DIR/harness/node_modules" ] || (cd "$SCRIPT_DIR/harness" && npm install)
[ -d "$SCRIPT_DIR/.venv" ] || (python3 -m venv "$SCRIPT_DIR/.venv" && source "$SCRIPT_DIR/.venv/bin/activate" && pip install -e ".[dev,screening]")

cd "$SCRIPT_DIR/harness"
exec npx tsx src/index.ts "$@"
