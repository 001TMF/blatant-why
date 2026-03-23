#!/usr/bin/env bash
set -e

echo "=== Proteus Environment Setup ==="
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js >= 18 required. Install from https://nodejs.org/"
    exit 1
fi
NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VER" -lt 18 ]; then
    echo "ERROR: Node.js >= 18 required (found v$NODE_VER)"
    exit 1
fi
echo "✓ Node.js $(node -v)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python >= 3.10 required"
    exit 1
fi
echo "✓ Python $(python3 --version)"

# Install Python deps
echo ""
echo "Installing Python dependencies..."
pip install pyyaml httpx mcp 2>/dev/null || pip install --user pyyaml httpx mcp
echo "✓ Python dependencies installed"

# Install Node deps
echo ""
echo "Installing Node.js dependencies..."
cd harness && npm install && cd ..
echo "✓ Node.js dependencies installed"

# Build harness
echo ""
echo "Building harness..."
cd harness && npx tsc && cd ..
echo "✓ Harness built"

# Check .env
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠ Please edit .env and add your API keys"
    echo "  At minimum, set TAMARIND_API_KEY (free at https://tamarind.bio)"
fi

# Check local tools
echo ""
echo "Checking local tools..."
for tool in PROTEUS_FOLD_DIR PROTEUS_PROT_DIR PROTEUS_AB_DIR; do
    val="${!tool}"
    if [ -n "$val" ] && [ -d "$val" ]; then
        echo "✓ $tool = $val"
    else
        echo "  $tool not set (cloud compute will be used)"
    fi
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start Proteus:"
echo "  cd harness && npm run dev"
echo ""
echo "Or run the built version:"
echo "  cd harness && npm start"
