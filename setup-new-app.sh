#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${1:-}"
APP_PORT="${2:-}" # Optional port argument

if [ -z "$APP_NAME" ]; then
    echo "❌ Usage: ./setup-new-app.sh <app_name> [port]"
    echo "Example: ./setup-new-app.sh mrpsystem 8090"
    exit 1
fi

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PY313="$SOURCE/runtimes/python/macos-arm64/python313/bin/python3.13"
APP_DIR="$SOURCE/apps/$APP_NAME"
ENV_DIR="$SOURCE/environments/$APP_NAME"

if [ ! -d "$APP_DIR" ]; then
    echo "❌ ERROR: App folder not found at $APP_DIR"
    echo "Please copy your app code into apps/$APP_NAME first."
    exit 1
fi

echo "🏗️  Setting up environment for: $APP_NAME"

# 1. Create Venv
echo "1. Creating isolated venv..."
rm -rf "$ENV_DIR"
"$PY313" -m venv "$ENV_DIR"

# 2. Install dependencies
if [ -f "$APP_DIR/requirements.txt" ]; then
    echo "2. Installing dependencies..."
    "$ENV_DIR/bin/pip" install -q --upgrade pip
    "$ENV_DIR/bin/pip" install -q -r "$APP_DIR/requirements.txt"
else
    echo "⚠️  Warning: No requirements.txt found in $APP_DIR. Skipping pip install."
fi

# 3. Generate config
echo "3. Generating config/local-model.env..."
mkdir -p "$APP_DIR/config"
CONFIG_FILE="$APP_DIR/config/local-model.env"

# If no port provided, try to guess one based on existing envs, or default to 8090
if [ -z "$APP_PORT" ]; then
    APP_PORT=8090
    while grep -rq "JULIAN_PORT=\"$APP_PORT\"" "$SOURCE/apps"/*/config/local-model.env 2>/dev/null; do
        ((APP_PORT++))
    done
fi

VENV_PY="$ENV_DIR/bin/python"

cat > "$CONFIG_FILE" <<CONFIG
# Auto-generated config for $APP_NAME
JULIAN_STORAGE_ROOT="$SOURCE"
JULIAN_PYTHON="$VENV_PY"
JULIAN_HOST="127.0.0.1"
JULIAN_PORT="$APP_PORT"
JULIAN_LLM_BASE_URL="http://127.0.0.1:8081/v1"
JULIAN_LLM_API_KEY="not-needed"
JULIAN_LLM_ENABLED="true"
CONFIG

echo "✅ DONE! $APP_NAME is ready."
echo "📂 Port: $APP_PORT"
echo "▶️  To start it, run: ./start-app.sh $APP_NAME"
