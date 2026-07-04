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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/venv/Scripts/activate" ]]; then
  source "$REPO_ROOT/venv/Scripts/activate"
elif [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
  source "$REPO_ROOT/venv/bin/activate"
fi

RCC_BIN=""
if [[ -x "$REPO_ROOT/venv/Scripts/pyside6-rcc.exe" ]]; then
  RCC_BIN="$REPO_ROOT/venv/Scripts/pyside6-rcc.exe"
elif [[ -x "$REPO_ROOT/venv/Scripts/pyside6-rcc" ]]; then
  RCC_BIN="$REPO_ROOT/venv/Scripts/pyside6-rcc"
elif [[ -x "C:/Users/d_yut/AppData/Local/Programs/Python/Python313/Scripts/pyside6-rcc.exe" ]]; then
  RCC_BIN="C:/Users/d_yut/AppData/Local/Programs/Python/Python313/Scripts/pyside6-rcc.exe"
elif [[ -x "/mnt/c/Users/d_yut/AppData/Local/Programs/Python/Python313/Scripts/pyside6-rcc.exe" ]]; then
  RCC_BIN="/mnt/c/Users/d_yut/AppData/Local/Programs/Python/Python313/Scripts/pyside6-rcc.exe"
elif [[ -x "C:/Users/d_yut/AppData/Local/Programs/Python/Python313/Lib/site-packages/PySide6/rcc.exe" ]]; then
  RCC_BIN="C:/Users/d_yut/AppData/Local/Programs/Python/Python313/Lib/site-packages/PySide6/rcc.exe"
elif [[ -x "/mnt/c/Users/d_yut/AppData/Local/Programs/Python/Python313/Lib/site-packages/PySide6/rcc.exe" ]]; then
  RCC_BIN="/mnt/c/Users/d_yut/AppData/Local/Programs/Python/Python313/Lib/site-packages/PySide6/rcc.exe"
elif [[ -x "C:\\Users\\d_yut\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\pyside6-rcc.exe" ]]; then
  RCC_BIN="C:\\Users\\d_yut\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\pyside6-rcc.exe"
elif command -v pyside6-rcc >/dev/null 2>&1; then
  RCC_BIN="$(command -v pyside6-rcc)"
fi

if [[ -z "$RCC_BIN" ]]; then
  echo "pyside6-rcc could not be found. Install PySide6 and try again." >&2
  exit 1
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  scripts/macos/create-icons.sh
  echo "Generated icns file for macOS"
  ls -al
fi

cd "$REPO_ROOT/res"
qrc="resources.qrc"
"$RCC_BIN" --project -o "$qrc"
OUTPUT_PY="../src/fk/desktop/resources.py"
"$RCC_BIN" -g python "$qrc" -o "$OUTPUT_PY"
rm "$qrc"
