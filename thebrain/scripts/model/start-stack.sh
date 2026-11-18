#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="$ROOT/config/local-model.env"
[[ -f "$CONFIG" ]] || { echo "Missing $CONFIG. Copy config/local-model.env.example and set the actual Qwen/llama.cpp paths." >&2; exit 2; }
set -a
# shellcheck disable=SC1090
source "$CONFIG"
set +a
if [[ -z "${JULIAN_STORAGE_ROOT:-}" ]]; then JULIAN_STORAGE_ROOT="$(cd "$ROOT/.." && pwd)"; fi
JULIAN_STORAGE_ROOT="$(cd "$JULIAN_STORAGE_ROOT" && pwd)"
export JULIAN_STORAGE_ROOT
export JULIAN_RUNTIME_HOME="${JULIAN_RUNTIME_HOME:-$JULIAN_STORAGE_ROOT/.julian-runtime}"
export JULIAN_DATA_DIR="${JULIAN_DATA_DIR:-$JULIAN_STORAGE_ROOT/data/julian}"
export JULIAN_DATABASE_PATH="${JULIAN_DATABASE_PATH:-$JULIAN_DATA_DIR/julian.sqlite3}"
export JULIAN_LLM_BASE_URL="${JULIAN_LLM_BASE_URL:-http://127.0.0.1:${JULIAN_LLM_PORT:-8081}/v1}"
export JULIAN_LLM_MODEL="${JULIAN_LLM_MODEL:-qwen-local}"
export JULIAN_LLM_ENABLED="${JULIAN_LLM_ENABLED:-true}"
"$ROOT/scripts/model/start-model.sh"
echo "Starting Julian API on ${JULIAN_HOST:-127.0.0.1}:${JULIAN_PORT:-8080}"
echo "Storage root: $JULIAN_STORAGE_ROOT"
echo "Data directory: $JULIAN_DATA_DIR"
exec "$ROOT/julianrebuild.sh" run
