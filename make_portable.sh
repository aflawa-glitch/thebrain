#!/usr/bin/env bash
set -Eeuo pipefail

# Accept app name as an argument, default to 'thebrain'
APP_NAME="${1:-thebrain}"

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PY313="$SOURCE/runtimes/python/macos-arm64/python313/bin/python3.13"
VENV_DIR="$SOURCE/environments/$APP_NAME"
APP_DIR="$SOURCE/apps/$APP_NAME"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ ERROR: App folder not found at $APP_DIR"
    exit 1
fi

echo "=== Making $APP_NAME Portable at: $SOURCE ==="

echo "1. Rebuilding Venv at new location..."
rm -rf "$VENV_DIR"
"$PY313" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "2. Updating config paths..."
VENV_PY="$VENV_DIR/bin/python"
cd "$APP_DIR"
"$VENV_PY" - <<PYEOF
import pathlib
p = pathlib.Path("config/local-model.env")
if p.exists():
    text = p.read_text()
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        if line.startswith("JULIAN_STORAGE_ROOT="):
            new_lines.append('JULIAN_STORAGE_ROOT="$SOURCE"')
        elif line.startswith("JULIAN_PYTHON="):
            new_lines.append('JULIAN_PYTHON="$VENV_PY"')
        else:
            new_lines.append(line)
    p.write_text("\n".join(new_lines) + "\n")
PYEOF

echo "✅ DONE! $APP_NAME is portable and ready to run from $SOURCE"
