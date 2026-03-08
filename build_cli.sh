#!/bin/bash
# Build standalone CLI binary with PyInstaller

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_PYTHON="$PROJECT_ROOT/venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON}"
DIST_DIR="$PROJECT_ROOT/dist"
MODE="${1:---onefile}"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "✗ Python not found: $PYTHON_BIN"
    echo "  Tip: create venv first or set PYTHON_BIN=/path/to/python"
    exit 1
fi

case "$MODE" in
    --onefile|--onedir)
        ;;
    *)
        echo "Usage: $0 [--onefile|--onedir]"
        echo "  --onefile  Single file binary (smaller distribution, slower startup)"
        echo "  --onedir   Directory build (larger output, faster startup)"
        exit 1
        ;;
esac

echo "[1/2] Installing build tools..."
"$PYTHON_BIN" -m pip install --upgrade pyinstaller

echo "[2/2] Building standalone CLI..."
if [ "$MODE" = "--onefile" ]; then
    rm -rf "$DIST_DIR/wsj-scraper-cli"
    "$PYTHON_BIN" -m PyInstaller \
        --noconfirm \
        --clean \
        --onefile \
        --collect-data playwright_stealth \
        --name wsj-scraper-cli \
        "$PROJECT_ROOT/run_scraper.py"
else
    rm -rf "$DIST_DIR/wsj-scraper-cli-fast"
    "$PYTHON_BIN" -m PyInstaller \
        --noconfirm \
        --clean \
        --onedir \
        --collect-data playwright_stealth \
        --name wsj-scraper-cli-fast \
        "$PROJECT_ROOT/run_scraper.py"
fi

echo ""
echo "✓ Build completed"
if [ "$MODE" = "--onefile" ]; then
    echo "  Binary: $DIST_DIR/wsj-scraper-cli"
    echo "  Note: onefile startup is slower due to temporary extraction"
else
    echo "  Binary: $DIST_DIR/wsj-scraper-cli-fast/wsj-scraper-cli-fast"
    echo "  Note: onedir startup is faster"
fi
