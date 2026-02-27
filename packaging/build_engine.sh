#!/bin/bash
set -euo pipefail

# Build the standalone Python engine for embedding in the Mac app.
#
# Prerequisites:
#   pip install pyinstaller   (or: uv pip install pyinstaller)
#
# Usage:
#   ./packaging/build_engine.sh
#
# Output:
#   dist/longview-engine/          -- standalone engine directory
#   Also copied to: macos/LongviewHealth/LongviewHealth/Resources/longview-engine/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RESOURCES_DIR="$PROJECT_ROOT/macos/LongviewHealth/LongviewHealth/Resources"

cd "$PROJECT_ROOT"

# Use the project venv's pyinstaller if available
if [ -x ".venv/bin/pyinstaller" ]; then
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYINSTALLER="pyinstaller"
fi

echo "==> Building standalone Python engine..."
"$PYINSTALLER" packaging/longview.spec \
    --distpath dist/ \
    --workpath build/pyinstaller/ \
    --noconfirm

echo "==> Verifying build..."
if [ ! -f "dist/longview-engine/longview" ]; then
    echo "ERROR: Build failed -- dist/longview-engine/longview not found"
    exit 1
fi

# Quick smoke test
echo "==> Smoke test..."
dist/longview-engine/longview --version

echo "==> Copying to Xcode resources..."
mkdir -p "$RESOURCES_DIR"
rm -rf "$RESOURCES_DIR/longview-engine"
cp -R dist/longview-engine "$RESOURCES_DIR/longview-engine"

echo "==> Done!"
echo "    Engine: dist/longview-engine/"
echo "    Xcode:  $RESOURCES_DIR/longview-engine/"
echo ""
echo "    Build the app in Xcode to include the engine in the .app bundle."
