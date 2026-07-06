#!/usr/bin/env bash

#
# Flowkeeper - Pomodoro timer for power users and teams
# Copyright (c) 2023 Constantine Kulak
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

set -e

# Resolve project root directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Step 0 - Check Python version (needs 3.10+ for `str | None` syntax)
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    for py in python3.13 python3.12 python3.11 python3.10; do
        if command -v "$py" &>/dev/null; then
            PYTHON_BIN="$py"
            break
        fi
    done
fi
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    echo "ERROR: Python 3.10+ is required. Install with: brew install python@3.12"
    exit 1
fi
echo "Using Python: $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))"

# Step 1 - Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo ">>> Creating virtual environment with $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
VENV_PIP="$PROJECT_ROOT/venv/bin/pip"
PYSIDE6_RCC="$PROJECT_ROOT/venv/bin/pyside6-rcc"

# Step 2 - Install dependencies if PySide6 or nuitka is missing
if ! "$VENV_PYTHON" -c "import PySide6" 2>/dev/null || ! "$VENV_PYTHON" -c "import nuitka" 2>/dev/null; then
    echo ">>> Installing dependencies..."
    "$VENV_PIP" install -r requirements.txt nuitka
fi

# Step 3 - Generate app icon (flowkeeper.icns)
if [ ! -f "flowkeeper.icns" ]; then
    echo ">>> Generating app icon (flowkeeper.icns)..."
    bash scripts/macos/create-icons.sh
fi

# Step 4 - Generate resources.py (Qt resources compiled with pyside6-rcc)
if [ ! -f "src/fk/desktop/resources.py" ]; then
    echo ">>> Generating resources.py..."
    cd res
    "$PYSIDE6_RCC" --project -o resources.qrc
    "$PYSIDE6_RCC" -g python resources.qrc -o ../src/fk/desktop/resources.py
    rm -f resources.qrc
    cd "$PROJECT_ROOT"
fi

# Step 5 - Cleanup previous build artifacts
echo ">>> Cleaning previous build..."
rm -rf build dist Flowkeeper.dmg

FK_VERSION=$(bash scripts/common/get-version.sh)
echo ">>> Building Flowkeeper v$FK_VERSION..."

# Step 6 - Build the app bundle with Nuitka (unsigned)
echo ">>> Compiling with Nuitka (this may take several minutes)..."
PYTHONPATH=src "$VENV_PYTHON" -m nuitka \
  --standalone \
  --enable-plugin=pyside6 \
  --macos-app-icon=flowkeeper.icns \
  --macos-create-app-bundle \
  --macos-signed-app-name=org.flowkeeper.Flowkeeper \
  --macos-app-version="$FK_VERSION" \
  --macos-app-name=Flowkeeper \
  --product-name=Flowkeeper \
  --product-version="$FK_VERSION" \
  --no-deployment-flag=site-builtins \
  --output-dir=build \
  --output-file=Flowkeeper \
  src/fk/desktop/desktop.py

# Step 7 - Move app bundle to dist/standalone
echo ">>> Moving app bundle to dist/standalone/..."
rm -rf dist/standalone
mkdir -p dist/standalone
mv build/desktop.app dist/standalone/Flowkeeper.app

# Step 8 - Remove quarantine attributes so the app can be opened without signing
echo ">>> Removing quarantine attributes..."
xattr -cr dist/standalone/Flowkeeper.app

# Step 9 - Create a DMG image
echo ">>> Creating DMG..."
create-dmg \
  --volname "Flowkeeper Installer" \
  --volicon "flowkeeper.icns" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "Flowkeeper.app" 200 190 \
  --hide-extension "Flowkeeper.app" \
  --app-drop-link 600 185 \
  "Flowkeeper.dmg" \
  "dist/standalone"

# Remove quarantine from the DMG as well
xattr -cr "Flowkeeper.dmg" 2>/dev/null || true

echo ""
echo "============================================"
echo "  Build complete!"
echo "  DMG:  $PROJECT_ROOT/Flowkeeper.dmg"
echo "  App:  $PROJECT_ROOT/dist/standalone/Flowkeeper.app"
echo "  Version: $FK_VERSION"
echo "============================================"
echo ""
echo "Note: The app is ad-hoc signed (not notarized)."
echo "If macOS blocks it, right-click the app -> Open, or run:"
echo "  xattr -cr dist/standalone/Flowkeeper.app"
