#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

find_iscc() {
  local candidates=()
  if [[ -n "${ISCC_EXE:-}" ]]; then
    candidates+=("$ISCC_EXE")
  fi
  if [[ -n "${LOCALAPPDATA:-}" ]]; then
    candidates+=("$LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe")
  fi
  if [[ -n "${USERPROFILE:-}" ]]; then
    candidates+=("$USERPROFILE/AppData/Local/Programs/Inno Setup 6/ISCC.exe")
  fi
  candidates+=("/c/Program Files/Inno Setup 6/ISCC.exe" "/c/Program Files (x86)/Inno Setup 6/ISCC.exe")

  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v py >/dev/null 2>&1; then
  PYTHON_BIN='py -3'
else
  echo "Python is not available in PATH." >&2
  exit 1
fi

if [[ ! -d "$REPO_ROOT/venv" ]]; then
  if [[ "$PYTHON_BIN" == 'py -3' ]]; then
    eval "$PYTHON_BIN -m venv venv"
  else
    "$PYTHON_BIN" -m venv venv
  fi
fi

if [[ -f "$REPO_ROOT/venv/Scripts/activate" ]]; then
  source "$REPO_ROOT/venv/Scripts/activate"
elif [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
  source "$REPO_ROOT/venv/bin/activate"
fi

if [[ "$PYTHON_BIN" == 'py -3' ]]; then
  eval "$PYTHON_BIN -m pip install --upgrade pip setuptools wheel"
  eval "$PYTHON_BIN -m pip install -r requirements.txt pyinstaller"
else
  "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
  "$PYTHON_BIN" -m pip install -r requirements.txt pyinstaller
fi

bash "$REPO_ROOT/scripts/common/generate-resources.sh"

rm -rf build dist
mkdir -p build dist/standalone

if [[ "$PYTHON_BIN" == 'py -3' ]]; then
  eval "$PYTHON_BIN -m PyInstaller scripts/common/pyinstaller/portable.spec --distpath=build"
  eval "$PYTHON_BIN -m PyInstaller scripts/common/pyinstaller/normal.spec --distpath=build"
else
  "$PYTHON_BIN" -m PyInstaller scripts/common/pyinstaller/portable.spec --distpath=build
  "$PYTHON_BIN" -m PyInstaller scripts/common/pyinstaller/normal.spec --distpath=build
fi

mkdir -p dist/standalone
if [[ -d "$REPO_ROOT/build/flowkeeper" ]]; then
  cp -r "$REPO_ROOT/build/flowkeeper/." "$REPO_ROOT/dist/standalone/"
fi
if [[ -f "$REPO_ROOT/build/Flowkeeper.exe" ]]; then
  cp "$REPO_ROOT/build/Flowkeeper.exe" "$REPO_ROOT/dist/standalone/Flowkeeper.exe"
fi

export FK_REPO_ROOT="$REPO_ROOT"
export FK_VERSION="1.0.0"

ISCC_EXE="$(find_iscc || true)"
if [[ -z "$ISCC_EXE" ]]; then
  echo "Inno Setup not found; installing it now..."
  bash "$REPO_ROOT/scripts/windows/install-innosetup.sh"
  ISCC_EXE="$(find_iscc || true)"
fi

if [[ -z "$ISCC_EXE" ]]; then
  echo "Inno Setup is still not available. Please install it manually and rerun the script." >&2
  exit 1
fi

"$ISCC_EXE" "$REPO_ROOT/scripts/windows/windows-installer.iss"

installer_candidates=(
  "$REPO_ROOT/dist/mysetup.exe"
  "$REPO_ROOT/dist/setup.exe"
  "$REPO_ROOT/scripts/windows/dist/mysetup.exe"
  "$REPO_ROOT/scripts/windows/dist/setup.exe"
)

for candidate in "${installer_candidates[@]}"; do
  if [[ -f "$candidate" ]]; then
    cp "$candidate" "$REPO_ROOT/dist/setup.exe"
    echo "Windows installer created at $REPO_ROOT/dist/setup.exe"
    exit 0
  fi
done

echo "Installer build finished, but the expected output file was not found." >&2
exit 1
