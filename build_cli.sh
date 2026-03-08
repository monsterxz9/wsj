#!/bin/bash
# Build standalone CLI binary with PyInstaller

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_PYTHON="$PROJECT_ROOT/venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON}"
DIST_DIR="$PROJECT_ROOT/dist"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "✗ Python not found: $PYTHON_BIN"
    echo "  Tip: create venv first or set PYTHON_BIN=/path/to/python"
    exit 1
fi

echo "[1/2] Installing build tools..."
"$PYTHON_BIN" -m pip install --upgrade pyinstaller

echo "[2/2] Building standalone CLI..."
"$PYTHON_BIN" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --collect-data playwright_stealth \
    --name wsj-scraper-cli \
    "$PROJECT_ROOT/run_scraper.py"

echo ""
echo "✓ Build completed"
echo "  Binary: $DIST_DIR/wsj-scraper-cli"
